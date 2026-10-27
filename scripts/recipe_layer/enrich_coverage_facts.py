"""Version retained facts with a reviewed existing Axfood archive; no pricing I/O."""
import argparse
import json
from dataclasses import asdict
from pathlib import Path

from app.services.axfood_product_details import merge_axfood_details
from app.services.official_product_facts import supplement_catalog_facts
from coverage_reference import digest, file_sha, load_reference


def main(args):
    prepared, facts, _references, _recipes, scope = load_reference(args)
    codes = set(args.codes.read_text().splitlines())
    selected = [p for p in prepared.universe.products
                if getattr(facts.get((p.store_id, p.product_id)), 'retailer_product_id', None) in codes]
    before = {k: digest(asdict(v)) for k, v in facts.items()}
    stats = merge_axfood_details(selected, facts, args.archive)
    for key, value in supplement_catalog_facts(selected, facts).items():
        facts[key] = value
    changes = [{'store_id': k[0], 'product_id': k[1], 'before_sha256': before.get(k),
                'after_sha256': digest(asdict(v)), 'conflicts': list(v.conflicts)}
               for k, v in facts.items() if before.get(k) != digest(asdict(v))]
    version = facts.version + ':recipe-coverage-20261027:' + digest(changes)
    args.output.write_text(json.dumps({'facts_version': version, 'facts': [[k, asdict(v)] for k, v in facts.items()]},
                                    ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    args.report.write_text(json.dumps({'before_scope': scope, 'after_facts_sha256': file_sha(args.output),
        'after_facts_version': version, 'archive': args.archive.as_posix(),
        'archive_manifest_sha256': file_sha(args.archive / 'manifest.json'), 'stats': stats,
        'changed_products': changes}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print({'selected': len(selected), 'changed': len(changes), 'stats': stats}, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['universe', 'facts', 'output', 'codes', 'archive', 'report']:
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--clock', required=True)
    main(p.parse_args())
