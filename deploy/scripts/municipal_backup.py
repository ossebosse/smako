"""Inventory current municipal recovery state, never historical attempt trees."""
import json
import os
from pathlib import Path

from sqlalchemy.engine import make_url

from grocery_data.app.services.municipal_rollout import refresh_scopes, registry_path

SOURCE_ROOTS = {
    'COOP_MUNICIPAL_OFFERS_ROOT': 'coop-municipal-offers',
    'ICA_STRUCTURED_OFFERS_ROOT': 'ica-structured-offers',
    'HEMKOP_MUNICIPAL_ROOT': 'hemkop-municipal',
    'LIDL_MUNICIPAL_ROOT': 'lidl-municipal',
    'CITYGROSS_MUNICIPAL_ROOT': 'citygross-municipal',
    'WILLYS_FLYER_ROOT': 'willys-flyer',
}


def recovery_roots():
    grocery = Path(make_url(os.environ['GROCERY_DATABASE_URL']).database).resolve().parent
    universe = Path(os.environ['PRICE_UNIVERSE_CACHE_ROOT']).resolve()
    return {'grocery': grocery, 'operations': universe.parent / 'reports/operations'}


def current_files():
    """Return exact metadata and its immutable database dependencies.

    Paths stay below the configured data roots. Hash-bound databases are copied
    byte-for-byte by the caller; SQLite backup would invalidate their references.
    Active writer sidecars are rejected instead of silently losing WAL data.
    """
    roots = recovery_roots()
    files = {}

    def add(path, role):
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError('municipal recovery dependency missing')
        resolved = path.resolve()
        if not resolved.is_relative_to(roots[role].resolve()):
            raise ValueError('municipal recovery dependency escaped data root')
        relative = resolved.relative_to(roots[role].resolve()).as_posix()
        files['runtime/' + role + '/' + relative] = resolved

    def database_refs(value, base):
        if isinstance(value, dict):
            if isinstance(value.get('database'), str):
                database = Path(value['database'])
                database = database if database.is_absolute() else base / database
                if any(Path(str(database) + suffix).exists() and Path(str(database) + suffix).stat().st_size
                       for suffix in ('-wal', '-journal')):
                    raise ValueError('municipal source database is not immutable')
                add(database, 'grocery')
                if value.get('sha256'):
                    from deploy.scripts.backup_sqlite import _sha256
                    if _sha256(database) != value['sha256']:
                        raise ValueError('municipal source reference hash mismatch')
            for child in value.values():
                database_refs(child, base)
        elif isinstance(value, list):
            for child in value:
                database_refs(child, base)

    registry = registry_path()
    if registry.exists():
        add(registry, 'grocery')
    scopes = refresh_scopes()
    for variable, default in SOURCE_ROOTS.items():
        root = Path(os.getenv(variable, str(roots['grocery'] / default)))
        if (root / 'config.json').exists():
            add(root / 'config.json', 'grocery')
        for scope in scopes:
            for filename in ('source-state.json', 'structured-source.json'):
                state = root / scope['municipality_code'] / filename
                if state.exists():
                    add(state, 'grocery')
                    payload = json.loads(state.read_bytes())
                    # Outcome reports have attempt-relative diagnostic paths.
                    # Only the accepted pointer graph owns build dependencies.
                    database_refs({k: payload[k] for k in ('database', 'sha256', 'approved', 'partial_approved')
                                   if k in payload}, root)
    operations = roots['operations']
    for path in operations.glob('*.json'):
        add(path, 'operations')
    for scope in scopes:
        for path in (operations / 'municipalities' / scope['municipality_code']).glob('*.json'):
            add(path, 'operations')
    return files


def restored_target(relative):
    relative = Path(relative)
    if relative.is_absolute() or '..' in relative.parts or len(relative.parts) < 3:
        raise ValueError('invalid municipal recovery path')
    prefix, role, *parts = relative.parts
    roots = recovery_roots()
    if prefix != 'runtime' or role not in roots:
        raise ValueError('unknown municipal recovery root')
    target = roots[role].joinpath(*parts)
    if not target.resolve().is_relative_to(roots[role].resolve()):
        raise ValueError('municipal restore target escaped data root')
    return target
