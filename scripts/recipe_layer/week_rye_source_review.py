"""Review retained source-bound rye bread without a whole-library inventory."""
import argparse
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from app.models import Product
from app.services.complete_recipes import product_form_compatible
from app.services.personal_policy import ProductFacts


def main(a):
    recipe=SimpleNamespace(design=True,preparation=SimpleNamespace(input_forms={'bröd':'as_sold'}),ingredients=[SimpleNamespace(name='bröd',product_requirements=['pack:rye_bread'])])
    if a.reuse:
        data=a.reuse.read_bytes()
        result=json.loads(data)
        result['reused_source_review_sha256']=hashlib.sha256(data).hexdigest()
        result['scope']='Recheck the 12 previously reviewed source-bound rye rows; no second catalog scan.'
        for row in result['rows']:
            row['form_and_rye_requirement_passed']=product_form_compatible(recipe,'bröd',Product(**row['product']),ProductFacts(**row['fact']))
    else:
        u=json.loads(a.universe.read_bytes())
        products=[r for r in u['universe']['products'] if r['name'].casefold()=='rågbröd']
        del u
        facts=json.loads(a.facts.read_bytes())
        rows=[]
        for raw in products:
            product=Product(**raw)
            snapshot=raw.get('source_provenance',{}).get('source_snapshot_id')
            found=[(key,f) for key,f in facts['facts'] if f.get('source_product_id')==raw['product_id'] and f.get('source_snapshot_id')==snapshot and raw['store_id'] in key]
            for key,source in found:
                rows.append({'product':raw,'fact_key':key,'fact':source,'form_and_rye_requirement_passed':product_form_compatible(recipe,'bröd',product,ProductFacts(**source))})
        result={'universe_sha256':hashlib.sha256(a.universe.read_bytes()).hexdigest(),'facts_sha256':hashlib.sha256(a.facts.read_bytes()).hexdigest(),'named_rye_products':len(products),'rows':rows}
    result['composition_completeness']='Missing formulas remain unknown; marketed rye-bread identity supplies no allergen/nutrient or rye-percentage certificate.'
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print({'source_bound_facts':len(result['rows']),'qualified':sum(r['form_and_rye_requirement_passed'] for r in result['rows'])})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--universe',type=Path)
    p.add_argument('--facts',type=Path)
    p.add_argument('--reuse',type=Path)
    p.add_argument('--output',type=Path,required=True)
    main(p.parse_args())
