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
from dataclasses import asdict, replace
from pathlib import Path
from threading import RLock

from app.services.personal_policy import ProductFacts

FACTS_VERSION = "retained-catalog-facts-v3"
_CACHE = {}
_LOCK = RLock()


def project_raw_facts(raw, *, chain, product_id, snapshot_id, source_reference, observed_at=None):
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
    conflicts = []
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
                    if key and len(raw_values) != 1:
                        conflicts.append("nutrition." + key)
                    if key and len(raw_values) == 1:
                        try:
                            value = float(raw_values[0])
                        except (TypeError, ValueError):
                            conflicts.append("nutrition." + key)
                            continue
                        if math.isfinite(value) and value >= 0:
                            values[key].append(value * 100 / amount)
                        else:
                            conflicts.append("nutrition." + key)
                nutrition = {
                    key: rows[0]
                    for key, rows in values.items()
                    if len(rows) == 1
                    and math.isfinite(rows[0])
                    and "nutrition." + key not in conflicts
                }
                conflicts.extend(
                    f"nutrition.{key}" for key, rows in values.items() if len(rows) != 1
                )
                basis = f"Produktdeklaration per {amount:g} {unit}; omräknad till 100 {unit}"
        elif declarations:
            conflicts.append("nutrition_basis")
    if chain == "coop" and raw.get("nutrientInformation") and basis is None:
        conflicts.append("nutrition_basis")
    tags = {t.get("code") for t in raw.get("accreditedTags", []) if isinstance(t, dict)}
    vegan = bool(
        tags & {"EUROPEAN_V_LABEL_VEGAN", "VEGAN_SOCIETY_VEGAN_LOGO", "100_PERCENT_VEGANSKT"}
    )
    animal_positive = bool(tags & {"KOTT_FRAN_SVERIGE", "SVENSK_FAGEL", "MJOLK_FRAN_SVERIGE"})
    animal_positive |= bool(
        set(raw.get("labels", [])) & {"meat_from_sweden", "swedish_bird", "milk_from_sweden"}
    )
    # Only positive ingredient evidence. Absence of these words proves nothing.
    if isinstance(ingredients, str):
        composition = re.split(
            r"kan innehålla|spår av|may contain", ingredients, flags=re.IGNORECASE
        )[0]
        animal_positive |= bool(
            re.search(
                r"\b(mjölk|komjölk|getmjölk|grädde|ägg|äggula|äggvita|kycklingkött|nötkött|fläskkött)\b",
                composition,
                re.IGNORECASE,
            )
        )
    animal = (
        None if vegan and animal_positive else False if vegan else True if animal_positive else None
    )
    if vegan and animal_positive:
        conflicts.append("animal")
    if chain in {"willys", "hemkop"} and positive and negative:
        conflicts.append("organic")
    # A complete ingredient string is useful for positive conflicts; it is NOT
    # an exhaustive proof of allergen absence or compound-product suitability.
    fact = ProductFacts(
        source=source_reference,
        source_product_id=product_id,
        source_snapshot_id=snapshot_id,
        retailer_product_id=str(raw.get("id") if chain == "coop" else raw.get("code") or ""),
        ingredients_complete=False,
        ingredients=(ingredients,) if isinstance(ingredients, str) and ingredients.strip() else (),
        organic=organic,
        nutrition=nutrition,
        nutrition_unit=unit,
        nutrition_basis=basis,
        nutrition_preparation="draining_unknown"
        if (
            isinstance(ingredients, str)
            and re.search(r"\b(lake|avrunnen|avrunnet|avrunna)\b", ingredients, re.IGNORECASE)
            or re.search(
                r"\b(mozzarella|feta|salladsost)\b", str(raw.get("name", "")), re.IGNORECASE
            )
        )
        else "as_sold",
        animal=animal,
        observed_at=observed_at,
        conflicts=tuple(conflicts),
    )
    evidence = {
        "source": source_reference,
        "product_id": product_id,
        "source_product_id": str(raw.get("id") or raw.get("code") or product_id),
        "snapshot_id": snapshot_id,
        "observed_at": observed_at,
        "market": "SE",
    }
    fields = {
        "organic": organic,
        "animal": animal,
        "ingredients": fact.ingredients or None,
        "nutrition_basis": basis,
        "nutrition_unit": unit,
        **{f"nutrition.{k}": v for k, v in nutrition.items()},
    }
    return replace(
        fact, field_sources={k: (dict(evidence),) for k, v in fields.items() if v is not None}
    )


def facts_version(facts):
    return (
        FACTS_VERSION
        + ":"
        + hashlib.sha256(
            json.dumps(
                [[list(k), asdict(v)] for k, v in sorted(facts.items())],
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
    )


class FactsCollection(dict):
    """Public, immutable-by-convention projection with a content version."""

    def __init__(self, values):
        super().__init__(values)
        self.version = facts_version(self)


def complete_identity_facts(prepared, original):
    """Facts only, using the existing checked GTIN + exact package identity.

    Concurrent Swedish observations (<=7 days apart) may fill absent fields.
    Conflicting variants, declarations or bases never supply convenient values.
    Product objects, price observations and their timestamps are never mutated.
    """
    from grocery_data.app.domain.identifiers import InvalidGtinError, normalize_gtin

    result = dict(original)
    for positions in prepared.product_search_index.groups.values():
        products = [prepared.universe.products[i] for i in positions]
        if len(products) < 2 or any(not p.gtin or not p.package_quantity for p in products):
            continue
        if any(p.chain not in {"coop", "hemkop", "willys", "ica"} for p in products):
            continue
        try:
            if len({normalize_gtin(p.gtin).normalized_gtin for p in products}) != 1:
                continue
        except InvalidGtinError:
            continue

        # GTIN establishes identity; these checks veto contradictory variants.
        def variants(p):
            return tuple(
                sorted(
                    float(x.replace(",", ".")) for x in re.findall(r"(\d+(?:[.,]\d+)?)\s*%", p.name)
                )
            )

        observed = [p.source_provenance.source_observed_at for p in products if p.source_provenance]
        if (
            len(observed) != len(products)
            or (max(observed) - min(observed)).total_seconds() > 7 * 86400
        ):
            continue
        if (
            any(
                len({getattr(p, field) for p in products if getattr(p, field)}) > 1
                for field in ("product_form", "canonical_food", "brand")
            )
            or len({variants(p) for p in products if variants(p)}) > 1
        ):
            for p in products:
                key = (p.store_id, p.product_id)
                if key in result:
                    result[key] = replace(
                        result[key],
                        conflicts=tuple(sorted(set(result[key].conflicts) | {"identity_variant"})),
                    )
            continue
        entries = [
            original[(p.store_id, p.product_id)]
            for p in products
            if (p.store_id, p.product_id) in original
            and original[(p.store_id, p.product_id)].source_product_id == p.product_id
            and original[(p.store_id, p.product_id)].source_snapshot_id
            == p.source_provenance.source_snapshot_id
        ]
        if not entries:
            continue
        markets = {
            e.get("market")
            for f in entries
            for values in f.field_sources.values()
            for e in values
            if e.get("market")
        }
        if markets - {"SE"}:
            continue
        changes, sources = {}, {}
        conflicts = set().union(*(set(f.conflicts) for f in entries))
        for field in ("organic", "animal", "ingredients"):
            known = [
                (getattr(f, field), f)
                for f in entries
                if getattr(f, field) is not None and getattr(f, field) != ()
            ]
            distinct = {json.dumps(v, ensure_ascii=False, sort_keys=True) for v, _ in known}
            if len(distinct) > 1 or field in conflicts:
                conflicts.add(field)
                changes[field] = () if field == "ingredients" else None
            elif known:
                changes[field] = known[0][0]
            if known:
                sources[field] = tuple(
                    e
                    for _, f in known
                    for e in f.field_sources.get(
                        field,
                        (
                            {
                                "source": f.source,
                                "product_id": f.source_product_id,
                                "snapshot_id": f.source_snapshot_id,
                                "observed_at": f.observed_at,
                            },
                        ),
                    )
                )
        nutritional = [f for f in entries if f.nutrition]
        # Reference basis must agree exactly; do not mix raw/prepared or g/ml.
        bases = {
            (f.nutrition_unit, f.nutrition_basis, f.nutrition_preparation) for f in nutritional
        }
        nutrition = {}
        if len(bases) > 1 or "nutrition_basis" in conflicts:
            conflicts.add("nutrition_basis")
        elif nutritional:
            (
                changes["nutrition_unit"],
                changes["nutrition_basis"],
                changes["nutrition_preparation"],
            ) = next(iter(bases))
            for key in set().union(*(f.nutrition.keys() for f in nutritional)):
                field = "nutrition." + key
                known = [(f.nutrition[key], f) for f in nutritional if key in f.nutrition]
                if len({v for v, _ in known}) == 1 and field not in conflicts:
                    nutrition[key] = known[0][0]
                else:
                    conflicts.add(field)
                sources[field] = tuple(
                    e
                    for _, f in known
                    for e in f.field_sources.get(
                        field,
                        (
                            {
                                "source": f.source,
                                "product_id": f.source_product_id,
                                "snapshot_id": f.source_snapshot_id,
                                "observed_at": f.observed_at,
                            },
                        ),
                    )
                )
        if nutritional:
            changes["nutrition"] = nutrition
            if len(bases) > 1 or "nutrition_basis" in conflicts:
                changes.update(nutrition_unit=None, nutrition_basis=None)
        for p in products:
            key = (p.store_id, p.product_id)
            current = original.get(key) or ProductFacts(
                source="verified-gtin-facts",
                source_product_id=p.product_id,
                source_snapshot_id=p.source_provenance.source_snapshot_id,
            )
            result[key] = replace(
                current,
                **changes,
                field_sources={**current.field_sources, **sources},
                conflicts=tuple(sorted(conflicts)),
            )
    from app.services.reviewed_ingredients import enrich_ingredients

    return FactsCollection(enrich_ingredients(prepared, result))


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
    with _LOCK:
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
            source_rows = []
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
                    source_rows.append((snapshot, row, product, path))

        # A telemetry/profile write in this same SQLite database changes its
        # mtime, but cannot change these public source facts. Key the actual
        # relevant join rows, not the entire database's write activity.
        revision = hashlib.sha256(
            json.dumps(
                [(snapshot, tuple(row)) for snapshot, row, _, _ in source_rows],
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        key = (
            str(Path(database).resolve()),
            str(raw_root),
            prepared.universe.universe_id,
            FACTS_VERSION,
            revision,
        )
        # Validate every distinct source payload even on a cache hit. Neither
        # unchanged snapshot identity nor preserved file timestamps can bless
        # a missing/corrupt/replaced source. Streaming keeps scratch memory small.
        hashes = {}
        for _, _, _, path in source_rows:
            if path not in hashes:
                try:
                    with path.open("rb") as stream:
                        hashes[path] = hashlib.file_digest(stream, "sha256").hexdigest()
                except OSError:
                    hashes[path] = None
        cacheable = all(hashes[path] == row["payload_hash"] for _, row, _, path in source_rows)
        if cacheable and key in _CACHE:
            return _CACHE[key]
        last_path, document = None, None
        for snapshot, row, product, path in source_rows:
            if hashes[path] != row["payload_hash"]:
                continue
            try:
                if path != last_path:
                    data = path.read_bytes()
                    if hashlib.sha256(data).hexdigest() != row["payload_hash"]:
                        cacheable = False
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
                    observed_at=product.source_provenance.source_observed_at.isoformat(),
                )
            except (OSError, ValueError, KeyError, IndexError, TypeError, AttributeError):
                cacheable = False
                continue  # Missing or conflicting evidence remains unknown.
        projected = complete_identity_facts(prepared, result)
        if cacheable:
            if len(_CACHE) >= 4:
                _CACHE.pop(next(iter(_CACHE)))
            _CACHE[key] = projected
        return projected
