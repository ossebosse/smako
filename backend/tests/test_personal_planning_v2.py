"""Frozen, combined personal-planning contracts; no network/provider calls."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from app.config import Settings
from app.models import PlanRequest, Product, Store
from app.models.personal import (
    ExtraNeed,
    MealSettings,
    MealSlot,
    PantryItem,
    PersonalPlanning,
    TasteProfile,
)
from app.models.product import OfferMetadata
from app.models.provenance import SourceProvenance
from app.models.recipe import Recipe, RecipeIngredient
from app.services.economic_ingredient_selector import EconomicIngredientPool
from app.services.personal_planner import PersonalPlanner
from app.services.personal_policy import PolicyConflict, ProductFacts, interpret_profile
from app.services.personal_store import PersonalConflict, PersonalStore, available_items
from app.services.plan_store import PlanStore
from app.services.price_universe import PriceUniverseBuilder, PriceUniverseKey
from app.services.price_universe_runtime import PreparedPriceUniverse

NOW = datetime(2026, 9, 10, 18, tzinfo=UTC)


def product(name, quantity, unit, price, *, identity=None, store="coop", **extra):
    return Product(
        name=name,
        product_id=identity or name,
        canonical_name=name,
        category="mat",
        store_id=store,
        store_name=store,
        chain=store,
        price=price,
        package_quantity=quantity,
        package_unit=unit,
        quantity_confidence="exact",
        semantic_confidence="exact",
        source_provenance=SourceProvenance(
            source_provider="own",
            source_channel="catalog",
            source_snapshot_id="v2-frozen",
            source_observed_at=NOW,
            store_id=store,
        ),
        **extra,
    )


def prepared(*products):
    universe = PriceUniverseBuilder().build(
        PriceUniverseKey.create(
            city="Lund",
            postal_codes=["22350"],
            snapshot_ids=["v2-frozen"],
            source_strategy_version="fixture",
            normalizer_version="v1",
            taxonomy_version="v1",
        ),
        products,
        built_at=NOW,
    )
    return PreparedPriceUniverse(
        universe=universe,
        stores=tuple(
            Store(store_id=s, name=s, chain=s, city="Lund")
            for s in sorted({p.store_id for p in products})
        ),
        economic_pool=EconomicIngredientPool(),
        source_name="frozen",
    )


def key_for(p, name):
    return next(
        k
        for k, indices in p.product_search_index.groups.items()
        if p.universe.products[indices[0]].name == name
    )


def recipe(name="Mjölk och bröd", servings=1, ingredients=None):
    return Recipe(
        name=name,
        servings=servings,
        ingredients=ingredients
        or [
            RecipeIngredient(name="mjölk", quantity=200, unit="ml"),
            RecipeIngredient(name="bröd", quantity=80, unit="g"),
        ],
        instructions=["Servera tillsammans."],
    )


def state(items=()):
    return {
        "id": "test-state",
        "revision": 0,
        "profile": None,
        "items": [i.model_dump() for i in items],
        "reservations": {},
        "events": {},
    }


def request(*, extras=(), slots=(), meals=None, **kwargs):
    return PlanRequest(
        recipes=0,
        diversity_mode="cheapest",
        max_stores=2,
        personal=PersonalPlanning(
            extras=list(extras), slots=list(slots), meals=meals or [], **kwargs
        ),
    )


def run(p, req, inventory=None, **kwargs):
    return PersonalPlanner(
        req, Settings(price_provider="mock"), p, inventory or state(), now=NOW, **kwargs
    ).create()


def test_generic_and_exact_without_recipes_share_whole_store_cap():
    p = prepared(
        product("mjölk 1,5 %", 1000, "ml", 15),
        product("mjölk 3 %", 1000, "ml", 9),
        product("ICA Basic servetter", 50, "st", 20, store="ica"),
    )
    extra = ExtraNeed(
        query="mjölk 1,5 %", quantity=1200, unit="ml", properties=["1,5 %"], confirmed=True
    )
    exact = ExtraNeed(
        kind="exact",
        query="ICA Basic servetter",
        product_key=key_for(p, "ICA Basic servetter"),
        quantity=1,
        unit="st",
        food=False,
        confirmed=True,
    )
    req = request(extras=[extra, exact])
    result = run(p, req)
    assert result.portions == 0 and result.recipes == []
    assert result.optimized_basket.total == 50
    assert result.optimized_basket.store_count == 2
    with pytest.raises(Exception, match="complete basket"):
        run(p, req.model_copy(update={"max_stores": 1}))


def test_dinner_breakfast_snack_extra_partial_stock_and_idempotent_lifecycle(tmp_path):
    p = prepared(product("mjölk", 1000, "ml", 20), product("bröd", 500, "g", 25))
    slots = [
        MealSlot(id=t, day=1, meal_type=t, recipe=recipe())
        for t in ("dinner", "breakfast", "snack")
    ]
    meals = [
        MealSettings(meal_type=t, count=1, servings=1) for t in ("dinner", "breakfast", "snack")
    ]
    req = request(
        slots=slots,
        meals=meals,
        extras=[ExtraNeed(query="mjölk", quantity=600, unit="ml", confirmed=True)],
    )
    plans = PlanStore(tmp_path / "plans.sqlite3")
    private, owner = PersonalStore(plans), "a" * 64
    stock = private.update_pantry(
        owner, 0, [PantryItem(id="milk", name="mjölk", quantity=300, unit="ml")]
    )
    req.personal.pantry_revision = stock["revision"]
    result = run(p, req, stock)
    assert result.optimized_basket.total == 45
    assert sum(a["quantity"] for a in result.personal.allocations) == 300
    assert sum(s["quantity"] for s in result.personal.future_surplus if s["unit"] == "ml") == 100
    saved = plans.create(req, result, owner_actor_hash=owner)
    reserved = private.read(owner)
    assert reserved["items"][0]["quantity"] == 300  # creation NEVER buys stock
    assert available_items(reserved)[0]["available"] == 0
    purchased = private.inventory_action(owner, saved, "purchase", reserved["revision"])
    replay = private.inventory_action(owner, saved, "purchase", reserved["revision"])
    assert replay == purchased
    assert sum(i["quantity"] for i in purchased["items"] if i["unit"] == "ml") == 1300
    consumed = private.inventory_action(owner, saved, "consume", purchased["revision"])
    assert sum(i["quantity"] for i in consumed["items"] if i["unit"] == "ml") == 100
    assert private.inventory_action(owner, saved, "consume", purchased["revision"]) == consumed
    assert plans.get_owned(saved.plan_id, owner_actor_hash=owner).revision == 1


def test_concurrent_stock_revision_preserves_plan_and_inventory(tmp_path):
    p = prepared(product("mjölk", 1000, "ml", 20))
    plans = PlanStore(tmp_path / "plans.sqlite3")
    private, owner = PersonalStore(plans), "b" * 64
    req = request(extras=[ExtraNeed(query="mjölk", quantity=200, unit="ml", confirmed=True)])
    result = run(p, req)
    private.update_pantry(owner, 0, [PantryItem(name="mjölk", quantity=100, unit="ml")])
    with pytest.raises(PersonalConflict):
        plans.create(req, result, owner_actor_hash=owner)
    assert plans.owned_plan_ids(owner_actor_hash=owner) == ()
    assert private.read(owner)["items"][0]["quantity"] == 100


def test_unknown_allergy_and_exclusion_fail_closed():
    p = prepared(product("bröd", 500, "g", 25))
    extra = ExtraNeed(query="bröd", quantity=100, unit="g", confirmed=True)
    for profile in (
        TasteProfile(allergies=["jordnötter"]),
        TasteProfile(allergies=["okänd allergi"]),
        TasteProfile(exclusions=["koriander"]),
    ):
        with pytest.raises(PolicyConflict) as exc:
            run(p, request(extras=[extra], profile=profile))
        assert exc.value.code == "DATA_BLOCKED"
    with pytest.raises(PolicyConflict, match="hårda val"):
        run(p, request(extras=[extra], profile=TasteProfile(exclusions=["bröd"])))


def test_source_supported_allergy_checks_compound_products_and_trace():
    p = prepared(product("bröd", 500, "g", 25))
    facts = ProductFacts(
        source="frozen manufacturer label",
        source_product_id="bröd",
        source_snapshot_id="v2-frozen",
        ingredients_complete=True,
        ingredients=("vete", "vatten"),
        allergens_checked=("jordnötter",),
    )
    req = request(
        extras=[ExtraNeed(query="bröd", quantity=100, unit="g", confirmed=True)],
        profile=TasteProfile(allergies=["jordnötter"]),
    )
    assert run(p, req, facts={("coop", "bröd"): facts}).personal.checks["allergy"] == "VERIFIED"
    from dataclasses import replace

    with pytest.raises(PolicyConflict, match="spår"):
        run(p, req, facts={("coop", "bröd"): replace(facts, allergens_trace=("jordnötter",))})


def test_profile_interpretation_preserves_uncertainty_and_separates_soft_hard():
    parsed = interpret_profile(
        "Gillar kyckling, ogillar koriander, måste undvika jordnötter, kanske annat"
    )
    assert parsed["profile"]["likes"] == ["kyckling"]
    assert parsed["profile"]["dislikes"] == ["koriander"]
    assert parsed["profile"]["exclusions"] == ["jordnötter"]
    assert parsed["unresolved"] == ["kanske annat"]


def test_organic_cost_share_includes_food_extras_after_discount_excludes_nonfood():
    p = prepared(
        product("mjölk", 1000, "ml", 20),
        product("bröd", 500, "g", 25),
        product("servetter", 50, "st", 100),
    )
    facts = {
        ("coop", "mjölk"): ProductFacts(
            source="label",
            source_product_id="mjölk",
            source_snapshot_id="v2-frozen",
            organic=True,
            animal=True,
        )
    }
    req = request(
        extras=[
            ExtraNeed(query=n, quantity=1, unit=u, confirmed=True)
            for n, u in (("mjölk", "ml"), ("bröd", "g"), ("servetter", "st"))
        ],
        organic_percent=40,
    )
    result = run(p, req, facts=facts)
    assert result.optimized_basket.total == 145
    assert result.personal.checks["organic_cost_percent"] == pytest.approx(20 / 45 * 100)
    req.personal.organic_percent = 50
    with pytest.raises(PolicyConflict):
        run(p, req, facts=facts)


def test_selected_nutrition_limit_never_uses_unknown_as_zero():
    from app.models.personal import PortionLimits

    meal = MealSettings(
        meal_type="breakfast", count=1, servings=1, limits=PortionLimits(max_fat_g=20)
    )
    req = request(
        slots=[MealSlot(id="b", day=1, meal_type="breakfast", recipe=recipe())], meals=[meal]
    )
    p = prepared(product("mjölk", 1000, "ml", 20), product("bröd", 500, "g", 25))
    with pytest.raises(PolicyConflict) as exc:
        run(p, req)
    assert exc.value.code == "DATA_BLOCKED"


@pytest.mark.parametrize(
    "quantity,member,total",
    [(500, False, 30), (1000, False, 60), (500, True, 30), (1000, True, 50)],
)
def test_multibuy_threshold_and_membership(quantity, member, total):
    offer = OfferMetadata(
        kind="multipack",
        description="2 för 50 kr – kräver köp av 2",
        price=50,
        required_packages=2,
        eligibility="member",
        membership_program="COOP_MEMBER",
    )
    p = prepared(product("bröd", 500, "g", 30, offers=[offer]))
    req = request(extras=[ExtraNeed(query="bröd", quantity=quantity, unit="g", confirmed=True)])
    req = req.model_copy(update={"memberships": {"coop": member}})
    result = run(p, req)
    assert result.optimized_basket.total == total
    assert len(result.personal.needs[0]["unused_source_offers"]) == (
        0 if member and quantity == 1000 else 1
    )
    assert result.personal.checks["same_menu_comparisons"][0]["total"] == total


def test_strategic_extra_packages_require_opt_in_and_are_audited():
    offer = OfferMetadata(kind="multipack", description="2 för 32", price=32, required_packages=2)
    p = prepared(product("bröd", 500, "g", 30, offers=[offer]))
    req = request(extras=[ExtraNeed(query="bröd", quantity=100, unit="g", confirmed=True)])
    minimal = run(p, req)
    assert minimal.optimized_basket.total == 30
    req.personal.surplus_mode = "allow_larger"
    strategic = run(p, req)
    item = strategic.optimized_basket.stores[0].items[0]
    assert strategic.optimized_basket.total == 32
    assert item.packages_needed == 2 and item.required_quantity == 100
    assert item.waste_quantity == 900
    assert strategic.personal.larger_purchase_cost == 2
    assert (
        not PersonalPlanner(req, Settings(), p, state(), now=NOW)
        .auditor.audit(strategic.ingredients, strategic.optimized_basket)
        .passed
    )


def test_nutrition_is_per_portion_and_rechecked_after_servings_change():
    from app.models.personal import PortionLimits

    p = prepared(product("mjölk", 1000, "ml", 20), product("bröd", 500, "g", 25))
    facts = {
        (p.store_id, p.product_id): ProductFacts(
            source="frozen label",
            source_product_id=p.product_id,
            source_snapshot_id="v2-frozen",
            nutrition_unit=p.package_unit,
            nutrition_basis="per_100_as_sold",
            nutrition={"protein_g": 3.4 if p.name == "mjölk" else 9.0},
        )
        for p in p.universe.products
    }
    meal = MealSettings(
        meal_type="breakfast",
        count=1,
        servings=1,
        limits=PortionLimits(min_protein_g=10, max_protein_g=15),
    )
    req = request(
        slots=[MealSlot(id="b", day=1, meal_type="breakfast", recipe=recipe())], meals=[meal]
    )
    result = run(p, req, facts=facts)
    assert result.personal.checks["nutrition"][0]["values"]["protein_g"] == pytest.approx(14)
    req.personal.slots[0].recipe = req.personal.slots[0].recipe.model_copy(update={"servings": 2})
    with pytest.raises(PolicyConflict, match="per portion"):
        run(p, req, facts=facts)
    req.personal.slots[0].recipe = recipe()
    req.personal.meals[0].limits.min_weight_g = 200
    with pytest.raises(PolicyConflict, match="tillagningsutbyte"):
        run(p, req, facts=facts)


def test_organic_animals_includes_eggs_and_dairy_and_unknown_composites():
    p = prepared(product("ägg", 6, "st", 25), product("mjölk", 1000, "ml", 20))
    facts = {
        (p.store_id, p.product_id): ProductFacts(
            source="label",
            source_product_id=p.product_id,
            source_snapshot_id="v2-frozen",
            animal=True,
            organic=False,
        )
        for p in p.universe.products
    }
    for n, u in (("ägg", "st"), ("mjölk", "ml")):
        req = request(
            extras=[ExtraNeed(query=n, quantity=1, unit=u, confirmed=True)], organic_animals=True
        )
        with pytest.raises(PolicyConflict, match="animalier"):
            run(p, req, facts=facts)


def test_pantry_unit_isolation_unusable_and_multiple_plan_reservations(tmp_path):
    p = prepared(product("mjölk", 1000, "ml", 20))
    plans = PlanStore(tmp_path / "plans.sqlite3")
    owner = "c" * 64
    private = PersonalStore(plans)
    stock = private.update_pantry(
        owner,
        0,
        [
            PantryItem(name="mjölk", quantity=1000, unit="g"),
            PantryItem(id="bad", name="mjölk", quantity=1000, unit="ml", unusable=True),
            PantryItem(id="good", name="mjölk", quantity=300, unit="ml"),
        ],
    )
    extra = ExtraNeed(query="mjölk", quantity=300, unit="ml", use_pantry=True, confirmed=True)
    req = request(extras=[extra], pantry_revision=stock["revision"])
    result = run(p, req, stock)
    assert result.optimized_basket.total == 0
    saved = plans.create(req, result, owner_actor_hash=owner)
    stock = private.read(owner)
    req.personal.pantry_revision = stock["revision"]
    second = run(p, req, stock)
    assert second.optimized_basket.total == 20
    assert second.personal.allocations == []
    private.inventory_action(owner, saved, "release", stock["revision"])
    assert next(i for i in private.read(owner)["items"] if i["id"] == "good")["quantity"] == 300


def test_free_text_canonical_spoof_cannot_bypass_exclusion():
    p = prepared(product("mjölk", 1000, "ml", 20), product("bröd", 500, "g", 25))
    bad = recipe(
        ingredients=[
            RecipeIngredient(name="jordnötter", canonical_name="bröd", quantity=100, unit="g")
        ]
    )
    req = request(
        slots=[MealSlot(id="b", day=1, meal_type="breakfast", recipe=bad)],
        meals=[MealSettings(meal_type="breakfast", count=1)],
        profile=TasteProfile(exclusions=["jordnötter"]),
    )
    with pytest.raises(PolicyConflict, match="uteslutning"):
        run(p, req)


def test_recipe_edit_keeps_revision_on_failure_and_all_other_slots(tmp_path):
    p = prepared(product("mjölk", 1000, "ml", 20), product("bröd", 500, "g", 25))
    slots = [MealSlot(id=f"b{i}", day=i, meal_type="breakfast", recipe=recipe()) for i in (1, 2)]
    req = request(slots=slots, meals=[MealSettings(meal_type="breakfast", count=2)])
    plans = PlanStore(tmp_path / "plans.sqlite3")
    owner = "d" * 64
    private = PersonalStore(plans)
    first = plans.create(req, run(p, req), owner_actor_hash=owner)
    before = first.plan.model_dump_json()
    stock = private.read(owner)
    spec = req.personal.model_copy(deep=True)
    spec.pantry_revision = stock["revision"]
    spec.slots[0].recipe = recipe(name="Redigerat recept", servings=2)
    new_req = req.model_copy(update={"personal": spec})
    result = run(p, new_req, stock, plan_id=first.plan_id)
    second = plans.append(
        plan_id=first.plan_id,
        request=new_req,
        response=result,
        operation="recipe_replaced",
        expected_parent=1,
        owner_actor_hash=owner,
    )
    assert second.plan.personal.slots[1] == first.plan.personal.slots[1]
    assert (
        plans.get_owned(first.plan_id, owner_actor_hash=owner, revision=1).plan.model_dump_json()
        == before
    )
    with pytest.raises(PermissionError):
        plans.get_owned(first.plan_id, owner_actor_hash="e" * 64)
    with pytest.raises(PersonalConflict):
        plans.append(
            plan_id=first.plan_id,
            request=new_req,
            response=result,
            operation="recipe_replaced",
            expected_parent=2,
            owner_actor_hash=owner,
        )
    assert plans.get_owned(first.plan_id, owner_actor_hash=owner).revision == 2


def test_private_data_erasure_restore_suppression(tmp_path):
    import sqlite3

    from deploy.scripts.privacy_erasure_ledger import SuppressionDirective, _apply_plan_directives

    plans = PlanStore(tmp_path / "plans.sqlite3")
    private = PersonalStore(plans)
    one = private.update_pantry("a" * 64, 0, [PantryItem(name="mjölk", quantity=100, unit="ml")])
    other = private.update_pantry("b" * 64, 0, [PantryItem(name="bröd", quantity=50, unit="g")])
    target = tmp_path / "restored.sqlite3"
    with sqlite3.connect(plans.path) as src, sqlite3.connect(target) as dst:
        src.backup(dst)
    plans.erase_owned(owner_actor_hash="a" * 64)
    assert private.read("a" * 64)["items"] == []
    directive = SuppressionDirective(
        id="test-erasure",
        created_at=NOW.isoformat(),
        target_kind="private_state",
        target_record_id=one["id"],
        action="SUPPRESS_ON_RESTORE",
    )
    _apply_plan_directives(target, (directive,))
    restored = PersonalStore(PlanStore(target))
    assert restored.read("a" * 64)["items"] == []
    assert restored.read("b" * 64)["items"] == other["items"]


def test_account_requires_configuration_and_never_accepts_email_as_owner(monkeypatch):
    from app.api.account import ENV_KEYS, configured, verified_owner
    from starlette.requests import Request

    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    assert not configured()
    req = Request({"type": "http", "headers": [], "session": {"email": "same@example.test"}})
    assert verified_owner(req) is None


def test_legacy_global_diet_is_not_silently_ignored_in_personal_mode():
    p = prepared(product("mjölk", 1000, "ml", 20))
    req = request(extras=[ExtraNeed(query="mjölk", quantity=100, unit="ml", confirmed=True)])
    req = req.model_copy(update={"diet_preference": "vegan"})
    with pytest.raises(PolicyConflict, match="globala kostkravet"):
        run(p, req)


def test_distribution_controls_candidate_selection_and_rejects_contradictions(monkeypatch):
    from app.services.personal_policy import protein_category
    from pydantic import ValidationError

    p = prepared(
        product("bröd", 500, "g", 10),
        product("kyckling", 500, "g", 30),
        product("fisk", 500, "g", 40),
    )
    options = [
        recipe(name=n, ingredients=[RecipeIngredient(name=n, quantity=100, unit="g")])
        for n in ("bröd", "kyckling", "fisk")
    ]
    monkeypatch.setattr(PersonalPlanner, "_candidates", lambda self, meal: options)
    req = PlanRequest(
        recipes=0,
        diversity_mode="cheapest",
        personal=PersonalPlanning(
            meals=[
                MealSettings(
                    meal_type="snack",
                    count=3,
                    distribution={"vegetarian": 1, "chicken": 1, "fish": 1},
                )
            ]
        ),
    )
    result = run(p, req)
    assert sorted(protein_category(r) for r in result.recipes) == ["chicken", "fish", "vegetarian"]
    with pytest.raises(ValidationError, match="överstiger"):
        MealSettings(count=2, distribution={"vegetarian": 2, "fish": 1})
    with pytest.raises(ValidationError, match="Vegetarisk"):
        MealSettings(diet="vegan", distribution={"fish": 1})


def test_private_api_owner_revision_validation_and_no_personal_logging(
    tmp_path, monkeypatch, caplog
):
    from app.api import account, personal, plan
    from app.services.personal_policy import pantry_checks
    from fastapi.testclient import TestClient

    from backend.tests.test_privacy_erasure import _application

    application, factory, settings = _application(tmp_path)
    for module in (account, personal, plan):
        monkeypatch.setattr(module, "get_settings", lambda: settings)
    application.include_router(personal.router)
    personal.install_handlers(application)
    with TestClient(application) as first, TestClient(application) as second:
        payload = {
            "revision": 0,
            "items": [{"name": "privat-test-ingrediens", "quantity": 100, "unit": "g"}],
        }
        response = first.put("/api/personal/pantry", json=payload)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "private, no-store"
        assert second.get("/api/personal/state").json()["items"] == []
        assert first.put("/api/personal/pantry", json=payload).status_code == 409
        assert (
            first.put(
                "/api/personal/profile",
                json={"revision": 1, "profile": {"likes": ["privat-test-ingrediens"]}},
            ).status_code
            == 422
        )
        assert (
            first.put(
                "/api/personal/pantry", json={"revision": 1, "items": [], "owner": "b" * 64}
            ).status_code
            == 422
        )
        assert (
            first.put(
                "/api/personal/pantry",
                json={"revision": 1, "items": []},
                headers={"Origin": "https://attacker.example"},
            ).status_code
            == 403
        )
        assert first.get("/api/personal/state").json()["profile"] is None
    assert "privat-test-ingrediens" not in caplog.text
    notes = pantry_checks(
        [PantryItem(name="jordnötter", quantity=1, unit="g").model_dump()],
        TasteProfile(allergies=["jordnötter"]),
    )
    assert notes[0]["code"] == "CONFLICT" and "jordnötter" in notes[0]["message"]
    factory.kw["bind"].dispose()


def test_personal_cache_identity_includes_owner_state_profile_memberships_and_recipes():
    from copy import deepcopy

    p = prepared(product("mjölk", 1000, "ml", 20))
    req = request(extras=[ExtraNeed(query="mjölk", quantity=100, unit="ml", confirmed=True)])
    base = state()
    identities = {run(p, req, base).personal.cache_identity}
    other = deepcopy(base)
    other["id"] = "another-private-state"
    identities.add(run(p, req, other).personal.cache_identity)
    req.personal.profile.likes = ["mjölk"]
    identities.add(run(p, req, base).personal.cache_identity)
    req.memberships = {"coop": True}
    identities.add(run(p, req, base).personal.cache_identity)
    req.personal.extras[0].quantity = 200
    identities.add(run(p, req, base).personal.cache_identity)
    assert len(identities) == 5


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf")])
def test_conflicting_nutrition_never_passes(value):
    from app.models.personal import PortionLimits

    p = prepared(product("bröd", 500, "g", 10))
    r = recipe(ingredients=[RecipeIngredient(name="bröd", quantity=100, unit="g")])
    req = request(
        slots=[MealSlot(id="b", day=1, meal_type="breakfast", recipe=r)],
        meals=[
            MealSettings(meal_type="breakfast", count=1, limits=PortionLimits(max_protein_g=100))
        ],
    )
    facts = {
        ("coop", "bröd"): ProductFacts(
            source="frozen",
            source_product_id="bröd",
            source_snapshot_id="v2-frozen",
            nutrition_unit="g",
            nutrition_basis="per_100_as_sold",
            nutrition={"protein_g": value},
        )
    }
    with pytest.raises(PolicyConflict, match="konfliktfyllda"):
        run(p, req, facts=facts)


def test_guest_migration_requires_verified_owner_and_is_atomic(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from app.api import account, plan
    from app.services.beta_observability import pseudonymous_actor
    from fastapi import HTTPException
    from starlette.requests import Request

    settings = Settings(
        plan_store_path=tmp_path / "migration.sqlite3",
        secret_key="migration-test-key-000000000000000000001",
    )
    plans = PlanStore(settings.plan_store_path)
    for module in (account, plan):
        monkeypatch.setattr(module, "get_settings", lambda: settings)
    req = Request(
        {
            "type": "http",
            "method": "POST",
            "scheme": "https",
            "path": "/api/account/migrate-guest",
            "headers": [],
            "server": ("testserver", 443),
            "session": {},
            "app": SimpleNamespace(state=SimpleNamespace(plan_store=plans)),
        }
    )
    req.state.anonymous_session_id = "verified-guest-capability"
    guest = pseudonymous_actor(req.state.anonymous_session_id, settings)
    private = PersonalStore(plans)
    source = private.update_pantry(guest, 0, [PantryItem(name="mjölk", quantity=200, unit="ml")])
    payload = account.MigrationRequest(
        guest_revision=1, account_revision=0, confirm_move_to_verified_account=True
    )
    with pytest.raises(HTTPException) as denied:
        account.migrate_guest(payload, req)
    assert denied.value.status_code == 403
    req.scope["session"]["account_owner"] = (
        "a" * 64
    )  # verified middleware output, never a request field
    assert account.migrate_guest(payload, req)["status"] == "MOVED"
    assert private.read("a" * 64)["id"] == source["id"]
    assert private.read(guest)["items"] == []
    private.update_pantry(guest, 0, [PantryItem(name="bröd", quantity=50, unit="g")])
    with pytest.raises(PersonalConflict, match="redan personliga data"):
        account.migrate_guest(payload.model_copy(update={"account_revision": 2}), req)
    assert private.read(guest)["items"][0]["name"] == "bröd"
    assert private.read("a" * 64)["items"][0]["name"] == "mjölk"
