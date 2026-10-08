"""Package reviewed source-process changes on a pinned existing runtime.

Three Git identities are explicit: deployed base, unchanged comparison parent,
and reviewed candidate. Only candidate deltas are applied to the deployed base;
unrelated newer consumer/meal code never enters the source image.
"""
import argparse
import difflib
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path


def git(*args):
    return subprocess.check_output(['git', *args])


def blob(ref, path):
    proc = subprocess.run(['git', 'show', ref+':'+path], capture_output=True, check=False)
    return proc.stdout if proc.returncode == 0 else None


def transplant(base, before, after):
    if base == before:
        return after
    if base is None or before is None or after is None:
        raise ValueError('incompatible source lineage')
    old, new = before.decode().splitlines(keepends=True), after.decode().splitlines(keepends=True)
    result = base.decode()
    matcher = difflib.SequenceMatcher(a=old, b=new, autojunk=False)
    # Each replacement must have exactly one matching context in the deployed
    # version. Never offset-fuzz or fall back to copying the newer entire file.
    for group in reversed(list(matcher.get_grouped_opcodes(3))):
        i1, i2 = group[0][1], group[-1][2]
        j1, j2 = group[0][3], group[-1][4]
        source, target = ''.join(old[i1:i2]), ''.join(new[j1:j2])
        if not source or result.count(source) != 1:
            raise ValueError('source patch context is missing or ambiguous')
        result = result.replace(source, target, 1)
    return result.encode()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('base-commit', 'parent-commit', 'commit', 'base-image', 'base-tag'):
        p.add_argument('--'+name, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    for name in ('base_commit', 'parent_commit', 'commit'):
        setattr(args, name, git('rev-parse', '--verify', getattr(args, name)+'^{commit}').decode().strip())
    import re

    if not re.fullmatch('sha256:[a-f0-9]{64}', args.base_image) or not re.fullmatch('[a-z0-9:._-]+', args.base_tag):
        raise ValueError('invalid pinned image identity')
    changed = git('diff', '--name-only', args.parent_commit, args.commit).decode().splitlines()
    selected = [x for x in changed if x.startswith(('grocery_data/app/', 'deploy/scripts/'))
                or x in ('grocery_data/__main__.py', 'grocery_data/ops.py', 'backend/app/services/price_universe.py')]
    if not selected:
        raise ValueError('empty source patch')
    files, base_hashes, hashes = {}, {}, {}
    for path in selected:
        base = blob(args.base_commit, path)
        result = transplant(base, blob(args.parent_commit, path), blob(args.commit, path))
        if result is None:
            raise ValueError('source file deletion requires separate packaging review')
        files[path] = result
        hashes[path] = hashlib.sha256(result).hexdigest()
        base_hashes[path] = hashlib.sha256(base).hexdigest() if base is not None else None
    manifest = {'schema': 'smako-source-patch-v2', 'commit': args.commit,
                'parent_commit': args.parent_commit, 'base_commit': args.base_commit,
                'base_image': args.base_image, 'base_tag': args.base_tag,
                'files': hashes, 'base_files': base_hashes}
    files['SOURCE-PATCH.json'] = json.dumps(manifest, indent=2).encode()
    files['verify-base.py'] = b'''import hashlib,json
from pathlib import Path
m=json.loads(Path('/tmp/SOURCE-PATCH.json').read_bytes())
for p,h in m['base_files'].items():
 f=Path('/srv/app')/p
 assert (hashlib.sha256(f.read_bytes()).hexdigest() if f.exists() else None)==h,p
'''
    copies = '\n'.join('COPY --chown=app:app '+path+' /srv/app/'+path for path in files if path in selected)
    files['Dockerfile'] = (f'FROM {args.base_tag}\nUSER root\n'
        'COPY SOURCE-PATCH.json /tmp/SOURCE-PATCH.json\nCOPY verify-base.py /tmp/verify-base.py\n'
        'RUN python /tmp/verify-base.py\n'+copies+'\nCOPY SOURCE-PATCH.json /srv/app/SOURCE-PATCH.json\n'
        f'ENV BUILD_ID=source-ops-{args.commit[:12]}\nLABEL org.opencontainers.image.revision={args.commit}\nUSER app\n').encode()
    args.output.mkdir(parents=True, exist_ok=True)
    target = args.output/f'smako-source-ops-{args.commit[:12]}.zip'
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
    (args.output/'source-package.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps(manifest['package']))


if __name__ == '__main__':
    main()
