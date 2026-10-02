"""Import explicit SLV food IDs for reviewed offline use; never invoked by planning.

Usage: python scripts/import_slv_references.py --output path.json 362 372
Retains source IDs, food versions, URLs, retrieval times and raw response hashes.
An import supplies data only: a separate reviewed mapping must qualify its use.
"""
import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

BASE = 'https://dataportal.livsmedelsverket.se/livsmedel'


def acquire(client, url):
    response = client.get(url)
    response.raise_for_status()
    return response.json(), {'url': str(response.url), 'sha256': hashlib.sha256(response.content).hexdigest(),
                             'observed_at': datetime.now(UTC).isoformat(), 'status': response.status_code}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('food_ids', nargs='+', type=int)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit('Refusing to replace a retained reference version. Choose a new path.')
    result = {'source': 'Livsmedelsverkets Livsmedelsdatabas', 'source_url': BASE,
              'license': 'https://creativecommons.org/licenses/by/4.0/deed.sv',
              'retrieved_at': datetime.now(UTC).isoformat(), 'foods': {}}
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        for identity in sorted(set(args.food_ids)):
            food, acquisition = acquire(client, f'{BASE}/api/v1/livsmedel/{identity}?sprak=1')
            assert food['nummer'] == identity and food['version']
            link = next(x['href'] for x in food['links'] if x['rel'] == 'naringvarden')
            nutrients, nutrient_acquisition = acquire(client, BASE + link)
            result['foods'][str(identity)] = {'food': food, 'nutrients': nutrients,
                'source_url': acquisition['url'], 'retrieved_at': acquisition['observed_at'],
                'acquisition': [acquisition, nutrient_acquisition]}
            print(f'{identity}: {food["namn"]}', flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
