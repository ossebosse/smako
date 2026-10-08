"""One admin entry point: local relay + existing SSH server diagnostics.

Default status is read-only. SSH credentials and private configuration are
never emitted. An unreachable side remains explicitly unknown.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path


def bounded_json(path):
    if not path.is_file():
        return None
    if path.stat().st_size > 1_000_000:
        raise ValueError('local_status_file_too_large')
    return json.loads(path.read_bytes())


def relay_status(workspace, pwsh):
    if os.name != 'nt':
        return {'status': 'unknown', 'reason': 'Windows_not_available', 'last_observed_at': None}
    out = {'checked_at': datetime.now(UTC).isoformat(), 'volumes': {}}
    for volume in ('C:/', 'D:/'):
        try:
            usage = shutil.disk_usage(volume)
            out['volumes'][volume] = {'free_bytes': usage.free, 'total_bytes': usage.total}
        except OSError as exc:
            out['volumes'][volume] = {'status': 'unknown', 'error_type': type(exc).__name__}
    if not workspace.is_dir():
        return {**out, 'status': 'unknown', 'reason': 'relay_workspace_unavailable'}
    try:
        qualified = bounded_json(workspace / 'last-qualified-source.json') or {}
        receipt = bounded_json(workspace / 'last-success.json') or {}
        out['qualified'] = {k: qualified.get(k) for k in ('sha256', 'observed_from', 'completed_at', 'collection_day')}
        out['receipt'] = {k: receipt.get(k) for k in ('sha256', 'observed_from', 'completed_at', 'server')}
        out['pending_delivery'] = bool(qualified.get('sha256') and qualified.get('sha256') != receipt.get('sha256'))
        files = list((workspace / 'completed').glob('*.smako-source'))
        out['queue_artifacts'] = len(files)
        out['queue_bytes'] = sum(p.stat().st_size for p in files)
        logs = sorted((workspace / 'logs').glob('*.jsonl'), key=lambda p: p.stat().st_mtime, reverse=True)
        if logs:
            latest = logs[0]
            out['last_observed_at'] = datetime.fromtimestamp(latest.stat().st_mtime, UTC).isoformat()
            with latest.open('rb') as handle:
                handle.seek(max(0, latest.stat().st_size - 65536))
                lines = handle.read().splitlines()
            events = []
            for line in lines:
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                events.append({k: event[k] for k in ('event', 'status', 'at', 'timestamp', 'error_type', 'exit_code') if k in event})
            out['recent_events'] = events[-8:]
            out['activity_overdue'] = (datetime.now(UTC).timestamp()-latest.stat().st_mtime) > 10*3600
        command = "$t=Get-ScheduledTask -TaskName 'Smako Willys Local Relay' -ErrorAction Stop; $i=$t|Get-ScheduledTaskInfo; [ordered]@{state=[string]$t.State;enabled=$t.Settings.Enabled;last_result=$i.LastTaskResult;last_run=$i.LastRunTime.ToUniversalTime().ToString('o');next_run=$i.NextRunTime.ToUniversalTime().ToString('o');execute=$t.Actions.Execute;arguments=$t.Actions.Arguments;working_directory=$t.Actions.WorkingDirectory;user=$t.Principal.UserId;logon_type=[string]$t.Principal.LogonType;run_level=[string]$t.Principal.RunLevel}|ConvertTo-Json -Compress"
        result = subprocess.run([str(pwsh), '-NoProfile', '-NonInteractive', '-Command', command],
                                capture_output=True, text=True, timeout=30, check=True)
        out['task'] = json.loads(result.stdout)
        out['status'] = 'observed'
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        out.update(status='unknown', error_type=type(exc).__name__)
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='smako', help='Existing administrative SSH alias')
    parser.add_argument('--workspace', type=Path, default=Path('D:/smako-local-relay/scopes/municipality-1281'))
    parser.add_argument('--pwsh', type=Path, default=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe')
    parser.add_argument('operation', nargs=argparse.REMAINDER, help='status, incidents, reproduce or guarded repair arguments')
    args = parser.parse_args()
    operation = args.operation or ['status']
    # SSH is a shell boundary: quote every argument, never interpolate source data.
    import shlex

    command = shlex.join(['sudo', '-n', 'docker', 'exec', '--user', '10001:10001',
                         'smako-scheduler-1', 'python', '-m', 'grocery_data.ops', *operation])
    try:
        proc = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', args.host, command],
                              capture_output=True, text=True, encoding='utf-8', check=False,
                              timeout=7500 if 'repair' in operation else 90)
        if '--help' in operation and proc.returncode == 0:
            print(proc.stdout)
            return 0
        try:
            server = json.loads(proc.stdout.splitlines()[-1])
        except (ValueError, IndexError):
            # Raw exceptions can contain private infrastructure details. Keep
            # the remote error class only; operator may inspect protected logs.
            server = {'status': 'unknown', 'reason': 'remote_command_failed', 'exit_code': proc.returncode}
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        server = {'status': 'unknown', 'reason': 'server_unreachable_or_invalid_status', 'error_type': type(exc).__name__}
    if operation == ['status']:
        windows = relay_status(args.workspace, args.pwsh)
        qualified = windows.get('qualified', {}).get('sha256')
        imported = [x for x in server.get('required_contexts', []) if qualified and x.get('source_artifact_sha256') == qualified]
        if imported and windows.get('pending_delivery'):
            windows['delivery_stage'] = 'imported_waiting_receipt' if all(x.get('loaded') for x in imported) else 'imported_waiting_publication'
        print(json.dumps({'server': server, 'windows': windows}, ensure_ascii=False))
    else:
        print(json.dumps(server, ensure_ascii=False))
    return int(server.get('status') in ('unknown', 'failed'))


if __name__ == '__main__':
    raise SystemExit(main())
