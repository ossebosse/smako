"""Server-side immutable app hotfix build from a verified Git package; no switch."""
import argparse
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--commit', required=True)
parser.add_argument('--sha256', required=True)
parser.add_argument('--evidence-root', type=Path, default=Path('/opt/smako/evidence/public-menu-20261002'))
args = parser.parse_args()
commit = args.commit
assert len(commit) == 40 and all(c in '0123456789abcdef' for c in commit)
base = 'sha256:d8a166fa7ee162cd0570f9d8089ff800e00d9c949ac3c674e387c5fff1538dd7'
base_tag = 'smako-lund-transition:08c137475d9c'
assert subprocess.check_output(['docker','image','inspect',base_tag,'--format','{{.Id}}'],text=True).strip() == base
evidence = args.evidence_root.resolve()
assert evidence.is_relative_to('/opt/smako/evidence')
archive = evidence / f'smako-server-{commit[:12]}.zip'
assert hashlib.sha256(archive.read_bytes()).hexdigest() == args.sha256
release = Path('/opt/smako/releases/public-menu-' + commit[:12])
assert Path('/opt/smako/current').resolve() != release
with zipfile.ZipFile(archive) as source:
    manifest = json.loads(source.read('RELEASE.json'))
    assert manifest['commit'] == commit and manifest['kind'] == 'server'
    for name, digest in manifest['files'].items():
        assert hashlib.sha256(source.read(name)).hexdigest() == digest
        assert not Path(name).is_absolute() and '..' not in Path(name).parts
    if release.exists():
        assert all(hashlib.sha256((release/n).read_bytes()).hexdigest() == h for n,h in manifest['files'].items())
    else:
        source.extractall(release)
dockerfile = evidence / 'Dockerfile.hotfix'
dockerfile.write_text(f'''FROM {base_tag}
LABEL org.opencontainers.image.revision={commit}
ENV BUILD_ID={commit}
COPY --chown=10001:10001 backend /srv/app/backend
COPY --chown=10001:10001 grocery_data /srv/app/grocery_data
COPY --chown=10001:10001 deploy /srv/app/deploy
COPY --chown=10001:10001 pyproject.toml RELEASE.json /srv/app/
''')
image = 'smako-public-menu:' + commit[:12]
with (evidence / f'image-build-{commit[:12]}.log').open('w') as log:
    subprocess.run(['docker','build','--network','none','-f',str(dockerfile),'-t',image,str(release)],stdout=log,stderr=log,check=True)
identity = subprocess.check_output(['docker','image','inspect',image,'--format','{{.Id}}'],text=True).strip()
(evidence/'candidate-image.json').write_text(json.dumps({'commit':commit,'image':identity,'release':str(release),'base_image':base,'network':'none'},indent=2))
print(identity)
