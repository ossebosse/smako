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
import unicodedata
from collections import defaultdict
from copy import deepcopy
from dataclasses import asdict, replace
from pathlib import Path
from threading import RLock

from app.services.personal_policy import ProductFacts

FACTS_VERSION = "retained-catalog-facts-v9-ready-baked-bread"
_CACHE = {}
_LOCK = RLock()


def _coop_bread_form_fields(raw):
    """Positive ready-to-eat Matbröd evidence, never a marketing-name guess."""
    description = raw.get("description")
    ingredients = raw.get("listOfIngredients")
    if not isinstance(description, str) or not isinstance(ingredients, str) or not ingredients.strip():
        return None
    category_fields = raw.get("navCategories")
    if not isinstance(category_fields, list):
        return None
    pending = list(category_fields)
    categories = []
    for _ in range(100):
        if not pending:
            break
        node = pending.pop()
        if isinstance(node, dict):
            categories.append(str(node.get("name", "")).casefold().strip())
            parents = node.get("superCategories")
            if isinstance(parents, list):
                pending.extend(parents)
    if "matbröd" not in categories or pending:
        return None
    consumer = raw.get("consumerInformationText", ())
    consumer = [v for v in consumer if isinstance(v, str)] if isinstance(consumer, list) else []
    context = " ".join([str(raw.get("name", "")), description, *categories, *consumer]).casefold()
    fields = {"name": raw.get("name"), "navCategories": deepcopy(raw.get("navCategories", [])),
              "description": description, "listOfIngredients": ingredients,
              "consumerInformationText": consumer}
    # A ready-to-eat statement conditional on baking/thawing is not proof of
    # the as-sold form. Negative preparation information wins over a positive.
    if re.search(r"\b(?:baka|bakas|grädda|gräddas|gräddning|ugn|halvgrädd\w*|förgrädd\w*|"
                 r"bake[ -]?off|deg|brödmix|brödblandning|fylld\w*|fyllt|fyllning|"
                 r"kaffebröd|brioche|kaka|kakor|muffin\w*|fryst\w*|djupfryst\w*|tina|tinas|upptining|"
                 r"uppvärmning|värmas|tillagas|tillagning|måste)\b", context) or re.search(
                     r"\b(?:inte|ej|aldrig)\b.{0,60}\b(?:äta|ätas|servera|serveras|avnjuta|avnjutas)\b|"
                     r"\b(?:äta|ätas|serveras)\b.{0,15}\b(?:inte|ej)\b", context):
        return "not_ready_plain_bread", fields
    if not re.search(r"\b(?:äta|ätas|servera|serveras|avnjuta|avnjutas)\s+(?:precis\s+)?som\s+(?:den|det|de)\s+är\b", description.casefold()):
        return None
    return "ready_baked_bread", fields


def _coop_energy_evidence(raw, *, basis_quantity, basis_unit):
    """Veto gross declaration contradictions; never correct or derive energy.

    EU 1169/2011 Annex XIV uses separately rounded kJ/kcal nutrient factors
    (e.g. 37/9 for fat and 8/2 for fibre). Exact conversion is inappropriate:
    https://eur-lex.europa.eu/eli/reg/2011/1169/oj
    Our conservative integrity screen permits max(8 kJ, 8% of the larger
    energy) on the ORIGINAL declared basis. This is neither a legal tolerance
    nor proof of equivalence. The separate >1000 kcal/100g veto exceeds the
    dietary-fat factor with margin; no mass ceiling applies to ml without
    density. Thresholds remain unknown, and macros are not used to infer kcal.
    """
    entries = [deepcopy(row) for row in raw.get("nutrientLinks", ())
               if isinstance(row, dict) and row.get("description") == "Energi"
               and row.get("unit") in {"Kilokalori", "Kilojoule"}]
    if not entries:
        return None
    reasons, values = [], {}
    for source_unit, key in (("Kilokalori", "kcal"), ("Kilojoule", "kj")):
        rows = [row for row in entries if row["unit"] == source_unit]
        if len(rows) > 1:
            reasons.append(f"{key}_duplicate")
            continue
        if not rows:
            continue
        row = rows[0]
        amounts = row.get("amount")
        if not isinstance(amounts, list) or len(amounts) != 1:
            reasons.append(f"{key}_invalid_amount")
            continue
        accuracy = row.get("amountAccuracy", {})
        if not isinstance(accuracy, dict):
            reasons.append(f"{key}_invalid_accuracy")
            continue
        if accuracy.get("code") not in (None, "EXACT"):
            continue  # A declared bound is not a point value or a pair member.
        try:
            value = float(amounts[0])
        except (TypeError, ValueError, OverflowError):
            reasons.append(f"{key}_invalid_amount")
            continue
        if isinstance(amounts[0], bool) or not math.isfinite(value) or value < 0:
            reasons.append(f"{key}_invalid_amount")
        else:
            values[key] = value
    pair = None
    if "kcal" in values and "kj" in values:
        converted = values["kcal"] * 4.184
        difference = abs(values["kj"] - converted)
        tolerance = max(8.0, 0.08 * max(values["kj"], converted))
        if not math.isfinite(converted) or difference > tolerance:
            reasons.append("energy_pair_mismatch")
        # Preserve only finite calculated diagnostics in serializable evidence.
        pair = {"reference_kj_per_kcal": 4.184,
                "absolute_tolerance_kj": 8.0, "relative_tolerance": 0.08}
    if basis_unit == "g" and basis_quantity and "kcal" in values:
        per_100g = values["kcal"] / basis_quantity * 100
        if not math.isfinite(per_100g) or per_100g > 1000:
            reasons.append("kcal_above_conservative_mass_ceiling")
    return {
        "policy": "coop-explicit-energy-integrity-v1",
        "status": "conflict" if reasons else "no_conflict_detected",
        "reasons": reasons,
        "raw_fields": {"nutrientLinks": entries,
                       "nutrientInformation": deepcopy(raw.get("nutrientInformation", []))},
        "basis_quantity": basis_quantity, "basis_unit": basis_unit,
        "pair_check": pair,
    }


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
    energy_quantity, energy_evidence = None, None
    conflicts = []
    limits = []
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
                energy_quantity = amount
                fields = {
                    ("Energi", "Kilokalori"): "kcal",
                    ("Protein", "Gram"): "protein_g",
                    ("Kolhydrat", "Gram"): "carbs_g",
                    ("Fett", "Gram"): "fat_g",
                }
                values = defaultdict(list)
                for nutrient in raw.get("nutrientLinks", []):
                    if not isinstance(nutrient, dict):
                        continue
                    key = fields.get((nutrient.get("description"), nutrient.get("unit")))
                    raw_values = nutrient.get("amount", [])
                    raw_accuracy = nutrient.get("amountAccuracy", {})
                    accuracy = raw_accuracy.get("code") if isinstance(raw_accuracy, dict) else "UNKNOWN"
                    if key and accuracy not in (None, "EXACT"):
                        limits.append({"field": key, "amount": raw_values,
                                       "accuracy": accuracy, "basis_quantity": amount,
                                       "basis_unit": unit})
                        continue  # A threshold is not an exact declared value.
                    if key and (not isinstance(raw_values, list) or len(raw_values) != 1):
                        conflicts.append("nutrition." + key)
                    if key and isinstance(raw_values, list) and len(raw_values) == 1:
                        try:
                            value = float(raw_values[0])
                        except (TypeError, ValueError, OverflowError):
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
    if chain == "coop":
        energy_evidence = _coop_energy_evidence(raw, basis_quantity=energy_quantity, basis_unit=unit)
        if energy_evidence and energy_evidence["status"] == "conflict":
            nutrition.pop("kcal", None)
            conflicts.extend(("nutrition.kcal", "nutrition.energy"))
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
    frozen_fields = {}
    classifications = {}
    if chain == "coop":
        # Exact positive retailer declarations, not an inferred flattened
        # category or a storage temperature shared by unrelated foods.
        consumer = raw.get("consumerInformationText", ())
        if isinstance(consumer, list) and any(isinstance(v, str) and v.strip().casefold() in {"fryst", "frysta", "djupfryst", "djupfrysta"} for v in consumer):
            frozen_fields["consumerInformationText"] = consumer
        claims = raw.get("claimReportingInformations", {})
        descriptions = claims.get("description", ()) if isinstance(claims, dict) else ()
        if isinstance(descriptions, list) and any(isinstance(v, dict) and v.get("languageCode") == "sv"
                and str(v.get("value", "")).strip().casefold() in {"fryst", "frysta", "djupfryst", "djupfrysta"} for v in descriptions):
            frozen_fields["claimReportingInformations.description"] = descriptions
        if frozen_fields:
            classifications["frozen"] = frozen_fields
        bread_form = _coop_bread_form_fields(raw)
        if bread_form and (bread_form[0] != "ready_baked_bread" or not frozen_fields):
            classifications[bread_form[0]] = bread_form[1]
    # A complete ingredient string is useful for positive conflicts; it is NOT
    # an exhaustive proof of allergen absence or compound-product suitability.
    fact = ProductFacts(
        source=source_reference,
        source_product_id=product_id,
        source_snapshot_id=snapshot_id,
        retailer_product_id=str(raw.get("id") if chain == "coop" else raw.get("code") or ""),
        product_classification=tuple(classifications),
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
        conflicts=tuple(dict.fromkeys(conflicts)),
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
        fact, field_sources={**{k: (dict(evidence),) for k, v in fields.items() if v is not None},
                            **({"nutrition.energy": ({**evidence, **energy_evidence},),
                                **({"nutrition.kcal": ({**evidence, **energy_evidence},)}
                                   if energy_evidence["status"] == "conflict" or "kcal" in nutrition else {})}
                               if energy_evidence else {}),
                            **({"product_classification": tuple({**evidence, "value": value, "raw_fields": fields,
                                "identity_method": "hash_verified_retained_product_fields"}
                                for value, fields in classifications.items())} if classifications else {}),
                            **({"nutrition_limits": tuple({**evidence, **r} for r in limits)}
                               if limits else {})}
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


def identity_variant_conflicts(products):
    """Veto fact propagation, never invalidate independently observed facts.

    A canonical value equal to the displayed name is a fallback label, not an
    independently established food classification. GTIN and exact package are
    checked by the caller. Names never establish identity or transfer prices.
    """
    def text(value):
        return " ".join(unicodedata.normalize("NFKC", value or "").casefold().split())

    reasons = []
    for field in ("product_form", "canonical_food", "brand"):
        values = set()
        for product in products:
            value = text(getattr(product, field))
            if field == "canonical_food" and value == text(product.name):
                continue
            if value:
                values.add(value)
        if len(values) > 1:
            reasons.append(field)
    percentages = {
        tuple(sorted(float(x.replace(",", "."))
                     for x in re.findall(r"(\d+(?:[.,]\d+)?)\s*%", p.name)))
        for p in products
    } - {()}
    if len(percentages) > 1:
        reasons.append("percentage_variant")
    if len({(p.package_quantity, p.package_unit) for p in products}) > 1:
        reasons.append("package")
    return tuple(reasons)


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

        observed = [p.source_provenance.source_observed_at for p in products if p.source_provenance]
        if (
            len(observed) != len(products)
            or (max(observed) - min(observed)).total_seconds() > 7 * 86400
        ):
            continue
        if identity_variant_conflicts(products):
            # Quarantine this cross-source join. An optional ambiguous listing
            # cannot taint the original store's independently retained facts.
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
        if "nutrition.energy" in conflicts:
            # Rejected kcal is intentionally absent from nutrition above, but
            # its original pair must accompany the conflict across exact joins.
            for field in ("nutrition.energy", "nutrition.kcal"):
                sources[field] = tuple(e for f in entries for e in f.field_sources.get(field, ()))
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

    return FactsCollection(enrich_ingredients(prepared, complete_coop_retailer_facts(prepared, result)))



def complete_coop_retailer_facts(prepared, original):
    """Reuse verified catalog facts, never catalog prices, via opaque retailer ID.

    A DKE externalId is NOT declared to be a GTIN. It must match an existing
    Coop catalog id with explicit EAN, exact display variant/brand/package and
    concurrent source observations. Unknown or conflicting matches stay unknown.
    """
    from grocery_data.app.domain.identifiers import InvalidGtinError, normalize_gtin

    def label(value):
        return " ".join(unicodedata.normalize("NFKC", value or "").casefold()
                        .replace("®", "").replace("™", "").split())

    donors = defaultdict(list)
    for p in prepared.universe.products:
        provenance = p.source_provenance
        fact = original.get((p.store_id, p.product_id))
        if not (p.chain == "coop" and provenance and provenance.source_provider == "own"
                and provenance.source_channel == "catalog" and p.gtin and fact
                and fact.source_product_id == p.product_id
                and fact.source_snapshot_id == provenance.source_snapshot_id
                and fact.retailer_product_id == p.gtin and not fact.conflicts):
            continue
        try:
            normalize_gtin(p.gtin)
        except InvalidGtinError:
            continue
        donors[fact.retailer_product_id].append((p, fact))
    result = dict(original)
    for p in prepared.universe.products:
        provenance = p.source_provenance
        key = (p.store_id, p.product_id)
        if (key in original or p.chain != "coop" or not provenance
                or provenance.source_provider != "own" or provenance.source_channel != "offers"
                or p.price_context_type != "physical_store" or p.coverage != "offers_only"
                or provenance.retailer_id_namespace != "coop:public-product"
                or not provenance.retailer_identity_source_sha256
                or not provenance.retailer_product_id or not p.brand or not p.package_quantity):
            continue
        matches = donors.get(provenance.retailer_product_id, [])
        if not matches:
            continue
        def compatible(donor, p=p, provenance=provenance):
            dp = donor.source_provenance
            return (label(p.name) == label(donor.name)
                    and label(p.brand) == label(donor.brand)
                    and p.package_quantity == donor.package_quantity
                    and p.package_unit == donor.package_unit
                    and p.sale_model == donor.sale_model
                    and p.usable_quantity == donor.usable_quantity
                    and p.usable_unit == donor.usable_unit
                    and abs((provenance.source_observed_at - dp.source_observed_at).total_seconds()) <= 7 * 86400)
        if not all(compatible(donor) for donor, _ in matches):
            continue  # A collision cannot be settled by picking the first row.
        fields = ('nutrition', 'nutrition_unit', 'nutrition_basis', 'nutrition_preparation',
                  'ingredients', 'organic', 'animal', 'conflicts')
        signatures = {json.dumps({**{k: getattr(f, k) for k in fields},
            'limits': [{k: e.get(k) for k in ('field', 'amount', 'accuracy', 'basis_quantity', 'basis_unit')}
                       for e in f.field_sources.get('nutrition_limits', ())]}, sort_keys=True)
                      for _, f in matches}
        if len(signatures) != 1:
            continue
        fact = matches[0][1]  # All relevant values explicitly agreed above.
        evidence = {'namespace': 'coop:public-product',
                    'retailer_product_id': provenance.retailer_product_id,
                    'offer_source_sha256': provenance.retailer_identity_source_sha256,
                    'offer_snapshot_id': provenance.source_snapshot_id,
                    'catalog_ean': matches[0][0].gtin,
                    'method': 'exact_retailer_id_name_brand_package_concurrent_catalog',
                    'catalog_sources': [dict(source) for _, f in matches
                        for sources in f.field_sources.values() for source in sources]}
        result[key] = replace(fact, source='verified-coop-retailer-facts',
            source_product_id=p.product_id, source_snapshot_id=provenance.source_snapshot_id,
            field_sources={**fact.field_sources, 'retailer_identity': (evidence,)})
    return result


def raw_product(document, reference):
    value = document
    pointer = reference.split("#", 1)[1]
    for token in re.findall(r"[^.\[\]/]+", pointer):
        value = value[int(token)] if isinstance(value, list) else value[token]
    if not isinstance(value, dict):
        raise TypeError("Source product pointer is not an object")
    return value


def _load_retained_catalog_facts(prepared, *, database=None, raw_root=None):
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
            resolved_paths = {}
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
                    location = row["payload_location"]
                    if location not in resolved_paths:
                        candidate = (raw_root / location).resolve()
                        resolved_paths[location] = (
                            candidate if candidate.is_relative_to(raw_root) else None
                        )
                    path = resolved_paths[location]
                    if path is None:
                        continue
                    source_rows.append((snapshot, row, product, path))

        # A telemetry/profile write in this same SQLite database changes its
        # mtime, but cannot change these public source facts. Key the actual
        # relevant join rows, not the entire database's write activity.
        revision = hashlib.sha256(
            json.dumps(
                {"source_rows": [(snapshot, tuple(row)) for snapshot, row, _, _ in source_rows],
                 "fact_targets": [
                     (p.store_id, p.product_id, p.name, p.brand, p.gtin, p.chain,
                      p.package_quantity, p.package_unit, p.usable_quantity, p.usable_unit,
                      str(p.sale_model), p.coverage, p.price_context_type,
                      p.source_provenance.model_dump(mode="json"))
                     for p in targets.values()]},
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


def load_retained_facts(prepared, *, database=None, raw_root=None):
    from app.services.lidl_product_facts import reviewed_facts
    from app.services.offer_catalog_facts import complete, eligible
    from app.services.official_product_facts import declared_facts

    def merge_fact(prior, fact):
        if prior and "nutrition.energy" in prior.conflicts:
            # A declaration with only invalid energy has no usable nutrition
            # left. Another source must not erase that unresolved conflict or
            # the raw pair needed to investigate it.
            sources = dict(fact.field_sources)
            for field in ("nutrition.energy", "nutrition.kcal"):
                sources[field] = (*prior.field_sources.get(field, ()),
                                  *sources.get(field, ()))
            return replace(fact, field_sources=sources,
                           conflicts=tuple(dict.fromkeys((*fact.conflicts, *prior.conflicts))))
        # Missing fields are not contradictory values; differing overlapping
        # authoritative values/units must never disappear behind precedence.
        if prior and prior.nutrition and fact.nutrition and (
            prior.nutrition_unit != fact.nutrition_unit
            or any(prior.nutrition[k] != fact.nutrition[k]
                   for k in prior.nutrition.keys() & fact.nutrition.keys())
            or prior.conflicts
        ):
            return replace(fact, conflicts=(*fact.conflicts, 'official_declaration_conflict'))
        return fact

    catalog = _load_retained_catalog_facts(prepared, database=database, raw_root=raw_root)
    if any(eligible(p) for p in prepared.universe.products):
        from sqlalchemy.engine import make_url

        from grocery_data.app.config import GroceryDataSettings

        settings = GroceryDataSettings.from_env()
        url = make_url(settings.database_url)
        retained_db = database or (url.database if url.get_backend_name() == 'sqlite' else None)
        if retained_db:
            for key, fact in complete(prepared.universe.products, retained_db,
                                      raw_root or settings.raw_snapshot_root).items():
                catalog[key] = merge_fact(catalog.get(key), fact)
    reviewed = {key: merge_fact(catalog.get(key), fact)
                for key, fact in reviewed_facts(prepared.universe.products).items()}
    for key, fact in declared_facts(prepared.universe.products).items():
        reviewed[key] = merge_fact(reviewed.get(key) or catalog.get(key), fact)
    result = dict(catalog)
    result.update(reviewed)
    from app.services.official_product_facts import supplement_catalog_facts
    supplemented = supplement_catalog_facts(prepared.universe.products, result)
    if not reviewed and supplemented == catalog:
        return catalog  # Preserve the hash-verified retained-source cache.
    return FactsCollection(supplemented)
