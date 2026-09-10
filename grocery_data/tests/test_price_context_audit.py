from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient

from grocery_data.__main__ import main as cli_main
from grocery_data.app.domain.enums import PriceContextState
from grocery_data.app.main import create_app
from grocery_data.app.services.price_context_audit import PriceContextAuditor
from grocery_data.app.storage import (
    create_database_engine,
    create_schema,
    create_session_factory,
    session_scope,
)
from grocery_data.app.storage.models import (
    CatalogSnapshotModel,
    PhysicalStoreModel,
    ProviderStoreIdentityMappingModel,
    RawSnapshotModel,
    SourceProductModel,
    StoreContextLinkModel,
    StoreModel,
)

NOW = datetime(2026, 8, 24, 10, tzinfo=UTC)
FIXTURE = Path(__file__).parents[1] / "app" / "services" / "fixtures" / "official_stores_lund.json"


def _storage():  # type: ignore[no-untyped-def]
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    return engine, create_session_factory(engine)


def _load_all_official_lund_stores(session) -> dict[tuple[str, str], str]:  # type: ignore[no-untyped-def]
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    identities: dict[tuple[str, str], str] = {}
    for chain, group in payload["chains"].items():
        for source in group["stores"]:
            external_id = source["external_store_id"]
            physical_id = f"physical:{chain}:{external_id}"
            aliases = (
                [source["secondary_external_store_id"]]
                if source.get("secondary_external_store_id")
                else []
            )
            session.add(
                PhysicalStoreModel(
                    id=physical_id,
                    chain=chain,
                    external_store_id=external_id,
                    external_store_aliases=aliases,
                    name=source["name"],
                    address=source.get("address"),
                    postal_code=source.get("postal_code"),
                    city=source.get("city"),
                    latitude=(Decimal(source["latitude"]) if source.get("latitude") else None),
                    longitude=(Decimal(source["longitude"]) if source.get("longitude") else None),
                    official_source=group["official_source"],
                    discovered_at=NOW,
                    last_seen_at=NOW,
                    is_active=True,
                    lifecycle_state="active",
                )
            )
            identities[(chain, external_id)] = physical_id
    session.flush()
    return identities


def _context_link(
    session,  # type: ignore[no-untyped-def]
    physical_id: str,
    *,
    provider: str,
    context_id: str,
    coverage: str,
    basket: bool,
    observed_at: datetime = NOW,
    channel: str = "catalog",
) -> None:
    session.add(
        StoreContextLinkModel(
            id=f"link-{len(session.new)}-{physical_id[-8:]}",
            physical_store_id=physical_id,
            grocery_context_id=context_id,
            source_provider=provider,
            source_channel=channel,
            grocery_context_name=context_id,
            price_context_type="online_store",
            coverage=coverage,
            relation_type="exact_store_online_context",
            confidence="exact",
            evidence="closed fixture exact identity",
            basket_eligible=basket,
            offers_only=coverage == "offers_only",
            snapshot_id=f"snapshot:{context_id}",
            observed_at=observed_at,
            linked_at=observed_at,
            last_verified_at=observed_at,
            is_active=True,
        )
    )


def _provider_mapping(
    session,  # type: ignore[no-untyped-def]
    physical_id: str,
    *,
    context_id: str | None,
    verified: bool,
) -> None:
    suffix = physical_id.replace(":", "-")[-20:]
    session.add(
        ProviderStoreIdentityMappingModel(
            id=f"map-{suffix}",
            physical_store_id=physical_id,
            provider="primat",
            provider_context_id=context_id if verified else None,
            provider_store_id=context_id if verified else None,
            confidence="exact_address" if verified else "none",
            status="verified" if verified else "unresolved",
            evidence=(
                "exact normalized address and chain"
                if verified
                else "bounded Lund provider response had no unique strong match"
            ),
            verified_identity_fingerprint="a" * 64 if verified else None,
            observed_identity_fingerprint="a" * 64 if verified else None,
            candidate_context_id=None,
            verified_at=NOW if verified else None,
            last_checked_at=NOW,
            is_active=True,
        )
    )


def _fresh_lidl_regional_snapshot(session) -> None:  # type: ignore[no-untyped-def]
    store = StoreModel(
        id="lidl-region-store",
        chain="lidl",
        external_id="public-default-region",
        name="Lidl Sverige – publika erbjudanden",
        city="Sverige",
        online_shopping=False,
        coverage="offers_only",
        price_context_type="regional",
        raw_reference="fixture://lidl-region",
        is_active=True,
        first_seen_at=NOW,
        last_seen_at=NOW,
    )
    snapshot = CatalogSnapshotModel(
        id="lidl-regional-snapshot",
        chain="lidl",
        scope_key="sverige",
        coverage="offers_only",
        state="promoted",
        is_active=True,
        connector_version="fixture-v1",
        parser_version="fixture-v1",
        normalizer_version="fixture-v1",
        created_at=NOW,
        promoted_at=NOW,
    )
    raw = RawSnapshotModel(
        id="lidl-regional-raw",
        catalog_snapshot_id=snapshot.id,
        chain="lidl",
        store_external_id=store.external_id,
        kind="offer_page",
        method="GET",
        url="https://public.example/lidl/offers",
        query={},
        fetched_at=NOW,
        http_status=200,
        content_type="application/json",
        payload_hash="b" * 64,
        payload_size=2,
        payload_location="fixture://lidl-offers.json",
        request_fingerprint="c" * 64,
        connector_version="fixture-v1",
    )
    session.add_all([store, snapshot, raw])
    session.flush()
    product = SourceProductModel(
        id="lidl-regional-product",
        catalog_snapshot_id=snapshot.id,
        raw_snapshot_id=raw.id,
        store_id=store.id,
        chain="lidl",
        store_external_id=store.external_id,
        external_product_id="offer-1",
        gtin="7310000000001",
        name="Regional fixture offer",
        category_path=[],
        sale_price=Decimal("19.90"),
        raw_reference="fixture://lidl-offers.json#offer-1",
        fetched_at=NOW,
        parser_version="fixture-v1",
        source_fields={},
        source_record_hash="d" * 64,
    )
    session.add(product)


def _populate_explained_lund(session) -> None:  # type: ignore[no-untyped-def]
    ids = _load_all_official_lund_stores(session)

    for external_id in ("2176", "2354"):
        _context_link(
            session,
            ids[("willys", external_id)],
            provider="own",
            context_id=f"own:willys:{external_id}",
            coverage="full_catalog",
            basket=True,
        )
    _context_link(
        session,
        ids[("willys", "2863")],
        provider="own",
        context_id="own:willys:2863",
        coverage="partial_catalog",
        basket=False,
    )
    _context_link(
        session,
        ids[("hemkop", "4224")],
        provider="own",
        context_id="own:hemkop:4224",
        coverage="full_online_catalog",
        basket=True,
    )
    # Karhögstorg 4123 intentionally has an exact GroceryContext identity but
    # no promoted price snapshot in this closed fixture, so it is explained as
    # NO_PRICE_CONTEXT rather than unknown.

    for index, (chain, group) in enumerate((("ica", 2), ("coop", 1))):
        chain_ids = [
            (external_id, physical_id)
            for (candidate_chain, external_id), physical_id in ids.items()
            if candidate_chain == chain
        ]
        for position, (_external_id, physical_id) in enumerate(chain_ids):
            context_id = f"primat:{chain}:{position}"
            verified = position < group
            _provider_mapping(
                session,
                physical_id,
                context_id=context_id,
                verified=verified,
            )
            if verified:
                _context_link(
                    session,
                    physical_id,
                    provider="primat",
                    context_id=context_id,
                    coverage="full_catalog",
                    basket=True,
                )

    _fresh_lidl_regional_snapshot(session)
    # A Malmö City Gross price context must never appear in the Lund audit.
    session.add(
        PhysicalStoreModel(
            id="physical:citygross:hyllie",
            chain="citygross",
            external_store_id="hyllie",
            name="City Gross Malmö Hyllie",
            address="Hyllie stationstorg 2",
            postal_code="21532",
            city="Malmö",
            official_source="fixture://citygross-malmo",
            discovered_at=NOW,
            last_seen_at=NOW,
            is_active=True,
            lifecycle_state="active",
        )
    )
    session.flush()


def test_all_23_official_lund_stores_have_exactly_one_explained_state() -> None:
    engine, factory = _storage()
    try:
        with session_scope(factory) as session:
            _populate_explained_lund(session)
            report = PriceContextAuditor(session).audit("Lund", now=NOW)

            assert report.physical_stores == 23
            assert report.explained_states == 23
            assert report.unknown == 0
            assert sum(report.state_counts.values()) == 23
            assert report.state_counts == {
                "external_full_context": 3,
                # Coop now has OWN as its basket primary. Missing or unresolved
                # Primat fallback identities must therefore not masquerade as
                # unresolved primary mappings for the six Coop fixtures that
                # have no verified price context.
                "mapping_unresolved": 7,
                "no_price_context": 7,
                "own_full_context": 3,
                "own_offers_only": 1,
                "regional_offers_only": 2,
            }
            assert report.chains["citygross"].physical_stores == 0
            assert report.chains["citygross"].chain_reason == (
                "NO_LUND_CONTEXT: no active physical stores registered for Lund"
            )
    finally:
        engine.dispose()


def test_offers_only_and_regional_lidl_are_never_basket_eligible() -> None:
    engine, factory = _storage()
    try:
        with session_scope(factory) as session:
            _populate_explained_lund(session)
            report = PriceContextAuditor(session).audit("Lund", now=NOW)
            stortorget = next(
                row for row in report.chains["willys"].stores if row.name.endswith("Stortorget")
            )
            assert stortorget.state is PriceContextState.OWN_OFFERS_ONLY
            assert stortorget.coverage == "partial_catalog"
            assert stortorget.basket_eligible is False

            assert len(report.chains["lidl"].stores) == 2
            assert all(
                row.state is PriceContextState.REGIONAL_OFFERS_ONLY
                and row.context_scope == "regional"
                and row.basket_eligible is False
                for row in report.chains["lidl"].stores
            )
            assert all(not row.contexts for row in report.chains["lidl"].stores)
            assert not any(
                link.physical_store_id.startswith("physical:lidl:")
                for link in session.query(StoreContextLinkModel).all()
            )
    finally:
        engine.dispose()


def test_stale_own_offer_does_not_hide_unresolved_external_basket_mapping() -> None:
    engine, factory = _storage()
    try:
        with session_scope(factory) as session:
            physical = PhysicalStoreModel(
                id="physical:ica:stale",
                chain="ica",
                external_store_id="stale",
                name="ICA stale fixture",
                city="Lund",
                official_source="fixture://ica",
                discovered_at=NOW,
                last_seen_at=NOW,
                is_active=True,
                lifecycle_state="active",
            )
            session.add(physical)
            session.flush()
            _context_link(
                session,
                physical.id,
                provider="own",
                context_id="own:ica:stale-offers",
                coverage="offers_only",
                basket=False,
                observed_at=NOW - timedelta(hours=49),
                channel="offers",
            )
            _provider_mapping(
                session,
                physical.id,
                context_id=None,
                verified=False,
            )
            session.flush()

            [item] = PriceContextAuditor(session).audit("Lund", now=NOW).chains["ica"].stores
            assert item.state is PriceContextState.MAPPING_UNRESOLVED
            assert item.basket_eligible is False
    finally:
        engine.dispose()


def test_stale_verified_primary_context_remains_explicitly_stale() -> None:
    engine, factory = _storage()
    try:
        with session_scope(factory) as session:
            physical = PhysicalStoreModel(
                id="physical:ica:stale-primary",
                chain="ica",
                external_store_id="stale-primary",
                name="ICA stale primary fixture",
                city="Lund",
                official_source="fixture://ica",
                discovered_at=NOW,
                last_seen_at=NOW,
                is_active=True,
                lifecycle_state="active",
            )
            session.add(physical)
            session.flush()
            context_id = "primat:ica:stale-primary"
            _context_link(
                session,
                physical.id,
                provider="primat",
                context_id=context_id,
                coverage="full_catalog",
                basket=True,
                observed_at=NOW - timedelta(hours=49),
            )
            _provider_mapping(
                session,
                physical.id,
                context_id=context_id,
                verified=True,
            )
            session.flush()

            [item] = PriceContextAuditor(session).audit("Lund", now=NOW).chains["ica"].stores
            assert item.state is PriceContextState.STALE_CONTEXT
            assert item.price_source == "primat"
            assert item.basket_eligible is False
    finally:
        engine.dispose()


def test_fresh_external_offers_identity_is_explained_but_never_basket_eligible() -> None:
    engine, factory = _storage()
    try:
        with session_scope(factory) as session:
            physical = PhysicalStoreModel(
                id="physical:coop:offers-only",
                chain="coop",
                external_store_id="offers-only",
                name="Coop offers-only fixture",
                city="Lund",
                official_source="fixture://coop",
                discovered_at=NOW,
                last_seen_at=NOW,
                is_active=True,
                lifecycle_state="active",
            )
            session.add(physical)
            session.flush()
            context_id = "primat:coop:offers-only"
            _context_link(
                session,
                physical.id,
                provider="primat",
                context_id=context_id,
                coverage="offers_only",
                basket=False,
            )
            _provider_mapping(
                session,
                physical.id,
                context_id=context_id,
                verified=True,
            )
            session.flush()

            [item] = PriceContextAuditor(session).audit("Lund", now=NOW).chains["coop"].stores
            assert item.state is PriceContextState.NO_PRICE_CONTEXT
            assert item.price_source == "primat"
            assert item.coverage == "offers_only"
            assert item.fresh is True
            assert item.basket_eligible is False
            assert "non-basket coverage" in item.reason
            assert [context.grocery_context_id for context in item.contexts] == [context_id]
    finally:
        engine.dispose()


def test_fallback_mapping_drift_does_not_override_own_primary_state() -> None:
    engine, factory = _storage()
    try:
        with session_scope(factory) as session:
            physical = PhysicalStoreModel(
                id="physical:coop:drift",
                chain="coop",
                external_store_id="drift",
                name="Coop drift fixture",
                city="Lund",
                official_source="fixture://coop",
                discovered_at=NOW,
                last_seen_at=NOW,
                is_active=True,
                lifecycle_state="active",
            )
            session.add(physical)
            session.flush()
            context_id = "primat:coop:lkg"
            _context_link(
                session,
                physical.id,
                provider="primat",
                context_id=context_id,
                coverage="full_catalog",
                basket=True,
            )
            _provider_mapping(
                session,
                physical.id,
                context_id=context_id,
                verified=True,
            )
            session.flush()
            mapping = session.query(ProviderStoreIdentityMappingModel).one()
            mapping.status = "mapping_drift"
            mapping.candidate_context_id = "primat:coop:new-candidate"
            mapping.observed_identity_fingerprint = "e" * 64
            mapping.drift_detected_at = NOW
            session.flush()

            [item] = PriceContextAuditor(session).audit("Lund", now=NOW).chains["coop"].stores
            # Coop's accepted OWN catalogue is primary. A drifting Primat LKG
            # is retained as diagnostic evidence, but it is only an explicit
            # fallback and therefore cannot define the store's primary state.
            assert item.state is PriceContextState.NO_PRICE_CONTEXT
            assert item.basket_eligible is False
            assert item.mappings[0].status == "mapping_drift"
            assert "no active fresh store-specific price context" in item.reason
    finally:
        engine.dispose()


def test_price_context_api_is_read_only_and_exposes_per_store_reason(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    engine, factory = _storage()
    try:
        with session_scope(factory) as session:
            _populate_explained_lund(session)
        monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
        client = TestClient(create_app(factory))

        response = client.get("/stores/price-contexts", params={"city": "Lund"})

        assert response.status_code == 200
        body = response.json()
        assert body["physical_stores"] == body["explained_states"] == 23
        assert body["unknown"] == 0
        assert body["live_provider_requests"] == 0
        assert body["physical_validation_required"] is False
        assert all(
            store["reason"] for chain in body["chains"].values() for store in chain["stores"]
        )
    finally:
        engine.dispose()


def test_audit_price_contexts_cli_is_offline_and_has_no_unknown_state(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    database = tmp_path / "price-context-cli.sqlite"
    database_url = f"sqlite+pysqlite:///{database.as_posix()}"
    engine = create_database_engine(database_url)
    create_schema(engine)
    factory = create_session_factory(engine)
    timestamp = datetime.now(tz=UTC)
    with session_scope(factory) as session:
        session.add(
            PhysicalStoreModel(
                id="physical:hemkop:4123",
                chain="hemkop",
                external_store_id="4123",
                name="Hemköp Lund Karhögstorg",
                address="Karhögstorg 2A",
                postal_code="22358",
                city="Lund",
                official_source="fixture://hemkop/4123",
                discovered_at=timestamp,
                last_seen_at=timestamp,
                is_active=True,
                lifecycle_state="active",
            )
        )
    engine.dispose()
    monkeypatch.setenv("GROCERY_DATABASE_URL", database_url)
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")

    assert cli_main(["audit-price-contexts", "--city", "Lund"]) == 0

    body = json.loads(capsys.readouterr().out)
    assert body["physical_stores"] == body["explained_states"] == 1
    assert body["unknown"] == 0
    assert body["state_counts"] == {"no_price_context": 1}
    assert body["live_provider_requests"] == 0
