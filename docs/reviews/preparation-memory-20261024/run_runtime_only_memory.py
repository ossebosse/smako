"""Three ordinary write/load sequences without caller-side GC or allocator trim."""
from __future__ import annotations

import json
import os
import subprocess

from run_pilot import IMAGE, REVISION, ROOT, SOURCE, worker, write


def main():
    assert not subprocess.check_output(['docker','ps','--filter','name=smako-preparation-','--format','{{.Names}}']).strip()
    base = json.loads((ROOT/f'candidate-{REVISION}-plain-command.json').read_bytes())
    destination = ROOT/f'runtime-only-memory-{REVISION}'
    destination.mkdir()
    summary = []
    for index in range(1,4):
        folder = destination/str(index)
        folder.mkdir();os.chown(folder,10001,10001)
        args = [s.replace(str(ROOT/f'candidate-{REVISION}-plain')+':/output:rw',str(folder)+':/output:rw') for s in base]
        i = args.index('--entrypoint')
        args[i:i] = ['-v','/tmp/temporary_memory_runtime_only.py:/temporary_memory_entry.py:ro']
        args = args[:args.index(IMAGE)+1]+['-u','/temporary_memory_entry.py',
            '--inputs','/inputs/malmo','--output','/output','--runtime-cleanup-only']
        print(json.dumps({'start':f'runtime-only-memory-{index}'}),flush=True)
        receipt = worker(args,f'smako-preparation-{REVISION}-runtime-memory-{index}',folder)
        report = json.loads((folder/'temporary-memory.json').read_bytes())
        final = json.loads((folder/'final-resource.json').read_bytes())
        assert report['caller_phase_cleanup'] is False
        assert report['memory_target_passed'] and final['memory_target_passed']
        assert report['serialized_sha256'] == '06cbf0b12e619f09dd3709b808916d1c74676859d246ad72f74d52d0e6d91857'
        assert report['held_old_products'] == report['held_new_products'] == 89458 and report['held_fact_rows'] == 71138
        summary.append({'source_commit':SOURCE,'report':report,'receipt':receipt,'final_resource':final})
        write(destination/'summary.json',summary)
    write(destination/'complete.json',{'source_commit':SOURCE,'status':'RUNTIME_CLEANUP_ONLY_MEMORY_PASSED',
        'samples':3,'full_release_qualified':False})


if __name__ == '__main__':
    main()
