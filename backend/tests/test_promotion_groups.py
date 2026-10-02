"""Explicit SYNTHETIC group contracts; these are not live retailer campaigns."""

from datetime import date

import pytest
from app.models.personal import ExtraNeed
from app.models.product import OfferMetadata, PromotionGroup
from app.services.basket_auditor import BasketAuditor

from backend.tests.test_personal_planning_v2 import prepared, product, request, run
from grocery_data.app.domain.promotion_pricing import UserPricingContext


def group(**overrides):
    return PromotionGroup(
        **{
            "group_id": "synthetic-choice-3",
            "chain": "coop",
            "store_id": "coop",
            "eligible_product_ids": ("mjölk", "bröd", "ris"),
            "required_packages": 3,
            "pricing_rule": "fixed_total",
            "amount": 75,
            "valid_from": date(2026, 9, 1),
            "valid_to": date(2026, 10, 1),
            "source": "own",
            "source_snapshot_id": "v2-frozen",
            **overrides,
        }
    )


def extras(count=1):
    return [
        ExtraNeed(query=n, quantity=1000 * count, unit=u, confirmed=True)
        for n, u in [("mjölk", "ml"), ("bröd", "g"), ("ris", "g")]
    ]


def catalog(*groups, extra_offers=()):
    return prepared(
        *[
            product(
                n,
                1000,
                u,
                30,
                promotion_groups=groups,
                offers=list(extra_offers) if n == "mjölk" else [],
            )
            for n, u in [("mjölk", "ml"), ("bröd", "g"), ("ris", "g")]
        ]
    )


def test_three_explicit_group_items_for_75_whole_basket_and_audit():
    result = run(catalog(group()), request(extras=extras()))
    basket = result.optimized_basket
    assert basket.total == 75
    rows = basket.stores[0].items
    assert [i.total_price for i in rows] == [25, 25, 25]
    assert all(len(i.group_applications) == 1 for i in rows)
    applied = rows[0].group_applications[0]
    assert sum(r["packages"] for r in applied["contributors"]) == 3
    assert BasketAuditor(pantry_items=frozenset()).audit(result.ingredients, basket).passed
    corrupt = basket.model_copy(
        update={
            "stores": [
                basket.stores[0].model_copy(
                    update={
                        "items": [rows[0].model_copy(update={"group_applications": []}), *rows[1:]]
                    }
                )
            ]
        }
    )
    assert not BasketAuditor(pantry_items=frozenset()).audit(result.ingredients, corrupt).passed


def test_group_cost_participates_in_candidate_ranking_and_safe_bounds():
    from decimal import Decimal

    from app.models.ingredient import NormalizedIngredient
    from app.models.product import ProductCandidate
    from app.services.basket_optimizer import BasketOptimizer

    p = catalog(group())
    candidates = {
        v.name: [ProductCandidate.from_product(v, match_score=1)] for v in p.universe.products
    }
    needs = [
        NormalizedIngredient(canonical_name=n, required_quantity=1000, unit=u)
        for n, u in (("mjölk", "ml"), ("bröd", "g"), ("ris", "g"))
    ]
    optimizer = BasketOptimizer()
    assert optimizer.same_depth_nested_store_limited_keys(
        needs, candidates, p.stores, max_stores=2
    )[0][1] == Decimal(75)
    assert optimizer.same_depth_nested_store_limited_requirement_keys(
        [(n.canonical_name, n.required_quantity, n.unit) for n in needs],
        candidates,
        p.stores,
        max_stores=2,
    )[0][1] == Decimal(75)
    assert optimizer.optimistic_relaxed_key(needs, candidates, allowed_store_ids=["coop"])[1] == 0


def test_below_threshold_caps_and_expired_groups():
    assert run(catalog(group()), request(extras=extras()[:2])).optimized_basket.total == 60
    assert (
        run(catalog(group(max_groups=1)), request(extras=extras(2))).optimized_basket.total == 165
    )

    assert (
        run(
            catalog(group(valid_to=date(2026, 9, 9))), request(extras=extras())
        ).optimized_basket.total
        == 90
    )


def test_large_group_basket_is_explicitly_blocked_before_recursion():
    from app.services.basket_calculator import BasketCalculator, GroupPricingError
    basket = run(catalog(group()), request(extras=extras())).optimized_basket
    items = [i.model_copy(update={"packages_needed": 1000}) for i in basket.stores[0].items]
    with pytest.raises(GroupPricingError, match="500"):
        BasketCalculator.quote_group_basket(items)


def test_competing_groups_and_single_product_offer_never_share_units():
    other = group(
        group_id="synthetic-pair", required_packages=2, pricing_rule="group_discount", amount=35
    )
    # 2 for 25 plus remaining 30 beats 3 for 75.
    assert run(catalog(group(), other), request(extras=extras())).optimized_basket.total == 55
    # Cheap standalone milk cannot also contribute to 3 for 75.
    offer = OfferMetadata(kind="campaign", description="synthetic milk", price=1)
    assert (
        run(catalog(group(), extra_offers=[offer]), request(extras=extras())).optimized_basket.total
        == 61
    )


def test_group_membership_is_projected_and_audited():
    p = catalog(group(membership_program="COOP_MEMBER"))
    req = request(extras=extras())
    assert run(p, req).optimized_basket.total == 90
    req.memberships = {"coop": True}
    result = run(p, req)
    assert result.optimized_basket.total == 75
    auditor = BasketAuditor(pantry_items=frozenset())
    assert not auditor.audit(result.ingredients, result.optimized_basket).passed
    assert auditor.audit(
        result.ingredients,
        result.optimized_basket,
        user_pricing_context=UserPricingContext.from_chain_flags({"coop": True}),
    ).passed


def test_group_identity_context_and_conflicts_fail_closed():
    with pytest.raises(ValueError, match="source evidence"):
        run(catalog(group(store_id="other")), request(extras=extras()))
    with pytest.raises(ValueError, match="Conflicting"):
        run(catalog(group(), group(amount=60)), request(extras=extras()))


def test_explicit_group_membership_on_one_source_row_still_selects_joint_winner():
    p = prepared(
        product("mjölk", 1000, "ml", 30, promotion_groups=(group(amount=40),)),
        product("bröd", 1000, "g", 30),
        product("ris", 1000, "g", 30),
        product("ris", 1000, "g", 20, identity="outside-group"),
    )
    result = run(p, request(extras=extras()))
    assert result.optimized_basket.total == 40
    assert {i.product_id for g in result.optimized_basket.stores for i in g.items} == {
        "mjölk",
        "bröd",
        "ris",
    }


def test_zero_cost_purchases_still_require_physical_purchase_confirmation(tmp_path):
    from app.services.personal_store import PersonalConflict, PersonalStore
    from app.services.plan_store import PlanStore

    p = catalog(group(pricing_rule="group_discount", amount=90))
    req = request(extras=extras())
    result = run(p, req)
    assert result.optimized_basket.total == 0
    store = PlanStore(tmp_path / "plans.sqlite")
    private, owner = PersonalStore(store), "a" * 64
    saved = store.create(req, result, owner_actor_hash=owner)
    state = private.read(owner)
    with pytest.raises(PersonalConflict, match="verkligt inköp"):
        private.inventory_action(owner, saved, "consume", state["revision"])
    bought = private.inventory_action(owner, saved, "purchase", state["revision"])
    assert sum(i["quantity"] for i in bought["items"]) == 3000
    assert bought["ledger"][0]["total"] == 0


def test_other_context_and_existing_pantry_do_not_qualify_for_group():
    from app.models.personal import PantryItem

    from backend.tests.test_personal_planning_v2 import state

    needs = extras()
    needs[0].use_pantry = True
    result = run(
        catalog(group()),
        request(extras=needs),
        state([PantryItem(name="mjölk", quantity=1000, unit="ml")]),
    )
    assert result.optimized_basket.total == 60
    assert not any(i.group_applications for g in result.optimized_basket.stores for i in g.items)
    p = prepared(
        product("mjölk", 1000, "ml", 30, promotion_groups=(group(amount=40),)),
        product("bröd", 1000, "g", 30),
        product("ris", 1000, "g", 10, store="ica"),
    )
    assert run(p, request(extras=extras())).optimized_basket.total == 70


def test_fixed_group_works_with_campaign_prices_without_inventing_ordinary_price():
    # Exact identified variants can mix using explicit group membership even
    # when their independent current purchases are campaigns, not base prices.
    rows=[]
    for name,unit in [('mjölk','ml'),('bröd','g'),('ris','g')]:
        rows.append(product(name,1000,unit,None,sale_price=30,effective_price=30,
            promotion_groups=(group(),),offers=[OfferMetadata(kind='campaign',description='Aktuellt kampanjköp',price=30,
                valid_from=date(2026,9,1),valid_to=date(2026,10,1))]))
    result=run(prepared(*rows),request(extras=extras()))
    assert result.optimized_basket.total==75
    assert all(i.regular_unit_price is None for g in result.optimized_basket.stores for i in g.items)
    assert BasketAuditor(pantry_items=frozenset()).audit(result.ingredients,result.optimized_basket).passed
    # A discount off an unknown base may not masquerade as a fixed total.
    bad=group(pricing_rule='group_discount',amount=15)
    with pytest.raises(ValueError,match='No complete basket'):
        run(prepared(*[p.model_copy(update={'promotion_groups':(bad,)}) for p in rows]),request(extras=extras()))


def test_mixed_variants_share_whole_campaign_when_no_single_purchase_is_evidenced():
    from grocery_data.app.domain.purchase_terms import PurchaseTerms
    rows=[]
    for name,unit in [('mjölk','ml'),('bröd','g'),('ris','g')]:
        terms=PurchaseTerms(source_reference='synthetic:verified-membership',purchase_form='fixed_package',complete_group_size=3)
        rows.append(product(name,1000,unit,None,sale_price=None,effective_price=25,
            promotion_groups=(group(),),offers=[OfferMetadata(kind='multipack',description='Tre valfria verifierade varianter',price=75,required_packages=3,
                purchase_terms=terms,valid_from=date(2026,9,1),valid_to=date(2026,10,1))]))
    result=run(prepared(*rows),request(extras=extras()))
    basket=result.optimized_basket
    assert basket.total==75 and sum(i.packages_needed for g in basket.stores for i in g.items)==3
    assert all(i.regular_unit_price is None and not i.pending_group_checkout for g in basket.stores for i in g.items)
    assert BasketAuditor(pantry_items=frozenset()).audit(result.ingredients,basket).passed
    completed=run(prepared(*rows),request(extras=extras()[:2]))
    assert completed.optimized_basket.total==75
    assert sum(i.packages_needed for g in completed.optimized_basket.stores for i in g.items)==3
    assert BasketAuditor(pantry_items=frozenset()).audit(completed.ingredients,completed.optimized_basket).passed
    # Dates/membership still restrict the group even on the offers-only early path.
    for bad in (group(valid_to=date(2026,9,2)),group(membership_program='COOP_MEMBER')):
        result=run(prepared(*[p.model_copy(update={'promotion_groups':(bad,)}) for p in rows]),request(extras=extras()))
        assert result.optimized_basket.total==225  # three complete independent groups


def test_shared_household_group_cap_is_aggregated_across_stores_and_survives_audit():
    from app.services.basket_calculator import BasketCalculator
    g=group(max_groups=1,limit_scope='household_campaign',limit_key='official-campaign-household')
    result=run(catalog(g),request(extras=extras()))
    first=result.optimized_basket.stores[0].items
    second=[i.model_copy(update={'store_id':'coop-2','ingredient':i.ingredient+' second store',
        'promotion_groups':(g.model_copy(update={'store_id':'coop-2'}),),'group_applications':[]}) for i in first]
    rows=BasketCalculator.quote_group_basket([*first,*second])
    assert sum(i.total_price for i in rows)==165  # one 75 group, remaining three ordinary at 30
    applications={a['application'] for i in rows for a in i.group_applications}
    assert len(applications)==1
    assert all(i.promotion_groups[0].limit_key=='official-campaign-household' for i in rows)
    bad=g.model_copy(update={'valid_to':date(2026,9,2)})
    with pytest.raises(ValueError,match='campaign dates'):
        BasketCalculator.quote_group_basket([i.model_copy(update={'promotion_groups':(bad,)}) for i in first])


@pytest.mark.parametrize("entry", ["basket", "nested", "requirements", "single", "relaxed"])
def test_unrequested_offer_aliases_do_not_trigger_joint_cartesian_search(entry, monkeypatch):
    """The municipal pool is larger than the actual basket's ingredient set."""
    from app.models.ingredient import NormalizedIngredient
    from app.models.product import ProductCandidate
    from app.services.basket_optimizer import BasketOptimizer

    p = catalog()
    candidates = {v.name: [ProductCandidate.from_product(v, match_score=1)] for v in p.universe.products}
    unrelated = candidates["ris"][0].model_copy(update={
        "price": None, "product_id": "unrequested-product",
        "offers": [OfferMetadata(kind="campaign", description="Synthetic cap", price=20, max_quantity=1)],
    })
    expanded = {**candidates, "unrequested-a": [unrelated], "unrequested-b": [unrelated]}
    needs = [NormalizedIngredient(canonical_name="ris", required_quantity=1000, unit="g")]
    optimizer = BasketOptimizer()

    def calculate(rows):
        if entry == "basket":
            return optimizer.optimize(needs, rows, p.stores, 3)
        if entry == "nested":
            return optimizer.same_depth_nested_store_limited_keys(needs, rows, p.stores, max_stores=3)
        if entry == "requirements":
            return optimizer.same_depth_nested_store_limited_requirement_keys([("ris", 1000, "g")], rows, p.stores, max_stores=3)
        if entry == "single":
            return optimizer.single_store_options(needs, rows, p.stores)
        return optimizer.optimistic_relaxed_key(needs, rows, allowed_store_ids=[s.store_id for s in p.stores])

    expected = calculate(candidates)
    def no_unrelated_cartesian_search(*args, **kwargs):
        raise AssertionError("Unrequested offer aliases trigger Cartesian checkout")
    monkeypatch.setattr(optimizer, "_optimize_promotion_groups", no_unrelated_cartesian_search)
    assert calculate(expanded) == expected


def test_nested_caps_share_one_exact_group_search(monkeypatch):
    from app.models.ingredient import NormalizedIngredient
    from app.models.product import ProductCandidate
    from app.services.basket_optimizer import BasketOptimizer
    p = catalog(group())
    candidates = {v.name: [ProductCandidate.from_product(v, match_score=1)] for v in p.universe.products}
    needs = [NormalizedIngredient(canonical_name=v.name, required_quantity=1000, unit=v.package_unit) for v in p.universe.products]
    stores = [p.stores[0], p.stores[0].model_copy(update={"store_id":"unused-2"}), p.stores[0].model_copy(update={"store_id":"unused-3"})]
    optimizer = BasketOptimizer()
    expected = tuple(optimizer.same_depth_store_limited_key(needs, candidates, stores, max_stores=cap) for cap in (1, 2, 3))
    original = optimizer._optimize_promotion_groups
    calls = []
    def counted(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)
    monkeypatch.setattr(optimizer, "_optimize_promotion_groups", counted)
    assert optimizer.same_depth_nested_store_limited_keys(needs, candidates, stores, max_stores=3) == expected
    assert len(calls) == 1, "Nested caps must share the same exact Cartesian enumeration"


def test_group_budget_fallback_uses_identical_compact_nested_keys(monkeypatch):
    from app.models.ingredient import NormalizedIngredient
    from app.models.product import ProductCandidate
    from app.services import basket_optimizer as module
    p = catalog(group())
    candidates = {}
    for value in p.universe.products:
        offer = ProductCandidate.from_product(value, match_score=1).model_copy(update={"coverage":"offers_only"})
        base = offer.model_copy(update={"product_id":value.product_id+"-base", "promotion_groups":(), "coverage":"full", "price":40})
        candidates[value.name] = (offer, base)
    needs = [NormalizedIngredient(canonical_name=v.name, required_quantity=1000, unit=v.package_unit) for v in p.universe.products]
    stores = [p.stores[0], p.stores[0].model_copy(update={"store_id":"unused-2"}), p.stores[0].model_copy(update={"store_id":"unused-3"})]
    monkeypatch.setattr(module, "_MAX_GROUP_COMBINATIONS", 0)
    optimizer = module.BasketOptimizer()
    expected = tuple(optimizer.same_depth_store_limited_key(needs, candidates, stores, max_stores=cap) for cap in (1, 2, 3))
    def no_materialized_checkout(*args, **kwargs):
        raise AssertionError("Ranking must reuse compact keys for the existing base fallback")
    monkeypatch.setattr(optimizer, "optimize", no_materialized_checkout)
    with optimizer.quote_cache() as stats:
        assert optimizer.same_depth_nested_store_limited_keys(needs, candidates, stores, max_stores=3) == expected
        misses = stats.subset_vector_misses
        assert misses > 0, "Verified base rows must retain immutable quote-cache eligibility"
        assert optimizer.same_depth_nested_store_limited_keys(needs, candidates, stores, max_stores=3) == expected
        assert stats.subset_vector_misses == misses
        assert stats.subset_vector_hits > 0
