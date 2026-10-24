"""Bounded serial follow-ups on one explicitly pinned synthetic benchmark.

Run with the existing evidence host's authorized Docker access. Every probe
gets its own public cache/PlanStore copy; no production volume is mounted.
Do not start until the first plain probe has completed and met its memory gate.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import time
from contextlib import closing
from pathlib import Path

ROOT = Path('/opt/smako/evidence/preparation-memory-20261024')
MEMORY_TARGET = 2684354560
EXPECTED_HASH = '1c0ad484edda7e36bf026b83a6e4f171dddf9c8d4a2b3d5359d95fa90bc227b7'


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def counts(path):
    with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as connection:
        return {
            'artifacts': list(connection.execute(
                'SELECT kind, COUNT(*) FROM planner_owned_artifacts GROUP BY kind')),
            'saved_deliveries': connection.execute('SELECT COUNT(*) FROM consumer_plan_revisions').fetchone()[0],
            'owners': connection.execute('SELECT COUNT(*) FROM personal_private_state').fetchone()[0],
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-commit', required=True)
    parser.add_argument('--extra-cold-processes', type=int, default=2, choices=(0, 2))
    options = parser.parse_args()
    commit = options.source_commit
    if len(commit) != 40 or any(c not in '0123456789abcdef' for c in commit):
        parser.error('source-commit must be an exact lowercase Git SHA')
    revision = commit[:7]
    prior = ROOT / f'candidate-{revision}-plain'
    prior_state = json.loads(subprocess.check_output([
        'docker', 'inspect', f'smako-preparation-{revision}-plain']))[0]
    if prior_state['State']['Running']:
        raise RuntimeError('The preceding worker must complete before follow-up probes start')
    if prior_state['State']['ExitCode'] or prior_state['State']['OOMKilled']:
        raise RuntimeError('The preceding worker did not complete cleanly')
    active = subprocess.check_output([
        'docker', 'ps', '--filter', 'name=smako-preparation-', '--format', '{{.Names}}'])
    if active.strip():
        raise RuntimeError('Another preparation probe is running; keep workers serial')
    report = json.loads((prior / 'L5000-verified-distribution.json').read_bytes())
    if (len(report['records']) != 4
            or any(r['outcome'] != 'PASS' or not r['audit_passed'] for r in report['records'])
            or any(r['semantic_sha256'] != EXPECTED_HASH or r['paid'] != 988.32 for r in report['records'])
            or max(r['cgroup_peak_bytes'] for r in report['records']) > MEMORY_TARGET):
        raise RuntimeError('The pilot quality/memory gate is not met; do not broaden qualification')
    write(ROOT / f'candidate-{revision}-receipt.json', {
        'state': prior_state['State'], 'image': prior_state['Image']})
    base = json.loads((ROOT / f'candidate-{revision}-plain-command.json').read_bytes())
    if f'{ROOT}/code-{revision}/backend:/srv/app/backend:ro' not in base:
        raise RuntimeError('Command does not mount the requested source; refuse to relabel evidence')
    destination = ROOT / f'cache-modes-{revision}'
    destination.mkdir()
    modes = [*[(f'cold-{index}', 5000, 1) for index in range(2, options.extra_cold_processes + 2)],
             ('legacy', 5000, 4), ('prefix262', 262, 4),
             *[(f'restart-{index}', 5000, 1) for index in range(1, 4)],
             *[(f'cache-loss-{index}', 5000, 1) for index in range(1, 4)],
             *[(f'new-owner-{index}', 5000, 1) for index in range(1, 4)]]
    summary = []
    for mode, size, repeat in modes:
        started = time.perf_counter()
        output = destination / mode
        output.mkdir()
        empty_app = mode.startswith(('cold-', 'cache-loss'))
        new_owner = mode == 'legacy' or mode.startswith(('new-owner', 'cold-'))
        if not empty_app:
            shutil.copytree(prior / 'prepared', output / 'prepared')
        if not new_owner:
            with (closing(sqlite3.connect(f'file:{prior / "owned.sqlite"}?mode=ro', uri=True)) as source,
                  closing(sqlite3.connect(output / 'owned.sqlite')) as copied):
                source.backup(copied)
                if mode.startswith('cache-loss'):
                    copied.execute("DELETE FROM planner_owned_artifacts WHERE kind IN ('qualification', 'menu_view')")
                    copied.commit()
        for path in [output, *output.rglob('*')]:
            os.chown(path, 10001, 10001)
        before = counts(output / 'owned.sqlite') if (output / 'owned.sqlite').exists() else None
        provision_seconds = time.perf_counter() - started
        args = [arg.replace(str(prior) + ':/output:rw', str(output) + ':/output:rw') for arg in base]
        # Foreground subprocess owns one bounded worker; retain it for OOM/exit evidence.
        if '-d' in args:
            args.remove('-d')
        name = f'smako-preparation-{revision}-{mode}'
        args[args.index('--name') + 1] = name
        args[args.index('--size') + 1] = str(size)
        args[args.index('--repeat') + 1] = str(repeat)
        args[args.index('--arms') + 1] = 'main' if mode == 'legacy' else 'verified'
        if size == 262:
            old = '/opt/smako/evidence/integration-scaling-20261023/final-grid-libraries/5000:/srv/app/backend/app/data/recipes:ro'
            args[args.index(old)] = old.replace('/5000:', '/262:')
        args[args.index('--execution-environment') + 1] = (
            f'Uninstrumented {commit}; serial 2 CPU/3 GiB incl swap; {mode}; '
            'own synthetic store/public cache; OS disk cache uncontrolled')
        write(destination / f'{mode}-command.json', args)
        print(json.dumps({'start': mode, 'provision_seconds': provision_seconds}), flush=True)
        started = time.perf_counter()
        with (destination / f'{mode}.log').open('x') as log:
            result = subprocess.run(args, stdout=log, stderr=subprocess.STDOUT, check=False)
        worker = json.loads(subprocess.check_output(['docker', 'inspect', name]))[0]
        receipt = {'source_commit': commit, 'state': worker['State'], 'image': worker['Image'],
                   'process_wall_seconds': time.perf_counter() - started,
                   'provision_seconds_excluded_from_process': provision_seconds,
                   'before': before,
                   'app_cache_at_start': 'empty' if empty_app else 'copy of prepared primary cache',
                   'owner_store_at_start': 'new' if new_owner else 'backup of synthetic primary store',
                   'after': counts(output / 'owned.sqlite') if (output / 'owned.sqlite').exists() else None}
        write(destination / f'{mode}-receipt.json', receipt)
        summary.append({'mode': mode, **receipt})
        write(destination / 'summary.json', summary)
        print(json.dumps({'complete': mode, 'exit_code': result.returncode,
                          'OOMKilled': worker['State']['OOMKilled']}), flush=True)
        if result.returncode or worker['State']['OOMKilled']:
            raise RuntimeError(f'Failed probe {mode}; preserve evidence before further qualification')
        current = json.loads((output / f'L{size}-{"main" if mode == "legacy" else "verified"}-distribution.json').read_bytes())
        if (any(r['outcome'] != 'PASS' or not r['audit_passed'] for r in current['records'])
                or any(r['paid'] != (996.22 if size == 262 else 988.32) for r in current['records'])
                or (size == 5000 and any(r['semantic_sha256'] != EXPECTED_HASH for r in current['records']))
                or max(r['cgroup_peak_bytes'] for r in current['records']) > MEMORY_TARGET):
            raise RuntimeError(f'Quality/memory gate failed in {mode}; stop the sequence')


if __name__ == '__main__':
    main()
