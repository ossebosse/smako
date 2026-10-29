"""Explicit owner policy, exact public destinations and ordinary checkout."""

from copy import deepcopy
from datetime import UTC, date, datetime
from functools import lru_cache

import pytest
from app.errors import PriceProviderError
from app.models import OfferMetadata, Product, SourceProvenance, Store
from app.providers.coop_syd_base import CoopSydBaseProvider, assigned_stores
from app.providers.federated import FederatedGroceryPriceProvider

from grocery_data.tests.test_coop_municipality import inventory as real_inventory

OBSERVED = datetime(2026, 10, 29, 9, tzinfo=UTC)
_inventory = lru_cache(maxsize=2)(real_inventory)


def inventory(code, city):
    return deepcopy(_inventory(code, city))


def product(**updates):
    fields = {
        "product_id": "source-milk", "name": "Mjölk", "canonical_name": "mjölk", "category": "Mejeri",
        "store_id": "online-local", "store_name": "Coop Online Syd", "chain": "coop",
        "gtin": "7300156578167", "package_quantity": 1500, "package_unit": "ml",
        "usable_quantity": 1500, "usable_unit": "ml", "quantity_confidence": "exact",
        "sale_model": "fixed_package", "price": 15.5, "effective_price": 9,
        "member_price": 9, "offers": [OfferMetadata(kind="member", description="Online member",
            member_program="coop", price=9, max_quantity=1,
            valid_from=date(2026, 10, 26), valid_to=date(2026, 11, 1))],
        "source_provenance": SourceProvenance(
            source_provider="own", source_channel="catalog", source_snapshot_id="real-source",
            source_observed_at=OBSERVED, provider_store_id="730400",
            price_context="online_fulfillment", chain="coop",
        ),
    }
    return Product(**(fields | updates))


class Provider:
    def __init__(self, stores=(), products=None):
        self.stores, self.products = list(stores), products or {}

    async def find_stores(self, postal):
        return self.stores

    async def get_store_products(self, store):
        assert store in {s.store_id for s in self.stores}
        return self.products.get(store, [])

    async def search_products(self, query, stores):
        return [p for s in stores for p in self.products.get(s, [])]

    async def get_offers(self, store):
        return [p for p in self.products.get(store, []) if p.offers]

    def report(self):
        return {}


def source():
    p = product()
    store = Store(store_id="online-local", name="Coop Online Syd", chain="coop", city="Lund",
                  source_store_id="730400", price_context_type="online_fulfillment",
                  coverage="full_online_catalog", source_provenance=p.source_provenance)
    return Provider([store], {store.store_id: [p, product(product_id="no-base", price=None)]})


def physical(official):
    s = Store(store_id="temporary", chain="coop", name=official["name"], city=official["city"],
              address=official["address"], postal_code=official["postal_code"],
              physical_store_external_id=official["external_id"],
              price_context_type="physical_store", coverage="offers_only")
    return s.model_copy(update={"store_id": FederatedGroceryPriceProvider._context_id(s)})


@pytest.mark.parametrize("code,city,expected", [
    ("1281", "Lund", {"2696"}), ("1280", "Malmö", {"3850", "3853"}),
])
@pytest.mark.parametrize("has_campaign", [False, True])
async def test_one_physical_checkout_ordinary_source_and_unchanged_campaign(code, city, expected, has_campaign):
    inv = inventory(code, city)
    targets = assigned_stores(inv)
    assert set(targets) == expected
    official = next(iter(targets.values()))
    shop = physical(official)
    campaign = product(product_id="physical-offer", store_id=shop.store_id, store_name=shop.name,
                       price=None, member_price=None, offers=[OfferMetadata(
                           kind="campaign", description="Physical campaign", price=12, max_quantity=2,
                           valid_from=date(2026, 10, 26), valid_to=date(2026, 11, 1),
                       )])
    base = Provider([shop] if has_campaign else [], {shop.store_id: [campaign]} if has_campaign else {})
    provider = CoopSydBaseProvider(base, source(), inventory=inv)
    stores = await provider.find_stores("22350" if city == "Lund" else "21120")
    assert len(stores) == len(expected) and len({s.store_id for s in stores}) == len(stores)
    for target in stores:
        assert target.price_label == "Baspris från Coop Online Syd"
        assert target.price_semantics == "online_price"
        assert target.price_context_type == "physical_store"
        rows = await provider.get_store_products(target.store_id)
        projected = [p for p in rows if p.source_provenance.source_role == "owner_assigned_base_price"]
        assert len(projected) == 1
        p = projected[0]
        assert (p.price, p.effective_price, p.member_price, p.offers, p.promotion_groups) == (15.5, 15.5, None, [], ())
        assert p.package_quantity == 1500 and p.gtin == "7300156578167"
        assert p.source_provenance.provider_store_id == "730400"
        assert p.source_provenance.source_snapshot_id == "real-source"
        assert p.source_provenance.source_observed_at == OBSERVED
        assert p.source_provenance.price_context == "online_fulfillment"
        assert p.store_id == target.store_id and p.store_name == target.name
        assert await provider.search_products("mjölk", [target.store_id]) == rows
        if has_campaign and target.store_id == shop.store_id:
            assert rows[0] is campaign
            assert (await provider.get_offers(target.store_id))[0] is campaign
            assert rows[0].offers[0].max_quantity == 2
        else:
            assert await provider.get_offers(target.store_id) == []
    assert len(await provider.find_stores("22350")) == len(stores)


async def test_smaller_coop_is_not_assigned_and_online_prices_remain_a_separate_source():
    inv = inventory("1281", "Lund")
    small = physical(next(r["store"] for r in inv["stores"] if r["store"]["external_id"] == "3839"))
    online = source().stores[0]
    base = Provider([small, online])
    provider = CoopSydBaseProvider(base, source(), inventory=inv)
    result = await provider.find_stores("22350")
    assert small in result and online in result
    assert small.coverage == "offers_only" and small.price_label is None
    assert await provider.get_store_products(small.store_id) == []


@pytest.mark.parametrize("change", ["ledger", "unknown_municipality", "wrong_source", "duplicate_source"])
async def test_no_assignment_for_unverified_destination_or_source(change):
    inv = inventory("1281", "Lund")
    row = next(r for r in inv["stores"] if r["store"]["external_id"] == "2696")
    own = source()
    if change == "ledger":
        row["store"]["source_fields"]["ledger_account_number"] = "wrong"
    elif change == "unknown_municipality":
        row["geographic_evidence"]["status"] = "unknown"
    elif change == "wrong_source":
        own.stores = [own.stores[0].model_copy(update={"source_store_id": "730500"})]
    else:
        own.stores *= 2
    with pytest.raises((ValueError, PriceProviderError)):
        provider = CoopSydBaseProvider(Provider(), own, inventory=inv)
        await provider.find_stores("22350")
