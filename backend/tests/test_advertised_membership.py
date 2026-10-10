"""Conditional advertised membership policy, without claiming account eligibility."""
import json

import pytest
from app.api.plan import _production_consumer_request
from app.config import Settings
from app.models import PlanRequest
from app.models.personal import ExtraNeed, PersonalPlanning
from app.services.personal_planner import PersonalPlanner
from app.services.plan_mutation import _pricing_context

from backend.tests.test_product_search import offer, prepare, product, search
from backend.tests.test_weight_offers import NOW, retained
from backend.tests.test_weight_offers import prepare as weight_prepare
from grocery_data.app.domain.promotion_pricing import MembershipProgram, PriceContract


def test_new_consumer_calculation_includes_all_without_changing_held_memberships():
    old = PlanRequest(memberships={"coop": False})
    original = old.model_dump_json()
    new = _production_consumer_request(old, Settings(app_env="test"))
    assert new.membership_price_policy == "all_advertised"
    assert not new.memberships["coop"] and not new.membership_programs
    assert len(new.pricing_memberships) == 6 and all(new.pricing_memberships.values())
    assert old.model_dump_json() == original
    assert "membership_price_policy" not in json.loads(original)
    assert PlanRequest.model_validate_json(original).model_dump_json() == original
    assert PlanRequest.model_validate_json(new.model_dump_json()).pricing_memberships == new.pricing_memberships
    assert _pricing_context(old).cache_identity != _pricing_context(new).cache_identity
    assert not _pricing_context(new).allows(PriceContract(
        reference="private", mechanism="sale_price", description="Personal coupon", price=1, eligibility="user_specific", personal_offer_id="private-coupon"))


@pytest.mark.parametrize("program", list(MembershipProgram))
def test_all_chains_member_offer_is_conditional_and_cache_isolated(program):
    p = prepare(product(store=program.chain, offers=[offer(kind="member", member_program=program, price=29.9)]))
    public = search(p)
    result = search(p, membership_price_policy="all_advertised")
    assert public["results"][0]["best_price"] == 49.9
    assert result["results"][0]["best_price"] == 29.9
    assert result["results"][0]["prices"][0]["membership_required"]
    assert search(p) == public


def test_real_weight_basket_without_membership_selection_keeps_audit_and_terms():
    req = PlanRequest(recipes=0, diversity_mode="cheapest", purchase_planning_mode="estimated",
        membership_price_policy="all_advertised", personal=PersonalPlanning(extras=[
            ExtraNeed(query="Satsumas", quantity=1000, unit="g", confirmed=True)]))
    plan = PersonalPlanner(req, Settings(price_provider="mock"), weight_prepare(retained()),
        {"id":"conditional", "revision":0, "items":[], "reservations":{}, "events":{}}, now=NOW).create()
    assert plan.optimized_basket.total == 22.4
    row = plan.optimized_basket.stores[0].items[0]
    assert row.membership_required and row.membership_program == "COOP_MEMBER"
    assert row.purchased_quantity == 1120
    assert plan.personal.checks["checkout_audit"]["passed"]
    assert req.memberships == {} and req.membership_programs == ()


@pytest.mark.parametrize("quantity,total", [(500,30),(1000,50),(1500,80)])
def test_member_multibuy_keeps_whole_groups_and_residual_price(quantity, total):
    from app.models.product import OfferMetadata

    from backend.tests.test_personal_planning_v2 import prepared, product, request, run
    candidate = product("bröd", 500, "g", 30, offers=[OfferMetadata(kind="multipack",
        description="2 för 50", price=50, required_packages=2, eligibility="member", membership_program="COOP_MEMBER")])
    req = request(extras=[ExtraNeed(query="bröd", quantity=quantity, unit="g", confirmed=True)])
    req.membership_price_policy = "all_advertised"
    result = run(prepared(candidate), req)
    assert result.optimized_basket.total == total
    assert result.personal.checks["checkout_audit"]["passed"]


def test_membership_price_used_by_shared_recipe_and_shopping_needs():
    from app.models.personal import MealSettings, MealSlot
    from app.models.product import OfferMetadata
    from app.models.recipe import Recipe, RecipeIngredient

    from backend.tests.test_personal_planning_v2 import prepared, product, request, run

    p = product("bröd", 500, "g", 30, offers=[OfferMetadata(kind="member", description="Medlemspris",
        price=20, eligibility="member", membership_program="COOP_MEMBER")])
    recipe = Recipe(name="Bröd till frukost", servings=1,
        ingredients=[RecipeIngredient(name="bröd", quantity=200, unit="g")], instructions=["Servera brödet."])
    req = request(slots=[MealSlot(id="breakfast-1", day=1, meal_type="breakfast", recipe=recipe)],
        meals=[MealSettings(meal_type="breakfast", count=1, servings=1)],
        extras=[ExtraNeed(query="bröd", quantity=200, unit="g", confirmed=True)])
    req.membership_price_policy = "all_advertised"
    result = run(prepared(p), req)
    assert result.optimized_basket.total == 20
    assert sum(row.packages_needed for s in result.optimized_basket.stores for row in s.items) == 1
    assert result.personal.checks["checkout_audit"]["passed"]


def test_search_api_applies_policy_to_older_clients(monkeypatch):
    from app.api import product_search as api
    from app.services.product_search import ProductSearchRequest
    from fastapi import Response

    class Index:
        def search(self, request, **kwargs):
            assert request.memberships == ()
            assert request.membership_price_policy == "all_advertised"
            return {"policy": request.membership_price_policy}

    from types import SimpleNamespace

    monkeypatch.setattr(api.GLOBAL_PREPARED_PRICE_UNIVERSES, "get_for_request", lambda *args: SimpleNamespace(product_search_index=Index()))
    assert api.search_products(ProductSearchRequest(query="kaffe"), Response())["policy"] == "all_advertised"
