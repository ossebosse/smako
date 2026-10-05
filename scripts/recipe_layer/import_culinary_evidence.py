"""Import a retained, hash-verified manufacturer attribute; no network or prices."""
import argparse
import json
from pathlib import Path

from grocery_data.app.services.product_declarations import PATH, parse_santa_maria_culinary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('raw', type=Path)
    parser.add_argument('acquisition', type=Path)
    parser.add_argument('--registry', type=Path, default=PATH)
    args = parser.parse_args()
    row = parse_santa_maria_culinary(args.raw.read_bytes(), json.loads(args.acquisition.read_bytes()))
    content = json.loads(args.registry.read_bytes())
    rows = content.setdefault('culinary_declarations', [])
    if row not in rows:
        # A changed source is not permission to overwrite historical evidence.
        # Ambiguous duplicate identities are rejected by the ordinary binder.
        rows.append(row)
    args.registry.write_text(json.dumps(content, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'imported_source': row['source'], 'attributes': row['culinary_forms']}))


if __name__ == '__main__':
    main()
