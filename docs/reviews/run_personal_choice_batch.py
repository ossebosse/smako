"""Run one explicitly budgeted isolated batch on the existing evidence host."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path('/opt/smako/evidence/personal-choice-latency-20261025')
IMAGE = 'sha256:dc23ba03be3ca2370d28d6230d392160a63fb278a56f5b0171ebe91947713072'
INPUTS = Path('/opt/smako/evidence/preparation-memory-20261024/axfood-facts-eeda184/malmo')


def write(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('arm')
    parser.add_argument('--seconds', type=int, required=True)
    parser.add_argument('--policy', default='smako-verified-reference-v1')
    parser.add_argument('--instrument', action='store_true')
    parser.add_argument('--profile', action='store_true')
    parser.add_argument('--serve-port', type=int)
    parser.add_argument('--cases', nargs='+')
    args = parser.parse_args()
    journal_path = ROOT / 'budget.json'
    journal = json.loads(journal_path.read_bytes()) if journal_path.exists() else []
    assert all(r['status'] == 'closed' for r in journal), 'Unclosed prior reservation; diagnose first'
    used = sum(r['wall_seconds'] for r in journal)
    assert 0 < args.seconds <= 1800 and used + args.seconds <= 7200
    assert not subprocess.check_output(['docker', 'ps', '--filter', 'name=smako-personal-choice-', '--format', '{{.Names}}']).strip()
    folder = ROOT / args.arm
    folder.mkdir()
    os.chown(folder, 10001, 10001)
    source = ROOT / (args.arm.split('-')[0] + '-code')
    assert source.is_dir()
    name = 'smako-personal-choice-' + args.arm
    command = ['docker', 'run', '--name', name, '--network', 'none', '--read-only', '--cpus', '2',
        '--memory', '3g', '--memory-swap', '3g', '--pids-limit', '128', '--user', '10001:10001',
        '--tmpfs', '/tmp:rw,nosuid,size=128m', '-v', f'{source}:/srv/app:ro',
        '-v', f'{ROOT}/personal_choice_probe.py:/probe.py:ro', '-v', f'{INPUTS}:/inputs:ro',
        '-v', f'{ROOT}/ui-requests.json:/ui-requests.json:ro',
        '-v', f'{folder}:/output:rw', '-e', 'PYTHONPATH=/srv/app/backend:/srv/app',
        '-e', 'PYTHON_DOTENV_DISABLED=1', '-e', 'PYTHONDONTWRITEBYTECODE=1',
        '--entrypoint', 'python', IMAGE, '-u', '/probe.py', '--inputs', '/inputs',
        '--output', '/output/result', '--policy', args.policy, '--requests', '/ui-requests.json']
    if args.instrument:
        command.append('--instrument')
    if args.profile:
        command.append('--profile')
    if args.serve_port:
        command[command.index('none')] = 'bridge'
        index = command.index('--entrypoint')
        command[index:index] = ['-p', f'127.0.0.1:{args.serve_port}:{args.serve_port}']
        command.extend(['--serve-port', str(args.serve_port)])
    if args.cases:
        command.extend(['--cases', *args.cases])
    write(folder / 'command.json', command)
    row = {'arm': args.arm, 'reserved_seconds': args.seconds, 'started_at': datetime.now(UTC).isoformat(), 'status': 'running'}
    journal.append(row)
    write(journal_path, journal)
    started = time.perf_counter()
    try:
        with (folder / 'worker.log').open('x') as log:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=args.seconds, check=False)
        row['exit_code'] = result.returncode
    except subprocess.TimeoutExpired:
        subprocess.run(['docker', 'kill', name], check=True, capture_output=True)
        row['exit_code'] = 124
        row['batch_timeout'] = True
    finally:
        row.update(status='closed', wall_seconds=time.perf_counter() - started, ended_at=datetime.now(UTC).isoformat())
        write(journal_path, journal)
        inspection = json.loads(subprocess.check_output(['docker', 'inspect', name]))[0]
        write(folder / 'receipt.json', {'budget': row, 'state': inspection['State'], 'image': inspection['Image'],
            'resources': {k: inspection['HostConfig'][k] for k in ('Memory', 'MemorySwap', 'NanoCpus', 'NetworkMode', 'ReadonlyRootfs')},
            'mounts': [{k: m[k] for k in ('Source', 'Destination', 'RW')} for m in inspection['Mounts']]})
    print(json.dumps(row), flush=True)


if __name__ == '__main__':
    main()
