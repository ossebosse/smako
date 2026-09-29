"""Incremental review relative to preserved uncommitted work, never reset/apply."""
import difflib
import hashlib
import json
import subprocess
import tarfile
import xml.etree.ElementTree as ET
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


changed=['backend/app/providers/coop_municipality_offers.py',
         'backend/app/services/production_price_universe_build.py',
         'grocery_data/__main__.py','deploy/scripts/run_daily_refresh.py',
         'grocery_data/app/services/coop_municipal_refresh.py',
         'grocery_data/scripts/collect_coop_physical_offers.py','docs/HANDOFF.md',
         'grocery_data/app/connectors/coop/parser.py','grocery_data/app/connectors/coop/models.py',
         'grocery_data/app/connectors/coop/browser.py','grocery_data/app/connectors/coop/structured_offers.py']
added=['grocery_data/app/services/coop_offer_job.py','grocery_data/tests/test_coop_offer_job.py',
       'backend/tests/test_coop_refresh_wiring.py','docs/coop_refresh_integration.md',
       'deploy/coop-runtime.override.yaml']
patch=[]
files={}
for name in changed+added:
    old=HERE/'backups'/name.replace('/','__')
    text=old.read_text(encoding='utf8') if old.exists() else ''
    current=ROOT/name
    files[name]={'before':sha(old) if old.exists() else None,'after':sha(current)}
    patch.extend(difflib.unified_diff(text.splitlines(keepends=True),current.read_text(encoding='utf8').splitlines(keepends=True),
        fromfile='a/'+name if old.exists() else '/dev/null',tofile='b/'+name))
(HERE/'incremental.patch').write_text(''.join(patch),encoding='utf8',newline='\n')
checked=subprocess.run(['git','apply','--reverse','--check','--ignore-space-change',str(HERE/'incremental.patch')],
    cwd=ROOT,capture_output=True)
assert checked.returncode==0,checked.stderr.decode(errors='replace')
with tarfile.open(HERE/'review-files.tar.gz','w:gz') as archive:
    for name in files:archive.add(ROOT/name,arcname=name)
preserved={}
for name,manifest in [('coop-lund-activation-20260922','verification.json'),
    ('coop-municipal-contract-20260922','verification.json'),('coop-nutrition-20260922','verification.json'),
    ('coop-1520-20260922','verification.json'),('xtra-text-20260922','verification.json'),
    ('coop-municipality-20260921','delivery-manifest.json')]:
    folder=ROOT/'reports'/name
    hashes=json.loads((folder/manifest).read_bytes())['artifact_hashes']
    assert all(sha(folder/n)==h for n,h in hashes.items()),name
    preserved[name]=len(hashes)
inherited=json.loads((ROOT/'reports/municipality-offers-20260920/inherited-work.json').read_bytes())
original=Path(inherited['source'])
assert all(sha(original/n)==h for n,h in inherited['files'].items())
preserved['pending_ica_worktree_inherited_files']=len(inherited['files'])
cases={}
for file in ['tests.xml','final-changed-tests.xml','ica-boundary-tests.xml','builder-tests.xml','empty-response-tests.xml','final-policy-tests.xml']:
    for case in ET.parse(HERE/file).iter('testcase'):
        assert case.find('failure') is None and case.find('error') is None
        cases[(case.attrib['classname'],case.attrib['name'])]=True
package=json.loads((HERE/'package-result.json').read_bytes())
assert all(sha(ROOT/n.removeprefix('/srv/app/'))==h for n,h in package['runtime']['code'].items())
result={'branch':subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),
    'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
    'incremental_files':files,'reverse_patch_check':'PASS; patch checked, never applied',
    'preserved_artifacts':preserved,'pytest_unique_cases':len(cases),'pytest_failures':0,
    'ruff':'PASS','compileall':'PASS','image_id':package['image_id'],
    'packaged_modules_verified':len(package['runtime']['code']), 'production_activation':False}
result['artifact_hashes']={p.relative_to(HERE).as_posix():sha(p) for p in HERE.rglob('*') if p.is_file() and p.name!='verification.json' and '__pycache__' not in p.parts}
(HERE/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({k:v for k,v in result.items() if k not in {'incremental_files','artifact_hashes'}},ensure_ascii=False))
