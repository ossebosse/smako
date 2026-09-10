from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from grocery_data.__main__ import main
from grocery_data.app.domain import (
    Chain,
    CoverageLevel,
    PhysicalStore,
    ProviderStoreMappingStatus,
    StoreIdentityMatchConfidence,
)
from grocery_data.app.services.provider_store_identity import (
    PrimatCatalogSmokeRequest,
    PrimatContextSmokeBundle,
    PrimatContextSmokeEvidence,
    PrimatSmokeProductSample,
    PrimatStoreCandidate,
    PrimatStoreDiscoveryBundle,
    PrimatStoreDiscoveryRequest,
    ProviderContextSmokeActivationService,
    ProviderStoreIdentityMappingService,
    read_primat_store_discovery_bundle,
)
from grocery_data.app.storage import (
    PhysicalStoreRepository,
    ProviderStoreIdentityMappingRepository,
    StoreContextLinkRepository,
    create_database_engine,
    create_schema,
    create_session_factory,
    session_scope,
)

NOW = datetime(2026, 8, 24, 8, tzinfo=UTC)
RESPONSE_HASH = "a" * 64


@pytest.fixture
def storage():  # type: ignore[no-untyped-def]
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    try:
        yield factory
    finally:
        engine.dispose()


def _physical(
    chain: Chain,
    external_id: str,
    name: str,
    address: str,
    postal_code: str,
    *,
    aliases: tuple[str, ...] = (),
    latitude: Decimal | None = None,
    longitude: Decimal | None = None,
) -> PhysicalStore:
    return PhysicalStore(
        id=f"physical:{chain.value}:{external_id}",
        chain=chain,
        external_store_id=external_id,
        external_store_aliases=aliases,
        name=name,
        address=address,
        postal_code=postal_code,
        city="Lund",
        latitude=latitude,
        longitude=longitude,
        official_source=f"https://official.example/{chain.value}/{external_id}",
        discovered_at=NOW,
        last_seen_at=NOW,
    )


def _candidate(
    chain: Chain,
    context: str,
    provider_id: str,
    name: str,
    *,
    address: str | None = None,
    postal_code: str | None = None,
    latitude: Decimal | None = None,
    longitude: Decimal | None = None,
    observed_at: datetime = NOW,
) -> PrimatStoreCandidate:
    return PrimatStoreCandidate(
        provider_context_id=f"primat:{context}",
        provider_store_id=provider_id,
        chain=chain,
        name=name,
        address=address,
        postal_code=postal_code,
        city="Lund",
        latitude=latitude,
        longitude=longitude,
        tier="full",
        coverage=CoverageLevel.FULL_CATALOG,
        selected=True,
        source_snapshot_id="primat-resolve-fixture",
        observed_at=observed_at,
        raw_reference=f"response:{RESPONSE_HASH}:stores[0]",
    )


def _bundle(
    *items: PrimatStoreCandidate,
    captured_at: datetime = NOW,
) -> PrimatStoreDiscoveryBundle:
    return PrimatStoreDiscoveryBundle(
        schema_version="primat-store-discovery-bundle-v1",
        city="Lund",
        postal_code="22350",
        captured_at=captured_at,
        request=PrimatStoreDiscoveryRequest(
            host="primat.nu",
            path="/api/v3/stores/resolve",
            content_type="application/json",
            response_sha256=RESPONSE_HASH,
        ),
        raw_rows=len(items),
        items=items,
    )


def _smoke_bundle(
    *,
    context_id: str,
    provider_store_id: str,
    chain: Chain,
    observed_at: datetime,
    product_rows: int = 2,
    priced_rows: int = 2,
    coverage: CoverageLevel = CoverageLevel.FULL_CATALOG,
) -> PrimatContextSmokeBundle:
    product_hash = "b" * 64
    samples = (
        PrimatSmokeProductSample(
            product_id="milk-1",
            name="Mjölk 1 l",
            current_price=Decimal("16.90"),
        ),
    ) if priced_rows else ()
    return PrimatContextSmokeBundle(
        schema_version="primat-context-smoke-bundle-v1",
        city="Lund",
        postal_code="22350",
        captured_at=observed_at,
        store_discovery_response_sha256=RESPONSE_HASH,
        resolve_request=PrimatStoreDiscoveryRequest(
            host="primat.nu",
            path="/api/v3/stores/resolve",
            content_type="application/json",
            response_sha256="c" * 64,
        ),
        product_request=PrimatCatalogSmokeRequest(
            host="primat.nu",
            path="/api/v3/products",
            content_type="application/json",
            response_sha256=product_hash,
        ),
        identity_revalidated=True,
        query_label="common-packaged-food",
        items=(
            PrimatContextSmokeEvidence(
                provider_context_id=context_id,
                provider_store_id=provider_store_id,
                chain=chain,
                coverage=coverage,
                source_snapshot_id="primat-smoke-snapshot",
                observed_at=observed_at,
                product_rows=product_rows,
                priced_product_rows=priced_rows,
                samples=samples,
                raw_reference=f"response:{product_hash}:context:{context_id}",
            ),
        ),
    )


def test_exact_address_mapping_is_persisted_but_smoke_pending(storage) -> None:  # type: ignore[no-untyped-def]
    with session_scope(storage) as session:
        physical = PhysicalStoreRepository(session).upsert(
            _physical(
                Chain.ICA,
                "official-ica",
                "ICA Kvantum Clemenstorget",
                "Clemenstorget 5",
                "22221",
            )
        )
        report = ProviderStoreIdentityMappingService(session).reconcile(
            _bundle(
                _candidate(
                    Chain.ICA,
                    "ica:provider-ica",
                    "provider-ica",
                    "Provider display label",
                    address="Clemenstorget 5",
                    postal_code="22221",
                )
            ),
            city="Lund",
            persist=True,
        )
        mapping = ProviderStoreIdentityMappingRepository(session).get(
            physical.id,
            provider="primat",
        )
        links = StoreContextLinkRepository(session).list_for_physical_store(physical.id)

    assert report.verified == 1
    assert report.fuzzy_links == 0
    assert report.network_requests == 0
    assert report.decisions[0].confidence == StoreIdentityMatchConfidence.EXACT_ADDRESS
    assert mapping is not None
    assert mapping.status == ProviderStoreMappingStatus.VERIFIED.value
    assert mapping.provider_context_id == "primat:ica:provider-ica"
    assert len(links) == 1
    assert links[0].basket_eligible is False
    assert links[0].evidence.endswith("catalog smoke pending")


def test_exact_official_alias_id_is_strong(storage) -> None:  # type: ignore[no-untyped-def]
    with session_scope(storage) as session:
        PhysicalStoreRepository(session).upsert(
            _physical(
                Chain.COOP,
                "3813",
                "Coop Mårtenstorget",
                "Mårtenstorget 11",
                "22351",
                aliases=("106430",),
            )
        )
        report = ProviderStoreIdentityMappingService(session).reconcile(
            _bundle(
                _candidate(
                    Chain.COOP,
                    "coop:106430",
                    "106430",
                    "Unrelated provider label",
                )
            ),
            city="Lund",
        )

    assert report.verified == 1
    assert report.decisions[0].confidence == StoreIdentityMatchConfidence.EXACT_ID


def test_fuzzy_name_is_suggestion_only_and_never_links(storage) -> None:  # type: ignore[no-untyped-def]
    with session_scope(storage) as session:
        physical = PhysicalStoreRepository(session).upsert(
            _physical(
                Chain.ICA,
                "official-ica",
                "ICA Maxi Gunnesbo",
                "Traktorvägen 1",
                "22660",
            )
        )
        report = ProviderStoreIdentityMappingService(session).reconcile(
            _bundle(
                _candidate(
                    Chain.ICA,
                    "ica:other",
                    "other",
                    "ICA Maxi Lund Gunnesbo",
                    address="Annan gata 9",
                    postal_code="22222",
                )
            ),
            city="Lund",
            persist=True,
        )
        links = StoreContextLinkRepository(session).list_for_physical_store(physical.id)

    assert report.unresolved == 1
    assert report.automatic_links == 0
    assert report.decisions[0].confidence == StoreIdentityMatchConfidence.PROBABLE
    assert report.decisions[0].suggestions
    assert links == []


def test_ambiguous_exact_address_remains_unresolved(storage) -> None:  # type: ignore[no-untyped-def]
    with session_scope(storage) as session:
        physical = PhysicalStoreRepository(session).upsert(
            _physical(
                Chain.COOP,
                "official-coop",
                "Coop Lund",
                "Testgatan 1",
                "22350",
            )
        )
        report = ProviderStoreIdentityMappingService(session).reconcile(
            _bundle(
                _candidate(
                    Chain.COOP,
                    "coop:a",
                    "a",
                    "Coop A",
                    address="Testgatan 1",
                    postal_code="22350",
                ),
                _candidate(
                    Chain.COOP,
                    "coop:b",
                    "b",
                    "Coop B",
                    address="Testgatan 1",
                    postal_code="22350",
                ),
            ),
            city="Lund",
            persist=True,
        )
        mapping = ProviderStoreIdentityMappingRepository(session).get(
            physical.id,
            provider="primat",
        )

    assert report.unresolved == 1
    assert report.decisions[0].confidence == StoreIdentityMatchConfidence.AMBIGUOUS
    assert mapping is not None
    assert mapping.status == ProviderStoreMappingStatus.UNRESOLVED.value


def test_mapping_drift_retains_lkg_context_and_link(storage) -> None:  # type: ignore[no-untyped-def]
    first = _candidate(
        Chain.ICA,
        "ica:2771",
        "2771",
        "ICA Clemenstorget",
        address="Clemenstorget 5",
        postal_code="22221",
    )
    changed_at = NOW + timedelta(hours=1)
    changed = _candidate(
        Chain.ICA,
        "ica:2771",
        "2771",
        "ICA Clemenstorget",
        address="Providergatan 99",
        postal_code="22221",
        observed_at=changed_at,
    )
    with session_scope(storage) as session:
        physical = PhysicalStoreRepository(session).upsert(
            _physical(
                Chain.ICA,
                "1004409",
                "ICA Clemenstorget",
                "Clemenstorget 5",
                "22221",
                aliases=("2771",),
            )
        )
        service = ProviderStoreIdentityMappingService(session)
        first_report = service.reconcile(_bundle(first), city="Lund", persist=True)
        changed_report = service.reconcile(
            _bundle(changed, captured_at=changed_at),
            city="Lund",
            persist=True,
        )
        mapping = ProviderStoreIdentityMappingRepository(session).get(
            physical.id,
            provider="primat",
        )
        links = StoreContextLinkRepository(session).list_for_physical_store(physical.id)

    assert first_report.verified == 1
    assert changed_report.mapping_drift == 1
    assert changed_report.decisions[0].lkg_retained is True
    assert mapping is not None
    assert mapping.status == ProviderStoreMappingStatus.MAPPING_DRIFT.value
    assert mapping.provider_context_id == "primat:ica:2771"
    assert mapping.verified_identity_fingerprint != mapping.observed_identity_fingerprint
    assert len(links) == 1
    assert links[0].grocery_context_id == "primat:ica:2771"


def test_unresolved_mapping_can_become_verified_when_strong_evidence_appears(
    storage,  # type: ignore[no-untyped-def]
) -> None:
    with session_scope(storage) as session:
        physical = PhysicalStoreRepository(session).upsert(
            _physical(
                Chain.COOP,
                "3813",
                "Coop Mårtenstorget",
                "Mårtenstorget 11",
                "22351",
                aliases=("106430",),
            )
        )
        service = ProviderStoreIdentityMappingService(session)
        unresolved = service.reconcile(
            _bundle(
                _candidate(
                    Chain.COOP,
                    "coop:other",
                    "other",
                    "Coop Somewhere",
                )
            ),
            city="Lund",
            persist=True,
        )
        later = NOW + timedelta(hours=1)
        verified = service.reconcile(
            _bundle(
                _candidate(
                    Chain.COOP,
                    "coop:106430",
                    "106430",
                    "Provider label",
                    observed_at=later,
                ),
                captured_at=later,
            ),
            city="Lund",
            persist=True,
        )
        mapping = ProviderStoreIdentityMappingRepository(session).get(
            physical.id,
            provider="primat",
        )

    assert unresolved.unresolved == 1
    assert verified.verified == 1
    assert mapping is not None
    assert mapping.verified_at == later


def test_only_catalog_smoke_promotes_verified_identity_link_to_basket(storage) -> None:  # type: ignore[no-untyped-def]
    smoke_at = NOW + timedelta(minutes=10)
    with session_scope(storage) as session:
        physical = PhysicalStoreRepository(session).upsert(
            _physical(
                Chain.COOP,
                "3813",
                "Coop Mårtenstorget",
                "Mårtenstorget 11",
                "22351",
                aliases=("106430",),
            )
        )
        ProviderStoreIdentityMappingService(session).reconcile(
            _bundle(
                _candidate(
                    Chain.COOP,
                    "coop:106430",
                    "106430",
                    "Provider label",
                )
            ),
            city="Lund",
            persist=True,
        )
        before = StoreContextLinkRepository(session).list_for_physical_store(physical.id)[0]
        assert before.basket_eligible is False

        report = ProviderContextSmokeActivationService(session).activate(
            _smoke_bundle(
                context_id="primat:coop:106430",
                provider_store_id="106430",
                chain=Chain.COOP,
                observed_at=smoke_at,
            ),
            city="Lund",
            persist=True,
        )
        after = StoreContextLinkRepository(session).list_for_physical_store(physical.id)[0]

    assert report.contexts_activated == 1
    assert report.contexts_rejected == 0
    assert report.network_requests == 0
    assert after.basket_eligible is True
    assert after.snapshot_id == "primat-smoke-snapshot"
    assert after.observed_at == smoke_at


def test_smoke_with_wrong_provider_identity_is_rejected_and_link_stays_ineligible(
    storage,  # type: ignore[no-untyped-def]
) -> None:
    with session_scope(storage) as session:
        physical = PhysicalStoreRepository(session).upsert(
            _physical(
                Chain.ICA,
                "1004409",
                "ICA Clemenstorget",
                "Clemenstorget 5",
                "22221",
                aliases=("2771",),
            )
        )
        ProviderStoreIdentityMappingService(session).reconcile(
            _bundle(
                _candidate(
                    Chain.ICA,
                    "ica:2771",
                    "2771",
                    "Provider label",
                )
            ),
            city="Lund",
            persist=True,
        )
        report = ProviderContextSmokeActivationService(session).activate(
            _smoke_bundle(
                context_id="primat:ica:2771",
                provider_store_id="different-provider-id",
                chain=Chain.ICA,
                observed_at=NOW + timedelta(minutes=5),
            ),
            city="Lund",
            persist=True,
        )
        link = StoreContextLinkRepository(session).list_for_physical_store(physical.id)[0]

    assert report.contexts_activated == 0
    assert report.decisions[0].reason == (
        "smoke provider store ID differs from verified mapping"
    )
    assert link.basket_eligible is False


def test_priced_smoke_never_upgrades_offers_only_discovery_to_basket(storage) -> None:  # type: ignore[no-untyped-def]
    with session_scope(storage) as session:
        physical = PhysicalStoreRepository(session).upsert(
            _physical(
                Chain.COOP,
                "3813",
                "Coop Mårtenstorget",
                "Mårtenstorget 11",
                "22351",
                aliases=("106430",),
            )
        )
        ProviderStoreIdentityMappingService(session).reconcile(
            _bundle(
                _candidate(
                    Chain.COOP,
                    "coop:106430",
                    "106430",
                    "Provider label",
                ).model_copy(update={"coverage": CoverageLevel.OFFERS_ONLY})
            ),
            city="Lund",
            persist=True,
        )
        report = ProviderContextSmokeActivationService(session).activate(
            _smoke_bundle(
                context_id="primat:coop:106430",
                provider_store_id="106430",
                chain=Chain.COOP,
                observed_at=NOW + timedelta(minutes=5),
                # Even a forged/misclassified full smoke must not override the
                # offers-only tier persisted by store discovery.
                coverage=CoverageLevel.FULL_CATALOG,
            ),
            city="Lund",
            persist=True,
        )
        link = StoreContextLinkRepository(session).list_for_physical_store(physical.id)[0]

    assert report.contexts_activated == 0
    assert report.decisions[0].reason == (
        "mapped discovery context is not complete-catalog"
    )
    assert link.coverage == CoverageLevel.OFFERS_ONLY.value
    assert link.basket_eligible is False


def test_closed_replay_bundle_rejects_credentials(tmp_path: Path) -> None:
    payload = _bundle().model_dump(mode="json", by_alias=True)
    payload["authorization"] = "Bearer must-not-survive"
    path = tmp_path / "primat-stores.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="forbidden key"):
        read_primat_store_discovery_bundle(path)


def test_mapping_cli_replays_offline_and_persists_strong_mapping(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database = tmp_path / "mapping.sqlite"
    database_url = f"sqlite+pysqlite:///{database.as_posix()}"
    engine = create_database_engine(database_url)
    create_schema(engine)
    factory = create_session_factory(engine)
    with session_scope(factory) as session:
        PhysicalStoreRepository(session).upsert(
            _physical(
                Chain.COOP,
                "3813",
                "Coop Mårtenstorget",
                "Mårtenstorget 11",
                "22351",
                aliases=("106430",),
            )
        )
    engine.dispose()
    bundle_path = tmp_path / "primat-stores.json"
    bundle_path.write_text(
        json.dumps(
            _bundle(
                _candidate(
                    Chain.COOP,
                    "coop:106430",
                    "106430",
                    "Provider Coop",
                )
            ).model_dump(mode="json", by_alias=True)
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    monkeypatch.setenv("GROCERY_DATABASE_URL", database_url)

    assert (
        main(
            [
                "map-primat-stores",
                "--city",
                "Lund",
                "--database",
                str(database),
                "--input",
                str(bundle_path),
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)

    assert payload["live_provider_requests"] == 0
    assert payload["fuzzy_auto_links"] == 0
    assert payload["report"]["verified"] == 1
    check = create_database_engine(database_url)
    try:
        factory = create_session_factory(check)
        with session_scope(factory) as session:
            rows = ProviderStoreIdentityMappingRepository(session).list_for_city("Lund")
            assert len(rows) == 1
            assert rows[0].status == ProviderStoreMappingStatus.VERIFIED.value
    finally:
        check.dispose()
