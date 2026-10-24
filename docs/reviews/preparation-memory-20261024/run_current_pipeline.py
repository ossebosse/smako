"""Foreground, fail-closed serial verification of the pinned current runtime.

This is an evidence command, not an installed scheduler or app queue. It waits
for this task's three temporary-memory probes before any new menu worker.
Every later stage is entered only after the previous subprocess succeeds.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
import zipfile
from pathlib import Path

from run_pilot import IMAGE, LIMIT, REVISION, ROOT, SOURCE, write

METHOD = '17568fe52f2f4da372b1263979673cb79f74f731fa8ada05acc6fe8058e0d6b6'
ARCHIVE_SHA = 'b54bf786e1344df6d0fb36e77ba7db97de1ce224bad93d7daed7ecfed494c8a1'
EXPECTED = '1c0ad484edda7e36bf026b83a6e4f171dddf9c8d4a2b3d5359d95fa90bc227b7'


def main():
    assert SOURCE == 'eeda184926f02e73ab76e71e50c740e9dcb01b02'
    deadline = time.monotonic()+1800
    while subprocess.run(['pgrep','-f',f'^python3 /tmp/run_temporary_{REVISION}.py$'],capture_output=True,check=False).stdout.strip():
        if time.monotonic()>deadline:
            raise TimeoutError('Temporary-memory sequence did not finish; no menu worker started')
        time.sleep(5)
    trials = json.loads((ROOT/f'temporary-memory-{REVISION}-summary.json').read_bytes())
    assert len(trials) == 3
    for trial in trials:
        assert trial['receipt']['source_commit'] == SOURCE
        assert trial['receipt']['state']['ExitCode'] == 0 and not trial['receipt']['state']['OOMKilled']
        assert trial['final_resource']['memory_target_passed']
        assert trial['report']['method_signature'] == METHOD
    assert not subprocess.check_output(['docker','ps','--filter','name=smako-preparation-','--format','{{.Names}}']).strip()
    archive = Path('/tmp/candidate-catalogue-row-io.zip')
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == ARCHIVE_SHA
    code = ROOT/f'code-{REVISION}'
    with zipfile.ZipFile(archive) as bundle:
        for entry in bundle.infolist():
            if not entry.is_dir():
                assert hashlib.sha256(bundle.read(entry)).digest() == hashlib.sha256((code/entry.filename).read_bytes()).digest()
    output = ROOT/f'candidate-{REVISION}-plain'
    output.mkdir();os.chown(output,10001,10001)
    args = json.loads((ROOT/'candidate-b5c242d-plain-command.json').read_bytes())
    args = [s.replace(str(ROOT/'code-b5c242d'),str(code))
             .replace(str(ROOT/'candidate-b5c242d-plain')+':/output:rw',str(output)+':/output:rw') for s in args]
    args.remove('-d')
    name = f'smako-preparation-{REVISION}-plain'
    args[args.index('--name')+1] = name
    i = args.index('--entrypoint');args[i:i] = ['-e',f'SMAKO_MEMORY_TARGET_METHOD={METHOD}']
    args[args.index('--execution-environment')+1] = (
        f'Uninstrumented {SOURCE}; serial2CPU/3GiB incl swap; empty app/preparation cache and new synthetic owner; '
        'three same-process warm calls; OS disk cache uncontrolled, never cleared')
    assert args[args.index('python')+1] == IMAGE
    write(ROOT/f'candidate-{REVISION}-plain-command.json',args)
    started = time.perf_counter()
    print(json.dumps({'start':name}),flush=True)
    with (ROOT/f'candidate-{REVISION}-plain-worker.log').open('x') as log:
        result = subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,check=False)
    worker = json.loads(subprocess.check_output(['docker','inspect',name]))[0]
    h = worker['HostConfig']
    write(ROOT/f'candidate-{REVISION}-plain-process-receipt.json',{
        'source_commit':SOURCE,'archive_sha256':ARCHIVE_SHA,'state':worker['State'],'image':worker['Image'],
        'process_wall_seconds':time.perf_counter()-started,
        'resources':{k:h[k] for k in ('Memory','MemorySwap','NanoCpus','PidsLimit','NetworkMode','ReadonlyRootfs')},
        'user':worker['Config']['User'],'mounts':[{k:m[k] for k in ('Source','Destination','RW')} for m in worker['Mounts']]})
    assert result.returncode == 0 and not worker['State']['OOMKilled']
    report = json.loads((output/'L5000-verified-distribution.json').read_bytes())
    assert report['method_signature'] == METHOD and len(report['records']) == 4
    assert all(r['outcome']=='PASS' and r['audit_passed'] and r['paid']==988.32 and r['semantic_sha256']==EXPECTED
               and r['cgroup_peak_bytes']<=LIMIT for r in report['records'])
    final = json.loads((output/'final-resource.json').read_bytes())
    assert final['memory_target_passed'] and final['target_enforced_for_current_runtime']
    for script,extra in (
        ('run_cache_modes.py',['--source-commit',SOURCE]),
        ('run_pilot.py',[]),('run_http_history.py',[]),('run_matched.py',[]),('run_full_matrix.py',[]),
    ):
        print(json.dumps({'next_stage':script}),flush=True)
        subprocess.run(['python3','/tmp/'+script,*extra],check=True)


if __name__ == '__main__':
    main()
