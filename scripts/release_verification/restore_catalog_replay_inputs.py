"""Restore authentic raw input metadata, then use immutable runtime replay.

Only three reviewed Lund online snapshots; no product/price/plan/user tables
are copied. Original raw hashes and times are mandatory. Existing rows remain.
Run the pinned image with network none and the source evidence mounted read-only.
"""
import argparse
import asyncio
import hashlib
import json
import os
import shutil
import sqlite3
from pathlib import Path
from types import SimpleNamespace

from grocery_data import __main__ as cli
from grocery_data.app.services.manual_refresh_operations import (
    RefreshRunLock,
    production_refresh_lock_path,
)

p = argparse.ArgumentParser()
p.add_argument('--apply', action='store_true')
args = p.parse_args()
source_path = Path('/evidence/grocery.sqlite')
target_path = Path('/srv/app/var/grocery/grocery_data.sqlite')
source_raw = Path('/evidence/raw')
target_raw = Path('/srv/app/var/raw_snapshots')
targets = [('coop', '512e0fab56674cce8498757944a8e119'),
           ('hemkop', '92d1e8138efb41878d4d5ded88fd3be5'),
           ('hemkop', '228179f436044eba99af165b817b89b3')]
wal = Path(str(source_path) + '-wal')
assert not wal.exists() or wal.stat().st_size == 0
source = sqlite3.connect(source_path.as_uri() + '?mode=ro&immutable=1', uri=True)
source.row_factory = sqlite3.Row
source.execute('PRAGMA temp_store=MEMORY')
catalogs, runs, raw = {}, {}, {}


def catalog(sid):
    if sid is None or sid in catalogs:
        return
    row = source.execute('SELECT * FROM catalog_snapshots WHERE id=?', (sid,)).fetchone()
    assert row is not None
    catalogs[sid] = dict(row)
    if row['collector_run_id']:
        run = source.execute('SELECT * FROM collector_runs WHERE id=?', (row['collector_run_id'],)).fetchone()
        assert run is not None
        runs[run['id']] = dict(run)
    catalog(row['previous_active_snapshot_id'])


for chain, sid in targets:
    catalog(sid)
    assert catalogs[sid]['chain'] == chain and catalogs[sid]['is_active']
    assert catalogs[sid]['coverage'] == 'full_online_catalog'
    for row in source.execute('SELECT * FROM raw_snapshots WHERE catalog_snapshot_id=?', (sid,)):
        row = dict(row)
        path = (source_raw / row['payload_location']).resolve()
        assert path.is_relative_to(source_raw)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row['payload_hash']
        target = (target_raw / row['payload_location']).resolve()
        assert target.is_relative_to(target_raw)
        if target.exists():
            assert hashlib.sha256(target.read_bytes()).hexdigest() == row['payload_hash']
        raw[row['id']] = row
assert len(raw) > 0
report = {'raw_files_verified': len(raw), 'source_snapshots': targets,
          'raw_observations_unchanged': True, 'copied_product_tables': False,
          'plan_database_touched': False, 'mode': 'apply' if args.apply else 'validation_only'}
print(json.dumps(report), flush=True)
if not args.apply:
    raise SystemExit(0)
assert os.environ['GROCERY_RAW_SNAPSHOT_ROOT'] == str(target_raw)
with RefreshRunLock(production_refresh_lock_path(target_path, Path('/srv/app/var/price_universes'))):
    with sqlite3.connect(target_path) as db:
        # Preserve parent references; all copied historical metadata is inactive.
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('BEGIN IMMEDIATE')
        db.execute('PRAGMA defer_foreign_keys=ON')
        for table, rows in [('collector_runs', runs), ('catalog_snapshots', catalogs), ('raw_snapshots', raw)]:
            cols = [r[1] for r in db.execute('PRAGMA table_info(' + table + ')')]
            for row in rows.values():
                assert set(cols) == set(row)
                existing = db.execute('SELECT * FROM ' + table + ' WHERE id=?', (row['id'],)).fetchone()
                if existing:
                    # Historical promotion/run state may legitimately differ.
                    if table == 'raw_snapshots':
                        assert dict(zip(cols, existing, strict=True)) == row
                    continue
                restored = dict(row)
                if table == 'catalog_snapshots':
                    restored['is_active'] = 0
                db.execute('INSERT INTO ' + table + ' (' + ','.join(cols) + ') VALUES (' + ','.join('?' for _ in cols) + ')', [restored[c] for c in cols])
        for row in raw.values():
            target = target_raw / row['payload_location']
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_raw / row['payload_location'], target)
                assert hashlib.sha256(target.read_bytes()).hexdigest() == row['payload_hash']
        db.commit()
    # CLI replay reparses, qualifies and promotes with the unmodified release.
    # No accept-schema-change override and no fake collection/observation time.
    for chain, sid in targets:
        result = asyncio.run(cli._replay(SimpleNamespace(chain=chain, snapshot_id=sid,
                                                       promote=True, accept_schema_change=False)))
        assert result == 0, (chain, sid, result)
print(json.dumps({'restoration_and_ordinary_replay': 'PASS', 'network': 'none'}), flush=True)
