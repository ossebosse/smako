"""Bounded retained-catalogue retrieval for every remaining ingredient group.

Aliases find review candidates, never authorize identity, quantity or prices.
Run with budgeted_check; no remote collection or activation is performed.
"""
import argparse
import json
import re
from dataclasses import asdict
from pathlib import Path

from app.services.ingredient_normalizer import _search_text
from coverage_reference import load_reference
from full_coverage_worklist import NOTES

from grocery_data.app.services.axfood_detail_archive import read_document, verify_release

ALIASES = {
    'tamarindpasta': r'tamarind', 'masa harina': r'harina|maseca|minsa|nixtamal|majsmjol',
    'nötkött': r'notkott|biff|innanlar|hogrev|entrecote|fransyska|notstek|ryggbit|rostas|oxfile|flankstek|ytterlar|notrulle',
    'pärlkorn': r'parlkorn|matkorn|korngryn|barley', 'klibbigt ris': r'klibb|sticky|glutin|sushi',
    'bambuskott': r'bambusk|bamboo', 'tapiokastärkelse': r'tapiok|tapioc|cassava',
    'äggula': r'agg', 'äggvita': r'agg', 'rimmat fläsk': r'flask|bacon',
    'klibbigt rismjöl': r'rismjol|glutin|rice flour', 'tapiokapärlor': r'tapiok|tapioc',
    'breda risnudlar': r'risnud|rice noodle|pad thai', 'rispapper': r'rispapp|rice paper|varrull',
    'uradlinser': r'urad|black gram|vigna mungo', 'bittergurka': r'bitter|karela',
    'chana dal': r'chana|dal|kikart', 'gröna mungbönor': r'mung',
    'vattenkastanjer': r'vattenkastanj|water chestnut', 'silkestofu': r'tofu|silken',
    'fläsklever': r'lever', 'fläsksida med svål': r'flask|pork belly',
    'fjälster': r'fjalster|fjaster|hogtarm|svintarm', 'groddade mungbönor': r'grodd',
    'kalvlägg med ben': r'kalv|ossobuc', 'kokta ägg': r'agg',
    'matbanan': r'matbanan|kokbanan|plantain', 'mungbönsstärkelse': r'mung|glasnud',
    'risvermicelli': r'risnud|vermicelli', 'runda risnudlar': r'risnud|rice noodle',
    'råa räkor': r'rakor|scampi|vannamei', 'sattu': r'sattu|kikartsmjol|gram flour',
    'svart te': r'svart te|ceylon|assam|breakfast|darjeeling|loose leaf',
    'svarta linser': r'linser|beluga', 'vegansk smördeg': r'smordeg|puff pastry',
    'vetegluten': r'vetegluten|vital.*gluten|seitan', 'edamame i balja': r'edamame|sojabon',
    'grapefrukt': r'grapefrukt|grapefruit|grape ', 'grön matbanan': r'matbanan|kokbanan|plantain',
    'hirs': r'hirs|millet', 'kastanjer': r'kastanj|chestnut', 'majskolv': r'majskolv|corn.*cob',
    'popcornmajs': r'popcorn', 'psylliumfröskal': r'psyllium|fiberhusk|husk',
    'risflingor': r'risfling|poha|rice flake', 'rökt makrill': r'makrill',
    'vattenmelon': r'vattenmelon|watermelon',
}


def main(args):
    prepared, facts, _refs, _recipes, scope = load_reference(args)
    patterns = {name: re.compile(ALIASES.get(name, _search_text(name))) for name in NOTES}
    groups = {name: [] for name in patterns}
    for p in prepared.universe.products:
        text = _search_text(p.name)
        for name, pattern in patterns.items():
            if pattern.search(text):
                f = facts.get((p.store_id, p.product_id))
                if f and (not p.source_provenance or f.source_snapshot_id != p.source_provenance.source_snapshot_id
                          or f.source_product_id != p.product_id):
                    f = None
                groups[name].append({'product': p.model_dump(mode='json'), 'facts': asdict(f) if f else None})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({'scope': scope, 'groups': groups}, ensure_ascii=False), encoding='utf-8')
    manifest = verify_release(args.archive)
    retained = {}
    for rows in groups.values():
        for row in rows:
            p, f = row['product'], row['facts'] or {}
            code = f.get('retailer_product_id') or (p.get('source_provenance') or {}).get('retailer_product_id')
            if p['chain'] not in {'willys', 'hemkop'} or not code:
                continue
            key = p['chain'] + ':' + code
            if key in retained:
                continue
            doc = read_document(args.archive, p['chain'], code, manifest=manifest)
            retained[key] = {'status': doc.status, 'raw': doc.raw if doc.status == 'verified' else None}
    args.output.with_suffix('.details.json').write_text(json.dumps(retained, ensure_ascii=False), encoding='utf-8')
    print({'groups': len(groups), 'retained_articles': len(retained),
           'verified_documents': sum(r['status'] == 'verified' for r in retained.values())}, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['universe', 'facts', 'output', 'archive']:
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--clock', required=True)
    main(p.parse_args())
