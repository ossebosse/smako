"""Explicit persisted build/relay scope; never changes saved user selections."""
import json
import os
from pathlib import Path

from grocery_data.app.domain.municipality import municipality_name


def relay_municipality(workspace, requested=None):
    from grocery_data.app.services.durable_files import atomic_write_bytes

    path = Path(workspace) / "source-scope.json"
    if path.exists():
        data = json.loads(path.read_bytes())
        if set(data) != {"schema", "municipality_code"} or data["schema"] != "willys-municipal-relay-v1":
            raise ValueError("invalid persistent relay scope")
        code = data["municipality_code"]
        municipality_name(code)
        if requested is not None and requested != code:
            raise ValueError("use separate relay workspace per municipality")
        return code
    if requested is not None:
        municipality_name(requested)
        atomic_write_bytes(path, json.dumps({"schema": "willys-municipal-relay-v1", "municipality_code": requested}).encode())
    return requested


def matches_relay_scope(manifest, code):
    area = manifest.source_scope.geographic_area
    return (area.mode == "municipality" and area.municipality_code == code) if code else area.mode == "locality"


def load_build_scopes():
    path = os.getenv("WILLYS_MUNICIPAL_CONFIG", "").strip()
    if not path:
        return {}
    data = json.loads(Path(path).read_bytes())
    if set(data) != {"schema", "build_scopes"} or data["schema"] != "willys-municipal-build-v1":
        raise ValueError("unsupported Willys municipal configuration")
    scopes = data["build_scopes"]
    if not isinstance(scopes, dict) or not scopes:
        raise ValueError("municipal build scopes missing")
    for postal, code in scopes.items():
        if not isinstance(postal, str) or len(postal) != 5 or not postal.isdigit():
            raise ValueError("invalid build postal scope")
        municipality_name(code)
    return scopes


def require_import_scope(manifest):
    area = manifest.source_scope.geographic_area
    if area.mode == "municipality" and area.municipality_code not in load_build_scopes().values():
        raise ValueError("municipal source not enabled in persistent build configuration")


def approved_snapshot_stores(database, postal):
    """Only active independently validated municipal source artifacts may widen a build."""
    code = load_build_scopes().get(postal)
    if code is None:
        return None
    import sqlite3

    from grocery_data.app.domain import GeographicArea, SourceStore
    from grocery_data.app.services.area_membership import approved_municipal_stores

    area = GeographicArea(city=municipality_name(code), mode="municipality", municipality_code=code)
    with sqlite3.connect(Path(database).resolve().as_uri() + "?mode=ro", uri=True) as db:
        rows = db.execute("SELECT metrics FROM catalog_snapshots WHERE chain='willys' AND is_active=1 AND scope_key=?", (area.city.casefold(),)).fetchall()
    if len(rows) != 1:
        raise ValueError("one approved municipal Willys source snapshot required")
    metrics = json.loads(rows[0][0])
    inventory = metrics.get("willys_municipal_inventory")
    if not inventory or inventory["area"] != area.model_dump(mode="json"):
        raise ValueError("active source lacks matching municipal evidence")
    selected = approved_municipal_stores(inventory)
    return {key: SourceStore.model_validate(value) for key, value in selected.items()
            if value.online_shopping is True}
