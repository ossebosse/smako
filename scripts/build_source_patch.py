"""Package reviewed source-process changes on a pinned existing runtime.

Three Git identities are explicit: deployed base, unchanged comparison parent,
and reviewed candidate. Only candidate deltas are applied to the deployed base;
unrelated newer consumer/meal code never enters the source image.
"""
import argparse
import base64
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


def exact_runtime_base(base, path, runtime):
    """Allow only a proven newline representation of the reviewed Git base."""
    encoded = runtime["files"][path]
    actual = base64.b64decode(encoded, validate=True) if encoded is not None else None
    if actual == base:
        return actual
    if base is None or actual is None or not path.endswith(".py") or actual.replace(b"\r\n", b"\n") != base:
        raise ValueError("runtime source differs from reviewed Git base: " + path)
    return actual


AXFOOD_READER_FILES = frozenset({
    'backend/app/services/axfood_product_details.py',
    'backend/app/services/personal_source_facts.py',
    'grocery_data/app/services/axfood_detail_archive.py',
})


SOURCE_DASHBOARD_FILES = frozenset({
    'backend/app/services/store_collection_history.py',
    'backend/app/services/store_operations.py', 'backend/app/static/admin.js',
})
COOP_APP_BASE_REFS = {
    'grocery_data/app/connectors/coop/online_catalog_parser.py': '50d1a87bf513640fbb1e07256c6c037f304e8252',
    'grocery_data/app/connectors/coop/schema_review.py': 'b235e51ec39ea2367e157e5ddf2da750de1afcdc',
    'grocery_data/app/services/collector.py': 'a162f948eb98243b313a888d7a5fbae8161f25ab',
}


def coop_app_backport(path, base, after):
    """Reviewed v2 app lineage: replace only Coop's shared-collector branch."""
    if path not in COOP_APP_BASE_REFS or base is None or after is None:
        raise ValueError('unreviewed Coop app backport path')
    if path != 'grocery_data/app/services/collector.py':
        return after  # Dedicated Coop modules, with their exact historical Git base.
    def span(data):
        start = data.index(b'    elif chain == Chain.COOP and parser_version')
        end = data.index(b'    elif chain == Chain.HEMKOP and parser_version', start)
        if data.count(b'    elif chain == Chain.COOP and parser_version') != 1:
            raise ValueError('ambiguous Coop collector branch')
        return start, end
    start, end = span(base)
    new_start, new_end = span(after)
    return base[:start] + after[new_start:new_end] + base[end:]


def selected_paths(changed, *, axfood_reader_only=False, include_source_dashboard=False):
    if axfood_reader_only:
        if not AXFOOD_READER_FILES <= set(changed):
            raise ValueError('Axfood reader release requires every reviewed reader dependency')
        return sorted(AXFOOD_READER_FILES)
    return [x for x in changed if x.startswith(('grocery_data/app/', 'deploy/scripts/'))
            or x in ('grocery_data/__main__.py', 'grocery_data/ops.py', 'backend/app/services/price_universe.py',
                     'backend/app/providers/coop_municipality_offers.py',
                     'grocery_data/scripts/collect_coop_municipality.py')
            or (include_source_dashboard and x in SOURCE_DASHBOARD_FILES)]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('base-commit', 'parent-commit', 'commit', 'base-image', 'base-tag'):
        p.add_argument('--'+name, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--base-config', type=Path, required=True,
                   help='Private docker image inspect JSON for the pinned base image')
    p.add_argument('--base-files', type=Path,
                   help='Private {image,files} JSON with base64 bytes from the pinned runtime')
    p.add_argument('--axfood-reader-only', action='store_true',
                   help='Separate reviewed three-file Axfood reader package; exclude planner/scheduler deltas')
    p.add_argument('--include-source-dashboard', action='store_true',
                   help='Include the three explicit municipal source dashboard dependencies in the app image')
    p.add_argument('--coop-online-app-backport', action='store_true',
                   help='Reviewed historical app-only Coop bases; preserve all non-Coop collector branches')
    args = p.parse_args()
    for name in ('base_commit', 'parent_commit', 'commit'):
        setattr(args, name, git('rev-parse', '--verify', getattr(args, name)+'^{commit}').decode().strip())
    import re

    if not re.fullmatch('sha256:[a-f0-9]{64}', args.base_image) or not re.fullmatch('[a-z0-9:._-]+', args.base_tag):
        raise ValueError('invalid pinned image identity')
    changed = git('diff', '--name-only', args.parent_commit, args.commit).decode().splitlines()
    selected = selected_paths(changed, axfood_reader_only=args.axfood_reader_only,
                              include_source_dashboard=args.include_source_dashboard)
    if not selected:
        raise ValueError('empty source patch')
    runtime = json.loads(args.base_files.read_bytes()) if args.base_files else None
    if runtime is not None and (runtime.get("image") != args.base_image or set(runtime["files"]) != set(selected)):
        raise ValueError("runtime file inventory does not match the pinned image and selected files")
    files, base_hashes, hashes = {}, {}, {}
    for path in selected:
        backport = args.coop_online_app_backport and path in COOP_APP_BASE_REFS
        base = blob(COOP_APP_BASE_REFS[path] if backport else args.base_commit, path)
        actual = exact_runtime_base(base, path, runtime) if runtime is not None else base
        result = (coop_app_backport(path, base, blob(args.commit, path)) if backport else
                  transplant(base, blob(args.parent_commit, path), blob(args.commit, path)))
        if result is None:
            raise ValueError('source file deletion requires separate packaging review')
        files[path] = result
        hashes[path] = hashlib.sha256(result).hexdigest()
        base_hashes[path] = hashlib.sha256(actual).hexdigest() if actual is not None else None
    manifest = {'schema': 'smako-source-patch-v2', 'commit': args.commit,
                'parent_commit': args.parent_commit, 'base_commit': args.base_commit,
                'base_image': args.base_image, 'base_tag': args.base_tag,
                'files': hashes, 'base_files': base_hashes}
    if args.axfood_reader_only:
        manifest['scope'] = 'axfood-reader-only; no planner, scheduler or price changes'
    if args.coop_online_app_backport:
        manifest['coop_app_base_refs'] = COOP_APP_BASE_REFS
    from beta_release_workers.image_config import final_image_config, flatten_instructions
    inspected = json.loads(args.base_config.read_bytes())
    if not isinstance(inspected, list) or len(inspected) != 1 or inspected[0]['Id'] != args.base_image:
        raise ValueError('image configuration does not match the pinned base')
    expected_config = final_image_config(
        inspected[0]['Config'], release='source-ops-' + args.commit[:12], commit=args.commit,
        base_image=args.base_image, managed_kind='source-release-v1')
    flatten = flatten_instructions(expected_config)
    manifest['flattened_image_config_sha256'] = hashlib.sha256(
        json.dumps(expected_config, sort_keys=True).encode()).hexdigest()
    files['IMAGE-CONFIG.json'] = json.dumps(expected_config, sort_keys=True).encode()
    files['SOURCE-PATCH.json'] = json.dumps(manifest, indent=2).encode()
    files['verify-base.py'] = b'''import hashlib,json
from pathlib import Path
m=json.loads(Path('/tmp/SOURCE-PATCH.json').read_bytes())
for p,h in m['base_files'].items():
 f=Path('/srv/app')/p
 assert (hashlib.sha256(f.read_bytes()).hexdigest() if f.exists() else None)==h,p
'''
    copies = '\n'.join('COPY --chown=app:app '+path+' /srv/app/'+path for path in files if path in selected)
    files['Dockerfile'] = (f'FROM {args.base_tag} AS patched\nUSER root\n'
        'COPY SOURCE-PATCH.json /tmp/SOURCE-PATCH.json\nCOPY verify-base.py /tmp/verify-base.py\n'
        'RUN python /tmp/verify-base.py\n'+copies+'\nCOPY SOURCE-PATCH.json /srv/app/SOURCE-PATCH.json\n'
        + flatten).encode()
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
