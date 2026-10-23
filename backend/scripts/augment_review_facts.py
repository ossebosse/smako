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
import tempfile
from dataclasses import asdict
from pathlib import Path

from app.services.axfood_product_details import merge_axfood_details
from app.services.official_product_facts import shell_egg_quantity_proofs
from app.services.personal_policy import ProductFacts
from app.services.personal_source_facts import FactsCollection
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact

from grocery_data.app.services.axfood_detail_archive import verify_release


def _augment(products, facts, details):
    stats = merge_axfood_details(products, facts, details) if details else {}
    shell_egg_quantity_proofs(products, facts)
    manifests = ()
    if details:
        from grocery_data.app.services import axfood_detail_archive
        manifests = (Path(details).resolve().name, axfood_detail_archive.VERSION,
                     hashlib.sha256(Path(axfood_detail_archive.__file__).read_bytes()).hexdigest())
    return FactsCollection(facts, source_manifests=manifests), stats


def augment(inputs, output, details=None):
    """Verify every input before reading models; publish one complete new folder."""
    inputs, output = Path(inputs).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError("Output exists; choose a new folder")
    if details is not None:
        verify_release(details)
    manifest = json.loads((inputs / "matrix-inputs.json").read_bytes())
    required = {"combined-prices.json", "combined-facts.json", "combined-request.json"}
    if (inputs / "product-facts.json").exists():
        required.add("product-facts.json")
    if not required <= manifest["sha256"].keys():
        raise ValueError("Consumed inputs must all have manifest hashes")
    verified = {}
    for name, digest in manifest["sha256"].items():
        if not isinstance(name, str) or Path(name).name != name or name == "matrix-inputs.json":
            raise ValueError("Unsafe manifest filename")
        path = inputs / name
        if not path.resolve().is_relative_to(inputs):
            raise ValueError("Input leaves evidence folder")
        body = path.read_bytes()
        if hashlib.sha256(body).hexdigest() != digest:
            raise ValueError(f"Input hash mismatch: {name}")
        verified[name] = body
    prices = verified["combined-prices.json"]
    products = PreparedPriceUniverseArtifact.model_validate_json(prices).restore().universe.products
    report = {}
    combined = json.loads(verified["combined-facts.json"])
    facts, report["combined"] = _augment(products, {tuple(k): ProductFacts(**v) for k, v in combined["facts"]},
                                         details)
    body = json.dumps({"facts_version": facts.version,
                       "source_manifests": facts.source_manifests,
                       "facts": [[list(k), asdict(v)] for k, v in sorted(facts.items())]},
                      ensure_ascii=False).encode()
    verified["combined-facts.json"] = body
    if "product-facts.json" in verified:
        rows = json.loads(verified["product-facts.json"])
        exported, report["product_facts"] = _augment(
            products, {(r["store_id"], r["product_id"]): ProductFacts(**r["facts"]) for r in rows["rows"]}, details)
        verified["product-facts.json"] = json.dumps({"facts_version": exported.version,
            "source_manifests": exported.source_manifests, "rows": [
            {"store_id": k[0], "product_id": k[1], "facts": asdict(v)} for k, v in sorted(exported.items())]},
            ensure_ascii=False).encode()
    manifest["sha256"] = {name: hashlib.sha256(data).hexdigest() for name, data in verified.items()}
    manifest["derived_from"] = {"inputs": str(inputs), "details": str(details) if details else None,
                                "stats": report}
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".augment-", dir=output.parent))
    try:
        for name, data in verified.items():
            (staging / name).write_bytes(data)
        (staging / "matrix-inputs.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        staging.rename(output)
    finally:
        # Only this invocation's exact disposable staging directory.
        if staging.exists():
            shutil.rmtree(staging)
    return report


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--inputs", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--details", type=Path, help="Immutable release with <chain>/<code>.json")
    args = p.parse_args()
    report = augment(args.inputs, args.output, args.details)
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
