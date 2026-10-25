"""Three frozen samples per validity/cache path, serial and without overwrites."""
from __future__ import annotations

import hashlib
import itertools
import json
import os
import shutil
import sqlite3
from contextlib import closing
from pathlib import Path

from run_pilot import IMAGE, LIBRARIES, REVISION, ROOT, SOURCE, gates, worker, write

METHOD = '17568fe52f2f4da372b1263979673cb79f74f731fa8ada05acc6fe8058e0d6b6'


def backup(source,destination):
    with (closing(sqlite3.connect(f'file:{source}?mode=ro',uri=True)) as original,
          closing(sqlite3.connect(destination)) as copied):
        original.backup(copied)


def main():
    gates()
    source = ROOT/f'http-history-{REVISION}'
    completed = json.loads((source/'complete.json').read_bytes())
    assert completed['status'] == 'HTTP_AND_NONEMPTY_HISTORY_DIAGNOSTICS_PASSED'
    prepared = source/'prepare'
    baseline = json.loads((prepared/'history-prepare.json').read_bytes())
    baseline_protocol = json.loads((prepared/'protocol.json').read_bytes())
    assert baseline_protocol['method_signature'] == METHOD and baseline_protocol['source_commit'] == SOURCE
    assert baseline['quality']['audit_passed'] and baseline['actual_pantry_revision'] == 1
    assert baseline['before']['saved_revisions'] == baseline['after']['saved_revisions'] == 1
    assert baseline['after']['private_sha256'] == baseline['before']['private_sha256']
    destination = ROOT/f'history-arrival-{REVISION}'
    destination.mkdir()
    snapshot = destination/'source-owned.sqlite'
    backup(prepared/'owned.sqlite',snapshot)
    template = json.loads((ROOT/f'candidate-{REVISION}-plain-command.json').read_bytes())
    summary = []
    libraries = {size:json.loads((ROOT/f'pilot-{REVISION}/original/malmo'/str(size)/
        f'L{size}-main-distribution.json').read_bytes())['library_version'] for size in (262,5000)}
    entry_sha = hashlib.sha256(Path('/tmp/history_arrival_entry.py').read_bytes()).hexdigest()
    bootstrap_sha = hashlib.sha256(Path('/tmp/http_history_entry.py').read_bytes()).hexdigest()
    write(destination/'protocol.json',{'source_commit':SOURCE,'samples_per_mode':3,
        'modes':['valid/prepared','valid/certificate','incomplete/prepared','incomplete/certificate'],
        'controller_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'probe_entry_sha256':entry_sha,'bootstrap_entry_sha256':bootstrap_sha,
        'method_signature':METHOD,'library_versions':libraries,'inputs':baseline_protocol['inputs'],
        'source_snapshot_sha256':hashlib.sha256(snapshot.read_bytes()).hexdigest(),
        'source_history':baseline['after'],
        'limitations':['Native PlanStore arrivals, separate from ordinary HTTP Save',
            'Incomplete means four meals valid for the past request but not the current five-meal layout',
            'Synthetic checkout rejection is covered separately by permanent regression tests',
            'Arrival times include a CPython call-profile hook; native method objects and results are unchanged',
            'Fresh processes with copied warm public disk; OS disk cache uncontrolled']})
    for kind,cache_path,index in itertools.product(('valid','incomplete'),('prepared','certificate'),range(1,4)):
        pair = destination/kind/cache_path/str(index)
        pair.mkdir(parents=True)
        for stage,size in (('seed',262),('arrival',5000)):
            folder = pair/stage
            folder.mkdir()
            prior = snapshot if stage == 'seed' else pair/'seed/owned.sqlite'
            backup(prior,folder/'owned.sqlite')
            expected_history = (baseline['after']['history_sha256'] if stage == 'seed' else
                json.loads((pair/'seed/history-seed.json').read_bytes())['after']['history_sha256'])
            expected_private = baseline['after']['private_sha256']
            expected_revision = baseline['actual_pantry_revision']
            if stage == 'arrival':
                seeded = json.loads((pair/'seed/history-seed.json').read_bytes())
                expected_private = seeded['after']['private_sha256']
                expected_revision = seeded['private_revision_after']
            assert expected_revision == (1 if stage == 'seed' else 2)
            shutil.copytree(prepared/'prepared',folder/'prepared')
            if stage == 'arrival' and cache_path == 'certificate':
                with sqlite3.connect(folder/'owned.sqlite') as connection:
                    connection.execute("DELETE FROM planner_owned_artifacts WHERE kind='menu_view'")
            for path in (folder,*folder.rglob('*')):
                os.chown(path,10001,10001)
            args = [value.replace(str(ROOT/f'candidate-{REVISION}-plain')+':/output:rw',str(folder)+':/output:rw')
                    .replace(str(LIBRARIES/'5000')+':',str(LIBRARIES/str(size))+':') for value in template]
            i = args.index('--entrypoint')
            args[i:i] = ['-v','/tmp/http_history_entry.py:/http_history_entry.py:ro',
                         '-v','/tmp/history_arrival_entry.py:/history_arrival_entry.py:ro']
            args = args[:args.index(IMAGE)+1]+['-u','/history_arrival_entry.py',
                '--inputs','/inputs/malmo','--output','/output','--store','/output/owned.sqlite',
                '--stage',stage,'--arrival-kind',kind,'--cache-path',cache_path,
                '--expected-private-sha256',expected_private,
                '--expected-history-sha256',expected_history,
                '--expected-revision',str(expected_revision),
                '--expected-context',baseline['quality']['verified_reference']['context'],
                '--baseline-paid',str(baseline['quality']['paid'])]
            print(json.dumps({'start':str(folder)}),flush=True)
            receipt = worker(args,f'smako-preparation-{REVISION}-arrival-{kind}-{cache_path}-{index}-{stage}',folder)
            report_path = folder/f'history-{stage}.json'
            report = json.loads(report_path.read_bytes())
            final = json.loads((folder/'final-resource.json').read_bytes())
            assert final['measurement_complete'] and final['memory_target_passed']
            assert final['target_enforced_for_current_runtime']
            assert final['method_signature'] == final['target_method_signature']
            assert final['method_signature'] == METHOD
            assert final['entry_sha256'] == entry_sha
            assert final['memory']['swap.current'] == 0
            assert final['report_sha256'] == hashlib.sha256(report_path.read_bytes()).hexdigest()
            protocol = json.loads((folder/'protocol.json').read_bytes())
            assert protocol['bootstrap_entry_sha256'] == bootstrap_sha
            assert protocol['probe_entry_sha256'] == entry_sha and protocol['method_signature'] == METHOD
            assert protocol['inputs'] == baseline_protocol['inputs']
            assert protocol['library_version'] == libraries[size]
            summary.append({'kind':kind,'cache_path':cache_path,'sample':index,'stage':stage,
                'report':report,'receipt':receipt,'final_resource':final})
            write(destination/'summary.json',summary)
    assert len(summary) == 24
    write(destination/'complete.json',{'source_commit':SOURCE,'status':'HISTORY_ARRIVAL_MODES_PASSED',
        'samples_per_mode':3,'arrival_samples':12,'seed_workers':12,'full_release_qualified':False})


if __name__ == '__main__':
    main()
