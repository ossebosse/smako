"""Recount every received authoring batch without importing or approving content."""
import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from app.services.ingredient_normalizer import canonicalize_ingredient_name
from app.services.meal_library_content import encoded, identity, validate_pack_bytes
from app.services.recipe_authoring import library_vocabulary, standardize
from app.services.recipe_library import current_recipes

SOURCE = Path('backend/app/data/recipes/incoming/authoring-1000-20261101')


def audit(source, vocabulary):
    rows, files, known, blockers, seen = [], [], [], defaultdict(set), set()
    verified = set()
    for manifest_path in sorted(source.glob('*/source/SOURCE-MANIFEST.json')):
        root = manifest_path.parent.resolve()
        for entry in json.loads(manifest_path.read_bytes())['preserved_files']:
            path = (root / entry['path']).resolve()
            if not path.is_relative_to(root):
                raise ValueError('Source path leaves delivery: ' + entry['path'])
            raw = path.read_bytes()
            if len(raw) != entry['bytes'] or hashlib.sha256(raw).hexdigest() != entry['sha256']:
                raise ValueError('Changed original source: ' + str(path))
            verified.add(path)
    for path in sorted(source.glob('*/source/paket/*.json')):
        if path.resolve() not in verified:
            raise ValueError('Unmanifested original source: ' + str(path))
        raw = path.read_bytes()
        document = json.loads(raw)
        if document.get('schema_version') != 'smako-recipe-authoring-v1':
            continue
        files.append({'path': path.relative_to(source).as_posix(), 'sha256': hashlib.sha256(raw).hexdigest()})
        for original in document['recipes']:
            rid = ':'.join(original.get(k, v) for k, v in [('base_id', ''), ('version', '1.0.0'), ('variant_id', 'base')])
            if rid in seen:
                raise ValueError('Duplicate received identity: ' + rid)
            seen.add(rid)
            unknown, normalizations = set(), []
            for component in original['components']:
                for ingredient in component['ingredients']:
                    literal = ingredient['name'].casefold()
                    canonical = canonicalize_ingredient_name(ingredient['name'])
                    key = canonical + '|' + ingredient['form']
                    if literal != canonical:
                        normalizations.append({'source': ingredient['name'], 'canonical': canonical})
                    if key not in vocabulary:
                        unknown.add(key)
                        blockers[key].add(rid)
            row = {'source_id': rid, 'base_id': original['base_id'], 'source_file': files[-1]['path'],
                   'unknown_ingredients': sorted(unknown), 'normalizations_to_review': normalizations}
            try:
                pack, warnings = standardize({**document, 'recipes': [original]}, vocabulary, reviewed_at='2026-11-01')
                checked = validate_pack_bytes(encoded(pack))
                if checked['rejections']:
                    raise ValueError(str(checked['rejections']))
                recipe = checked['recipes'][0]
                assert identity(recipe) == rid
                row.update(status='native_compatible_not_approved', warnings=warnings)
                known.extend(pack['recipes'])
            except ValueError as exc:
                row.update(status='blocked', reason=str(exc))
            rows.append(row)
    ranked = [{'identity': key, 'variants': len(ids), 'source_ids': sorted(ids),
               'only_register_blocker': sum(r['unknown_ingredients'] == [key] for r in rows)}
              for key, ids in blockers.items()]
    ranked.sort(key=lambda r: (-r['variants'], -r['only_register_blocker'], r['identity']))
    return {'source_files': files, 'received_variants': len(rows),
            'received_bases': len({r['base_id'] for r in rows}), 'status': dict(Counter(r['status'] for r in rows)),
            'ranked_register_blockers': ranked, 'variants': rows}, known


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report, compatible = audit(args.source, library_vocabulary(current_recipes()))
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'queue.json').write_bytes(encoded(report))
    (args.output / 'native-compatible.json').write_bytes(encoded({
        'schema_version': 'smako-meal-pack-v1', 'pack_id': 'expansion-probe-not-approved', 'recipes': compatible}))
    print({k: report[k] for k in ('received_variants', 'received_bases', 'status')})


if __name__ == '__main__':
    main()
