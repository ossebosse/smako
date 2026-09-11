"""Project already collected, hash-verified catalog declarations for V2 policy.

No source requests, price changes, user data or guessed joins. This adapter only
fills the proven gap between retained source payloads and personal constraints.
Allergen absence and cooked yield remain unknown: catalog labels cannot prove them.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
from collections import defaultdict
from pathlib import Path
from threading import RLock

from app.services.personal_policy import ProductFacts

FACTS_VERSION = "retained-catalog-facts-v1"
_CACHE = {}
_LOCK = RLock()


def project_raw_facts(raw, *, chain, product_id, snapshot_id, source_reference):
    """Known explicit retailer fields only; no name/brand/image inference."""
    ingredients = raw.get("listOfIngredients") if chain == "coop" else None
    organic = None
    if chain == "coop":
        tags = {t.get("code") for t in raw.get("accreditedTags", []) if isinstance(t, dict)}
        if tags & {"EU_ORGANIC_FARMING", "KRAV_MARK"}:
            organic = True
    elif chain in {"hemkop", "willys"}:
        tags = set(raw.get("labels", []))
        positive = bool(tags & {"eu_ecological", "krav"})
        negative = raw.get("nonEkoProduct") is True
        # Contradictory boolean/marking must not become a positive assertion.
        organic = (
            None if positive and negative else True if positive else False if negative else None
        )
    nutrition, unit, basis = {}, None, None
    if chain == "coop":
        declarations = raw.get("nutrientInformation", [])
        if len(declarations) == 1:
            header = declarations[0].get("header", {})
            code = header.get("nutrientBasisQuantityUnit", {}).get("code")
            amount = header.get("nutrientBasisQuantity")
            if (
                code in {"GRM", "MLT"}
                and header.get("preparationState", {}).get("code") in {None, "UNPREPARED"}
                and header.get("nutrientBasisQuantityType") == "BY_MEASURE"
                and isinstance(amount, (float, int))
                and not isinstance(amount, bool)
                and math.isfinite(amount)
                and amount > 0
            ):
                unit = {"GRM": "g", "MLT": "ml"}[code]
                fields = {
                    ("Energi", "Kilokalori"): "kcal",
                    ("Protein", "Gram"): "protein_g",
                    ("Kolhydrat", "Gram"): "carbs_g",
                    ("Fett", "Gram"): "fat_g",
                }
                values = defaultdict(list)
                for nutrient in raw.get("nutrientLinks", []):
                    key = fields.get((nutrient.get("description"), nutrient.get("unit")))
                    raw_values = nutrient.get("amount", [])
                    if key and len(raw_values) == 1:
                        try:
                            value = float(raw_values[0])
                        except (TypeError, ValueError):
                            continue
                        if math.isfinite(value) and value >= 0:
                            values[key].append(value * 100 / amount)
                nutrition = {
                    key: rows[0]
                    for key, rows in values.items()
                    if len(rows) == 1 and math.isfinite(rows[0])
                }
                basis = f"Produktdeklaration per {amount:g} {unit}; omräknad till 100 {unit}"
    # A complete ingredient string is useful for positive conflicts; it is NOT
    # an exhaustive proof of allergen absence or compound-product suitability.
    return ProductFacts(
        source=source_reference,
        source_product_id=product_id,
        source_snapshot_id=snapshot_id,
        ingredients_complete=False,
        ingredients=(ingredients,) if isinstance(ingredients, str) and ingredients.strip() else (),
        organic=organic,
        nutrition=nutrition,
        nutrition_unit=unit,
        nutrition_basis=basis,
    )


def raw_product(document, reference):
    value = document
    pointer = reference.split("#", 1)[1]
    for token in re.findall(r"[^.\[\]/]+", pointer):
        value = value[int(token)] if isinstance(value, list) else value[token]
    if not isinstance(value, dict):
        raise TypeError("Source product pointer is not an object")
    return value


def load_retained_facts(prepared, *, database=None, raw_root=None):
    from sqlalchemy.engine import make_url

    from grocery_data.app.config import GroceryDataSettings as GrocerySettings

    settings = GrocerySettings.from_env()
    if database is None:
        url = make_url(settings.database_url)
        if url.get_backend_name() != "sqlite" or not url.database:
            return {}
        database = url.database
    raw_root = Path(raw_root or settings.raw_snapshot_root).resolve()
    if not Path(database).is_file():
        return {}
    key = (str(database), str(raw_root), prepared.universe.universe_id, FACTS_VERSION)
    with _LOCK:
        if key in _CACHE:
            return _CACHE[key]
        targets = {
            p.product_id: p
            for p in prepared.universe.products
            if p.chain in {"coop", "hemkop", "willys"}
            and p.source_provenance
            and p.source_provenance.source_provider == "own"
        }
        snapshots = {p.source_provenance.source_snapshot_id for p in targets.values()}
        result = {}
        if not snapshots:
            return result
        with sqlite3.connect(f"file:{Path(database).as_posix()}?mode=ro", uri=True) as db:
            db.row_factory = sqlite3.Row
            if not db.execute("SELECT 1 FROM sqlite_master WHERE name='products'").fetchone():
                return {}
            db.execute("BEGIN")
            last_path, document = None, None
            for snapshot in sorted(snapshots):
                rows = db.execute(
                    """SELECT p.id, p.chain, p.external_product_id,
                    p.store_external_id, p.raw_reference, r.payload_hash, r.payload_location
                    FROM products p JOIN raw_snapshots r ON r.id=p.raw_snapshot_id
                    WHERE p.catalog_snapshot_id=? AND r.catalog_snapshot_id=? ORDER BY r.payload_location, p.id""",
                    (snapshot, snapshot),
                )
                for row in rows:
                    product = targets.get(row["id"])
                    if product is None or product.source_provenance.source_snapshot_id != snapshot:
                        continue
                    if (
                        product.chain != row["chain"]
                        or product.source_provenance.provider_store_id != row["store_external_id"]
                    ):
                        continue
                    path = (raw_root / row["payload_location"]).resolve()
                    if not path.is_relative_to(raw_root):
                        continue
                    try:
                        if path != last_path:
                            data = path.read_bytes()
                            if hashlib.sha256(data).hexdigest() != row["payload_hash"]:
                                continue
                            document = json.loads(data)
                            last_path = path
                        raw = raw_product(document, row["raw_reference"])
                        identity = raw.get("id") if row["chain"] == "coop" else raw.get("code")
                        if str(identity) != row["external_product_id"]:
                            continue
                        result[(product.store_id, product.product_id)] = project_raw_facts(
                            raw,
                            chain=row["chain"],
                            product_id=product.product_id,
                            snapshot_id=snapshot,
                            source_reference=f"{row['chain']}:{row['raw_reference']}:{row['payload_hash']}",
                        )
                    except (OSError, ValueError, KeyError, IndexError, TypeError, AttributeError):
                        continue  # Missing or conflicting evidence remains unknown.
        if len(_CACHE) >= 4:
            _CACHE.pop(next(iter(_CACHE)))
        _CACHE[key] = result
        return result
