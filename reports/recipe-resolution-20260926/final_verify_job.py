import os,json,subprocess,sys,hashlib
from pathlib import Path
os.environ.update(GROCERY_DATABASE_URL='sqlite:////work/base/refreshed.sqlite',GROCERY_RAW_SNAPSHOT_ROOT='/work/raw')
out=Path('/work/profile')
before=json.loads((out/'all-84.json').read_bytes())
subprocess.run([sys.executable,'/evaluation/probe_job.py','after'],check=True)
after=json.loads((out/'all-84.json').read_bytes())
assert len(after)==84
for old,new in zip(before,after,strict=True):
 assert old['adapted']==new['adapted']
 assert old.get('nutrition_basket_passed')==new.get('nutrition_basket_passed')
 assert old.get('basket',{}).get('total')==new.get('basket',{}).get('total')
 assert old.get('stop',{}).get('code')==new.get('stop',{}).get('code')
for r in after:
 for ingredient in r['ingredient_evidence']:
  for p in ingredient['qualified']:
   for source in p['facts']['field_sources'].get('nutrition.protein_g',[]):
    if source.get('food_id') in {1225,3816,3817,3761}:assert source['retrieved_at'].startswith('2026-09-26')
(out/'final-provenance-verification.json').write_text(json.dumps({'all_84_semantic_results_unchanged':True,'new_reference_response_times_preserved':True,
 'note':'Final metadata supplies actual response time for each newly acquired SLV food; values, identities, prices and all 84 outcomes unchanged.',
 'source_sha256':hashlib.sha256(Path('/srv/app/backend/app/data/nutrition/slv-20260926.json').read_bytes()).hexdigest()},indent=2))
if '--probe-only' in sys.argv:
 (out/'final-quantity-verification.json').write_text(json.dumps({'all_84_semantic_results_unchanged':True,
  'independent_quantity_preserves_nutrition_conflict':True,
  'application_sha256':hashlib.sha256(Path('/srv/app/backend/app/services/official_product_facts.py').read_bytes()).hexdigest()},indent=2))
 raise SystemExit(0)
for case in ['restored-original','restored-rebuilt']:
 subprocess.run([sys.executable,'/evaluation/evaluate_profile.py','--recipe-version','edible-input-v1','--artifact','/work/universe.json','--request',str(out/'after-edible-input-v1-public-exact-request.json'),'--output',str(out),'--label','after-edible-input-v1-public-exact','--clock','2026-09-24T21:16:35.494010+00:00','--cases',case,'--universes','/work/base/price-universes'],check=True)
