"""Read-only retained public input export. No retailer calls or private settings."""
import io
import shlex
import subprocess
import tarfile
from pathlib import Path

DEST = Path(__file__).parent / 'inputs'
CODE = r'''
from pathlib import Path
import tarfile,sys
p=Path('/work')
paths=[]
for base in ['coop-municipal/1281/attempts/20260928T070313-cfce2f18c7f5/xtra-3658',
             'ica-structured/1281/20260928T145357-0c7287ca',
             'coop-municipal/1281/attempts/20260928T110111-54abec7fc898/structured']:
 for f in (p/base).rglob('*'):
  if f.is_file() and f.suffix in {'.json','.html','.pdf'}: paths.append(f)
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as t:
 for f in paths:t.add(f,arcname=f.relative_to(p))
'''
cmd = ['docker','run','--rm','--network','none','--user','10001:10001',
       '-v','/var/tmp/smako-ica-hemkop-municipality-20260928/data:/work:ro',
       '--entrypoint','/opt/ica-venv/bin/python',
       'smako-ica-hemkop-municipality:20260928-v8','-c',CODE]
r = subprocess.run(['ssh','-oBatchMode=yes','smako','python3 -c '+shlex.quote(
    'import subprocess,sys;sys.stdout.buffer.write(subprocess.check_output('+repr(cmd)+'))')],
    capture_output=True,check=True)
DEST.mkdir(exist_ok=True)
with tarfile.open(fileobj=io.BytesIO(r.stdout),mode='r:gz') as t:
    for m in t.getmembers():
        p=DEST/m.name
        assert m.isfile() and p.resolve().is_relative_to(DEST.resolve())
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_bytes(t.extractfile(m).read())
print('Retained public files:',len(list(DEST.rglob('*'))))
