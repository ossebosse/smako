"""Saved real declarations; any artificial prices stay in other test fixtures."""

import hashlib
import importlib.util
import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from app.services.personal_planner import PersonalPlanner
from app.services.reviewed_product_nutrition import reviewed_facts
from app.services.reviewed_warm_meals import candidates, preparation

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "lidl_offer_adapter", ROOT / "reports/source-implementation-20260915/lidl_offer_adapter.py"
)
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


@pytest.fixture
def products():
    return adapter.candidate_models(
        json.loads((ROOT / "reports/source-unblock-20260915/lidl-lund-candidate.json").read_bytes())
    )[1]


def planner_for(products, evidence=None, estimates=True):
    from app.config import Settings
    from app.services.economic_ingredient_selector import EconomicIngredientPool
    from app.services.price_universe import PriceUniverseBuilder, PriceUniverseKey
    from app.services.price_universe_runtime import PreparedPriceUniverse

    from backend.tests.test_personal_planning_v2 import request, state

    now = datetime(2026, 9, 15, 17, 30, tzinfo=UTC)
    store = adapter.candidate_models(
        json.loads((ROOT / "reports/source-unblock-20260915/lidl-lund-candidate.json").read_bytes())
    )[0]
    key = PriceUniverseKey.create(
        city="Lund",
        postal_codes=["22350"],
        snapshot_ids=[p.source_provenance.source_snapshot_id for p in products],
        source_strategy_version="isolated-test",
        normalizer_version="v1",
        taxonomy_version="v1",
    )
    prepared = PreparedPriceUniverse(
        universe=PriceUniverseBuilder().build(key, products, built_at=now),
        stores=(store,),
        economic_pool=EconomicIngredientPool(),
        source_name="reviewed-offer-fixture",
    )

    return PersonalPlanner(
        request(allow_nutrition_estimates=estimates),
        Settings(price_provider="mock"),
        prepared,
        state(),
        facts=reviewed_facts(products) if evidence is None else evidence,
        now=now,
    )


def test_exact_gtin_version_and_explicit_nutrition_basis(products):
    evidence = reviewed_facts(products)
    assert len(evidence) == 2
    cheese, chicken = products[1:]
    cf, kf = (evidence[(p.store_id, p.product_id)] for p in (cheese, chicken))
    assert cf.nutrition == {"kcal": 360, "protein_g": 27, "fat_g": 28, "carbs_g": 0}
    assert kf.nutrition == {"kcal": 160, "protein_g": 20, "fat_g": 8.5}
    assert kf.field_sources["nutrition_bounds"][0]["bounds"]["carbs_g"] == {
        "operator": "<",
        "value": 0.5,
    }
    assert (
        cf.field_sources["nutrition.protein_g"][0]["identity_chain"]["supplier_gtin"]
        == "07393720092442"
    )
    assert (
        kf.field_sources["nutrition.protein_g"][0]["identity_chain"]["manufacturer_article"]
        == "8028"
    )
    assert cf.observed_at != cheese.source_provenance.source_observed_at.isoformat()
    assert all(p.price is None for p in products)


def test_saved_declarations_and_exact_pack_chain_support_the_registry():
    from app.services.reviewed_product_nutrition import PATH

    declarations = json.loads((ROOT / 'reports/lidl-nutrition-20260915/public-declarations.json').read_bytes())
    rows = json.loads(PATH.read_bytes())['products']
    for row in rows:
        declaration = row['declaration']
        saved = declarations[declaration['source']]
        assert declaration['document_sha256'] == saved['document_sha256']
        assert declaration['retrieved_at'] == saved['retrieved_at']
    chicken = rows[1]
    chain = chicken['identity_chain']
    assert chain['retailer_asset_sha256'] == chicken['candidate_review']['source_image_sha256']
    for key, file in [('manufacturer_asset_sha256', 'lidl-nutrition-20260915/kronfagel-8028.png'),
                      ('retailer_asset_sha256', 'source-unblock-20260915/lidl-product-11919135.png')]:
        assert hashlib.sha256((ROOT / 'reports' / file).read_bytes()).hexdigest() == chain[key]
    assert 'Art nr: 8028.' in declarations['kronfagel']['public_product_text']
    assert '900 g' in declarations['kronfagel']['public_product_text']
    assert 'Näringsvärde Per 100 g' in declarations['kronfagel']['public_product_text']
    assert '07393720092442' in declarations['dabas']['public_product_text']


@pytest.mark.parametrize(
    "change",
    [
        {"gtin": "7393720092541"},
        {"name": "Allerum Grevé 18 månader"},
        {"package_quantity": 700},
        {"usable_quantity": 600},
        {"package_unit": "ml"},
    ],
)
def test_near_variant_does_not_inherit_declaration(products, change):
    assert not reviewed_facts([products[1].model_copy(update=change)])


def test_next_campaign_and_old_snapshot_do_not_inherit_review(products):
    p = products[1]
    assert not reviewed_facts(
        [
            p.model_copy(
                update={
                    "source_provenance": p.source_provenance.model_copy(
                        update={"source_snapshot_id": "next-week"}
                    )
                }
            )
        ]
    )


def test_raw_thigh_only_exact_no_discard_preparation(products):
    planner = planner_for(products)
    chicken = products[2]
    thigh = next(r for r in candidates(2) if preparation(r) == "chicken_thigh_oven")
    breast = next(r for r in candidates(2) if preparation(r) == "chicken_oven")
    e = planner.nutrition_evidence(chicken, "kyckling", "g", {"protein_g"}, thigh)
    assert e.evidence_kind == "reviewed_warm_input_estimate"
    assert e.nutrition["protein_g"] * 300 / 100 == 60  # measured RAW input, two servings
    assert (
        thigh.ingredients[0].quantity == 400
    )  # generated meal uses 200 g/person, not breast's 150 g
    history = e.field_sources["nutrition.protein_g"][-1]
    assert history["cooked_quantity_g"] is None and not history["package_surplus_included"]
    assert "food_id" not in history  # never the breast SLV reference
    for recipe in (
        None,
        breast,
        thigh.model_copy(update={"instructions": [*thigh.instructions, "Häll av skyn."]}),
    ):
        assert planner.nutrition_evidence(chicken, "kyckling", "g", {"protein_g"}, recipe) is None
    assert planner.nutrition_evidence(chicken, "kyckling", "g", {"carbs_g"}, thigh) is None
    assert (
        planner_for(products, estimates=False).nutrition_evidence(
            chicken, "kyckling", "g", {"protein_g"}, thigh
        )
        is None
    )


@pytest.mark.parametrize(
    "change",
    [
        {"nutrition_preparation": "cooked"},
        {"nutrition_unit": "ml"},
        {"field_sources": {}},
        {"conflicts": ("nutrition_basis",)},
        {"nutrition": {"protein_g": 99}},
    ],
)
def test_incomplete_or_changed_declaration_is_not_silently_qualified(products, change):
    facts = reviewed_facts(products)
    p = products[2]
    facts[(p.store_id, p.product_id)] = replace(facts[(p.store_id, p.product_id)], **change)
    recipe = next(r for r in candidates() if preparation(r) == "chicken_thigh_oven")
    assert (
        planner_for(products, facts).nutrition_evidence(p, "kyckling", "g", {"protein_g"}, recipe)
        is None
    )


def test_cheese_cold_topping_uses_own_declaration(products):
    recipe = next(r for r in candidates() if preparation(r) == "lentil_pasta_cheese")
    evidence = planner_for(products).nutrition_evidence(
        products[1], "ost", "g", {"protein_g"}, recipe
    )
    assert evidence.source == "reviewed_product_declaration"
    assert evidence.nutrition["protein_g"] == 27


def test_real_cheese_reaches_selected_purchase_and_audit_without_ordinary_price(products):
    from app.models.personal import MealSettings, MealSlot, PortionLimits
    from app.models.recipe import Recipe, RecipeIngredient

    planner = planner_for(products)
    planner.spec.meals = [
        MealSettings(meal_type="snack", count=1, servings=1, limits=PortionLimits(min_protein_g=20))
    ]
    planner.meals = {m.meal_type: m for m in planner.spec.meals}
    planner.spec.slots = [
        MealSlot(
            id="snack-1",
            day=1,
            meal_type="snack",
            recipe=Recipe(
                name="Granskad ost, diagnostiskt delmål",
                servings=1,
                ingredients=[RecipeIngredient(name="ost", quantity=80, unit="g")],
                instructions=["Servera tillsammans."],
            ),
        )
    ]
    planner.request.personal = planner.spec.model_copy(deep=True)
    plan = planner.create()
    assert plan.optimized_basket.total == 79.9
    assert plan.optimized_basket.store_count == 1
    item = plan.optimized_basket.stores[0].items[0]
    assert item.product_id == "11574846" and item.packages_needed == 1
    assert item.regular_unit_price is None and item.purchase_date.isoformat() == "2026-09-15"
    assert plan.personal.checks["nutrition"][0]["values"]["protein_g"] == pytest.approx(21.6)
    assert plan.optimized_basket.verification_status == "VERIFIED"
