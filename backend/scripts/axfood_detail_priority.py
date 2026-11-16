"""Order Willys/Hemköp detail codes by what the recipe library needs.

Reads a prepared PriceUniverse artifact and its facts; starts no requests.
Writes one code per line for each chain: recipe-candidate products without a
declaration first, most-used ingredients first. Hemköp shares Axfood's article
master, so a Hemköp code already queued for Willys is left out (the reader
binds it with ``axfood_shared_article_code``). Pass a file to
``scripts/fetch_axfood_product_details.py --priority-codes``; the approved
catalogue queue and its proof stay exactly the same, only the order changes.

    python backend/scripts/axfood_detail_priority.py --universe universe.json \
        [--facts facts.json] --output-dir priority/
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT)]


def needs_declaration(fact) -> bool:
    return fact is None or not fact.nutrition or not fact.ingredients


def priority_codes(prepared, facts, recipes):
    from app.services.ingredient_normalizer import canonicalize_ingredient_name as canon
    from app.services.meal_prepared_artifacts import ingredient_search_positions

    uses = Counter(canon(i.canonical_name or i.name) for r in recipes for i in r.ingredients)
    index = {e.key: e.product_indexes for e in prepared.universe.indexes.canonical}
    products = prepared.universe.products
    weight = defaultdict(Counter)
    for name, count in uses.items():
        positions = set(index.get(name, ())) | set(ingredient_search_positions(prepared, name, complete=True))
        for position in positions:
            product = products[position]
            if product.chain not in {"willys", "hemkop"}:
                continue
            fact = facts.get((product.store_id, product.product_id))
            code = getattr(fact, "retailer_product_id", None) if fact else None
            if code and needs_declaration(fact):
                weight[product.chain][code] += count
    ordered = {chain: [code for code, _ in sorted(codes.items(), key=lambda item: (-item[1], item[0]))]
               for chain, codes in weight.items()}
    willys = set(ordered.get("willys", ()))
    ordered["hemkop"] = [code for code in ordered.get("hemkop", ()) if code not in willys]
    return ordered


def _facts(prepared, path):
    from app.services.personal_policy import ProductFacts
    from app.services.personal_source_facts import FactsCollection, load_retained_facts

    if path is None:
        return load_retained_facts(prepared)
    document = json.loads(path.read_bytes())
    rows = document["facts"]
    return FactsCollection({tuple(key): ProductFacts(**value) for key, value in rows})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--facts", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
    from app.services.recipe_library import current_recipes

    prepared = PreparedPriceUniverseArtifact.from_file(args.universe).restore()
    ordered = priority_codes(prepared, _facts(prepared, args.facts), current_recipes(None))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary = {}
    for chain in ("willys", "hemkop"):
        codes = ordered.get(chain, [])
        (args.output_dir / f"priority-{chain}.txt").write_text(
            "".join(code + "\n" for code in codes), encoding="utf-8")
        summary[chain] = len(codes)
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
