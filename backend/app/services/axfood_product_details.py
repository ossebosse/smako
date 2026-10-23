"""Ingredients and nutrition from retained Axfood product-detail documents.

Willys and Hemköp catalogue rows carry no ingredients or nutrients. The
public product detail (``/axfood/rest/p/{code}``) does. Documents fetched by
``scripts/fetch_axfood_product_details.py`` are stored as
``<root>/<chain>/<code>.json`` plus ``<code>.meta.json``. This module binds
them to already priced products by the exact retailer article code from the
product's own catalogue facts; prices are never read from a detail document.

Willys and Hemköp share Axfood's article master. A Hemköp product without its
own document may use the Willys document for the identical article code
(binding ``axfood_shared_article_code``); a stated GTIN must match either way.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import replace
from pathlib import Path

from app.services.personal_source_facts import project_raw_facts

AXFOOD_CHAINS = ("willys", "hemkop")
_DETAIL_FIELDS = ("ingredients", "nutrition_basis", "nutrition_unit", "nutrition_limits")


def configured_root():
    value = os.environ.get("AXFOOD_PRODUCT_DETAIL_ROOT")
    return Path(value) if value else None


def _document(root, chain, code):
    path = root / chain / f"{code}.json"
    meta_path = root / chain / f"{code}.meta.json"
    if not path.is_file() or not meta_path.is_file():
        return None
    payload = path.read_bytes()
    meta = json.loads(meta_path.read_bytes())
    digest = hashlib.sha256(payload).hexdigest()
    if meta.get("payload_sha256") != digest or meta.get("http_status") != 200:
        return None
    raw = json.loads(payload)
    if not isinstance(raw, dict) or str(raw.get("code")) != code:
        return None
    return raw, meta, digest


def merge_axfood_details(products, facts, root=None):
    """Add detail ingredients/nutrition to Willys/Hemköp facts in place.

    Returns counters. Catalogue facts keep their organic/label evidence;
    existing declarations are not overwritten.
    """
    root = Path(root) if root else configured_root()
    stats = {"products": 0, "own_document": 0, "shared_document": 0, "gtin_mismatch": 0, "no_document": 0}
    if root is None or not root.is_dir():
        return stats
    for product in products:
        if product.chain not in AXFOOD_CHAINS or not product.source_provenance:
            continue
        key = (product.store_id, product.product_id)
        fact = facts.get(key)
        code = getattr(fact, "retailer_product_id", None) if fact else None
        if not code:
            continue
        stats["products"] += 1
        found = _document(root, product.chain, code)
        binding = "exact_retailer_article_code"
        if found is None and product.chain == "hemkop":
            found = _document(root, "willys", code)
            binding = "axfood_shared_article_code"
        if found is None:
            stats["no_document"] += 1
            continue
        raw, meta, digest = found
        gtin = getattr(product, "gtin", None)
        if gtin and str(raw.get("ean") or "").lstrip("0") != str(gtin).lstrip("0"):
            stats["gtin_mismatch"] += 1
            continue
        stats["own_document" if binding.startswith("exact") else "shared_document"] += 1
        source = f"{meta['chain']}:product_detail:{code}:{digest}"
        detail = project_raw_facts(raw, chain=product.chain, product_id=product.product_id,
                                   snapshot_id=product.source_provenance.source_snapshot_id,
                                   source_reference=source, observed_at=meta.get("fetched_at"))
        provenance = {"binding": binding, "document_chain": meta["chain"], "document_url": meta.get("url"),
                      "payload_sha256": digest, "fetched_at": meta.get("fetched_at")}
        sources = {k: tuple({**e, **provenance} for e in v) for k, v in detail.field_sources.items()
                   if k in _DETAIL_FIELDS or k.startswith("nutrition.") or k == "animal"}
        changes = {}
        if detail.ingredients and not fact.ingredients:
            changes["ingredients"] = detail.ingredients
        if detail.nutrition and not fact.nutrition:
            changes.update(nutrition=detail.nutrition, nutrition_unit=detail.nutrition_unit,
                           nutrition_basis=detail.nutrition_basis,
                           nutrition_preparation=detail.nutrition_preparation)
        if fact.animal is None and detail.animal is not None:
            changes["animal"] = detail.animal
        kept = {k: v for k, v in sources.items()
                if (k == "ingredients" and "ingredients" in changes)
                or (k.startswith("nutrition") and "nutrition" in changes)
                or (k == "animal" and "animal" in changes)}
        if not changes and not detail.conflicts:
            continue
        nutrient_conflicts = tuple(c for c in detail.conflicts if c.startswith("nutrition")) if "nutrition" in changes else ()
        facts[key] = replace(fact, **changes, field_sources={**fact.field_sources, **kept},
                             conflicts=tuple(dict.fromkeys((*fact.conflicts, *nutrient_conflicts,
                                                            *(c for c in detail.conflicts if not c.startswith("nutrition"))))))
    return stats
