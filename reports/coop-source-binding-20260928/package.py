"""Final evidence inventory; no activation or publishing side effects."""
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
import xml.etree.ElementTree as ET

P=Path(__file__).parent;ROOT=P.parents[1]
def read(name):return json.loads((P/name).read_bytes())
assert read('acceptance.json')['status']=='PASS'
tests=ET.parse(P/'final-regression.xml').getroot().find('testsuite').attrib
assert tests['errors']==tests['failures']==tests['skipped']=='0'
source=read('source-manifest.json')
assert all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==h for name,h in source['files'].items())
prior=json.loads((P.parent/'lund-base-strategy-20260928/PACKAGE.json').read_bytes())
assert all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==h for name,h in prior['evidence_hashes'].items())
files=[p for p in P.rglob('*') if p.is_file() and p.name!='PACKAGE.json' and '__pycache__' not in p.parts]
files += [ROOT/'docs/HANDOFF.md',ROOT/'grocery_data/tests/test_coop_structured_schema_transition.py',
          ROOT/'grocery_data/tests/fixtures/coop-physical-transition-20260928.json.gz',
          ROOT/'backend/tests/test_coop_municipality_provider.py']
package={'created_at':datetime.now(UTC).isoformat(),'policy_id':'lund-own-five-base-20260928-v1',
    'policy_sha256':hashlib.sha256((P/'policy.json').read_bytes()).hexdigest(),
    'production_activation':False,'original_policy_changed':False,'prior_candidate_preserved':True,
    'image':read('image.json'),'source_tree_sha256':source['source_tree_sha256'],
    'application_source_files':len(source['files']),'application_code_changes':source['changed_from_verified_alternative'],
    'acceptance':{'status':'PASS','actual_coop_stores':len(read('acceptance.json')['rows']),
        'actual_serving_products':read('acceptance.json')['products_after'],'live_collection':'2026-09-28T11:01Z',
        'next_rebuild_fault_injection':True,'actual_restart':True,'http_profiles':4},
    'tests':{'passed':int(tests['tests']),'ruff':'PASS','compileall':'PASS','python':'3.12'},
    'prior_evidence':read('prior-evidence-verification.json'),
    'isolated_remote_root':'/var/tmp/smako-coop-source-binding-20260928',
    'rollback_candidate':'/var/tmp/smako-lund-base-strategy-20260928',
    'remaining_tasks':['original-policy Primat full_catalog blocker','ICA/Hemkop municipality gaps',
        'older PurchaseTerms binding','Lidl/Willys current campaign gaps','Malmo publication',
        'historical Lidl fixture','unsupported conditional Coop rows remain quarantined'],
    'evidence_hashes':{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}}
(P/'PACKAGE.json').write_text(json.dumps(package,ensure_ascii=False,indent=2),encoding='utf-8')
print('Packaged',len(files),'evidence files;',tests['tests'],'tests; production_activation=False')
