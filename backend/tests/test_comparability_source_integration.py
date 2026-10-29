"""Retained source -> existing DB repository -> OWN API -> consumer model."""

import json
from datetime import datetime

import pytest
from app.providers.own import OwnGroceryPriceProvider

from grocery_data.app.api.catalog import _product_item, _promotion_item
from grocery_data.app.connectors.coop import CoopParser
from grocery_data.app.connectors.coop.online_catalog_parser import CoopOnlineCatalogParser
from grocery_data.app.connectors.willys.parser import WillysParser
from grocery_data.app.domain import RawBatch, RawFetch, SourceStore
from grocery_data.app.normalization import ProductNormalizer
from grocery_data.app.services.offer_rows import qualify_rows
from grocery_data.app.storage import (
    ProductBundleRepository,
    RawSnapshotRepository,
    SnapshotRepository,
    StoreRepository,
    create_database_engine,
    create_schema,
    create_session_factory,
    session_scope,
)
from grocery_data.tests.test_comparability_source_replay import ROOT, capture


def through_repository(source, store, raw, version):
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    with session_scope(create_session_factory(engine)) as session:
        sr = StoreRepository(session).upsert(store, seen_at=raw.fetched_at)
        snap = SnapshotRepository(session).create(
            chain=store.chain,
            coverage=store.coverage,
            connector_version="retained-test",
            scope_key="test:" + store.external_id,
            parser_version=version,
            normalizer_version=ProductNormalizer.normalizer_version,
            created_at=raw.fetched_at,
        )
        rr = RawSnapshotRepository(session).record_fetch(
            raw, catalog_snapshot_id=snap.id, payload_location="retained-fixture"
        )
        normalized = ProductNormalizer().normalize(source, parser_version=version)
        bundle = ProductBundleRepository(session).persist(
            source=source,
            canonical=normalized,
            catalog_snapshot_id=snap.id,
            raw_snapshot_id=rr.id,
            store_id=sr.id,
        )
        session.flush()
        row = _product_item(bundle.product, bundle.source_product, None, sr)
        row["offers"] = [
            _promotion_item(o, product=bundle.product, source=bundle.source_product, store=sr)
            for o in bundle.promotions
        ]
        p = OwnGroceryPriceProvider(
            "http://retained.invalid",
            include_offers_only=True,
            include_conditional_offer_products=True,
        )._product_from_row(row)
        assert p is not None
    engine.dispose()
    return p


def test_real_garlic_and_capped_weight_survive_every_mapping():
    for identity, chain in [
        ("036a35871545499789de7cf99ddd0451", "coop"),
        ("0eeef76b41194e05bb3d14d2722c453d", "willys"),
    ]:
        evidence = json.loads((ROOT / f"product-{identity}.json").read_bytes())
        row = evidence["record"]
        meta = evidence["raw"]
        at = datetime.fromisoformat(meta["fetched_at"])
        store = SourceStore(
            chain=chain,
            external_id=meta["store_external_id"],
            name=chain + " retained online",
            online_shopping=True,
            coverage="full_online_catalog",
            price_context_type="online_fulfillment" if chain == "coop" else "online_store",
            city="Lund",
            raw_reference="retained-source-store",
        )
        raw = RawFetch(
            chain=chain,
            store_external_id=store.external_id,
            kind=meta["kind"],
            url=meta["url"],
            fetched_at=at,
            payload=json.dumps(row).encode(),
            http_status=200,
            method=meta["method"],
            connector_version=meta["connector_version"],
        )
        parser = CoopOnlineCatalogParser() if chain == "coop" else WillysParser()
        source = (
            parser.parse_product(row, store=store, reference="raw:retained-extract", fetched_at=at)
            if chain == "coop"
            else parser._parse_product(row, store, "raw:retained-extract", at)
        )
        p = through_repository(source, store, raw, parser.parser_version)
        if chain == "coop":
            assert p.package_quantity == 57 and p.package_unit == "g"
        else:
            assert (
                p.offers[0].limit_unit == "purchase_packages"
                and p.offers[0].price_basis_unit == "kg"
            )


def test_actual_scan_both_physical_stores_survive_own_without_online_price_transfer():
    for sid in ["3659", "3820"]:
        store, raw, _ = capture(sid)
        parsed = CoopParser().parse_catalog(
            RawBatch(chain="coop", store_external_id=sid, documents=(raw,)),
            ["raw:retained-oct10"],
            store,
        )
        approved, _ = qualify_rows(parsed, store=store, observed_at=raw.fetched_at)
        source = next(p for p in approved.products if "ytterfil" in p.name.lower())
        p = through_repository(source, store, raw, CoopParser.parser_version)
        assert p.offers[0].price == 65 and p.purchase_terms.approximate_package_g == 1000
        assert p.price_context_type == "physical_store" and p.gtin is None and p.price is None


def test_scan_full_shopping_baskets(tmp_path):
    from datetime import UTC

    from app.config import Settings
    from app.models import PlanRequest
    from app.models.personal import ExtraNeed, PersonalPlanning
    from app.services.personal_planner import PersonalPlanner
    from app.services.personal_policy import interpretation
    from app.services.plan_store import PlanStore

    from backend.tests.test_comparability_sales_units import prepare
    from backend.tests.test_product_search import search

    for sid in ["3659", "3820"]:
        store, raw, _ = capture(sid)
        parsed = CoopParser().parse_catalog(
            RawBatch(chain="coop", store_external_id=sid, documents=(raw,)),
            ["raw:retained-oct10"],
            store,
        )
        approved, _ = qualify_rows(parsed, store=store, observed_at=raw.fetched_at)
        source = next(p for p in approved.products if "ytterfil" in p.name.lower())
        p = through_repository(source, store, raw, CoopParser.parser_version)
        now = datetime(2026, 10, 10, 16, tzinfo=UTC)
        prepared = prepare(p, now=now)
        found = search(prepared, "fläskytterfilé", now=now, memberships=["COOP_MEMBER"])["results"][
            0
        ]
        assert found["display_price"] == 65 and found["display_price_unit"] == "kg"
        request = PlanRequest(
            recipes=0,
            purchase_planning_mode="estimated",
            membership_price_policy="all_advertised",
            personal=PersonalPlanning(
                extras=[
                    ExtraNeed(
                        kind="exact",
                        query=p.name,
                        quantity=1000,
                        unit="g",
                        properties=interpretation(p.name),
                        product_key=found["product_key"],
                        confirmed=True,
                    )
                ]
            ),
        )
        plan = PersonalPlanner(
            request,
            Settings(price_provider="mock"),
            prepared,
            {"id": "scan-" + sid, "revision": 0, "items": [], "reservations": {}, "events": {}},
            now=now,
        ).create()
        assert (
            plan.optimized_basket.total == 65 and plan.personal.checks["checkout_audit"]["passed"]
        )
        saved = PlanStore(tmp_path / (sid + ".sqlite")).create(
            request, plan, owner_actor_hash="a" * 64
        )
        assert (
            PlanStore(tmp_path / (sid + ".sqlite"))
            .get_owned(saved.plan_id, owner_actor_hash="a" * 64)
            .plan.model_dump()
            == plan.model_dump()
        )


@pytest.mark.parametrize("verified_limit,grams,expected_total", [
    (False, 60, 21.8), (True, 60, 15), (True, 342, 51.8),
])
def test_garlic_quantity_and_multibuy_full_shopping_basket(verified_limit, grams, expected_total):
    from app.config import Settings
    from app.models import PlanRequest
    from app.models.personal import ExtraNeed, PersonalPlanning
    from app.services.personal_planner import PersonalPlanner

    from backend.tests.test_comparability_sales_units import NOW, prepare
    from backend.tests.test_product_search import search

    evidence = json.loads((ROOT / "product-036a35871545499789de7cf99ddd0451.json").read_bytes())
    row = evidence["record"]
    if verified_limit:
        # Explicitly synthetic limits exercise basket maths independently. The
        # unmodified retained response must use ordinary prices under v4.
        for promotion in row.get("onlinePromotions", []):
            promotion.update(maxNumberOfUse=4500,
                             maxNumberOfUseWithUnit={"unit": "Styck", "value": 5.0})
    meta = evidence["raw"]
    at = datetime.fromisoformat(meta["fetched_at"])
    store = SourceStore(
        chain="coop",
        external_id=meta["store_external_id"],
        name="Coop retained online",
        online_shopping=True,
        coverage="full_online_catalog",
        price_context_type="online_fulfillment",
        city="Lund",
        raw_reference="retained-source-store",
    )
    raw = RawFetch(
        chain="coop",
        store_external_id=store.external_id,
        kind=meta["kind"],
        url=meta["url"],
        fetched_at=at,
        payload=json.dumps(row).encode(),
        http_status=200,
        method=meta["method"],
        connector_version=meta["connector_version"],
    )
    parser = CoopOnlineCatalogParser()
    source = parser.parse_product(row, store=store, reference="raw:retained-extract", fetched_at=at)
    product = through_repository(source, store, raw, parser.parser_version)
    prepared = prepare(product)
    found = search(prepared, "Vitlök", now=NOW, memberships=["COOP_MEMBER"])["results"][0]
    request = PlanRequest(
        recipes=0,
        membership_price_policy="all_advertised",
        personal=PersonalPlanning(
            extras=[
                ExtraNeed(
                    kind="exact",
                    query="Vitlök",
                    quantity=grams,
                    unit="g",
                    product_key=found["product_key"],
                    confirmed=True,
                )
            ]
        ),
    )
    plan = PersonalPlanner(
        request,
        Settings(price_provider="mock"),
        prepared,
        {"id": "garlic", "revision": 0, "items": [], "reservations": {}, "events": {}},
        now=NOW,
    ).create()
    assert plan.optimized_basket.total == expected_total
    item = plan.optimized_basket.stores[0].items[0]
    assert item.packages_needed == (grams + 56) // 57 and item.package_quantity == 57
    assert plan.personal.checks["checkout_audit"]["passed"]
