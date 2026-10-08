"""Build only the reviewed dd12 app incident/domain-status delta, never meal code.

Usage: python scripts/build_app_incident_patch.py --commit HEAD --output .local/releases/app-incident
The deployed image is checked by the build operator, and every base file by Docker.
"""
import argparse
import hashlib
import json
import runpy
import subprocess
import zipfile
from pathlib import Path

BASE = 'dd12cc80e98c79aa32c159223c8bc1ceeaaa7580'
PARENT = '0462ccfdc198e6133c35dcbc44d346516dd7bc0f'
DOMAIN_FIX = 'ab2718aa645da0fcc797a746cbe47267ad1946a0'
IMAGE = 'sha256:c8362751b13a6e649beadad2a3c27b9b5df8bfd1e2fa177ff68e01e1d7b8b2c7'
TAG = 'smako-status-reconnect:dd12cc80e98c'
FILES = ('backend/app/api/personal.py', 'backend/app/api/plan.py',
         'backend/app/services/beta_observability.py', 'backend/app/services/app_incidents.py')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    helpers = runpy.run_path(str(Path(__file__).with_name('build_source_patch.py')))
    blob, transplant = helpers['blob'], helpers['transplant']
    commit = subprocess.check_output(['git', 'rev-parse', '--verify', args.commit+'^{commit}']).decode().strip()
    files, base_hashes, hashes = {}, {}, {}
    for path in FILES:
        base = blob(BASE, path)
        content = base
        if path in FILES[:2]:
            content = transplant(content, blob(DOMAIN_FIX+'^', path), blob(DOMAIN_FIX, path))
        # Only this task's differences, never full later versions of shared files.
        content = transplant(content, blob(PARENT, path), blob(commit, path))
        files[path] = content
        base_hashes[path] = hashlib.sha256(base).hexdigest() if base else None
        hashes[path] = hashlib.sha256(content).hexdigest()
    manifest = {'schema': 'smako-app-incident-patch-v1', 'commit': commit,
                'base_commit': BASE, 'base_image': IMAGE, 'base_tag': TAG,
                'domain_fix_commit': DOMAIN_FIX, 'delta_parent': PARENT,
                'files': hashes, 'base_files': base_hashes}
    files['APP-PATCH.json'] = json.dumps(manifest, indent=2).encode()
    files['verify-base.py'] = b'''import hashlib,json
from pathlib import Path
m=json.loads(Path('/tmp/APP-PATCH.json').read_bytes())
for p,h in m['base_files'].items():
 f=Path('/srv/app')/p
 assert (hashlib.sha256(f.read_bytes()).hexdigest() if f.exists() else None)==h,p
'''
    copies = '\n'.join('COPY --chown=app:app '+p+' /srv/app/'+p for p in FILES)
    files['Dockerfile'] = (f'FROM {TAG}\nUSER root\n'
        'COPY APP-PATCH.json /tmp/APP-PATCH.json\nCOPY verify-base.py /tmp/verify-base.py\n'
        'RUN python /tmp/verify-base.py\n'+copies+'\nCOPY APP-PATCH.json /srv/app/APP-PATCH.json\n'
        f'ENV BUILD_ID=app-incident-{commit[:12]}\nLABEL org.opencontainers.image.revision={commit}\nUSER app\n').encode()
    args.output.mkdir(parents=True, exist_ok=True)
    target = args.output / f'smako-app-incident-{commit[:12]}.zip'
    if target.exists():
        raise ValueError('immutable package already exists')
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path, data in sorted(files.items()):
            info = zipfile.ZipInfo(path, (2026, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    manifest['package'] = {'file': target.name, 'bytes': target.stat().st_size,
                           'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}
    (args.output / 'package.json').write_text(json.dumps(manifest, indent=2), encoding='utf8')
    print(json.dumps(manifest['package']))


if __name__ == '__main__':
    main()
