"""Two actual prepared test artifacts, distinct serving scopes and user choices."""
from datetime import timedelta

import pytest
from app.api import plan
from app.config import Settings
from app.models.store import StorePickupOption
from app.services.municipal_runtime import distance_to_store, required_contexts
from app.services.price_universe_runtime import PreparedPriceUniverseManager

from backend.tests.test_price_universe_runtime import (
    NON_FRESHNESS_TEST_MAX_AGE_HOURS,
    OBSERVED_AT,
    _CountingProvider,
    _pool,
    _product,
    _StaticSelector,
    _store,
)
from grocery_data.tests.test_municipal_rollout import (
    registry,  # noqa: F401 - shared registry fixture
)


async def build(manager, city, postal, identities):
    class Provider(_CountingProvider):
        async def find_stores(self, postal_code):
            return self.stores if postal_code == postal else []

    stores = [_store(store_id=identity, snapshot_id=identity).model_copy(update={
        "city": city, "postal_code": postal, "latitude": 55.60 + i * .02, "longitude": 13.00})
        for i, identity in enumerate(identities)]
    products = [_product("product-" + identity, canonical, store_id=identity, snapshot_id=identity,
                         price=10+i, quantity=1000, index=i)
                for i, (identity, canonical) in enumerate(zip(identities, ("ris", "tofu"), strict=False))]
    pool = _pool(products).model_copy(update={"ingredients": [_pool([p]).ingredients[0] for p in products]})
    return await manager.build_and_activate(city=city, postal_codes=[postal],
        provider=Provider(stores, products), selector=_StaticSelector(pool),
        memberships={}, built_at=OBSERVED_AT)


@pytest.mark.asyncio
async def test_two_cities_restart_selection_and_no_cross_city_contexts(registry, tmp_path, monkeypatch):  # noqa: F811 - imported pytest fixture
    manager = PreparedPriceUniverseManager()
    lund = await build(manager, "Lund", "22350", ["own:hemkop:4123"])
    malmo = await build(manager, "Malmö", "21120", ["own:hemkop:4247", "own:hemkop:malmo-other"])
    restarted = PreparedPriceUniverseManager()
    for prepared in (lund, malmo):
        destination = tmp_path / (prepared.universe.key.scope_id.replace(":", "-") + ".json")
        manager.write_artifact(prepared, destination)
        restarted.load_file_and_activate(destination)
    assert restarted.get_for_request("22350", {}).universe.universe_id == lund.universe.universe_id
    assert restarted.get_for_request("21120", {}).universe.universe_id == malmo.universe.universe_id
    assert restarted.get_for_request("99999", {}) is None
    settings = Settings(max_price_age_hours=NON_FRESHNESS_TEST_MAX_AGE_HOURS)
    assert required_contexts(settings, malmo) == {"own:hemkop:4247", "own:hemkop:malmo-other"}
    monkeypatch.setattr(plan, "GLOBAL_PREPARED_PRICE_UNIVERSES", restarted)
    monkeypatch.setattr(plan, "get_settings", lambda: settings)
    rows = (await plan.available_price_contexts(postal_code="21120", latitude=55.60, longitude=13.0))["contexts"]
    assert {r["context_id"] for r in rows} == {"own:hemkop:4247", "own:hemkop:malmo-other"}
    assert rows[0]["distance_km"] == 0
    municipalities = (await plan.available_municipalities())["municipalities"]
    assert next(r for r in municipalities if r["name"] == "Malmö")["available"]
    # A missing required Lund base never disables otherwise healthy Malmö.
    assert not next(r for r in municipalities if r["name"] == "Lund")["available"]
    first = malmo.request_view(now=OBSERVED_AT, allowed_context_ids=("own:hemkop:4247",))
    second = malmo.request_view(now=OBSERVED_AT, allowed_context_ids=("own:hemkop:malmo-other",))
    assert first.cache_identity != second.cache_identity
    assert first.usable_context_ids == ("own:hemkop:4247",)
    for rows in (first.economic_pool.candidates_by_name, first.economic_pool.semantic_candidates_by_name,
                 first.economic_pool.projection_shortlist_support_by_name):
        assert all(p.store_id == "own:hemkop:4247" for values in rows.values() for p in values)
    with pytest.raises(ValueError, match="Valda"):
        malmo.request_view(now=OBSERVED_AT, allowed_context_ids=("own:hemkop:4123",))
    with pytest.raises(ValueError, match="Valda"):
        malmo.request_view(now=OBSERVED_AT + timedelta(hours=49), allowed_context_ids=("own:hemkop:4247",))
    assert len(malmo.stores) == 2  # Shared artifact and another user's view stay intact.


def test_distance_uses_pickup_not_fulfillment_warehouse():
    store = _store().model_copy(update={"latitude": 55.6, "longitude": 13.0,
        "price_context_type": "online_fulfillment", "pickup_options": ()})
    assert distance_to_store(store, 55.6, 13.0) == (None, None)
    store = store.model_copy(update={"pickup_options": (StorePickupOption(
        physical_store_id="verified-pickup", name="Pickup", confidence="high",
        latitude=55.61, longitude=13.0),)})
    distance, basis = distance_to_store(store, 55.6, 13.0)
    assert 1 < distance < 1.2 and basis == "pickup"


@pytest.mark.asyncio
async def test_real_public_calculation_obeys_selection_and_separates_cached_results(monkeypatch):
    from app.models import PlanRequest
    from app.services.meal_plan_optimizer import MealPlanService

    from backend.tests.test_price_universe_runtime import _candidate, _FixtureCandidateGenerator

    identities = ("own:hemkop:4123", "own:hemkop:other")
    stores = [_store(store_id=identity) for identity in identities]
    products = [_product(f"{store}-{canonical}", canonical, store_id=store,
                         price=price, quantity=quantity, index=i)
        for store, price in zip(identities, (25, 100), strict=True)
        for i, (canonical, quantity) in enumerate((("tofu", 400), ("ris", 1000), ("morot", 1000)))]
    maps = {canonical: [_candidate(p) for p in products if p.canonical_name == canonical]
            for canonical in ("tofu", "ris", "morot")}
    pool = _pool(products).model_copy(update={"candidates_by_name": maps, "semantic_candidates_by_name": maps,
        "matched_candidates_by_name": maps, "ingredients": [_pool([p]).ingredients[0] for p in products[:3]]})
    manager = PreparedPriceUniverseManager()
    prepared = await manager.build_and_activate(city="Lund", postal_codes=["22350"],
        provider=_CountingProvider(stores, products), selector=_StaticSelector(pool), memberships={}, built_at=OBSERVED_AT)
    service = MealPlanService(Settings(price_provider="auto", price_universe_required=True,
        max_price_age_hours=NON_FRESHNESS_TEST_MAX_AGE_HOURS),
        candidate_generator=_FixtureCandidateGenerator(), price_universe_manager=manager)

    async def no_legacy(*a, **k): return None, "fixture"
    monkeypatch.setattr(service, "_legacy_plan_from_pool", no_legacy)
    request = PlanRequest(recipes=1, servings=4, max_stores=1, strategy="optimized", candidate_recipe_count=10,
        beam_width=5, optimization_iterations=0, min_kcal_per_serving=0, max_kcal_per_serving=3000,
        min_protein_g_per_serving=0, min_vegetable_g_per_serving=0)
    totals = []
    for identity in reversed(identities):
        result = await service.create_plan(request.model_copy(update={"allowed_store_ids": (identity,)}))
        assert {s.store_id for s in result.optimized_basket.stores} == {identity}
        totals.append(result.optimized_basket.total)
    assert totals[0] > totals[1]
    assert len(prepared.stores) == 2
