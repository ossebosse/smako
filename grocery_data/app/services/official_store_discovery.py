from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from grocery_data.app.connectors.citygross import CityGrossConnector
from grocery_data.app.connectors.coop import CoopConnector
from grocery_data.app.connectors.hemkop import HemkopConnector
from grocery_data.app.connectors.ica import IcaConnector
from grocery_data.app.connectors.lidl import LidlConnector
from grocery_data.app.connectors.willys import WillysConnector
from grocery_data.app.domain import (
    Chain,
    ConnectorStatus,
    CoverageLevel,
    GeographicArea,
    PhysicalStore,
    PhysicalStoreLifecycleState,
    PriceContextType,
    SourceStore,
    StoreDiscoveryErrorCode,
    is_complete_catalog_coverage,
)
from grocery_data.app.domain.source_strategy import SourceChannel, SourceProvider
from grocery_data.app.services.store_coverage import (
    ExactStoreIdentityMatcher,
    GroceryContextEvidence,
)
from grocery_data.app.storage import (
    PhysicalStoreDiscoveryHealthRepository,
    PhysicalStoreRepository,
    StoreContextLinkRepository,
)

_OFFICIAL_SOURCES: dict[Chain, str] = {
    Chain.WILLYS: "https://www.willys.se/axfood/rest/v1/store",
    Chain.HEMKOP: "https://www.hemkop.se/axfood/rest/store?online=false",
    Chain.ICA: "https://www.ica.se/butiker/oppettider/lund/",
    Chain.COOP: "https://www.coop.se/butiker-erbjudanden/",
    Chain.LIDL: "https://www.lidl.se/s/sv-SE/butiker/lund/",
    Chain.CITY_GROSS: "https://www.citygross.se/api/v1/PageData/stores",
}


def stable_physical_store_id(chain: Chain, external_store_id: str) -> str:
    """Create a readable stable registry key, hashing only unusually long IDs."""

    external = external_store_id.strip()
    if not external:
        raise ValueError("external_store_id must not be blank")
    candidate = f"physical:{chain.value}:{external}"
    if len(candidate) <= 64:
        return candidate
    digest = hashlib.sha256(f"{chain.value}:{external}".encode()).hexdigest()[:32]
    return f"physical:{chain.value}:{digest}"


class OfficialStoreDiscoveryEmptyResult(RuntimeError):
    """A locator expected to contain a city returned no physical sites."""


def _source_context_capability(
    source: SourceStore,
    *,
    observed_at: datetime,
) -> GroceryContextEvidence | None:
    """Project only source-proven OWN price/offer capabilities.

    This deliberately does not make a capability basket-eligible. Eligibility
    requires a persisted promoted snapshot in :func:`persisted_own_context_evidence`.
    Lidl's public default-region offers are not assigned to its physical rows.
    """

    effective_coverage = source.coverage
    if source.chain == Chain.HEMKOP and source.online_shopping is True:
        # Bounded discovery has PARTIAL operational coverage because it has no
        # crawl authority. The row still proves this exact store can activate
        # the already accepted Hemköp full-online protocol.
        effective_coverage = CoverageLevel.FULL_ONLINE_CATALOG
    complete = is_complete_catalog_coverage(effective_coverage)
    if (
        complete
        and source.online_shopping is True
        and source.chain
        in {
            Chain.WILLYS,
            Chain.HEMKOP,
            Chain.CITY_GROSS,
        }
    ):
        channel = SourceChannel.CATALOG
        offers_only = False
    elif (
        source.coverage == CoverageLevel.OFFERS_ONLY
        and source.chain == Chain.ICA
        and bool(source.source_fields.get("offers_url"))
    ) or (
        source.coverage == CoverageLevel.OFFERS_ONLY
        and source.chain == Chain.COOP
        and bool(source.source_fields.get("store_page_path"))
    ):
        channel = SourceChannel.OFFERS
        offers_only = True
    else:
        return None

    physical_external_id = source.physical_store_external_id or source.external_id
    price_context_type = source.price_context_type
    if price_context_type is None and channel == SourceChannel.OFFERS:
        price_context_type = PriceContextType.PHYSICAL_STORE
    return GroceryContextEvidence(
        grocery_context_id=f"own:{source.chain.value}:{source.external_id}",
        chain=source.chain,
        name=source.name,
        city=source.city,
        address=source.address,
        postal_code=source.postal_code,
        latitude=source.latitude,
        longitude=source.longitude,
        external_store_id=source.external_id,
        physical_store_external_id=physical_external_id,
        price_context_type=price_context_type,
        source_provider=SourceProvider.OWN,
        source_channel=channel,
        coverage=effective_coverage,
        basket_eligible=False,
        offers_only=offers_only,
        snapshot_id=None,
        # Locator time is capability evidence, never a price observation time.
        observed_at=None,
        active=True,
        local_store_id=None,
    )


def _fixture_source_store(chain: Chain, row: Mapping[str, Any]) -> SourceStore:
    online = row.get("online_shopping") is True
    if chain == Chain.WILLYS:
        coverage = CoverageLevel.FULL_CATALOG if online else CoverageLevel.PARTIAL_CATALOG
        price_context = PriceContextType.ONLINE_STORE if online else None
    elif chain == Chain.HEMKOP:
        coverage = CoverageLevel.FULL_ONLINE_CATALOG if online else CoverageLevel.PARTIAL_CATALOG
        price_context = PriceContextType.ONLINE_STORE if online else None
    elif chain in {Chain.ICA, Chain.COOP, Chain.LIDL}:
        coverage = CoverageLevel.OFFERS_ONLY
        price_context = PriceContextType.PHYSICAL_STORE
    else:
        coverage = CoverageLevel.PARTIAL_CATALOG
        price_context = None
    external_id = str(row.get("external_store_id") or "").strip()
    source_fields: dict[str, Any] = {}
    if chain == Chain.ICA:
        source_fields["offers_url"] = "fixture:official-highlight-offers"
        source_fields["store_id"] = row.get("secondary_external_store_id")
    elif chain == Chain.COOP:
        source_fields["store_page_path"] = "fixture:official-store-detail"
    return SourceStore(
        chain=chain,
        external_id=external_id,
        name=str(row.get("name") or "").strip(),
        address=row.get("address"),
        postal_code=row.get("postal_code"),
        city=row.get("city"),
        latitude=row.get("latitude"),
        longitude=row.get("longitude"),
        online_shopping=online,
        coverage=coverage,
        price_context_type=price_context,
        physical_store_external_id=(
            external_id if chain in {Chain.WILLYS, Chain.HEMKOP, Chain.ICA, Chain.COOP} else None
        ),
        raw_reference=f"fixture:official-store:{chain.value}:{external_id}",
        source_fields=source_fields,
    )


def persisted_own_context_evidence(
    session: Session,
    city: str,
) -> tuple[GroceryContextEvidence, ...]:
    """Project active OWN contexts and their promoted snapshot evidence.

    An active StoreModel is capability evidence. It becomes basket-eligible
    only when an active PROMOTED snapshot with compatible coverage applies to
    its city/store scope. The snapshot timestamp, not locator time, is exposed
    as the price observation time.
    """

    # One city snapshot is not proof for every store in that city. The
    # projector requires actual source-product rows for the exact local store.
    from grocery_data.app.services.store_context_reconciliation import (
        OwnContextEvidenceProjector,
    )

    return OwnContextEvidenceProjector(session).project_city(city)


def _merge_context_evidence(
    *groups: Iterable[GroceryContextEvidence],
) -> tuple[GroceryContextEvidence, ...]:
    merged: dict[tuple[str, str], GroceryContextEvidence] = {}
    for group in groups:
        for context in group:
            merged[(context.source_provider.value, context.grocery_context_id)] = context
    return tuple(merged.values())


def _discovery_error_code(exc: Exception) -> StoreDiscoveryErrorCode:
    if isinstance(exc, OfficialStoreDiscoveryEmptyResult):
        return StoreDiscoveryErrorCode.EMPTY_LOCATOR_RESULT
    if isinstance(exc, TimeoutError):
        return StoreDiscoveryErrorCode.BOUNDED_TIMEOUT
    if isinstance(exc, (TypeError, ValueError)):
        return StoreDiscoveryErrorCode.SCHEMA_OR_IDENTITY_CONTRACT_FAILED
    return StoreDiscoveryErrorCode.DISCOVERY_FAILED


def _closed_discovery_error(exc: Exception) -> str:
    error_type = type(exc).__name__
    return f"{error_type}: {_discovery_error_code(exc).value}"


class OfficialStoreDiscoveryResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    chain: Chain
    city: str
    official_source: str
    status: ConnectorStatus
    complete: bool
    stores: tuple[PhysicalStore, ...] = ()
    contexts: tuple[GroceryContextEvidence, ...] = ()
    request_count: int = Field(default=0, ge=0)
    http_error_count: int = Field(default=0, ge=0)
    rate_limit_count: int = Field(default=0, ge=0)
    source_scope_total: int | None = Field(default=None, ge=0)
    outside_city_count: int = Field(default=0, ge=0)
    excluded_context_count: int = Field(default=0, ge=0)
    city_outcome: str = "stores_discovered"
    evidence: str

    @model_validator(mode="after")
    def reconcile_scope_counts(self) -> OfficialStoreDiscoveryResult:
        if self.source_scope_total is not None and self.source_scope_total != (
            len(self.stores) + self.outside_city_count + self.excluded_context_count
        ):
            raise ValueError("official locator scope totals do not reconcile")
        return self


class OfficialStoreDiscoveryReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    city: str
    generated_at: datetime
    physical_stores: int
    healthy_chains: int
    own_contexts_considered: int = Field(default=0, ge=0)
    external_contexts_considered: int = Field(default=0, ge=0)
    context_links_verified: int = Field(default=0, ge=0)
    results: dict[str, OfficialStoreDiscoveryResult]
    errors: dict[str, str] = Field(default_factory=dict)


class OfficialStoreDiscoveryAdapter(Protocol):
    chain: Chain

    async def discover(
        self,
        area: GeographicArea,
        *,
        observed_at: datetime,
    ) -> OfficialStoreDiscoveryResult: ...

    async def aclose(self) -> None: ...


class SourceStoreOfficialAdapter:
    """Adapter from a bounded chain locator to connector-neutral physical sites."""

    def __init__(
        self,
        connector: Any,
        *,
        official_source: str,
        fetch_method: str = "fetch_stores",
        parse_method: str = "parse_stores",
        include: Callable[[SourceStore], bool] | None = None,
        physical_external_id: Callable[[SourceStore], str | None] | None = None,
        physical_external_aliases: Callable[[SourceStore], Sequence[str]] | None = None,
        allow_empty_result: bool = False,
        empty_city_outcome: str = "no_city_context",
    ) -> None:
        self.connector = connector
        self.chain = Chain(connector.chain)
        self.official_source = official_source
        self.fetch_method = fetch_method
        self.parse_method = parse_method
        self.include = include or (lambda _store: True)
        self.physical_external_id = physical_external_id or (lambda store: store.external_id)
        self.physical_external_aliases = physical_external_aliases or (lambda _store: ())
        self.allow_empty_result = allow_empty_result
        self.empty_city_outcome = empty_city_outcome

    async def discover(
        self,
        area: GeographicArea,
        *,
        observed_at: datetime,
    ) -> OfficialStoreDiscoveryResult:
        batch = await getattr(self.connector, self.fetch_method)(area)
        references = [
            f"official-store-discovery:{self.chain.value}:{index}:{document.kind}"
            for index, document in enumerate(batch.documents)
        ]
        parsed: list[SourceStore] = getattr(self.connector, self.parse_method)(
            batch,
            references,
            area,
        )
        stores: list[PhysicalStore] = []
        contexts: list[GroceryContextEvidence] = []
        outside_city = 0
        excluded_contexts = 0
        for source in parsed:
            if not self.include(source):
                excluded_contexts += 1
                continue
            if (source.city or "").casefold().strip() != area.city.casefold().strip():
                outside_city += 1
                continue
            external_id = self.physical_external_id(source)
            if not external_id:
                excluded_contexts += 1
                continue
            stores.append(
                PhysicalStore(
                    id=stable_physical_store_id(self.chain, external_id),
                    chain=self.chain,
                    external_store_id=external_id,
                    external_store_aliases=tuple(self.physical_external_aliases(source)),
                    name=source.name,
                    address=source.address,
                    postal_code=source.postal_code,
                    city=source.city,
                    latitude=source.latitude,
                    longitude=source.longitude,
                    official_source=self.official_source,
                    discovered_at=observed_at,
                    last_seen_at=observed_at,
                    active=True,
                    lifecycle_state=PhysicalStoreLifecycleState.ACTIVE,
                )
            )
            context = _source_context_capability(source, observed_at=observed_at)
            if context is not None:
                contexts.append(context)
        unique = {store.id: store for store in stores}
        if len(unique) != len(stores):
            raise ValueError(f"{self.chain.value} official locator returned duplicate identities")
        if not unique and not self.allow_empty_result:
            raise OfficialStoreDiscoveryEmptyResult
        metrics = batch.transport
        city_outcome = self.empty_city_outcome if not unique else "stores_discovered"
        evidence = (
            f"bounded official locator completed; {city_outcome}"
            if not unique
            else "bounded official locator completed without access challenge"
        )
        return OfficialStoreDiscoveryResult(
            chain=self.chain,
            city=area.city,
            official_source=self.official_source,
            status=ConnectorStatus.HEALTHY,
            complete=True,
            stores=tuple(
                sorted(unique.values(), key=lambda store: (store.name.casefold(), store.id))
            ),
            contexts=tuple(sorted(contexts, key=lambda context: context.grocery_context_id)),
            request_count=metrics.request_count,
            http_error_count=metrics.http_error_count,
            rate_limit_count=metrics.rate_limit_count,
            source_scope_total=len(parsed),
            outside_city_count=outside_city,
            excluded_context_count=excluded_contexts,
            city_outcome=city_outcome,
            evidence=evidence,
        )

    async def aclose(self) -> None:
        await self.connector.aclose()


class FixtureOfficialStoreAdapter:
    """Offline adapter for the closed, sanitized official-store evidence fixture."""

    def __init__(self, chain: Chain, payload: Mapping[str, Any]) -> None:
        self.chain = chain
        self.payload = payload

    async def discover(
        self,
        area: GeographicArea,
        *,
        observed_at: datetime,
    ) -> OfficialStoreDiscoveryResult:
        city = str(self.payload.get("city") or "").strip()
        if city.casefold() != area.city.casefold():
            raise ValueError("fixture city does not match requested city")
        source = str(self.payload.get("official_source") or "").strip()
        rows = self.payload.get("stores")
        if not source or not isinstance(rows, list):
            raise ValueError("official-store fixture chain entry is incomplete")
        stores: list[PhysicalStore] = []
        contexts: list[GroceryContextEvidence] = []
        for row in rows:
            if not isinstance(row, dict):
                raise TypeError("official-store fixture record must be an object")
            external_id = str(row.get("external_store_id") or "").strip()
            secondary_external_id = str(row.get("secondary_external_store_id") or "").strip()
            stores.append(
                PhysicalStore(
                    id=stable_physical_store_id(self.chain, external_id),
                    chain=self.chain,
                    external_store_id=external_id,
                    external_store_aliases=(
                        (secondary_external_id,)
                        if secondary_external_id and secondary_external_id != external_id
                        else ()
                    ),
                    name=str(row.get("name") or ""),
                    address=row.get("address"),
                    postal_code=row.get("postal_code"),
                    city=row.get("city"),
                    latitude=row.get("latitude"),
                    longitude=row.get("longitude"),
                    official_source=source,
                    discovered_at=observed_at,
                    last_seen_at=observed_at,
                )
            )
            context = _source_context_capability(
                _fixture_source_store(self.chain, row),
                observed_at=observed_at,
            )
            if context is not None:
                contexts.append(context)
        declared = int(self.payload.get("source_scope_total", len(stores)))
        outside = int(self.payload.get("outside_city_count", 0))
        excluded = int(self.payload.get("excluded_context_count", 0))
        if declared != len(stores) + outside + excluded:
            raise ValueError("official-store fixture totals do not reconcile")
        city_outcome = str(
            self.payload.get("city_outcome")
            or (
                "no_lund_context"
                if self.chain == Chain.CITY_GROSS and not stores
                else "stores_discovered"
            )
        )
        return OfficialStoreDiscoveryResult(
            chain=self.chain,
            city=city,
            official_source=source,
            status=ConnectorStatus.HEALTHY,
            complete=True,
            stores=tuple(stores),
            contexts=tuple(contexts),
            source_scope_total=declared,
            outside_city_count=outside,
            excluded_context_count=excluded,
            city_outcome=city_outcome,
            evidence=f"sanitized real official-store fixture; {city_outcome}",
        )

    async def aclose(self) -> None:
        return None


class OfficialStoreDiscoveryService:
    """Independently discover/reconcile physical sites; never crawl catalogues."""

    def __init__(
        self,
        adapters: Mapping[Chain, OfficialStoreDiscoveryAdapter],
        *,
        session: Session | None = None,
    ) -> None:
        self.adapters = dict(adapters)
        self.session = session

    async def discover_city(
        self,
        city: str,
        *,
        chains: Sequence[Chain] | None = None,
        observed_at: datetime | None = None,
        contexts: Iterable[GroceryContextEvidence] = (),
        confirm_store_removals: bool = False,
    ) -> OfficialStoreDiscoveryReport:
        city = city.strip()
        if not city:
            raise ValueError("city must not be blank")
        timestamp = observed_at or datetime.now(tz=UTC)
        if timestamp.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        timestamp = timestamp.astimezone(UTC)
        requested = tuple(chains) if chains is not None else tuple(self.adapters)
        injected_contexts = tuple(contexts)
        persisted_contexts = (
            persisted_own_context_evidence(self.session, city) if self.session is not None else ()
        )
        results: dict[str, OfficialStoreDiscoveryResult] = {}
        errors: dict[str, str] = {}
        repository = PhysicalStoreRepository(self.session) if self.session is not None else None
        health_repository = (
            PhysicalStoreDiscoveryHealthRepository(self.session)
            if self.session is not None
            else None
        )
        link_repository = (
            StoreContextLinkRepository(self.session) if self.session is not None else None
        )
        links_verified = 0
        discovered_contexts: dict[tuple[str, str], GroceryContextEvidence] = {}
        for chain in requested:
            adapter = self.adapters.get(chain)
            previous_count = (
                len(repository.list_for_city(city, chain=chain, active_only=True))
                if repository is not None
                else 0
            )
            if adapter is None:
                errors[chain.value] = "official store-discovery adapter is not configured"
                if health_repository is not None:
                    health_repository.record(
                        chain=chain,
                        city=city,
                        status=ConnectorStatus.BROKEN,
                        complete=False,
                        discovered_count=0,
                        previous_count=previous_count,
                        observed_at=timestamp,
                        error_code=StoreDiscoveryErrorCode.MISSING_ADAPTER,
                    )
                continue
            result: OfficialStoreDiscoveryResult | None = None
            try:
                result = await adapter.discover(
                    GeographicArea(city=city),
                    observed_at=timestamp,
                )
                results[chain.value] = result
                for context in result.contexts:
                    discovered_contexts[
                        (context.source_provider.value, context.grocery_context_id)
                    ] = context
                if repository is None:
                    continue
                existing = repository.list_for_city(city, chain=chain, active_only=False)
                existing_active = [row for row in existing if row.is_active]
                count_collapsed = len(result.stores) < len(existing_active)
                if count_collapsed and (not confirm_store_removals or not result.stores):
                    # A single chain is one persistence unit. A conflict in a
                    # later row must not commit earlier rows from a broken run.
                    with self.session.begin_nested():
                        for store in result.stores:
                            repository.upsert(store, seen_at=timestamp)
                    degraded = result.model_copy(
                        update={
                            "status": ConnectorStatus.DEGRADED,
                            "complete": False,
                            "evidence": (
                                f"{result.evidence}; store_count_collapse_requires_confirmation"
                            ),
                        }
                    )
                    results[chain.value] = degraded
                    errors[chain.value] = "store_count_collapse_requires_confirmation"
                    if health_repository is not None:
                        health_repository.record(
                            chain=chain,
                            city=city,
                            status=ConnectorStatus.DEGRADED,
                            complete=False,
                            discovered_count=len(result.stores),
                            previous_count=previous_count,
                            observed_at=timestamp,
                            error_code=StoreDiscoveryErrorCode.STORE_COUNT_COLLAPSE,
                        )
                    continue
                if not result.stores:
                    if health_repository is not None:
                        health_repository.record(
                            chain=chain,
                            city=city,
                            status=result.status,
                            complete=result.complete,
                            discovered_count=0,
                            previous_count=previous_count,
                            observed_at=timestamp,
                            error_code=(
                                None
                                if result.status == ConnectorStatus.HEALTHY
                                else StoreDiscoveryErrorCode.DISCOVERY_FAILED
                            ),
                        )
                    continue
                chain_links_verified = 0
                with self.session.begin_nested():
                    for store in result.stores:
                        repository.upsert(store, seen_at=timestamp)
                        if link_repository is not None:
                            available_contexts = _merge_context_evidence(
                                result.contexts,
                                persisted_contexts,
                                injected_contexts,
                            )
                            for match in ExactStoreIdentityMatcher.physical_to_context(
                                store,
                                available_contexts,
                            ):
                                link_repository.upsert(
                                    match.as_link(store.id, verified_at=timestamp)
                                )
                                chain_links_verified += 1
                    repository.reconcile_discovery(
                        chain,
                        city=city,
                        seen_physical_store_ids={store.id for store in result.stores},
                        observed_at=timestamp,
                    )
                links_verified += chain_links_verified
                if health_repository is not None:
                    health_repository.record(
                        chain=chain,
                        city=city,
                        status=result.status,
                        complete=result.complete,
                        discovered_count=len(result.stores),
                        previous_count=previous_count,
                        observed_at=timestamp,
                        error_code=(
                            None
                            if result.status == ConnectorStatus.HEALTHY
                            else StoreDiscoveryErrorCode.DISCOVERY_FAILED
                        ),
                    )
            except Exception as exc:  # noqa: BLE001 - independent chain failure is the contract
                errors[chain.value] = _closed_discovery_error(exc)
                if result is not None:
                    results[chain.value] = result.model_copy(
                        update={
                            "status": ConnectorStatus.BROKEN,
                            "complete": False,
                            "evidence": (f"{result.evidence}; persistence_or_identity_failure"),
                        }
                    )
                if health_repository is not None:
                    error_code = _discovery_error_code(exc)
                    health_repository.record(
                        chain=chain,
                        city=city,
                        status=(
                            ConnectorStatus.DEGRADED
                            if error_code == StoreDiscoveryErrorCode.EMPTY_LOCATOR_RESULT
                            else ConnectorStatus.BROKEN
                        ),
                        complete=False,
                        discovered_count=len(result.stores) if result is not None else 0,
                        previous_count=previous_count,
                        observed_at=timestamp,
                        error_code=error_code,
                    )
        all_contexts = _merge_context_evidence(
            discovered_contexts.values(),
            persisted_contexts,
            injected_contexts,
        )
        return OfficialStoreDiscoveryReport(
            city=city,
            generated_at=timestamp,
            physical_stores=sum(len(result.stores) for result in results.values()),
            healthy_chains=sum(
                result.status == ConnectorStatus.HEALTHY and result.complete
                for result in results.values()
            ),
            own_contexts_considered=sum(
                context.source_provider == SourceProvider.OWN for context in all_contexts
            ),
            external_contexts_considered=sum(
                context.source_provider != SourceProvider.OWN for context in all_contexts
            ),
            context_links_verified=links_verified,
            results=results,
            errors=errors,
        )

    async def aclose(self) -> None:
        for adapter in self.adapters.values():
            await adapter.aclose()


def live_official_store_adapters(
    chains: Iterable[Chain] | None = None,
) -> dict[Chain, OfficialStoreDiscoveryAdapter]:
    """Build only the requested bounded adapters (all six by default)."""

    requested = set(chains) if chains is not None else set(Chain)
    adapters: dict[Chain, OfficialStoreDiscoveryAdapter] = {}
    if Chain.WILLYS in requested:
        adapters[Chain.WILLYS] = SourceStoreOfficialAdapter(
            WillysConnector(),
            official_source=_OFFICIAL_SOURCES[Chain.WILLYS],
        )
    if Chain.HEMKOP in requested:
        adapters[Chain.HEMKOP] = SourceStoreOfficialAdapter(
            HemkopConnector.for_bounded_discovery(),
            official_source=_OFFICIAL_SOURCES[Chain.HEMKOP],
        )
    if Chain.ICA in requested:
        adapters[Chain.ICA] = SourceStoreOfficialAdapter(
            IcaConnector(),
            official_source=_OFFICIAL_SOURCES[Chain.ICA],
            fetch_method="fetch_physical_stores",
            parse_method="parse_physical_stores",
            physical_external_aliases=lambda store: tuple(
                value
                for value in (str(store.source_fields.get("store_id") or "").strip(),)
                if value and value != store.external_id
            ),
        )
    if Chain.COOP in requested:
        adapters[Chain.COOP] = SourceStoreOfficialAdapter(
            CoopConnector(),
            official_source=_OFFICIAL_SOURCES[Chain.COOP],
            fetch_method="fetch_physical_stores",
            parse_method="parse_physical_stores",
            physical_external_aliases=lambda store: tuple(
                value
                for value in (str(store.source_fields.get("ledger_account_number") or "").strip(),)
                if value and value != store.external_id
            ),
        )
    if Chain.LIDL in requested:
        adapters[Chain.LIDL] = SourceStoreOfficialAdapter(
            LidlConnector.for_bounded_discovery(),
            official_source=_OFFICIAL_SOURCES[Chain.LIDL],
            include=lambda store: store.price_context_type == PriceContextType.PHYSICAL_STORE,
        )
    if Chain.CITY_GROSS in requested:
        adapters[Chain.CITY_GROSS] = SourceStoreOfficialAdapter(
            CityGrossConnector.for_bounded_discovery(),
            official_source=_OFFICIAL_SOURCES[Chain.CITY_GROSS],
            physical_external_id=lambda store: store.physical_store_external_id,
            allow_empty_result=True,
            empty_city_outcome="no_lund_context",
        )
    unknown = requested - set(Chain)
    if unknown:
        raise ValueError("unknown official store-discovery chain")
    return adapters


def fixture_official_store_adapters(
    path: Path,
) -> dict[Chain, OfficialStoreDiscoveryAdapter]:
    root = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(root, dict) or root.get("schema") != "official-store-discovery-v1":
        raise ValueError("official-store fixture schema changed")
    chains = root.get("chains")
    if not isinstance(chains, dict):
        raise TypeError("official-store fixture lacks chains")
    return {
        chain: FixtureOfficialStoreAdapter(chain, chains[chain.value])
        for chain in Chain
        if isinstance(chains.get(chain.value), dict)
    }


__all__ = [
    "FixtureOfficialStoreAdapter",
    "OfficialStoreDiscoveryAdapter",
    "OfficialStoreDiscoveryReport",
    "OfficialStoreDiscoveryResult",
    "OfficialStoreDiscoveryService",
    "SourceStoreOfficialAdapter",
    "fixture_official_store_adapters",
    "live_official_store_adapters",
    "persisted_own_context_evidence",
    "stable_physical_store_id",
]
