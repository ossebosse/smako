"""Freeze public serving inputs only, from read-only mounts; no source collection.

Run in an isolated container with /source/price_universes, /source/grocery,
/source/raw_snapshots read-only and an empty /work writable directory.
User plans, accounts, receipts, sessions and settings are deliberately excluded.
"""
import hashlib
import json
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.services.price_universe_runtime import PreparedPriceUniverseArtifact

from grocery_data.app.services.prepared_universe_activation import PreparedUniverseArtifactStore


def main():
    source, target = Path('/source'), Path('/work')
    target.mkdir(exist_ok=True)
    assert not any(target.iterdir()), 'Freeze destination must be empty'
    store = PreparedUniverseArtifactStore(source / 'price_universes')
    manifest = store.read_active('Lund')
    path = store.resolve_active_artifact('Lund')
    assert path and manifest
    payload = path.read_bytes()
    artifact = PreparedPriceUniverseArtifact.model_validate_json(payload)
    (target / 'universe.json').write_bytes(payload)
    (target / 'manifest.json').write_text(manifest.model_dump_json(indent=2))
    snapshots = set(artifact.universe.key.snapshot_ids)
    tables = ('catalog_snapshots', 'products', 'source_products', 'raw_snapshots')
    counts, hashes = {}, {}
    with sqlite3.connect((source / 'grocery/grocery_data.sqlite').as_uri() + '?mode=ro', uri=True) as src:
        src.execute('BEGIN')
        snapshots.update(r[0] for r in src.execute(
            "SELECT id FROM catalog_snapshots WHERE is_active=1 AND state='promoted' AND coverage='full_online_catalog'"
        ))
        with sqlite3.connect(target / 'grocery.sqlite') as dst:
            for table in tables:
                schema = src.execute('SELECT sql FROM sqlite_master WHERE type=? AND name=?', ('table', table)).fetchone()
                assert schema
                dst.execute(schema[0])
                key = 'id' if table == 'catalog_snapshots' else 'catalog_snapshot_id'
                cursor = src.execute(f'SELECT * FROM {table} WHERE {key} IN (' + ','.join('?' for _ in snapshots) + ')', sorted(snapshots))
                rows = cursor.fetchall()
                columns = [c[0] for c in cursor.description]
                dst.executemany(f'INSERT INTO {table} VALUES (' + ','.join('?' for _ in columns) + ')', rows)
                counts[table] = len(rows)
                if table == 'raw_snapshots':
                    for values in rows:
                        row = dict(zip(columns, values, strict=True))
                        location = Path(row['payload_location'])
                        raw = (source / 'raw_snapshots' / location).resolve()
                        assert raw.is_relative_to((source / 'raw_snapshots').resolve())
                        if not raw.is_file():
                            continue
                        digest = hashlib.sha256(raw.read_bytes()).hexdigest()
                        assert digest == row['payload_hash'], 'Published source hash mismatch'
                        out = (target / 'raw' / location).resolve()
                        assert out.is_relative_to((target / 'raw').resolve())
                        out.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(raw, out)
                        hashes[location.as_posix()] = digest
            dst.commit()
            assert dst.execute('PRAGMA quick_check').fetchone()[0] == 'ok'
    assert store.read_active('Lund') == manifest, 'Publication changed during freeze; retry separately'
    report = {
        'frozen_at_utc': datetime.now(UTC).isoformat(),
        'artifact_sha256': hashlib.sha256(payload).hexdigest(),
        'universe_id': artifact.universe.universe_id,
        'products': len(artifact.universe.products), 'tables': counts,
        'raw_files': len(hashes), 'raw_sha256': hashes,
        'private_tables_copied': False, 'source_read_only': True,
        'external_collection_calls': 0,
    }
    (target / 'freeze.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != 'raw_sha256'}), flush=True)


if __name__ == '__main__':
    main()
