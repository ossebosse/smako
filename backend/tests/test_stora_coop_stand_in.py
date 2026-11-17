"""Owner decision 2026-11-17: Stora Coop is shown, Coop Online Syd never."""
import pytest
from app.models.provenance import SourceProvenance
from app.models.store import Store
from app.services.price_universe_runtime import EconomicIngredientPool, PreparedPriceUniverse

from backend.tests.test_personal_planning_v2 import NOW, prepared, product


def lineage(role=None):
    return SourceProvenance(source_provider="own", source_channel="catalog", source_snapshot_id="v2-frozen",
                            source_observed_at=NOW, provider_store_id="730400", source_role=role)


def universe(*, with_stora=True):
    base = prepared(product("mjölk", 1000, "ml", 12, store="online"), product("mjölk", 1000, "ml", 12, store="stora"),
                    product("mjölk", 1000, "ml", 13, store="willys"))
    stores = [Store(store_id="online", name="Coop Online Syd", chain="coop", city="Lund",
                    price_context_type="online_fulfillment", source_store_id="730400", source_provenance=lineage()),
              Store(store_id="willys", name="Willys Lund", chain="willys", city="Lund")]
    if with_stora:
        stores.append(Store(store_id="stora", name="Stora Coop Lund", chain="coop", city="Lund",
                            price_context_type="physical_store",
                            source_provenance=lineage("owner_assigned_base_price")))
    return PreparedPriceUniverse(universe=base.universe, stores=tuple(stores),
                                 economic_pool=EconomicIngredientPool(), source_name="frozen")


def test_online_shop_is_never_offered_where_stora_coop_stands_in():
    view = universe().request_view(now=NOW)
    assert {s.store_id for s in view.stores} == {"stora", "willys"}
    assert "online" not in view.usable_context_ids


@pytest.mark.parametrize("chosen", [("online",), ("online", "stora"), ("online", "willys")])
def test_a_saved_choice_of_the_online_shop_means_stora_coop(chosen):
    view = universe().request_view(now=NOW, allowed_context_ids=chosen)
    names = {s.name for s in view.stores}
    assert "Coop Online Syd" not in names and "Stora Coop Lund" in names


def test_without_a_stand_in_the_online_shop_stays():
    view = universe(with_stora=False).request_view(now=NOW)
    assert "online" in {s.store_id for s in view.stores}


def test_one_shop_with_two_price_contexts_is_one_choice():
    base = prepared(*(product(f"vara{i}", 1000, "g", 10, store="catalog") for i in range(3)),
                    product("kampanj", 1000, "g", 5, store="campaign"), product("mjölk", 1000, "ml", 13, store="willys"))
    stores = (Store(store_id="catalog", name="Hemköp Lund Karhögstorg", chain="hemkop", city="Lund",
                    address="Karhögstorg 2a", price_context_type="online_store"),
              Store(store_id="campaign", name="Hemköp Lund Karhögstorg", chain="hemkop", city="Lund",
                    address="Karhögstorg  2A", price_context_type="physical_store"),
              Store(store_id="willys", name="Willys Lund", chain="willys", city="Lund", address="Magistratsvägen 22"))
    universe = PreparedPriceUniverse(universe=base.universe, stores=stores,
                                     economic_pool=EconomicIngredientPool(), source_name="frozen")
    assert universe.store_companions() == {"catalog": frozenset({"campaign"})}
    for chosen in (("catalog",), ("campaign",)):
        view = universe.request_view(now=NOW, allowed_context_ids=chosen)
        assert {s.store_id for s in view.stores} == {"catalog", "campaign"}
