"""Freeze the tested local image, without loading/deploying it elsewhere."""
import subprocess,shlex,json
from pathlib import Path
code="""import subprocess,pathlib,hashlib,json
path=pathlib.Path('/tmp/smako-coop-nutrition-20260922/coop-candidate-image.tar')
assert not path.exists()
image='smako-coop-candidate:nutrition-20260922'
id=subprocess.check_output(['docker','inspect','--format','{{.Id}}',image],text=True).strip()
subprocess.run(['docker','image','save','-o',str(path),image],check=True)
path.chmod(0o600)
with path.open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
print(json.dumps({'image_id':id,'archive':str(path),'archive_sha256':sha,'bytes':path.stat().st_size,'production_activation':False}))
"""
r=subprocess.run(['ssh','smako','python3 -c '+shlex.quote(code)],capture_output=True,check=True)
d=json.loads(r.stdout);Path(__file__).with_name('package-export.json').write_text(json.dumps(d,indent=2),encoding='utf8');print(json.dumps(d))
