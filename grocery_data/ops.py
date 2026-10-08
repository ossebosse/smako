"""Administrative status/reproduction and guarded repairs using existing jobs."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import UTC, datetime
from types import SimpleNamespace

from grocery_data.app.services.operations_diagnostics import (
    evidence,
    paths,
    read_json,
    readonly,
    record_incidents,
    reproduce,
    stamp,
    status,
)


def repair(args):
    from deploy.scripts.run_daily_refresh import (
        _operations_lock,
        _run_locked,
        build_refresh_command,
    )
    from grocery_data import __main__ as cli
    from grocery_data.app.services.durable_files import atomic_write_bytes

    database, _universe, root = paths()
    with _operations_lock() as lock:
        index = read_json(root / 'source-incidents.json')
        incident = index.get('incidents', {}).get(args.incident_id)
        pipeline = False
        if incident is None and args.action == 'publish':
            incident = read_json(root/'pipeline-incidents.json').get('incidents', {}).get(args.incident_id)
            pipeline = incident is not None
        if incident is None or incident['signature'] != args.signature:
            raise ValueError('incident_identity_changed_or_missing')
        if args.action != 'publish' and incident.get('status') != 'open':
            raise ValueError('incident_already_recovered')
        if args.runtime != os.environ.get('BUILD_ID'):
            raise ValueError('reviewed_runtime_does_not_match')
        current = incident
        if not pipeline:
            with readonly(database) as db:
                current = evidence(db, incident['snapshot_id'])
                if current['code'] == 'SOURCE_COMMERCIAL_CONFLICT':
                    current = reproduce(database, os.environ['GROCERY_RAW_SNAPSHOT_ROOT'], incident['snapshot_id'])
                if current['signature'] != args.signature or current['state'] != 'rejected':
                    raise ValueError('source_state_changed_rediagnose')
        report = status()
        if not report['storage']['adequate']:
            raise ValueError('insufficient_storage_margin')
        related = [x for x in report['required_contexts'] if x['chain'] == incident.get('chain')]
        if args.action == 'publish':
            if not report['required_contexts'] or report['unknown_required_contexts'] or any(not x.get('qualified') or x.get('freshness') == 'STALE' for x in report['required_contexts']):
                raise ValueError('mandatory_sources_not_qualified_and_fresh')
        elif any(x.get('snapshot_id') != incident.get('last_qualified_snapshot') for x in related
                 if x['store_id'] in incident['store_ids']):
            raise ValueError('qualified_source_changed_rediagnose')
        history_path = root / 'incident-repairs.json'
        history = read_json(history_path) or {'attempts': {}}
        key = ':'.join([args.incident_id, incident.get('snapshot_id') or report.get('disk_manifest', 'unknown'), args.action, args.runtime])
        if key in history['attempts']:
            raise ValueError('repair_already_attempted_read_result_before_new_action')
        command = None
        if args.action == 'replay':
            if current['code'] != 'SOURCE_SCHEMA_CHANGED':
                raise ValueError('replay_not_permitted_for_this_failure')
            from grocery_data.app.domain import Chain, CoverageLevel
            with readonly(database) as db:
                row = db.execute('SELECT coverage,metrics FROM catalog_snapshots WHERE id=?',
                                 (incident['snapshot_id'],)).fetchone()
            connector = cli._replay_connector(Chain(current['chain']),
                coverage=CoverageLevel(row['coverage']),
                catalog_completion=json.loads(row['metrics'] or '{}').get('catalog_completion', {}))
            if connector.parser_version == incident['parser_version']:
                raise ValueError('same_parser_cannot_repair_schema')
            proof = reproduce(database, os.environ['GROCERY_RAW_SNAPSHOT_ROOT'], incident['snapshot_id'])
            oldest = min(datetime.fromisoformat(r['fetched_at']) for r in proof['raw_references'])
            if (datetime.now(UTC) - oldest).total_seconds() >= 48*3600:
                raise ValueError('retained_source_expired')
        elif args.action == 'retry':
            if current['code'] not in ('SOURCE_COMMERCIAL_CONFLICT', 'SOURCE_TRANSPORT_FAILED', 'SOURCE_RATE_LIMITED', 'SOURCE_INCOMPLETE'):
                raise ValueError('code_review_required_no_identical_schema_recrawl')
            if current['chain'] != 'hemkop' or len(current['store_ids']) != 1:
                raise ValueError('no_verified_context_scoped_retry_adapter_use_existing_source_job')
            state = read_json(root / 'demand-refresh.json')
            retry = state.get('source_retries', {}).get(current['chain'], {}).get('retry_at')
            if retry and datetime.fromisoformat(retry) > datetime.now(UTC):
                raise ValueError('source_retry_deadline_not_reached')
            allowed = set(os.environ.get('HEMKOP_STORE_EXTERNAL_IDS', '').split(','))
            if not set(current['store_ids']).issubset(allowed):
                raise ValueError('store_outside_current_allowlist')
            command = build_refresh_command() + ['--chain', 'hemkop', '--no-external-refresh']
        else:
            command = build_refresh_command() + ['--chain', 'citygross', '--no-external-refresh']
        if not args.apply:
            return {'status': 'dry_run', 'action': args.action, 'incident_id': args.incident_id,
                    'runtime': args.runtime, 'source_writes': False, 'network_requests': 0,
                    'operation_lease_checked': True}
        history['attempts'][key] = {'started_at': stamp(), 'status': 'running'}
        # Bound attempts, retain newest records; originals remain in job logs.
        history['attempts'] = dict(list(history['attempts'].items())[-128:])
        atomic_write_bytes(history_path, json.dumps(history).encode())
        try:
            if args.action == 'replay':
                code = asyncio.run(cli._replay(SimpleNamespace(chain=incident['chain'],
                    snapshot_id=incident['snapshot_id'], promote=True, accept_schema_change=False)))
            else:
                old_allowlist = os.environ.get('HEMKOP_STORE_EXTERNAL_IDS')
                try:
                    if args.action == 'retry':
                        os.environ['HEMKOP_STORE_EXTERNAL_IDS'] = current['store_ids'][0]
                    code = _run_locked(lock, started_at=datetime.now(UTC), command=command,
                                       run_kind='incident_' + args.action)
                finally:
                    if old_allowlist is not None:
                        os.environ['HEMKOP_STORE_EXTERNAL_IDS'] = old_allowlist
            history['attempts'][key].update(status='complete' if code == 0 else 'failed', exit_code=code)
        except Exception as exc:
            history['attempts'][key].update(status='failed', error_type=type(exc).__name__)
            raise
        finally:
            history['attempts'][key]['completed_at'] = stamp()
            atomic_write_bytes(history_path, json.dumps(history).encode())
            record_incidents()
        return history['attempts'][key]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('status')
    commands.add_parser('incidents')
    rep = commands.add_parser('reproduce')
    rep.add_argument('--snapshot-id', required=True)
    action = commands.add_parser('repair')
    action.add_argument('--incident-id', required=True)
    action.add_argument('--signature', required=True)
    action.add_argument('--runtime', required=True)
    action.add_argument('--action', choices=('replay', 'retry', 'publish'), required=True)
    action.add_argument('--apply', action='store_true')
    args = parser.parse_args(argv)
    database, _universe, root = paths()
    if args.command == 'status':
        result = status()
    elif args.command == 'incidents':
        result = {'sources': read_json(root / 'source-incidents.json'),
                  'pipeline': read_json(root/'pipeline-incidents.json')}
    elif args.command == 'reproduce':
        result = reproduce(database, os.environ['GROCERY_RAW_SNAPSHOT_ROOT'], args.snapshot_id)
    else:
        result = repair(args)
    print(json.dumps(result, ensure_ascii=False, default=str))
    return int(result.get('status') == 'failed')


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, LookupError) as exc:
        import re

        message = str(exc)
        code = message if re.fullmatch('[a-z_]{1,100}', message) else type(exc).__name__
        print(json.dumps({'status': 'failed', 'code': code}))
        raise SystemExit(1) from None
