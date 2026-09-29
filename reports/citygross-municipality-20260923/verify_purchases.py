"""Real retained municipal City Gross prices, ordinary builder/matcher/checkout.

No retailer calls, model calls, new recipes or guessed nutrition. Reuses the
existing retained recipe and the source observations from the final v4 replay.
"""
import asyncio
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO / "backend"), str(REPO)]
ROOT = Path(__file__).resolve().parent


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf8")


async def build(code, store_id):
    from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
    from app.services.production_price_universe_build import build_city_price_universe

    from grocery_data.app.storage import create_database_engine, create_schema

    source = ROOT / f"final-v4-replay-{code}"
    inventory = json.loads((source / "inventory.json").read_bytes())
    record = json.loads((source / "coverage.json").read_bytes())["stores"][0]
    directory = ROOT / ("purchases-" + store_id)
    directory.mkdir(exist_ok=True)
    artifact = directory / "universe.json"
    override = ROOT / "purchase-artifact-inputs.json"
    if override.exists():
        configured = json.loads(override.read_bytes()).get(store_id)
        if configured:
            artifact = Path(configured)
    if not artifact.exists():
        database = directory / "empty-base.sqlite"
        engine = create_database_engine("sqlite:///" + database.resolve().as_posix())
        create_schema(engine)
        engine.dispose()
        official = next(r["store"] for r in inventory["stores"] if r["store"]["external_id"] == store_id)
        report = await build_city_price_universe(database, inventory["area"]["city"],
            official["postal_code"], None, artifact, 48,
            citygross_municipal_enabled=True,
            citygross_sources=[{"database": source / store_id / "own.sqlite",
                "inventory": inventory, "store_ids": [store_id], "snapshot_ids": [record["snapshot_id"]]}])
        assert report["status"] == "PASS" and report["network_attempts"] == 0
        save(directory / "build.json", report)
    prepared = PreparedPriceUniverseArtifact.model_validate_json(artifact.read_bytes())
    assert len(prepared.stores) == 1
    products = list(prepared.universe.products)
    assert prepared.stores[0].source_store_id == store_id
    assert products and all(p.store_id == prepared.stores[0].store_id for p in products)
    assert all(p.source_provenance.provider_store_id == store_id for p in products)
    save(directory / "used-artifact.json", {"path": str(artifact.resolve()),
         "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
         "universe_id": prepared.universe.universe_id})
    return products, record, directory


def purchase(need, product, context, *, on_date=None):
    from app.services.basket_auditor import BasketAuditor
    from app.services.basket_calculator import BasketCalculator
    from app.services.product_matcher import ProductMatcher
    from app.services.user_pricing import price_candidate_for_context

    matches = ProductMatcher().match(need, [product])
    if not matches:
        raise ValueError("normal matcher rejected ingredient/product")
    candidate = price_candidate_for_context(matches[0], context, on_date=on_date)
    item = BasketCalculator().calculate_item(need, candidate)
    audit = BasketAuditor(pantry_items=frozenset()).audit([need], [item], user_pricing_context=context)
    if not audit.passed:
        raise ValueError("normal basket audit rejected purchase")
    return item, audit


async def run(selected_store_ids=None):
    from app.models.ingredient import NormalizedIngredient
    from app.models.recipe import Recipe
    from app.services.basket_auditor import BasketAuditor
    from app.services.ingredient_normalizer import IngredientNormalizer

    from grocery_data.app.domain.promotion_pricing import UserPricingContext

    recipe_path = REPO / "reports/coop-refresh-integration-20260922/request-recipes.json"
    blocks = json.loads(recipe_path.read_bytes())
    recipe = next(Recipe.model_validate(r) for block in blocks for r in block["recipes"]
                  if r["name"] == "Tomatpasta med ägg och gul lök")
    needs = IngredientNormalizer().normalize_and_aggregate([recipe])
    public = UserPricingContext()
    member = UserPricingContext.from_chain_flags({"citygross": True})
    report = {"observed_test_at": datetime.now(UTC), "network_price_requests": 0,
              "production_activation": False, "source_mode": "retained_final_v4_database_replay",
              "recipe_source": str(recipe_path.relative_to(REPO)),
              "recipe_sha256": hashlib.sha256(recipe_path.read_bytes()).hexdigest(),
              "nutrition_claim": "No new nutritional acceptance; exact retained recipe purchase test only",
              "stores": []}
    for code, store_id in (("1280", "3211"), ("1230", "3229")):
        if selected_store_ids and store_id not in selected_store_ids:
            continue
        products, source, directory = await build(code, store_id)
        row = {"store_id": store_id, "municipality_code": code,
               "snapshot_id": source["snapshot_id"], "source_observed_at": source["observed_at"],
               "price_universe_products": len(products), "products": []}
        # Explicit pasta purchase on the common, exact product variant.
        pasta = next(p for p in products if p.source_provenance.retailer_product_id == "101548709_ST")
        pasta_need = NormalizedIngredient(canonical_name="pasta", required_quantity=2000, unit="g")
        item, audit = purchase(pasta_need, pasta, public)
        row["products"].append({"purpose": "public_multibuy", "source_product": pasta.model_dump(mode="json"),
                                "need": pasta_need.model_dump(mode="json"), "item": item.model_dump(mode="json"),
                                "audit": audit.model_dump(mode="json")})
        # Use current member products only when the ordinary semantic matcher
        # qualifies their source identity. Record both public and member prices.
        member_checks = []
        for product in products:
            if not any(str(o.eligibility) == "member" and o.is_active() for o in product.offers):
                continue
            unit = product.usable_unit or product.package_unit
            quantity = product.usable_quantity or product.package_quantity
            if unit not in {"g", "ml", "st"} or not quantity:
                continue
            need = NormalizedIngredient(canonical_name=product.canonical_name,
                                        display_name=product.name, required_quantity=quantity, unit=unit)
            try:
                public_item, public_audit = purchase(need, product, public)
                member_item, member_audit = purchase(need, product, member)
            except ValueError:
                continue
            if public_item.total_price <= member_item.total_price:
                continue
            member_checks.append({"product": product.model_dump(mode="json"),
                "purpose": "exact_named_retail_product_purchase;not_a_recipe_ingredient_substitution",
                "need": need.model_dump(mode="json"), "public_item": public_item.model_dump(mode="json"),
                "member_item": member_item.model_dump(mode="json"),
                "public_audit": public_audit.model_dump(mode="json"), "member_audit": member_audit.model_dump(mode="json")})
            break
        assert member_checks, f"no valid member probe for {store_id}"
        row["membership"] = member_checks
        cap = pasta.source_provenance.maximum_purchase_units
        assert cap == 25 and pasta.source_provenance.quantity_limit_source_url
        cap_need = pasta_need.model_copy(update={"required_quantity": 25 * pasta.package_quantity})
        cap_item, cap_audit = purchase(cap_need, pasta, public)
        try:
            purchase(cap_need.model_copy(update={"required_quantity": 26 * pasta.package_quantity}), pasta, public)
        except ValueError as exc:
            assert "purchase-unit limit exceeded" in str(exc)
        else:
            raise AssertionError("26 packages accepted despite exact source cap25")
        row["purchase_cap"] = {"limit": cap, "accepted_packages": cap_item.packages_needed,
            "accepted_cost": cap_item.total_price, "audit": cap_audit.model_dump(mode="json"),
            "rejected_packages": 26, "source": pasta.source_provenance.quantity_limit_source_url}
        recipe_items, selections = [], []
        from app.services.product_matcher import ProductMatcher
        by_id = {p.product_id: p for p in products}
        for need in needs:
            options = []
            for matched in ProductMatcher().match(need, products):
                product = by_id[matched.product_id]
                # Explicit representative purchase: the retained recipe uses
                # fresh tomato separately from crushed canned tomato. Existing
                # generic matching also admits passata, so constrain this test
                # to the source's actual fresh-produce category without
                # changing matching or attaching prices to another identity.
                if need.canonical_name == "tomat" and product.category != "Frukt & grönt > Grönsaker > Tomater":
                    continue
                try:
                    candidate_item, _ = purchase(need, product, public)
                    options.append((candidate_item.total_price, product.product_id, candidate_item, product))
                except ValueError:
                    continue
            if not options:
                raise ValueError(f"retained recipe lacks auditable {need.canonical_name} in {store_id}")
            _, _, chosen, chosen_product = min(options, key=lambda item: (item[0], item[1]))
            recipe_items.append(chosen)
            selections.append({"ingredient": need.model_dump(mode="json"),
                               "product": chosen_product.model_dump(mode="json"),
                               "purchase": chosen.model_dump(mode="json")})
        recipe_audit = BasketAuditor(pantry_items=frozenset()).audit(needs, recipe_items, user_pricing_context=public)
        assert recipe_audit.passed
        row["recipe"] = {"definition": recipe.model_dump(mode="json"), "selections": selections,
                          "cost": round(sum(i.total_price for i in recipe_items), 2),
                          "audit": recipe_audit.model_dump(mode="json"), "nutrition_verification": "not_performed",
                          "explicit_fresh_tomato_selection": True,
                          "known_matcher_gap": "generic tomato also admits passata; this explicit purchase uses source fresh-produce category"}
        save(directory / "purchases.json", row)
        report["stores"].append(row)
        save(ROOT / "purchases.json", report)
    print(json.dumps([{"store": r["store_id"], "pu": r["price_universe_products"],
                      "recipe_cost": r["recipe"]["cost"]} for r in report["stores"]]))
    return report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store-id", action="append")
    args = parser.parse_args()
    asyncio.run(run(args.store_id))
