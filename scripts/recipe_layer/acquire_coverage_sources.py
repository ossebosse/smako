"""Acquire an explicit public supplier-document list, never store prices.

Use budgeted_check. Immutable prior acquisitions are not overwritten. Raw files
stay local; only source hashes and reviewed normalized declarations enter Git.
"""
import argparse
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

from grocery_data.app.services.product_declarations import parse_dabas


def main(args):
    queue = json.loads(args.queue.read_bytes())
    args.output.mkdir(parents=True, exist_ok=True)
    outcomes = []
    with httpx.Client(timeout=15, follow_redirects=True) as client:
        for item in queue:
            key = item.get('gtin') or item['kind']
            target = args.output / (key + '.json')
            if target.exists():
                raise ValueError('Acquisition already exists; review/reuse instead of overwriting: ' + key)
            source = {'url': item['url'], 'observed_at': datetime.now(UTC).isoformat()}
            outcome = {'item': item, 'source': source}
            try:
                response = client.get(item['url'])
                body = response.content
                source.update(status=response.status_code, sha256=hashlib.sha256(body).hexdigest())
                raw = args.output / (key + ('.html' if item['kind'] == 'dabas' else '.' + item.get('format', 'pdf')))
                raw.write_bytes(body)
                source['local_copy'] = raw.as_posix()
                response.raise_for_status()
                if item['kind'] == 'dabas':
                    outcome['declaration'] = parse_dabas(body, source)
                outcome['status'] = 'acquired'
            except (httpx.HTTPError, ValueError) as error:
                outcome.update(status='failed', reason=str(error))
            target.write_text(json.dumps(outcome, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
            outcomes.append(outcome)
            print(key, outcome['status'], source.get('status'), flush=True)
            time.sleep(1)
    (args.output / 'index.json').write_text(json.dumps(outcomes, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--queue', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    main(p.parse_args())
