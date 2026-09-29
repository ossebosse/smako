"""Read the published private artifact; exercise existing matcher/checkout/audit."""
import argparse
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from app.models.ingredient import NormalizedIngredient
from app.services.basket_auditor import BasketAuditor
from app.services.basket_calculator import BasketCalculator, GroupPricingError
from app.services.lidl_product_facts import reviewed_facts
from app.services.personal_planner import PersonalPlanner
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
from app.services.product_matcher import ProductMatcher
from app.services.user_pricing import price_candidate_for_context

from grocery_data.app.domain.promotion_pricing import UserPricingContext
from grocery_data.app.services.prepared_universe_activation import PreparedUniverseArtifactStore


def run(root, city):
    artifact = PreparedUniverseArtifactStore(root / "price-universes").resolve_active_artifact(city, verify_hash=True)
    prepared = PreparedPriceUniverseArtifact.model_validate_json(artifact.read_bytes()).restore()
    products = [p for p in prepared.universe.products if p.chain == "lidl"]
    facts = reviewed_facts(products)
    rows, capped = [], []
    context = UserPricingContext.from_chain_flags({"lidl": True})
    for product in products:
        if product.name not in {"Hamburgare", "Lingongrova"}:
            continue
        need = NormalizedIngredient(canonical_name=product.name.casefold(), required_quantity=product.package_quantity, unit="g")
        matches = ProductMatcher().match(need, [product])
        assert len(matches) == 1
        candidate = price_candidate_for_context(matches[0], context, on_date=date(2026, 9, 23))
        item = BasketCalculator().calculate_item(need, candidate)
        audit = BasketAuditor(pantry_items=frozenset()).audit([need], [item], user_pricing_context=context)
        assert audit.passed
        try:
            price_candidate_for_context(matches[0], UserPricingContext(), on_date=date(2026, 9, 23))
        except ValueError:
            nonmember = "blocked_unknown_ordinary_price"
        else:
            raise AssertionError("member-only offer leaked")
        fact = facts.get((product.store_id, product.product_id))
        planner = SimpleNamespace(spec=SimpleNamespace(allow_nutrition_estimates=False), source_facts=lambda _, f=fact: f)
        nutrition = PersonalPlanner._nutrition_evidence(planner, product, product.name.casefold(), "g", {"kcal", "protein_g", "fat_g", "carbs_g"}, None)
        rows.append({"store_id": product.source_provenance.provider_store_id, "context": product.store_id,
            "product_id": product.source_provenance.retailer_product_id, "name": product.name,
            "checkout": item.model_dump(mode="json"), "audit_passed": audit.passed, "nonmember": nonmember,
            "nutrition": asdict(nutrition) if nutrition else None,
            "nutrition_status": "exact_supplier_declaration_as_sold" if nutrition else "missing_compatible_declaration",
            "ordinary_price": product.price, "source": product.source_provenance.model_dump(mode="json")})
        if product.name == "Hamburgare":
            capped.append(item)
    assert len({r["store_id"] for r in rows}) == len(products) // 3
    valid = BasketCalculator.quote_group_basket(capped[:2])
    assert sum(i.total_price for i in valid) == 318
    # A third recipe purchase in an already used store must consume the same
    # household allowance as the first two distinct physical stores.
    try:
        BasketCalculator.quote_group_basket([capped[0], capped[1], capped[0]])
    except GroupPricingError:
        limit = "third_package_across_stores_and_recipes_blocked"
    else:
        raise AssertionError("household limit multiplied")
    result = {"city": city, "artifact": str(artifact), "price_universe_id": prepared.universe.universe_id,
        "kind": "published_artifact_checkout_replay_no_network", "purchase_date": "2026-09-23",
        "source_observations_rewritten": False, "actual_stores": len(capped), "rows": rows,
        "household_limit": limit, "two_stores_two_packages_total": 318}
    (root / "purchases.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"city": city, "stores": len(capped), "audited_purchases": len(rows), "household_limit": limit}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--city", required=True)
    args = parser.parse_args()
    run(args.root, args.city)
