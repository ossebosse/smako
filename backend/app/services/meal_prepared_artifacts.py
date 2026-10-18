"""Bounded, durable preparation of public content; never cache purchase approval."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import zlib
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType

from app.services.meal_library_content import atomic_write, digest, encoded

SCHEMA = "smako-recipe-preparation-v2"
MAX_GENERATIONS = 8
MAX_BYTES = 32 * 1024 * 1024
STATS = {"hits":0,"misses":0,"writes":0,"invalid":0}


def ingredient_search_positions(prepared_universe, name, *, complete):
    """Share existing text/alias retrieval; all qualification remains live."""
    from app.services.ingredient_normalizer import CANONICAL_ALIASES, canonicalize_ingredient_name
    from app.services.product_search import ProductSearchRequest
    canonical = canonicalize_ingredient_name(name)
    aliases = tuple(dict.fromkeys((name, *CANONICAL_ALIASES.get(canonical, ())))) if complete else (name,)
    if complete:
        common = prepare_ingredient_search(prepared_universe)
        if name in common:
            return common[name]
    key = "recipe-search:" + digest(payload_bytes([aliases, method_signature()]))

    def compute():
        index = prepared_universe.product_search_index
        matches = set()
        for alias in aliases:
            found, _, _ = index.retrieve(ProductSearchRequest(query=alias))
            matches.update(i for k in found for i in index.groups[k])
        return frozenset(matches)

    return prepared_universe.product_search_cache.get_or_compute(key, compute)


def prepare_ingredient_search(prepared_universe):
    """Prepare library ingredient retrieval on the existing artifact path.

    The persisted payload contains public product positions only. Stores,
    complete inventory, exact aliases and method code bind both hits and
    absences. A replacement universe owns a fresh in-memory cache.
    """
    from app.services.ingredient_normalizer import CANONICAL_ALIASES, canonicalize_ingredient_name
    from app.services.product_search import ProductSearchRequest
    from app.services.recipe_library import _registered, library_version
    key = "recipe-ingredient-index:" + digest(payload_bytes([
        library_version(), CANONICAL_ALIASES, method_signature()]))

    def load():
        names = sorted({canonicalize_ingredient_name(i.name)
                        for r in _registered() for i in r.ingredients})
        queries = {name: tuple(dict.fromkeys((name, *CANONICAL_ALIASES.get(name, ()))))
                   for name in names}
        inventory = hashlib.sha256()
        for product in prepared_universe.universe.products:
            inventory.update(product.model_dump_json().encode())
            inventory.update(b"\n")
        identity = [prepared_universe.universe.universe_id, inventory.hexdigest(),
                    [s.model_dump(mode="json") for s in prepared_universe.stores], queries]

        def compute():
            index = prepared_universe.product_search_index
            rows = {}
            for name, aliases in queries.items():
                positions = set()
                for alias in aliases:
                    found, _, _ = index.retrieve(ProductSearchRequest(query=alias))
                    positions.update(i for k in found for i in index.groups[k])
                rows[name] = sorted(positions)
            return rows

        rows = prepared("ingredient-search", identity, compute)
        valid = (isinstance(rows, dict) and set(rows) == set(names)
                 and all(isinstance(values, list) and all(type(i) is int and
                     0 <= i < len(prepared_universe.universe.products) for i in values)
                         for values in rows.values()))
        if not valid:
            STATS["invalid"] += 1
            rows = compute()
        return MappingProxyType({name: frozenset(values) for name, values in rows.items()})

    return prepared_universe.product_search_cache.get_or_compute(key, load)


def payload_bytes(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",", ":")).encode()


def decode_payload(envelope):
    if envelope.get("encoding") == "zlib-json-v1":
        compressed = base64.b64decode(envelope["payload"],validate=True)
        decoder = zlib.decompressobj()
        raw = decoder.decompress(compressed,128 * 1024 * 1024 + 1)
        if len(raw) > 128 * 1024 * 1024 or not decoder.eof or decoder.unused_data:
            raise ValueError("Prepared payload exceeds expansion limit or is incomplete")
        if digest(raw) != envelope["sha256"]:
            raise ValueError("Prepared artifact payload hash mismatch")
        return json.loads(raw)
    if envelope.get("encoding") != "json-v1":
        raise ValueError("Unknown prepared payload encoding")
    payload = envelope["payload"]
    if digest(payload_bytes(payload)) != envelope["sha256"]:
        raise ValueError("Prepared artifact payload hash mismatch")
    return payload


def root():
    from app.config import get_settings
    configured = os.environ.get("RECIPE_PREPARATION_CACHE_ROOT")
    return Path(configured) if configured else get_settings().plan_store_path.parent / "recipe_prepared"


@lru_cache(maxsize=1)
def method_signature():
    base = Path(__file__).parents[1]
    repository = Path(__file__).parents[3]
    # Conservative code invalidation also binds authoritative declaration
    # adapters and model changes. Content-only imports keep this signature.
    paths = [*base.joinpath("models").glob("*.py"),*base.joinpath("services").glob("*.py"),
             *base.joinpath("data/nutrition").glob("*.json"),
             repository / "grocery_data/app/data/product_declarations.json",
             repository / "grocery_data/app/services/product_declarations.py"]
    return digest(encoded({p.relative_to(repository).as_posix():digest(p.read_bytes())
                           for p in sorted(paths)}))


def prepared(kind, identity, compute, *, storable=None):
    """Reject partial/wrong version artefacts and safely recompute on any cache fault.

    ``storable`` is asked after ``compute``; when it returns False the result
    is returned but never written (e.g. a projection that hit a read error).
    """
    key = digest(encoded([SCHEMA,kind,identity,method_signature()]))
    directory = root() / kind
    path = directory / (key + ".json")
    try:
        if path.stat().st_size > MAX_BYTES:
            raise ValueError("Prepared artifact too large")
        envelope = json.loads(path.read_bytes())
        if envelope["schema"] != SCHEMA or envelope["key"] != key:
            raise ValueError("Prepared artifact signature mismatch")
        payload = decode_payload(envelope)
        STATS["hits"] += 1
        return payload
    except FileNotFoundError:
        pass
    except (OSError,ValueError,KeyError,TypeError,zlib.error):
        STATS["invalid"] += 1
    STATS["misses"] += 1
    payload = compute()
    if storable is not None and not storable():
        STATS["unstorable"] = STATS.get("unstorable", 0) + 1
        return payload
    raw = payload_bytes(payload)
    compressed = len(raw) > 256 * 1024
    data = payload_bytes({"schema":SCHEMA,"key":key,"payload":
        base64.b64encode(zlib.compress(raw,1)).decode() if compressed else payload,
        "encoding":"zlib-json-v1" if compressed else "json-v1", "sha256":digest(raw)})
    try:
        directory.mkdir(parents=True,exist_ok=True)
        # Existing generation evidence is retained. At the bounded capacity,
        # continue safely in memory rather than growing disk indefinitely.
        existing = list(directory.glob("*.json"))
        limit = 4096 if kind == "content" else MAX_GENERATIONS
        total_bytes = sum(p.stat().st_size for p in existing)
        if (len(raw) <= 128 * 1024 * 1024 and len(data) <= MAX_BYTES and total_bytes + len(data) <= MAX_BYTES
                and (path.exists() or len(existing) < limit)):
            atomic_write(path,data)
            STATS["writes"] += 1
    except OSError:
        pass  # read-only deployments still use the ordinary checked calculation
    return payload


def prepare_content(recipes):
    from app.services.meal_library_content import identity
    from app.services.recipe_library import _structural_check, ingredient_key
    index = {}
    for recipe in recipes:
        key = identity(recipe)
        def compute(recipe=recipe, key=key):
            _structural_check(recipe)
            return {"identity":key,"content_sha256":recipe.design.content_sha256,
                    "ingredients":[ingredient_key(i) for i in recipe.ingredients],
                    "meal_types":list(recipe.design.meal_types),
                    "ingredient_count":recipe.design.ingredient_count}
        row = prepared("content",recipe.model_dump(mode="json"),compute)
        # Cache provenance never substitutes for the issued content registry.
        if row["identity"] != key or row["content_sha256"] != recipe.design.content_sha256:
            raise ValueError("Prepared content identity mismatch")
        for ingredient in row["ingredients"]:
            index.setdefault(ingredient,[]).append(key)
    return {"schema":SCHEMA,"method_signature":method_signature(),"dependencies":index,"stats":dict(STATS)}


def declaration_index(universe, facts, source_facts):
    """Snapshot/fact-bound declaration classes shared across meal types/requests.

    Includes the full product inventory: a previously missing product invalidates
    negative results. Prices/terms/date/owner approval are never stored here.
    """
    from app.services.declaration_semantics import declaration_food_class
    from app.services.personal_source_facts import facts_version
    version = getattr(facts,"version",None) or facts_version(facts)
    # The prepared universe also contains large search indexes. Classification
    # depends on the exact product inventory and facts, not those derived indexes.
    inventory = hashlib.sha256()
    # Hash every exact product row without building a second large Python/JSON
    # inventory tree. Order and all fields still bind additions and negatives.
    for product in universe.products:
        inventory.update(product.model_dump_json().encode())
        inventory.update(b"\n")
    identity = [universe.universe_id, inventory.hexdigest(), version]
    def compute():
        return {str(i):food_class for i,product in enumerate(universe.products)
                if (food_class := declaration_food_class(product,source_facts(product)))}
    value = prepared("declarations",identity,compute)
    if not all(str(k).isdigit() and 0 <= int(k) < len(universe.products) and isinstance(v,str)
               for k,v in value.items()):
        raise ValueError("Prepared declaration index has invalid operands")
    return {int(k):v for k,v in value.items()}
