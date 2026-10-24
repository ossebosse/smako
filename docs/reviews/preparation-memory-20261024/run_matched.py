"""Three plain cold baseline processes and one current diagnostic phase profile.

Current plain cold samples are the separately recorded primary/cold-2/cold-3.
Never compare profiler timings to plain timings as matched observations.
Baseline memory above the current 2.5 GiB target is recorded, not relabeled
as a successful current-code qualification. The hard 3 GiB limit is unchanged.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

ROOT = Path('/opt/smako/evidence/preparation-memory-20261024')
CURRENT = 'eeda184926f02e73ab76e71e50c740e9dcb01b02'
BASELINE = '9162f0fe5800a5c6ce52ac18cbbefa1a044ecc94'
OLD_CODE = Path('/opt/smako/evidence/sol-architecture-fixes-20261024-9162f0f/code')
EXPECTED = '1c0ad484edda7e36bf026b83a6e4f171dddf9c8d4a2b3d5359d95fa90bc227b7'
PROFILE_SHA = 'd0f8a45823d7e9d3cef8f50bf7f03d246f954cedec673a279a66efa67c93eaaf'


def write(path, data):
    path.write_text(json.dumps(data, indent=2)+'\n')


def execute(args, folder, name, source, method, instrumented):
    if '-d' in args:
        args.remove('-d')
    args[args.index('--name')+1] = name
    write(folder/'command.json',args)
    started = time.perf_counter()
    with (folder/'worker.log').open('x') as log:
        result = subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,check=False)
    state = json.loads(subprocess.check_output(['docker','inspect',name]))[0]
    h = state['HostConfig']
    receipt = {'source_commit':source,'state':state['State'],'image':state['Image'],
        'process_wall_seconds':time.perf_counter()-started,'instrumented':instrumented,
        'resources':{k:h[k] for k in ('Memory','MemorySwap','NanoCpus','NetworkMode','ReadonlyRootfs')},
        'user':state['Config']['User'],
        'mounts':[{k:m[k] for k in ('Source','Destination','RW')} for m in state['Mounts']]}
    write(folder/'receipt.json',receipt)
    assert result.returncode == 0 and not state['State']['OOMKilled']
    assert h['Memory'] == h['MemorySwap'] == 3221225472 and h['NanoCpus'] == 2000000000
    path = folder/'L5000-verified-distribution.json'
    report = json.loads(path.read_bytes())
    current = json.loads((ROOT/'candidate-eeda184-plain/L5000-verified-distribution.json').read_bytes())
    assert report['inputs'] == current['inputs'] and report['library_version'] == current['library_version']
    assert report['method_signature'] == method
    assert len(report['records']) == 1
    row = report['records'][0]
    assert row['outcome'] == 'PASS' and row['audit_passed'] and row['paid'] == 988.32
    assert row['semantic_sha256'] == EXPECTED
    final_path = folder/'final-resource.json'
    if instrumented:
        assert final_path.exists(), 'Current phase profile requires its post-serialization memory receipt'
        footer = json.loads(final_path.read_bytes())
        assert footer['measurement_complete'] and footer['phase_report_serialized']
        assert footer['method_signature'] == method and footer['target_enforced_for_current_runtime']
        assert footer['instrumentation_entry_sha256'] == PROFILE_SHA
        assert footer['memory']['swap_current'] == 0
        assert footer['phase_report_sha256'] == hashlib.sha256((folder/'phase-profile.json').read_bytes()).hexdigest()
    final_peak = (json.loads(final_path.read_bytes())['memory']['peak']
                  if final_path.exists() else row['cgroup_peak_bytes'])
    return {'source_commit':source,'instrumented':instrumented,'wall_seconds':row['wall_seconds'],
        'cgroup_peak_bytes':row['cgroup_peak_bytes'],'raw_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'final_cgroup_peak_bytes':final_peak,'memory_target_passed':final_peak <= 2684354560,
        'process_wall_seconds':receipt['process_wall_seconds']}


def main():
    assert not subprocess.check_output(['docker','ps','--filter','name=smako-preparation-','--format','{{.Names}}']).strip()
    template = json.loads((ROOT/'candidate-eeda184-plain-command.json').read_bytes())
    baseline_method = json.loads((ROOT/'baseline-profile-r2/L5000-verified-distribution.json').read_bytes())['method_signature']
    current_method = json.loads((ROOT/'candidate-eeda184-plain/L5000-verified-distribution.json').read_bytes())['method_signature']
    destination = ROOT/'matched-eeda184'
    destination.mkdir()
    summary = []
    for index in range(1,4):
        folder = destination/f'baseline-plain-{index}'
        folder.mkdir();os.chown(folder,10001,10001)
        args = [s.replace(str(ROOT/'code-eeda184'),str(OLD_CODE))
                 .replace(str(ROOT/'candidate-eeda184-plain')+':/output:rw',str(folder)+':/output:rw') for s in template]
        args[args.index('--repeat')+1] = '1'
        args[args.index('--execution-environment')+1] = (
            f'UNINSTRUMENTED baseline {BASELINE}; serial2CPU/3GiB incl swap; '
            'empty app/preparation cache and new synthetic owner; OS disk cache uncontrolled')
        print(json.dumps({'start':folder.name}),flush=True)
        summary.append(execute(args,folder,f'smako-preparation-9162f0f-matched-{index}',
                               BASELINE,baseline_method,False))
        write(destination/'summary.json',summary)
    folder = destination/'current-instrumented'
    folder.mkdir();os.chown(folder,10001,10001)
    assert hashlib.sha256(Path('/tmp/smako-profile-preparation-20261024.py').read_bytes()).hexdigest() == PROFILE_SHA
    args = [s.replace(str(ROOT/'candidate-eeda184-plain')+':/output:rw',str(folder)+':/output:rw')
             .replace('/tmp/plain_preparation_entry.py:/preparation_probe.py:ro',
                      '/tmp/profile_memory_entry.py:/preparation_probe.py:ro') for s in template]
    i = args.index('--entrypoint');args[i:i] = ['-e','SMAKO_PROFILE_REPORT=/output/phase-profile.json',
        '-v','/tmp/smako-profile-preparation-20261024.py:/profile_instrumentation.py:ro']
    args[args.index('--repeat')+1] = '1'
    args[args.index('--execution-environment')+1] = (
        f'INSTRUMENTED {CURRENT}; serial2CPU/3GiB incl swap; empty app/preparation cache and new owner; '
        'one diagnostic phase profile; not interchangeable with plain timing samples')
    summary.append(execute(args,folder,'smako-preparation-eeda184-profile',CURRENT,current_method,True))
    write(destination/'summary.json',summary)
    assert summary[-1]['memory_target_passed']
    write(destination/'complete.json',{'status':'MATCHED_PLAIN_SAMPLES_COLLECTED_SEPARATE_PHASE_PROFILE',
        'baseline_plain_samples':3,'current_plain_folders':['candidate-eeda184-plain',
            'cache-modes-eeda184/cold-2','cache-modes-eeda184/cold-3'],
        'current_phase_profile_samples':1,'os_cache':'uncontrolled; never cleared'})


if __name__ == '__main__':
    main()
