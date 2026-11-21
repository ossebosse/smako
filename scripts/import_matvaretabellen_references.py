"""Import explicit Matvaretabellen foods for reviewed offline use; never invoked by planning.

Usage: python scripts/import_matvaretabellen_references.py --output path.json
Retains food IDs, the published portion weight of one decilitre (used as a
food-specific density estimate), macros per 100 g and the edible part, with
the URL, retrieval time and raw response hash. An import supplies data only:
a separate reviewed mapping must qualify its use.
"""
import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

URL = 'https://www.matvaretabellen.no/api/nb/foods.json'
# Owner request 2026-11-21: volume-to-mass for liquids sold by volume, and a
# butternut reference (Livsmedelsverket has only Cucurbita maxima).
DENSITY = {
    'grädde': '01.015',            # Kremfløte, 37 % fett
    'mjölk': '01.231',             # Lettmelk, 0,5 % fett
    'sojasås': '10.126',           # Soyasaus
    'ättiksprit 12 procent': '12.027',  # Eddik, 7 %
    'äppelcidervinäger': '10.178',  # Eplecidereddik
    'olivolja': '08.112',          # Olivenolje, extra virgin
}
NUTRITION = {'butternutpumpa': '06.210'}  # Gresskar, butternut, rå
MACROS = {'Protein': 'protein_g', 'Fett': 'fat_g', 'Karbo': 'carbs_g'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit('Refusing to replace a retained reference version. Choose a new path.')
    response = httpx.get(URL, timeout=120, follow_redirects=True)
    response.raise_for_status()
    acquisition = {'url': str(response.url), 'status': response.status_code,
                   'sha256': hashlib.sha256(response.content).hexdigest(),
                   'observed_at': datetime.now(UTC).isoformat()}
    foods = {f['foodId']: f for f in response.json()['foods']}
    result = {'attribution': 'Matvaretabellen 2026. Mattilsynet. www.matvaretabellen.no',
              'license_url': 'https://www.mattilsynet.no/mat-og-drikke/matvaretabellen/opphavsrett',
              'acquisition': acquisition, 'density': {}, 'foods': {}}
    for name, food_id in DENSITY.items():
        food = foods[food_id]
        (dl,) = [p for p in food['portions'] if p['id'] == 'dl' and p['unit'] == 'g']
        result['density'][name] = {'food_id': food_id, 'description': food['foodName'],
            'source_url': food.get('uri') or URL,
            'portion': dl, 'value': dl['quantity'] / 100, 'unit': 'g/ml',
            'basis': 'published household portion weight of 1 dl; rounded, estimate'}
    for name, food_id in NUTRITION.items():
        food = foods[food_id]
        values = {MACROS[c['nutrientId']]: c['quantity'] for c in food['constituents'] if c.get('nutrientId') in MACROS}
        values['kcal'] = food['calories']['quantity']
        result['foods'][name] = {'food_id': food_id, 'description': food['foodName'], 'latin_name': food.get('latinName'),
            'nutrition': values, 'unit': 'g', 'basis_quantity': 100,
            'original_values': {'calories': food['calories'],
                                **{c['nutrientId']: c for c in food['constituents'] if c.get('nutrientId') in MACROS}},
            'source_url': food.get('uri') or URL}
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v['value'] for k, v in result['density'].items()}, ensure_ascii=False))


if __name__ == '__main__':
    main()
