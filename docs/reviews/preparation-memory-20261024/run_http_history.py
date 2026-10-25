"""Serial ASGI diagnostic, then three fresh-process nonempty-history recoveries.

Run only after the completed pilot. The existing authoritative synthetic saved
revision and private state are backed up through SQLite. Only derived caches
are removed in each recovery copy; no owner/private revision is rewound.
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
from contextlib import closing

from run_pilot import IMAGE, REVISION, ROOT, SOURCE, gates, worker, write


def copy_store(source, destination):
    with (closing(sqlite3.connect(f'file:{source}?mode=ro',uri=True)) as original,
          closing(sqlite3.connect(destination)) as copied):
        original.backup(copied)


def main():
    pilot = json.loads((ROOT/f'pilot-{REVISION}/complete.json').read_bytes())
    assert pilot['status'] == 'PILOT_PASSED_NOT_FULL_MATRIX' and pilot['source_commit'] == SOURCE
    gates()
    destination = ROOT/f'http-history-{REVISION}'
    destination.mkdir()
    template = json.loads((ROOT/f'candidate-{REVISION}-plain-command.json').read_bytes())
    summary = []
    for stage in ('http','prepare','recover-1','recover-2','recover-3'):
        folder = destination/stage
        folder.mkdir()
        if stage != 'http':
            prior = destination/('http' if stage == 'prepare' else 'prepare')
            copy_store(prior/'owned.sqlite',folder/'owned.sqlite')
            if stage == 'prepare':
                shutil.copytree(prior/'prepared',folder/'prepared')
            else:
                with sqlite3.connect(folder/'owned.sqlite') as connection:
                    connection.execute("DELETE FROM planner_owned_artifacts WHERE kind IN ('qualification','menu_view')")
        for path in (folder,*folder.rglob('*')):
            os.chown(path,10001,10001)
        args = [s.replace(str(ROOT/f'candidate-{REVISION}-plain')+':/output:rw',str(folder)+':/output:rw')
                for s in template]
        i = args.index('--entrypoint')
        args[i:i] = ['-v','/tmp/http_history_entry.py:/http_history_entry.py:ro']
        mode = stage.split('-',1)[0]
        args = args[:args.index(IMAGE)+1]+['-u','/http_history_entry.py',
            '--inputs','/inputs/malmo','--output','/output','--store','/output/owned.sqlite','--mode',mode]
        print(json.dumps({'start':stage}),flush=True)
        receipt = worker(args,f'smako-preparation-{REVISION}-history-{stage}',folder)
        report_path = folder/('http-history.json' if stage == 'http' else f'history-{mode}.json')
        data = json.loads(report_path.read_bytes())
        final = json.loads((folder/'final-resource.json').read_bytes())
        assert final['memory_target_passed'] and final['memory']['swap.current'] == 0
        if stage == 'http':
            assert data['status'] == 'HTTP_DIAGNOSTIC_PASSED_NOT_LATENCY_QUALIFICATION'
        summary.append({'stage':stage,'source_commit':SOURCE,'report':data,
                        'receipt':receipt,'final_resource':final})
        write(destination/'summary.json',summary)
    write(destination/'complete.json',{'source_commit':SOURCE,'status':'HTTP_AND_NONEMPTY_HISTORY_DIAGNOSTICS_PASSED',
        'http_samples':1,'fresh_process_cache_loss_samples':3,'full_release_qualified':False})
    # Measure actual late-arriving identities before broadening to the full grid.
    # This child driver has not run during the preceding frozen pilot.
    from run_history_arrival import main as history_arrival
    history_arrival()


if __name__ == '__main__':
    main()
