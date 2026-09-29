"""Revalidate native paths after rejecting composed foods as plain ingredients."""
import os,json,subprocess,sys,shutil
from pathlib import Path
os.environ.update(GROCERY_DATABASE_URL='sqlite:////work/base/refreshed.sqlite',GROCERY_RAW_SNAPSHOT_ROOT='/work/raw')
out=Path('/work/profile');identity='--identity-guard' in sys.argv;fallback='--fallback-guard' in sys.argv
guard='fallback' if fallback else 'identity' if identity else 'composite'
archive=out/('before-'+guard+'-guard');archive.mkdir(exist_ok=True)
for p in out.glob('*.json'):
 if p.name.startswith('after-') or p.name in {'all-84.json','all-84-diagnostics.json','search-reference.json','http-new-recipes-after-integration.json','http-cream-after-integration.json'}:
  shutil.copy2(p,archive/p.name)
for job in ['probe_job.py','profile_job.py','search_job.py','http_generated_job.py','http_cream_job.py','rebuild_evidence_job.py']:
 subprocess.run([sys.executable,'/evaluation/'+job,'after'],check=True)
subprocess.run([sys.executable,'/evaluation/evaluate_profile.py','--recipe-version','edible-input-v1','--artifact','/work/universe.json','--request',str(out/'after-edible-input-v1-public-exact-request.json'),'--output',str(out),'--label','after-edible-input-v1-public-exact','--clock','2026-09-24T21:16:35.494010+00:00','--cases','restored-rebuilt','--universes','/work/base/price-universes'],check=True)
if fallback:
 subprocess.run([sys.executable,'/evaluation/evaluate_profile.py','--recipe-version','legacy','--artifact','/work/universe.json','--request',str(out/'after-edible-input-v1-public-exact-request.json'),'--output',str(out),'--label','after-legacy-public-exact','--clock','2026-09-24T21:16:35.494010+00:00','--cases','restored-original','--universes','/work/base/price-universes'],check=True)
before=json.loads((archive/'all-84.json').read_bytes());after=json.loads((out/'all-84.json').read_bytes())
assert len(before)==len(after)==84
changes=[]
for b,a in zip(before,after,strict=True):
 assert b['adapted']==a['adapted']
 if b.get('nutrition_basket_passed')!=a.get('nutrition_basket_passed') or b.get('basket',{}).get('total')!=a.get('basket',{}).get('total'):
  changes.append({'recipe':a['adapted']['name'],'before_pass':b.get('nutrition_basket_passed'), 'after_pass':a.get('nutrition_basket_passed'),'before_cost':b.get('basket',{}).get('total'),'after_cost':a.get('basket',{}).get('total')})
(out/(guard+'-guard-verification.json')).write_text(json.dumps({'recipe_changes':changes,'all_84_repeated':True,'free_four_profiles_repeated':True,'http_repeated':True,'rebuild_repeated':True},ensure_ascii=False,indent=2),encoding='utf8')
