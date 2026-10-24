"""Bounded serial follow-ups on synthetic 193629f benchmark state.

Run with the existing evidence host's authorized Docker access. Every probe
gets its own public cache/PlanStore copy; no production volume is mounted.
Do not start until the first plain probe has completed and met its memory gate.
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import time
from contextlib import closing
from pathlib import Path

ROOT = Path('/opt/smako/evidence/preparation-memory-20261024')
PRIOR = ROOT / 'candidate-193629f-plain'
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
    prior_state = json.loads(subprocess.check_output([
        'docker', 'inspect', 'smako-preparation-193629f-plain']))[0]
    if prior_state['State']['Running']:
        raise RuntimeError('The preceding worker must complete before follow-up probes start')
    if prior_state['State']['ExitCode'] or prior_state['State']['OOMKilled']:
        raise RuntimeError('The preceding worker did not complete cleanly')
    active = subprocess.check_output([
        'docker', 'ps', '--filter', 'name=smako-preparation-', '--format', '{{.Names}}'])
    if active.strip():
        raise RuntimeError('Another preparation probe is running; keep workers serial')
    report = json.loads((PRIOR / 'L5000-verified-distribution.json').read_bytes())
    if (len(report['records']) != 4
            or any(r['outcome'] != 'PASS' or not r['audit_passed'] for r in report['records'])
            or any(r['semantic_sha256'] != EXPECTED_HASH or r['paid'] != 988.32 for r in report['records'])
            or max(r['cgroup_peak_bytes'] for r in report['records']) > MEMORY_TARGET):
        raise RuntimeError('The pilot quality/memory gate is not met; do not broaden qualification')
    write(ROOT / 'candidate-193629f-receipt.json', {
        'state': prior_state['State'], 'image': prior_state['Image']})
    base = json.loads((ROOT / 'candidate-193629f-plain-command.json').read_bytes())
    destination = ROOT / 'cache-modes-193629f'
    destination.mkdir()
    modes = [('legacy', 5000, 4), ('prefix262', 262, 4),
             *[(f'restart-{index}', 5000, 1) for index in range(1, 4)],
             *[(f'cache-loss-{index}', 5000, 1) for index in range(1, 4)],
             *[(f'new-owner-{index}', 5000, 1) for index in range(1, 4)]]
    summary = []
    for mode, size, repeat in modes:
        started = time.perf_counter()
        output = destination / mode
        output.mkdir()
        if not mode.startswith('cache-loss'):
            shutil.copytree(PRIOR / 'prepared', output / 'prepared')
        if mode != 'legacy' and not mode.startswith('new-owner'):
            with (closing(sqlite3.connect(f'file:{PRIOR / "owned.sqlite"}?mode=ro', uri=True)) as source,
                  closing(sqlite3.connect(output / 'owned.sqlite')) as copied):
                source.backup(copied)
                if mode.startswith('cache-loss'):
                    copied.execute("DELETE FROM planner_owned_artifacts WHERE kind IN ('qualification', 'menu_view')")
                    copied.commit()
        for path in [output, *output.rglob('*')]:
            os.chown(path, 10001, 10001)
        before = counts(output / 'owned.sqlite') if (output / 'owned.sqlite').exists() else None
        provision_seconds = time.perf_counter() - started
        args = [arg.replace(str(PRIOR) + ':/output:rw', str(output) + ':/output:rw') for arg in base]
        # Foreground subprocess owns one bounded worker; retain it for OOM/exit evidence.
        args.remove('-d')
        name = f'smako-preparation-193629f-{mode}'
        args[args.index('--name') + 1] = name
        args[args.index('--size') + 1] = str(size)
        args[args.index('--repeat') + 1] = str(repeat)
        args[args.index('--arms') + 1] = 'main' if mode == 'legacy' else 'verified'
        if size == 262:
            old = '/opt/smako/evidence/integration-scaling-20261023/final-grid-libraries/5000:/srv/app/backend/app/data/recipes:ro'
            args[args.index(old)] = old.replace('/5000:', '/262:')
        args[args.index('--execution-environment') + 1] = (
            f'Uninstrumented 193629f; serial 2 CPU/3 GiB incl swap; {mode}; '
            'own synthetic store/public cache; OS disk cache uncontrolled')
        write(destination / f'{mode}-command.json', args)
        print(json.dumps({'start': mode, 'provision_seconds': provision_seconds}), flush=True)
        started = time.perf_counter()
        with (destination / f'{mode}.log').open('x') as log:
            result = subprocess.run(args, stdout=log, stderr=subprocess.STDOUT, check=False)
        worker = json.loads(subprocess.check_output(['docker', 'inspect', name]))[0]
        receipt = {'state': worker['State'], 'image': worker['Image'],
                   'process_wall_seconds': time.perf_counter() - started,
                   'provision_seconds_excluded_from_process': provision_seconds,
                   'before': before,
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
