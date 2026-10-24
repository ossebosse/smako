"""Complete the explicit 252-cell inventory after the frozen 48-cell pilot.

One foreground worker at a time, unchanged two CPUs/3 GiB, four calls per
cell (first plus three comparable warm calls). Every finished group is
inventoried before the next starts. Missing/blocked/failed evidence never
becomes a delivered and audited menu. Defaults and production are untouched.
"""
from __future__ import annotations

import itertools
import json
import os
from decimal import Decimal

from run_pilot import (
    LIBRARIES,
    LIMIT,
    ORIGINAL,
    PROFILES,
    REVISION,
    ROOT,
    SOURCE,
    sha,
    worker,
    write,
)

ALL_PROFILES = ('standard','protein40','all-macros','vegan','distribution',
                'organic-share','breakfast-snack-weight')
POLICIES = {'main':'legacy','verified':'smako-verified-reference-v1',
            'uncapped':'smako-full-library-reference-v5'}
REFERENCE_LIMITS = {'seed':0,'refinement':0,'seed_variant_shortlist':False,'substitution':0,
                    'merge_generations':False,'substitution_screen_margin':-1.0,'substitution_slot_limit':0}


def blocked_signature(cell):
    return {(row['code'],row['stage']) for row in cell['blocked_evidence']}


def collect(destination):
    current_method = json.loads((ROOT/f'candidate-{REVISION}-plain/L5000-verified-distribution.json').read_bytes())['method_signature']
    cells = {key:{'facts_arm':key[0],'city':key[1],'profile':key[2],'library_size':key[3],
                  'search_policy':key[4],'status':'NOT_RUN_ON_CURRENT_CODE','evidence':[]}
        for facts,city,profile in itertools.product(('original','axfood_103'),('malmo','lund'),ALL_PROFILES)
        for size,policy in [*itertools.product((262,1000,2000,5000),('legacy','smako-verified-reference-v1')),
                            (262,'smako-full-library-reference-v5')]
        for key in [(facts,city,profile,size,policy)]}
    reports = {}
    for root in (ROOT/f'pilot-{REVISION}',destination):
        for facts,city,size in itertools.product(('original','axfood_103'),('malmo','lund'),(262,1000,2000,5000)):
            parent = root/facts/city/str(size)
            for path in parent.glob('**/L*-*.json'):
                data = json.loads(path.read_bytes())
                if data.get('schema') != 'smako-planner-acceptance-v1':
                    continue
                assert data['method_signature'] == current_method, ('Wrong source method',path)
                arm = data['label'].split('-',1)[1]
                key = facts,city,data['case'],size,POLICIES[arm]
                assert key not in reports, ('Duplicate cell evidence',key)
                reports[key] = (path,data)
                cell = cells[key]
                inputs = ORIGINAL if facts == 'original' else ROOT/f'axfood-facts-{REVISION}'
                manifest = json.loads((inputs/city/'matrix-inputs.json').read_bytes())
                assert data['inputs']['sha256'] == manifest['sha256'], ('Wrong frozen inputs',path)
                cell.update(source_commit=SOURCE,method_signature=data['method_signature'],
                    library_version=data['library_version'],inputs=data['inputs'],
                    input_manifest_sha256=sha(inputs/city/'matrix-inputs.json'),
                    library_manifest_sha256=sha(LIBRARIES/str(size)/'library-manifest.json'),
                    evidence=[{'path':str(path),'raw_sha256':sha(path),'records':len(data['records'])}])
                rows = data['records']
                final = path.parent/'final-resource.json'
                if final.exists():
                    cell['shared_process_final_resource'] = json.loads(final.read_bytes())
                if len(rows) != 4:
                    cell['status'] = 'INCOMPLETE_RECORDS'
                    continue
                if (any(r.get('cgroup_peak_bytes',LIMIT+1) > LIMIT for r in rows)
                        or (final.exists() and not cell['shared_process_final_resource']['memory_target_passed'])):
                    cell['status'] = 'FAILED_MEMORY_GATE'
                    continue
                if all(r['outcome'] == 'BLOCKED' for r in rows):
                    cell.update(status='OBSERVED_BLOCKED_NOT_GLOBAL_IMPOSSIBILITY',
                                blocked_evidence=[{k:r.get(k) for k in ('code','stage','reason')} for r in rows])
                    continue
                if not all(r['outcome'] == 'PASS' and r.get('audit_passed') for r in rows):
                    cell['status'] = 'FAILED_OUTCOME_OR_AUDIT'
                    continue
                if arm == 'uncapped':
                    assert data.get('reference_contract') == POLICIES[arm] and data.get('uncapped') is True
                    assert all(type(data['search_limits'].get(k)) is type(v) and data['search_limits'][k] == v
                               for k,v in REFERENCE_LIMITS.items())
                cell.update(status='AUDITED_PENDING_CROSS_CELL_GATES',
                    paid=[r['paid'] for r in rows],
                    semantic_sha256=[r['semantic_sha256'] for r in rows],
                    wall_seconds=[r['wall_seconds'] for r in rows],
                    warm_seconds=[r['wall_seconds'] for r in rows[1:]],
                    cgroup_peak_bytes=max(r['cgroup_peak_bytes'] for r in rows))
    failures = []
    for key,cell in cells.items():
        facts,city,profile,size,policy = key
        if policy == 'smako-verified-reference-v1' and cell['status'] == 'OBSERVED_BLOCKED_NOT_GLOBAL_IMPOSSIBILITY':
            required = [(facts,city,profile,size,'legacy'),(facts,city,profile,262,'legacy')]
            if size != 262:
                required.append((facts,city,profile,{1000:262,2000:1000,5000:2000}[size],policy))
            for target in dict.fromkeys(required):
                prior = cells[target]
                if prior['status'] == 'AUDITED_PENDING_CROSS_CELL_GATES':
                    failures.append({'cell':key,'gate':'OUTCOME_REGRESSION','against':target})
                elif (prior['status'] == 'OBSERVED_BLOCKED_NOT_GLOBAL_IMPOSSIBILITY'
                      and blocked_signature(cell) != blocked_signature(prior)):
                    failures.append({'cell':key,'gate':'UNEXPLAINED_BLOCKED_OUTCOME_CHANGE','against':target})
        if cell['status'] != 'AUDITED_PENDING_CROSS_CELL_GATES':
            if cell['status'].startswith('FAILED_'):
                failures.append({'cell':key,'gate':cell['status']})
            continue
        if len(set(cell['paid'])) != 1:
            failures.append({'cell':key,'gate':'INCONSISTENT_REPEATED_PRICE'})
        if policy != 'smako-verified-reference-v1':
            continue
        required = [(facts,city,profile,size,'legacy'),(facts,city,profile,262,'legacy')]
        if size != 262:
            previous = {1000:262,2000:1000,5000:2000}[size]
            required.append((facts,city,profile,previous,policy))
        if any(cells[k]['status'] != 'AUDITED_PENDING_CROSS_CELL_GATES' for k in required):
            continue
        for target in required:
            if max(Decimal(str(v)) for v in cell['paid']) > min(Decimal(str(v)) for v in cells[target]['paid']):
                failures.append({'cell':key,'gate':'PRICE_REGRESSION','against':target})
        if size == 5000:
            small = cells[facts,city,profile,262,policy]
            legacy = cells[facts,city,profile,5000,'legacy']
            if small['status'] == legacy['status'] == 'AUDITED_PENDING_CROSS_CELL_GATES':
                ratio = max(cell['warm_seconds'])/min(small['warm_seconds'])
                cell['warm_max_5000_over_min_262'] = ratio
                if ratio > 1.25:
                    failures.append({'cell':key,'gate':'WARM_SCALING','ratio':ratio})
                if max(cell['warm_seconds']) > min(legacy['warm_seconds']):
                    failures.append({'cell':key,'gate':'WARM_SLOWER_THAN_LEGACY'})
    assert len(cells) == 252
    measured = sum(bool(c['evidence']) for c in cells.values())
    result = {'schema':'smako-current-full-matrix-v1','source_commit':SOURCE,'cells':list(cells.values()),
        'all_dimensions_enumerated':True,'measured_cells':measured,'required_cells':252,
        'audited_menu_cells':sum(c['status']=='AUDITED_PENDING_CROSS_CELL_GATES' for c in cells.values()),
        'observed_blocked_cells':sum(c['status']=='OBSERVED_BLOCKED_NOT_GLOBAL_IMPOSSIBILITY' for c in cells.values()),
        'failures':failures,'full_matrix_qualified':False,
        'status':'FAILED_GATE' if failures else 'IN_PROGRESS',
        'limitations':['Blocked outcomes are observed evidence, never a global impossibility proof',
                       'Baseline-code, cache-mode, temporary-memory and HTTP queue evidence are separate',
                       'Current defaults remain legacy; production is unchanged']}
    write(destination/'cells.json',result)
    if failures:
        raise RuntimeError(f'Full matrix stopped at concrete gate: {failures[0]}')
    return result


def main():
    pilot = ROOT/f'pilot-{REVISION}'
    complete = json.loads((pilot/'complete.json').read_bytes())
    assert complete['status'] == 'PILOT_PASSED_NOT_FULL_MATRIX' and complete['source_commit'] == SOURCE
    destination = ROOT/f'full-matrix-{REVISION}'
    destination.mkdir()
    collect(destination)
    base = json.loads((ROOT/f'candidate-{REVISION}-plain-command.json').read_bytes())
    extra_profiles = tuple(p for p in ALL_PROFILES if p not in PROFILES)
    groups = [(262,extra_profiles,('main','verified'),'remaining'),
              (262,ALL_PROFILES,('uncapped',),'reference'),
              (1000,ALL_PROFILES,('main','verified'),'all'),
              (2000,ALL_PROFILES,('main','verified'),'all'),
              (5000,extra_profiles,('main','verified'),'remaining')]
    for facts,city in itertools.product(('original','axfood_103'),('malmo','lund')):
        inputs = ORIGINAL if facts == 'original' else ROOT/f'axfood-facts-{REVISION}'
        for size,profiles,arms,part in groups:
            folder = destination/facts/city/str(size)/part
            folder.mkdir(parents=True);os.chown(folder,10001,10001)
            args = [s.replace(str(ROOT/f'candidate-{REVISION}-plain')+':/output:rw',str(folder)+':/output:rw')
                    .replace(str(ORIGINAL)+':/inputs:ro',str(inputs)+':/inputs:ro')
                    .replace(str(LIBRARIES/'5000')+':',str(LIBRARIES/str(size))+':') for s in base]
            args[args.index('--inputs')+1] = f'/inputs/{city}'
            args[args.index('--size')+1] = str(size)
            i = args.index('--cases');args[i+1:i+2] = profiles
            i = args.index('--arms');args[i+1:i+2] = arms
            if facts == 'axfood_103':
                prior = destination/'original'/city/str(size)/part
                i = args.index('--entrypoint');args[i:i] = ['-v',f'{prior}:/previous:ro']
                args += ['--previous-menus-root','/previous']
            args[args.index('--execution-environment')+1] = (
                f'Uninstrumented {SOURCE}; serial2CPU/3GiB incl swap; {facts}/{city}/{size}/{part}; '
                'first+3warm per profile/policy; own synthetic store; shared public preparation within process; OS cache uncontrolled')
            print(json.dumps({'start':str(folder)}),flush=True)
            worker(args,f'smako-preparation-{REVISION}-grid-{facts}-{city}-{size}-{part}',folder)
            collect(destination)
    result = collect(destination)
    assert result['measured_cells'] == 252 and not result['failures']
    assert result['audited_menu_cells'] + result['observed_blocked_cells'] == 252
    # Completion of sampling stays distinct from qualification: blocked outcome
    # equivalence and all separate release gates still require explicit review.
    result['status'] = 'ALL_252_MEASURED_REVIEW_REQUIRED'
    write(destination/'cells.json',result)
    write(destination/'complete.json',{'source_commit':SOURCE,'status':result['status'],
        'measured_cells':252,'full_matrix_qualified':False})


if __name__ == '__main__':
    main()
