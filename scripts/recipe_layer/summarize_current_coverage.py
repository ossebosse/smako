"""Compact complete before/after input inventories without changing definition."""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


def read(path):return json.loads(path.read_bytes())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main(args):
    before,after=read(args.before),read(args.after)
    for key in ['universe_sha256','facts_sha256','clock','manifest_sha256','recipe_ids','imported_reference_ids']:
        assert before[key]==after[key],key
    historical=read(Path('docs/reviews/recipe-quality-and-planning-20261026/purchase-coverage.json'))
    changes=read(Path('docs/reviews/week-search-and-cache-20261026/recipe-review.json'))['corrected']
    successors={r['previous_id']:r['runtime_id'] for r in changes}
    positions={rid:i for i,rid in enumerate(after['recipe_ids'])}
    def index(rid):return positions[successors.get(rid,rid)]
    result={k:after[k] for k in ['scope','universe_sha256','facts_sha256','clock','manifest_sha256','recipe_ids','imported_reference_ids','current_variants','imported_variants','other_original_variants_not_inventoried']}
    result.update(before_raw_sha256=sha(args.before),after_raw_sha256=sha(args.after),
        before_raw_local_copy=args.before.as_posix(),after_raw_local_copy=args.after.as_posix(),
        before_method=before['method_signature'],after_method=after['method_signature'],products=[],modes={})
    product_positions={}
    def value(row):
        out={k:v for k,v in row.items() if k not in ['identity','unit','quantity','requirements','recipe_indices','examples']}
        if 'examples' in row:
            out['product_indices']=[]
            for p in row['examples']:
                key=json.dumps(p,sort_keys=True,ensure_ascii=False)
                if key not in product_positions:
                    product_positions[key]=len(result['products']);result['products'].append(p)
                out['product_indices'].append(product_positions[key])
        return out
    def scope(row):return (row['identity'],row['unit'],row['quantity'],tuple(row['requirements']))
    for mode in ['exact','estimated']:
        a,b=before['modes'][mode],after['modes'][mode]
        assert a['conditions']==b['conditions']
        prior={scope(r):r for r in a['shared_inputs']}
        assert set(prior)=={scope(r) for r in b['shared_inputs']}
        inputs=[];changed=[]
        missing=[set() for _ in after['recipe_ids']]
        for row in b['shared_inputs']:
            old=prior[scope(row)]
            assert old['recipe_indices']==row['recipe_indices']
            out={k:row[k] for k in ['identity','unit','quantity','requirements','recipe_indices']}
            old_value,new_value=value(old),value(row)
            if old_value==new_value:out.update(before_equals_after=True,**new_value)
            else:
                out.update(before=old_value,after=new_value);changed.append(row['identity'])
            inputs.append(out)
            if row['status']=='blocked':
                for i in row['recipe_indices']:missing[i].add(row['identity'])
        old_set,new_set=set(a['resolved_indices']),set(b['resolved_indices'])
        assert new_set=={i for i,missing_inputs in enumerate(missing) if not missing_inputs}
        hist=historical['modes'][mode]
        hist_set={index(hist['recipe_ids'][i]) for i in hist['resolved_indices']}
        rye=[positions[r['runtime_id']] for r in changes if 'creamed-cabbage-chickpeas' in r['runtime_id']]
        result['modes'][mode]={'conditions':b['conditions'],'historical_resolved':len(hist_set),
            'current_before_resolved':len(old_set),'current_after_resolved':len(new_set),
            'before_resolved_indices':sorted(old_set),'resolved_indices':sorted(new_set),
            'newly_resolved_indices':sorted(new_set-old_set),'lost_indices':sorted(old_set-new_set),
            'historical_to_before_gained_indices':sorted(old_set-hist_set),'historical_to_before_lost_indices':sorted(hist_set-old_set),
            'rye_variants':[{'recipe_index':i,'historical_resolved':i in hist_set,'current_before_resolved':i in old_set,'current_after_resolved':i in new_set} for i in rye],
            'changed_input_identities':dict(Counter(changed)),'shared_inputs':inputs,
            'blocked_variants_by_identity':b['blocked_variants_by_identity'],
            'single_missing_group_release_upper_bound':dict(Counter(next(iter(s)) for s in missing if len(s)==1))}
    assert set(result['modes']['exact']['resolved_indices'])<=set(result['modes']['estimated']['resolved_indices'])
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'purchase-coverage.json').write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    research=read(args.research)
    assert research['universe_sha256']==after['universe_sha256'] and research['facts_sha256']==after['facts_sha256']
    review={'raw_research_sha256':sha(args.research),'raw_research_local_copy':args.research.as_posix(),
        'scope':'Retained exact rows; no collection, invented ingredient formula, edible yield or price attachment', 'groups':{}}
    for name,rows in research['groups'].items():
        unique=set();coconut=[]
        for row in rows:
            p=row['product']
            unique.add((p['name'],p.get('package_quantity'),p.get('package_unit')))
            if name=='kokosflingor':
                coconut.append({k:p.get(k) for k in ['product_id','store_id','name','brand','category','package_quantity','package_unit','usable_quantity','usable_unit','quantity_confidence','source_provenance']})
        review['groups'][name]={'retained_rows':len(rows),'unique_name_packages':len(unique),
            'rows_with_nonempty_exact_ingredient_declaration':sum(bool(r['exact_facts'] and r['facts'].get('ingredients')) for r in rows),
            'status':('existing dry whole-coconut definition; retrieval/semantic alias corrected; exact declared g package retained'
                      if name=='kokosflingor' else 'unchanged; no new composition/edible-mass declaration established')}
        if coconut:review['groups'][name]['source_rows']=coconut
    (args.output/'source-review.json').write_text(json.dumps(review,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print({m:{k:v for k,v in r.items() if k in ['historical_resolved','current_before_resolved','current_after_resolved','changed_input_identities','rye_variants']} for m,r in result['modes'].items()})
    print({'compact_bytes':(args.output/'purchase-coverage.json').stat().st_size})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for field in ['before','after','research','output']:p.add_argument('--'+field,type=Path,required=True)
    main(p.parse_args())
