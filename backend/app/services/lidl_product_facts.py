"""Exact supplier GTIN/variant/pack declaration; no image or price inference."""
import hashlib
import json
from pathlib import Path

from app.services.declaration_semantics import document_classification
from app.services.personal_policy import ProductFacts

PATH = Path(__file__).parents[1] / "data/nutrition/lidl-lingongrova-20260923.json"


def reviewed_facts(products):
    products = [p for p in products if p.chain == "lidl"]
    if not products:
        return {}
    row = json.loads(PATH.read_bytes())
    result = {}
    for product in products:
        prov = product.source_provenance
        if (product.chain != "lidl" or not prov or not prov.source_snapshot_id
                or prov.retailer_id_namespace != "lidl:public-product"
                or prov.retailer_product_id != row["retailer_product_id"]
                or product.gtin != row["gtin"] or product.name != row["name"]
                or product.brand != row["brand"] or product.package_quantity != row["package_quantity"]
                or product.package_unit != row["package_unit"]
                or product.usable_quantity != row["package_quantity"] or product.usable_unit != row["package_unit"]
                # Supplier facts describe a stable exact GTIN/variant/package,
                # not a campaign's price. A new independently qualified source
                # may reuse the declaration, retaining its real observation.
                or not any(o.price_contract_id
                           and o.price_contract_id.startswith('lidl:household:')
                           and o.price_contract_id.endswith(':' + row['retailer_product_id'])
                           and o.campaign_evidence and o.campaign_evidence.store_external_id == prov.provider_store_id
                           and o.campaign_evidence.offer_id == row['retailer_product_id']
                           for o in product.offers)):
            continue
        source = {"kind": "product_declaration", "url": row["source"]["url"],
            "document_sha256": row["source"]["document_sha256"], "retrieved_at": row["source"]["observed_at"],
            "version": row["document_version"], "gtin": row["supplier_gtin"],
            "identity_method": "exact_checksum_gtin_name_brand_fixed_pack",
            "review_sha256": hashlib.sha256(PATH.read_bytes()).hexdigest(),
            "basis_quantity": 100, "basis_unit": "g", "preparation": "as_sold"}
        result[(product.store_id, product.product_id)] = ProductFacts(
            source="verified_lidl_supplier_declaration", source_product_id=product.product_id,
            source_snapshot_id=prov.source_snapshot_id, retailer_product_id=prov.retailer_product_id,
            ingredients_complete=True, ingredient_evidence_kind="product_declaration",
            product_classification=document_classification(row['source'].get('text', '')),
            ingredients=tuple(row["ingredients"]), nutrition=row["nutrition"], nutrition_unit="g",
            nutrition_basis="Pågen LingonGrova 500 g; deklarerat per 100 g som såld",
            nutrition_preparation="as_sold", observed_at=row["source"]["observed_at"],
            field_sources={**{f"nutrition.{k}": (source,) for k in row["nutrition"]},
                           "ingredients": (source,), "nutrition_preparation": (source,),
                           "product_classification": (source,)})
    return result


def declaration_matches_product(product, fact):
    return fact == reviewed_facts([product]).get((product.store_id, product.product_id))
