"""Re-derive a frozen review data folder with retained Axfood details and egg mass proofs.

The frozen exports hold facts as the server derived them at export time.
This writes a NEW folder (never in place) whose combined-facts.json and
product-facts.json add what the current load path would add: Axfood product
details (merge_axfood_details) and shell-egg usable-mass proofs. Prices,
request and clock are copied byte for byte; matrix-inputs.json gets the new
facts hash.

    python backend/scripts/augment_review_facts.py --inputs <data/lund> \
        --details .local/axfood-details --output <data/lund-axfood>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from dataclasses import asdict
from pathlib import Path

from app.services.axfood_product_details import merge_axfood_details
from app.services.official_product_facts import shell_egg_quantity_proofs
from app.services.personal_policy import ProductFacts
from app.services.personal_source_facts import FactsCollection
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact


def _augment(products, facts, details):
    stats = merge_axfood_details(products, facts, details) if details else {}
    shell_egg_quantity_proofs(products, facts)
    return FactsCollection(facts), stats


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--inputs", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--details", type=Path, help="Root with <chain>/<code>.json Axfood documents")
    args = p.parse_args()
    if args.output.exists():
        p.error(f"{args.output} exists; choose a new folder")
    manifest = json.loads((args.inputs / "matrix-inputs.json").read_bytes())
    prices = (args.inputs / "combined-prices.json").read_bytes()
    assert hashlib.sha256(prices).hexdigest() == manifest["sha256"]["combined-prices.json"]
    products = PreparedPriceUniverseArtifact.model_validate_json(prices).restore().universe.products
    args.output.mkdir(parents=True)
    report = {}
    combined = json.loads((args.inputs / "combined-facts.json").read_bytes())
    facts, report["combined"] = _augment(products, {tuple(k): ProductFacts(**v) for k, v in combined["facts"]},
                                         args.details)
    body = json.dumps({"facts_version": facts.version,
                       "facts": [[list(k), asdict(v)] for k, v in sorted(facts.items())]},
                      ensure_ascii=False).encode()
    (args.output / "combined-facts.json").write_bytes(body)
    rows = json.loads((args.inputs / "product-facts.json").read_bytes())
    exported, report["product_facts"] = _augment(
        products, {(r["store_id"], r["product_id"]): ProductFacts(**r["facts"]) for r in rows["rows"]}, args.details)
    (args.output / "product-facts.json").write_text(json.dumps({"facts_version": exported.version, "rows": [
        {"store_id": k[0], "product_id": k[1], "facts": asdict(v)} for k, v in sorted(exported.items())]},
        ensure_ascii=False), encoding="utf-8")
    for name in ("combined-prices.json", "combined-request.json"):
        shutil.copyfile(args.inputs / name, args.output / name)
    manifest["sha256"]["combined-facts.json"] = hashlib.sha256(body).hexdigest()
    manifest["derived_from"] = {"inputs": str(args.inputs), "details": str(args.details) if args.details else None,
                                "stats": report}
    (args.output / "matrix-inputs.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
