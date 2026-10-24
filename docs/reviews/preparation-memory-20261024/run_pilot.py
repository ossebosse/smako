"""Serial frozen pilot after repeated cache and temporary-memory gates.

No production output is mounted. Axfood input generation preserves frozen
prices/request/clock and verifies the existing immutable partial release.
This pilot does not qualify the full acceptance matrix or change defaults.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from decimal import Decimal
from pathlib import Path

ROOT = Path('/opt/smako/evidence/preparation-memory-20261024')
SOURCE = 'eeda184926f02e73ab76e71e50c740e9dcb01b02'
REVISION = SOURCE[:7]
RELEASE = '16410fb3d4e21746a75cb6c34072bb4bcc159c20ceefec2ba1187bb883ac233a'
IMAGE = 'sha256:dc23ba03be3ca2370d28d6230d392160a63fb278a56f5b0171ebe91947713072'
LIMIT = 2684354560
PROFILES = ('standard', 'distribution', 'organic-share')
ORIGINAL = Path('/opt/smako/evidence/integration-scaling-20261023/output/data')
LIBRARIES = Path('/opt/smako/evidence/integration-scaling-20261023/final-grid-libraries')


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def gates():
    summary = json.loads((ROOT/f'cache-modes-{REVISION}/summary.json').read_bytes())
    if len(summary) != 13:
        raise RuntimeError('Thirteen cache-mode trials are required before pilot broadening')
    for receipt in summary:
        assert receipt['state']['ExitCode'] == 0 and not receipt['state']['OOMKilled']
        report = json.loads(next((ROOT/f'cache-modes-{REVISION}'/receipt['mode']).glob('L*-distribution.json')).read_bytes())
        assert all(r['outcome'] == 'PASS' and r['audit_passed'] and r['cgroup_peak_bytes'] <= LIMIT
                   for r in report['records'])
        final = json.loads((ROOT/f'cache-modes-{REVISION}'/receipt['mode']/'final-resource.json').read_bytes())
        assert final['memory_target_passed'] and final['target_enforced_for_current_runtime']
    temporary = json.loads((ROOT/f'temporary-memory-{REVISION}-summary.json').read_bytes())
    assert len(temporary) == 3
    for trial in temporary:
        assert trial['receipt']['source_commit'] == SOURCE
        assert trial['receipt']['state']['ExitCode'] == 0 and not trial['receipt']['state']['OOMKilled']
        assert trial['report']['memory_target_passed'] and trial['report']['stages'][-1]['stage'] == 'complete'
        assert trial['final_resource']['memory_target_passed']
    assert not subprocess.check_output(['docker','ps','--filter','name=smako-preparation-','--format','{{.Names}}']).strip()


def worker(args, name, folder):
    args = list(args)
    if '-d' in args:
        args.remove('-d')
    args[args.index('--name')+1] = name
    write(folder/'command.json', args)
    started = time.perf_counter()
    with (folder/'worker.log').open('x') as log:
        outcome = subprocess.run(args, stdout=log, stderr=subprocess.STDOUT, check=False)
    state = json.loads(subprocess.check_output(['docker','inspect',name]))[0]
    h = state['HostConfig']
    receipt = {'source_commit': SOURCE, 'state': state['State'], 'image': state['Image'],
               'process_wall_seconds': time.perf_counter()-started,
               'resources': {k:h[k] for k in ('Memory','MemorySwap','NanoCpus','PidsLimit','NetworkMode','ReadonlyRootfs')},
               'user': state['Config']['User'],
               'mounts': [{k:m[k] for k in ('Source','Destination','RW')} for m in state['Mounts']]}
    write(folder/'receipt.json', receipt)
    assert outcome.returncode == 0 and not state['State']['OOMKilled'], name
    assert h['Memory'] == h['MemorySwap'] == 3221225472 and h['NanoCpus'] == 2000000000
    assert h['NetworkMode'] == 'none' and h['ReadonlyRootfs'] is True and state['Config']['User'] == '10001:10001'
    final = folder/'final-resource.json'
    if final.exists():
        assert json.loads(final.read_bytes())['memory_target_passed'], name
    return receipt


def prepare_facts(base):
    output = ROOT/f'axfood-facts-{REVISION}'
    output.mkdir(); os.chown(output,10001,10001)
    proofs = []
    release_path = Path('/srv/smako/data/axfood-product-details/releases')/RELEASE
    release_manifest = json.loads((release_path/'manifest.json').read_bytes())
    for city in ('malmo','lund'):
        evidence = output/f'{city}-evidence'
        evidence.mkdir(); os.chown(evidence,10001,10001)
        args = [s.replace(str(ROOT/f'candidate-{REVISION}-plain')+':/output:rw',str(output)+':/output:rw') for s in base]
        i = args.index('--entrypoint')
        args[i:i] = ['-v',f'{release_path}:/details/{RELEASE}:ro',
                     '-v','/tmp/facts_projection_entry.py:/facts_projection_entry.py:ro']
        args = args[:args.index(IMAGE)+1]+['-u','/facts_projection_entry.py',
            '--memory-report',f'/output/{city}-evidence/memory.json',
            '--inputs',f'/inputs/{city}','--details',f'/details/{RELEASE}','--output',f'/output/{city}']
        worker(args,f'smako-preparation-{REVISION}-augment-{city}',evidence)
        memory = json.loads((evidence/'memory.json').read_bytes())
        assert memory['memory_target_passed']
        manifest = json.loads((output/city/'matrix-inputs.json').read_bytes())
        old = json.loads((ORIGINAL/city/'matrix-inputs.json').read_bytes())
        assert manifest['now'] == old['now']
        assert all(manifest['sha256'][key] == old['sha256'][key]
                   for key in ('combined-prices.json','combined-request.json'))
        proofs.append({'city':city,'manifest_sha256':sha(output/city/'matrix-inputs.json'),
                       'original_manifest_sha256':sha(ORIGINAL/city/'matrix-inputs.json'),
                       'release_id':RELEASE,'release_manifest_sha256':sha(release_path/'manifest.json'),
                       'release_coverage':release_manifest['coverage'],
                       'manifest':manifest})
    write(output/'projection-proof.json',{'source_commit':SOURCE,'partial_release':True,
        'proofs':proofs})
    return output


def report(folder, size, arm, profile):
    return json.loads((folder/f'L{size}-{arm}-{profile}.json').read_bytes())


def validate(folder, size):
    method = json.loads((ROOT/f'candidate-{REVISION}-plain/L5000-verified-distribution.json').read_bytes())['method_signature']
    for profile in PROFILES:
        old, new = (report(folder,size,arm,profile) for arm in ('main','verified'))
        for data in (old,new):
            assert data['method_signature'] == method
            assert len(data['records']) == 4
            assert all(r['outcome'] == 'PASS' and r['audit_passed'] and r['cgroup_peak_bytes'] <= LIMIT
                       for r in data['records']), (folder,profile)
            assert len({r['paid'] for r in data['records']}) == 1
        assert max(Decimal(str(r['paid'])) for r in new['records']) <= min(Decimal(str(r['paid'])) for r in old['records'])


def validate_warm_ratios(folder):
    ratios = []
    for profile in PROFILES:
        large = report(folder,5000,'verified',profile)['records']
        small = report(folder.parent/'262',262,'verified',profile)['records']
        legacy = report(folder,5000,'main',profile)['records']
        ratio = max(r['wall_seconds'] for r in large[1:])/min(r['wall_seconds'] for r in small[1:])
        assert ratio <= 1.25, (folder,profile,ratio)
        assert max(r['wall_seconds'] for r in large[1:]) <= min(r['wall_seconds'] for r in legacy[1:])
        assert max(r['paid'] for r in large) <= min(r['paid'] for r in small)
        ratios.append({'profile':profile,'max_5000_over_min_262':ratio,'passed':True})
    return ratios


def make_empty_group(folder):
    if folder.exists():
        assert not any(folder.iterdir()), f'Preserve incomplete evidence before resuming: {folder}'
    else:
        folder.mkdir(parents=True)


def validate_closed_resources(folder, method):
    receipt = json.loads((folder/'receipt.json').read_bytes())
    assert receipt['source_commit'] == SOURCE and receipt['image'] == IMAGE
    assert receipt['state']['ExitCode'] == 0 and not receipt['state']['OOMKilled']
    assert receipt['resources']['Memory'] == receipt['resources']['MemorySwap'] == 3221225472
    assert receipt['resources']['NanoCpus'] == 2000000000
    assert receipt['resources']['NetworkMode'] == 'none' and receipt['resources']['ReadonlyRootfs'] is True
    assert receipt['user'] == '10001:10001'
    final = json.loads((folder/'final-resource.json').read_bytes())
    assert final['method_signature'] == method and final['target_enforced_for_current_runtime']
    assert final['memory_target_passed'] and final['memory']['peak'] <= LIMIT
    assert final['memory']['swap_current'] == 0


def resume_inputs():
    completed = json.loads((ROOT/f'runtime-only-memory-{REVISION}/complete.json').read_bytes())
    assert completed['source_commit'] == SOURCE and completed['samples'] == 3
    assert completed['status'] == 'RUNTIME_CLEANUP_ONLY_MEMORY_PASSED'
    enriched = ROOT/f'axfood-facts-{REVISION}'
    proof = json.loads((enriched/'projection-proof.json').read_bytes())
    assert proof['source_commit'] == SOURCE and proof['partial_release'] is True
    assert [r['city'] for r in proof['proofs']] == ['malmo','lund']
    for row in proof['proofs']:
        city = row['city']
        assert row['release_id'] == RELEASE
        assert row['release_manifest_sha256'] == sha(Path('/srv/smako/data/axfood-product-details/releases')/RELEASE/'manifest.json')
        assert row['manifest_sha256'] == sha(enriched/city/'matrix-inputs.json')
        assert row['original_manifest_sha256'] == sha(ORIGINAL/city/'matrix-inputs.json')
        for inputs in (ORIGINAL,enriched):
            manifest = json.loads((inputs/city/'matrix-inputs.json').read_bytes())
            assert all(sha(inputs/city/name) == digest for name,digest in manifest['sha256'].items())
        old = json.loads((ORIGINAL/city/'matrix-inputs.json').read_bytes())
        assert row['manifest']['now'] == old['now']
        assert all(row['manifest']['sha256'][name] == old['sha256'][name]
                   for name in ('combined-prices.json','combined-request.json'))
    return enriched


def resume_summary(destination):
    summary = json.loads((destination/'summary.json').read_bytes())
    expected = [(facts,city,size) for facts in ('original','axfood_103')
                for city in ('malmo','lund') for size in (262,5000)]
    observed = [(r['facts_arm'],r['city'],r['size']) for r in summary]
    assert observed == expected[:len(observed)], 'Completed groups must be an exact ordered prefix'
    method = json.loads((ROOT/f'candidate-{REVISION}-plain/L5000-verified-distribution.json').read_bytes())['method_signature']
    for row in summary:
        assert row['source_commit'] == SOURCE
        inputs = ORIGINAL if row['facts_arm'] == 'original' else ROOT/f'axfood-facts-{REVISION}'
        assert row['input_manifest_sha256'] == sha(inputs/row['city']/'matrix-inputs.json')
        assert row['library_manifest_sha256'] == sha(LIBRARIES/str(row['size'])/'library-manifest.json')
        folder = destination/row['facts_arm']/row['city']/str(row['size'])
        validate_closed_resources(folder,method)
        validate(folder,row['size'])
        if row['size'] == 5000:
            assert json.loads((folder.parent/'warm-ratios.json').read_bytes()) == validate_warm_ratios(folder)
    return summary


def main(*, resume=False):
    gates()
    base = json.loads((ROOT/f'candidate-{REVISION}-plain-command.json').read_bytes())
    if resume:
        enriched = resume_inputs()
    else:
        subprocess.run(['python3','/tmp/run_runtime_only_memory.py'],check=True)
        enriched = prepare_facts(base)
    destination = ROOT/f'pilot-{REVISION}'
    if not resume:
        destination.mkdir()
    summary = resume_summary(destination) if resume else []
    finished = {(r['facts_arm'],r['city'],r['size']) for r in summary}
    for facts, inputs in (('original',ORIGINAL),('axfood_103',enriched)):
        for city in ('malmo','lund'):
            for size in (262,5000):
                if (facts,city,size) in finished:
                    continue
                folder = destination/facts/city/str(size)
                make_empty_group(folder); os.chown(folder,10001,10001)
                args = [s.replace(str(ROOT/f'candidate-{REVISION}-plain')+':/output:rw',str(folder)+':/output:rw')
                        .replace(str(ORIGINAL)+':/inputs:ro',str(inputs)+':/inputs:ro')
                        .replace(str(LIBRARIES/'5000')+':',str(LIBRARIES/str(size))+':') for s in base]
                args[args.index('--inputs')+1] = f'/inputs/{city}'
                args[args.index('--size')+1] = str(size)
                i = args.index('--cases'); args[i+1:i+2] = PROFILES
                i = args.index('--arms'); args[i+1:i+2] = ['main','verified']
                if facts == 'axfood_103':
                    prior = destination/'original'/city/str(size)
                    i = args.index('--entrypoint'); args[i:i] = ['-v',f'{prior}:/previous:ro']
                    args += ['--previous-menus-root','/previous']
                args[args.index('--execution-environment')+1] = (
                    f'Uninstrumented {SOURCE}; serial2CPU/3GiB incl swap; {facts}/{city}/{size}; '
                    'shared public preparation within process; fresh synthetic store; first+3warm per profile/policy; OS cache uncontrolled')
                print(json.dumps({'start':str(folder)}),flush=True)
                worker(args,f'smako-preparation-{REVISION}-pilot-{facts}-{city}-{size}',folder)
                validate(folder,size)
                summary.append({'facts_arm':facts,'city':city,'size':size,'status':'MEASURED_PILOT_ONLY',
                    'source_commit':SOURCE,'input_manifest_sha256':sha(inputs/city/'matrix-inputs.json'),
                    'library_manifest_sha256':sha(LIBRARIES/str(size)/'library-manifest.json')})
                write(destination/'summary.json',summary)
                if size == 5000:
                    write(folder.parent/'warm-ratios.json',validate_warm_ratios(folder))
    write(destination/'complete.json',{'source_commit':SOURCE,'status':'PILOT_PASSED_NOT_FULL_MATRIX',
        'groups':len(summary),'profile_policy_cells':48,'full_matrix_qualified':False})


if __name__ == '__main__':
    main()
