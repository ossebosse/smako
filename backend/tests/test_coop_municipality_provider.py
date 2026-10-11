"""Real retained Coop source, explicit clock; optional municipal source boundary."""

import copy
import importlib

import httpx
import pytest
from app.models import Store
from app.providers.coop_municipality_offers import CoopMunicipalityOfferProvider, approved_inventory
from app.providers.own import OwnGroceryPriceProvider
from fastapi import FastAPI

from backend.tests.test_coop_physical_pipeline import ReplayClock
from grocery_data.app.api import catalog_router
from grocery_data.app.connectors.coop.connector import CoopRowApprovedOfferConnector
from grocery_data.app.domain import GeographicArea, RawBatch
from grocery_data.app.services.collector import GroceryCollector
from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
from grocery_data.app.storage import create_database_engine, create_schema, create_session_factory
from grocery_data.tests.test_coop_physical_structured import FIXTURES, source


class Base:
    def __init__(self, stores=()):
        self.stores = list(stores)

    async def find_stores(self, postal):
        return self.stores

    async def search_products(self, query, ids):
        return []

    async def get_store_products(self, store):
        return []

    def report(self):
        return {}


def inventory(store):
    from grocery_data.tests.test_coop_municipality import inventory as real_inventory

    inv = real_inventory("1281", "Lund")
    inv["selected_store_ids"] = [store.external_id]
    inv["stores"] = [r for r in inv["stores"] if r["store"]["external_id"]==store.external_id]
    return inv



@pytest.mark.parametrize("change", ["outside", "unknown", "xtra", "conflict", "duplicate"])
def test_inventory_cannot_guess_scope_or_concept(change):
    store, _ = source("3839")
    inv = inventory(store)
    row = next(r for r in inv["stores"] if r["store"]["external_id"]==store.external_id)
    if change in {"outside", "unknown"}:
        row["geographic_evidence"]["status"] = change
    elif change == "xtra":
        row["store"]["source_fields"]["concept"] = "X:-tra"
    elif change == "conflict":
        row["store"]["source_fields"]["identity_conflict"] = True
    else:
        inv["stores"].append(copy.deepcopy(row))
    with pytest.raises(ValueError):
        approved_inventory(inv)


async def test_missing_optional_database_keeps_base(tmp_path):
    store, _ = source("3839")
    base = Base([Store(store_id="baseline", name="Baseline", chain="willys", city="Lund")])
    provider = CoopMunicipalityOfferProvider(
        base, None, database=tmp_path / "absent.sqlite", inventory=inventory(store)
    )
    assert await provider.find_stores("22350") == base.stores
    assert provider.report()["coop_municipality_offers"]["setup"]["status"] == "error"


@pytest.mark.parametrize("duplicate_base", [False, True])
@pytest.mark.parametrize("parser_version", [None, "coop-parser-v3", "coop-parser-v4", "coop-parser-v5"])
async def test_actual_rows_locality_inventory_caps_and_wrong_store(
    tmp_path, monkeypatch, duplicate_base, parser_version
):
    for name in [
        "grocery_data.app.api.common",
        "grocery_data.app.api.catalog",
        "grocery_data.app.services.freshness",
        "app.providers.own",
        "app.models.product",
        "grocery_data.app.domain.promotion_pricing",
        "grocery_data.app.services.fixed_checkout_price",
        "app.providers.coop_municipality_offers",
    ]:
        monkeypatch.setattr(importlib.import_module(name), "datetime", ReplayClock)
    store, batch = source("3839")
    inv = inventory(store)
    locator = RawBatch.model_validate_json((FIXTURES / "3839-locator.json").read_bytes())
    database = tmp_path / "own.sqlite"
    engine = create_database_engine("sqlite:///" + database.as_posix())
    create_schema(engine)
    factory = create_session_factory(engine)
    collector = GroceryCollector(factory, FilesystemRawSnapshotStore(tmp_path / "raw"))
    retained = CoopRowApprovedOfferConnector(store=store, locator=locator, offers=batch)
    result = await collector.collect_area(
        retained, GeographicArea(city=store.city), scope_key="test:coop:3839:offer-rows"
    )
    assert result.promoted
    app = FastAPI()
    app.state.session_factory = factory
    app.include_router(catalog_router)
    async with httpx.AsyncClient(
        base_url="http://isolated", transport=httpx.ASGITransport(app=app)
    ) as client:
        own = OwnGroceryPriceProvider(
            "http://isolated",
            client=client,
            include_offers_only=True,
            include_conditional_offer_products=True,
        )
        online = Store(
            store_id="online",
            chain="coop",
            name="Online",
            city="Lund",
            price_context_type="online_fulfillment",
            physical_store_external_id="3839",
        )
        physical = Store(
            store_id="same-physical",
            chain="coop",
            name=store.name,
            city=store.city,
            address=store.address,
            postal_code=store.postal_code,
            physical_store_external_id=store.external_id,
            price_context_type="physical_store",
        )
        base = Base([online, physical] if duplicate_base else [online])
        provider = CoopMunicipalityOfferProvider(base, own, database=database, inventory=inv)
        # The default uses the REAL current parser version from collection.
        # Legacy compatibility must not hide a newly emitted version rejection.
        if parser_version is not None:
            for evidence in provider.evidence.values():
                evidence["parser_version"] = parser_version
        stores = await provider.find_stores("22350")
        assert len(stores) == 2  # Online remains separate, physical never duplicated.
        assert provider.report()["coop_municipality_offers"]["3839"]["accepted"] == 93
        rows = [p for values in provider.products.values() for p in values]
        assert all(p.store_id != "online" for p in rows)
        if duplicate_base:
            assert all(p.store_id == "same-physical" for p in rows)
        raw = {p.external_product_id: p for p in retained.extracted.products}
        for p in rows:
            offer = p.offers[0]
            key = offer.campaign_evidence.offer_id
            assert (
                p.price is None
                and offer.price_contract_id
                == raw[key].offers[0].source_payload["price_contract_id"]
            )
        # A single mismatched retained variant cannot move its price to another store.
        first = next(iter(provider.evidence))
        provider.evidence[first]["external_id"] = "wrong"
        provider._loaded = False
        provider.products.clear()
        provider.stores.clear()
        await provider.find_stores("22350")
        assert provider.diagnostics["3839"]["accepted"] == 92
        assert provider.diagnostics["3839"]["rejected"]["source_purchase_identity_mismatch"] == 1
        # A future/unreviewed parser cannot inherit this document admission.
        for evidence in provider.evidence.values():
            evidence["parser_version"] = "coop-parser-unreviewed"
        provider._loaded = False
        provider.products.clear()
        provider.stores.clear()
        assert await provider.find_stores("22350") == base.stores
        assert provider.diagnostics["3839"]["accepted"] == 0
        assert provider.diagnostics["3839"]["rejected"]["row_qualification_unverified"] == 93
        # Removing municipality evidence cannot turn into legacy postcode scope.
        bad = copy.deepcopy(inv)
        bad["stores"][0]["geographic_evidence"]["status"] = "unknown"
        invalid = CoopMunicipalityOfferProvider(base, own, database=database, inventory=bad)
        assert await invalid.find_stores("22350") == base.stores
    engine.dispose()


@pytest.mark.parametrize("failure", ["missing", "corrupt"])
async def test_optional_setup_failure_preserves_actual_base_build(tmp_path, failure):
    from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
    from app.services.production_price_universe_build import build_city_price_universe

    from backend.tests.test_own_provider_grocery_data_contract import _contract_database
    from backend.tests.test_production_price_universe_build import _copy_sqlite_database

    engine, _ = _contract_database()
    database = tmp_path / "base.sqlite"
    try:
        _copy_sqlite_database(engine, database)
    finally:
        engine.dispose()
    optional = tmp_path / "optional.sqlite"
    if failure == "corrupt":
        optional.write_bytes(b"not a valid SQLite source")
    store, _ = source("3839")
    baseline = tmp_path / "baseline.json"
    candidate = tmp_path / "candidate.json"
    await build_city_price_universe(database, "Lund", "22350", None, baseline, 48)
    result = await build_city_price_universe(
        database,
        "Lund",
        "22350",
        None,
        candidate,
        48,
        coop_offer_database=optional,
        coop_municipality_inventory=inventory(store),
    )
    left = PreparedPriceUniverseArtifact.model_validate_json(baseline.read_bytes())
    right = PreparedPriceUniverseArtifact.model_validate_json(candidate.read_bytes())
    assert left.universe.products == right.universe.products
    assert result["status"] == "PASS" and result["coop_optional_setup_error"]
    assert result["persistent_activation"] is False and result["network_attempts"] == 0
