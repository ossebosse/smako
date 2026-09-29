"""Two reviewed declarations, opt-in only; bind to the exact reviewed offer snapshot.

This does not collect prices, activate sources, or certify a future campaign.
The registry is deliberately not loaded by production retained-facts loading.
"""

import hashlib
import json
from functools import lru_cache
from pathlib import Path

from app.services.personal_policy import ProductFacts

PATH = Path(__file__).parents[1] / "data/nutrition/reviewed-lidl-20260915.json"


@lru_cache(maxsize=1)
def declaration_version():
    return "reviewed-product-declarations:" + hashlib.sha256(PATH.read_bytes()).hexdigest()


@lru_cache(maxsize=1)
def _reviews():
    return json.loads(PATH.read_bytes())["products"]


def reviewed_facts(products):
    result = {}
    reviews = _reviews()
    for product in products:
        for row in reviews:
            provenance = product.source_provenance
            if not (
                provenance
                and provenance.source_snapshot_id == row["source_snapshot_id"]
                and product.product_id == row["product_id"]
                and product.gtin == row["gtin"]
                and product.name == row["name"]
                and product.package_quantity == float(row["quantity"])
                and product.package_unit == row["unit"]
                and product.usable_quantity == float(row["quantity"])
                and product.usable_unit == row["unit"]
                and product.chain == "lidl"
            ):
                continue
            declaration = row["declaration"]
            if (
                declaration["basis_quantity"] != 100
                or declaration["basis_unit"] != "g"
                or declaration["preparation"] != "as_sold"
            ):
                raise ValueError("Reviewed declaration must be per 100 g")
            chain = row["identity_chain"]
            if chain["method"] == "reviewed_exact_pack_artwork_and_article" and not (
                chain.get("reviewed")
                and chain.get("manufacturer_asset_sha256")
                and chain.get("retailer_asset_sha256")
                and chain.get("manufacturer_article")
            ):
                raise ValueError("Missing exact pack identity review")
            source = {
                "kind": "product_declaration",
                **{
                    key: declaration[key]
                    for key in (
                        "url",
                        "document_sha256",
                        "retrieved_at",
                        "version",
                        "edible_state",
                    )
                },
                "identity_chain": row["identity_chain"],
                "gtin": row["gtin"],
                "variant": row["variant"],
                "campaign_id": row["campaign_id"],
                "review": declaration_version(),
                "basis_quantity": 100,
                "basis_unit": "g",
                "preparation": "as_sold",
            }
            result[(product.store_id, product.product_id)] = ProductFacts(
                source="reviewed_product_declaration",
                source_product_id=product.product_id,
                source_snapshot_id=provenance.source_snapshot_id,
                retailer_product_id=product.product_id,
                ingredients_complete=True,
                ingredient_evidence_kind="product_declaration",
                ingredients=tuple(declaration["ingredients"]),
                nutrition_unit="g",
                nutrition_basis="Produktdeklaration per 100 g som såld; "
                + declaration["edible_state"],
                nutrition_preparation="as_sold",
                nutrition=declaration["nutrition"],
                observed_at=declaration["retrieved_at"],
                field_sources={
                    **{f"nutrition.{key}": (source,) for key in declaration["nutrition"]},
                    "nutrition_bounds": ({"bounds": declaration["bounds"], **source},),
                    "nutrition_preparation": (source,),
                    "ingredients": (source,),
                },
            )
    return result


def declaration_matches_product(product, fact):
    return fact == reviewed_facts([product]).get((product.store_id, product.product_id))


def is_reviewed_raw_thigh(fact):
    if not fact or fact.source != "reviewed_product_declaration":
        return False
    return any(
        row.get("edible_state") == "raw_skinless_boneless_thigh"
        and row.get("review") == declaration_version()
        for row in fact.field_sources.get("nutrition_preparation", ())
    )
