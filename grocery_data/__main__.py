from __future__ import annotations

import argparse
import asyncio
import io
import json
import os
import sys
from contextlib import redirect_stdout
from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from uuid import uuid4

from sqlalchemy import func, select

from grocery_data.app.config import GroceryDataSettings, load_repository_dotenv
from grocery_data.app.connectors import ConnectorRegistry
from grocery_data.app.connectors.base import ConnectorFetchError, collection_policy_audit
from grocery_data.app.connectors.citygross import CityGrossConnector
from grocery_data.app.connectors.citygross.client import CityGrossClient
from grocery_data.app.connectors.coop import CoopOnlineCatalogConnector
from grocery_data.app.connectors.hemkop import (
    HemkopConnector,
    HemkopOperatorCrawlPolicy,
)
from grocery_data.app.connectors.ica import (
    IcaOnlineCatalogConnector,
    IcaOnlineSourcePolicyError,
)
from grocery_data.app.connectors.ica.online_catalog_models import (
    ICA_CATEGORY_TREE_KIND,
    ICA_PRODUCT_BATCH_KIND,
    ICA_PRODUCT_PAGE_KIND,
    ICA_STORE_CONTEXT_KIND,
)
from grocery_data.app.connectors.lidl import LidlConnector
from grocery_data.app.connectors.willys import WillysConnector
from grocery_data.app.connectors.willys.client import WillysClient
from grocery_data.app.domain import (
    Chain,
    Confidence,
    CoverageLevel,
    GeographicArea,
    PromotionType,
    RawBatch,
)
from grocery_data.app.domain.community_evidence import (
    CommunityEvidenceType,
    EvidenceVerificationStatus,
    ModerationDecision,
)
from grocery_data.app.domain.physical_price import (
    PhysicalPriceComparison,
    PhysicalPriceObservation,
    PhysicalProductIdentityStatus,
    PhysicalValidationSessionStatus,
)
from grocery_data.app.domain.source_strategy import (
    SourceProvider,
    SourceUnavailableError,
    source_strategy_for,
)
from grocery_data.app.monitoring import fingerprint_json
from grocery_data.app.services.catalog_recipe_coverage import CatalogRecipeCoverageBenchmark
from grocery_data.app.services.catalog_snapshot_quality import CatalogSnapshotQualityReporter
from grocery_data.app.services.closed_provider_cache import inspect_closed_provider_cache
from grocery_data.app.services.closed_provider_cache_store import (
    ClosedProviderCacheArtifactStore,
    ClosedProviderCacheValidationDecision,
)
from grocery_data.app.services.closed_provider_context_activation import (
    activate_closed_primat_context_links,
    validate_closed_primat_context_links,
)
from grocery_data.app.services.collector import GroceryCollector
from grocery_data.app.services.connector_acceptance import assess_parser_health
from grocery_data.app.services.coop_online_context_activation import (
    CoopOnlineContextActivationService,
)
from grocery_data.app.services.coop_refresh_configuration import (
    COOP_VERIFIED_ONLINE_CONTEXT_ID,
    assess_coop_refresh_configuration,
)
from grocery_data.app.services.daily_refresh import (
    UniverseRefreshHook,
    report_from_collection_results,
    run_universe_refresh,
)
from grocery_data.app.services.external_price_import import ExternalPriceSnapshotImportService
from grocery_data.app.services.freshness import (
    FreshnessPolicy,
    FreshnessState,
    assess_freshness,
    next_scheduled_refresh,
    project_source_freshness,
)
from grocery_data.app.services.hemkop_context_collection import (
    HemkopContextCollectionPlan,
    HemkopContextCollectionTarget,
    HemkopMultiContextCollectionPlanner,
)
from grocery_data.app.services.ica_recipe_coverage import RecipeQueryCoverageBenchmark
from grocery_data.app.services.manual_refresh_operations import (
    REFRESH_PARENT_LOCK_NONCE_ENV,
    RefreshAlreadyRunningError,
    RefreshRunLock,
    credential_safe_report,
    production_refresh_lock_path,
    refresh_lock_owned_by_process,
    write_refresh_report,
)
from grocery_data.app.services.official_store_discovery import (
    OfficialStoreDiscoveryService,
    fixture_official_store_adapters,
    live_official_store_adapters,
)
from grocery_data.app.services.physical_price_candidates import (
    PersistedExternalPhysicalPriceCandidateReader,
    PersistedPhysicalPriceCandidateReader,
    combined_candidates_for_observation,
    expected_providers_for_store,
    physical_observation_from_row,
)
from grocery_data.app.services.physical_price_validation import (
    PhysicalPriceValidationService,
    build_accuracy_report,
    derived_observation_confidence,
)
from grocery_data.app.services.physical_session_reconciliation import (
    PhysicalSessionComparisonBundle,
    PhysicalSessionReconciliationService,
)
from grocery_data.app.services.physical_validation_v3 import (
    PhysicalValidationV3Service,
)
from grocery_data.app.services.prepared_universe_activation import (
    PreparedUniverseArtifactRefreshHook,
    PreparedUniverseArtifactStore,
    validate_backend_prepared_universe_artifact,
)
from grocery_data.app.services.price_context_audit import PriceContextAuditor
from grocery_data.app.services.primat_comparison import compare_export_files
from grocery_data.app.services.provider_store_identity import (
    ProviderContextSmokeActivationService,
    ProviderStoreIdentityMappingService,
    read_primat_context_smoke_bundle,
    read_primat_store_discovery_bundle,
)
from grocery_data.app.services.purchase_model_analysis import PurchaseModelAnalyzer
from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
from grocery_data.app.services.replay import DatabaseReplayService
from grocery_data.app.services.snapshot_manager import SnapshotManager
from grocery_data.app.services.store_context_reconciliation import (
    CredentialFreeContextImporter,
    ExactStoreContextReconciler,
    OwnContextEvidenceProjector,
    read_credential_free_context_bundle,
)
from grocery_data.app.services.store_coverage import StoreCoverageAuditor
from grocery_data.app.storage import (
    CommunityEvidenceRepository,
    ConnectorHealthRepository,
    PhysicalPriceObservationRepository,
    PhysicalStoreRepository,
    PhysicalValidationSessionRepository,
    PriceObservationModel,
    SessionFactory,
    SnapshotRepository,
    create_database_engine,
    create_schema,
    create_session_factory,
    session_scope,
)

# Backwards-compatible CLI seam for tests and callers that used to patch the
# module-level name. This still delegates to the repository-scoped loader,
# including its PYTHON_DOTENV_DISABLED fail-closed switch.
load_dotenv = load_repository_dotenv


def _json(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def _runtime() -> tuple[GroceryDataSettings, object, object]:
    settings = GroceryDataSettings.from_env()
    engine = create_database_engine(settings.database_url)
    return settings, engine, create_session_factory(engine)


def _explicit_sqlite_runtime(database: str | Path) -> tuple[Path, object, object]:
    """Open an existing explicitly named SQLite DB; never fall back to defaults."""

    resolved = Path(database).resolve(strict=True)
    if not resolved.is_file():
        raise ValueError("explicit database must be a regular SQLite file")
    engine = create_database_engine(f"sqlite+pysqlite:///{resolved.as_posix()}")
    return resolved, engine, create_session_factory(engine)


def _policy_audit_fields(audit: object | None) -> dict[str, object]:
    if audit is None:
        return {}
    model_dump = getattr(audit, "model_dump", None)
    if not callable(model_dump):
        raise TypeError("source policy audit must be a validated domain model")
    return dict(model_dump(mode="json"))


def _store_discovery_connector(chain: Chain):
    """Create live store discovery without granting REVIEW crawl authority."""

    if chain is Chain.CITY_GROSS:
        return CityGrossConnector.for_bounded_discovery()
    if chain is Chain.HEMKOP:
        return HemkopConnector.for_bounded_discovery()
    return ConnectorRegistry().create(chain)


def _collection_connector(chain: Chain):
    """Create the operation-specific collector, preserving source-policy gates."""

    if chain is Chain.WILLYS:
        from grocery_data.app.services.source_artifact import (
            SourceArtifactError,
            willys_collection_location,
        )

        if willys_collection_location() == "LOCAL_RELAY":
            raise SourceArtifactError("Willys direct collection is disabled; use a verified import")

    if chain is Chain.CITY_GROSS:
        return CityGrossConnector.for_full_collection()
    if chain is Chain.HEMKOP:
        return HemkopConnector.for_full_collection()
    if chain is Chain.LIDL:
        # Registry creation is deliberately bounded for discovery/canaries.
        # The daily collection path must traverse the complete published offer
        # surface so its OFFERS_ONLY snapshot has a proved termination count.
        return LidlConnector()
    return ConnectorRegistry().create(chain)


def _ica_browser_connector(
    store_or_context: str,
    *,
    full_catalog: bool,
) -> IcaOnlineCatalogConnector:
    """Build an exact ephemeral-browser ICA connector behind existing gates."""

    if full_catalog:
        raise IcaOnlineSourcePolicyError(
            "ICA browser full collection remains disabled until an observer-backed "
            "full traversal has passed the one-category proof"
        )
    return IcaOnlineCatalogConnector.for_bounded_browser_discovery(store_or_context)


def _ica_browser_category_proof_connector(
    store_or_context: str,
) -> tuple[IcaOnlineCatalogConnector, object]:
    """Build the separately authorized one-category browser proof."""

    connector = IcaOnlineCatalogConnector.for_browser_category_proof(store_or_context)
    assert connector.client is not None
    return connector, connector.client


def _exact_collection_connector(
    chain: Chain,
    context_store_id: str,
    *,
    ica_transport: str = "http",
):
    """Create one exact-context collector without weakening connector policy."""

    if chain is Chain.HEMKOP:
        return HemkopConnector.for_exact_full_collection(context_store_id)
    if chain is Chain.COOP:
        # Coop's value is an online assortment/price context, not a
        # physical-store identity.
        return CoopOnlineCatalogConnector.for_exact_full_collection(context_store_id)
    if chain is Chain.ICA:
        # The modern ICA source is independently scoped by its verified
        # region UUID. The registry's ordinary ICA connector remains the
        # accepted OFFERS_ONLY adapter.
        if ica_transport == "browser":
            return _ica_browser_connector(context_store_id, full_catalog=True)
        if ica_transport != "http":
            raise ValueError("unknown ICA collection transport")
        return IcaOnlineCatalogConnector.for_exact_full_collection(context_store_id)
    if ica_transport != "http":
        raise ValueError("--ica-transport browser is valid only for ICA")
    return _collection_connector(chain)


def _exact_collection_scope(chain: Chain, city: str, context_store_id: str) -> str:
    """Return the stable independently promotable scope for an exact context.

    Coop 730400 is one regional online price/assortment context shared by
    several pickup geographies, while ICA's region UUID is itself the stable
    online price-context identity. Qualifying either with the requested city
    would create duplicate logical snapshots for the same prices. Other exact
    physical-store collectors retain their backwards-compatible city namespace.
    """

    normalized_context = context_store_id.casefold().strip()
    if not normalized_context:
        raise ValueError("context_store_id must not be blank")
    if chain is Chain.COOP:
        return f"coop:online:{normalized_context}"
    if chain is Chain.ICA:
        return f"ica:online:{normalized_context}"
    normalized_city = city.casefold().strip()
    if not normalized_city:
        raise ValueError("city must not be blank")
    return f"{normalized_city}:{chain.value}:{normalized_context}"


async def _close_connector(connector: object | None) -> None:
    if connector is None:
        return
    close = getattr(connector, "aclose", None)
    if callable(close):
        await close()


async def _stores(args: argparse.Namespace) -> int:
    settings = GroceryDataSettings.from_env()
    registry = ConnectorRegistry()
    results = []
    exit_code = 0
    chains = list(Chain) if args.chain == "all" else [Chain(args.chain)]
    for chain in chains:
        descriptor = next(item for item in registry.descriptors() if item.chain == chain)
        if not descriptor.implemented:
            results.append(
                {
                    "chain": chain.value,
                    "coverage": descriptor.source_coverage.value,
                    "status": "not_implemented",
                    "limitation": descriptor.limitation,
                    "stores": [],
                }
            )
            exit_code = 2
            continue
        # Registry construction for City Gross is intentionally a bounded
        # one-page adapter. Store discovery must not require or inherit live
        # full-crawl authority merely because FULL_ONLINE was accepted.
        connector = _store_discovery_connector(chain)
        try:
            raw = await connector.fetch_stores(GeographicArea(city=args.city))
            records = FilesystemRawSnapshotStore(settings.raw_snapshot_root).save_batch(
                raw,
                snapshot_id=f"store-discovery-{uuid4().hex}",
            )
            stores = connector.parse_stores(
                raw,
                [f"raw:{record.document_id}" for record in records],
                GeographicArea(city=args.city),
            )
            results.append(
                {
                    "chain": chain.value,
                    "coverage": connector.coverage.value,
                    "status": "ok",
                    "stores": [store.model_dump(mode="json") for store in stores],
                    "raw_documents": len(records),
                    **_policy_audit_fields(collection_policy_audit(connector)),
                }
            )
        finally:
            await connector.aclose()
    _json({"city": args.city, "chains": results})
    return exit_code


async def _collect(args: argparse.Namespace) -> int:
    chains = list(Chain) if args.chain == "all" else [Chain(args.chain)]
    ica_transport = getattr(args, "ica_transport", "http")
    context_store_id = getattr(args, "context_store_id", None)
    if ica_transport == "browser" and (
        chains != [Chain.ICA]
        or context_store_id is None
        or not str(context_store_id).strip()
        or len(args.city) != 1
    ):
        raise ValueError(
            "--ica-transport browser requires one ICA chain, one city and --context-store-id"
        )
    settings, engine, factory = _runtime()
    registry = ConnectorRegistry()
    raw_store = FilesystemRawSnapshotStore(settings.raw_snapshot_root)
    results = []
    exit_code = 0
    try:
        for chain in chains:
            descriptor = next(item for item in registry.descriptors() if item.chain == chain)
            if not descriptor.implemented:
                results.append(
                    {
                        "chain": chain.value,
                        "status": "not_implemented",
                        "coverage": descriptor.source_coverage.value,
                        "limitation": descriptor.limitation,
                    }
                )
                exit_code = 2
                continue
            for city in args.city:
                connector = None
                try:
                    if context_store_id is not None:
                        if len(chains) != 1 or len(args.city) != 1:
                            raise ValueError(
                                "--context-store-id requires exactly one chain and one city"
                            )
                        connector = (
                            _exact_collection_connector(
                                chain,
                                context_store_id,
                                ica_transport=ica_transport,
                            )
                            if chain is Chain.ICA
                            else _exact_collection_connector(chain, context_store_id)
                        )
                        audit = collection_policy_audit(connector)
                        allowlist = tuple(getattr(audit, "store_allowlist", ()))
                        if set(allowlist) != {context_store_id}:
                            raise ValueError(
                                "--context-store-id must be the connector's one exact "
                                "operator-allowlisted store"
                            )
                        collection_scope = _exact_collection_scope(
                            chain,
                            city,
                            context_store_id,
                        )
                    else:
                        connector = _collection_connector(chain)
                        collection_scope = None
                    result = await GroceryCollector(factory, raw_store).collect_area(
                        connector,
                        GeographicArea(city=city),
                        auto_promote=not args.no_promote,
                        scope_key=collection_scope,
                    )
                    results.append(
                        {
                            "chain": chain.value,
                            "city": city,
                            "snapshot_id": result.snapshot_id,
                            "scope_key": result.scope_key,
                            "active_snapshot_id": result.active_snapshot_id,
                            "status": result.status.value,
                            "promoted": result.promoted,
                            "candidate_staged": args.no_promote and not result.promoted,
                            "stores": len(result.stores),
                            "metrics": result.metrics.model_dump(mode="json"),
                            "warnings": result.warnings,
                            **_policy_audit_fields(result.source_policy_audit),
                        }
                    )
                    if not result.promoted and not (
                        args.no_promote and result.status.value == "healthy"
                    ):
                        exit_code = 2
                except Exception as exc:  # noqa: BLE001 - sanitized per-chain CLI boundary
                    results.append(
                        {
                            "chain": chain.value,
                            "city": city,
                            "status": "failed",
                            "error_type": type(exc).__name__,
                        }
                    )
                    exit_code = 2
                finally:
                    await _close_connector(connector)
    finally:
        engine.dispose()
    _json({"results": results})
    return exit_code


# City Gross currently has a verified own online-store context only for Malmö.
# This is an explicit source fact, not a city-distance heuristic. Running a
# Lund candidate would create a predictably broken empty snapshot and obscure
# the healthy Malmö last-known-good state.
_UNVERIFIED_OWN_COLLECTION_CONTEXTS = frozenset(
    {
        (Chain.CITY_GROSS, "lund"),
        (Chain.HEMKOP, "lund"),
        (Chain.HEMKOP, "malmö"),
        (Chain.HEMKOP, "malmo"),
    }
)
# Cities whose OWN context plan must be derived from exact persisted official
# physical-store links instead of treating one city as one price context.
_MULTI_CONTEXT_OWN_COLLECTION_CITIES = frozenset(
    {
        (Chain.HEMKOP, "lund"),
        (Chain.HEMKOP, "malmö"),
        (Chain.HEMKOP, "malmo"),
    }
)
# Verified source-report scope for the production-approved Hemköp contexts.
# This prevents a global operator allowlist from making a Lund-only refresh
# fail merely because it also contains the separately approved Malmö ID.
_HEMKOP_VERIFIED_CONTEXT_CITIES = {
    "4123": "lund",
    "4224": "lund",
    "4247": "malmö",
}
_GLOBAL_OWN_COLLECTION_CONTEXTS = {Chain.LIDL: "Sverige"}

# Coop 730400 is a regional online assortment/price context, not a physical
# store.  Lund, Hjärup and Malmö pickup points have independently verified
# fulfillment relations to this one context.  A daily request containing more
# than one of these cities must still schedule exactly one catalogue job.
_COOP_ONLINE_CONTEXT_CITIES: dict[str, frozenset[str]] = {
    "730400": frozenset({"lund", "hjärup", "hjarup", "malmö", "malmo"}),
}


def _coop_online_context_for_city(city: str) -> str | None:
    normalized = city.casefold().strip()
    matches = [
        context_id
        for context_id, cities in _COOP_ONLINE_CONTEXT_CITIES.items()
        if normalized in cities
    ]
    if len(matches) > 1:
        raise ValueError("city maps to more than one Coop online price context")
    return matches[0] if matches else None


def _coop_context_served_cities(context_id: str, requested: list[str]) -> tuple[str, ...]:
    eligible = _COOP_ONLINE_CONTEXT_CITIES.get(context_id, frozenset())
    return tuple(
        {
            city.casefold().strip(): city.strip()
            for city in requested
            if city.strip() and city.casefold().strip() in eligible
        }.values()
    )


def _own_collection_roles(chain: Chain) -> tuple[str, ...]:
    """Return explicit OWN roles; external fallbacks never become crawl work."""

    try:
        strategy = source_strategy_for(chain)
    except SourceUnavailableError:
        return ()
    roles: list[str] = []
    if strategy.primary_source.provider is SourceProvider.OWN:
        roles.append("basket")
    if strategy.offer_source is not None and strategy.offer_source.provider is SourceProvider.OWN:
        roles.append("offers")
    if (
        strategy.enrichment_source is not None
        and strategy.enrichment_source.provider is SourceProvider.OWN
    ):
        roles.append("enrichment")
    return tuple(roles)


def _collect_all_plan(
    cities: list[str],
    registry: ConnectorRegistry | None = None,
    *,
    selected_chains: frozenset[Chain] | None = None,
) -> tuple[list[tuple[Chain, str, tuple[str, ...]]], list[dict[str, object]]]:
    """Build a deterministic daily OWN plan without invoking any connector."""

    connector_registry = registry or ConnectorRegistry()
    unique_cities = tuple(
        {city.casefold().strip(): city.strip() for city in cities if city.strip()}.values()
    )
    descriptors = {item.chain: item for item in connector_registry.descriptors()}
    targets: list[tuple[Chain, str, tuple[str, ...]]] = []
    skipped: list[dict[str, object]] = []
    for chain in Chain:
        if selected_chains and chain not in selected_chains:
            continue
        descriptor = descriptors[chain]
        roles = _own_collection_roles(chain)
        if chain is Chain.CITY_GROSS:
            from grocery_data.app.services.citygross_municipal_job import configuration
            try:
                _root, municipal = configuration()
            except (OSError, ValueError, KeyError, TypeError):
                municipal = {"enabled": False}
            if municipal["enabled"]:
                selected_cities = [city for city in unique_cities
                                   if city.casefold() == municipal["city"].casefold()]
                skipped.extend({"chain": chain.value, "city": city, "status": "not_applicable",
                                "reason": "municipal City Gross job owns exact source selection",
                                "source_management": "citygross_municipal",
                                "roles": roles} for city in selected_cities)
                if len(selected_cities) == len(unique_cities):
                    continue
        if chain is Chain.LIDL:
            from grocery_data.app.services.lidl_municipal_job import configuration
            try:
                _root, municipal = configuration()
            except (OSError, ValueError, KeyError, TypeError):
                municipal = {"enabled": False}
            if municipal["enabled"]:
                selected_cities = [city for city in unique_cities
                                   if city.casefold() == municipal["city"].casefold()]
                skipped.extend({"chain": chain.value, "city": city, "status": "not_applicable",
                                "reason": "municipal Lidl job owns exact source selection",
                                "source_management": "lidl_municipal",
                                "roles": roles} for city in selected_cities)
                if len(selected_cities) == len(unique_cities):
                    continue
        if chain is Chain.WILLYS:
            from grocery_data.app.services.source_artifact import willys_collection_location

            if willys_collection_location() == "LOCAL_RELAY":
                skipped.extend(
                    {
                        "chain": "willys",
                        "city": city,
                        "status": "not_applicable",
                        "reason": "Willys OWN awaits validated LOCAL_RELAY imports",
                        "collection_location": "LOCAL_RELAY",
                        "roles": roles,
                    }
                    for city in unique_cities
                )
                continue
        if not descriptor.implemented:
            skipped.append(
                {
                    "chain": chain.value,
                    "city": None,
                    "status": "skipped",
                    "reason": "own connector is not implemented",
                }
            )
            continue
        if not roles:
            skipped.append(
                {
                    "chain": chain.value,
                    "city": None,
                    "status": "skipped",
                    "reason": "no OWN collection role is configured",
                }
            )
            continue
        if chain is Chain.COOP:
            # Physical-store offers and the regional full online catalogue are
            # two independent source roles.  Each requested city gets its own
            # bounded offers refresh, while all pickup cities sharing 730400
            # produce exactly one catalogue refresh.
            if "offers" in roles:
                targets.extend((chain, city, ("offers",)) for city in unique_cities)
            scheduled_contexts: set[str] = set()
            if "basket" in roles:
                for city in unique_cities:
                    context_id = _coop_online_context_for_city(city)
                    if context_id is None:
                        skipped.append(
                            {
                                "chain": chain.value,
                                "city": city,
                                "status": "skipped",
                                "reason": "no verified OWN online basket context for this geography",
                                "roles": ("basket",),
                            }
                        )
                        continue
                    if context_id in scheduled_contexts:
                        continue
                    scheduled_contexts.add(context_id)
                    targets.append((chain, city, ("basket",)))
            continue
        global_scope = _GLOBAL_OWN_COLLECTION_CONTEXTS.get(chain)
        if global_scope is not None:
            # Lidl's accepted own source is one national/public regional offer
            # context. Lund + Malmö must not create duplicate logical daily
            # snapshots of the exact same payload.
            targets.append((chain, global_scope, roles))
            continue
        for city in unique_cities:
            if chain is Chain.CITY_GROSS and municipal["enabled"] and city in selected_cities:
                continue
            if (chain, city.casefold().strip()) in _UNVERIFIED_OWN_COLLECTION_CONTEXTS:
                skipped.append(
                    {
                        "chain": chain.value,
                        "city": city,
                        # City Gross has no verified Lund context by design;
                        # that healthy absence is not an operational failure.
                        # Hemköp remains a real skip until its exact persisted
                        # multi-context registry resolves the approved target.
                        "status": ("not_applicable" if chain is Chain.CITY_GROSS else "skipped"),
                        "reason": "no verified OWN source context for this geography",
                        "roles": roles,
                    }
                )
                continue
            targets.append((chain, city, roles))
    return targets, skipped


def _selected_refresh_chains(args: argparse.Namespace) -> frozenset[Chain]:
    values = tuple(getattr(args, "chain", ()) or ())
    return frozenset(Chain(str(value)) for value in values)


def _operator_flag(name: str) -> bool:
    raw = os.getenv(name, "").strip().casefold()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"", "0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean flag")


def _operator_ids(name: str) -> frozenset[str]:
    return frozenset(value.strip() for value in os.getenv(name, "").split(",") if value.strip())


def _review_target_skip(
    chain: Chain,
    roles: tuple[str, ...],
    *,
    context_store_id: str | None = None,
) -> dict[str, object] | None:
    """Explain a disabled REVIEW crawl before any client is constructed."""

    if "basket" not in roles:
        return None
    if chain is Chain.COOP:
        configuration = assess_coop_refresh_configuration(os.environ)
        if configuration.valid:
            return None
        reasons = {
            "coop_full_catalog_disabled": (
                "operator opt-in disabled (COOP_ALLOW_FULL_CRAWL=false)"
            ),
            "coop_full_catalog_opt_in_invalid": ("operator opt-in is not a valid boolean"),
            "coop_online_context_not_allowlisted": (
                "verified context 730400 is outside the exact allowlist"
            ),
            "coop_online_context_allowlist_too_broad": (
                "Coop exact allowlist contains an unverified context"
            ),
        }
        return {
            "status": "skipped",
            "reason": reasons.get(
                configuration.diagnostic_code,
                "Coop full online catalogue configuration is invalid",
            ),
            "diagnostic_code": configuration.diagnostic_code,
            "source_policy": configuration.configured_policy,
            "operator_opt_in": configuration.operator_opt_in,
            "configured_allowlist_size": len(configuration.configured_context_ids),
            "configured_context_ids": list(configuration.configured_context_ids),
            "context_id": context_store_id or configuration.context_id,
            "network_requests": 0,
        }
    policy: tuple[str, str] | None = {
        Chain.CITY_GROSS: (
            "CITYGROSS_ALLOW_FULL_CRAWL",
            "CITYGROSS_STORE_EXTERNAL_IDS",
        ),
        Chain.HEMKOP: (
            "HEMKOP_ALLOW_FULL_CRAWL",
            "HEMKOP_STORE_EXTERNAL_IDS",
        ),
    }.get(chain)
    if policy is None:
        return None
    flag_name, allowlist_name = policy
    enabled = _operator_flag(flag_name)
    allowlist = _operator_ids(allowlist_name)
    reason: str | None = None
    if not enabled:
        reason = f"operator opt-in disabled ({flag_name}=false)"
    elif not allowlist:
        reason = f"exact allowlist is empty ({allowlist_name})"
    elif context_store_id is not None and context_store_id not in allowlist:
        reason = f"context is outside exact allowlist ({allowlist_name})"
    if reason is None:
        return None
    return {
        "status": "skipped",
        "reason": reason,
        "source_policy": "review",
        "operator_opt_in": enabled,
        "configured_allowlist_size": len(allowlist),
        "network_requests": 0,
    }


def _last_known_good(
    factory: SessionFactory,
    chain: Chain,
    scope_key: str,
) -> dict[str, object]:
    with session_scope(factory) as session:
        row = SnapshotRepository(session).last_known_good(
            chain,
            scope_key=scope_key.casefold().strip(),
        )
        if row is None:
            return {
                "active_snapshot_id": None,
                "active_snapshot_observed_at": None,
                "active_snapshot_age_hours": None,
                "active_snapshot_coverage": None,
            }
        observed_at = (
            session.scalar(
                select(func.min(PriceObservationModel.observed_at)).where(
                    PriceObservationModel.catalog_snapshot_id == row.id
                )
            )
            or row.created_at
        )
        age = max(0.0, (datetime.now(tz=UTC) - observed_at).total_seconds() / 3600)
        return {
            "active_snapshot_id": row.id,
            "active_snapshot_observed_at": observed_at,
            "active_snapshot_age_hours": round(age, 3),
            "active_snapshot_coverage": row.coverage,
        }


def _hemkop_context_plan(
    factory: SessionFactory,
    city: str,
    *,
    policy: HemkopOperatorCrawlPolicy,
) -> HemkopContextCollectionPlan:
    """Read persisted official evidence only; planning performs no source requests."""

    with session_scope(factory) as session:
        return HemkopMultiContextCollectionPlanner(session).plan(city, policy=policy)


def _hemkop_collect_all_contexts(
    factory: SessionFactory,
    cities: list[str],
) -> tuple[
    list[tuple[HemkopContextCollectionTarget, HemkopOperatorCrawlPolicy]],
    list[dict[str, object]],
    int,
]:
    """Resolve REVIEW-authorized Lund contexts without fabricating store work."""

    contexts: list[tuple[HemkopContextCollectionTarget, HemkopOperatorCrawlPolicy]] = []
    diagnostics: list[dict[str, object]] = []
    unmatched: dict[str, tuple[str, str, bool]] = {}
    matched_store_ids: set[str] = set()
    failures = 0
    unique_cities = tuple(
        {city.casefold().strip(): city.strip() for city in cities if city.strip()}.values()
    )
    for city in unique_cities:
        from grocery_data.app.services.municipal_rollout import hemkop_policy, scope_for_city
        if (Chain.HEMKOP, city.casefold().strip()) not in _MULTI_CONTEXT_OWN_COLLECTION_CITIES and scope_for_city(city) is None:
            continue
        try:
            policy = HemkopOperatorCrawlPolicy.from_environment()
            policy = hemkop_policy(city, policy)
            plan = _hemkop_context_plan(factory, city, policy=policy)
        except Exception as exc:  # noqa: BLE001 - closed policy/planning boundary
            failures += 1
            diagnostics.append(
                {
                    "chain": Chain.HEMKOP.value,
                    "city": city,
                    "status": "failed",
                    "reason": "multi-context planning failed closed",
                    "error_type": type(exc).__name__,
                    "source_policy": "review",
                    "network_requests": 0,
                }
            )
            continue
        contexts.extend((target, policy) for target in plan.targets)
        matched_store_ids.update(target.store_external_id for target in plan.targets)
        diagnostics.extend(
            {
                "chain": Chain.HEMKOP.value,
                "city": city,
                "context_store_id": item.store_external_id,
                "physical_store_id": item.physical_store_id,
                "grocery_context_id": item.grocery_context_id,
                "status": "skipped",
                "reason": item.reason,
                "source_policy": plan.source_policy,
                "operator_opt_in": plan.operator_opt_in,
                "network_requests": 0,
            }
            for item in plan.skipped
        )
        unmatched.update(
            {
                store_id: (city, plan.source_policy, plan.operator_opt_in)
                for store_id in plan.unmatched_allowlist_ids
            }
        )
    requested_city_keys = {city.casefold().strip() for city in unique_cities}
    unresolved_allowlist = {
        store_id: value
        for store_id, value in unmatched.items()
        if store_id not in matched_store_ids
        and (
            _HEMKOP_VERIFIED_CONTEXT_CITIES.get(store_id) is None
            or _HEMKOP_VERIFIED_CONTEXT_CITIES[store_id] in requested_city_keys
        )
    }
    diagnostics.extend(
        {
            "chain": Chain.HEMKOP.value,
            "city": city,
            "context_store_id": store_id,
            "status": "skipped",
            "reason": "allowlisted ID has no active exact official online context",
            "source_policy": source_policy,
            "operator_opt_in": operator_opt_in,
            "network_requests": 0,
        }
        for store_id, (city, source_policy, operator_opt_in) in sorted(unresolved_allowlist.items())
    )
    failures += len(unresolved_allowlist)
    return contexts, diagnostics, failures


async def _run_collect_all(args: argparse.Namespace) -> tuple[dict[str, object], int]:
    """Run each explicit OWN connector independently and preserve every LKG.

    REVIEW sources still enforce their connector-local operator opt-in and
    allowlist. One rejected/blocked chain-city target never prevents another
    chain from collecting. No external provider is contacted or substituted.
    """

    settings, engine, factory = _runtime()
    raw_store = FilesystemRawSnapshotStore(settings.raw_snapshot_root)
    selected_chains = _selected_refresh_chains(args)
    if selected_chains:
        targets, skipped = _collect_all_plan(
            args.city,
            selected_chains=selected_chains,
        )
    else:
        targets, skipped = _collect_all_plan(args.city)
    municipal_preparation_diagnostics = []
    if selected_chains and Chain.HEMKOP not in selected_chains:
        hemkop_contexts, context_diagnostics, planning_failures = [], [], 0
    else:
        from grocery_data.app.services.hemkop_municipal_job import (
            run_source_job as prepare_hemkop_municipality,
        )
        for city in args.city:
            try:
                await prepare_hemkop_municipality(city=city)
            except Exception as exc:  # noqa: BLE001 - optional offers cannot erase a verified mandatory base
                municipal_preparation_diagnostics.append({'chain': 'hemkop', 'city': city,
                    'status': 'failed_optional_municipal_source', 'error_type': type(exc).__name__})
        hemkop_contexts, context_diagnostics, planning_failures = _hemkop_collect_all_contexts(
            factory, args.city
        )
    requested_context = str(getattr(args, "context_store_id", "") or "").strip()
    if requested_context:
        if (
            selected_chains
            not in {
                frozenset({Chain.HEMKOP}),
                frozenset({Chain.COOP}),
            }
            or len(set(args.city)) != 1
        ):
            raise ValueError(
                "--context-store-id requires exactly --chain hemkop/coop and one --city"
            )
        if selected_chains == frozenset({Chain.COOP}):
            verified_context = _coop_online_context_for_city(args.city[0])
            if (
                requested_context != COOP_VERIFIED_ONLINE_CONTEXT_ID
                or verified_context != requested_context
            ):
                raise ValueError(
                    "requested Coop context is not the verified online context for this city"
                )
            # A source-recovery run refreshes only the full online catalogue;
            # physical offers remain an independent source/scope.
            targets = [
                target for target in targets if target[0] is Chain.COOP and target[2] == ("basket",)
            ]
            skipped = [item for item in skipped if item.get("chain") != Chain.COOP.value]
            hemkop_contexts = []
            context_diagnostics = []
            planning_failures = 0
        else:
            hemkop_contexts = [
                row for row in hemkop_contexts if row[0].store_external_id == requested_context
            ]
            context_diagnostics = [
                row
                for row in context_diagnostics
                if row.get("context_store_id") in {None, requested_context}
            ]
            # A policy/allowlist diagnostic for this exact store proves that the
            # requested context was resolved from the official registry.  It is
            # merely not runnable under the current REVIEW authorization.
            requested_context_resolved = bool(hemkop_contexts) or any(
                row.get("context_store_id") == requested_context for row in context_diagnostics
            )
            if not requested_context_resolved:
                context_diagnostics.append(
                    {
                        "chain": Chain.HEMKOP.value,
                        "city": args.city[0],
                        "context_store_id": requested_context,
                        "status": "skipped",
                        "reason": "requested context is not an approved exact refresh target",
                        "network_requests": 0,
                    }
                )
            planning_failures = sum(
                row.get("status") == "failed"
                or (
                    row.get("status") == "skipped"
                    and row.get("context_store_id") == requested_context
                )
                for row in context_diagnostics
            )
    # A persisted exact context supersedes the legacy "unverified geography"
    # placeholder. If none exists, the original skip remains truthful.
    hemkop_context_cities = {
        target.city.casefold().strip() for target, _policy in hemkop_contexts
    } | {
        str(item.get("city") or "").casefold().strip()
        for item in context_diagnostics
        if item.get("chain") == Chain.HEMKOP.value and item.get("context_store_id") is not None
    }
    skipped = [
        item
        for item in skipped
        if not (
            item.get("chain") == Chain.HEMKOP.value
            and str(item.get("city") or "").casefold().strip() in hemkop_context_cities
        )
    ]
    results: list[dict[str, object]] = [*skipped, *context_diagnostics, *municipal_preparation_diagnostics]
    failures = planning_failures
    try:
        for chain, city, roles in targets:
            connector = None
            collection_scope: str | None = None
            lkg_scope = city
            context_fields: dict[str, object] = {}
            try:
                if chain is Chain.COOP and "basket" in roles:
                    if roles != ("basket",):
                        raise ValueError("Coop daily catalogue and physical offers must be split")
                    context_id = _coop_online_context_for_city(city)
                    if context_id is None:
                        raise ValueError("Coop daily target lacks a verified online context")
                    collection_scope = _exact_collection_scope(chain, city, context_id)
                    lkg_scope = collection_scope
                    served_cities = _coop_context_served_cities(context_id, args.city)
                    context_fields = {
                        "context_store_id": context_id,
                        "grocery_context_id": f"own:coop:{context_id}",
                        "context_name": "Coop Online Syd",
                        "scope_key": collection_scope,
                        "served_cities": served_cities,
                        "price_context_type": "online_fulfillment",
                        "price_semantics": "online_price",
                    }
                    policy_skip = _review_target_skip(
                        chain,
                        roles,
                        context_store_id=context_id,
                    )
                    if policy_skip is not None:
                        results.append(
                            {
                                "chain": chain.value,
                                "city": city,
                                "roles": roles,
                                "source_provider": SourceProvider.OWN.value,
                                "fallback_used": False,
                                **context_fields,
                                **policy_skip,
                                **_last_known_good(factory, chain, lkg_scope),
                            }
                        )
                        continue
                    connector = _exact_collection_connector(chain, context_id)
                    audit = collection_policy_audit(connector)
                    if audit is None or tuple(audit.store_allowlist) != (context_id,):
                        raise ValueError("Coop daily online connector is not exactly scoped")
                else:
                    policy_skip = _review_target_skip(chain, roles)
                    if policy_skip is not None:
                        results.append(
                            {
                                "chain": chain.value,
                                "city": city,
                                "roles": roles,
                                "source_provider": SourceProvider.OWN.value,
                                "fallback_used": False,
                                **policy_skip,
                                **_last_known_good(factory, chain, lkg_scope),
                            }
                        )
                        continue
                    connector = _collection_connector(chain)
                collector = GroceryCollector(factory, raw_store)
                if collection_scope is None:
                    result = await collector.collect_area(
                        connector,
                        GeographicArea(city=city),
                        auto_promote=not args.no_promote,
                    )
                else:
                    result = await collector.collect_area(
                        connector,
                        GeographicArea(city=city),
                        auto_promote=not args.no_promote,
                        scope_key=collection_scope,
                    )
                accepted_staged = args.no_promote and result.status.value == "healthy"
                item: dict[str, object] = {
                    "chain": chain.value,
                    "city": city,
                    "roles": roles,
                    "source_provider": SourceProvider.OWN.value,
                    "fallback_used": False,
                    "snapshot_id": result.snapshot_id,
                    "scope_key": result.scope_key,
                    "status": result.status.value,
                    "promoted": result.promoted,
                    "candidate_staged": accepted_staged,
                    "stores": len(result.stores),
                    "products": result.metrics.products_parsed,
                    "requests": result.metrics.request_count,
                    "metrics": result.metrics.model_dump(mode="json"),
                    "warnings": result.warnings,
                    **context_fields,
                    **_policy_audit_fields(result.source_policy_audit),
                    **_last_known_good(factory, chain, lkg_scope),
                }
                results.append(item)
                if not result.promoted and not accepted_staged:
                    failures += 1
            except Exception as exc:  # noqa: BLE001 - isolated, sanitized daily boundary
                failures += 1
                results.append(
                    {
                        "chain": chain.value,
                        "city": city,
                        "roles": roles,
                        "source_provider": SourceProvider.OWN.value,
                        "fallback_used": False,
                        "status": "failed",
                        "error_type": type(exc).__name__,
                        **context_fields,
                        **_last_known_good(factory, chain, lkg_scope),
                    }
                )
            finally:
                await _close_connector(connector)

        for target, policy in hemkop_contexts:
            connector = None
            try:
                connector = HemkopConnector.for_exact_full_collection(
                    target.store_external_id,
                    policy=policy,
                )
                audit = collection_policy_audit(connector)
                if audit is None or tuple(audit.store_allowlist) != (target.store_external_id,):
                    raise ValueError("Hemköp daily context connector is not exactly scoped")
                result = await GroceryCollector(factory, raw_store).collect_area(
                    connector,
                    GeographicArea(city=target.city),
                    auto_promote=not args.no_promote,
                    scope_key=target.scope_key,
                )
                accepted_staged = args.no_promote and result.status.value == "healthy"
                results.append(
                    {
                        "chain": Chain.HEMKOP.value,
                        "city": target.city,
                        "context_store_id": target.store_external_id,
                        "physical_store_id": target.physical_store_id,
                        "grocery_context_id": target.grocery_context_id,
                        "scope_key": target.scope_key,
                        "roles": target.roles,
                        "source_provider": SourceProvider.OWN.value,
                        "fallback_used": False,
                        "snapshot_id": result.snapshot_id,
                        "status": result.status.value,
                        "promoted": result.promoted,
                        "candidate_staged": accepted_staged,
                        "stores": len(result.stores),
                        "products": result.metrics.products_parsed,
                        "requests": result.metrics.request_count,
                        "metrics": result.metrics.model_dump(mode="json"),
                        "warnings": result.warnings,
                        **_policy_audit_fields(result.source_policy_audit),
                        **_last_known_good(
                            factory,
                            Chain.HEMKOP,
                            target.scope_key,
                        ),
                    }
                )
                if not result.promoted and not accepted_staged:
                    failures += 1
            except Exception as exc:  # noqa: BLE001 - one context never blocks its peers
                failures += 1
                results.append(
                    {
                        "chain": Chain.HEMKOP.value,
                        "city": target.city,
                        "context_store_id": target.store_external_id,
                        "physical_store_id": target.physical_store_id,
                        "grocery_context_id": target.grocery_context_id,
                        "scope_key": target.scope_key,
                        "roles": target.roles,
                        "source_provider": SourceProvider.OWN.value,
                        "fallback_used": False,
                        "status": "failed",
                        "error_type": type(exc).__name__,
                        **_last_known_good(
                            factory,
                            Chain.HEMKOP,
                            target.scope_key,
                        ),
                    }
                )
            finally:
                await _close_connector(connector)
    finally:
        engine.dispose()

    report: dict[str, object] = {
        "run_type": "daily_own_collection",
        "cities": list(
            {city.casefold().strip(): city.strip() for city in args.city if city.strip()}.values()
        ),
        "results": results,
        "summary": {
            "targets": len(targets) + len(hemkop_contexts),
            "completed": sum(item.get("status") == "healthy" for item in results),
            "failed": failures,
            "skipped": sum(item.get("status") == "skipped" for item in results),
            "external_provider_requests": 0,
            "fallbacks_used": 0,
        },
    }
    return report, 0 if failures == 0 else 2


async def _collect_all(args: argparse.Namespace) -> int:
    report, exit_code = await _run_collect_all(args)
    _json(report)
    return exit_code


_DEFAULT_CITY_POSTAL_CODES = {
    "lund": "22350",
    "malmö": "21120",
    "malmo": "21120",
}


def _refresh_city_postal_codes(args: argparse.Namespace) -> dict[str, str]:
    cities = tuple(
        {city.casefold().strip(): city.strip() for city in args.city if city.strip()}.values()
    )
    if not cities:
        raise ValueError("at least one city is required")
    configured: dict[str, str] = {}
    bare: list[str] = []
    for raw in tuple(getattr(args, "postal_code", ()) or ()):
        value = str(raw).strip()
        if "=" in value:
            city, code = value.split("=", 1)
            key = city.casefold().strip()
            digits = "".join(character for character in code if character.isdigit())
            if key not in {item.casefold().strip() for item in cities}:
                raise ValueError("--postal-code names a city outside this refresh")
            if len(digits) != 5:
                raise ValueError("postal codes must contain exactly five digits")
            configured[key] = digits
        else:
            digits = "".join(character for character in value if character.isdigit())
            if len(digits) != 5:
                raise ValueError("postal codes must contain exactly five digits")
            bare.append(digits)
    if bare:
        if len(bare) != len(cities):
            raise ValueError(
                "bare --postal-code values must be repeated once per --city in the same order"
            )
        configured.update(
            (city.casefold().strip(), code) for city, code in zip(cities, bare, strict=True)
        )
    result: dict[str, str] = {}
    for city in cities:
        key = city.casefold().strip()
        default = _DEFAULT_CITY_POSTAL_CODES.get(key)
        code = configured.get(key, default)
        if code is None:
            raise ValueError(f"no default postal scope for {city}; pass --postal-code {city}=NNNNN")
        result[city] = code
    return result


def _external_cache_inputs(
    args: argparse.Namespace,
    cities: tuple[str, ...],
) -> dict[str, Path]:
    raw_value = getattr(args, "external_cache", None)
    if raw_value is None:
        return {}
    values = tuple(raw_value) if isinstance(raw_value, (list, tuple)) else (raw_value,)
    mapped: dict[str, Path] = {}
    bare: list[Path] = []
    city_keys = {city.casefold().strip(): city for city in cities}
    for raw in values:
        text = str(raw).strip()
        if "=" in text:
            city, path = text.split("=", 1)
            key = city.casefold().strip()
            if key not in city_keys:
                raise ValueError("--external-cache names a city outside this refresh")
            mapped[city_keys[key]] = Path(path)
        else:
            bare.append(Path(text))
    if bare:
        if len(bare) != len(cities):
            raise ValueError(
                "bare --external-cache paths require one path per --city in the same order"
            )
        mapped.update(zip(cities, bare, strict=True))
    return mapped


def _sqlite_database_path(settings: GroceryDataSettings) -> Path:
    from sqlalchemy.engine import make_url

    url = make_url(settings.database_url)
    if url.get_backend_name() != "sqlite" or not url.database:
        raise RuntimeError(
            "self-contained PriceUniverse refresh currently requires the configured SQLite DB"
        )
    return Path(url.database).resolve(strict=True)


def _daily_refresh_dry_run(args: argparse.Namespace) -> dict[str, object]:
    """Describe bounded production work without creating clients or writing state."""

    settings, engine, factory = _runtime()
    database = _sqlite_database_path(settings)
    selected = _selected_refresh_chains(args)
    coop_lkg_by_context: dict[str, dict[str, object]] = {}
    try:
        if selected:
            targets, skipped = _collect_all_plan(
                args.city,
                selected_chains=selected,
            )
        else:
            targets, skipped = _collect_all_plan(args.city)
        if selected and Chain.HEMKOP not in selected:
            hemkop_contexts, hemkop_diagnostics, planning_failures = [], [], 0
        else:
            hemkop_contexts, hemkop_diagnostics, planning_failures = _hemkop_collect_all_contexts(
                factory, args.city
            )
        for chain, city, roles in targets:
            if chain is not Chain.COOP or roles != ("basket",):
                continue
            context_id = _coop_online_context_for_city(city)
            if context_id is None:
                continue
            coop_lkg_by_context[context_id] = _last_known_good(
                factory,
                chain,
                _exact_collection_scope(chain, city, context_id),
            )
    finally:
        engine.dispose()

    requested_context = str(getattr(args, "context_store_id", "") or "").strip()
    if requested_context:
        if (
            selected not in {frozenset({Chain.HEMKOP}), frozenset({Chain.COOP})}
            or len(set(args.city)) != 1
        ):
            raise ValueError(
                "--context-store-id requires exactly --chain hemkop/coop and one --city"
            )
        if selected == frozenset({Chain.COOP}):
            if (
                requested_context != COOP_VERIFIED_ONLINE_CONTEXT_ID
                or _coop_online_context_for_city(args.city[0]) != requested_context
            ):
                raise ValueError(
                    "requested Coop context is not the verified online context for this city"
                )
            targets = [
                target for target in targets if target[0] is Chain.COOP and target[2] == ("basket",)
            ]
            skipped = [item for item in skipped if item.get("chain") != Chain.COOP.value]
            hemkop_contexts = []
            hemkop_diagnostics = []
            planning_failures = 0
        else:
            hemkop_contexts = [
                row for row in hemkop_contexts if row[0].store_external_id == requested_context
            ]
            hemkop_diagnostics = [
                row
                for row in hemkop_diagnostics
                if row.get("context_store_id") in {None, requested_context}
            ]
            planning_failures = sum(
                row.get("status") == "failed"
                or (
                    row.get("status") == "skipped"
                    and row.get("context_store_id") == requested_context
                )
                for row in hemkop_diagnostics
            )

    hemkop_context_cities = {
        target.city.casefold().strip() for target, _policy in hemkop_contexts
    } | {
        str(item.get("city") or "").casefold().strip()
        for item in hemkop_diagnostics
        if item.get("chain") == Chain.HEMKOP.value and item.get("context_store_id") is not None
    }
    skipped = [
        item
        for item in skipped
        if not (
            item.get("chain") == Chain.HEMKOP.value
            and str(item.get("city") or "").casefold().strip() in hemkop_context_cities
        )
    ]

    planned: list[dict[str, object]] = []
    for chain, city, roles in targets:
        context_id = (
            _coop_online_context_for_city(city)
            if chain is Chain.COOP and "basket" in roles
            else None
        )
        policy_skip = _review_target_skip(
            chain,
            roles,
            context_store_id=context_id,
        )
        planned.append(
            {
                "chain": chain.value,
                "city": city,
                "roles": roles,
                "context_store_id": context_id,
                "source_provider": SourceProvider.OWN.value,
                "status": "skipped" if policy_skip else "planned",
                "reason": policy_skip.get("reason") if policy_skip else None,
                "network_requests": 0,
                **(coop_lkg_by_context.get(context_id, {}) if context_id else {}),
            }
        )
    planned.extend(
        {
            "chain": Chain.HEMKOP.value,
            "city": target.city,
            "roles": target.roles,
            "context_store_id": target.store_external_id,
            "source_provider": SourceProvider.OWN.value,
            "status": "planned",
            "reason": None,
            "network_requests": 0,
        }
        for target, _policy in hemkop_contexts
    )
    dry_run_now = datetime.now(tz=UTC)
    dry_run_policy = FreshnessPolicy(
        warning_age_hours=settings.price_age_warning_hours,
        stale_age_hours=settings.max_price_age_hours,
    )
    dry_run_next = next_scheduled_refresh(
        os.getenv("DAILY_REFRESH_SCHEDULE"),
        now=dry_run_now,
    )
    for row in [*planned, *skipped, *hemkop_diagnostics]:
        _annotate_source_freshness(
            row,
            now=dry_run_now,
            policy=dry_run_policy,
            next_expected_refresh=dry_run_next,
        )
    postal_codes = _refresh_city_postal_codes(args)
    refresh_external = not bool(getattr(args, "no_external_refresh", False))
    selected_external = any(
        source_strategy_for(chain).primary_source.provider is SourceProvider.PRIMAT
        for chain in Chain
    )
    explicit_caches = _external_cache_inputs(args, tuple(postal_codes))
    external_city_plans: list[dict[str, object]] = []
    for city in postal_codes:
        if city in explicit_caches:
            external_city_plans.append(
                {
                    "city": city,
                    "status": "provided_cache",
                    "provider_requests_planned": 0,
                    "contexts": [],
                }
            )
        elif refresh_external and selected_external:
            try:
                external_city_plans.append(
                    _plan_production_primat_refresh(
                        database=database,
                        city=city,
                        max_age_hours=settings.max_price_age_hours,
                    )
                )
            except Exception as exc:  # noqa: BLE001 - sanitized planning boundary
                external_city_plans.append(
                    {
                        "city": city,
                        "status": "planning_failed",
                        "provider_requests_planned": 0,
                        "contexts": [],
                        "error_type": type(exc).__name__,
                    }
                )
        else:
            external_city_plans.append(
                {
                    "city": city,
                    "status": "not_selected",
                    "provider_requests_planned": 0,
                    "contexts": [],
                }
            )
    external_planning_failures = sum(
        row.get("status") in {"no_verified_primat_primary_contexts", "planning_failed"}
        for row in external_city_plans
    )
    return {
        "run_type": "daily_refresh_dry_run",
        "dry_run": True,
        "cities": list(postal_codes),
        "own_targets": [*planned, *skipped, *hemkop_diagnostics],
        "external_provider": {
            "provider": SourceProvider.PRIMAT.value,
            "status": (
                "planned_from_verified_contexts"
                if refresh_external and selected_external
                else "not_selected"
            ),
            "maximum_requests_per_city": 49,
            "cities": list(postal_codes),
            "city_plans": external_city_plans,
        },
        "price_universe": [
            {
                "city": city,
                "postal_code": postal,
                "action": "build_validate_atomic_activate_once",
            }
            for city, postal in postal_codes.items()
        ],
        "planning_failures": planning_failures + external_planning_failures,
        "network_requests": 0,
        "database_writes": 0,
        "snapshot_promotions": 0,
    }


def _ensure_backend_import_path() -> None:
    """Make the repository backend package importable for artifact validation only."""

    backend_root = Path(__file__).resolve().parents[1] / "backend"
    if not backend_root.is_dir():
        raise RuntimeError("backend package is unavailable for prepared artifact validation")
    value = str(backend_root)
    if value not in sys.path:
        sys.path.insert(0, value)


def _collection_row_applies_to_city(row: dict[str, object], city: str) -> bool:
    """Match a refresh row to a city without duplicating regional contexts."""

    normalized_city = city.casefold().strip()
    served = row.get("served_cities")
    if isinstance(served, (list, tuple, set, frozenset)):
        return normalized_city in {
            str(value).casefold().strip() for value in served if str(value).strip()
        }
    return str(row.get("city") or "").casefold().strip() == normalized_city


async def _daily_refresh_legacy(
    args: argparse.Namespace,
    *,
    universe_hook: UniverseRefreshHook | None = None,
) -> int:
    """Run isolated OWN work and publish a production-oriented freshness report.

    Licensed provider cache collection remains its separately budgeted explicit
    command. ``--external-cache`` registers an already closed local snapshot;
    this orchestration never re-queries Primat implicitly.
    """

    collection, exit_code = await _run_collect_all(args)
    settings = GroceryDataSettings.from_env()
    policy = FreshnessPolicy(
        warning_age_hours=settings.price_age_warning_hours,
        stale_age_hours=settings.max_price_age_hours,
    )
    external_cache = getattr(args, "external_cache", None)
    external_snapshot_ids: tuple[str, ...] = ()
    external_status: dict[str, object]
    if external_cache is None:
        external_status = {
            "status": "not_requested",
            "provider_requests": 0,
            "reason": "no closed external cache path supplied",
        }
    else:
        cache = inspect_closed_provider_cache(Path(external_cache), policy=policy)
        external_status = {
            "status": "closed_cache_available" if cache.usable else "closed_cache_stale",
            **cache.model_dump(mode="json"),
        }
        if cache.usable:
            activation_engine = create_database_engine(settings.database_url)
            try:
                activation_factory = create_session_factory(activation_engine)
                with session_scope(activation_factory) as activation_session:
                    activation = activate_closed_primat_context_links(
                        activation_session,
                        Path(external_cache),
                    )
            except Exception as exc:  # noqa: BLE001 - one closed provider is isolated
                external_status = {
                    **external_status,
                    "status": "closed_cache_context_activation_failed",
                    "context_activation": {
                        "status": "rejected",
                        "error_type": type(exc).__name__,
                        "provider_requests": 0,
                        "mappings_created": 0,
                    },
                }
            else:
                external_snapshot_ids = activation.snapshot_ids
                activation_status = {
                    "activated": "closed_cache_available",
                    "partially_activated": "closed_cache_partially_activated",
                    "rejected": "closed_cache_context_activation_rejected",
                }[activation.status]
                external_status = {
                    **external_status,
                    "status": activation_status,
                    "context_activation": activation.model_dump(mode="json"),
                }
            finally:
                activation_engine.dispose()

    candidate = getattr(args, "price_universe_candidate", None)
    if candidate is not None and universe_hook is not None:
        raise ValueError(
            "use either an injected PriceUniverse hook or a prepared candidate artifact"
        )
    rows = collection.get("results")
    if not isinstance(rows, list):
        raise TypeError("collect-all result lacks rows")
    cities = [str(city) for city in collection["cities"]]  # type: ignore[index]
    if candidate is not None and len(cities) != 1:
        raise ValueError("one prepared universe candidate can activate exactly one city")

    lineage_by_city: dict[str, tuple[str, ...]] = {}
    promoted_by_city: dict[str, bool] = {}
    for city in cities:
        normalized_city = city.casefold().strip()
        basket_snapshots = {
            str(row["snapshot_id"])
            for row in rows
            if _collection_row_applies_to_city(row, normalized_city)
            and bool(row.get("promoted"))
            and row.get("snapshot_id")
            and "basket" in {str(role).casefold() for role in row.get("roles") or ()}
        }
        lineage_by_city[normalized_city] = tuple(
            sorted(basket_snapshots.union(external_snapshot_ids))
        )
        promoted_by_city[normalized_city] = bool(basket_snapshots)

    if candidate is not None:
        _ensure_backend_import_path()
        cache_root = getattr(args, "price_universe_cache_root", None)
        artifact_store = PreparedUniverseArtifactStore(
            Path(cache_root) if cache_root is not None else settings.price_universe_cache_root
        )
        universe_hook = PreparedUniverseArtifactRefreshHook(
            artifact_store,
            candidate_loader=lambda _city: Path(candidate),
            validator=validate_backend_prepared_universe_artifact,
            expected_snapshot_ids_loader=lambda city: lineage_by_city.get(
                city.casefold().strip(),
                (),
            ),
        )

    reports = []
    universe_failed = False
    for city in cities:
        universe = await run_universe_refresh(
            city,
            promoted=promoted_by_city[city.casefold().strip()],
            hook=universe_hook,
        )
        universe_failed = universe_failed or universe.status == "rebuild_failed"
        report = report_from_collection_results(
            str(city),
            rows,
            policy=policy,
            universe=universe,
        )
        reports.append(report.model_dump(mode="json"))
    _json(
        {
            "run_type": "daily_refresh",
            "reports": reports,
            "own_collection": collection,
            "external_provider": external_status,
            "meal_generation_live_requests": 0,
            "schedule": "once_per_day",
        }
    )
    return 2 if universe_failed else exit_code


def _safe_scope_slug(value: str) -> str:
    slug = "".join(
        character if character.isalnum() else "-" for character in value.casefold().strip()
    ).strip("-")
    if not slug:
        raise ValueError("refresh scope cannot be represented as a filename")
    return slug


async def _collect_production_primat_cache(
    *,
    database: Path,
    city: str,
    postal_code: str,
    output: Path,
    max_age_hours: float,
    lkg_cache: Path | None = None,
) -> dict[str, object]:
    """Lazy backend seam; tests can replace it without constructing a provider."""

    _ensure_backend_import_path()
    from app.services.production_primat_refresh import collect_city_primat_cache

    return await collect_city_primat_cache(
        database,
        city,
        postal_code,
        output,
        max_age_hours,
        lkg_cache,
    )


def _plan_production_primat_refresh(
    *,
    database: Path,
    city: str,
    max_age_hours: float,
) -> dict[str, object]:
    """Lazy zero-network planning seam over persisted verified identities."""

    _ensure_backend_import_path()
    from app.services.production_primat_refresh import plan_city_primat_refresh

    return plan_city_primat_refresh(database, city, max_age_hours)


async def _build_production_price_universe(
    *,
    database: Path,
    city: str,
    postal_code: str,
    external_cache: Path | None,
    output: Path,
    max_price_age_hours: float,
) -> dict[str, object]:
    """Build from a consistent closed SQLite input under the refresh lock.

    Consumer telemetry can still write to the live DB while source operations
    are locked. Reuse the backup primitive (including committed WAL data), so
    the immutable builder keeps all its mutation and freshness checks intact.
    """

    _ensure_backend_import_path()
    from app.services.production_price_universe_build import build_city_price_universe

    from deploy.scripts.backup_sqlite import _backup_database

    offer_options = {}
    if os.getenv("ICA_STRUCTURED_OFFERS_ENABLED", "false").casefold() == "true":
        from grocery_data.app.services.ica_offer_job import structured_source_inputs
        offer_options = structured_source_inputs(city=city, root=Path(os.getenv(
            "ICA_STRUCTURED_OFFERS_ROOT", str(database.parent / "ica-structured-offers"))))
    from grocery_data.app.services.coop_offer_job import record_build, source_inputs
    offer_options.update(source_inputs(city=city))
    from grocery_data.app.services import citygross_municipal_job
    offer_options.update(citygross_municipal_job.source_inputs(city=city))
    from grocery_data.app.services import lidl_municipal_job
    offer_options.update(lidl_municipal_job.source_inputs(city=city))
    from grocery_data.app.services import willys_flyer_job
    offer_options.update(willys_flyer_job.source_inputs(city=city))
    from grocery_data.app.services import hemkop_municipal_job
    offer_options.update(hemkop_municipal_job.source_inputs(city=city))
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".price-universe-source-", dir=output.parent) as temporary:
        closed_database = Path(temporary) / "source.sqlite3"
        _backup_database(database, closed_database)
        result = await build_city_price_universe(
            closed_database,
            city,
            postal_code,
            external_cache,
            output,
            max_price_age_hours,
            **offer_options,
        )
        try:
            record_build(city=city, result=result)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            result["coop_build_receipt_error"] = type(exc).__name__
        try:
            citygross_municipal_job.record_build(city=city, result=result)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            result["citygross_build_receipt_error"] = type(exc).__name__
        try:
            lidl_municipal_job.record_build(city=city, result=result)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            result["lidl_build_receipt_error"] = type(exc).__name__
        try:
            willys_flyer_job.record_build(city=city, result=result)
        except (OSError, ValueError, KeyError) as exc:
            result["willys_flyer_build_receipt_error"] = type(exc).__name__
        return result


def _activate_external_context_links(
    settings: GroceryDataSettings,
    cache: Path,
) -> dict[str, object]:
    engine = create_database_engine(settings.database_url)
    try:
        factory = create_session_factory(engine)
        with session_scope(factory) as session:
            result = activate_closed_primat_context_links(
                session,
                cache,
                require_complete=True,
            )
            # Managed refresh publishes one closed cache as an indivisible
            # city scope.  Reject while the transaction is still open so a
            # partially activated report cannot commit link rows before the
            # orchestrator restores the previous cache manifest/LKG links.
            if result.status != "activated" or result.rejected != 0:
                raise RuntimeError("external context activation was rejected")
        return dict(result.model_dump(mode="json"))
    finally:
        engine.dispose()


def _validate_external_context_links(
    settings: GroceryDataSettings,
    cache: Path,
) -> dict[str, object]:
    """Preflight all persisted identities without changing link snapshots."""

    engine = create_database_engine(settings.database_url)
    try:
        factory = create_session_factory(engine)
        with session_scope(factory) as session:
            result = validate_closed_primat_context_links(session, cache)
        return dict(result.model_dump(mode="json"))
    finally:
        engine.dispose()


def _external_context_validation_decision(
    settings: GroceryDataSettings,
    cache: Path,
) -> ClosedProviderCacheValidationDecision[dict[str, object]]:
    report = _validate_external_context_links(settings, cache)
    accepted = bool(
        report.get("status") == "activated"
        and int(report.get("rejected") or 0) == 0
        and int(report.get("activated") or 0) == int(report.get("cache_stores") or -1)
    )
    return ClosedProviderCacheValidationDecision(
        accepted=accepted,
        value=report,
        reason_code=None if accepted else "db_identity_rejected",
    )


def _smoke_load_prepared_universe(path: Path, expected_id: str) -> dict[str, object]:
    """Load and price the representative basket without constructing a provider."""

    _ensure_backend_import_path()
    from app.services.basket_optimizer import BasketOptimizer
    from app.services.price_universe_runtime import (
        PRECOMPUTED_CANONICAL_REQUIREMENTS,
        PreparedPriceUniverseManager,
    )

    started = perf_counter()
    loaded = PreparedPriceUniverseManager().load_file_and_activate(path)
    if loaded.universe.universe_id != expected_id:
        raise RuntimeError("active PriceUniverse smoke load returned the wrong identity")
    load_ms = (perf_counter() - started) * 1000
    basket_started = perf_counter()
    basket = BasketOptimizer(memoize_store_subsets=True).optimize(
        PRECOMPUTED_CANONICAL_REQUIREMENTS,
        loaded.economic_pool.matched_candidates_by_name,
        loaded.stores,
        max_stores=3,
        calculate_savings=False,
    )
    return {
        "load_ms": load_ms,
        "representative_basket": {
            "requested_items": len(PRECOMPUTED_CANONICAL_REQUIREMENTS),
            "priced_items": sum(len(store.items) for store in basket.stores),
            "complete": sum(len(store.items) for store in basket.stores)
            == len(PRECOMPUTED_CANONICAL_REQUIREMENTS),
            "total": basket.total,
            "selected_context_ids": [store.store_id for store in basket.stores],
            "runtime_ms": (perf_counter() - basket_started) * 1000,
            "live_provider_requests": 0,
        },
    }


def _active_universe_status(
    store: PreparedUniverseArtifactStore,
    city: str,
    *,
    policy: FreshnessPolicy,
    smoke_load: bool = False,
    next_expected_refresh: datetime | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    try:
        manifest = store.read_active(city)
        if manifest is None:
            return {
                "city": city,
                "status": "inactive",
                "usable": False,
                "active": False,
            }
        artifact = store.resolve_active_artifact(city)
        if artifact is None:
            raise ValueError("active manifest did not resolve an artifact")
        evaluated_at = now or datetime.now(tz=UTC)
        freshness = assess_freshness(
            manifest.oldest_base_observed_at or manifest.oldest_observed_at,
            now=evaluated_at,
            policy=policy,
        )
        projection = project_source_freshness(
            manifest.oldest_base_observed_at or manifest.oldest_observed_at,
            now=evaluated_at,
            policy=policy,
            next_expected_source_refresh=next_expected_refresh,
        )
        smoke = (
            _smoke_load_prepared_universe(artifact, manifest.universe_id) if smoke_load else None
        )
        return {
            "city": city,
            "status": freshness.state.value,
            "usable": freshness.usable,
            "active": True,
            "universe_id": manifest.universe_id,
            "built_at": manifest.built_at,
            "activated_at": manifest.activated_at,
            "oldest_observed_at": manifest.oldest_observed_at,
            "oldest_price_age_hours": freshness.age_hours,
            "hours_until_stale": freshness.hours_until_stale,
            "stale_at": freshness.stale_at,
            "next_expected_source_refresh": next_expected_refresh,
            "source_will_expire_before_next_refresh": (
                projection.source_will_expire_before_next_refresh
            ),
            "snapshot_ids": list(manifest.snapshot_ids),
            "product_count": manifest.product_count,
            "canonical_index_count": manifest.canonical_index_count,
            "artifact_file": Path(manifest.artifact_file).name,
            "artifact_bytes": manifest.artifact_bytes,
            "artifact_mb": round(manifest.artifact_bytes / 1_048_576, 3),
            "hash_verified": True,
            "startup_load_ms": (round(float(smoke["load_ms"]), 3) if smoke is not None else None),
            "representative_basket_smoke": (
                smoke["representative_basket"] if smoke is not None else None
            ),
            "meal_request_provider_calls": 0,
        }
    except Exception as exc:  # noqa: BLE001 - status must be credential-free
        return {
            "city": city,
            "status": FreshnessState.BROKEN.value,
            "usable": False,
            "active": False,
            "error_type": type(exc).__name__,
        }


def _daily_refresh_lkg_status(
    settings: GroceryDataSettings,
    cache_root: Path,
    cities: tuple[str, ...],
) -> tuple[bool, list[dict[str, object]]]:
    """Read only the requested active manifests to choose truthful exit semantics."""

    policy = FreshnessPolicy(
        warning_age_hours=settings.price_age_warning_hours,
        stale_age_hours=settings.max_price_age_hours,
    )
    store = PreparedUniverseArtifactStore(cache_root)
    states = [
        # Exit code 2 means the retained universe is actually usable by the
        # current runtime, not merely fresh and hash-valid on disk.  This path
        # is only used after a lock/fatal refresh boundary, where the extra
        # authoritative load is preferable to reporting a false LKG.
        _active_universe_status(store, city, policy=policy, smoke_load=True)
        for city in cities
    ]
    return bool(states) and all(bool(state.get("usable")) for state in states), states


def _refresh_human_report(report: dict[str, object], report_path: Path | None = None) -> str:
    cities = " / ".join(str(city).upper() for city in report.get("cities", ()))
    lines = [f"{cities or 'PRICE'} PRICE REFRESH", "=" * 72]
    collection = report.get("own_collection")
    if collection is None and isinstance(report.get("own_targets"), list):
        collection = {"results": report["own_targets"]}
    if isinstance(collection, dict):
        rows = collection.get("results")
        if isinstance(rows, list):
            lines.append(
                "SOURCE      CONTEXT                         STATUS          PRODUCTS  AGE(h)  LKG"
            )
            for row in rows:
                if not isinstance(row, dict):
                    continue
                chain = str(row.get("chain") or "-")[:11]
                context = str(
                    row.get("context_name")
                    or row.get("grocery_context_id")
                    or row.get("context_store_id")
                    or row.get("city")
                    or "configured source"
                )[:31]
                status = str(row.get("status") or "-")[:15]
                products = str(row.get("products") or "-")
                age = row.get("active_snapshot_age_hours")
                age_text = f"{float(age):.1f}" if isinstance(age, (int, float)) else "-"
                lkg = "YES" if row.get("lkg_used") else "NO"
                lines.append(
                    f"{chain:<11} {context:<31} {status:<15} {products:>9} {age_text:>7}  {lkg}"
                )
                if row.get("status") in {"failed", "skipped", "not_applicable"} and row.get(
                    "reason"
                ):
                    lines.append(f"  reason: {row['reason']}")
    external = report.get("external_provider")
    if isinstance(external, dict):
        lines.append(
            "PRIMAT / LICENSED: "
            f"{external.get('status', '-')} | "
            f"max requests/city={external.get('maximum_requests_per_city', 0)}"
        )
        city_plans = external.get("city_plans")
        if isinstance(city_plans, list):
            for item in city_plans:
                if not isinstance(item, dict):
                    continue
                contexts = item.get("contexts")
                context_count = len(contexts) if isinstance(contexts, list) else 0
                lines.append(
                    "  "
                    f"{item.get('city', '-')}: {item.get('status', '-')} | "
                    f"contexts={context_count} | "
                    f"requests={item.get('provider_requests_planned', 0)}"
                )
    if isinstance(external, list):
        lines.append("PRIMAT / LICENSED")
        for item in external:
            if not isinstance(item, dict):
                continue
            lines.append(
                "  "
                f"{item.get('city', '-')}: {item.get('status', '-')} | "
                f"contexts={item.get('contexts', 0)} | rows={item.get('products', 0)} | "
                f"requests={item.get('provider_requests', 0)} | "
                f"context-LKG={item.get('context_lkg_used', 0)} | "
                f"age={item.get('age_hours', '-')} h | "
                f"LKG={'YES' if item.get('lkg_used') else 'NO'}"
            )
            if item.get("reason"):
                lines.append(f"    reason: {item['reason']}")
    universes = report.get("price_universes")
    if universes is None:
        universes = report.get("price_universe")
    if isinstance(universes, list):
        lines.append("PRICE UNIVERSE")
        for item in universes:
            if not isinstance(item, dict):
                continue
            lines.append(
                "  "
                f"{item.get('city', '-')}: {str(item.get('status', '-')).upper()} | "
                f"id={item.get('universe_id', '-')} | products={item.get('product_count', '-')} | "
                f"artifact={item.get('artifact_mb', '-')} MB | "
                f"oldest={item.get('oldest_price_age_hours', '-')} h"
            )
            if item.get("build_skipped_reason"):
                lines.append(f"    rebuild skipped: {item['build_skipped_reason']}")
    timing = report.get("timing_seconds")
    if isinstance(timing, dict):
        lines.append(
            "TIME: "
            f"collection={timing.get('collection', 0)} s, "
            f"external={timing.get('external_provider', 0)} s, "
            f"universe={timing.get('price_universe', 0)} s, "
            f"total={timing.get('total', 0)} s"
        )
    summary = report.get("summary")
    if isinstance(summary, dict):
        lines.append(
            f"RESULT: {summary.get('status', 'unknown')} (exit {summary.get('exit_code', '-')})"
        )
    if report_path is not None:
        lines.append(f"JSON REPORT: {report_path}")
    return "\n".join(lines)


def _emit_refresh_result(
    report: dict[str, object],
    *,
    output_format: str,
    report_path: Path | None = None,
) -> None:
    sanitized = credential_safe_report(report)
    if not isinstance(sanitized, dict):
        raise TypeError("refresh report did not sanitize to an object")
    if output_format == "json":
        _json(sanitized)
    else:
        print(_refresh_human_report(sanitized, report_path))


def _expected_snapshot_lineage(
    rows: list[dict[str, object]],
    city: str,
    *,
    max_age_hours: float,
    external_snapshot_ids: tuple[str, ...],
) -> tuple[str, ...]:
    expected = set(external_snapshot_ids)
    for row in rows:
        roles = {str(role).casefold() for role in row.get("roles") or ()}
        if "basket" not in roles or not _collection_row_applies_to_city(row, city):
            continue
        if row.get("promoted") and row.get("snapshot_id"):
            expected.add(str(row["snapshot_id"]))
            continue
        age = row.get("active_snapshot_age_hours")
        if (
            row.get("active_snapshot_id")
            and isinstance(age, (int, float))
            and float(age) < max_age_hours
        ):
            expected.add(str(row["active_snapshot_id"]))
    return tuple(sorted(expected))


def _source_observed_at(
    row: dict[str, object],
    *,
    now: datetime,
) -> datetime | None:
    raw = row.get("active_snapshot_observed_at") or row.get("observed_at")
    if isinstance(raw, str):
        try:
            raw = datetime.fromisoformat(raw)
        except ValueError:
            return None
    if isinstance(raw, datetime):
        if raw.tzinfo is None or raw.utcoffset() is None:
            return None
        return raw.astimezone(UTC)
    age = row.get("active_snapshot_age_hours")
    if age is None:
        age = row.get("age_hours")
    if isinstance(age, (int, float)) and not isinstance(age, bool) and age >= 0:
        from datetime import timedelta

        return now - timedelta(hours=float(age))
    return None


def _annotate_source_freshness(
    row: dict[str, object],
    *,
    now: datetime,
    policy: FreshnessPolicy,
    next_expected_refresh: datetime | None,
) -> dict[str, object]:
    """Attach policy/projection facts without changing source evidence."""

    if row.get("status") == "not_applicable" and row.get("source_management") in {"citygross_municipal", "lidl_municipal"}:
        # This is an ownership handoff, not a missing or stale catalog. Actual
        # per-store freshness is recorded by the municipal job and OWN.
        row.update(retry_required=False, source_will_expire_before_next_refresh=False)
        return row
    observed_at = _source_observed_at(row, now=now)
    roles = {str(role).casefold() for role in row.get("roles") or ()}
    basket_critical = "basket" in roles
    refresh_successful = row.get("status") in {
        "healthy",
        "planned",
        "refreshed",
        "provided_cache_activated",
    }
    projection = project_source_freshness(
        observed_at,
        now=now,
        policy=policy,
        next_expected_source_refresh=next_expected_refresh,
        basket_critical=basket_critical,
        refresh_successful=refresh_successful,
    )
    assessment = projection.freshness
    row.update(
        {
            "freshness": assessment.state.value,
            "snapshot_age_hours": assessment.age_hours,
            "hours_until_stale": assessment.hours_until_stale,
            "stale_at": assessment.stale_at,
            "next_expected_source_refresh": projection.next_expected_source_refresh,
            "source_will_expire_before_next_refresh": (
                projection.source_will_expire_before_next_refresh
            ),
            "retry_required": projection.retry_required,
        }
    )
    operational_warnings = list(row.get("operational_warnings") or ())
    if projection.source_will_expire_before_next_refresh:
        operational_warnings.append("source_will_expire_before_next_refresh")
    if projection.retry_required:
        operational_warnings.append("basket_critical_source_retry_required")
    if operational_warnings:
        row["operational_warnings"] = list(dict.fromkeys(operational_warnings))
    if (
        row.get("chain") == Chain.COOP.value
        and str(row.get("context_store_id") or "") == COOP_VERIFIED_ONLINE_CONTEXT_ID
        and basket_critical
    ):
        configuration = assess_coop_refresh_configuration(os.environ)
        row["coop_source_configuration"] = configuration.sanitized_report()
        if not configuration.valid:
            row["diagnostic_code"] = configuration.diagnostic_code
    return row


async def _daily_refresh_managed(args: argparse.Namespace) -> int:
    """Run the approved refresh graph once and publish one universe per city."""

    started_at = datetime.now(tz=UTC)
    started = perf_counter()
    settings = GroceryDataSettings.from_env()
    postal_codes = _refresh_city_postal_codes(args)
    cities = tuple(postal_codes)
    report_dir = Path(getattr(args, "report_dir", Path("reports/refresh"))).resolve()
    output_format = str(getattr(args, "format", "human"))

    if bool(getattr(args, "dry_run", False)):
        report = _daily_refresh_dry_run(args)
        targets = report.get("own_targets")
        blocked_required_targets = (
            sum(
                bool(
                    isinstance(row, dict)
                    and row.get("status") in {"failed", "skipped"}
                    and "basket" in {str(role).casefold() for role in row.get("roles") or ()}
                )
                for row in targets
            )
            if isinstance(targets, list)
            else 0
        )
        dry_run_degraded = bool(report.get("planning_failures") or blocked_required_targets)
        report["summary"] = {
            "status": "dry_run",
            "exit_code": 2 if dry_run_degraded else 0,
            "blocked_required_targets": blocked_required_targets,
        }
        path = write_refresh_report(
            report,
            report_dir,
            prefix="daily-refresh-dry-run",
        )
        _emit_refresh_result(report, output_format=output_format, report_path=path)
        return int(report["summary"]["exit_code"])  # type: ignore[index]

    database = _sqlite_database_path(settings)
    cache_root = (
        Path(args.price_universe_cache_root).resolve()
        if getattr(args, "price_universe_cache_root", None) is not None
        else settings.price_universe_cache_root.resolve()
    )
    lock = RefreshRunLock(production_refresh_lock_path(database, cache_root))
    parent_lock_nonce = os.getenv(REFRESH_PARENT_LOCK_NONCE_ENV, "").strip()
    lock_acquired_here = not parent_lock_nonce
    if parent_lock_nonce:
        if not refresh_lock_owned_by_process(
            lock.path,
            nonce=parent_lock_nonce,
            pid=os.getppid(),
        ):
            raise RuntimeError("invalid internal parent refresh-lock handoff")
    else:
        try:
            lock.acquire()
        except RefreshAlreadyRunningError:
            usable_lkg, active_states = _daily_refresh_lkg_status(
                settings,
                cache_root,
                cities,
            )
            exit_code = 2 if usable_lkg else 1
            report = {
                "run_type": "daily_refresh",
                "cities": list(cities),
                "price_universes": active_states,
                "summary": {
                    "status": "refresh_already_running",
                    "exit_code": exit_code,
                },
            }
            _emit_refresh_result(report, output_format=output_format)
            return exit_code

    collection_seconds = external_seconds = universe_seconds = 0.0
    report: dict[str, object] = {
        "run_type": "daily_refresh",
        "started_at": started_at,
        "cities": list(cities),
        "postal_codes": postal_codes,
        "meal_generation_live_provider_requests": 0,
        "discovery_requests": 0,
        "schedule": "manual_or_once_daily",
    }
    try:
        policy = FreshnessPolicy(
            warning_age_hours=settings.price_age_warning_hours,
            stale_age_hours=settings.max_price_age_hours,
        )
        next_expected_refresh = next_scheduled_refresh(
            os.getenv("DAILY_REFRESH_SCHEDULE"),
            now=started_at,
        )
        collection_started = perf_counter()
        collection, collection_exit = await _run_collect_all(args)
        collection_seconds = perf_counter() - collection_started
        raw_rows = collection.get("results")
        if not isinstance(raw_rows, list):
            raise TypeError("OWN collection report lacks result rows")
        collection_annotated_at = datetime.now(tz=UTC)
        rows: list[dict[str, object]] = []
        for raw in raw_rows:
            if not isinstance(raw, dict):
                raise TypeError("OWN collection result row must be an object")
            row = dict(raw)
            age = row.get("active_snapshot_age_hours")
            usable_lkg = bool(
                row.get("active_snapshot_id")
                and isinstance(age, (int, float))
                and float(age) < settings.max_price_age_hours
            )
            row["lkg_used"] = bool(not row.get("promoted") and usable_lkg)
            rows.append(
                _annotate_source_freshness(
                    row,
                    now=collection_annotated_at,
                    policy=policy,
                    next_expected_refresh=next_expected_refresh,
                )
            )
        collection["results"] = rows
        report["own_collection"] = collection

        requested_context = str(getattr(args, "context_store_id", "") or "").strip()
        requested_context_rows = [
            row
            for row in rows
            if requested_context
            and str(row.get("context_store_id") or "").strip() == requested_context
        ]
        # An exact-context command is an operator request for that one OWN
        # collection. If planning rejected it (for example because REVIEW
        # opt-in/allowlisting is absent), refreshing an unrelated external
        # cache and building a universe cannot satisfy the request.
        targeted_collection_not_eligible = bool(
            requested_context_rows
            and all(row.get("status") == "skipped" for row in requested_context_rows)
        )
        downstream_skip_reason = (
            "requested_own_context_not_eligible" if targeted_collection_not_eligible else None
        )

        universe_store = PreparedUniverseArtifactStore(cache_root)
        external_store = ClosedProviderCacheArtifactStore(cache_root / "external-provider-cache")
        candidate_root = cache_root / "refresh-candidates"
        candidate_root.mkdir(parents=True, exist_ok=True)
        explicit_caches = _external_cache_inputs(args, cities)
        if getattr(args, "price_universe_candidate", None) is not None and len(cities) != 1:
            raise ValueError("one explicit PriceUniverse candidate supports exactly one city")

        # Respect the existing explicit OWN-only runtime mode. The default
        # federated mode still requires the complete current external cache;
        # absence of context mappings never selects OWN-only implicitly.
        external_required_for_universe = not getattr(settings, "own_sources_only", False) and any(
            source_strategy_for(chain).primary_source.provider is SourceProvider.PRIMAT
            for chain in Chain
        )
        # --chain narrows OWN collection work, not the federated universe.
        # A targeted Hemköp refresh still needs the complete external cache
        # before Lund can be rebuilt without silently dropping ICA/Lidl rows.
        live_external_enabled = bool(
            external_required_for_universe and not getattr(args, "no_external_refresh", False)
        )
        external_paths: dict[str, Path | None] = {}
        external_snapshot_ids: dict[str, tuple[str, ...]] = {}
        external_build_allowed: dict[str, bool] = {}
        external_reports: list[dict[str, object]] = []

        external_started = perf_counter()
        for city, postal_code in postal_codes.items():
            city_external_started = perf_counter()
            if getattr(settings, "own_sources_only", False):
                if city in explicit_caches:
                    raise ValueError("OWN-only runtime cannot import an external price cache")
                external_paths[city], external_snapshot_ids[city] = None, ()
                external_build_allowed[city] = True
                external_reports.append({"city": city, "postal_code": postal_code,
                    "provider": SourceProvider.PRIMAT.value, "status": "not_selected",
                    "reason": "explicit_own_sources_only", "provider_requests": 0,
                    "contexts": 0, "products": 0, "snapshot_ids": [],
                    "lkg_used": False, "credentials_included": False})
                continue
            if targeted_collection_not_eligible:
                external_paths[city] = None
                external_snapshot_ids[city] = ()
                external_build_allowed[city] = False
                external_reports.append(
                    {
                        "city": city,
                        "postal_code": postal_code,
                        "provider": SourceProvider.PRIMAT.value,
                        "status": "not_run",
                        "reason": downstream_skip_reason,
                        "contexts": 0,
                        "context_failures": 0,
                        "context_lkg_used": 0,
                        "products": 0,
                        "age_hours": None,
                        "snapshot_ids": [],
                        "provider_requests": 0,
                        "runtime_seconds": round(
                            perf_counter() - city_external_started,
                            3,
                        ),
                        "lkg_used": False,
                        "error_type": None,
                        "context_validation": None,
                        "context_activation": None,
                        "cache_file": None,
                        "credentials_included": False,
                    }
                )
                continue
            city_slug = _safe_scope_slug(city)
            candidate = candidate_root / (
                f"primat-{city_slug}-{started_at.strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex}.json"
            )
            source_status = "not_selected"
            source_stage = "resolve_previous_cache"
            source_diagnostic = None
            source_error: str | None = None
            source_requests = 0
            source_contexts = 0
            source_context_failures = 0
            source_context_lkg = 0
            source_products = 0
            source_age_hours: float | None = None
            activated_path: Path | None = None
            snapshot_ids: tuple[str, ...] = ()
            context_validation: dict[str, object] | None = None
            context_activation: dict[str, object] | None = None
            used_lkg = False
            previous_external_manifest = external_store.active_manifest_bytes(city)
            external_manifest_changed = False
            try:
                prior = external_store.resolve_active(city, policy=policy)
                prior_lkg_path = prior[0] if prior is not None and prior[1].usable else None
                supplied = explicit_caches.get(city)
                if supplied is not None:
                    inspection = inspect_closed_provider_cache(supplied, policy=policy)
                    if inspection.postal_code != postal_code:
                        raise ValueError("explicit external cache has the wrong postal scope")
                    _manifest, context_validation = external_store.activate_validated(
                        supplied,
                        city=city,
                        policy=policy,
                        validator=lambda artifact: _external_context_validation_decision(
                            settings,
                            artifact,
                        ),
                    )
                    external_manifest_changed = (
                        external_store.active_manifest_bytes(city) != previous_external_manifest
                    )
                    source_status = "provided_cache_activated"
                elif live_external_enabled:
                    source_stage = "collect_parse_validate_export"
                    collected = await _collect_production_primat_cache(
                        database=database,
                        city=city,
                        postal_code=postal_code,
                        output=candidate,
                        max_age_hours=settings.max_price_age_hours,
                        lkg_cache=prior_lkg_path,
                    )
                    source_status = str(collected.get("status") or "failed").casefold()
                    transport = collected.get("transport")
                    if isinstance(transport, dict):
                        source_requests = int(transport.get("requests") or 0)
                    contexts = collected.get("contexts")
                    source_contexts = (
                        len(contexts)
                        if isinstance(contexts, list)
                        else int(collected.get("contexts") or 0)
                    )
                    source_context_failures = int(collected.get("context_failures") or 0)
                    source_context_lkg = int(collected.get("context_lkg_used") or 0)
                    output = collected.get("output")
                    if isinstance(output, dict):
                        source_products = int(output.get("products") or 0)
                    if source_status == "pass":
                        source_stage = "validate_and_activate_cache"
                        _manifest, context_validation = external_store.activate_validated(
                            candidate,
                            city=city,
                            policy=policy,
                            validator=lambda artifact: _external_context_validation_decision(
                                settings,
                                artifact,
                            ),
                        )
                        external_manifest_changed = (
                            external_store.active_manifest_bytes(city) != previous_external_manifest
                        )
                        source_status = "refreshed"
                    elif source_status == "skipped":
                        source_status = str(
                            collected.get("reason_code") or "external_refresh_skipped"
                        )
                    else:
                        raise RuntimeError("bounded Primat refresh did not pass")
                elif bool(getattr(args, "no_external_refresh", False)):
                    source_status = "active_cache_reuse_requested"

                resolved = external_store.resolve_active(
                    city,
                    policy=policy,
                )
                if resolved is not None and resolved[1].usable:
                    activated_path, cache_status, _manifest = resolved
                    source_stage = "activate_context_links"
                    context_activation = _activate_external_context_links(
                        settings,
                        activated_path,
                    )
                    if (
                        context_activation.get("status") != "activated"
                        or int(context_activation.get("rejected") or 0) != 0
                    ):
                        raise RuntimeError("external context activation was rejected")
                    snapshot_ids = cache_status.snapshot_ids
                    source_age_hours = cache_status.age_hours
                    source_contexts = source_contexts or cache_status.stores
                    source_products = source_products or cache_status.products
                    explicitly_reused = source_status == "active_cache_reuse_requested"
                    city_lkg = source_status not in {
                        "refreshed",
                        "provided_cache_activated",
                        "active_cache_reuse_requested",
                    }
                    used_lkg = city_lkg or source_context_lkg > 0
                    if explicitly_reused:
                        source_status = "active_cache_reused"
                    elif city_lkg:
                        source_status = "lkg_retained"
                    elif source_context_lkg:
                        source_status = "refreshed_with_context_lkg"
                elif source_status == "active_cache_reuse_requested":
                    source_status = "active_cache_unavailable"
            except Exception as exc:  # noqa: BLE001 - external city failures are isolated
                from grocery_data.app.services.refresh_diagnostics import source_failure_diagnostic

                source_error = type(exc).__name__
                source_diagnostic = getattr(
                    exc, "refresh_diagnostic", None
                ) or source_failure_diagnostic(exc)
                source_diagnostic = {"stage": source_stage, **source_diagnostic}
                source_requests = int(source_diagnostic.get("provider_requests", source_requests))
                try:
                    if external_manifest_changed:
                        external_store.restore_active_manifest(
                            city,
                            previous_external_manifest,
                        )
                    resolved = external_store.resolve_active(city, policy=policy)
                    if resolved is not None and resolved[1].usable:
                        activated_path, cache_status, _manifest = resolved
                        context_activation = _activate_external_context_links(
                            settings,
                            activated_path,
                        )
                        if (
                            context_activation.get("status") != "activated"
                            or int(context_activation.get("rejected") or 0) != 0
                        ):
                            raise RuntimeError("external LKG activation was rejected")
                        snapshot_ids = cache_status.snapshot_ids
                        source_age_hours = cache_status.age_hours
                        source_contexts = cache_status.stores
                        source_products = cache_status.products
                        used_lkg = True
                        source_status = "lkg_retained"
                    else:
                        source_status = "failed_no_lkg"
                except Exception as lkg_exc:  # noqa: BLE001 - report only error type
                    source_status = "failed_no_lkg"
                    source_error = type(lkg_exc).__name__
                    activated_path = None
            finally:
                if candidate.exists():
                    candidate.unlink()

            external_paths[city] = activated_path
            external_snapshot_ids[city] = snapshot_ids
            # A missing mapping is not authority to publish an OWN-only universe.
            # Even a source-targeted refresh must retain the complete federated
            # scope through a fresh active external cache.
            external_build_allowed[city] = bool(
                not external_required_for_universe or activated_path is not None
            )
            external_reports.append(
                {
                    "city": city,
                    "postal_code": postal_code,
                    "provider": SourceProvider.PRIMAT.value,
                    "roles": ("basket",),
                    "status": source_status,
                    "contexts": source_contexts,
                    "context_failures": source_context_failures,
                    "context_lkg_used": source_context_lkg,
                    "products": source_products,
                    "age_hours": source_age_hours,
                    "snapshot_ids": list(snapshot_ids),
                    "provider_requests": source_requests,
                    "runtime_seconds": round(
                        perf_counter() - city_external_started,
                        3,
                    ),
                    "lkg_used": used_lkg,
                    "error_type": source_error,
                    "failure_diagnostic": source_diagnostic,
                    "context_validation": context_validation,
                    "context_activation": context_activation,
                    "cache_file": activated_path.name if activated_path is not None else None,
                    "credentials_included": False,
                }
            )
            _annotate_source_freshness(
                external_reports[-1],
                now=datetime.now(tz=UTC),
                policy=policy,
                next_expected_refresh=next_expected_refresh,
            )
        external_seconds = perf_counter() - external_started
        report["external_provider"] = external_reports

        if os.getenv("ICA_STRUCTURED_OFFERS_ENABLED", "false").casefold() == "true":
            from grocery_data.app.services.ica_offer_job import run_structured_offer_job
            report["ica_structured_offers"] = []
            for city in cities:
                try:
                    offer_result = await run_structured_offer_job(city=city, root=Path(os.getenv(
                        "ICA_STRUCTURED_OFFERS_ROOT", str(database.parent / "ica-structured-offers"))))
                    report["ica_structured_offers"].append({k: v for k, v in offer_result.items()
                        if k not in {"coverage"}})
                except Exception as exc:  # noqa: BLE001 - optional source keeps valid base
                    report["ica_structured_offers"].append({"city": city,
                        "status": "failed_optional_source_lkg_retained", "error": type(exc).__name__})

        if not bool(getattr(args, "no_promote", False)):
            from grocery_data.app.services import hemkop_municipal_job
            report['hemkop_municipal'] = []
            for city in cities:
                try:
                    result = await hemkop_municipal_job.run_source_job(city=city)
                    report['hemkop_municipal'].append({k: v for k, v in result.items() if k != 'inventory'})
                except Exception as exc:  # noqa: BLE001 - optional source preserves mandatory base
                    report['hemkop_municipal'].append({'city': city, 'status': 'failed_optional_source', 'error_type': type(exc).__name__})
            from grocery_data.app.services.coop_offer_job import run_offer_job
            try:
                report["coop_municipal_offers"] = await run_offer_job()
            except Exception as exc:  # noqa: BLE001 - optional source cannot break valid base
                report["coop_municipal_offers"] = {"status": "failed_optional_source", "error_type": type(exc).__name__}
            from grocery_data.app.services.citygross_municipal_job import run_source_job
            try:
                report["citygross_municipal"] = await run_source_job()
            except Exception as exc:  # noqa: BLE001 - optional source cannot break valid base
                report["citygross_municipal"] = {"status": "failed_optional_source", "error_type": type(exc).__name__}
            from grocery_data.app.services.lidl_municipal_job import run_source_job as run_lidl_job
            try:
                report["lidl_municipal"] = await run_lidl_job()
            except Exception as exc:  # noqa: BLE001 - optional source
                report["lidl_municipal"] = {"status": "failed_optional_source", "error_type": type(exc).__name__}
            from grocery_data.app.services.willys_flyer_job import (
                run_source_job as run_willys_flyer_job,
            )
            try:
                report["willys_flyer"] = await run_willys_flyer_job()
            except Exception as exc:  # noqa: BLE001 - optional source cannot stop the base
                report["willys_flyer"] = {"status": "failed_optional_source", "error_type": type(exc).__name__}

        universe_reports: list[dict[str, object]] = []
        build_failed = False
        universe_started = perf_counter()
        for city, postal_code in postal_codes.items():
            existing_before = universe_store.active_manifest_bytes(city)
            build_report: dict[str, object] | None = None
            build_error: str | None = None
            build_skipped_reason: str | None = None
            activation_status: str | None = None
            if bool(getattr(args, "no_promote", False)):
                build_error = "promotion_disabled"
                build_failed = True
            elif targeted_collection_not_eligible:
                build_skipped_reason = downstream_skip_reason
            elif not external_build_allowed[city]:
                build_error = "required_external_cache_unavailable"
                build_failed = True
            else:
                candidate_arg = getattr(args, "price_universe_candidate", None)
                candidate = (
                    Path(candidate_arg).resolve(strict=True)
                    if candidate_arg is not None
                    else candidate_root
                    / (
                        f"price-universe-{_safe_scope_slug(city)}-"
                        f"{started_at.strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex}.json"
                    )
                )
                try:
                    if candidate_arg is None:
                        if output_format == "human":
                            print(f"Building inactive PriceUniverse for {city} ...")
                        build_report = await _build_production_price_universe(
                            database=database,
                            city=city,
                            postal_code=postal_code,
                            external_cache=external_paths[city],
                            output=candidate,
                            max_price_age_hours=settings.max_price_age_hours,
                        )
                        if str(build_report.get("status")).casefold() != "pass":
                            raise RuntimeError("PriceUniverse candidate build did not pass")
                    expected = _expected_snapshot_lineage(
                        rows,
                        city,
                        max_age_hours=settings.max_price_age_hours,
                        external_snapshot_ids=external_snapshot_ids[city],
                    )
                    activation = universe_store.activate(
                        candidate,
                        city=city,
                        validator=lambda payload, city: validate_backend_prepared_universe_artifact(
                            payload,
                            city,
                            required_context_ids=settings.price_universe_required_context_ids,
                            max_price_age_hours=settings.max_price_age_hours,
                        ),
                        expected_snapshot_ids=expected,
                        freshness_policy=policy,
                    )
                    activation_status = activation.status
                except Exception as exc:  # noqa: BLE001 - old active manifest is LKG
                    build_error = type(exc).__name__
                    from grocery_data.app.services.operations_diagnostics import (
                        record_pipeline_failure,
                    )

                    try:
                        record_pipeline_failure("price_universe_build", exc, scope=city)
                    except (OSError, ValueError, KeyError, TypeError) as diagnostic_error:
                        # Original failure remains authoritative if diagnostics
                        # cannot be written (for example a full filesystem).
                        report["incident_index_error"] = type(diagnostic_error).__name__
                    build_failed = True
                    if universe_store.active_manifest_bytes(city) != existing_before:
                        raise RuntimeError(
                            "active PriceUniverse changed after a failed rebuild"
                        ) from None
                finally:
                    if candidate_arg is None and candidate.exists():
                        candidate.unlink()

            active = _active_universe_status(
                universe_store,
                city,
                policy=policy,
                smoke_load=activation_status is not None,
                next_expected_refresh=next_expected_refresh,
                now=datetime.now(tz=UTC),
            )
            active["activation_status"] = activation_status
            active["build_error"] = build_error
            active["build_skipped_reason"] = build_skipped_reason
            active["active_unchanged"] = activation_status is None
            if build_report is not None:
                active["build"] = build_report
                timing = build_report.get("timing_ms")
                if isinstance(timing, dict):
                    active["build_time_seconds"] = round(
                        float(timing.get("total") or 0) / 1000,
                        3,
                    )
            universe_reports.append(active)
        universe_seconds = perf_counter() - universe_started
        report["price_universes"] = universe_reports

        collection_degraded = any(row.get("status") in {"failed", "skipped"} for row in rows)
        external_degraded = any(
            row.get("status")
            in {
                "lkg_retained",
                "refreshed_with_context_lkg",
                "failed_no_lkg",
                "live_refresh_disabled",
                "active_cache_unavailable",
                "no_verified_primat_primary_contexts",
            }
            for row in external_reports
        )
        usable = all(bool(item.get("usable")) for item in universe_reports)
        fresh = all(item.get("status") == FreshnessState.FRESH.value for item in universe_reports)
        degraded = bool(
            collection_exit != 0
            or collection_degraded
            or external_degraded
            or build_failed
            or not fresh
        )
        exit_code = 1 if not usable else 2 if degraded else 0
        report["completed_at"] = datetime.now(tz=UTC)
        report["timing_seconds"] = {
            "collection": round(collection_seconds, 3),
            "external_provider": round(external_seconds, 3),
            "price_universe": round(universe_seconds, 3),
            "total": round(perf_counter() - started, 3),
        }
        report["summary"] = {
            "status": "fatal" if exit_code == 1 else "degraded" if exit_code == 2 else "complete",
            "exit_code": exit_code,
            "active_universes": sum(bool(item.get("active")) for item in universe_reports),
            "fresh_universes": sum(
                item.get("status") == FreshnessState.FRESH.value for item in universe_reports
            ),
            "lkg_contexts": sum(bool(row.get("lkg_used")) for row in rows)
            + sum(bool(row.get("lkg_used")) for row in external_reports),
            "universe_builds": sum(item.get("build") is not None for item in universe_reports),
            "universe_builds_per_city_max": 1,
        }
        # Optional isolated offer candidates share the operation lock but do
        # not change base readiness, source settings, or active price pointers.
        if os.getenv("ICA_AREA_OFFER_CANDIDATES_ENABLED", "false").casefold() == "true":
            from grocery_data.app.services.ica_offer_job import run_optional_candidate_job

            try:
                report["ica_offer_candidates"] = [
                    await run_optional_candidate_job(enabled=True, city=city,
                        root=report_dir / "ica-offer-candidates",
                        visual_command=json.loads(os.getenv("ICA_FLYER_VISUAL_COMMAND_JSON", "null"))) for city in cities
                ]
            except Exception as exc:  # noqa: BLE001 - optional configuration cannot stop the base
                report['ica_offer_candidates'] = [{'status':'failed_optional_configuration',
                    'error':type(exc).__name__, 'production_activation':False}]
            report["completed_at"] = datetime.now(tz=UTC)
            report["timing_seconds"]["total"] = round(perf_counter() - started, 3)
        path = write_refresh_report(report, report_dir, prefix="refresh-report")
        _emit_refresh_result(report, output_format=output_format, report_path=path)
        return exit_code
    finally:
        if lock_acquired_here:
            lock.release()


async def _daily_refresh(
    args: argparse.Namespace,
    *,
    universe_hook: UniverseRefreshHook | None = None,
) -> int:
    """Use managed production orchestration only for the new CLI surface.

    Direct callers and the established focused tests keep the old injected-hook
    seam unless the parser explicitly marks the namespace as managed.
    """

    if not bool(getattr(args, "managed_pipeline", False)):
        return await _daily_refresh_legacy(args, universe_hook=universe_hook)
    if universe_hook is not None:
        raise ValueError("managed daily-refresh does not accept an injected universe hook")
    return await _daily_refresh_managed(args)


def _refresh_status(args: argparse.Namespace) -> int:
    """Inspect persisted source/universe state without constructing a provider."""

    settings = GroceryDataSettings.from_env()
    postal_codes = _refresh_city_postal_codes(args)
    policy = FreshnessPolicy(
        warning_age_hours=settings.price_age_warning_hours,
        stale_age_hours=settings.max_price_age_hours,
    )
    root = settings.price_universe_cache_root.resolve()
    universe_store = PreparedUniverseArtifactStore(root)
    external_store = ClosedProviderCacheArtifactStore(root / "external-provider-cache")
    engine = create_database_engine(settings.database_url)
    cities: list[dict[str, object]] = []
    try:
        factory = create_session_factory(engine)
        for city, postal_code in postal_codes.items():
            universe = _active_universe_status(
                universe_store,
                city,
                policy=policy,
            )
            with session_scope(factory) as session:
                audit = PriceContextAuditor(
                    session,
                    max_price_age_hours=settings.max_price_age_hours,
                ).audit(city)
            try:
                resolved = external_store.resolve_active(city, policy=policy)
                external = (
                    {
                        **resolved[1].model_dump(mode="json"),
                        "active": True,
                    }
                    if resolved is not None
                    else {"active": False, "status": "not_configured"}
                )
            except Exception as exc:  # noqa: BLE001 - report only type
                external = {
                    "active": False,
                    "status": "broken",
                    "error_type": type(exc).__name__,
                }
            cities.append(
                {
                    "city": city,
                    "postal_code": postal_code,
                    "price_universe": universe,
                    "source_contexts": audit.model_dump(mode="json"),
                    "external_provider_cache": external,
                    "live_provider_requests": 0,
                }
            )
    finally:
        engine.dispose()

    states = [
        str(item["price_universe"].get("status"))  # type: ignore[union-attr]
        for item in cities
    ]
    if any(state in {"inactive", "broken", "stale"} for state in states):
        exit_code = 1
        overall = "unusable"
    elif any(state == FreshnessState.AGING.value for state in states):
        exit_code = 2
        overall = "aging"
    else:
        exit_code = 0
        overall = "fresh"
    report = {
        "run_type": "refresh_status",
        "generated_at": datetime.now(tz=UTC),
        "status": overall,
        "exit_code": exit_code,
        "cities": cities,
        "live_provider_requests": 0,
    }
    if getattr(args, "format", "human") == "json":
        _json(credential_safe_report(report))
    else:
        lines = [f"PRICE REFRESH STATUS: {overall.upper()}", "=" * 72]
        for item in cities:
            universe = item["price_universe"]
            audit = item["source_contexts"]
            assert isinstance(universe, dict) and isinstance(audit, dict)
            lines.append(
                f"{str(item['city']).upper()}: universe={str(universe.get('status')).upper()} "
                f"id={universe.get('universe_id', '-')} "
                f"oldest={universe.get('oldest_price_age_hours', '-')} h"
            )
            lines.append(
                "  "
                f"basket contexts={audit.get('basket_capable', 0)}, "
                f"stale={audit.get('stale', 0)}, unresolved={audit.get('mapping_unresolved', 0)}"
            )
        lines.append("LIVE PROVIDER REQUESTS: 0")
        print("\n".join(lines))
    return exit_code


async def _current_offers_report(args: argparse.Namespace) -> int:
    """Build exports from promoted snapshots, optionally refreshing stale sources."""

    reconfigure_stdout = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure_stdout):
        reconfigure_stdout(encoding="utf-8", errors="replace")

    from grocery_data.app.services.current_offers import (
        LUND_SELECTED_STORES,
        CurrentOffersReportService,
        render_current_offers_summary,
        write_current_offers_exports,
    )
    from grocery_data.app.storage import PhysicalStoreModel

    settings = GroceryDataSettings.from_env()
    max_age_hours = (
        float(args.max_age_hours)
        if args.max_age_hours is not None
        else settings.current_offers_max_age_hours
    )
    if max_age_hours <= 0:
        raise ValueError("--max-age-hours must be greater than zero")
    if args.preset == "lund-selected-stores":
        if str(args.city).strip().casefold() != "lund":
            raise ValueError("lund-selected-stores may only be used with --city Lund")
        aliases = tuple(LUND_SELECTED_STORES)
    else:
        aliases = tuple(args.store)
    if args.public_only:
        filter_mode = "public"
    elif args.member_only:
        filter_mode = "member"
    elif args.multibuy_only:
        filter_mode = "multibuy"
    else:
        filter_mode = "all"

    def external_cache_path() -> Path | None:
        cache_store = ClosedProviderCacheArtifactStore(
            settings.price_universe_cache_root.resolve() / "external-provider-cache"
        )
        manifest = cache_store.read_active(args.city)
        if manifest is None:
            return None
        path = (cache_store.root / Path(manifest.artifact_file)).resolve()
        try:
            path.relative_to(cache_store.root)
        except ValueError as exc:
            raise ValueError("active provider-cache artifact escapes its store") from exc
        return path

    def build_report():  # type: ignore[no-untyped-def]
        engine = create_database_engine(settings.database_url)
        try:
            factory = create_session_factory(engine)
            with session_scope(factory) as session:
                report = CurrentOffersReportService(
                    session,
                    external_cache=external_cache_path(),
                    max_age_hours=max_age_hours,
                ).build(
                    city=args.city,
                    store_aliases=aliases,
                    include_stale=args.include_stale,
                    filter_mode=filter_mode,
                    sort_by=args.sort,
                    active_only=args.active_only,
                )
                physical_ids = tuple(
                    store_id
                    for resolution in report.resolutions
                    for store_id in resolution.physical_store_ids
                )
                chains = tuple(
                    sorted(
                        set(
                            session.scalars(
                                select(PhysicalStoreModel.chain).where(
                                    PhysicalStoreModel.id.in_(physical_ids)
                                )
                            )
                        )
                    )
                )
            return report, chains
        finally:
            engine.dispose()

    report, chains = build_report()
    refresh_exit_code: int | None = None
    refresh_output = ""
    if args.refresh_if_stale and report.refresh_needed:
        refresh_argv = ["daily-refresh", "--city", str(args.city), "--format", "human"]
        for chain in chains:
            refresh_argv.extend(("--chain", chain))
        refresh_args = _parser().parse_args(refresh_argv)
        captured = io.StringIO()
        with redirect_stdout(captured):
            refresh_exit_code = await _daily_refresh(refresh_args)
        refresh_output = captured.getvalue().strip()
        report, _ = build_report()

    export_paths = write_current_offers_exports(report, Path(args.report_dir))
    if args.format == "json":
        _json(
            {
                "report": report.model_dump(mode="json"),
                "exports": {key: str(path) for key, path in export_paths.items()},
                "refresh_exit_code": refresh_exit_code,
            }
        )
    else:
        if refresh_output:
            print(refresh_output)
            print()
        print(render_current_offers_summary(report))
        print()
        print("EXPORTS")
        for label, path in export_paths.items():
            print(f"  {label}: {path}")
        if refresh_exit_code is not None:
            print(f"REFRESH EXIT CODE: {refresh_exit_code}")

    if report.current_offer_count == 0:
        return 1
    return 2 if report.stale_or_incomplete_sources else 0


def _activate_price_universe(args: argparse.Namespace) -> int:
    """Validate and atomically publish one closed, locally prebuilt artifact."""

    _ensure_backend_import_path()
    settings = GroceryDataSettings.from_env()
    root = (
        Path(args.cache_root)
        if getattr(args, "cache_root", None) is not None
        else settings.price_universe_cache_root
    )
    result = PreparedUniverseArtifactStore(root).activate(
        Path(args.candidate),
        city=str(args.city),
        validator=validate_backend_prepared_universe_artifact,
        expected_snapshot_ids=tuple(getattr(args, "expected_snapshot_id", ()) or ()),
        freshness_policy=FreshnessPolicy(
            warning_age_hours=settings.price_age_warning_hours,
            stale_age_hours=settings.max_price_age_hours,
        ),
    )
    _json(
        {
            "run_type": "activate_prepared_price_universe",
            "city": str(args.city).strip(),
            "result": result.model_dump(mode="json"),
            "live_provider_requests": 0,
        }
    )
    return 0


def _daily_refresh_failure_state(
    args: argparse.Namespace,
) -> tuple[int, list[dict[str, object]]]:
    """Choose fatal/degraded from persisted LKG state after an outer failure."""

    try:
        settings = GroceryDataSettings.from_env()
        cities = tuple(_refresh_city_postal_codes(args))
        cache_root = (
            Path(args.price_universe_cache_root).resolve()
            if getattr(args, "price_universe_cache_root", None) is not None
            else settings.price_universe_cache_root.resolve()
        )
        usable, states = _daily_refresh_lkg_status(settings, cache_root, cities)
        return (2 if usable else 1), states
    except Exception:  # noqa: BLE001 - failure reporting must itself fail closed
        return 1, []


def _replay_connector(
    chain: Chain,
    *,
    coverage: CoverageLevel,
    catalog_completion: object,
):
    """Create parser transport for replay without granting live crawl authority."""

    if chain in {Chain.CITY_GROSS, Chain.HEMKOP, Chain.COOP, Chain.ICA} and coverage is (
        CoverageLevel.FULL_ONLINE_CATALOG
    ):
        if not isinstance(catalog_completion, dict) or not catalog_completion:
            raise ValueError(f"{chain.value} full replay lacks captured store identities")
        store_external_ids = tuple(sorted(str(value) for value in catalog_completion))
        if chain is Chain.CITY_GROSS:
            return CityGrossConnector.for_replay(store_external_ids=store_external_ids)
        if chain is Chain.COOP:
            return CoopOnlineCatalogConnector.for_replay(context_ids=store_external_ids)
        if chain is Chain.ICA:
            return IcaOnlineCatalogConnector.for_replay(context_ids=store_external_ids)
        return HemkopConnector.for_replay(store_external_ids=store_external_ids)
    return ConnectorRegistry().create(chain)


async def _replay(args: argparse.Namespace) -> int:
    settings, engine, factory = _runtime()
    chain = Chain(args.chain)
    with session_scope(factory) as session:
        source = SnapshotRepository(session).get(args.snapshot_id)
        if source is None:
            raise LookupError("catalog snapshot does not exist")
        if source.chain != chain.value:
            raise ValueError("snapshot chain does not match requested connector")
        connector = _replay_connector(
            chain,
            coverage=CoverageLevel(source.coverage),
            catalog_completion=(source.metrics or {}).get("catalog_completion", {}),
        )
    try:
        result = await DatabaseReplayService(
            factory,
            FilesystemRawSnapshotStore(settings.raw_snapshot_root),
        ).replay_snapshot(
            connector,
            args.snapshot_id,
            promote=args.promote,
            accept_schema_change=args.accept_schema_change,
        )
        _json(asdict(result))
        return 0 if result.status.value != "broken" else 2
    finally:
        engine.dispose()


def _canary_connector(
    chain: Chain,
    *,
    store: str | None = None,
    ica_transport: str = "http",
):
    """Create a deliberately bounded live connector for diagnostic canaries."""

    if chain is Chain.WILLYS:
        client = WillysClient(max_categories=1, max_pages_per_category=1, page_size=5)
        return WillysConnector(client=client)
    if chain is Chain.CITY_GROSS:
        # FULL_ONLINE is accepted for Hyllie, but source policy remains REVIEW.
        # Canary creation is always one page and never inherits full-crawl
        # authority from the registry descriptor.
        client = CityGrossClient(page_size=5, max_pages=1, allow_full_crawl=False)
        return CityGrossConnector(client=client)
    if chain is Chain.HEMKOP:
        # Store activation still occurs in a fresh anonymous session, but the
        # canary remains exactly one category and one five-product page.
        return HemkopConnector.for_bounded_discovery(page_size=5)
    if chain is Chain.ICA:
        if store is None or not store.strip():
            raise ValueError("ICA online canary requires --store")
        if ica_transport == "browser":
            return _ica_browser_connector(store, full_catalog=False)
        if ica_transport != "http":
            raise ValueError("unknown ICA canary transport")
        return IcaOnlineCatalogConnector.for_bounded_discovery(store)
    if ica_transport != "http":
        raise ValueError("--ica-transport browser is valid only for ICA")
    return ConnectorRegistry().create(chain)


async def _canary(args: argparse.Namespace) -> int:
    settings = GroceryDataSettings.from_env()
    chain = Chain(args.chain)
    ica_transport = getattr(args, "ica_transport", "http")
    if ica_transport == "browser" and chain is not Chain.ICA:
        raise ValueError("--ica-transport browser is valid only for ICA canary")
    connector = _canary_connector(
        chain,
        store=getattr(args, "store", None),
        ica_transport=ica_transport,
    )
    raw_store = FilesystemRawSnapshotStore(settings.raw_snapshot_root)
    try:
        area = GeographicArea(city=args.city)
        stores_raw = await connector.fetch_stores(area)
        store_records = raw_store.save_batch(
            stores_raw,
            snapshot_id=f"canary-{uuid4().hex}",
        )
        stores = connector.parse_stores(
            stores_raw,
            [f"raw:{record.document_id}" for record in store_records],
            area,
        )
        eligible_stores = [store for store in stores if connector.catalog_eligible(store)]
        if not eligible_stores:
            raise RuntimeError("canary found no catalog-eligible stores")
        sample_store = eligible_stores[0]
        catalog = await connector.fetch_catalog(sample_store)
        catalog_records = raw_store.save_batch(
            catalog,
            snapshot_id=f"canary-{uuid4().hex}",
        )
        parsed = connector.parse_catalog(
            catalog,
            [f"raw:{record.document_id}" for record in catalog_records],
            sample_store,
        )
        parser_health = assess_parser_health(
            products_parsed=len(parsed.products),
            products_quarantined=len(parsed.failures),
        )
        catalog_schema_fingerprints: list[str] = []
        for document in catalog.documents:
            if "json" not in str(document.content_type or "").casefold():
                continue
            try:
                catalog_schema_fingerprints.append(fingerprint_json(document.json_payload()).digest)
            except (TypeError, ValueError):
                continue
        _json(
            {
                "chain": args.chain,
                "city": args.city,
                "status": parser_health.status.value,
                "stores_found": len(stores),
                "sample_store": sample_store.name,
                "products_parsed": len(parsed.products),
                "products_quarantined": len(parsed.failures),
                "parse_success_rate": parser_health.parse_success_rate,
                "minimum_parse_success_rate": parser_health.minimum_parse_success_rate,
                "parser_health_passed": parser_health.accepted,
                "coverage": sample_store.coverage.value,
                "requests_captured": len(stores_raw.documents) + len(catalog.documents),
                "http_requests": (
                    stores_raw.transport.request_count + catalog.transport.request_count
                ),
                "schema_fingerprints": sorted(set(catalog_schema_fingerprints)),
                "catalog_completion": (
                    catalog.catalog_completion.model_dump(mode="json")
                    if catalog.catalog_completion is not None
                    else None
                ),
                **_policy_audit_fields(collection_policy_audit(connector)),
            }
        )
        return 0 if parser_health.accepted else 2
    except Exception as exc:  # noqa: BLE001 - sanitized canary boundary
        _json({"chain": args.chain, "status": "failed", "error_type": type(exc).__name__})
        return 2
    finally:
        await connector.aclose()


async def _ica_category_proof(args: argparse.Namespace) -> int:
    """Capture and immediately replay one exact category without promotion."""

    if getattr(args, "ica_transport", "http") != "browser":
        raise ValueError("ica-category-proof requires explicit --ica-transport browser")
    settings = GroceryDataSettings.from_env()
    connector, transport = _ica_browser_category_proof_connector(args.store)
    proof_id = f"ica-category-proof-{uuid4().hex}"
    raw_store = FilesystemRawSnapshotStore(settings.raw_snapshot_root)
    try:
        observe_category_frontend = getattr(
            transport,
            "observe_category_frontend",
            None,
        )
        if not callable(observe_category_frontend):
            raise TypeError(
                "selected ICA transport does not support frontend-observed category proof"
            )
        try:
            raw = await observe_category_frontend(
                next(iter(connector.allowed_context_ids)),
                args.category_id,
            )
        except ConnectorFetchError as exc:
            # Challenge/failure diagnostics are already sanitized by the
            # transport. Preserve that partial raw-first evidence before the
            # command returns its deliberately message-free failure envelope.
            raw_store.save_batch(exc.partial_batch, snapshot_id=proof_id)
            raise
    finally:
        # `fetch_category_proof` discards the browser context itself. This
        # closes the remaining inert transport before any replay work begins.
        await connector.aclose()

    records = raw_store.save_batch(raw, snapshot_id=proof_id)
    references = [f"raw:{record.document_id}" for record in records]
    region_id = next(iter(connector.allowed_context_ids))
    from grocery_data.app.connectors.ica.online_catalog_browser_transport import (
        reconcile_category_proof,
    )

    replayed = reconcile_category_proof(
        raw,
        region_id=region_id,
        category_id=args.category_id,
    )
    context_documents = tuple(
        document
        for document in replayed.documents
        if document.kind in {ICA_STORE_CONTEXT_KIND, ICA_CATEGORY_TREE_KIND}
    )
    context_batch = RawBatch(chain=Chain.ICA, documents=context_documents)
    mapping = connector._mapping_document(context_batch, region_id)
    area = GeographicArea(city=args.city)
    stores = connector.parse_stores(
        RawBatch(chain=Chain.ICA, documents=(mapping,)),
        ["raw:derived-exact-context-mapping"],
        area,
    )
    if len(stores) != 1:
        raise RuntimeError("ICA category proof did not reproduce one exact context")
    # Pure parser replay after browser close: these calls have no transport
    # object and cannot start a browser or issue network I/O.
    parsed = connector.parse_catalog(replayed, references, stores[0])
    completion = replayed.catalog_completion
    expected_unique = completion.unique_products if completion is not None else None
    replay_pass = (
        completion is not None
        and completion.complete
        and completion.limited
        and not parsed.failures
        and len(parsed.products) == expected_unique
    )
    observed_batch_sizes = [
        int(document.query["observed_batch_size"])
        for document in raw.documents
        if document.kind == ICA_PRODUCT_BATCH_KIND
        and document.query.get("observed_batch_size") is not None
    ]
    _json(
        {
            "chain": Chain.ICA.value,
            "transport": "browser",
            "city": args.city,
            "region_id": region_id,
            "category_id": args.category_id,
            "proof_id": proof_id,
            "raw_documents": len(raw.documents),
            "raw_bytes": sum(len(document.payload) for document in raw.documents),
            "product_pages": sum(
                document.kind == ICA_PRODUCT_PAGE_KIND for document in raw.documents
            ),
            "product_batches": sum(
                document.kind == ICA_PRODUCT_BATCH_KIND for document in raw.documents
            ),
            "observed_product_batch_sizes": observed_batch_sizes,
            "observed_product_batch_size_values": sorted(set(observed_batch_sizes)),
            "transport_metrics": raw.transport.model_dump(mode="json"),
            "completion": completion.model_dump(mode="json") if completion else None,
            "offline_replay": {
                "browser_calls": 0,
                "network_calls": 0,
                "products": len(parsed.products),
                "failures": len(parsed.failures),
                "status": "pass" if replay_pass else "failed",
            },
            "promotable": False,
        }
    )
    return 0 if replay_pass else 2


def _health(_: argparse.Namespace) -> int:
    _, engine, factory = _runtime()
    rows = []
    try:
        with session_scope(factory) as session:
            repository = ConnectorHealthRepository(session)
            for descriptor in ConnectorRegistry().descriptors():
                health = repository.get(descriptor.chain)
                rows.append(
                    {
                        "chain": descriptor.chain.value,
                        "coverage": descriptor.source_coverage.value,
                        "implemented": descriptor.implemented,
                        "status": health.status if health else "unknown",
                        "last_success_at": health.last_success_at if health else None,
                        "active_snapshot_id": health.active_snapshot_id if health else None,
                        "metrics": health.metrics if health else {},
                        "warnings": health.warnings if health else [],
                        "limitation": descriptor.limitation,
                    }
                )
    finally:
        engine.dispose()
    _json({"connectors": rows})
    return 0


def _snapshot_action(args: argparse.Namespace) -> int:
    _, engine, factory = _runtime()
    try:
        manager = SnapshotManager(factory)
        if args.command == "validate":
            row = manager.validate(args.snapshot_id)
            _json({"snapshot_id": row.id, "state": row.state})
        elif args.command == "promote":
            row = manager.promote(args.snapshot_id)
            _json({"snapshot_id": row.id, "state": row.state, "active": row.is_active})
        else:
            result = manager.diff(args.old, args.new)
            _json(result.model_dump(mode="json"))
        return 0
    finally:
        engine.dispose()


def _activate_coop_online_context(args: argparse.Namespace) -> int:
    """Attach an already-promoted 730400 snapshot to exact public pickup evidence.

    This is a local database reconciliation command. It performs no Coop or
    provider request and requires an explicit existing SQLite database so an
    operator cannot accidentally fall back to the development default.
    """

    database, engine, factory = _explicit_sqlite_runtime(args.database)
    try:
        with session_scope(factory) as session:
            result = CoopOnlineContextActivationService(session).activate(args.snapshot_id)
        _json(
            {
                "run_type": "activate_coop_online_context",
                "database": str(database),
                "result": asdict(result),
                "price_semantics": "online_price",
                "physical_shelf_price_claimed": False,
                "network_requests": 0,
            }
        )
        return 0
    finally:
        engine.dispose()


def _init_db(_: argparse.Namespace) -> int:
    _, engine, _ = _runtime()
    try:
        create_schema(engine)
    finally:
        engine.dispose()
    _json({"status": "initialized"})
    return 0


def _compare_primat(args: argparse.Namespace) -> int:
    """Compare explicit exports offline; this command never initializes providers."""

    report = compare_export_files(
        Path(args.own_export),
        Path(args.primat_export),
        store=args.store,
        sample_limit=args.sample_limit,
    )
    _json(report.model_dump(mode="json"))
    return 0


def _analyze_unknown_purchase_model(args: argparse.Namespace) -> int:
    _, engine, factory = _runtime()
    try:
        report = PurchaseModelAnalyzer(factory).analyze(
            Chain(args.chain),
            snapshot=args.snapshot,
            top_limit=args.top_limit,
            sample_limit=args.sample_limit,
        )
    finally:
        engine.dispose()
    _json(report)
    return 0


def _benchmark_ica_recipe_coverage(args: argparse.Namespace) -> int:
    _, engine, factory = _runtime()
    try:
        with session_scope(factory) as session:
            report = RecipeQueryCoverageBenchmark(session).run(
                args.store,
                max_price_age_days=args.max_age_days,
            )
            _json(report.model_dump(mode="json"))
    finally:
        engine.dispose()
    return 0


def _benchmark_catalog_recipe_coverage(args: argparse.Namespace) -> int:
    _, engine, factory = _runtime()
    try:
        with session_scope(factory) as session:
            report = CatalogRecipeCoverageBenchmark(session).run(
                args.snapshot_id,
                args.store_id,
                max_price_age_days=args.max_age_days,
            )
            _json(report.model_dump(mode="json"))
    finally:
        engine.dispose()
    return 0


def _benchmark_planner(args: argparse.Namespace) -> int:
    """Delegate to the offline active-PriceUniverse production benchmark."""

    backend_dir = Path(__file__).resolve().parents[1] / "backend"
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    from scripts.benchmark_planner_production import cli_main

    argv = [
        "--golden",
        args.golden,
        "--city",
        args.city,
        "--scenario",
        args.scenario,
        "--runs",
        str(args.runs),
        "--report-dir",
        str(args.report_dir),
        "--request-cold-target-seconds",
        str(args.request_cold_target_seconds),
        "--warm-target-seconds",
        str(args.warm_target_seconds),
        "--format",
        args.format,
    ]
    if args.cold:
        argv.append("--cold")
    if args.warm:
        argv.append("--warm")
    if args.enforce_targets:
        argv.append("--enforce-targets")
    return cli_main(argv)


def _catalog_snapshot_quality(args: argparse.Namespace) -> int:
    _, engine, factory = _runtime()
    try:
        with session_scope(factory) as session:
            report = CatalogSnapshotQualityReporter(session).run(
                args.snapshot_id,
                args.store_id,
                max_manual_samples=args.sample_limit,
            )
            _json(report.model_dump(mode="json"))
    finally:
        engine.dispose()
    return 0


def _optional_prompt(value: str | None, prompt: str) -> str | None:
    if value is not None:
        normalized = value.strip()
        return normalized or None
    if not sys.stdin.isatty():
        return None
    normalized = input(prompt).strip()
    return normalized or None


def _decimal_input(value: str | None, *, field: str, required: bool = False) -> Decimal | None:
    if value is None:
        if required:
            raise ValueError(f"{field} is required")
        return None
    normalized = value.strip().replace(",", ".")
    if not normalized:
        if required:
            raise ValueError(f"{field} is required")
        return None
    try:
        return Decimal(normalized)
    except InvalidOperation as exc:
        raise ValueError(f"{field} must be a decimal number") from exc


def _record_physical_price(args: argparse.Namespace) -> int:
    """Persist one optional manual sample without mutating catalog prices."""

    _, engine, factory = _runtime()
    try:
        store_id = _optional_prompt(args.store, "Physical store ID: ")
        if store_id is None:
            raise ValueError("--store is required outside an interactive terminal")
        gtin = _optional_prompt(args.gtin, "GTIN (leave blank to use product name): ")
        product_name = _optional_prompt(
            args.product_name,
            "Product name (optional when GTIN is supplied): ",
        )
        price_text = args.price
        if price_text is None and sys.stdin.isatty():
            price_text = input("Shelf price (SEK): ")
        observed_at = (
            datetime.fromisoformat(args.observed_at) if args.observed_at else datetime.now(tz=UTC)
        )
        provisional = PhysicalPriceObservation(
            id=uuid4().hex,
            physical_store_id=store_id,
            gtin=gtin,
            product_name=product_name,
            shelf_price=_decimal_input(price_text, field="price", required=True),
            comparison_price=_decimal_input(args.comparison_price, field="comparison-price"),
            comparison_unit=args.comparison_unit,
            promotion_type=(PromotionType(args.promotion) if args.promotion else None),
            member_only=args.member_only,
            multibuy_quantity=args.multibuy_quantity,
            multibuy_total_price=_decimal_input(
                args.multibuy_total_price,
                field="multibuy-total-price",
            ),
            observed_at=observed_at,
            confidence=Confidence.UNKNOWN,
            notes=args.notes,
        )
        with session_scope(factory) as session:
            store = PhysicalStoreRepository(session).get(store_id)
            if store is None:
                raise LookupError("physical store does not exist")
            reader = PersistedPhysicalPriceCandidateReader(session)
            candidates = combined_candidates_for_observation(
                provisional,
                persisted_reader=reader,
                external_reader=PersistedExternalPhysicalPriceCandidateReader(session),
            )
            comparisons = PhysicalPriceValidationService().compare_observation(
                provisional,
                candidates,
                expected_providers=expected_providers_for_store(session, store_id),
            )
            observation = provisional.model_copy(
                update={
                    "confidence": derived_observation_confidence(
                        comparisons,
                        gtin=provisional.gtin,
                    )
                }
            )
            PhysicalPriceObservationRepository(session).add(observation)
        _json(
            {
                "observation": observation.model_dump(mode="json"),
                "comparisons": [row.model_dump(mode="json") for row in comparisons],
                "catalog_price_updated": False,
                "sampled_only": True,
            }
        )
        return 0
    finally:
        engine.dispose()


def _physical_price_report(args: argparse.Namespace) -> int:
    settings, engine, factory = _runtime()
    try:
        with session_scope(factory) as session:
            if args.store:
                store = PhysicalStoreRepository(session).get(args.store)
                if store is None:
                    raise LookupError("physical store does not exist")
                rows = PhysicalPriceObservationRepository(session).list_for_store(args.store)
                scope = ", ".join(part for part in (store.name, store.city) if part) or store.id
            else:
                if args.chain is None and args.city is None:
                    raise ValueError("physical-price-report requires --store, --chain or --city")
                rows = PhysicalPriceObservationRepository(session).list_for_scope(
                    chain=Chain(args.chain) if args.chain else None,
                    city=args.city,
                )
                scope_parts = [
                    args.chain.upper() if args.chain else "All chains",
                    args.city,
                ]
                scope = ", ".join(part for part in scope_parts if part)
            observations = [physical_observation_from_row(row) for row in rows]
            reader = PersistedPhysicalPriceCandidateReader(session)
            validator = PhysicalPriceValidationService()
            session_comparisons: dict[
                str,
                dict[str, tuple[PhysicalPriceComparison, ...]],
            ] = {}
            session_comparison_provenance: dict[str, dict[str, object]] = {}
            session_bundles: dict[str, PhysicalSessionComparisonBundle] = {}
            comparison_rows = []
            for observation in observations:
                if observation.validation_session_item_id:
                    session_id = observation.validation_session_id or ""
                    if session_id not in session_comparisons:
                        bundle = PhysicalSessionReconciliationService(session).current_report(
                            session_id
                        )
                        grouped: dict[str, list[PhysicalPriceComparison]] = {}
                        for comparison in bundle.comparisons:
                            grouped.setdefault(comparison.observation_id, []).append(comparison)
                        session_comparisons[session_id] = {
                            key: tuple(value) for key, value in grouped.items()
                        }
                        session_comparison_provenance[session_id] = bundle.metadata()
                        session_bundles[session_id] = bundle
                    comparison_rows.extend(session_comparisons[session_id].get(observation.id, ()))
                    continue
                comparison_rows.extend(
                    validator.compare_observation(
                        observation,
                        combined_candidates_for_observation(
                            observation,
                            persisted_reader=reader,
                            external_reader=PersistedExternalPhysicalPriceCandidateReader(session),
                        ),
                        expected_providers=expected_providers_for_store(
                            session,
                            observation.physical_store_id,
                        ),
                    )
                )
            comparisons = tuple(comparison_rows)
            report = build_accuracy_report(
                observations,
                comparisons,
                scope_label=scope,
                minimum_sample=settings.min_sample_for_accuracy_score,
            )
            completed_session_reports: dict[str, dict[str, object]] = {}
            validation_repository = PhysicalValidationSessionRepository(session)
            for session_id, legacy_bundle_object in sorted(session_bundles.items()):
                validation_session = validation_repository.get(session_id)
                if (
                    validation_session is None
                    or validation_session.status is not PhysicalValidationSessionStatus.COMPLETED
                ):
                    continue
                legacy_bundle = legacy_bundle_object
                v3_report = PhysicalValidationV3Service(
                    session,
                    official_freshness_hours=Decimal(
                        str(settings.field_validation_max_price_age_hours)
                    ),
                    minimum_comparable_sample=settings.min_sample_for_accuracy_score,
                ).report(session_id)
                official = v3_report["official"]
                assert isinstance(official, dict)
                session_observations = tuple(
                    row for row in observations if row.validation_session_id == session_id
                )
                identified = sum(
                    row.identity_status
                    not in {
                        None,
                        PhysicalProductIdentityStatus.GTIN_MISMATCH,
                        PhysicalProductIdentityStatus.SHELF_CODE_UNKNOWN,
                        PhysicalProductIdentityStatus.NO_MATCH,
                    }
                    for row in session_observations
                )
                status_counts = official.get("status_counts", {})
                no_digital_match = (
                    int(status_counts.get("no_digital_match", 0))
                    if isinstance(status_counts, dict)
                    else 0
                )
                comparison_count = int(official["comparison_count"])
                counts = {
                    "raw_observations": len(session_observations),
                    "identified_observations": identified,
                    "digital_matches": comparison_count - no_digital_match,
                    "comparable_comparisons": int(official["comparable_denominator"]),
                    "excluded_comparisons": int(official["excluded_comparisons"]),
                }
                completed_session_reports[session_id] = {
                    "legacy_comparison": {
                        "metadata": legacy_bundle.metadata(),
                        "comparisons": [
                            row.model_dump(mode="json") for row in legacy_bundle.comparisons
                        ],
                        "post_visit_diagnostic_comparisons": [
                            row.model_dump(mode="json")
                            for row in legacy_bundle.diagnostic_comparisons
                        ],
                    },
                    "semantic_v2_official": official,
                    "post_visit_diagnostics": v3_report["post_visit_diagnostics"],
                    "counts": counts,
                    "v3_metadata": v3_report,
                }
        _json(
            {
                "report": report.model_dump(mode="json"),
                "comparisons": [row.model_dump(mode="json") for row in comparisons],
                "session_comparison_provenance": session_comparison_provenance,
                "completed_session_reports": completed_session_reports,
                "sampled_only": True,
                "blocks_normal_use": False,
                "accuracy_display": ("scored" if report.score_eligible else "insufficient_sample"),
            }
        )
        return 0
    finally:
        engine.dispose()


def _reconcile_physical_session(args: argparse.Namespace) -> int:
    """Add a versioned post-visit diagnostic without replacing official evidence."""

    _, engine, factory = _runtime()
    database_session = factory()
    try:
        settings = GroceryDataSettings.from_env()
        service = PhysicalValidationV3Service(
            database_session,
            official_freshness_hours=Decimal(str(settings.field_validation_max_price_age_hours)),
            minimum_comparable_sample=settings.min_sample_for_accuracy_score,
        )
        official = service.lock_official(args.session_id)
        diagnostic = service.register_post_visit_diagnostic(
            args.session_id,
            snapshot_id=args.snapshot_id,
            reason=args.reason,
        )
        if args.dry_run:
            database_session.rollback()
        else:
            database_session.commit()
        _json(
            {
                "session_id": args.session_id,
                "persisted": not args.dry_run,
                "official": official.metadata(),
                "official_comparisons": [
                    row.model_dump(mode="json") for row in official.comparisons
                ],
                "post_visit_diagnostic_comparisons": [
                    row.model_dump(mode="json") for row in diagnostic.comparisons
                ],
                "post_visit_diagnostic": diagnostic.metadata(),
                "official_replaced_by_diagnostic": False,
                "catalog_prices_updated": False,
                "physical_observations_updated": False,
                "live_provider_requests": 0,
            }
        )
        return 0
    except BaseException:
        database_session.rollback()
        raise
    finally:
        database_session.close()
        engine.dispose()


def _import_physical_digital_prices(args: argparse.Namespace) -> int:
    """Import a closed credential-free external snapshot for offline validation."""

    _, engine, factory = _runtime()
    try:
        with session_scope(factory) as session:
            result = ExternalPriceSnapshotImportService(session).import_file(
                Path(args.input),
                max_bytes=100_000_000,
            )
        _json(
            {
                "imports": [asdict(result)],
                "products": result.products,
                "credential_free": True,
                "live_provider_requests": 0,
            }
        )
        return 0
    finally:
        engine.dispose()


def _map_primat_stores(args: argparse.Namespace) -> int:
    """Replay one closed store discovery and persist only strong mappings."""

    database, engine, factory = _explicit_sqlite_runtime(args.database)
    input_path = Path(args.input)
    try:
        bundle = read_primat_store_discovery_bundle(input_path, max_bytes=5_000_000)
        with session_scope(factory) as session:
            report = ProviderStoreIdentityMappingService(session).reconcile(
                bundle,
                city=args.city,
                persist=not args.dry_run,
            )
        _json(
            {
                "report": report.model_dump(mode="json"),
                "input": {
                    "file": input_path.resolve().name,
                    "schema": bundle.schema_version,
                    "response_sha256": bundle.request.response_sha256,
                    "credential_free": True,
                },
                "persisted": not args.dry_run,
                "database": database.name,
                "live_provider_requests": 0,
                "fuzzy_auto_links": 0,
            }
        )
        return 0
    finally:
        engine.dispose()


def _verify_primat_context_smoke(args: argparse.Namespace) -> int:
    """Replay product/price smoke and activate only verified identity links."""

    database, engine, factory = _explicit_sqlite_runtime(args.database)
    try:
        bundle = read_primat_context_smoke_bundle(Path(args.input), max_bytes=5_000_000)
        with session_scope(factory) as session:
            report = ProviderContextSmokeActivationService(session).activate(
                bundle,
                city=args.city,
                persist=not args.dry_run,
            )
        _json(
            {
                "report": report.model_dump(mode="json"),
                "input": {
                    "file": Path(args.input).resolve().name,
                    "schema": bundle.schema_version,
                    "credential_free": True,
                },
                "persisted": not args.dry_run,
                "database": database.name,
                "live_provider_requests": 0,
                "identity_mapping_required": "verified",
            }
        )
        return 0 if report.contexts_rejected == 0 else 2
    finally:
        engine.dispose()


async def _audit_store_coverage(args: argparse.Namespace) -> int:
    """Run bounded official discovery, persist it, then reconcile price contexts."""

    if args.skip_official_discovery and not args.context_export:
        raise ValueError("--skip-official-discovery requires --context-export")
    if args.skip_official_discovery and (
        args.fixture or args.confirm_store_removals or args.chain != "all"
    ):
        raise ValueError("--skip-official-discovery cannot be combined with locator options")
    settings, engine, factory = _runtime()
    fixture_path = Path(args.fixture).resolve() if args.fixture else None
    selected_chain = None if args.chain == "all" else Chain(args.chain)
    adapters = {}
    if not args.skip_official_discovery:
        adapters = (
            fixture_official_store_adapters(fixture_path)
            if fixture_path is not None
            else live_official_store_adapters(
                (selected_chain,) if selected_chain is not None else None
            )
        )
        if selected_chain is not None:
            adapters = {selected_chain: adapters[selected_chain]}
    discovery_service: OfficialStoreDiscoveryService | None = None
    try:
        with session_scope(factory) as session:
            external_rows: tuple[object, ...] = ()
            if args.authoritative_context_export and not args.context_export:
                raise ValueError("--authoritative-context-export requires --context-export")
            if args.context_export:
                bundle = read_credential_free_context_bundle(
                    Path(args.context_export),
                    max_bytes=100_000_000,
                )
                external_rows = bundle.items
                wrong_city = sorted(
                    {
                        row.city
                        for row in external_rows
                        if row.city is not None
                        and row.city.casefold().strip() != args.city.casefold().strip()
                    }
                )
                if wrong_city:
                    raise ValueError("context export city does not match requested audit city")
            external_contexts = CredentialFreeContextImporter.import_rows(
                external_rows,
                max_age_hours=settings.max_price_age_hours,
            )
            discovery = None
            discovered_contexts = ()
            reconciliation_at = datetime.now(tz=UTC)
            if not args.skip_official_discovery:
                discovery_service = OfficialStoreDiscoveryService(adapters, session=session)
                discovery = await discovery_service.discover_city(
                    args.city,
                    confirm_store_removals=args.confirm_store_removals,
                    contexts=external_contexts,
                )
                discovered_contexts = tuple(
                    context for result in discovery.results.values() for context in result.contexts
                )
                reconciliation_at = discovery.generated_at
            own_contexts = OwnContextEvidenceProjector(session).project_city(args.city)
            merged_contexts = {
                (context.source_provider, context.grocery_context_id): context
                for context in (*discovered_contexts, *own_contexts, *external_contexts)
            }
            authoritative_sources = (
                {
                    (context.chain, context.source_provider, context.source_channel)
                    for context in external_contexts
                }
                if args.authoritative_context_export
                else None
            )
            reconciliation = ExactStoreContextReconciler(session).reconcile_city(
                args.city,
                tuple(merged_contexts.values()),
                verified_at=reconciliation_at,
                authoritative_sources=authoritative_sources,
            )
            # Discovery has already reconciled each chain independently into
            # the physical-store registry. Read that registry as the LKG view:
            # passing only this run's healthy chains would make a failed
            # locator look like authoritative evidence that its stores vanished.
            coverage = StoreCoverageAuditor(session).audit(
                args.city,
                now=reconciliation_at,
            )
        discovery_payload = (
            discovery.model_dump(mode="json")
            if discovery is not None
            else {
                "city": args.city,
                "mode": "context_import_only",
                "skipped": True,
                "locator_requests": 0,
                "evidence": "persisted active PhysicalStore LKG; discovery health unchanged",
            }
        )
        locator_requests = (
            sum(result.request_count for result in discovery.results.values())
            if discovery is not None
            else 0
        )
        _json(
            {
                "discovery": discovery_payload,
                "context_reconciliation": reconciliation.model_dump(mode="json"),
                "coverage": coverage.model_dump(mode="json"),
                "store_discovery_only": not args.skip_official_discovery,
                "discovery_skipped": args.skip_official_discovery,
                "context_import_only": args.skip_official_discovery,
                "locator_requests": locator_requests,
                "catalog_requests": 0,
                "physical_validation_required": False,
                "chain_scope": args.chain,
            }
        )
        return 0 if discovery is None or not discovery.errors else 2
    finally:
        if discovery_service is not None:
            await discovery_service.aclose()
        engine.dispose()


def _audit_price_contexts(args: argparse.Namespace) -> int:
    """Audit persisted context evidence without any live provider request."""

    settings, engine, factory = _runtime()
    try:
        with session_scope(factory) as session:
            report = PriceContextAuditor(
                session,
                max_price_age_hours=settings.max_price_age_hours,
            ).audit(args.city)
        _json(report.model_dump(mode="json"))
        return 0 if report.unknown == 0 else 2
    finally:
        engine.dispose()


def _community_evidence_list(args: argparse.Namespace) -> int:
    """List privacy-safe append-only reports for local moderation."""

    _settings, engine, factory = _runtime()
    try:
        with session_scope(factory) as session:
            repository = CommunityEvidenceRepository(session)
            rows = repository.list_recent(
                physical_store_id=args.store,
                chain=args.chain,
                evidence_type=(CommunityEvidenceType(args.type) if args.type else None),
                limit=args.limit,
            )
            output = []
            for row in rows:
                current_status = repository.current_status(row.id)
                if args.status and current_status.value != args.status:
                    continue
                output.append(
                    {
                        "id": row.id,
                        "created_at": row.created_at,
                        "observed_at": row.observed_at,
                        "type": row.evidence_type,
                        "source": row.evidence_source,
                        "status": current_status.value,
                        "chain": row.chain,
                        "physical_store_id": row.physical_store_id,
                        "gtin": row.gtin,
                        "source_product_id": row.source_product_id,
                        "product_name": row.product_name,
                        "shelf_price": row.shelf_price,
                        "price_unit": row.price_unit,
                        "identity_confidence": row.identity_confidence,
                        "evidence_confidence": row.evidence_confidence,
                    }
                )
            metrics = repository.privacy_safe_metrics()
        _json({"reports": output, "metrics": metrics})
        return 0
    finally:
        engine.dispose()


def _community_evidence_moderate(args: argparse.Namespace) -> int:
    """Append a moderation decision; never mutate the submitted evidence row."""

    _settings, engine, factory = _runtime()
    try:
        with session_scope(factory) as session:
            repository = CommunityEvidenceRepository(session)
            event = repository.moderate(
                args.evidence_id,
                ModerationDecision(
                    status=EvidenceVerificationStatus(args.status),
                    reason=args.reason,
                    moderator_id="local-operator",
                    idempotency_key=args.request_id,
                ),
            )
        _json(
            {
                "evidence_id": event.evidence_id,
                "status": event.status,
                "created_at": event.created_at,
                "append_only": True,
            }
        )
        return 0
    finally:
        engine.dispose()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m grocery_data")
    sub = parser.add_subparsers(dest="command", required=True)
    stores = sub.add_parser("stores", help="rediscover official chain stores")
    stores.add_argument("--city", required=True)
    stores.add_argument(
        "--chain", choices=["all", *(chain.value for chain in Chain)], default="all"
    )
    collect = sub.add_parser("collect", help="collect, validate and promote a city snapshot")
    collect.add_argument(
        "--chain", choices=["all", *(chain.value for chain in Chain)], required=True
    )
    collect.add_argument("--city", action="append", required=True)
    collect.add_argument(
        "--context-store-id",
        help=(
            "persist one explicitly allowlisted price context under its own snapshot scope; "
            "this does not grant crawl authority"
        ),
    )
    collect.add_argument(
        "--ica-transport",
        choices=("http", "browser"),
        default="http",
        help=(
            "ICA exact-context transport; browser requires --chain ica, one city and "
            "--context-store-id. It is never used by daily-refresh"
        ),
    )
    collect.add_argument(
        "--no-promote",
        action="store_true",
        help="leave a healthy candidate HEALTH_CHECKED for review and offline replay",
    )
    collect_all = sub.add_parser(
        "collect-all",
        help=(
            "run each eligible OWN connector independently; exact Hemköp Lund "
            "contexts require persisted official links plus REVIEW opt-in"
        ),
    )
    collect_all.add_argument("--city", action="append", required=True)
    collect_all.add_argument(
        "--chain",
        action="append",
        choices=[chain.value for chain in Chain],
        help="restrict collection to one or more configured chains",
    )
    collect_all.add_argument(
        "--context-store-id",
        help="exact Hemköp context; requires one city and --chain hemkop",
    )
    collect_all.add_argument(
        "--no-promote",
        action="store_true",
        help="stage healthy candidates without replacing active snapshots",
    )
    daily_refresh = sub.add_parser(
        "daily-refresh",
        help=(
            "run isolated daily OWN refreshes, retain LKG and report 36/48h freshness; "
            "never queries an external provider during meal generation"
        ),
    )
    daily_refresh.add_argument("--city", action="append", required=True)
    daily_refresh.add_argument(
        "--chain",
        action="append",
        choices=[chain.value for chain in Chain],
        help="debug only: restrict collection to one or more configured chains",
    )
    daily_refresh.add_argument(
        "--context-store-id",
        help=(
            "exact REVIEW context; requires one city and --chain hemkop/coop; "
            "Coop supports only verified online context 730400"
        ),
    )
    daily_refresh.add_argument(
        "--postal-code",
        action="append",
        help=("area build scope as CITY=NNNNN; defaults are Lund=22350 and Malmö=21120"),
    )
    daily_refresh.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "show approved work without network requests, database writes or promotions; "
            "writes only a sanitized planning report"
        ),
    )
    daily_refresh.add_argument(
        "--no-external-refresh",
        action="store_true",
        help="do not query Primat; reuse a fresh active closed cache when available",
    )
    daily_refresh.add_argument(
        "--no-promote",
        action="store_true",
        help="stage healthy OWN candidates without replacing active snapshots",
    )
    activate_universe = sub.add_parser(
        "activate-price-universe",
        help=(
            "validate and atomically activate one prebuilt local PriceUniverse artifact; "
            "makes no connector/provider request"
        ),
    )
    activate_universe.add_argument("--city", required=True)
    activate_universe.add_argument("--candidate", type=Path, required=True)
    activate_universe.add_argument(
        "--cache-root",
        type=Path,
        help="managed artifact root; defaults to PRICE_UNIVERSE_CACHE_ROOT",
    )
    activate_universe.add_argument(
        "--expected-snapshot-id",
        action="append",
        default=[],
        help=("required promoted/frozen snapshot lineage; repeat for every expected snapshot"),
    )
    daily_refresh.add_argument(
        "--external-cache",
        action="append",
        help=(
            "closed cache as CITY=PATH (or one bare path per city); suppresses live "
            "provider refresh for that city"
        ),
    )
    daily_refresh.add_argument(
        "--price-universe-candidate",
        type=Path,
        help=(
            "optional already-prebuilt credential-free prepared universe artifact; "
            "it is fully validated and activated through an atomic local manifest"
        ),
    )
    daily_refresh.add_argument(
        "--price-universe-cache-root",
        type=Path,
        help=("managed artifact/manifest root; defaults to PRICE_UNIVERSE_CACHE_ROOT"),
    )
    daily_refresh.add_argument(
        "--report-dir",
        type=Path,
        default=Path("reports/refresh"),
        help="directory for sanitized immutable aggregate JSON reports",
    )
    daily_refresh.add_argument(
        "--format",
        choices=("human", "json"),
        default="human",
        help="console output format; a JSON report is always written",
    )
    daily_refresh.set_defaults(managed_pipeline=True)
    status = sub.add_parser(
        "status",
        help="show active PriceUniverse and persisted source freshness without network",
    )
    status.add_argument("--city", action="append", required=True)
    status.add_argument(
        "--postal-code",
        action="append",
        help="optional CITY=NNNNN status scope",
    )
    status.add_argument("--format", choices=("human", "json"), default="human")
    current_offers = sub.add_parser(
        "current-offers-report",
        help=(
            "build a provenance-preserving report of current public, member and "
            "multibuy offers from approved active snapshots"
        ),
    )
    current_offers.add_argument("--city", default="Lund")
    current_offers.add_argument(
        "--store",
        action="append",
        default=[],
        help="exact store id or registry-backed store alias; repeat as needed",
    )
    current_offers.add_argument(
        "--preset",
        choices=("lund-selected-stores",),
        help="use the reviewed Lund store selection from the operations guide",
    )
    current_offers.add_argument(
        "--refresh-if-stale",
        action="store_true",
        help=(
            "run the existing approved daily-refresh pipeline when selected source "
            "data exceeds the current-offers freshness limit"
        ),
    )
    current_offers.add_argument(
        "--max-age-hours",
        type=float,
        help="override CURRENT_OFFERS_MAX_AGE_HOURS for this report",
    )
    current_offers.add_argument(
        "--sort",
        choices=("savings", "name", "category"),
        default="savings",
    )
    current_filter = current_offers.add_mutually_exclusive_group()
    current_filter.add_argument("--public-only", action="store_true")
    current_filter.add_argument("--member-only", action="store_true")
    current_filter.add_argument("--multibuy-only", action="store_true")
    current_offers.add_argument(
        "--active-only",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    current_offers.add_argument(
        "--include-stale",
        action="store_true",
        help="include clearly labelled stale rows outside the current main totals",
    )
    current_offers.add_argument(
        "--report-dir",
        type=Path,
        default=Path("reports/current-offers"),
    )
    current_offers.add_argument(
        "--format",
        choices=("human", "json"),
        default="human",
    )
    health = sub.add_parser("health", help="show connector health")
    del health
    replay = sub.add_parser("replay", help="reparse immutable raw responses without network")
    replay.add_argument("--chain", choices=[chain.value for chain in Chain], required=True)
    replay.add_argument("--snapshot-id", required=True)
    replay.add_argument("--promote", action="store_true")
    replay.add_argument("--accept-schema-change", action="store_true")
    canary = sub.add_parser("canary", help="run a tiny opt-in live connector check")
    canary.add_argument("chain", choices=[chain.value for chain in Chain])
    canary.add_argument("--city", default="Lund")
    canary.add_argument(
        "--store",
        help=("exact verified store/context identity; required by the ICA online canary"),
    )
    canary.add_argument(
        "--ica-transport",
        choices=("http", "browser"),
        default="http",
        help="ICA canary transport; browser is valid only with the ICA chain",
    )
    category_proof = sub.add_parser(
        "ica-category-proof",
        help=(
            "capture one complete allowlisted ICA category through an ephemeral browser, "
            "then close it and replay the sanitized raw documents without promotion"
        ),
    )
    category_proof.add_argument("--city", default="Lund")
    category_proof.add_argument(
        "--store",
        required=True,
        help="exact verified ICA region UUID or retailer route",
    )
    category_proof.add_argument("--category-id", required=True)
    category_proof.add_argument(
        "--ica-transport",
        choices=("http", "browser"),
        default="http",
        help="must be explicitly set to browser for this separately authorized proof",
    )
    validate = sub.add_parser("validate", help="advance a parsed snapshot after validation")
    validate.add_argument("--snapshot-id", required=True)
    promote = sub.add_parser("promote", help="atomically promote a health-checked snapshot")
    promote.add_argument("--snapshot-id", required=True)
    activate_coop_context = sub.add_parser(
        "activate-coop-online-context",
        help=(
            "link an active promoted Coop 730400 FULL_ONLINE snapshot to exact public "
            "pickup evidence; makes zero network requests"
        ),
    )
    activate_coop_context.add_argument("--snapshot-id", required=True)
    activate_coop_context.add_argument(
        "--database",
        required=True,
        help="explicit existing SQLite database; no default database is used",
    )
    diff = sub.add_parser("diff", help="compare two normalized snapshots")
    diff.add_argument("--old", required=True)
    diff.add_argument("--new", required=True)
    compare_primat = sub.add_parser(
        "compare-primat",
        help="compare own and Primat product exports offline",
    )
    compare_primat.add_argument("--store", required=True, help="store label for the report")
    compare_primat.add_argument("--own-export", required=True, help="own JSON/JSONL export")
    compare_primat.add_argument(
        "--primat-export",
        required=True,
        help="Primat JSON/JSONL export",
    )
    compare_primat.add_argument("--sample-limit", type=int, default=10)
    unknown = sub.add_parser(
        "analyze-unknown-purchase-model",
        help="diagnose products whose purchase model remains unknown",
    )
    unknown.add_argument("--chain", choices=[chain.value for chain in Chain], required=True)
    unknown.add_argument("--snapshot", default="active")
    unknown.add_argument("--top-limit", type=int, default=20)
    unknown.add_argument("--sample-limit", type=int, default=20)
    recipe_coverage = sub.add_parser(
        "benchmark-ica-recipe-coverage",
        help="measure fresh, usable ICA candidates for the meal taxonomy",
    )
    recipe_coverage.add_argument("--store", required=True, help="internal grocery-data store id")
    recipe_coverage.add_argument("--max-age-days", type=int, choices=range(1, 91), default=7)
    catalog_recipe_coverage = sub.add_parser(
        "benchmark-catalog-recipe-coverage",
        help="measure fresh usable candidates in a persisted catalog snapshot",
    )
    catalog_recipe_coverage.add_argument("--snapshot-id", required=True)
    catalog_recipe_coverage.add_argument("--store-id", required=True)
    catalog_recipe_coverage.add_argument(
        "--max-age-days", type=int, choices=range(1, 91), default=7
    )
    planner_benchmark = sub.add_parser(
        "benchmark-planner",
        help=(
            "benchmark process-cold, request-cold and warm planner latency against "
            "an immutable economic golden without provider calls"
        ),
    )
    planner_benchmark.add_argument(
        "--golden",
        default="production",
        help="'production' or an explicit repository-local golden JSON path",
    )
    planner_benchmark.add_argument("--city", default="Lund")
    planner_benchmark.add_argument(
        "--scenario",
        default="balanced_max2_no_memberships",
    )
    planner_benchmark.add_argument("--cold", action="store_true")
    planner_benchmark.add_argument("--warm", action="store_true")
    planner_benchmark.add_argument("--runs", type=int, default=3)
    planner_benchmark.add_argument(
        "--report-dir",
        type=Path,
        default=Path("reports/planner-performance/benchmarks"),
    )
    planner_benchmark.add_argument(
        "--request-cold-target-seconds",
        type=float,
        default=10.0,
    )
    planner_benchmark.add_argument(
        "--warm-target-seconds",
        type=float,
        default=1.0,
    )
    planner_benchmark.add_argument("--enforce-targets", action="store_true")
    planner_benchmark.add_argument(
        "--format",
        choices=("human", "json"),
        default="human",
    )
    snapshot_quality = sub.add_parser(
        "snapshot-quality",
        help="report persisted catalog quality and completion evidence offline",
    )
    snapshot_quality.add_argument("--snapshot-id", required=True)
    snapshot_quality.add_argument("--store-id", required=True)
    snapshot_quality.add_argument("--sample-limit", type=int, choices=range(101), default=20)
    record_physical = sub.add_parser(
        "record-physical-price",
        help="record an optional manual shelf-price sample; never updates catalog prices",
    )
    record_physical.add_argument("--store")
    record_physical.add_argument("--gtin")
    record_physical.add_argument("--product-name")
    record_physical.add_argument("--price")
    record_physical.add_argument("--comparison-price")
    record_physical.add_argument("--comparison-unit")
    record_physical.add_argument(
        "--promotion",
        choices=[promotion.value for promotion in PromotionType],
    )
    record_physical.add_argument(
        "--member-only",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    record_physical.add_argument("--multibuy-quantity", type=int)
    record_physical.add_argument("--multibuy-total-price")
    record_physical.add_argument("--observed-at")
    record_physical.add_argument("--notes")
    physical_report = sub.add_parser(
        "physical-price-report",
        help="report sampled physical-vs-digital accuracy for one physical store",
    )
    physical_report.add_argument("--store")
    physical_report.add_argument("--chain", choices=[chain.value for chain in Chain])
    physical_report.add_argument("--city")
    physical_reconcile = sub.add_parser(
        "reconcile-physical-session",
        help=(
            "explicitly compare one completed field session with one exact promoted "
            "snapshot without changing frozen evidence"
        ),
    )
    physical_reconcile.add_argument("--session-id", required=True)
    physical_reconcile.add_argument("--snapshot-id", required=True)
    physical_reconcile.add_argument(
        "--reason",
        required=True,
        help="operator reason retained with the immutable reconciliation binding",
    )
    physical_reconcile.add_argument(
        "--dry-run",
        action="store_true",
        help="validate and report the binding, then roll back all database changes",
    )
    physical_import = sub.add_parser(
        "import-physical-digital-prices",
        help="import a closed persisted external comparison cache; never calls a provider",
    )
    physical_import.add_argument("--input", required=True)
    primat_mapping = sub.add_parser(
        "map-primat-stores",
        help="replay a bounded Primat store list and persist only strong identity mappings",
    )
    primat_mapping.add_argument("--city", required=True)
    primat_mapping.add_argument(
        "--database",
        required=True,
        help="explicit existing SQLite database; no default database is used",
    )
    primat_mapping.add_argument(
        "--input",
        required=True,
        help="closed primat-store-discovery-bundle-v1",
    )
    primat_mapping.add_argument(
        "--dry-run",
        action="store_true",
        help="report decisions without changing mapping or context-link rows",
    )
    primat_smoke = sub.add_parser(
        "verify-primat-context-smoke",
        help="replay bounded Primat product/price evidence and activate verified links",
    )
    primat_smoke.add_argument("--city", required=True)
    primat_smoke.add_argument(
        "--database",
        required=True,
        help="explicit existing SQLite database; no default database is used",
    )
    primat_smoke.add_argument("--input", required=True)
    primat_smoke.add_argument(
        "--dry-run",
        action="store_true",
        help="report eligibility without changing context-link rows",
    )
    store_coverage = sub.add_parser(
        "audit-store-coverage",
        help="run bounded official store discovery and reconcile physical stores to contexts",
    )
    store_coverage.add_argument("--city", required=True)
    store_coverage.add_argument(
        "--chain",
        choices=["all", *(chain.value for chain in Chain)],
        default="all",
        help="run all official locators or one bounded chain locator (default all)",
    )
    store_coverage.add_argument(
        "--fixture",
        help="offline sanitized official-store fixture (live discovery is the default)",
    )
    store_coverage.add_argument(
        "--confirm-store-removals",
        action="store_true",
        help="confirm a non-empty locator count reduction after operator review",
    )
    store_coverage.add_argument(
        "--context-export",
        help=(
            "credential-free persisted external context evidence; never a provider key "
            "or live request"
        ),
    )
    store_coverage.add_argument(
        "--skip-official-discovery",
        action="store_true",
        help=(
            "context-import-only mode: use the persisted active PhysicalStore LKG, "
            "make zero locator/catalog requests, and leave discovery health unchanged; "
            "requires --context-export"
        ),
    )
    store_coverage.add_argument(
        "--authoritative-context-export",
        action="store_true",
        help="deactivate missing links only for provider/channels present in this non-empty export",
    )
    price_contexts = sub.add_parser(
        "audit-price-contexts",
        help="explain one persisted price-context state per physical store; makes no live requests",
    )
    price_contexts.add_argument("--city", required=True)
    community_list = sub.add_parser(
        "community-evidence-list",
        help="list recent privacy-safe community reports for moderation",
    )
    community_list.add_argument("--store")
    community_list.add_argument("--chain", choices=[chain.value for chain in Chain])
    community_list.add_argument("--type", choices=[value.value for value in CommunityEvidenceType])
    community_list.add_argument(
        "--status",
        choices=[value.value for value in EvidenceVerificationStatus],
    )
    community_list.add_argument("--limit", type=int, default=100)
    community_moderate = sub.add_parser(
        "community-evidence-moderate",
        help="append an accept/reject/quarantine/resolution decision",
    )
    community_moderate.add_argument("evidence_id")
    community_moderate.add_argument(
        "--status",
        required=True,
        choices=[
            value.value
            for value in EvidenceVerificationStatus
            if value is not EvidenceVerificationStatus.USER_REPORTED
        ],
    )
    community_moderate.add_argument("--reason", required=True)
    community_moderate.add_argument("--request-id", required=True)
    sub.add_parser("init-db", help="create development schema; use Alembic in production")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        # The export comparator is intentionally offline and credential-free.
        # Do not even read .env when this command is selected.
        if args.command == "compare-primat":
            return _compare_primat(args)
        load_dotenv()
        if args.command == "stores":
            return asyncio.run(_stores(args))
        if args.command == "collect":
            return asyncio.run(_collect(args))
        if args.command == "collect-all":
            return asyncio.run(_collect_all(args))
        if args.command == "daily-refresh":
            return asyncio.run(_daily_refresh(args))
        if args.command == "status":
            return _refresh_status(args)
        if args.command == "current-offers-report":
            return asyncio.run(_current_offers_report(args))
        if args.command == "activate-price-universe":
            return _activate_price_universe(args)
        if args.command == "replay":
            return asyncio.run(_replay(args))
        if args.command == "canary":
            return asyncio.run(_canary(args))
        if args.command == "ica-category-proof":
            return asyncio.run(_ica_category_proof(args))
        if args.command == "health":
            return _health(args)
        if args.command == "analyze-unknown-purchase-model":
            return _analyze_unknown_purchase_model(args)
        if args.command == "benchmark-ica-recipe-coverage":
            return _benchmark_ica_recipe_coverage(args)
        if args.command == "benchmark-catalog-recipe-coverage":
            return _benchmark_catalog_recipe_coverage(args)
        if args.command == "benchmark-planner":
            return _benchmark_planner(args)
        if args.command == "snapshot-quality":
            return _catalog_snapshot_quality(args)
        if args.command == "record-physical-price":
            return _record_physical_price(args)
        if args.command == "physical-price-report":
            return _physical_price_report(args)
        if args.command == "reconcile-physical-session":
            return _reconcile_physical_session(args)
        if args.command == "import-physical-digital-prices":
            return _import_physical_digital_prices(args)
        if args.command == "map-primat-stores":
            return _map_primat_stores(args)
        if args.command == "verify-primat-context-smoke":
            return _verify_primat_context_smoke(args)
        if args.command == "audit-store-coverage":
            return asyncio.run(_audit_store_coverage(args))
        if args.command == "audit-price-contexts":
            return _audit_price_contexts(args)
        if args.command == "community-evidence-list":
            return _community_evidence_list(args)
        if args.command == "community-evidence-moderate":
            return _community_evidence_moderate(args)
        if args.command == "activate-coop-online-context":
            return _activate_coop_online_context(args)
        if args.command in {"validate", "promote", "diff"}:
            return _snapshot_action(args)
        if args.command == "init-db":
            return _init_db(args)
    except KeyboardInterrupt:
        _json(
            {
                "status": "interrupted",
                "exit_code": 130,
                "active_universe_unchanged_until_atomic_activation": True,
            }
        )
        return 130
    except Exception as exc:  # noqa: BLE001 - never expose secret-bearing exception text
        active_states: list[dict[str, object]] = []
        if args.command == "daily-refresh":
            exit_code, active_states = _daily_refresh_failure_state(args)
        else:
            exit_code = 2
        failure: dict[str, object] = {
            "status": "failed",
            "error_type": type(exc).__name__,
        }
        if args.command == "daily-refresh":
            failure["exit_code"] = exit_code
            failure["price_universes"] = active_states
        _json(failure)
        return exit_code
    return 2


if __name__ == "__main__":
    sys.exit(main())
