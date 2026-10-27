"""Read-only retrieval for review, including negative/source needs; never approval.

Run through budgeted_check. Uses retained snapshots and existing article codes.
The optional detail queue is limited to the declared Willys store, exact whole
labels and existing catalogue codes, and still needs the normal collector lease.
"""
import argparse
import json
import re
from dataclasses import asdict
from pathlib import Path

from app.services.ingredient_normalizer import _search_text
from app.services.intake_product_links import entries
from coverage_reference import digest, file_sha, load_reference


def main(args):
    prepared, facts, _references, _recipes, scope = load_reference(args)
    groups = {row['name'] for row in entries().values() if row['kind'] == 'definition_only'}
    groups |= {'limejuice', 'keso', 'kvarg', 'kapris'}
    rows = {name: [] for name in sorted(groups)}
    tokens = {name: _search_text(name).split() for name in groups}
    print({'loaded': len(prepared.universe.products)}, flush=True)
    # Retrieval is deliberately broad. A later human/code review must approve
    # identity, form and quantity separately; a search hit is never evidence.
    for p in prepared.universe.products:
        text = _search_text(p.name)
        for name in groups:
            terms = tokens[name]
            if not all(t in text for t in terms):
                continue
            f = facts.get((p.store_id, p.product_id))
            if not f or not p.source_provenance or f.source_product_id != p.product_id or f.source_snapshot_id != p.source_provenance.source_snapshot_id:
                f = None
            rows[name].append({'product': p.model_dump(mode='json'), 'facts': asdict(f) if f else None})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({'scope': scope, 'groups': rows}, ensure_ascii=False), encoding='utf-8')
    if args.queue:
        labels = r'(?:(?:limejuice|lime juice)(?: eko)?|(?:keso(?: cottage cheese)?|cottage cheese)(?: (?:mini|laktosfri|naturell|eko|ekologisk|[0-9.,]+%))*|(?:laktosfri )?(?:mild )?kvarg (?:mild )?naturell(?: (?:eko|ekologisk|[0-9.,]+%))*|kapris(?: sma|fina| fin| i lag)*|tamarindpaste sour concentrate|mynta klass 1)'
        codes = {}
        for name in ['limejuice', 'keso', 'kvarg', 'kapris', 'tamarindpasta', 'mynta']:
            for row in rows[name]:
                p, f = row['product'], row['facts'] or {}
                if p['chain'] != 'willys' or not re.fullmatch(labels, _search_text(p['name'])):
                    continue
                code = f.get('retailer_product_id') or (p['source_provenance'] or {}).get('retailer_product_id')
                if code:
                    codes.setdefault(code, []).append({'store_id': p['store_id'], 'product_id': p['product_id'], 'name': p['name'],
                                                       'snapshot': p['source_provenance']['source_snapshot_id']})
        body = ''.join(code + '\n' for code in codes).encode()
        args.queue.write_bytes(body)
        prior = json.loads(args.catalog_proof.read_bytes())
        prior.update(codes_sha256=file_sha(args.queue), count=len(codes),
                     selection={'method': 'reviewed exact labels, existing article master only',
                                'universe_sha256': scope['universe_sha256'], 'products': codes,
                                'source_catalog_proof_sha256': file_sha(args.catalog_proof)})
        args.queue.with_suffix('.proof.json').write_text(json.dumps(prior, ensure_ascii=False, indent=2), encoding='utf-8')
    print({'groups': len(rows), 'products': sum(map(len, rows.values())), 'queue': len(codes) if args.queue else 0,
           'scope': digest(scope)}, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['universe', 'facts', 'output']:
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--clock', required=True)
    p.add_argument('--queue', type=Path)
    p.add_argument('--catalog-proof', type=Path)
    main(p.parse_args())
