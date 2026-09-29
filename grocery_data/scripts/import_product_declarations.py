"""Import retained official declaration pages, without prices or campaign IDs."""
import argparse
import json
from pathlib import Path

from grocery_data.app.services.product_declarations import parse_declaration


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    rows = []
    for item in json.loads(args.manifest.read_bytes()):
        acquisition = json.loads(Path(item['acquisition']).read_bytes())
        row = parse_declaration(Path(item['document']).read_bytes(), acquisition)
        if any(r['gtin'] == row['gtin'] for r in rows):
            raise ValueError('duplicate declaration: explicit version resolution required')
        rows.append(row)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({'schema': 'official-product-declarations-v1',
        'declarations': rows}, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
