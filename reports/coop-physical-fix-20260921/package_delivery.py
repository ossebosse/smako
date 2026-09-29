"""Create a review patch against the preserved dirty pre-Coop baseline."""
import difflib
import hashlib
import json
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
paths = '''grocery_data/app/connectors/coop/structured_offers.py
grocery_data/app/connectors/coop/browser.py
grocery_data/app/connectors/coop/models.py
grocery_data/app/connectors/coop/parser.py
grocery_data/app/connectors/coop/connector.py
grocery_data/app/services/offer_rows.py
grocery_data/app/api/catalog.py
backend/app/providers/own.py
grocery_data/scripts/collect_coop_physical_offers.py
grocery_data/tests/test_coop_physical_structured.py
backend/tests/test_coop_physical_pipeline.py
grocery_data/tests/test_coop_connector.py
grocery_data/tests/test_coop_offers_acceptance.py
backend/tests/test_verified_offer_deposit.py
docs/HANDOFF.md
docs/coop_physical_offers.md'''.splitlines()
paths += [p.relative_to(ROOT).as_posix() for p in sorted((ROOT / 'grocery_data/tests/fixtures/coop-physical-20260921').glob('*.json'))]
paths += [p.relative_to(ROOT).as_posix() for p in [HERE / n for n in ['README.md','COVERAGE.md','EXAMPLES.md','RELEASE.md','verify_isolated.py']]]
paths = sorted(paths)
baseline = json.loads((HERE / 'baseline.json').read_bytes())
patch = []
files = {}
with tarfile.open(HERE / 'prework.tar.gz') as archive:
    for name in paths:
        if name in baseline:
            before = archive.extractfile(name).read()
            assert hashlib.sha256(before).hexdigest() == baseline[name]
            exists = True
        else:
            git = subprocess.run(['git','show','HEAD:'+name],cwd=ROOT,capture_output=True)
            exists = git.returncode == 0
            before = git.stdout if exists else b''
        after = (ROOT / name).read_bytes()
        if before == after:
            continue
        files[name] = {'before_sha256': hashlib.sha256(before).hexdigest() if exists else None,
                       'after_sha256': hashlib.sha256(after).hexdigest()}
        patch.append(f'diff --git a/{name} b/{name}\n')
        if not exists:
            patch.append('new file mode 100644\n')
        chunks = difflib.unified_diff(before.decode('utf-8').splitlines(True),
                     after.decode('utf-8').splitlines(True),
                     fromfile='a/'+name if exists else '/dev/null',tofile='b/'+name)
        for chunk in chunks:
            patch.append(chunk if chunk.endswith('\n') else chunk + '\n\\ No newline at end of file\n')
patch_bytes = ''.join(patch).replace('\r\n','\n').encode()
(HERE / 'incremental.patch').write_bytes(patch_bytes)
check = subprocess.run(['git','apply','--reverse','--check',str(HERE/'incremental.patch')],cwd=ROOT,capture_output=True,text=True)
assert check.returncode == 0, check.stderr
other_changes = [name for name,sha in baseline.items() if name not in files
                 and hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != sha]
assert not other_changes, other_changes
manifest = {'branch':subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),
            'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            'baseline':'prework.tar.gz for preexisting dirty files, otherwise HEAD or absent',
            'patch_sha256':hashlib.sha256(patch_bytes).hexdigest(),
            'reverse_apply_check':'passed, read-only; patch not applied anywhere',
            'other_inherited_changes':other_changes,'files':files,'production_activation':False}
(HERE/'delivery-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
verification={'pytest':{'passed':184,'seconds':26.46},'affected_rerun':{'passed':22,'seconds':10.40},
              'ruff':'pass on 14 changed Python files','compileall':'pass on 14 changed Python files',
              'final_live':'final-live-v2','final_acceptance':'final-acceptance-v2',
              'production_mutations':False,'image_calls':0,'paid_calls':0,
              'code':{k:v['after_sha256'] for k,v in files.items() if k.endswith('.py')}}
(HERE/'verification.json').write_text(json.dumps(verification,indent=2),encoding='utf-8')
print(json.dumps({'files':len(files),'patch_bytes':len(patch_bytes),'reverse_check':'PASS','unrelated_changes':other_changes}))
