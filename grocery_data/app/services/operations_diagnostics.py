"""Bounded administrative diagnostics over existing source and job evidence.

No source fetch, planner, image build or global archive walk is performed.
Snapshots/raw documents remain authoritative; this file is a disposable index.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy.engine import make_url

from grocery_data.app.services.durable_files import atomic_write_bytes

MAX_INCIDENTS = 128
MAX_INDEX_BYTES = 2_000_000
MAX_RAW_BYTES = 32_000_000


def stamp():
    return datetime.now(UTC).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def read_json(path, *, limit=MAX_INDEX_BYTES):
    path = Path(path)
    if not path.exists():
        return {}
    if path.stat().st_size > limit:
        raise ValueError("diagnostic_input_size_exceeded")
    return json.loads(path.read_bytes())


def paths(environment=None):
    env = os.environ if environment is None else environment
    database = Path(make_url(env['GROCERY_DATABASE_URL']).database)
    universe = Path(env['PRICE_UNIVERSE_CACHE_ROOT'])
    return database, universe, universe.parent / 'reports/operations'


def readonly(database):
    db = sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True, timeout=5)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA query_only=ON')
    return db


def classify(metrics, reason):
    diff = metrics.get('effective_schema_diff') or {}
    if any(diff.get(k) for k in ('added', 'removed', 'type_changed')):
        return 'SOURCE_SCHEMA_CHANGED', 'qualification', 'B:review_code_and_replay'
    completion = metrics.get('catalog_completion') or {}
    if any(x.get('conflicting_duplicates', 0) for x in completion.values()):
        return 'SOURCE_COMMERCIAL_CONFLICT', 'collection', 'C:bounded_fresh_attempt'
    run = metrics.get('run_metrics') or {}
    if run.get('rate_limit_count'):
        return 'SOURCE_RATE_LIMITED', 'transport', 'A:wait_then_retry'
    if run.get('http_error_count'):
        return 'SOURCE_TRANSPORT_FAILED', 'transport', 'A:bounded_retry'
    if any(not x.get('complete') for x in completion.values()):
        return 'SOURCE_INCOMPLETE', 'collection', 'A:bounded_fresh_attempt'
    if reason in ('InsufficientStorageError', 'DiskFullError'):
        return 'STORAGE_CAPACITY', 'storage', 'D:capacity_review'
    return 'SOURCE_QUALIFICATION_FAILED', 'qualification', 'B:inspect_retained_evidence'


def evidence(db, snapshot_id):
    row = db.execute('SELECT * FROM catalog_snapshots WHERE id=?', (snapshot_id,)).fetchone()
    if row is None:
        raise LookupError('snapshot_missing')
    metrics = json.loads(row['metrics'] or '{}')
    code, step, action = classify(metrics, row['rejection_reason'])
    refs = [dict(r) for r in db.execute(
        'SELECT kind,store_external_id,payload_location,payload_hash,fetched_at,page_number '
        'FROM raw_snapshots WHERE catalog_snapshot_id=? ORDER BY fetched_at,id', (snapshot_id,))]
    # References only. A complete set is available through reproduce, not copied
    # repeatedly into the bounded current index.
    selected = refs if len(refs) <= 12 else refs[:6] + refs[-6:]
    store_ids = sorted({r['store_external_id'] for r in refs if r['store_external_id']})
    channels = {}
    if store_ids and db.execute("SELECT 1 FROM sqlite_master WHERE name='stores'").fetchone():
        for store_id in store_ids:
            values = [r[0] for r in db.execute('SELECT DISTINCT price_context_type FROM stores '
                                               'WHERE chain=? AND external_id=? AND price_context_type IS NOT NULL',
                                               (row['chain'], store_id))]
            channels[store_id] = values[0] if len(values) == 1 else 'unknown'
    diff = metrics.get('effective_schema_diff') or {}
    signature = digest([row['chain'], row['scope_key'], code, diff])
    return {
        'incident_id': 'source-' + signature[:24], 'signature': signature,
        'code': code, 'chain': row['chain'], 'scope': row['scope_key'],
        'store_ids': store_ids, 'channels': channels, 'coverage': row['coverage'],
        'snapshot_id': row['id'], 'run_id': row['collector_run_id'],
        'parser_version': row['parser_version'], 'connector_version': row['connector_version'],
        'runtime': metrics.get('runtime_build_id', 'unknown_historical_runtime'),
        'failed_step': step, 'next_action': action, 'state': row['state'],
        'observed_at': row['rejected_at'] or row['created_at'],
        'expected': 'qualified_complete_source_with_consistent_contract',
        'observed': {'schema_diff': diff, 'completion': metrics.get('catalog_completion', {})},
        'raw_count': len(refs), 'raw_reference_digest': digest(refs), 'raw_references': selected,
        'raw_references_truncated': len(selected) != len(refs),
        'reproduce': {'command': 'python -m grocery_data.ops reproduce --snapshot-id ' + row['id'],
                      'network_requests': 0, 'source_content_is_untrusted_data': True},
    }


def reproduce(database, raw_root, snapshot_id):
    """Verify selected original bytes and extract exact conflict evidence once.

    No replay database is created by this read-only command. Ordinary replay
    remains a separate explicitly mutating repair operation.
    """
    raw_root = Path(raw_root).resolve()
    with readonly(database) as db:
        out = evidence(db, snapshot_id)
        refs = list(db.execute('SELECT * FROM raw_snapshots WHERE catalog_snapshot_id=? '
                              'ORDER BY fetched_at,id', (snapshot_id,)))
    total = 0
    seen = {}
    conflicts = []
    fields = []
    for rec in refs:
        path = (raw_root / rec['payload_location']).resolve()
        if not path.is_relative_to(raw_root):
            raise ValueError('raw_reference_outside_root')
        total += path.stat().st_size
        if total > MAX_RAW_BYTES:
            raise ValueError('bounded_reproduction_size_exceeded')
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != rec['payload_hash']:
            raise ValueError('raw_hash_mismatch')
        if out['chain'] != 'hemkop':
            continue
        payload = json.loads(data)
        ref = {k: rec[k] for k in ('payload_hash', 'payload_location', 'fetched_at', 'page_number')}
        if rec['kind'] in ('stores', 'store_context'):
            for position, row in enumerate(payload if isinstance(payload, list) else [payload]):
                if isinstance(row, dict) and str(row.get('storeId')) in out['store_ids']:
                    for key in ('hasPickingBaseStore', 'storeId', 'onlineStore'):
                        fields.append({'field': key, 'json_path': (f'$[{position}]' if isinstance(payload, list) else '$')+'.'+key, 'present': key in row,
                                       'value': row.get(key), 'reference': ref})
        if rec['kind'] != 'catalog_page':
            continue
        from grocery_data.app.connectors.hemkop.client import _DUPLICATE_SEMANTIC_FIELDS

        for row in payload.get('results') or []:
            identity = (rec['store_external_id'], row.get('code'))
            value = {k: row.get(k) for k in _DUPLICATE_SEMANTIC_FIELDS}
            if identity in seen and seen[identity][0] != value:
                prior, previous_ref = seen[identity]
                changed = {k: {'before': prior[k], 'after': value[k]}
                           for k in value if prior[k] != value[k]}
                conflicts.append({'store_id': identity[0], 'product_id': identity[1],
                                  'changed': changed, 'first': previous_ref, 'second': ref})
            else:
                seen[identity] = (value, ref)
    out.update(raw_files_verified=len(refs), raw_bytes_verified=total,
               fields=fields[:24], conflicts=conflicts[:4], conflicts_truncated=len(conflicts) > 4)
    return out


def record_incidents(environment=None):
    """Called under the existing operation lease, after a job or demand check.

    Only the latest 100 initial failures, then rowid increments are examined.
    No raw archive scan on an ordinary status read; repeated failures update
    one bounded entry. Recovery of the source is distinct from publication.
    """
    env = os.environ if environment is None else environment
    database, _universe, root = paths(env)
    path = root / 'source-incidents.json'
    index = read_json(path) or {'schema': 'source-incidents-v1', 'watermark': 0, 'incidents': {}}
    with readonly(database) as db:
        if not index['watermark']:
            latest = db.execute('SELECT max(rowid) FROM catalog_snapshots').fetchone()[0] or 0
            index['watermark'] = max(0, latest - 100)
        pending = index.get('pending', [])
        rows = []
        if pending:
            rows.extend(db.execute('SELECT rowid,id,state FROM catalog_snapshots WHERE id IN (' +
                                   ','.join('?' for _ in pending) + ') ORDER BY rowid', pending))
        rows.extend(db.execute('SELECT rowid,id,state FROM catalog_snapshots WHERE rowid>? '
                               'ORDER BY rowid LIMIT 100', (index['watermark'],)))
        index['pending'] = []
        for row in rows:
            index['watermark'] = max(index['watermark'], row['rowid'])
            if row['state'] not in ('promoted', 'rejected'):
                index['pending'].append(row['id'])
                continue
            if row['state'] != 'rejected':
                continue
            current = evidence(db, row['id'])
            key = current['incident_id']
            previous = index['incidents'].get(key, {})
            current.update(first_seen=previous.get('first_seen', current['observed_at']),
                           last_seen=current['observed_at'], occurrences=previous.get('occurrences', 0) + 1,
                           diagnostic_runtime=env.get('BUILD_ID', 'unknown'), status='open')
            # Only a new signature gets a small verified extraction. Repeats
            # retain references to their own newest source and the first proof.
            if not previous:
                try:
                    proof = reproduce(database, env['GROCERY_RAW_SNAPSHOT_ROOT'], row['id'])
                    current['reproduction'] = {k: proof[k] for k in ('fields', 'conflicts', 'raw_files_verified')}
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    current['reproduction_error'] = type(exc).__name__
            else:
                current['reproduction'] = previous.get('reproduction', {})
            index['incidents'][key] = current
        if len(index['pending']) > 128:
            raise ValueError('too_many_unfinished_source_jobs')
        for item in index['incidents'].values():
            active = db.execute('SELECT id,promoted_at FROM catalog_snapshots WHERE chain=? '
                                'AND scope_key=? AND is_active=1 AND state=\'promoted\' '
                                'ORDER BY promoted_at DESC LIMIT 1', (item['chain'], item['scope'])).fetchone()
            item['last_qualified_snapshot'] = active['id'] if active else None
            if active and active['promoted_at'] > item['last_seen']:
                item.update(status='source_recovered', recovered_at=active['promoted_at'])
    ordered = sorted(index['incidents'].values(), key=lambda x: x['last_seen'], reverse=True)[:MAX_INCIDENTS]
    index['incidents'] = {v['incident_id']: v for v in ordered}
    index['checked_at'] = stamp()
    payload = json.dumps(index, ensure_ascii=False, sort_keys=True).encode()
    # Fail visibly, preserve prior index, never hide/truncate source evidence.
    if len(payload) > MAX_INDEX_BYTES:
        raise ValueError('incident_index_size_exceeded')
    atomic_write_bytes(path, payload)
    return index


def request_json(url):
    try:
        try:
            response = urllib.request.urlopen(url, timeout=10)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            return {'http_status': response.status, 'body': json.loads(response.read(1_000_000))}
    except (OSError, ValueError) as exc:
        return {'status': 'unknown', 'error_type': type(exc).__name__, 'observed_at': stamp()}


def status(environment=None, *, now=None):
    env = os.environ if environment is None else environment
    now = now or datetime.now(UTC)
    database, universe, root = paths(env)
    state = read_json(root / 'demand-refresh.json')
    manifest = read_json(universe / 'active' / ('city-' + env.get('REFRESH_CITY', 'Lund').lower() + '.json'))
    base = env.get('INTERNAL_APP_BASE_URL', 'http://127.0.0.1:8000').rstrip('/')
    ready = request_json(base + '/ready')
    serving = request_json(base + '/api/price-universe/status')
    loaded_ids = set(serving.get('body', {}).get('snapshot_ids', []))
    required_ids = set(filter(None, env.get('PRICE_UNIVERSE_REQUIRED_CONTEXT_IDS', '').split(',')))
    contexts = []
    with readonly(database) as db:
        for physical in state.get('base_scope', []):
            if physical['store_id'] not in required_ids:
                continue
            provenance = physical.get('source_provenance', {})
            chain = physical['chain']
            external_id = provenance.get('provider_store_id')
            # Never join large snapshot metrics onto every product before a
            # GROUP BY: SQLite can materialize gigabytes of repeated JSON.
            # Read each active snapshot once, then its small indexed aggregate.
            row = None
            candidates = db.execute('SELECT id,promoted_at, '
                'json_extract(metrics,\'$.source_artifact.sha256\') artifact_sha256 '
                'FROM catalog_snapshots WHERE chain=? AND is_active=1 '
                'AND state=\'promoted\' AND coverage!=\'offers_only\' '
                'ORDER BY promoted_at DESC', (chain,)).fetchall()
            for candidate in candidates:
                observed = db.execute('SELECT min(fetched_at) FROM source_products '
                    'WHERE catalog_snapshot_id=? AND chain=? AND store_external_id=?',
                    (candidate['id'], chain, external_id)).fetchone()[0]
                if observed is not None:
                    row = {**dict(candidate), 'observed': observed}
                    break
            entry = {'context_id': physical['store_id'], 'chain': chain, 'store_id': external_id,
                     'channel': physical.get('price_context_type', provenance.get('price_context_type', 'unknown'))}
            if row:
                age = (now - datetime.fromisoformat(row['observed'])).total_seconds() / 3600
                loaded = row['id'] in loaded_ids
                published = row['id'] in manifest.get('snapshot_ids', [])
                entry.update(snapshot_id=row['id'], observed_at=row['observed'], age_hours=round(age, 3),
                             freshness='STALE' if age >= 48 else 'AGING' if age >= 36 else 'FRESH',
                             remaining_hours=round(48-age, 3), qualified=True,
                             published=published, loaded=loaded, receipt='unknown_until_relay_read',
                             stage='loaded' if loaded else 'published' if published else 'qualified_pending_publication')
                entry['source_artifact_sha256'] = row['artifact_sha256']
                if loaded_ids:
                    served = db.execute('SELECT catalog_snapshot_id,min(fetched_at) observed FROM source_products '
                                        'WHERE chain=? AND store_external_id=? AND catalog_snapshot_id IN (' +
                                        ','.join('?' for _ in loaded_ids) + ') GROUP BY catalog_snapshot_id '
                                        'ORDER BY observed LIMIT 1', (chain, external_id, *sorted(loaded_ids))).fetchone()
                    if served:
                        entry['serving_source'] = {'snapshot_id': served[0], 'observed_at': served[1],
                            'age_hours': round((now-datetime.fromisoformat(served[1])).total_seconds()/3600, 3)}
                retry = state.get('source_retries', {}).get(chain, {}).get('retry_at')
                retry_times = [now] + [datetime.fromisoformat(t) for t in (retry, state.get('retry_at')) if t]
                # Conservative warning estimate, not a runtime guarantee or a
                # new freshness deadline. Based on current 65-minute recovery.
                entry['freshness_risk'] = max(retry_times) + timedelta(minutes=75) >= datetime.fromisoformat(row['observed']) + timedelta(hours=48)
                entry['publication_overdue'] = not loaded and (now - datetime.fromisoformat(row['promoted_at'])).total_seconds() > 4500
            else:
                entry.update(stage='unknown', qualified=False)
            contexts.append(entry)
    # Same-volume copies used by ordinary SQLite build/import plus reserve.
    db_bytes = sum(p.stat().st_size for p in [database, Path(str(database)+'-wal'), Path(str(database)+'-shm')] if p.exists())
    artifact_bytes = manifest.get('artifact_bytes', 0)
    required = 2 * db_bytes + 2 * artifact_bytes + 536_870_912
    free = shutil.disk_usage(database.parent).free
    inbox = Path(env.get('SOURCE_RELAY_INBOX', str(Path(env['GROCERY_RAW_SNAPSHOT_ROOT'])/'source-inbox/willys')))
    queue = {'status': 'unknown', 'reason': 'receiver_inbox_unavailable'}
    if inbox.is_dir():
        artifacts = list(inbox.glob('*.smako-source'))
        queue = {'status': 'observed', 'artifacts': len(artifacts),
                 'bytes': sum(p.stat().st_size for p in artifacts),
                 'meaning': 'retained inbox files; import status comes from snapshot artifact hashes'}
    incidents = read_json(root / 'source-incidents.json')
    blockers = [x['context_id'] for x in contexts if x.get('freshness') == 'STALE' or not x.get('qualified')]
    for item in contexts:
        matches = [x for x in incidents.get('incidents', {}).values()
                   if x['chain'] == item['chain'] and item['store_id'] in x['store_ids'] and x['status'] == 'open']
        item['first_failed_step'] = matches[0]['failed_step'] if matches else None
        item['incident_ids'] = [x['incident_id'] for x in matches]
        if item.get('qualified') and not item.get('loaded'):
            item['publication_waits_for_contexts'] = blockers
    missing = sorted(required_ids - {x['context_id'] for x in contexts})
    return {'schema': 'smako-operations-status-v1', 'checked_at': now.isoformat(),
            'runtime': env.get('BUILD_ID', 'unknown'), 'ready': ready,
            'disk_manifest': manifest.get('universe_id'),
            'loaded_manifest': serving.get('body', {}).get('universe_id'),
            'receiver_inbox': queue,
            'required_contexts': contexts, 'unknown_required_contexts': missing,
            'storage': {'free_bytes': free, 'required_estimate_bytes': required, 'adequate': free >= required,
                        'basis': '2*(database+WAL+SHM)+2*active_artifact+512MiB; queue growth not guaranteed'},
            'retry_at': state.get('retry_at'), 'last_success_at': state.get('last_success_at'),
            'runner': {k: v for k, v in read_json(root/'refresh-runner-status.json').items()
                       if k in ('status', 'run_kind', 'started_at', 'completed_at', 'checked_at', 'exit_code', 'runtime_reload')},
            'incidents': [{k: item[k] for k in ('incident_id', 'signature', 'code', 'chain', 'scope',
                                               'status', 'snapshot_id', 'failed_step', 'next_action',
                                               'first_seen', 'last_seen', 'occurrences')}
                          for item in incidents.get('incidents', {}).values()],
            'incident_index_observed_at': incidents.get('checked_at'),
            'pipeline_incidents': list(read_json(root/'pipeline-incidents.json').get('incidents', {}).values()),
            'external_price_requests': 0, 'external_notification': 'not_configured_by_this_tool',
            'windows': {'status': 'unknown', 'reason': 'requires_local_administrator_status_read'}}


def record_indicators(environment=None):
    """Deduplicate early warnings in existing protected operations storage.

    No external notification is configured here. A repeated observation updates
    last_seen, not occurrences; recovery and recurrence are explicit transitions.
    """
    env = os.environ if environment is None else environment
    _database, _universe, root = paths(env)
    current = status(env)
    flags = {'storage_capacity': not current['storage']['adequate']}
    for context in current['required_contexts']:
        key = context['context_id']
        flags[key+':failed_source'] = bool(context['incident_ids'])
        flags[key+':publication_delayed'] = context.get('publication_overdue', False)
        flags[key+':freshness_at_risk'] = context.get('freshness_risk', False)
    for key in current['unknown_required_contexts']:
        flags[key+':status_unknown'] = True
    path = root/'drift-indicators.json'
    history = read_json(path) or {'schema': 'drift-indicators-v1', 'indicators': {}}
    now = current['checked_at']
    for key, value in flags.items():
        prior = history['indicators'].get(key)
        if value:
            if prior is None:
                prior = {'first_seen': now, 'occurrences': 0, 'active': False}
            if not prior['active']:
                prior['occurrences'] += 1
            prior.update(active=True, last_seen=now)
            history['indicators'][key] = prior
        elif prior and prior['active']:
            prior.update(active=False, recovered_at=now)
    history.update(checked_at=now, notification='protected_status_only_no_external_delivery',
                   treatment_estimate_minutes=75, estimate_is_not_guarantee=True)
    atomic_write_bytes(path, json.dumps(history).encode())
    if (current['ready'].get('http_status') == 200
            and current['loaded_manifest'] == current['disk_manifest']
            and current['required_contexts']
            and not current['unknown_required_contexts']
            and all(c.get('loaded') and c.get('freshness') != 'STALE' for c in current['required_contexts'])):
        pipeline_path = root/'pipeline-incidents.json'
        pipeline = read_json(pipeline_path)
        if pipeline:
            for item in pipeline.get('incidents', {}).values():
                if item['status'] == 'open':
                    item.update(status='recovered', recovered_at=now, verified_manifest=current['loaded_manifest'])
            atomic_write_bytes(pipeline_path, json.dumps(pipeline).encode())
    return {'active': [k for k,v in history['indicators'].items() if v['active']],
            'notification': history['notification'], 'checked_at': now}


def schema_holds(operations_root):
    """An explicit reviewed replay/repair clears a deterministic schema hold.

    Do not repeatedly full-crawl identical rejected contracts. This does not
    mark a source fresh and never removes other chains from recovery.
    """
    index = read_json(Path(operations_root)/'source-incidents.json')
    result = {}
    for item in index.get('incidents', {}).values():
        if (item['code'] == 'SOURCE_SCHEMA_CHANGED' and item['status'] == 'open'
                and item.get('coverage') == 'full_online_catalog'):
            result.setdefault(item['chain'], []).extend(item['store_ids'])
    return {chain: sorted(set(stores)) for chain, stores in result.items()}


def record_pipeline_failure(stage, exc, *, scope):
    """Preserve actionable stack locations, never exception text or locals."""
    import traceback

    _database, _universe, root = paths()
    frames = []
    for frame in traceback.extract_tb(exc.__traceback__)[-12:]:
        parts = Path(frame.filename).parts
        start = next((i for i,p in enumerate(parts) if p in ('grocery_data', 'backend', 'deploy')), len(parts)-1)
        frames.append({'file': '/'.join(parts[start:]), 'line': frame.lineno, 'function': frame.name})
    signature = digest([stage, scope, type(exc).__name__, frames])
    key = 'pipeline-' + signature[:24]
    path = root/'pipeline-incidents.json'
    index = read_json(path) or {'schema': 'pipeline-incidents-v1', 'incidents': {}}
    old = index['incidents'].get(key, {})
    now = stamp()
    item = {'incident_id': key, 'signature': signature, 'code': 'PIPELINE_' + stage.upper() + '_FAILED',
            'failed_step': stage, 'scope': scope, 'status': 'open', 'error_type': type(exc).__name__,
            'runtime': os.getenv('BUILD_ID', 'unknown'), 'frames': frames,
            'first_seen': old.get('first_seen', now), 'last_seen': now,
            'occurrences': old.get('occurrences', 0) + 1,
            'expected': 'validated_complete_federation', 'observed': 'exception_before_success',
            'next_action': 'B:review_exact_stack_then_guarded_publish',
            'raw_source_evidence': 'source-incidents.json and retained snapshots; no duplicated raw archive'}
    index['incidents'][key] = item
    index['incidents'] = dict(list(index['incidents'].items())[-64:])
    atomic_write_bytes(path, json.dumps(index).encode())
    return key
