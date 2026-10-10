"""Shared, fail-closed geographic membership; independent of price and user choices.

Municipal membership needs an administrative address field or separately bound
official coordinates and SCB geometry. Address locality, postal-code equality,
name search and price context coverage are never municipal evidence.
"""
import re
import unicodedata
from datetime import datetime
from urllib.parse import urlsplit

from grocery_data.app.domain import GeographicArea, SourceStore
from grocery_data.app.domain.municipality import municipality_code, municipality_register

LOCALITY_PROVENANCE = "docs/store_coverage_and_physical_validation.md:strict-address-locality"
MUNICIPALITY_PROVENANCE = "docs/municipality_coverage.md:verified-address-municipality-v1"


def collection_area(city, *, environment=None, persist=False):
    """One explicit, durable collection scope; never a user shopping preference.

    Existing locality jobs remain unchanged until an official municipality code
    is selected. Each build city has its own saved selection, including restart.
    Callers that persist must hold the existing refresh operation lock.
    """
    import json
    import os
    from pathlib import Path

    from sqlalchemy.engine import make_url

    from grocery_data.app.domain.municipality import municipality_name
    from grocery_data.app.services.durable_files import atomic_write_bytes

    env = os.environ if environment is None else environment
    database = Path(make_url(env.get("GROCERY_DATABASE_URL", "sqlite:///var/grocery/grocery_data.sqlite")).database)
    path = Path(env.get("MUNICIPAL_COLLECTION_SCOPE_PATH", str(database.parent / "municipal-collection-scopes.json")))
    saved = json.loads(path.read_bytes()) if path.exists() else {"schema": "municipal-collection-scopes-v1", "cities": {}}
    if saved.get("schema") != "municipal-collection-scopes-v1":
        raise ValueError("unsupported municipal collection scope")
    key = _key(city)
    code = (saved["cities"].get(key) if saved.get("refresh_scopes") else
            env.get("REFRESH_MUNICIPALITY_CODE") or saved["cities"].get(key))
    if env.get("MUNICIPAL_REFRESH_SCOPE") and code != env["MUNICIPAL_REFRESH_SCOPE"]:
        raise ValueError("collection municipality differs from the current operation")
    if not code:
        return GeographicArea(city=city)
    name = municipality_name(code)
    if _key(city) != _key(name):
        raise ValueError("collection municipality does not match build city")
    if persist and saved["cities"].get(key) != code:
        saved["cities"][key] = code
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_bytes(path, json.dumps(saved, ensure_ascii=False, sort_keys=True).encode())
    return GeographicArea(city=name, mode="municipality", municipality_code=code)


def _key(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", value.casefold().strip())
                   if not unicodedata.combining(c))


def assess_area(store: SourceStore, area: GeographicArea) -> dict:
    result = {"status": "unknown", "reason": "official_address_or_locality_missing",
              "area_key": area.area_key, "mode": area.mode,
              "provenance": LOCALITY_PROVENANCE, "evidence": None}
    if area.mode == "locality":
        if store.address and store.city:
            inside = _key(store.city) == _key(area.city)
            result.update(status="inside" if inside else "outside",
                          reason="official_address_locality_matches_existing_area" if inside
                          else "official_address_locality_differs_from_existing_area")
        return result
    result.update(provenance=MUNICIPALITY_PROVENANCE,
                  reason="verified_address_municipality_missing")
    if store.source_fields.get("municipality_evidence_conflict"):
        result["reason"] = "conflicting_verified_municipality_addresses"
        return result
    evidence = store.source_fields.get("address_municipality_evidence")
    position = store.source_fields.get("position_municipality_evidence")
    if evidence is None and isinstance(position, dict):
        try:
            source = position["coordinate_source"]
            valid = (position["basis"] == "official_position_scb_regso_2025"
                     and position["store_id"] == store.external_id and position["chain"] == store.chain.value
                     and position["latitude"] == str(store.latitude) and position["longitude"] == str(store.longitude)
                     and position["municipality_code"] == area.municipality_code
                     and position["boundary_version"] == "RegSO_2025"
                     and position["boundary_source"].startswith("https://geodata.scb.se/geoserver/stat/wfs?")
                     and re.fullmatch(r"[0-9a-f]{64}", position["boundary_sha256"])
                     and re.fullmatch(r"[0-9a-f]{64}", source["sha256"])
                     and urlsplit(source["url"]).scheme == "https"
                     and datetime.fromisoformat(source["observed_at"]).tzinfo is not None
                     and position["status"] in {"inside", "outside", "unknown"})
        except (KeyError, TypeError, ValueError):
            valid = False
        if valid:
            result.update(status=position["status"], reason=position["reason"], evidence=position,
                          provenance="docs/municipality_geometry.md:scb-regso-2025-position",
                          uncertainty=position["uncertainty"])
        else:
            result["reason"] = "municipality_position_evidence_invalid"
        return result
    if not store.address or not isinstance(evidence, dict):
        return result
    result["evidence"] = evidence
    try:
        observed = datetime.fromisoformat(evidence["observed_at"])
        valid = (evidence["basis"] == "official_address_administrative_field"
                 and evidence["store_id"] == store.external_id
                 and evidence["chain"] == store.chain.value
                 and evidence["address"] == store.address
                 and evidence["field_path"]
                 and urlsplit(evidence["source_url"]).scheme == "https"
                 and observed.tzinfo is not None
                 and re.fullmatch(r"[0-9a-f]{64}", evidence["source_sha256"]))
    except (KeyError, TypeError, ValueError):
        valid = False
    if not valid:
        result["reason"] = "municipality_evidence_invalid_or_wrong_store"
        return result
    code = municipality_code(str(evidence.get("municipality_name", "")))
    if code is None or evidence.get("municipality_code", code) != code:
        result["reason"] = "municipality_name_code_unknown_or_conflicting"
        return result
    register = municipality_register()
    result.update(status="inside" if code == area.municipality_code else "outside",
                  reason="verified_address_municipality_matches" if code == area.municipality_code
                  else "verified_address_municipality_differs", municipality_code=code,
                  register_source=register["source_url"], register_version=register["version"],
                  register_sha256=register["source_sha256"],
                  uncertainty="retailer administrative address; not cadastral boundary verification")
    return result


def area_membership(store: SourceStore, area: GeographicArea) -> tuple[str, str]:
    result = assess_area(store, area)
    return result["status"], result["reason"]


def reuse_municipality_evidence(store: SourceStore, references: list[SourceStore],
                               area: GeographicArea) -> SourceStore:
    """Reuse exact, independently observed addresses across discovery queries.

    Never join by locality/name/postcode alone, and never renew observations.
    """
    if area.mode != "municipality":
        return store
    matches = [candidate for candidate in [store, *references]
               if (candidate.chain, candidate.external_id, candidate.address, candidate.postal_code)
               == (store.chain, store.external_id, store.address, store.postal_code)
               and isinstance(candidate.source_fields.get("address_municipality_evidence"), dict)
               and assess_area(candidate, area)["status"] in {"inside", "outside"}]
    codes = {assess_area(candidate, area)["municipality_code"] for candidate in matches}
    fields = dict(store.source_fields)
    if len(codes) > 1:
        fields["municipality_evidence_conflict"] = True
    elif len(codes) == 1 and assess_area(store, area)["status"] == "unknown":
        # Same membership, retain the earliest evidence rather than rejuvenating it.
        chosen = min(matches, key=lambda candidate: candidate.source_fields[
            "address_municipality_evidence"]["observed_at"])
        fields["address_municipality_evidence"] = chosen.source_fields["address_municipality_evidence"]
        fields["municipality"] = chosen.source_fields["address_municipality_evidence"]["municipality_name"]
    return store.model_copy(update={"source_fields": fields})


def approved_municipal_stores(inventory, *, concepts=None):
    """Rebind every selected physical store to this municipality, not a saved label."""
    spec = inventory["area"]
    if spec.get("mode") != "municipality":
        raise ValueError("explicit municipality required")
    from grocery_data.app.domain.municipality import municipality_name

    code = spec["municipality_code"]
    area = GeographicArea(city=municipality_name(code), mode="municipality", municipality_code=code)
    result = {}
    for row in inventory["stores"]:
        store = SourceStore.model_validate(row["store"])
        if ((concepts is not None and store.source_fields.get("concept") not in concepts)
                or store.source_fields.get("identity_conflict")
                or row["geographic_evidence"]["status"] != "inside"
                or assess_area(store,area)["status"] != "inside"):
            continue
        if store.external_id in result:
            raise ValueError("duplicate physical store identity")
        result[store.external_id] = store
    return result
