"""Bounded, rebuildable public preparation; never cache purchase approval."""
from __future__ import annotations

import base64
import hashlib
import heapq
import json
import os
import re
import zlib
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import lru_cache
from itertools import islice
from pathlib import Path
from types import MappingProxyType
from uuid import uuid4

from app.services.meal_library_content import atomic_write, digest, encoded

SCHEMA = "smako-recipe-preparation-v2"
MAX_GENERATIONS = 8
MAX_BYTES = 32 * 1024 * 1024
CONTENT_LIMIT = 4096
STATS = {"hits":0,"misses":0,"writes":0,"invalid":0}


@dataclass
class _ContentWriteBudget:
    directory: Path
    count: int
    size: int
    writable: bool = True
    lease: object = None
    retirement: list | None = None

    def write(self, path, data, raw_size):
        if not self.writable or path.parent != self.directory:
            if self.lease is not None:
                self.lease.failures += 1
            return
        if self.lease is not None:
            _retaining_write(self, path, data, raw_size)
            return
        try:
            old_size = path.stat().st_size
        except FileNotFoundError:
            old_size = None
        limit = CONTENT_LIMIT if self.directory.name == "content" else MAX_GENERATIONS
        if (raw_size > 128 * 1024 * 1024 or len(data) > MAX_BYTES
                or (old_size is None and self.count >= limit)
                or self.size - (old_size or 0) + len(data) > MAX_BYTES):
            return
        atomic_write(path, data)
        self.count += old_size is None
        self.size += len(data) - (old_size or 0)
        STATS["writes"] += 1


@contextmanager
def _content_write_batch():
    """Count disk usage once while holding the content writer's OS lock.

    Contention/read-only storage uses ordinary checked computation without
    writing. The lock covers the entire batch, including byte/count updates;
    another cooperating process must rescan after acquiring its own lease.
    No process-global usage snapshot can hide another writer or a removed file.
    """
    directory = root() / "content"
    budget = _ContentWriteBudget(directory, 0, 0, writable=False, lease=_shared_generation.get())
    handle = None
    try:
        directory.mkdir(parents=True, exist_ok=True)
        handle = (directory / ".preparation-write.lock").open("a+b")
        if os.name == "nt":
            import msvcrt

            if handle.seek(0, 2) == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        with os.scandir(directory) as entries:
            for entry in entries:
                if entry.name.endswith(".json"):
                    budget.count += 1
                    budget.size += entry.stat().st_size
        budget.writable = True
        if budget.lease is not None:
            _retire_interrupted_writes(directory, budget.lease)
    except OSError:
        pass
    try:
        yield budget
    finally:
        if handle is not None:
            handle.close()  # Both platforms release the OS lock on close.



@dataclass
class _SharedGeneration:
    cache_root: Path
    identity: str
    token: str
    writable: bool = False
    failures: int = 0
    ready: bool = False
    requested: set = field(default_factory=set)


_shared_generation: ContextVar = ContextVar("shared_recipe_preparation_generation", default=None)


@contextmanager
def _cache_lock(path):
    handle = None
    acquired = False
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle = path.open("a+b")
        if os.name == "nt":
            import msvcrt
            if handle.seek(0, 2) == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        acquired = True
    except OSError:
        pass
    try:
        yield acquired
    finally:
        if handle is not None:
            handle.close()


def _generation_state(cache_root):
    try:
        path = cache_root / ".shared-generation.json"
        if path.stat().st_size > 16384:
            return {}
        value = json.loads(path.read_bytes())
        return value if (isinstance(value, dict) and value.get("schema") == "smako-derived-generation-v1"
            and type(value.get("sequence")) is int and value["sequence"] >= 0
            and isinstance(value.get("token"), str)) else {}
    except (OSError, ValueError, TypeError):
        return {}


@contextmanager
def shared_preparation(identity):
    """Coordinator lease; workers never activate or publish another generation.

    Only rebuildable, format-verified cache entries can be retired. Sources,
    recipe packs and saved plans are outside these cache directories. An older
    computation can still return its exact value but cannot evict or mark the
    newer coordinator's data ready. Restart acquires a fresh CAS token.
    """
    cache_root = root().resolve()
    lease = _SharedGeneration(cache_root, digest(encoded([identity, method_signature()])), uuid4().hex)
    with _cache_lock(cache_root / ".generation.lock") as acquired:
        if acquired:
            prior = _generation_state(cache_root)
            state = {"schema":"smako-derived-generation-v1", "identity":lease.identity,
                     "token":lease.token, "sequence":int(prior.get("sequence",0))+1,
                     "method":method_signature(), "state":"preparing"}
            try:
                atomic_write(cache_root / ".shared-generation.json", encoded(state))
                lease.writable = True
            except OSError:
                pass
    token = _shared_generation.set(lease)
    completed = False
    try:
        yield lease
        completed = True
    finally:
        _shared_generation.reset(token)
        if completed and lease.writable and not lease.failures:
            with _cache_lock(cache_root / ".generation.lock") as acquired:
                state = _generation_state(cache_root)
                if acquired and state.get("token") == lease.token:
                    state.update(state="ready", requested_entries=len(lease.requested))
                    try:
                        atomic_write(cache_root / ".shared-generation.json", encoded(state))
                        lease.ready = True
                    except OSError:
                        pass



def _retire_interrupted_writes(directory, lease):
    directory = directory.resolve()
    if directory.parent != lease.cache_root:
        return
    with _cache_lock(lease.cache_root / ".generation.lock") as acquired:
        if not acquired or _generation_state(lease.cache_root).get("token") != lease.token:
            return
        for path in directory.glob(".derived-*.tmp"):
            if re.fullmatch(r"\.derived-[0-9a-f]{64}-[0-9a-f]{32}\.tmp", path.name):
                try:
                    path.unlink()  # Owned interrupted cache output, never source evidence.
                    STATS["interrupted_writes_removed"] = STATS.get("interrupted_writes_removed", 0) + 1
                except OSError:
                    lease.failures += 1


def _atomic_derived_write(path, data, lease):
    temporary = path.parent / (".derived-" + path.stem + "-" + lease.token + ".tmp")
    try:
        with temporary.open("wb") as handle:
            handle.write(data)
            handle.flush()
        # Derived values use the existing cache's atomic-replace contract.
        # Per-file fsync serializes thousands of small writes on this volume;
        # after interruption every persisted payload is still hash-validated.
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _retaining_write(budget, path, data, raw_size):
    lease = budget.lease
    directory = budget.directory.resolve()
    if (not lease.writable or directory.parent != lease.cache_root
            or path.parent.resolve() != directory or len(path.stem) != 64
            or any(c not in "0123456789abcdef" for c in path.stem)):
        lease.failures += 1
        return
    with _cache_lock(lease.cache_root / ".generation.lock") as acquired:
        if not acquired or _generation_state(lease.cache_root).get("token") != lease.token:
            lease.failures += 1
            return
        try:
            old_size = path.stat().st_size if path.exists() else 0
            if old_size:
                # A concurrent valid writer wins; a corrupt owned cache file
                # can be retired before replacement, keeping temp+final bytes
                # inside the same physical byte budget.
                existing = json.loads(path.read_bytes())
                if not isinstance(existing, dict) or existing.get("schema") != SCHEMA or existing.get("key") != path.stem:
                    lease.failures += 1
                    return
                try:
                    decode_payload(existing)
                    return
                except (ValueError, KeyError, TypeError, zlib.error):
                    path.unlink()
                    budget.count -= 1
                    budget.size -= old_size
                    old_size = 0
            limit = CONTENT_LIMIT if directory.name == "content" else MAX_GENERATIONS
            if raw_size > 128 * 1024 * 1024 or len(data) > MAX_BYTES:
                lease.failures += 1
                return
            while budget.count + (not old_size) > limit or budget.size - old_size + len(data) > MAX_BYTES:
                if budget.retirement is None:
                    budget.retirement = []
                    for candidate in directory.glob("*.json"):
                        # Exact file ownership, not a wildcard deletion policy.
                        if len(candidate.stem) != 64 or any(c not in "0123456789abcdef" for c in candidate.stem):
                            continue
                        try:
                            stat = candidate.stat()
                            if stat.st_size > MAX_BYTES:
                                continue
                            row = json.loads(candidate.read_bytes())
                            if isinstance(row, dict) and row.get("schema") == SCHEMA and row.get("key") == candidate.stem:
                                heapq.heappush(budget.retirement, (stat.st_mtime_ns, candidate.name, stat.st_size))
                        except (OSError, ValueError, TypeError):
                            continue
                retired = False
                while budget.retirement:
                    _age, name, size = heapq.heappop(budget.retirement)
                    candidate = directory / name
                    if candidate.as_posix() in lease.requested or candidate == path:
                        continue
                    if candidate.exists():
                        candidate.unlink()
                        budget.count -= 1
                        budget.size -= size
                        STATS["retired"] = STATS.get("retired", 0) + 1
                        STATS["retired_bytes"] = STATS.get("retired_bytes", 0) + size
                        retired = True
                        break
                if not retired:
                    lease.failures += 1
                    return
            _atomic_derived_write(path, data, lease)
            budget.count += not old_size
            budget.size += len(data) - old_size
            STATS["writes"] += 1
        except (OSError, ValueError, TypeError):
            lease.failures += 1


@contextmanager
def _derived_write_batch(directory, lease):
    with _cache_lock(directory / ".preparation-write.lock") as acquired:
        budget = _ContentWriteBudget(directory, 0, 0, writable=acquired, lease=lease)
        if acquired:
            try:
                if lease is not None:
                    _retire_interrupted_writes(directory, lease)
                for candidate in directory.glob("*.json"):
                    budget.count += 1
                    budget.size += candidate.stat().st_size
            except OSError:
                budget.writable = False
        yield budget


def prepare_current_sources(prepared_universe, facts, *, portions=(4,), progress=None):
    """One current public catalog; no profile, meal winner or price approval."""
    from app.services.meal_library_content import library_signature
    from app.services.personal_source_facts import facts_version
    from app.services.recipe_library import _current_issued_index, current_recipes
    if progress:
        progress("facts_identity")
    version = facts_version(facts)
    identity = {"library":library_signature(), "universe":prepared_universe.universe.universe_id,
                "facts":version, "portions":sorted(set(portions)),
                "scope":"current_content_declarations_ingredient_positions"}
    before = dict(STATS)
    with shared_preparation(identity) as lease:
        if progress:
            progress("current_content")
        content = prepare_content(current_recipes())
        if progress:
            progress("portion_views")
        counts = {str(n):len(_current_issued_index(n)) for n in sorted(set(portions))}
        def source_fact(product):
            fact = facts.get((product.store_id,product.product_id))
            return fact if (fact and fact.source and fact.source_product_id == product.product_id
                and product.source_provenance and fact.source_snapshot_id == product.source_provenance.source_snapshot_id) else None
        if progress:
            progress("declarations")
        declarations = declaration_index(prepared_universe.universe, facts, source_fact, verified_version=version)
        if progress:
            progress("ingredient_search")
        searches = prepare_ingredient_search(prepared_universe)
    cache = root()
    storage = {directory.name:{"files":sum(1 for p in directory.glob("*.json")),
        "bytes":sum(p.stat().st_size for p in directory.iterdir() if p.is_file())}
        for directory in cache.iterdir() if directory.is_dir()}
    total_bytes = sum(p.stat().st_size for p in cache.rglob("*") if p.is_file())
    return {"identity":identity, "ready":lease.ready, "persistence_failures":lease.failures,
            "storage":storage, "total_storage_bytes":total_bytes,
            "content_variants":len(current_recipes()), "portion_views":counts,
            "declarations":len(declarations), "ingredient_queries":len(searches),
            "stats":{key:value-before.get(key,0) for key,value in STATS.items()},
            "purchase_qualification":"not_performed", "method_signature":content["method_signature"]}


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
            lease = _shared_generation.get()
            if lease is not None:
                lease.failures += 1
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
             *base.joinpath("data/ingredients").glob("*.json"),
             *base.joinpath("data/nutrition").glob("*.json"),
             repository / "grocery_data/app/data/product_declarations.json",
             repository / "grocery_data/app/services/product_declarations.py"]
    return digest(encoded({p.relative_to(repository).as_posix():digest(p.read_bytes())
                           for p in sorted(paths)}))


@lru_cache(maxsize=64)
def _directory_at_capacity(directory, modified_ns, limit):
    # Directory modification time invalidates the snapshot when entries change.
    # A cached full result can only suppress a write, never approve one: the
    # ordinary count/byte checks below still govern every actual write.
    return sum(1 for _ in islice(directory.glob("*.json"), limit)) >= limit


def prepared(kind, identity, compute, *, storable=None, _write_budget=None):
    """Reject partial/wrong version artefacts and safely recompute on any cache fault.

    ``storable`` is asked after ``compute``; when it returns False the result
    is returned but never written (e.g. a projection that hit a read error).
    """
    key = digest(encoded([SCHEMA,kind,identity,method_signature()]))
    directory = root() / kind
    path = directory / (key + ".json")
    lease = _shared_generation.get()
    if lease is not None:
        lease.requested.add(path.resolve().as_posix())
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
    except (OSError,ValueError,KeyError,TypeError,RecursionError,zlib.error):
        STATS["invalid"] += 1
    STATS["misses"] += 1
    payload = compute()
    if storable is not None and not storable():
        if lease is not None:
            lease.failures += 1
        STATS["unstorable"] = STATS.get("unstorable", 0) + 1
        return payload
    raw = payload_bytes(payload)
    compressed = len(raw) > 256 * 1024
    data = payload_bytes({"schema":SCHEMA,"key":key,"payload":
        base64.b64encode(zlib.compress(raw,1)).decode() if compressed else payload,
        "encoding":"zlib-json-v1" if compressed else "json-v1", "sha256":digest(raw)})
    try:
        if _write_budget is not None:
            _write_budget.write(path, data, len(raw))
            return payload
        directory.mkdir(parents=True,exist_ok=True)
        if lease is not None:
            with _derived_write_batch(directory, lease) as budget:
                budget.write(path, data, len(raw))
            return payload
        # Existing generation evidence is retained. At the bounded capacity,
        # continue safely in memory rather than growing disk indefinitely.
        limit = CONTENT_LIMIT if kind == "content" else MAX_GENERATIONS
        if _directory_at_capacity(directory, directory.stat().st_mtime_ns, limit) and not path.exists():
            return payload
        with _cache_lock(directory / ".preparation-write.lock") as acquired:
            if not acquired:
                return payload
            existing = list(directory.glob("*.json"))
            if len(existing) >= limit and not path.exists():
                return payload
            total_bytes = sum(p.stat().st_size for p in existing)
            if (len(raw) <= 128 * 1024 * 1024 and len(data) <= MAX_BYTES and total_bytes + len(data) <= MAX_BYTES
                    and (path.exists() or len(existing) < limit)):
                atomic_write(path,data)
                STATS["writes"] += 1
    except OSError:
        pass  # read-only deployments still use the ordinary checked calculation
    return payload


def prepare_content(recipes):
    with _content_write_batch() as budget:
        return _prepare_content(recipes, budget)


def _prepare_content(recipes, budget):
    from app.services.meal_library_content import identity
    from app.services.recipe_library import _structural_check, ingredient_key
    index = {}
    from app.services.plan_jobs import check_cancelled
    for recipe in recipes:
        check_cancelled()
        key = identity(recipe)
        def compute(recipe=recipe, key=key):
            _structural_check(recipe)
            return {"identity":key,"content_sha256":recipe.design.content_sha256,
                    "ingredients":[ingredient_key(i) for i in recipe.ingredients],
                    "meal_types":list(recipe.design.meal_types),
                    "ingredient_count":recipe.design.ingredient_count}
        row = prepared("content",recipe.model_dump(mode="json"),compute, _write_budget=budget)
        # Cache provenance never substitutes for the issued content registry.
        if row["identity"] != key or row["content_sha256"] != recipe.design.content_sha256:
            raise ValueError("Prepared content identity mismatch")
        for ingredient in row["ingredients"]:
            index.setdefault(ingredient,[]).append(key)
    return {"schema":SCHEMA,"method_signature":method_signature(),"dependencies":index,"stats":dict(STATS)}


def declaration_index(universe, facts, source_facts, *, verified_version=None):
    """Snapshot/fact-bound declaration classes shared across meal types/requests.

    Includes the full product inventory: a previously missing product invalidates
    negative results. Prices/terms/date/owner approval are never stored here.
    """
    from app.services.declaration_semantics import declaration_food_class
    from app.services.personal_source_facts import facts_version
    version = verified_version or getattr(facts,"version",None) or facts_version(facts)
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
