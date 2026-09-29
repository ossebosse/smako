from pathlib import Path
import hashlib,json,subprocess
R=Path(__file__).resolve().parents[2]; out=Path(__file__).parent
p=json.loads((R/'reports/recipe-search-20260927/PACKAGE.json').read_bytes())
checks={k:hashlib.sha256((R/k).read_bytes()).hexdigest()==v['after_sha256'] for k,v in p['changed_application_files'].items()}
evidence={k:hashlib.sha256((R/k).read_bytes()).hexdigest()==v for k,v in p.get('evidence_hashes',{}).items()}
files={}
for folder in ['backend/app','grocery_data/app','grocery_data/scripts','deploy/scripts','backend/scripts','grocery_data/alembic']:
 for f in (R/folder).rglob('*'):
  if f.is_file() and '__pycache__' not in f.parts:files[f.relative_to(R).as_posix()]=hashlib.sha256(f.read_bytes()).hexdigest()
for f in ['deploy/requirements.txt','grocery_data/__init__.py','grocery_data/alembic.ini','pyproject.toml','grocery_data/__main__.py','grocery_data/source_cli.py','grocery_data/local_relay.py','backend/requirements.txt','grocery_data/requirements.txt','grocery_data/requirements-coop-candidate.txt','grocery_data/requirements-lidl-candidate.txt']:
 if (R/f).exists():files[f]=hashlib.sha256((R/f).read_bytes()).hexdigest()
result={'prior_application_checks':checks,'prior_package_keys':list(p),'prior_evidence_checks':evidence,'files':files,'source_tree_sha256':hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest(),'git_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),'production_activation':False}
(out/'source-manifest.json').write_text(json.dumps(result,indent=2))
assert all(checks.values()) and all(evidence.values())
print({'prior_app_files':len(checks),'evidence':len(evidence),'packaged_files':len(files),'source_tree':result['source_tree_sha256']})

