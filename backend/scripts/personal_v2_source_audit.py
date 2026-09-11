"""Read-only approved catalog-field audit. Never reads personal/receipt tables."""

import argparse
import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True)
    parser.add_argument("--universe-root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--raw-root", default="/srv/smako/data/raw_snapshots")
    parser.add_argument("--mapper", default=None)
    args = parser.parse_args()
    db = sqlite3.connect(f"file:{args.database}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    db.execute("BEGIN")
    snapshots = [
        dict(r)
        for r in db.execute(
            "SELECT id, chain, scope_key, created_at FROM catalog_snapshots WHERE is_active=1"
        )
    ]
    result = {"snapshots": snapshots, "source_fields": {}, "raw_documents": {}}
    for snap in snapshots:
        keys = Counter()
        count = 0
        for r in db.execute(
            "SELECT source_fields FROM source_products WHERE catalog_snapshot_id=?", (snap["id"],)
        ):
            count += 1
            raw = json.loads(r[0])

            def visit(obj, path="", keys=keys):
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        full = path + str(k)
                        keys[full + ":" + type(v).__name__] += 1
                        visit(v, full + ".")
                elif isinstance(obj, list):
                    for v in obj:
                        visit(v, path + "[].")

            visit(raw)
        result["source_fields"][snap["id"]] = {
            "chain": snap["chain"],
            "rows": count,
            "keys": dict(keys),
        }
        result["raw_documents"][snap["id"]] = [
            dict(r)
            for r in db.execute(
                "SELECT kind, payload_location, payload_size FROM raw_snapshots WHERE catalog_snapshot_id=? LIMIT 3",
                (snap["id"],),
            )
        ]
    root = Path(args.universe_root)
    manifest = json.loads((root / "active/city-lund.json").read_text())
    artifact = json.loads((root / manifest["artifact_file"]).read_text())
    result["raw_shapes"] = {}
    for snap in snapshots:
        if snap["chain"] not in {"coop", "hemkop", "willys", "ica"}:
            continue
        shapes = Counter()
        special = defaultdict(list)
        for doc in result["raw_documents"][snap["id"]]:
            path = Path(args.raw_root) / doc["payload_location"]
            raw = json.loads(path.read_text())

            def shape(obj, path="", shapes=shapes, special=special):
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        full = path + str(k)
                        shapes[full + ":" + type(v).__name__] += 1
                        if (
                            any(
                                w in k.lower()
                                for w in (
                                    "allerg",
                                    "nutri",
                                    "organic",
                                    "ingredient",
                                    "marking",
                                    "label",
                                    "certif",
                                    "symbol",
                                )
                            )
                            and len(special[full]) < 4
                        ):
                            special[full].append(v)
                        shape(v, full + ".")
                elif isinstance(obj, list):
                    for v in obj:
                        shape(v, path + "[].")

            shape(raw)
        result["raw_shapes"][snap["id"]] = {
            "chain": snap["chain"],
            "keys": dict(shapes),
            "special": dict(special),
        }
    result["source_identity_examples"] = [
        dict(r)
        for snap in snapshots
        for r in db.execute(
            "SELECT chain, external_product_id, store_external_id, raw_reference FROM source_products WHERE catalog_snapshot_id=? LIMIT 1",
            (snap["id"],),
        )
    ]
    result["raw_product_analysis"] = {}
    result["normalized_id_examples"] = [
        {k: p[k] for k in ("chain", "product_id", "store_id", "source_provenance")}
        for chain in ("coop", "hemkop", "willys", "ica")
        for p in [next(p for p in artifact["universe"]["products"] if p["chain"] == chain)]
    ]
    for snap in snapshots:
        if snap["chain"] not in {"coop", "hemkop", "willys"}:
            continue
        docs = {}
        fields = Counter()
        labels = Counter()
        examples = defaultdict(list)
        rows = db.execute(
            "SELECT p.id, p.external_product_id, p.raw_reference, r.payload_location FROM products p JOIN raw_snapshots r ON r.id=p.raw_snapshot_id WHERE p.catalog_snapshot_id=?",
            (snap["id"],),
        ).fetchall()
        for row in rows:
            location = row["payload_location"]
            if location not in docs:
                docs[location] = json.loads((Path(args.raw_root) / location).read_text())
            pointer = row["raw_reference"].split("#", 1)[-1]
            import re

            value = docs[location]
            for token in re.findall(r"[^.\[\]/]+", pointer):
                value = value[int(token)] if isinstance(value, list) else value[token]
            for k, v in value.items():
                if any(
                    w in k.lower()
                    for w in (
                        "allerg",
                        "nutri",
                        "organic",
                        "ingredient",
                        "energy",
                        "eko",
                        "yield",
                        "preparation",
                    )
                ):
                    fields[k + ":" + type(v).__name__] += 1
                    if v and len(examples[k]) < 2:
                        examples[k].append(v)
            for label in value.get("accreditedTags", []):
                labels[str(label)] += 1
            for label in value.get("labels", []):
                labels[label] += 1
        result["raw_product_analysis"][snap["id"]] = {
            "chain": snap["chain"],
            "rows": len(rows),
            "fields": dict(fields),
            "labels": dict(labels),
            "examples": dict(examples),
        }
    result["manifest"] = manifest
    result["artifact_keys"] = list(artifact)
    result["product_keys"] = list(artifact["universe"]["products"][0])
    result["chain_counts"] = dict(Counter(p.get("chain") for p in artifact["universe"]["products"]))
    result["normalized_special_fields"] = defaultdict(Counter)
    for p in artifact["universe"]["products"]:
        for k in p:
            if (
                any(
                    word in k.lower()
                    for word in (
                        "allerg",
                        "nutri",
                        "organic",
                        "ingredient",
                        "protein",
                        "fat",
                        "carb",
                        "yield",
                    )
                )
                and p[k]
            ):
                result["normalized_special_fields"][p.get("chain")][k] += 1
    if args.mapper:
        import importlib.util
        from datetime import UTC, datetime

        from app.config import Settings
        from app.models import PlanRequest
        from app.models.personal import MealSettings, PersonalPlanning
        from app.services.personal_planner import PersonalPlanner
        from app.services.price_universe_runtime import PreparedPriceUniverseArtifact

        module_spec = importlib.util.spec_from_file_location("retained_mapper", args.mapper)
        mapper = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(mapper)
        prepared = PreparedPriceUniverseArtifact.model_validate(artifact).restore()
        inventory = {
            "id": None,
            "revision": 0,
            "profile": None,
            "items": [],
            "events": {},
            "reservations": {},
        }
        meals = [
            MealSettings(meal_type=t, count=1, servings=4) for t in ("dinner", "breakfast", "snack")
        ]
        planner = PersonalPlanner(
            PlanRequest(recipes=0, personal=PersonalPlanning(meals=meals)),
            Settings(price_provider="mock"),
            prepared,
            inventory,
            now=datetime.now(UTC),
        )
        reachable = set()
        recipe_counts = {}
        for meal in meals:
            candidates = planner._candidates(meal)
            recipe_counts[meal.meal_type] = len(candidates)
            for recipe in candidates:
                for ingredient in planner.service.normalizer.normalize_and_aggregate([recipe]):
                    reachable.update(
                        i
                        for i, _ in planner.resolve(
                            ingredient.canonical_name,
                            ingredient.required_quantity,
                            ingredient.unit,
                            profile=planner.spec.profile,
                        )
                    )
        raw_by_id, docs = {}, {}
        raw_meta = {}
        all_source_snapshots = set(manifest["snapshot_ids"]) | {
            s["id"] for s in snapshots if s["chain"] == "ica"
        }
        for snapshot in sorted(all_source_snapshots):
            for row in db.execute(
                "SELECT p.id, p.chain, p.external_product_id, p.raw_reference, r.payload_location, r.payload_hash FROM products p JOIN raw_snapshots r ON r.id=p.raw_snapshot_id WHERE p.catalog_snapshot_id=?",
                (snapshot,),
            ):
                if row["chain"] not in {"coop", "hemkop", "willys", "ica"}:
                    continue
                location = row["payload_location"]
                if location not in docs:
                    import hashlib

                    raw_bytes = (Path(args.raw_root) / location).read_bytes()
                    assert hashlib.sha256(raw_bytes).hexdigest() == row["payload_hash"]
                    docs[location] = json.loads(raw_bytes)
                try:
                    raw_by_id[row["id"]] = mapper.raw_product(docs[location], row["raw_reference"])
                    raw_meta[row["id"]] = dict(row)
                except (KeyError, IndexError, ValueError, TypeError):
                    pass
        fields = (
            "ingredient_declaration",
            "structured_allergens",
            "free_text_allergen_statement",
            "may_contain",
            "no_usable_allergen_evidence",
            "specific_allergen_claim",
            "organic_true",
            "organic_false",
            "organic_unknown",
            "organic_conflicting",
            "kcal",
            "protein_g",
            "carbs_g",
            "fat_g",
            "nutrition_reference",
            "valid_package_denominator",
            "provenance",
            "mapped_nutrition_complete",
            "raw_edible_quantity",
            "cooked_yield",
            "conversion_evidence",
            "missing_yield",
        )
        coverage = {scope: {} for scope in ("all_searchable", "recipe_reachable")}
        raw_group_counts = Counter()
        header_fields = Counter()
        for scope, scope_rows in coverage.items():
            selected = (
                range(len(prepared.universe.products))
                if scope == "all_searchable"
                else sorted(reachable)
            )
            for i in selected:
                product = prepared.universe.products[i]
                chain = product.chain
                if chain not in {"coop", "hemkop", "willys", "ica"}:
                    continue
                row = scope_rows.setdefault(chain, {"products": 0, **dict.fromkeys(fields, 0)})
                row["products"] += 1
                raw = raw_by_id.get(product.product_id, {})
                ingredients = raw.get("listOfIngredients", "")
                claims = {x.get("code") for x in raw.get("allergyInfo", []) if isinstance(x, dict)}
                claims |= set(raw.get("labels", []))
                specific_claim = bool(
                    claims
                    & {
                        "GLUTEN_FREE",
                        "LACTOSE_FREE",
                        "glutenfree",
                        "laktosfree",
                        "crossed_ax",
                        "CROSSED_GRAIN_SYMBOL",
                    }
                )
                present = isinstance(ingredients, str) and bool(ingredients.strip())
                may_contain = bool(
                    re.search(r"kan innehålla|spår av|may contain", ingredients, re.IGNORECASE)
                )
                values = {
                    "ingredient_declaration": present,
                    "structured_allergens": False,
                    "free_text_allergen_statement": may_contain,
                    "may_contain": may_contain,
                    "specific_allergen_claim": specific_claim,
                    "no_usable_allergen_evidence": not (present or specific_claim),
                    "valid_package_denominator": product.usable_quantity is not None
                    and product.usable_unit is not None
                    and product.quantity_confidence in {"exact", "derived"},
                    "provenance": bool(product.source_provenance),
                    "raw_edible_quantity": False,
                    "cooked_yield": False,
                    "conversion_evidence": False,
                    "missing_yield": True,
                }
                fact = mapper.project_raw_facts(
                    raw,
                    chain=chain,
                    product_id=product.product_id,
                    snapshot_id=product.source_provenance.source_snapshot_id,
                    source_reference="retained exact snapshot",
                )
                values.update(
                    organic_true=fact.organic is True,
                    organic_false=fact.organic is False,
                    organic_unknown=fact.organic is None,
                    organic_conflicting=raw.get("nonEkoProduct") is True
                    and bool(set(raw.get("labels", [])) & {"krav", "eu_ecological"}),
                    nutrition_reference=bool(fact.nutrition_basis),
                    mapped_nutrition_complete={"kcal", "protein_g", "carbs_g", "fat_g"}
                    <= fact.nutrition.keys(),
                )
                for key in ("kcal", "protein_g", "carbs_g", "fat_g"):
                    values[key] = key in fact.nutrition
                for key, value in values.items():
                    row[key] += int(bool(value))
                if scope == "all_searchable":
                    for decl in raw.get("nutrientInformation", []):
                        for key, value in decl.get("header", {}).items():
                            header_fields[key + ":" + str(value)] += 1
                    for offer in raw.get("potentialPromotions", []):
                        raw_group_counts["offers"] += 1
                        raw_group_counts["realMixAndMatch_true"] += (
                            offer.get("realMixAndMatch") is True
                        )
                        raw_group_counts["explicit_productCodes_list"] += bool(
                            offer.get("productCodes")
                        ) and isinstance(offer.get("productCodes"), list)
                        raw_group_counts["complete_group_contract"] += bool(
                            offer.get("realMixAndMatch") is True
                            and offer.get("productCodes")
                            and offer.get("validFrom")
                            and offer.get("validUntil")
                        )
        for scope in coverage.values():
            for chain in scope.values():
                n = chain["products"]
                for key in fields:
                    chain[key] = {
                        "count": chain[key],
                        "percent": round(chain[key] * 100 / n, 2) if n else None,
                    }
        public = {
            "generated_at": datetime.now(UTC).isoformat(),
            "manifest": manifest,
            "coverage": coverage,
            "recipe_counts": recipe_counts,
            "recipe_scope": "Current default mixed-diet candidate generation, 4 servings, no memberships; union across dinner/breakfast/snack.",
            "raw_group_counts": dict(raw_group_counts),
            "nutrition_headers": dict(header_fields),
            "mix_and_match_live": "LIVE_DATA_UNAVAILABLE",
            "normalized_food_fields_before_mapping": result["normalized_special_fields"],
            "source_rows": {
                s["chain"] + ":" + s["scope_key"]: result["source_fields"][s["id"]]["rows"]
                for s in snapshots
                if s["chain"] in {"coop", "hemkop", "willys", "ica"}
            },
        }
        # Audit Primat's already approved closed-provider cache; never request it live.
        provider_root = root / "external-provider-cache"
        provider_manifest = json.loads((provider_root / "active/city-lund.json").read_text())
        provider = json.loads((provider_root / provider_manifest["artifact_file"]).read_text())
        public["primat_retained_cache_keys"] = list(provider)
        public["primat_retained_cache_manifest"] = provider_manifest
        result = public
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps({"snapshots": len(snapshots), "coverage_complete": bool(args.mapper)}))


if __name__ == "__main__":
    main()
