import json,hashlib,subprocess,sys,compileall,shutil
from pathlib import Path
from datetime import datetime,UTC
import xml.etree.ElementTree as E
R=Path('reports/willys-auto-20260924');old=json.loads((R/'initial-state.json').read_bytes())
files=json.loads((R/'changed-files.json').read_bytes())
with (R/'ruff.log').open('w',encoding='utf-8') as f:subprocess.run([sys.executable,'-m','ruff','check',*files],stdout=f,stderr=subprocess.STDOUT,check=True)
for file in files:assert compileall.compile_file(file,quiet=1)
(R/'compileall.json').write_text(json.dumps({'status':'PASS','files':files}),encoding='utf-8')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
accept=json.loads((R/'runtime-1280/ACCEPTANCE.json').read_bytes())
different={p:{'runtime':h,'package':sha(p)} for p,h in accept['final_code_hashes'].items() if sha(p)!=h}
assert set(different)=={'grocery_data/app/connectors/willys/flyer_text.py'}
q=json.loads((R/'FINAL-QUALIFICATION.json').read_bytes());assert sum(s['own'] for s in q['stores'])==208 and all(s['final_parser_equals_live_imported_purchase_rows'] for s in q['stores'])
q['final_text_rules_sha256']=sha('grocery_data/app/connectors/willys/flyer_text.py')
(R/'FINAL-QUALIFICATION.json').write_text(json.dumps(q,ensure_ascii=False,indent=2),encoding='utf-8')
tests=set();test_evidence={}
for name in ('focused-tests.xml','final-parser-tests.xml','preserved-chain-tests.xml'):
 rows=E.parse(R/name).findall('.//testcase');assert all(x.find('failure') is None and x.find('error') is None and x.find('skipped') is None for x in rows)
 tests.update((x.get('classname'),x.get('name')) for x in rows);test_evidence[name]={'tests':len(rows),'sha256':sha(R/name)}
verification={'checked_at':datetime.now(UTC).isoformat(),'unique_passed_tests':len(tests),'test_evidence':test_evidence,
 'runtime_acceptance':str(R/'runtime-1280/ACCEPTANCE.json'),'runtime_price_provider_checkout_refresh_hashes_equal_final_package':True,
 'parser_difference_since_runtime_start':different,'parser_difference_validation':'deposit label below price adversarial test; final raw replay equals all 208 imported purchase rows',
 'source_equivalence_sha256':sha(R/'FINAL-QUALIFICATION.json'),'no_new_observations_in_replay':True,
 'real_temporal_campaign_switch_verified':False,'previously_unreviewed_real_document_verified':False,
 'lund_publication':'blocked_incomplete_current_base','malmo_scope':'private OWN City Gross baseline plus Lidl and municipal Willys flyers; not complete federated Primat integration',
 'production_activation':False}
(R/'FINAL-VERIFICATION.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2),encoding='utf-8')
changed_existing={p for p,h in old.items() if not Path(p).exists() or sha(p)!=h}
assert changed_existing.issubset(set(files)),changed_existing-set(files)
package_files=files+['backend/tests/fixtures/willys-counted-offers-20260924.json','docs/willys_flyer_automatic.md']
manifest=[]
for file in package_files:
 target=R/'package-code'/file;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(file,target)
 assert sha(target)==sha(file)
 manifest.append({'path':file,'sha256':sha(file),'baseline_sha256':old.get(file)})
manifest_data={'created_at':datetime.now(UTC).isoformat(),'kind':'incremental reviewable package on preserved workspace, no activation',
 'files':manifest,'baseline_existing_files_unchanged':len(old)-len(changed_existing),'baseline_existing_files_changed':sorted(changed_existing),
 'verification':{'path':'FINAL-VERIFICATION.json','sha256':sha(R/'FINAL-VERIFICATION.json')},
 'report_sha256':sha(R/'README.md'),'release_sha256':sha(R/'RELEASE.md')}
(R/'PACKAGE.json').write_text(json.dumps(manifest_data,ensure_ascii=False,indent=2),encoding='utf-8')
print('Package verified:',len(manifest),'files,',len(tests),'unique passing tests,',len(old)-len(changed_existing),'initial files unchanged')
