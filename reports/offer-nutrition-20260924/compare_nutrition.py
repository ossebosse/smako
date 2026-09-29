"""Same retained products/contexts with baseline and final nutrition/matcher rules."""
from pathlib import Path
import importlib.util
import json
import sys
from collections import Counter
from types import SimpleNamespace
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
from app.services.product_matcher import ProductMatcher
from app.services.personal_planner import PersonalPlanner
from app.services.ingredient_normalizer import canonicalize_ingredient_name
from app.services.lidl_product_facts import reviewed_facts
from app.models.ingredient import NormalizedIngredient
import app.services.nutrition_reference as current

R=Path(__file__).resolve().parent
O=R.parent/'offer-coverage-20260924'

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m)
    return m

def load(p):
    return PreparedPriceUniverseArtifact.model_validate_json(p.read_bytes()).restore().universe.products

old=module('nutrition_baseline',R/'baseline-code/backend/app/services/nutrition_reference.py')
old.PATH=current.PATH;old.ASSEMBLY_PATH=current.ASSEMBLY_PATH
matcher=module('matcher_baseline',R/'baseline-code/backend/app/services/product_matcher.py').ProductMatcher
before=[p for p in load(O/'prepared-1280-second.json') if p.chain=='willys' and p.source_provenance.provider_store_id in ['2352','2843']]+[p for p in load(O/'lidl-current-1281/prepared.json') if p.source_provenance.provider_store_id=='0163']
after=[p for p in load(R/'prepared-1280-second.json') if p.chain=='willys' and p.source_provenance.provider_store_id in ['2352','2843']]+[p for p in load(R/'prepared-1281-second.json') if p.chain=='lidl' and p.source_provenance.provider_store_id=='0163']
result={}
for phase,products,ref,cls in [('before',before,old,matcher),('after',after,current,ProductMatcher)]:
    sys.modules['app.services.nutrition_reference']=ref
    facts=reviewed_facts(products);rows=[]
    for p in products:
        fact=facts.get((p.store_id,p.product_id))
        planner=SimpleNamespace(spec=SimpleNamespace(allow_nutrition_estimates=True),source_facts=lambda _,f=fact:f)
        e=PersonalPlanner._nutrition_evidence(planner,p,canonicalize_ingredient_name(p.name),'g',{'kcal','fat_g','carbs_g','protein_g'},None)
        need=NormalizedIngredient(canonical_name=p.name.casefold(),required_quantity=p.package_quantity,unit=p.package_unit)
        rows.append({'chain':p.chain,'store':p.source_provenance.provider_store_id,'name':p.name,'id':p.source_provenance.retailer_product_id,'package':[p.package_quantity,p.package_unit], 'matched':bool(cls().match(need,[p])), 'nutrition_reference_per_edible_100g': e.source_product_id if e else None,'nutrition_kind':getattr(e,'evidence_kind','product_declaration') if e else None,'nutrition_compatible_purchase_unit':e is not None and p.usable_unit=='g'})
    result[phase]=rows
    print(phase,Counter((r['chain'],r['store']) for r in rows))
    print('NUTRITION',[(r['chain'],r['store'],r['name'],r['nutrition_kind'],r['nutrition_compatible_purchase_unit']) for r in rows if r['nutrition_reference_per_edible_100g']])
    print('MATCHED',Counter((r['chain'],r['store']) for r in rows if r['matched']))
sys.modules['app.services.nutrition_reference']=current
(R/'nutrition-comparison.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
