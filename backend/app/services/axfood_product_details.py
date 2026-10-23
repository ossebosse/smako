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
import math
import os
import re
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

from app.services.personal_source_facts import project_raw_facts

from grocery_data.app.services.axfood_detail_archive import (
    VERSION,
    read_document,
    same_gtin,
    verify_release,
)

AXFOOD_CHAINS = ("willys", "hemkop")
_DETAIL_FIELDS = ("ingredients", "nutrition_basis", "nutrition_unit", "nutrition_limits")


def _nutrition_basis_identity(fact):
    """Recognize the two existing projectors' per-100-unit representations.

    ProductFacts values are normalized per 100 g/ml. The human-readable source
    label is provenance, not a different nutrient denominator. Unknown formats
    remain literal; units, preparation and every overlapping value still agree
    exactly before declarations can supplement each other.
    """
    basis = fact.nutrition_basis
    if not isinstance(basis, str) or fact.nutrition_unit not in {"g", "ml"}:
        return basis
    unit = fact.nutrition_unit
    label = " ".join(basis.casefold().split())
    official = (fact.nutrition_preparation == "as_sold"
                and label == f"officiell produktdeklaration per 100 {unit} som såld")
    projected = re.fullmatch(
        rf"produktdeklaration per ([0-9]+(?:\.[0-9]+)?(?:e[+-]?[0-9]+)?) {unit}; omräknad till 100 {unit}",
        label)
    if official or (projected and math.isfinite(float(projected[1])) and float(projected[1]) > 0):
        return "normalized_per_100", unit, fact.nutrition_preparation
    return basis


def configured_root():
    value = os.environ.get("AXFOOD_PRODUCT_DETAIL_ROOT")
    return Path(value) if value else None


@lru_cache(maxsize=2)
def _checked_release(root, manifest_hash):
    # Releases are immutable/read-only. Every consumed pair is STILL checked
    # against these file hashes, even after this bounded manifest cache hits.
    return verify_release(root)


def merge_axfood_details(products, facts, root=None):
    """Add detail ingredients/nutrition to Willys/Hemköp facts in place.

    Returns counters. Catalogue facts keep their organic/label evidence;
    existing declarations are not overwritten.
    """
    root = Path(root) if root else configured_root()
    stats = {"products": 0, "own_document": 0, "shared_document": 0,
             "gtin_mismatch": 0, "no_document": 0, "rejected_own_document": 0,
             "rejected_shared_document": 0, "rejections": {}, "conflicts": 0,
             "validation_version": VERSION}
    if root is None or not root.is_dir():
        return stats
    manifest = None
    if (root / "manifest.json").exists() or configured_root() == root:
        try:
            path = root / "manifest.json"
            if path.stat().st_size > 16 * 1024 * 1024:
                raise ValueError("Oversized manifest")
            manifest = _checked_release(root, hashlib.sha256(path.read_bytes()).hexdigest())
            stats["release_manifest"] = root.name
        except (OSError, ValueError, KeyError, TypeError):
            stats["rejections"]["invalid_release"] = 1
            return stats
    elif "staging" in root.parts:
        stats["rejections"]["unpublished_staging"] = 1
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
        found = read_document(root, product.chain, code, manifest=manifest)
        binding = "exact_retailer_article_code"
        if found.status == "revoked":
            facts[key] = replace(fact, conflicts=tuple(dict.fromkeys(
                (*fact.conflicts, "axfood_identity_revoked"))))
        if found.status not in {"missing", "verified"}:
            stats["rejected_own_document"] += 1
            stats["rejections"][found.status] = stats["rejections"].get(found.status, 0) + 1
        if found.status != "verified" and found.status != "revoked" and product.chain == "hemkop":
            found = read_document(root, "willys", code, manifest=manifest)
            binding = "axfood_shared_article_code"
            if found.status not in {"missing", "verified"}:
                stats["rejected_shared_document"] += 1
                stats["rejections"][found.status] = stats["rejections"].get(found.status, 0) + 1
        if found.status != "verified":
            if found.status == "revoked":
                facts[key] = replace(fact, conflicts=tuple(dict.fromkeys(
                    (*fact.conflicts, "axfood_identity_revoked"))))
            stats["no_document"] += 1
            continue
        raw, meta, digest = found.raw, found.meta, found.digest
        gtin = getattr(product, "gtin", None)
        try:
            # A catalogue GTIN requires a checksum-valid detail GTIN, too.
            matches = not gtin or same_gtin(gtin, raw.get("ean"))
        except ValueError:
            matches = False
        if not matches:
            stats["gtin_mismatch"] += 1
            continue
        stats["own_document" if binding.startswith("exact") else "shared_document"] += 1
        source = f"{meta['chain']}:product_detail:{code}:{digest}"
        detail = project_raw_facts(raw, chain=product.chain, product_id=product.product_id,
                                   snapshot_id=product.source_provenance.source_snapshot_id,
                                   source_reference=source, observed_at=meta.get("fetched_at"))
        provenance = {"binding": binding, "document_chain": meta["chain"], "document_url": meta.get("url"),
                      "payload_sha256": digest, "fetched_at": meta.get("fetched_at"),
                      "validation_version": VERSION}
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
        conflicts = list(detail.conflicts)
        if fact.ingredients and detail.ingredients and (
                tuple(" ".join(x.casefold().split()) for x in fact.ingredients)
                != tuple(" ".join(x.casefold().split()) for x in detail.ingredients)):
            conflicts.append("ingredients")
        if fact.animal is not None and detail.animal is not None and fact.animal != detail.animal:
            conflicts.append("animal")
        if fact.nutrition and detail.nutrition:
            compatible = (fact.nutrition_unit == detail.nutrition_unit
                          and _nutrition_basis_identity(fact) == _nutrition_basis_identity(detail)
                          and fact.nutrition_preparation == detail.nutrition_preparation)
            if not compatible:
                conflicts.append("nutrition_basis")
            else:
                conflicts.extend(f"nutrition.{k}" for k in fact.nutrition.keys() & detail.nutrition.keys()
                                 if fact.nutrition[k] != detail.nutrition[k])
                missing = detail.nutrition.keys() - fact.nutrition.keys()
                if missing:
                    changes["nutrition"] = {**fact.nutrition, **{k: detail.nutrition[k] for k in missing}}
        kept = {k: v for k, v in sources.items()
                if (k == "ingredients" and "ingredients" in changes)
                or (k.startswith("nutrition") and "nutrition" in changes)
                or (k == "animal" and "animal" in changes)}
        # Retain contradictory source evidence beside the existing declaration;
        # conflicts veto qualification even when there was no field to fill.
        for field in conflicts:
            if field in sources:
                kept[field] = (*fact.field_sources.get(field, ()), *sources[field])
        if not changes and not conflicts:
            continue
        stats["conflicts"] += bool(conflicts)
        if fact.nutrition and "nutrition" in changes:
            kept = {k: v for k, v in kept.items() if not k.startswith("nutrition.")
                    or k in conflicts or k.removeprefix("nutrition.") not in fact.nutrition}
        facts[key] = replace(fact, **changes, field_sources={**fact.field_sources, **kept},
                             conflicts=tuple(dict.fromkeys((*fact.conflicts, *conflicts))))
    return stats
