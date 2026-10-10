"""Additive municipal operation scopes in the existing collection registry.

The registry selects sources, never user stores. Collection, manifests, locks
and freshness remain owned by the normal refresh and PriceUniverse lifecycle.
"""
from __future__ import annotations

import json
import os
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy.engine import make_url

from grocery_data.app.domain.municipality import municipality_code, municipality_name
from grocery_data.app.services.area_membership import _key
from grocery_data.app.services.durable_files import atomic_write_bytes

SOURCES = ("ica", "coop", "xtra", "hemkop", "willys", "lidl", "citygross")
SOURCE_FLAGS = {
    "ica": "ICA_STRUCTURED_OFFERS_ENABLED",
    "coop": "COOP_MUNICIPAL_OFFERS_ENABLED",
    "xtra": "COOP_XTRA_OFFERS_ENABLED",
    "hemkop": "HEMKOP_MUNICIPAL_OFFERS_ENABLED",
    "lidl": "LIDL_MUNICIPAL_ENABLED",
    "citygross": "CITYGROSS_MUNICIPAL_ENABLED",
}


def registry_path(environment=None):
    env = os.environ if environment is None else environment
    database = Path(make_url(env.get("GROCERY_DATABASE_URL", "sqlite:///var/grocery/grocery_data.sqlite")).database)
    return Path(env.get("MUNICIPAL_COLLECTION_SCOPE_PATH") or database.parent / "municipal-collection-scopes.json")


def read_registry(environment=None):
    path = registry_path(environment)
    data = json.loads(path.read_bytes()) if path.exists() else {"schema": "municipal-collection-scopes-v1", "cities": {}}
    validate_registry(data)
    return data


def validate_registry(data):
    if not isinstance(data, dict) or data.get("schema") != "municipal-collection-scopes-v1" or not isinstance(data.get("cities"), dict):
        raise ValueError("unsupported municipal collection scope")
    scopes = data.get("refresh_scopes", {})
    if not isinstance(scopes, dict):
        raise TypeError("invalid municipal refresh scopes")
    postals = set()
    for code, scope in scopes.items():
        name = municipality_name(code)
        if not isinstance(scope, dict):
            raise TypeError("municipal refresh scope must be an object")
        postal = scope.get("postal_code")
        if not isinstance(postal, str) or len(postal) != 5 or not postal.isascii() or not postal.isdigit():
            raise ValueError("municipal build postal code must contain five digits")
        if postal in postals:
            raise ValueError("municipal build postal scopes must be unique")
        postals.add(postal)
        if data["cities"].get(_key(name)) != code:
            raise ValueError("municipal refresh and collection scopes disagree")
        if not isinstance(scope.get("enabled"), bool):
            raise TypeError("municipal enabled must be boolean")
        sources = scope.get("sources")
        if not isinstance(sources, list) or not sources or any(not isinstance(s, str) for s in sources) or len(set(sources)) != len(sources) or set(sources) - set(SOURCES):
            raise ValueError("invalid municipal source selection")
        required = scope.get("required_context_ids", [])
        if not isinstance(required, list) or any(not isinstance(v, str) or not v.strip() for v in required):
            raise ValueError("invalid municipal required contexts")


def refresh_scopes(environment=None):
    return sorted([{**scope, "municipality_code": code, "city": municipality_name(code)}
            for code, scope in read_registry(environment).get("refresh_scopes", {}).items()
            if scope["enabled"]], key=lambda s: (not s.get("legacy_operation_paths", False), s["city"]))


def scope_for_city(city, environment=None):
    return next((s for s in refresh_scopes(environment) if _key(s["city"]) == _key(city)), None)


def _current_sources(env):
    # Existing optional jobs can be enabled by their durable config, not only
    # process environment. Adopting the registry must not disable those feeds.
    from grocery_data.app.services.citygross_municipal_job import configuration as citygross
    from grocery_data.app.services.coop_offer_job import configuration as coop
    from grocery_data.app.services.lidl_municipal_job import configuration as lidl

    enabled = {source for source, flag in SOURCE_FLAGS.items() if env.get(flag, "false").casefold() == "true"}
    for source, loader in (("coop", coop), ("lidl", lidl), ("citygross", citygross)):
        _, config = loader(env)
        if config["enabled"]:
            enabled.add(source)
        if source == "coop" and config.get("xtra_enabled"):
            enabled.add("xtra")
    enabled.add("willys")
    return [source for source in SOURCES if source in enabled]


def add_municipality(code, postal_code, *, environment=None, persist=False):
    """Idempotent addition. Caller must hold the normal operation lease to persist."""
    env = os.environ if environment is None else environment
    name = municipality_name(code)
    data = read_registry(env)
    scopes = data.setdefault("refresh_scopes", {})
    # Opting into multiple municipalities must retain the current operation.
    if not scopes:
        current_city = env.get("REFRESH_CITY", "Lund")
        current_code = env.get("REFRESH_MUNICIPALITY_CODE") or municipality_code(current_city)
        if municipality_name(current_code).casefold() != current_city.casefold():
            raise ValueError("current refresh municipality conflicts with its city")
        sources = _current_sources(env)
        scopes[current_code] = {"postal_code": env.get("REFRESH_POSTAL_CODE", "22350"),
            "enabled": True, "sources": sources,
            "required_context_ids": [v.strip() for v in env.get("PRICE_UNIVERSE_REQUIRED_CONTEXT_IDS", "").split(",") if v.strip()],
            "legacy_operation_paths": True}
        data["cities"][_key(current_city)] = current_code
    if code in scopes:
        if scopes[code]["postal_code"] != postal_code:
            raise ValueError("municipality already registered with another build postal scope")
    else:
        scopes[code] = {"postal_code": postal_code, "enabled": True,
                        "sources": list(SOURCES), "required_context_ids": []}
    data["cities"][_key(name)] = code
    # Validate through the same reader without touching production before review.
    validate_registry(data)
    if persist:
        path = registry_path(env)
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_bytes(path, json.dumps(data, ensure_ascii=False, sort_keys=True).encode())
    return data


def scoped_environment(scope, environment=None):
    """Fully bind every adapter; never inherit another municipality's ID/seed."""
    env = dict(os.environ if environment is None else environment)
    code, city = scope["municipality_code"], scope["city"]
    env.update(REFRESH_CITY=city, REFRESH_POSTAL_CODE=scope["postal_code"],
               REFRESH_MUNICIPALITY_CODE=code, MUNICIPAL_REFRESH_SCOPE=code,
               PRICE_UNIVERSE_CITY=city,
               PRICE_UNIVERSE_REQUIRED_CONTEXT_IDS=",".join(scope.get("required_context_ids", [])))
    for source, flag in SOURCE_FLAGS.items():
        env[flag] = str(source in scope["sources"]).lower()
    env["HEMKOP_ALLOW_FULL_CRAWL"] = str("hemkop" in scope["sources"]).lower()
    for prefix in ("COOP", "LIDL", "CITYGROSS"):
        env[prefix + "_MUNICIPALITY_CODE"] = code
        env[prefix + "_MUNICIPAL_BUILD_CITY"] = city
        env.pop(prefix + "_MUNICIPAL_INVENTORY", None)
    env.update(WILLYS_FLYER_MUNICIPALITY_CODE=code, WILLYS_FLYER_BUILD_CITY=city)
    env.pop("WILLYS_FLYER_INVENTORY", None)
    # Different municipalities must never share a demand/backoff journal.
    if not scope.get("legacy_operation_paths"):
        root = Path(env.get("PRICE_UNIVERSE_CACHE_ROOT", "var/price_universes"))
        operation_root = root.parent / "reports" / "operations" / "municipalities" / code
        env["DEMAND_REFRESH_STATE_PATH"] = str(operation_root / "demand-refresh.json")
        env["REFRESH_RUNNER_STATUS_PATH"] = str(operation_root / "refresh-runner-status.json")
    return env


def hemkop_policy(city, policy):
    """Derive exact online targets from approved municipal evidence, never names."""
    from dataclasses import replace

    from grocery_data.app.services.area_membership import approved_municipal_stores
    from grocery_data.app.services.hemkop_municipal_job import configuration, read

    scope = scope_for_city(city)
    municipal_code = os.getenv("MUNICIPAL_REFRESH_SCOPE")
    if not municipal_code:
        return policy
    if scope is None or municipal_code != scope["municipality_code"]:
        raise ValueError("Hemkop transport municipality differs from registered scope")
    area, root, enabled = configuration(city)
    state = read(root / "source-state.json")
    if not enabled or state.get("inventory", {}).get("area") != area.model_dump(mode="json"):
        raise ValueError("verified municipal Hemkop inventory required")
    stores = approved_municipal_stores(state["inventory"])
    from grocery_data.app.services.operations_diagnostics import schema_holds

    root = Path(os.getenv("PRICE_UNIVERSE_CACHE_ROOT", "var/price_universes")).parent / "reports/operations"
    held = set(schema_holds(root).get("hemkop", []))
    return replace(policy, allowed_store_ids=frozenset(
        identity for identity, store in stores.items() if store.online_shopping is True and identity not in held))


@contextmanager
def municipal_environment(scope):
    """Only for the sequential command-line worker, never the web process."""
    previous = dict(os.environ)
    try:
        os.environ.clear()
        os.environ.update(scoped_environment(scope, previous))
        yield
    finally:
        os.environ.clear()
        os.environ.update(previous)
