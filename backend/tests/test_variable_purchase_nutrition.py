"""Real source-bound approximate pack: checkout and independent nutrition gate."""

import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from app.models.ingredient import NormalizedIngredient
from app.models.recipe import Recipe, RecipeIngredient
from app.services.basket_auditor import BasketAuditor
from app.services.basket_calculator import BasketCalculator
from app.services.official_product_facts import declared_facts
from app.services.personal_planner import PersonalPlanner
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
from app.services.product_matcher import ProductMatcher
from app.services.reviewed_warm_meals import TEMPLATES
from app.services.user_pricing import price_candidate_for_context

from grocery_data.app.domain.promotion_pricing import UserPricingContext


def test_real_lidl_arla_pack_price_and_declared_used_grams_remain_independent():
    root = Path(__file__).parents[2] / "reports/purchase-planning-20260925/final"
    prepared = PreparedPriceUniverseArtifact.model_validate_json(
        (root / "prepared-1281-second.json").read_bytes()
    ).restore()
    p = next(p for p in prepared.universe.products if p.name == "Hushållsost")
    fact = declared_facts([p])[(p.store_id, p.product_id)]
    assert p.gtin is None and p.price is None
    assert fact.field_sources["nutrition.kcal"][0]["supplier_gtin"] == "2340375300007"
    assert not fact.allergens_checked  # A milk declaration is no allergy clearance.
    for changed in (
        p.model_copy(update={"brand": "Other"}),
        p.model_copy(update={"name": "Hushållsost mager"}),
        p.model_copy(
            update={
                "offers": [
                    p.offers[0].model_copy(
                        update={"description": p.offers[0].description.replace("26%", "17%")}
                    )
                ]
            }
        ),
    ):
        assert not declared_facts([changed])
    need = NormalizedIngredient(canonical_name="ost", required_quantity=200, unit="g")
    matched = ProductMatcher().match(need, [p])
    assert matched
    candidate = price_candidate_for_context(
        matched[0], UserPricingContext(), on_date=date(2026, 9, 24), planning_mode="estimated"
    )
    item = BasketCalculator().calculate_item(need, candidate)
    assert (
        item.packages_needed == 1 and item.total_price == 153.78 and item.purchased_quantity == 2200
    )
    audit = BasketAuditor(pantry_items=frozenset()).audit([need], [item])
    assert audit.passed
    assert audit.verification_status == "VERIFIED_WITH_ESTIMATES"
    title, ingredients, instructions = TEMPLATES["lentil_pasta_cheese"]
    recipe = Recipe(
        name=title,
        servings=1,
        ingredients=[RecipeIngredient(name=n, quantity=q, unit="g") for n, q in ingredients],
        instructions=instructions,
    )
    planner = SimpleNamespace(request=SimpleNamespace(purchase_planning_mode="exact"), 
        source_facts=lambda _: fact, spec=SimpleNamespace(allow_nutrition_estimates=True)
    )
    nutrition = PersonalPlanner._nutrition_evidence(
        planner, p, "ost", "g", {"protein_g", "kcal"}, recipe
    )
    assert nutrition.nutrition["protein_g"] * 200 / 100 == 50
    assert (
        PersonalPlanner._nutrition_evidence(planner, p, "ost", "ml", {"protein_g"}, recipe) is None
    )
    (root.parent / "arla-purchase-and-nutrition.json").write_text(
        json.dumps(
            {
                "retrospective_price_replay_date": "2026-09-24",
                "nutrition_acquired": "2026-09-25",
                "source": fact.field_sources,
                "checkout": item.model_dump(mode="json"),
                "audit": audit.model_dump(mode="json"),
                "used_g": 200,
                "used_protein_g": 50,
                "recipe_component": title,
                "allergy_clearance": False,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
