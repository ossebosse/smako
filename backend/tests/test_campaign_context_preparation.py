"""Share source-only campaign existence, never age or user price approvals."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

from app.config import Settings
from app.models.ingredient import NormalizedIngredient
from app.models.product import OfferKind, OfferMetadata, ProductCandidate
from app.services import beta_observability, price_universe_runtime
from app.services.basket_calculator import BasketCalculator
from app.services.price_universe import PriceUniverseBuilder, PriceUniverseKey
from app.services.price_universe_runtime import (
    PreparedPriceUniverse,
    PreparedPriceUniverseManager,
    normalized_memberships,
)
from app.services.user_pricing import price_candidate_for_context

from backend.tests.test_price_universe_runtime import (
    POSTAL_CODE,
    SNAPSHOT_ID,
    STORE_ID,
    _pool,
    _product,
    _store,
)
from grocery_data.app.domain.campaign_validity import CampaignEvidence
from grocery_data.app.domain.promotion_pricing import UserPricingContext

OBSERVED = datetime(2026, 9, 14, 8, tzinfo=UTC)


def fixture(*, end=date(2026, 9, 20), strategy="fixture", observed=OBSERVED, price=20):
    product = _product("campaign-rice", "ris", price=price, quantity=1000, observed_at=observed)
    proof = CampaignEvidence(store_external_id="official", offer_id="campaign-rice", source_reference="raw:synthetic",
        observed_current_at=observed, checked_at=observed)
    product = product.model_copy(update={"price": None, "coverage": "offers_only",
        "offers": [OfferMetadata(kind=OfferKind.CAMPAIGN, description="Synthetic date-bound offer", price=price,
            valid_from=date(2026, 9, 16), valid_to=end, campaign_evidence=proof)],
        "source_provenance": product.source_provenance.model_copy(update={
            "source_channel": "offers", "provider_store_id": "official", "coverage": "offers_only"})})
    key = PriceUniverseKey.create(city="Lund", postal_codes=[POSTAL_CODE], snapshot_ids=[SNAPSHOT_ID],
        memberships=normalized_memberships({}), source_strategy_version=strategy, normalizer_version="fixture", taxonomy_version="fixture")
    return PreparedPriceUniverse(universe=PriceUniverseBuilder().build(key, [product], built_at=observed),
        stores=(_store(observed_at=observed),), economic_pool=_pool([product]), source_name="fixture", oldest_observed_at=observed)


def test_negative_start_end_and_stockholm_midnight_without_snapshot_change(monkeypatch):
    prepared = fixture()
    scan = Mock(wraps=price_universe_runtime.has_active_campaign)
    monkeypatch.setattr(price_universe_runtime, "has_active_campaign", scan)
    day = date(2026, 9, 15)
    assert prepared._active_campaign_contexts(day) == frozenset()
    assert prepared._active_campaign_contexts(day) == frozenset()
    assert scan.call_count == 1  # Negative cache entries are reusable too.
    assert prepared._active_campaign_contexts(day + timedelta(days=1)) == {STORE_ID}
    before = datetime(2026, 9, 20, 21, 59, tzinfo=UTC)
    after = datetime(2026, 9, 20, 22, tzinfo=UTC)
    assert prepared.request_view(now=before).usable_context_ids == (STORE_ID,)
    assert prepared.request_view(now=after).usable_context_ids == ()
    assert len(prepared._campaign_days) == 2
    assert prepared.universe.key.snapshot_ids == (SNAPSHOT_ID,)
    assert prepared.universe.products[0].source_provenance.source_observed_at == OBSERVED


def test_current_ages_and_invalid_observations_are_never_cached():
    prepared = fixture()
    early = datetime(2026, 9, 17, 8, tzinfo=UTC)
    first = prepared.status(now=early)
    later = prepared.status(now=early + timedelta(hours=1))
    assert later.oldest_price_age_hours == first.oldest_price_age_hours + 1
    # The same active campaign cannot turn a future observation into a valid one.
    poisoned = fixture(observed=early + timedelta(hours=2))
    assert poisoned._active_campaign_contexts(early.date()) == {STORE_ID}
    assert poisoned._context_partition(now=early, stale_age_hours=48)[0] == ()
    assert poisoned._context_partition(now=early + timedelta(hours=1), stale_age_hours=48)[0] == (STORE_ID,)


def test_new_artifact_and_restart_have_no_campaign_approval_from_previous_version():
    old = fixture()
    current = fixture(end=date(2026, 9, 16), strategy="new-version")
    assert old._active_campaign_contexts(date(2026, 9, 17)) == {STORE_ID}
    assert current._campaign_days == {}
    assert current._active_campaign_contexts(date(2026, 9, 17)) == frozenset()
    restarted = replace(old)
    assert restarted._campaign_days == {}
    assert restarted._active_campaign_contexts(date(2026, 9, 17)) == {STORE_ID}


def test_same_context_availability_never_reuses_old_campaign_price():
    old, current = fixture(), fixture(strategy="new-price-version", price=30)
    assert old.universe.universe_id != current.universe.universe_id
    day = date(2026, 9, 17)
    need = NormalizedIngredient(canonical_name="ris", required_quantity=1000, unit="g")
    for prepared, expected in ((old, 20), (current, 30)):
        assert prepared._active_campaign_contexts(day) == {STORE_ID}
        candidate = price_candidate_for_context(ProductCandidate.from_product(prepared.universe.products[0], match_score=1),
            UserPricingContext(), on_date=day)
        assert BasketCalculator().quote_item(need, candidate).total_price == expected


def test_single_flight_and_retired_scan_cannot_publish_into_new_artifact(monkeypatch):
    old, current = fixture(), fixture(end=date(2026, 9, 16), strategy="new-version")
    manager = PreparedPriceUniverseManager()
    manager.activate(old)
    entered, finish = Event(), Event()
    original = price_universe_runtime.has_active_campaign
    calls = []

    def scan(product, day):
        calls.append(product)
        if product is old.universe.products[0]:
            entered.set()
            assert finish.wait(5)
        return original(product, day)

    monkeypatch.setattr(price_universe_runtime, "has_active_campaign", scan)
    day = date(2026, 9, 17)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(old._active_campaign_contexts, day)
        assert entered.wait(5)
        second = pool.submit(old._active_campaign_contexts, day)
        manager.activate(current)
        assert manager.get_active("city:lund")._active_campaign_contexts(day) == frozenset()
        finish.set()
        assert first.result() == second.result() == {STORE_ID}
    assert len(calls) == 2  # One old scan, one current scan, no duplicate old scan.
    assert manager.get_active("city:lund") is current


def test_observability_reads_active_identity_without_scanning_readiness(monkeypatch):
    registry = Mock()
    registry.get_active.return_value = SimpleNamespace(universe=SimpleNamespace(universe_id="current-id"))
    monkeypatch.setattr(beta_observability, "GLOBAL_PREPARED_PRICE_UNIVERSES", registry)
    monkeypatch.setattr(beta_observability, "active_price_status", Mock(side_effect=AssertionError("unneeded scan")))
    assert beta_observability.price_universe_id(Settings(price_universe_city=" Lund ")) == "current-id"
    registry.get_active.assert_called_once_with("city:lund")
    registry.get_active.return_value = None
    assert beta_observability.price_universe_id(Settings()) is None
