"""Small reviewed source-backed ingredient overlay, applied before planning.

No product-name inference, GTIN fabrication, pricing or consumer network I/O.
Only exact retailer identity and compatible package/variant qualify. Ordinary
ingredient review never populates allergen absence or trace-check fields.
"""

import hashlib
import json
from dataclasses import replace
from datetime import datetime
from functools import lru_cache
from pathlib import Path

PATH = Path(__file__).parents[1] / "data/ingredients/reviewed-20260913.json"


@lru_cache(maxsize=1)
def reviews():
    document = json.loads(PATH.read_bytes())
    for row in document["products"]:
        assert hashlib.sha256(row["source_payload"].encode()).hexdigest() == row["sha256"]
        raw = json.loads(row["source_payload"])
        assert str(raw.get("code") or raw.get("id")) == row["retailer_product_id"]
        assert row["kind"] in {"reviewed_declaration", "reviewed_single_unprocessed_crop"}
        if row["kind"] == "reviewed_declaration":
            assert raw[row["field"]] == row["declaration"] and row["declaration"].strip()
        else:
            # Explicit individually reviewed whole-crop evidence. An empty
            # declaration, category or product name alone NEVER qualifies.
            assert row["single_ingredient"] in {"morot", "tomat"}
            assert raw["description"] == row["description"] and row["description"]
            assert row["category"] in {c.get("categoryCode") for c in raw["breadcrumbs"]}
            assert row["review_rationale"]
    return document["products"]


def enrich_ingredients(prepared, original):
    result = dict(original)
    by_id = {(r["chain"], r["retailer_product_id"]): r for r in reviews()}
    for p in prepared.universe.products:
        key = (p.store_id, p.product_id)
        fact = result.get(key)
        if not fact or not p.source_provenance:
            continue
        row = by_id.get((p.chain, fact.retailer_product_id))
        if not row or p.name != row["name"]:
            continue
        if row.get("package_quantity") is not None and (
            p.package_quantity != row["package_quantity"] or p.package_unit != row["package_unit"]
        ):
            continue
        if row.get("brand") and p.brand and p.brand.casefold() != row["brand"].casefold():
            continue
        if set(fact.conflicts) & {"ingredients", "identity_variant"}:
            continue
        if row["chain"] == "coop":
            # The approved retained declaration must still be exactly present.
            if tuple(fact.ingredients) != (row["declaration"],):
                continue
        else:
            observed = p.source_provenance.source_observed_at
            if (
                abs((observed - datetime.fromisoformat(row["observed_at"])).total_seconds())
                > 7 * 86400
            ):
                continue
        declaration = row.get("declaration") or row["single_ingredient"]
        if fact.ingredients and tuple(fact.ingredients) != (declaration,):
            continue
        evidence = {
            "source": row["source"],
            "source_product_id": row["retailer_product_id"],
            "sha256": row["sha256"],
            "observed_at": row["observed_at"],
            "field": row["field"],
            "kind": row["kind"],
            "review": "ingredient-review-20260913",
            "allergen_absence_checked": False,
            "review_rationale": row.get("review_rationale"),
        }
        result[key] = replace(
            fact,
            ingredients=(declaration,),
            ingredients_complete=True,
            ingredient_evidence_kind=row["kind"],
            field_sources={**fact.field_sources, "ingredients": (evidence,)},
            conflicts=tuple(sorted(set(fact.conflicts) | set(row.get("reference_conflicts", [])))),
        )
    return result
