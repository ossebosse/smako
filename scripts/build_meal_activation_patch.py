"""Package the tested meal/content image with the later reviewed app fixes.

No source-process image or production configuration is changed by this command.
"""
import argparse
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

BASE = '54cb2e8159a126de26fa11cb1d393dc275238fd3'
TAG = 'smako-content:all-classes-20261008'
IMAGE = 'sha256:9784eb872990039ffb547203c7f4b45f424fa5c58c0c275bcfe564be189d8fc6'
FILES = ('backend/app/api/plan.py', 'backend/app/services/beta_observability.py',
         'backend/app/services/app_incidents.py', 'backend/app/services/price_universe.py')


def blob(commit, path):
    result = subprocess.run(['git', 'show', commit + ':' + path], capture_output=True)
    if result.returncode:
        if subprocess.run(['git', 'cat-file', '-e', commit + ':' + path],
                          capture_output=True).returncode:
            return None
        result.check_returncode()
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    commit = subprocess.check_output(['git', 'rev-parse', '--verify',
                                     args.commit + '^{commit}']).decode().strip()
    actual = subprocess.check_output(['docker', 'image', 'inspect', TAG,
                                     '--format', '{{.Id}}']).decode().strip()
    if actual != IMAGE:
        raise ValueError('Unexpected content base image')
    files = {p: blob(commit, p) for p in FILES}
    if any(value is None for value in files.values()):
        raise ValueError('Missing release file')
    manifest = {'schema': 'smako-meal-activation-v1', 'commit': commit,
                'base_commit': BASE, 'base_image': IMAGE, 'base_tag': TAG,
                'content_commit': 'e819a9b2e8ae106bd0b6c9d54b71a95a0676e4b5',
                'files': {p: hashlib.sha256(v).hexdigest() for p, v in files.items()},
                'base_files': {p: hashlib.sha256(v).hexdigest() if v is not None else None
                               for p in FILES for v in [blob(BASE, p)]}}
    files['APP-PATCH.json'] = json.dumps(manifest, indent=2).encode()
    files['verify-base.py'] = b'''import hashlib,json
from pathlib import Path
m=json.loads(Path('/tmp/APP-PATCH.json').read_bytes())
for p,h in m['base_files'].items():
 f=Path('/srv/app')/p
 assert (hashlib.sha256(f.read_bytes()).hexdigest() if f.exists() else None)==h,p
'''
    copies = '\n'.join('COPY --chown=app:app ' + p + ' /srv/app/' + p for p in FILES)
    files['Dockerfile'] = (f'FROM {TAG}\nUSER root\n'
        'COPY APP-PATCH.json /tmp/APP-PATCH.json\nCOPY verify-base.py /tmp/verify-base.py\n'
        'RUN python /tmp/verify-base.py\n' + copies + '\n'
        'COPY APP-PATCH.json /srv/app/APP-PATCH.json\n'
        f'ENV BUILD_ID=meal-library-{commit[:12]}\n'
        f'LABEL org.opencontainers.image.revision={commit}\nUSER app\n').encode()
    args.output.mkdir(parents=True, exist_ok=True)
    target = args.output / f'smako-meal-library-{commit[:12]}.zip'
    if target.exists():
        raise ValueError('Immutable package already exists')
    with zipfile.ZipFile(target, 'x', zipfile.ZIP_DEFLATED) as archive:
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
