from datetime import UTC, date, datetime

import pytest
from app.models.basket import BasketItem
from app.models.ingredient import NormalizedIngredient
from app.models.plan import PlanRequest
from app.models.product import Product, ProductCandidate
from app.services.basket_auditor import BasketAuditor
from app.services.basket_calculator import BasketCalculator, GroupPricingError
from app.services.basket_optimizer import BasketVerificationPolicy
from app.services.user_pricing import price_candidate_for_context

from grocery_data.app.domain.promotion_pricing import UserPricingContext

DAY = date(2026, 9, 24)


def rate(chain="willys", form="variable_package", member=False):
    return Product(
        product_id="source-ad",
        name="Gouda",
        canonical_name="gouda",
        category="ost",
        store_id="store-1",
        store_name="Butik",
        chain=chain,
        price=None,
        sale_price=49.9,
        effective_price=49.9,
        coverage="offers_only",
        semantic_confidence="high",
        offers=[
            {
                "kind": "member" if member else "campaign",
                "member_program": chain if member else None,
                "description": "Gouda ca 1,1 kg",
                "price": 49.9,
                "price_basis_unit": "kg",
                "max_quantity": 3 if form == "variable_package" else None,
                "price_contract_id": "source:household:cheese",
                "valid_from": DAY,
                "valid_to": date(2026, 9, 27),
                "campaign_evidence": {
                    "store_external_id": "1",
                    "offer_id": "ad",
                    "source_reference": "raw:ad",
                    "observed_current_at": datetime(2026, 9, 24, 7, tzinfo=UTC),
                    "checked_at": datetime(2026, 9, 24, 7, tzinfo=UTC),
                },
                "purchase_terms": {
                    "source_reference": "raw:ad",
                    "purchase_form": form,
                    "quantity_basis": "source_approximation"
                    if form == "variable_package"
                    else "requirement",
                    "approximate_package_g": 1100 if form == "variable_package" else None,
                    "limit_scope": "household_campaign",
                },
            }
        ],
    )


def quote(p, grams, mode="estimated", member=False, day=DAY):
    need = NormalizedIngredient(canonical_name="gouda", required_quantity=grams, unit="g")
    candidate = price_candidate_for_context(
        ProductCandidate.from_product(p, 1),
        UserPricingContext.from_chain_flags({p.chain: member}),
        on_date=day,
        planning_mode=mode,
    )
    return need, BasketCalculator().calculate_item(need, candidate)


@pytest.mark.parametrize("chain", ["ica", "coop", "willys", "hemkop", "citygross", "lidl"])
def test_all_chain_whole_approximate_packages_roundtrip_and_audit(chain):
    p = rate(chain)
    with pytest.raises(ValueError, match="estimated planning"):
        quote(p, 200, "exact")
    need, item = quote(p, 200)
    assert item.total_price == 54.89 and item.packages_needed == 1
    assert item.waste_quantity == 900 and item.purchased_quantity == 1100
    assert item.regular_total_price is None and not item.ordinary_price_known
    assert item.verification_status == "VERIFIED_WITH_ESTIMATES"
    assert "minst 200" in item.purchase_warning
    restored = BasketItem.model_validate_json(item.model_dump_json())
    audit = BasketAuditor(pantry_items=frozenset()).audit([need], [restored])
    assert audit.passed and audit.verification_status == "VERIFIED_WITH_ESTIMATES"
    assert Product.model_validate_json(p.model_dump_json()).purchase_terms == p.purchase_terms


def test_loose_weight_uses_requirement_and_is_estimate():
    need, item = quote(rate(form="loose_weight"), 200)
    assert item.total_price == 9.98 and item.purchased_quantity == 200
    assert item.verification_status == "VERIFIED_WITH_ESTIMATES"
    assert BasketAuditor(pantry_items=frozenset()).audit([need], [item]).passed


def test_membership_dates_and_shared_household_cap():
    p = rate(member=True)
    with pytest.raises(ValueError):
        quote(p, 200)
    with pytest.raises(ValueError):
        quote(p, 200, member=True, day=date(2026, 9, 28))
    with pytest.raises(ValueError):
        quote(p, 3400, member=True)
    _, item = quote(p, 2000, member=True)
    with pytest.raises(GroupPricingError):
        BasketCalculator.quote_group_basket([item, item.model_copy(update={"store_id": "store-2"})])


def test_critical_or_variant_uncertainty_does_not_become_estimated_purchase():
    for updates in (
        {"critical_blockers": ("unknown household limit",)},
        {"deposit_status": "unknown"},
        {"identity_scope": "campaign_group", "variant_selection": "required"},
    ):
        p = rate()
        terms = p.purchase_terms.model_copy(update=updates)
        p = p.model_copy(
            update={
                "purchase_terms": terms,
                "offers": [p.offers[0].model_copy(update={"purchase_terms": terms})],
            }
        )
        with pytest.raises(ValueError, match="completion"):
            quote(p, 200)


def test_default_mode_and_saved_user_choice():
    assert PlanRequest().purchase_planning_mode == "exact"
    request = PlanRequest(purchase_planning_mode="estimated")
    assert (
        PlanRequest.model_validate_json(request.model_dump_json()).purchase_planning_mode
        == "estimated"
    )
    assert not BasketVerificationPolicy.strict_live(
        allow_estimated_quantities=False
    ).allow_estimated_quantities


def campaign_product():
    from backend.tests.test_personal_planning_v2 import product

    return product(
        "Garant färsk pizza olika sorter",
        400,
        "g",
        None,
        store="willys",
        sale_price=33,
        effective_price=33,
        coverage="offers_only",
        offers=[
            {
                "kind": "multipack",
                "description": "3 för 99 kr; ej ekologisk",
                "price": 99,
                "required_packages": 3,
                "valid_from": date(2026, 9, 7),
                "valid_to": date(2026, 9, 27),
                "price_contract_id": "campaign:pizza",
                "campaign_evidence": {
                    "store_external_id": "willys",
                    "offer_id": "pizza",
                    "source_reference": "raw:ad",
                    "observed_current_at": datetime(2026, 9, 10, 7, tzinfo=UTC),
                    "checked_at": datetime(2026, 9, 10, 7, tzinfo=UTC),
                },
                "purchase_terms": {
                    "source_reference": "raw:ad",
                    "purchase_form": "fixed_package",
                    "identity_scope": "campaign_group",
                    "variant_selection": "required",
                    "complete_group_size": 3,
                    "exclusions": ["ej ekologisk"],
                },
            }
        ],
    )


def test_conditional_group_is_counted_whole_purchase_never_specific_or_nutrition():
    from app.models.personal import ExtraNeed, TasteProfile
    from app.services.personal_policy import PolicyConflict

    from backend.tests.test_personal_planning_v2 import key_for, prepared, request, run

    p = campaign_product()
    universe = prepared(p)
    extra = ExtraNeed(
        kind="campaign",
        query=p.name,
        quantity=1,
        unit="st",
        product_key=key_for(universe, p.name),
        confirmed=True,
    )
    result = run(universe, request(extras=[extra]))
    item = result.optimized_basket.stores[0].items[0]
    assert item.total_price == 99 and item.packages_needed == 3
    assert item.purchased_quantity == 3 and item.unit == "st" and item.gtin is None
    assert item.conditional_variant_choice and item.verification_status == "UNVERIFIED"
    assert item.regular_unit_price is None and item.regular_total_price is None
    assert result.optimized_basket.verification_status == "UNVERIFIED"
    assert (
        BasketAuditor(pantry_items=frozenset())
        .audit(result.ingredients, result.optimized_basket)
        .passed
    )
    with pytest.raises(PolicyConflict):
        run(universe, request(extras=[extra], profile=TasteProfile(allergies=["mjölk"])))
    with pytest.raises(ValueError):
        price_candidate_for_context(
            ProductCandidate.from_product(p, 1), UserPricingContext(), on_date=DAY
        )


def test_personal_api_mode_applies_to_retained_unknown_weight_row():
    from app.models.personal import ExtraNeed
    from app.services.personal_policy import PolicyConflict

    from backend.tests.test_personal_planning_v2 import key_for, prepared, product, request, run

    source = product("Gouda", 1100, "g", 15, store="willys").source_provenance
    p = rate().model_copy(
        update={
            "store_id": "willys",
            "store_name": "willys",
            "source_provenance": source,
            "offers": [rate().offers[0].model_copy(update={"valid_from": date(2026, 9, 7)})],
        }
    )
    universe = prepared(p)
    extra = ExtraNeed(
        kind="exact",
        query=p.name,
        quantity=200,
        unit="g",
        product_key=key_for(universe, p.name),
        confirmed=True,
    )
    req = request(extras=[extra])
    with pytest.raises(PolicyConflict):
        run(universe, req)
    result = run(universe, req.model_copy(update={"purchase_planning_mode": "estimated"}))
    assert result.optimized_basket.total == 54.89
    assert result.personal.checks["purchase"] == "VERIFIED_WITH_ESTIMATES"


def test_group_search_displays_full_quote_without_fabricating_residual():
    from app.services.product_search import ProductSearchRequest

    from backend.tests.test_personal_planning_v2 import NOW, prepared

    result = prepared(campaign_product()).product_search_index.search(
        ProductSearchRequest(query="pizza"), now=NOW
    )
    row = result["products"][0] if "products" in result else result["results"][0]
    price = row["prices"][0]
    assert price["quoted_price"] == 99 and price["quoted_quantity"] == 3
    assert price["effective_price"] is None and price["regular_price"] is None


def test_weight_semantics_reach_shared_matcher_without_exact_mode_authorization():
    from app.services.product_matcher import ProductMatcher

    p = rate()
    need = NormalizedIngredient(canonical_name="ost", required_quantity=200, unit="g")
    matched = ProductMatcher().match(need, [p])
    assert matched and matched[0].sale_model == "variable_weight_package"
    with pytest.raises(ValueError):
        price_candidate_for_context(matched[0], UserPricingContext(), on_date=DAY)


def test_measured_purchase_is_required_and_retained_in_private_ledger(tmp_path):
    from app.models.personal import ExtraNeed
    from app.services.personal_store import PersonalConflict, PersonalStore
    from app.services.plan_store import PlanStore

    from backend.tests.test_personal_planning_v2 import key_for, prepared, product, request, run

    source = product("Gouda", 1100, "g", 15, store="willys").source_provenance
    p = rate().model_copy(
        update={
            "store_id": "willys",
            "store_name": "willys",
            "source_provenance": source,
            "offers": [rate().offers[0].model_copy(update={"valid_from": date(2026, 9, 7)})],
        }
    )
    pu = prepared(p)
    extra = ExtraNeed(
        kind="exact",
        query=p.name,
        quantity=200,
        unit="g",
        product_key=key_for(pu, p.name),
        confirmed=True,
    )
    req = request(extras=[extra]).model_copy(update={"purchase_planning_mode": "estimated"})
    result = run(pu, req)
    store = PlanStore(tmp_path / "plans.sqlite")
    owner = "a" * 64
    saved = store.create(req, result, owner_actor_hash=owner)
    private = PersonalStore(store)
    revision = private.read(owner)["revision"]
    with pytest.raises(PersonalConflict, match="verklig"):
        private.inventory_action(owner, saved, "purchase", revision)
    item = result.optimized_basket.stores[0].items[0]
    key = item.store_id + "|" + item.product_id + "|" + item.ingredient
    state = private.inventory_action(
        owner, saved, "purchase", revision, measured_purchase_quantities={key: 1030}
    )
    assert state["items"][0]["quantity"] == 1030
    assert state["ledger"][0]["rows"][0]["checkout"]["quantity_confidence"] == "estimated"
    assert store.get(saved.plan_id).request.purchase_planning_mode == "estimated"


def test_open_campaign_never_borrows_specific_product_nutrition():
    from types import SimpleNamespace

    from app.services.offer_catalog_facts import eligible
    from app.services.official_product_facts import declared_facts
    from app.services.personal_planner import PersonalPlanner

    p = campaign_product()
    assert not eligible(p) and not declared_facts([p])
    planner = SimpleNamespace(
        source_facts=lambda _: (_ for _ in ()).throw(
            AssertionError("must not look up a specific variant")
        )
    )
    assert PersonalPlanner._nutrition_evidence(planner, p, p.name, "g", {"protein_g"}, None) is None


def test_source_group_cannot_smuggle_private_confirmation():
    p = campaign_product().model_dump(exclude={"verification_status"})
    p["conditional_variant_choice"] = True
    with pytest.raises(ValueError, match="private request"):
        Product.model_validate(p)
