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
import stat
import sys
from collections import OrderedDict
from dataclasses import replace
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path

from app.services.personal_source_facts import project_raw_facts

from grocery_data.app.services.axfood_detail_archive import (
    CODE,
    VERSION,
    DetailEvidence,
    read_document,
    same_gtin,
    verify_release,
)

AXFOOD_CHAINS = ("willys", "hemkop")
_DETAIL_FIELDS = ("ingredients", "nutrition_basis", "nutrition_unit", "nutrition_limits")
DETAIL_READ_MAX_ENTRIES = 32768
DETAIL_READ_MAX_BYTES = 32 * 1024 * 1024
DETAIL_DIRECTORY_MAX_BYTES = 8 * 1024 * 1024


def _directory_stamp(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_mtime_ns, info.st_ctime_ns)


def _missing_detail_index(root):
    """Bounded per-projection names, solely to establish absent file pairs.

    Never infer absence from the publication manifest: an unlisted, corrupt or
    revoked file must still reach the ordinary reader. Symlink directories and
    failed/changed listings use that reader too. A fresh lstat before every
    negative lookup detects additions, replacements and permission changes.
    """
    result, retained = {}, 256
    try:
        resolved = root.resolve()
        for chain in AXFOOD_CHAINS:
            if retained + 512 > DETAIL_DIRECTORY_MAX_BYTES:
                return result
            path = root / chain
            before = path.lstat()
            if not stat.S_ISDIR(before.st_mode) or not path.resolve().is_relative_to(resolved):
                continue
            names, size = set(), 256
            with os.scandir(path) as entries:
                for entry in entries:
                    names.add(entry.name)
                    size += sys.getsizeof(entry.name)
                    if retained + size + sys.getsizeof(names) > DETAIL_DIRECTORY_MAX_BYTES:
                        return result
            if _directory_stamp(path.lstat()) == _directory_stamp(before):
                result[chain] = (path, _directory_stamp(before), names)
                retained += size + sys.getsizeof(names)
    except (OSError, RuntimeError):
        # A missing/unreadable directory is not itself evidence of missing files.
        pass
    return result


def _known_missing_pair(index, chain, code):
    if not isinstance(code, str) or not CODE.fullmatch(code) or chain not in index:
        return False
    path, stamp, names = index[chain]
    if f"{code}.json" in names or f"{code}.meta.json" in names:
        return False
    try:
        return _directory_stamp(path.lstat()) == stamp
    except OSError:
        return False


def _detail_bytes(key, evidence):
    # JSON trees plus the evidence envelope; shared objects are counted once
    # per entry, conservatively again across entries. Reserve mapping overhead.
    total, seen, pending = sys.getsizeof(evidence) + 256, set(), [key, vars(evidence)]
    while pending:
        value = pending.pop()
        if id(value) in seen:
            continue
        seen.add(id(value))
        total += sys.getsizeof(value)
        if isinstance(value, dict):
            pending.extend(value.keys())
            pending.extend(value.values())
        elif isinstance(value, (tuple, list)):
            pending.extend(value)
    return total


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


def _limit_conflicts(points, limits, unit):
    """Check source bounds without turning them into point amounts."""
    conflicts = []
    operators = {"LT": "lt", "<": "lt", "GT": "gt", ">": "gt",
                 "LE": "le", "<=": "le", "GE": "ge", ">=": "ge"}
    for evidence in limits:
        field = evidence.get("field")
        operator = operators.get(evidence.get("accuracy"))
        if field not in points or operator is None:
            continue
        try:
            quantities = evidence["amount"]
            if (not isinstance(quantities, list) or len(quantities) != 1
                    or evidence["basis_unit"] != unit):
                raise ValueError("Unusable bound basis")
            amount = Decimal(str(quantities[0]).replace(",", "."))
            basis = Decimal(str(evidence["basis_quantity"]))
            point = Decimal(str(points[field]))
            if not all(x.is_finite() for x in (amount, basis, point)) or amount < 0 or basis <= 0:
                raise ValueError("Unusable bound amount")
            bound = amount * 100 / basis
            if {"lt": point >= bound, "gt": point <= bound,
                "le": point > bound, "ge": point < bound}[operator]:
                conflicts.append(f"nutrition.{field}")
        except (ValueError, KeyError, TypeError, InvalidOperation):
            conflicts.append(f"nutrition.{field}")
    return conflicts


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
    # A publication is immutable. Validate each article once in this projection,
    # including misses, while every product still gets its own GTIN binding and
    # provenance. No cross-call raw-document cache can hide later corruption.
    documents, retained_bytes = OrderedDict(), sys.getsizeof(OrderedDict())
    missing_index = _missing_detail_index(root) if manifest is not None else {}

    def read(chain, code):
        nonlocal retained_bytes
        if not isinstance(code, str):
            return read_document(root, chain, code, manifest=manifest)
        key = (chain, code)
        if key in documents:
            documents.move_to_end(key)
            return documents[key][0]
        if _known_missing_pair(missing_index, chain, code):
            evidence = DetailEvidence("missing")
        else:
            evidence = read_document(root, chain, code, manifest=manifest)
        size = _detail_bytes(key, evidence)
        if size <= DETAIL_READ_MAX_BYTES and DETAIL_READ_MAX_ENTRIES > 0:
            while documents and (len(documents) >= DETAIL_READ_MAX_ENTRIES
                                 or retained_bytes + size > DETAIL_READ_MAX_BYTES):
                _, (_, removed) = documents.popitem(last=False)
                retained_bytes -= removed
            if retained_bytes + size <= DETAIL_READ_MAX_BYTES:
                documents[key] = evidence, size
                retained_bytes += size
        return evidence

    for product in products:
        if product.chain not in AXFOOD_CHAINS or not product.source_provenance:
            continue
        key = (product.store_id, product.product_id)
        fact = facts.get(key)
        code = getattr(fact, "retailer_product_id", None) if fact else None
        if not code:
            continue
        stats["products"] += 1
        found = read(product.chain, code)
        binding = "exact_retailer_article_code"
        if found.status == "revoked":
            facts[key] = replace(fact, conflicts=tuple(dict.fromkeys(
                (*fact.conflicts, "axfood_identity_revoked"))))
        if found.status not in {"missing", "verified"}:
            stats["rejected_own_document"] += 1
            stats["rejections"][found.status] = stats["rejections"].get(found.status, 0) + 1
        if found.status != "verified" and found.status != "revoked" and product.chain == "hemkop":
            found = read("willys", code)
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
        quantity = explicit_drained_quantity(product, raw, provenance)
        identity = retained_article_identity(product, fact, raw, provenance)
        sources = {k: tuple({**e, **provenance} for e in v) for k, v in detail.field_sources.items()
                   if k in _DETAIL_FIELDS or k.startswith("nutrition.") or k == "animal"}
        changes = {}
        if identity:
            sources['retailer_detail_gtin'] = (identity,)
        if quantity:
            previous = fact.field_sources.get('usable_quantity', ())
            if not previous:
                sources['usable_quantity'] = (quantity,)
        if detail.ingredients and not fact.ingredients:
            changes["ingredients"] = detail.ingredients
        if detail.nutrition and not fact.nutrition:
            changes.update(nutrition=detail.nutrition, nutrition_unit=detail.nutrition_unit,
                           nutrition_basis=detail.nutrition_basis,
                           nutrition_preparation=detail.nutrition_preparation)
        if fact.animal is None and detail.animal is not None:
            changes["animal"] = detail.animal
        conflicts = list(detail.conflicts)
        if identity:
            for previous_identity in (*fact.field_sources.get('retailer_image_gtin', ()),
                                      *fact.field_sources.get('retailer_detail_gtin', ())):
                try:
                    agrees = same_gtin(previous_identity.get('gtin'), identity['gtin'])
                except ValueError:
                    agrees = False
                if not agrees:
                    conflicts.append('identity_variant')
        if quantity and previous and any(p.get('quantity') != quantity['quantity'] for p in previous):
            conflicts.append('usable_quantity')
        if fact.ingredients and detail.ingredients and (
                tuple(" ".join(x.casefold().split()) for x in fact.ingredients)
                != tuple(" ".join(x.casefold().split()) for x in detail.ingredients)):
            conflicts.append("ingredients")
        if fact.animal is not None and detail.animal is not None and fact.animal != detail.animal:
            conflicts.append("animal")
        fact_limits = fact.field_sources.get("nutrition_limits", ())
        detail_limits = detail.field_sources.get("nutrition_limits", ())
        if (fact.nutrition or fact_limits) and (detail.nutrition or detail_limits):
            compatible = (fact.nutrition_unit == detail.nutrition_unit
                          and _nutrition_basis_identity(fact) == _nutrition_basis_identity(detail)
                          and fact.nutrition_preparation == detail.nutrition_preparation)
            if not compatible:
                conflicts.append("nutrition_basis")
            else:
                conflicts.extend(f"nutrition.{k}" for k in fact.nutrition.keys() & detail.nutrition.keys()
                                 if fact.nutrition[k] != detail.nutrition[k])
                conflicts.extend(_limit_conflicts(fact.nutrition, detail_limits, detail.nutrition_unit))
                conflicts.extend(_limit_conflicts(detail.nutrition, fact_limits, fact.nutrition_unit))
                missing = detail.nutrition.keys() - fact.nutrition.keys()
                if missing:
                    changes["nutrition"] = {**fact.nutrition, **{k: detail.nutrition[k] for k in missing}}
        kept = {k: v for k, v in sources.items()
                if (k == "ingredients" and "ingredients" in changes)
                or (k.startswith("nutrition") and "nutrition" in changes)
                or (k == "animal" and "animal" in changes)
                or k in {'usable_quantity', 'retailer_detail_gtin'}}
        if "nutrition_limits" in sources:
            kept["nutrition_limits"] = (*fact_limits, *sources["nutrition_limits"])
        # Retain contradictory source evidence beside the existing declaration;
        # conflicts veto qualification even when there was no field to fill.
        for field in conflicts:
            if field in sources:
                kept[field] = (*fact.field_sources.get(field, ()), *sources[field])
        if not changes and not conflicts and not kept:
            continue
        stats["conflicts"] += bool(conflicts)
        if fact.nutrition and "nutrition" in changes:
            kept = {k: v for k, v in kept.items() if not k.startswith("nutrition.")
                    or k in conflicts or k.removeprefix("nutrition.") not in fact.nutrition}
        facts[key] = replace(fact, **changes, field_sources={**fact.field_sources, **kept},
                             conflicts=tuple(dict.fromkeys((*fact.conflicts, *conflicts))))
    return stats


def retained_article_identity(product, fact, raw, provenance):
    """A verified article's declared GTIN, without editing the priced identity."""
    from grocery_data.app.domain.identifiers import InvalidGtinError, normalize_gtin
    from grocery_data.app.services.product_declarations import identity_text

    if (not getattr(product, 'name', None)
            or not all(isinstance(raw.get(k), str) for k in ['name', 'manufacturer', 'displayVolume', 'code', 'ean'])
            or identity_text(raw.get('name') or '') != identity_text(product.name)
            or not getattr(product, 'brand', None)
            or identity_text(raw.get('manufacturer') or '') != identity_text(product.brand)
            or raw.get('code') != fact.retailer_product_id or not raw.get('displayVolume')):
        return None
    try:
        gtin = normalize_gtin(raw.get('ean')).normalized_gtin
    except (InvalidGtinError, TypeError):
        return None
    return {**provenance, 'method': 'checksum_valid_exact_retained_article_detail_gtin',
            'gtin': gtin, 'source': provenance['document_url'], 'bound_fact_source': fact.source,
            'product_id': product.product_id, 'store_id': product.store_id,
            'snapshot_id': product.source_provenance.source_snapshot_id,
            'raw_fields': {k: raw[k] for k in ['name', 'manufacturer', 'displayVolume', 'code', 'ean']}}


def explicit_drained_quantity(product, raw, provenance):
    """Only an explicit net/drained sentence confirmed by the source pack label.

    A slash label alone, a comparison price, or a generic draining ratio cannot
    establish drained mass. The article/GTIN has already passed the reader gate.
    """
    if getattr(product, 'sale_model', None) != 'fixed_package' or getattr(product, 'package_unit', None) != 'g':
        return None
    text = raw.get('description') or ''
    if not isinstance(text, str) or not isinstance(raw.get('displayVolume'), str):
        return None
    matches = re.findall(r'\b(\d+(?:[,.]\d+)?) gram, avrunnen vikt (\d+(?:[,.]\d+)?) gram\.', text)
    if len(matches) != 1:
        return None
    net, drained = (float(n.replace(',', '.')) for n in matches[0])
    label = re.fullmatch(r'(\d+(?:[,.]\d+)?)/(\d+(?:[,.]\d+)?)g', raw.get('displayVolume') or '')
    if (not label or tuple(float(n.replace(',', '.')) for n in label.groups()) != (net, drained)
            or not 0 < drained < net < 100000 or product.package_quantity not in {net, drained}):
        return None
    return {**provenance, 'kind': 'axfood_explicit_drained_mass_v1', 'basis': 'drained', 'unit': 'g',
            'source': provenance['document_url'], 'sha256': provenance['payload_sha256'],
            'quantity': drained, 'purchased_net_quantity': net, 'raw_description': text,
            'raw_display_volume': raw['displayVolume'], 'article_code': raw['code'],
            'bound_product_id': product.product_id, 'bound_store_id': product.store_id,
            'bound_snapshot_id': product.source_provenance.source_snapshot_id,
            'source_package_quantity': product.package_quantity, 'source_package_unit': product.package_unit}
