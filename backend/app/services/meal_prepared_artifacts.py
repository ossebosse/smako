"""Bounded, durable preparation of public content; never cache purchase approval."""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from app.services.meal_library_content import atomic_write, digest, encoded

SCHEMA = "smako-recipe-preparation-v1"
MAX_GENERATIONS = 8
MAX_BYTES = 32 * 1024 * 1024
STATS = {"hits":0,"misses":0,"writes":0,"invalid":0}


def root():
    from app.config import get_settings
    configured = os.environ.get("RECIPE_PREPARATION_CACHE_ROOT")
    return Path(configured) if configured else get_settings().plan_store_path.parent / "recipe_prepared"


@lru_cache(maxsize=1)
def method_signature():
    base = Path(__file__).parents[1]
    paths = [base / "models/recipe.py", base / "services/recipe_library.py",
             base / "services/recipe_preparation.py", base / "services/ingredient_normalizer.py",
             base / "services/personal_source_facts.py", base / "services/personal_policy.py",
             base / "services/declaration_semantics.py"]
    return digest(encoded({str(p.relative_to(base)):digest(p.read_bytes()) for p in paths}))


def prepared(kind, identity, compute):
    """Reject partial/wrong version artefacts and safely recompute on any cache fault."""
    key = digest(encoded([SCHEMA,kind,identity,method_signature()]))
    directory = root() / kind
    path = directory / (key + ".json")
    try:
        if path.stat().st_size > MAX_BYTES:
            raise ValueError("Prepared artifact too large")
        envelope = json.loads(path.read_bytes())
        if envelope["schema"] != SCHEMA or envelope["key"] != key:
            raise ValueError("Prepared artifact signature mismatch")
        payload = envelope["payload"]
        if digest(encoded(payload)) != envelope["sha256"]:
            raise ValueError("Prepared artifact payload hash mismatch")
        STATS["hits"] += 1
        return payload
    except FileNotFoundError:
        pass
    except (OSError,ValueError,KeyError,TypeError):
        STATS["invalid"] += 1
    STATS["misses"] += 1
    payload = compute()
    data = encoded({"schema":SCHEMA,"key":key,"payload":payload,"sha256":digest(encoded(payload))})
    try:
        directory.mkdir(parents=True,exist_ok=True)
        # Existing generation evidence is retained. At the bounded capacity,
        # continue safely in memory rather than growing disk indefinitely.
        existing = list(directory.glob("*.json"))
        limit = 4096 if kind == "content" else MAX_GENERATIONS
        total_bytes = sum(p.stat().st_size for p in existing)
        if (len(data) <= MAX_BYTES and total_bytes + len(data) <= MAX_BYTES
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
    inventory = [p.model_dump(mode="json") for p in universe.products]
    identity = [universe.universe_id, digest(encoded(inventory)), version]
    def compute():
        return {str(i):food_class for i,product in enumerate(universe.products)
                if (food_class := declaration_food_class(product,source_facts(product)))}
    value = prepared("declarations",identity,compute)
    if not all(str(k).isdigit() and 0 <= int(k) < len(universe.products) and isinstance(v,str)
               for k,v in value.items()):
        raise ValueError("Prepared declaration index has invalid operands")
    return {int(k):v for k,v in value.items()}
