"""Build a closed production PriceUniverse from refreshed local data.

This module is deliberately an admin/refresh boundary.  It reads one explicit
SQLite database through an immutable, query-only connection, serves that data
to :class:`OwnGroceryPriceProvider` through an in-process ASGI transport, and
optionally combines it with an already-sanitized frozen external cache.  No
socket access is permitted while the universe is materialised.

The resulting file is a *candidate* artifact.  This service never calls
``PreparedUniverseArtifactStore`` and therefore never changes the active
production manifest; validation and activation belong to the caller.
"""

from __future__ import annotations

import json
import re
import socket
import sqlite3
from collections import Counter
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
from math import isfinite
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

import httpx
from app.config import Settings
from app.models import Product, Store
from app.providers import FederatedGroceryPriceProvider, ProviderBinding
from app.providers.base import GroceryPriceProvider
from app.providers.exact_identity_bridge import load_exact_identity_bridge
from app.providers.own import OwnGroceryPriceProvider
from app.services.meal_plan_optimizer import MealPlanService
from app.services.performance_trace import activate_performance_trace
from app.services.price_universe_runtime import (
    PreparedPriceUniverseArtifact,
    PreparedPriceUniverseManager,
)
from fastapi import FastAPI
from sqlalchemy.pool import NullPool

from grocery_data.app.api.catalog import router as catalog_router
from grocery_data.app.api.registry import router as registry_router
from grocery_data.app.domain import Chain, CoverageLevel, is_complete_catalog_coverage
from grocery_data.app.domain.source_strategy import (
    CHAIN_SOURCE_STRATEGIES,
    OWN_CATALOG,
    PRIMAT_CATALOG,
    SourceProvider,
    source_strategy_for,
)
from grocery_data.app.storage import create_database_engine, create_session_factory

from .primat_frozen_cache_collect import load_eligible_primat_contexts
from .primat_phase_c_export import FrozenExternalCacheBundle

_FORBIDDEN_CACHE_KEY = re.compile(
    r"(?:authorization|cookie|set[_-]?cookie|api[_-]?key|access[_-]?token|"
    r"refresh[_-]?token|client[_-]?secret|session|clearance)",
    flags=re.IGNORECASE,
)
class NetworkAccessBlockedError(RuntimeError):
    """A PriceUniverse build attempted to leave its local process."""


class _CountingASGITransport(httpx.AsyncBaseTransport):
    """Count internal API calls without changing the ordinary OWN adapter."""

    def __init__(self, application: FastAPI) -> None:
        self._inner = httpx.ASGITransport(app=application)
        self.requests = 0
        self.statuses: Counter[str] = Counter()
        self.methods: Counter[str] = Counter()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests += 1
        self.methods[request.method] += 1
        response = await self._inner.handle_async_request(request)
        self.statuses[str(response.status_code)] += 1
        return response

    async def aclose(self) -> None:
        await self._inner.aclose()

    def report(self) -> dict[str, object]:
        return {
            "requests": self.requests,
            "methods": dict(sorted(self.methods.items())),
            "statuses": dict(sorted(self.statuses.items())),
            "network_requests": 0,
        }


class _FrozenExternalCacheProvider(GroceryPriceProvider):
    """Read-only provider over one validated credential-free cache bundle."""

    source_name = "primat-frozen"
    attribution_text = "Fryst credential-free licensierad kandidatyta"

    def __init__(
        self,
        bundle: FrozenExternalCacheBundle,
        *,
        postal_code: str,
    ) -> None:
        super().__init__(use_member_prices=False)
        self._postal_code = postal_code
        self._stores = tuple(bundle.stores)
        self._products = tuple(bundle.products)
        self._calls: Counter[str] = Counter()

    async def find_stores(self, postal_code: str) -> list[Store]:
        self._calls["find_stores"] += 1
        return (
            [store.model_copy(deep=True) for store in self._stores]
            if _postal_code(postal_code) == self._postal_code
            else []
        )

    async def search_products(self, query: str, store_ids: list[str]) -> list[Product]:
        del query
        self._calls["search_products"] += 1
        allowed = set(store_ids)
        # ProductMatcher remains the semantic authority.  Returning the closed
        # bounded cache prevents provider-query aliases from dropping valid
        # products during refresh-time materialisation.
        return [
            product.model_copy(deep=True)
            for product in self._products
            if product.store_id in allowed
        ]

    async def get_store_products(self, store_id: str) -> list[Product]:
        self._calls["get_store_products"] += 1
        return [
            product.model_copy(deep=True)
            for product in self._products
            if product.store_id == store_id
        ]

    async def get_offers(self, store_id: str) -> list[Product]:
        self._calls["get_offers"] += 1
        return [
            product.model_copy(deep=True)
            for product in self._products
            if product.store_id == store_id and product.active_offers()
        ]

    def report(self) -> dict[str, object]:
        return {
            "stores": len(self._stores),
            "products": len(self._products),
            "calls": dict(sorted(self._calls.items())),
            "network_requests": 0,
        }

    @property
    def identity_products(self) -> tuple[Product, ...]:
        """Return immutable build inputs for offline exact-identity indexing."""

        return tuple(product.model_copy(deep=True) for product in self._products)


def _postal_code(value: str) -> str:
    digits = "".join(character for character in value if character.isdigit())
    if len(digits) != 5:
        raise ValueError("postal_code must contain exactly five digits")
    return digits


def _city(value: str) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise ValueError("city is required")
    return normalized


def _file_state(path: Path) -> tuple[object, ...]:
    """Return a cheap mutation guard for an immutable build input."""

    resolved = path.resolve(strict=True)
    stat = resolved.stat()
    sidecars: list[tuple[str, bool, int, int]] = []
    for suffix in ("-journal", "-shm", "-wal"):
        sidecar = resolved.with_name(resolved.name + suffix)
        if sidecar.exists():
            sidecar_stat = sidecar.stat()
            sidecars.append(
                (suffix, True, sidecar_stat.st_size, sidecar_stat.st_mtime_ns)
            )
        else:
            sidecars.append((suffix, False, 0, 0))
    return (
        stat.st_size,
        stat.st_mtime_ns,
        getattr(stat, "st_ino", 0),
        tuple(sidecars),
    )


def _database_columns(path: Path, table: str) -> frozenset[str]:
    connection = sqlite3.connect(
        f"file:{path.resolve(strict=True).as_posix()}?mode=ro&immutable=1",
        uri=True,
    )
    try:
        connection.execute("PRAGMA query_only=ON")
        return frozenset(str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})"))
    finally:
        connection.close()


def _read_only_engine(database: Path) -> tuple[Any, Any, bool]:
    """Create an immutable SQLite-backed session factory for the ASGI API."""

    resolved = database.resolve(strict=True)
    if not resolved.is_file():
        raise ValueError("database must be a regular SQLite file")
    columns = _database_columns(resolved, "stores")
    if not columns:
        raise ValueError("database lacks the stores table")
    compatibility_needed = not {
        "price_context_type",
        "physical_store_external_id",
    }.issubset(columns)

    def creator() -> sqlite3.Connection:
        connection = sqlite3.connect(
            f"file:{resolved.as_posix()}?mode=ro&immutable=1",
            uri=True,
            check_same_thread=False,
        )
        if compatibility_needed:
            connection.execute(
                """
                CREATE TEMP VIEW stores AS
                SELECT *,
                       NULL AS price_context_type,
                       NULL AS physical_store_external_id
                FROM main.stores
                """
            )
        connection.execute("PRAGMA query_only=ON")
        return connection

    engine = create_database_engine(
        "sqlite+pysqlite://",
        creator=creator,
        poolclass=NullPool,
    )
    return engine, create_session_factory(engine), compatibility_needed


def _read_only_app(session_factory: Any) -> FastAPI:
    application = FastAPI(
        title="Immutable production PriceUniverse source",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    application.state.session_factory = session_factory
    application.include_router(catalog_router)
    application.include_router(registry_router)
    return application


@contextmanager
def _network_disabled() -> Iterator[dict[str, int]]:
    """Deny DNS and socket connection attempts for the complete build phase."""

    attempts = {"count": 0}
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_create_connection = socket.create_connection
    original_getaddrinfo = socket.getaddrinfo

    def denied(*_args: object, **_kwargs: object) -> Any:
        attempts["count"] += 1
        raise NetworkAccessBlockedError("network disabled during PriceUniverse build")

    socket.socket.connect = denied  # type: ignore[method-assign]
    socket.socket.connect_ex = denied  # type: ignore[method-assign]
    socket.create_connection = denied  # type: ignore[assignment]
    socket.getaddrinfo = denied  # type: ignore[assignment]
    try:
        yield attempts
    finally:
        socket.socket.connect = original_connect  # type: ignore[method-assign]
        socket.socket.connect_ex = original_connect_ex  # type: ignore[method-assign]
        socket.create_connection = original_create_connection
        socket.getaddrinfo = original_getaddrinfo


def _assert_sanitized(value: object, *, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            key_text = str(key)
            if _FORBIDDEN_CACHE_KEY.search(key_text):
                raise ValueError(f"external cache contains a forbidden field at {path}")
            _assert_sanitized(nested, path=f"{path}.{key_text}")
    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            _assert_sanitized(nested, path=f"{path}[{index}]")
    elif isinstance(value, str) and "bearer " in value.casefold():
        raise ValueError(f"external cache contains a credential-shaped value at {path}")


def _aware(value: datetime, *, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return value.astimezone(UTC)


def _fresh(value: datetime, *, now: datetime, max_age_hours: float, field: str) -> None:
    observed = _aware(value, field=field)
    age = (now - observed).total_seconds() / 3600
    if age < -1:
        raise ValueError(f"{field} is in the future")


def _chain(value: str | None) -> Chain:
    try:
        return Chain(str(value or "").casefold().strip())
    except ValueError as exc:
        raise ValueError("external cache contains an unsupported chain") from exc


def _coverage(store: Store) -> CoverageLevel:
    provenance = store.source_provenance
    raw = store.coverage or store.tier or (provenance.coverage if provenance else None)
    try:
        coverage = CoverageLevel(str(raw or "").casefold())
    except ValueError as exc:
        raise ValueError("external cache store has invalid coverage") from exc
    if not is_complete_catalog_coverage(coverage):
        raise ValueError("external cache store is not basket-complete")
    return coverage


def _identity_values(store: Store) -> frozenset[str]:
    provenance = store.source_provenance
    return frozenset(
        str(value).strip()
        for value in (
            store.store_id,
            store.source_store_id,
            provenance.provider_store_id if provenance is not None else None,
        )
        if value is not None and str(value).strip()
    )


def _context_matches(store: Store, provider_context_id: str, provider_store_id: str) -> bool:
    identities = _identity_values(store)
    expected = {provider_context_id, provider_store_id}
    return any(
        expected_id == identity or expected_id.endswith(f":{identity}")
        for expected_id in expected
        for identity in identities
    )


def _load_external_cache(
    path: Path,
    *,
    database: Path,
    city: str,
    postal_code: str,
    max_age_hours: float,
    now: datetime,
) -> tuple[_FrozenExternalCacheProvider, frozenset[Chain]]:
    payload = json.loads(path.resolve(strict=True).read_text(encoding="utf-8"))
    _assert_sanitized(payload)
    bundle = FrozenExternalCacheBundle.model_validate(payload)
    if bundle.postal_code != postal_code:
        raise ValueError("external cache postal_code does not match the requested scope")
    _fresh(
        bundle.captured_at,
        now=now,
        max_age_hours=max_age_hours,
        field="external cache captured_at",
    )
    if not bundle.stores or not bundle.products:
        raise ValueError("external cache must contain stores and products")

    store_ids: set[str] = set()
    store_chains: dict[str, Chain] = {}
    store_snapshots: dict[str, str] = {}
    for store in bundle.stores:
        if store.store_id in store_ids:
            raise ValueError("external cache contains duplicate store IDs")
        store_ids.add(store.store_id)
        chain = _chain(store.chain)
        if PRIMAT_CATALOG not in CHAIN_SOURCE_STRATEGIES[chain].configured_catalog_sources:
            raise ValueError("external cache chain is not configured for Primat")
        _coverage(store)
        provenance = store.source_provenance
        if (
            provenance is None
            or provenance.source_provider != "primat"
            or provenance.source_channel != "catalog"
            or not provenance.source_snapshot_id
        ):
            raise ValueError("external cache store lacks Primat catalog provenance")
        _fresh(
            provenance.source_observed_at,
            now=now,
            max_age_hours=max_age_hours,
            field="external store observation",
        )
        store_chains[store.store_id] = chain
        store_snapshots[store.store_id] = provenance.source_snapshot_id

    configured_primat_chains = frozenset(
        chain
        for chain in Chain
        if PRIMAT_CATALOG in CHAIN_SOURCE_STRATEGIES[chain].configured_catalog_sources
    )
    eligible_candidates = load_eligible_primat_contexts(
        database,
        city=city,
        max_age_hours=max_age_hours,
        now=now,
        chains=configured_primat_chains,
    )
    eligible = tuple(
        row
        for row in eligible_candidates
        if source_strategy_for(
            row.chain,
            context_id=row.provider_context_id,
        ).basket_primary.provider
        is SourceProvider.PRIMAT
    )
    matched_context_ids: set[str] = set()
    for store in bundle.stores:
        chain = store_chains[store.store_id]
        matches = [
            row
            for row in eligible
            if row.chain is chain
            and _context_matches(store, row.provider_context_id, row.provider_store_id)
        ]
        if len(matches) != 1:
            raise ValueError("external cache store lacks one exact fresh persisted context link")
        match = matches[0]
        provenance = store.source_provenance
        assert provenance is not None
        if match.snapshot_id != provenance.source_snapshot_id:
            raise ValueError("external cache snapshot does not match the active context link")
        matched_context_ids.add(match.provider_context_id)
    eligible_context_ids = {row.provider_context_id for row in eligible}
    if matched_context_ids != eligible_context_ids:
        raise ValueError("external cache does not equal the complete eligible context scope")

    chains = frozenset(store_chains.values())

    product_keys: set[tuple[str, str]] = set()
    for product in bundle.products:
        key = (product.store_id, product.product_id)
        if key in product_keys:
            raise ValueError("external cache contains duplicate product identities")
        product_keys.add(key)
        if product.store_id not in store_ids:
            raise ValueError("external cache product belongs to an unknown store")
        if product.chain is None or _chain(product.chain) is not store_chains[product.store_id]:
            raise ValueError("external cache product chain does not match its store")
        provenance = product.source_provenance
        if (
            provenance is None
            or provenance.source_provider != "primat"
            or provenance.source_channel != "catalog"
            or provenance.source_snapshot_id != store_snapshots[product.store_id]
        ):
            raise ValueError("external cache product lacks matching Primat catalog provenance")
        _fresh(
            provenance.source_observed_at,
            now=now,
            max_age_hours=max_age_hours,
            field="external product observation",
        )

    return (
        _FrozenExternalCacheProvider(bundle, postal_code=postal_code),
        chains,
    )


def _build_settings() -> Settings:
    """Return the quality policy used by the production optimized path."""

    return Settings(
        price_provider="federated",
        meal_plan_strategy="optimized",
        openai_api_key=None,
        allow_mock_fallback=False,
        allow_medium_semantic_matches=False,
        allow_estimated_quantities=True,
        allow_unknown_quantities=False,
        allow_unknown_sale_model=False,
    )


async def build_city_price_universe(
    database: Path,
    city: str,
    postal_code: str,
    external_cache: Path | None,
    output: Path,
    max_price_age_hours: float,
    ica_offer_store_ids: frozenset[str] = frozenset(),
    ica_offer_database: Path | None = None,
    ica_municipal_stores: dict | None = None,
    hemkop_offer_database: Path | None = None,
    hemkop_municipal_stores: dict | None = None,
    coop_offer_database: Path | None = None,
    coop_municipality_inventory: dict | None = None,
    coop_offer_sources: tuple | list = (),
    coop_offer_source_errors: tuple | list = (),
    coop_syd_base_inventory: dict | None = None,
    lidl_municipal_enabled: bool = False,
    lidl_sources: tuple | list = (),
    lidl_source_errors: tuple | list = (),
    willys_flyer_enabled: bool = False,
    willys_flyer_sources: tuple | list = (),
    willys_flyer_source_errors: tuple | list = (),
    citygross_municipal_enabled: bool = False,
    citygross_sources: tuple | list = (),
    citygross_source_errors: tuple | list = (),
) -> dict[str, object]:
    """Build and atomically write one validated, inactive candidate artifact.

    ``external_cache=None`` produces an OWN-only universe.  Supplying a cache
    uses the central chain strategy to merge only exact, fresh, persisted
    Primat contexts.  Neither mode grants fallback permission.
    """

    started = perf_counter()
    normalized_city = _city(city)
    normalized_postal = _postal_code(postal_code)
    if not isfinite(max_price_age_hours) or max_price_age_hours <= 0:
        raise ValueError("max_price_age_hours must be finite and positive")
    database = database.resolve(strict=True)
    if not database.is_file():
        raise ValueError("database must be a regular SQLite file")
    external_cache = external_cache.resolve(strict=True) if external_cache is not None else None
    if external_cache is not None and not external_cache.is_file():
        raise ValueError("external_cache must be a regular file")
    output = output.resolve()
    if output.exists() and not output.is_file():
        raise ValueError("output must be a regular file path")
    if output == database or output == external_cache:
        raise ValueError("output must not overwrite a build input")

    now = datetime.now(tz=UTC)
    database_before = _file_state(database)
    external_before = _file_state(external_cache) if external_cache is not None else None
    setup_started = perf_counter()
    frozen: _FrozenExternalCacheProvider | None = None
    external_chains: frozenset[Chain] = frozenset()
    if external_cache is not None:
        frozen, external_chains = _load_external_cache(
            external_cache,
            database=database,
            city=normalized_city,
            postal_code=normalized_postal,
            max_age_hours=max_price_age_hours,
            now=now,
        )
    engine, session_factory, compatibility_view = _read_only_engine(database)
    transport = _CountingASGITransport(_read_only_app(session_factory))
    client = httpx.AsyncClient(
        transport=transport,
        base_url="http://immutable-grocery-data.local/",
        timeout=60.0,
    )
    from grocery_data.app.services.willys_municipal_scope import approved_snapshot_stores

    municipal_willys_stores = approved_snapshot_stores(database, normalized_postal)
    from grocery_data.app.services.hemkop_municipal_job import catalog_stores

    own = OwnGroceryPriceProvider(
        base_url="http://immutable-grocery-data.local",
        max_age_hours=max_price_age_hours,
        include_offers_only=bool(ica_offer_store_ids),
        include_conditional_offer_products=bool(ica_offer_store_ids),
        use_member_prices=False,
        client=client,
        municipal_willys_stores=municipal_willys_stores,
        municipal_hemkop_stores=catalog_stores(normalized_city),
    )
    bindings: list[ProviderBinding] = []
    own_chains = frozenset(
        chain
        for chain, strategy in CHAIN_SOURCE_STRATEGIES.items()
        if OWN_CATALOG in strategy.configured_catalog_sources
    )
    if own_chains:
        bindings.append(
            ProviderBinding(
                source=OWN_CATALOG,
                provider=own,
                chains=own_chains,
            )
        )

    if frozen is not None:
        bindings.append(
            ProviderBinding(
                source=PRIMAT_CATALOG,
                provider=frozen,
                chains=external_chains,
            )
        )
    federated_provider = FederatedGroceryPriceProvider(
        bindings,
        strategies=CHAIN_SOURCE_STRATEGIES,
        allow_fallback=False,
        own_sources_only=external_cache is None,
        max_price_age_hours=max_price_age_hours,
        use_member_prices=False,
        memberships={chain: False for chain in Chain},
    )
    identity_bridge = load_exact_identity_bridge(
        database,
        external_products=(frozen.identity_products if frozen is not None else ()),
        # The source-bound row-approved channel replaces legacy ICA imports.
        # Never attach an older copy of the same campaign with a different cap ID.
        exclude_offer_chains=frozenset({Chain.ICA}) if ica_offer_store_ids else frozenset(),
    )
    provider = identity_bridge.bind(federated_provider)
    offer_engine = offer_client = None
    if ica_offer_store_ids:
        from app.providers.ica_area_offers import IcaAreaOfferProvider
        offer_database = ica_offer_database or database
        offer_own = own
        offer_setup_error = None
        if ica_offer_database is not None and ica_offer_database.is_file():
            try:
                offer_engine, offer_sessions, _ = _read_only_engine(ica_offer_database)
                offer_client = httpx.AsyncClient(transport=_CountingASGITransport(_read_only_app(offer_sessions)),
                                                base_url="http://optional-ica-offers.local/")
                offer_own = OwnGroceryPriceProvider("http://optional-ica-offers.local", client=offer_client,
                                                   include_offers_only=True, include_conditional_offer_products=True,
                                                   max_age_hours=max_price_age_hours)
            except (OSError, ValueError, sqlite3.Error) as exc:
                offer_setup_error = type(exc).__name__
        provider = IcaAreaOfferProvider(provider, offer_own, database=offer_database,
                                       city=normalized_city, account_ids=ica_offer_store_ids,
                                       municipal_stores=ica_municipal_stores)
        if offer_setup_error:
            provider.evidence = {}
            provider.diagnostics["setup"] = {"status": "error", "error": offer_setup_error}
    coop_resources = []
    if hemkop_offer_database and hemkop_municipal_stores:
        from app.providers.hemkop_municipality_offers import HemkopMunicipalityOfferProvider
        hemkop_own, hemkop_setup_error = own, None
        try:
            hemkop_engine, hemkop_sessions, _ = _read_only_engine(hemkop_offer_database)
            hemkop_client = httpx.AsyncClient(transport=_CountingASGITransport(_read_only_app(hemkop_sessions)),
                                            base_url='http://optional-hemkop-offers.local/')
            hemkop_own = OwnGroceryPriceProvider('http://optional-hemkop-offers.local', client=hemkop_client,
                include_offers_only=True, include_conditional_offer_products=True, max_age_hours=max_price_age_hours)
            coop_resources.append((hemkop_client, hemkop_engine))
        except (OSError, ValueError, sqlite3.Error) as exc:
            hemkop_setup_error = type(exc).__name__
        provider = HemkopMunicipalityOfferProvider(provider, hemkop_own, database=hemkop_offer_database,
            city=normalized_city, account_ids=frozenset(hemkop_municipal_stores), municipal_stores=hemkop_municipal_stores)
        if hemkop_setup_error:
            provider.evidence = {}
            provider.diagnostics['setup'] = {'status': 'error', 'error': hemkop_setup_error}
    coop_sources = list(coop_offer_sources)
    if coop_municipality_inventory is not None:
        coop_sources.append({"database": coop_offer_database, "inventory": coop_municipality_inventory})
    for source in coop_sources:
        from app.providers.coop_municipality_offers import CoopMunicipalityOfferProvider

        try:
            if source["inventory"]["area"]["city"].casefold() != normalized_city.casefold():
                raise ValueError("Coop source municipality does not match the build")
            if source["database"] is None:
                raise ValueError("explicit approved Coop offers database required")
            coop_engine, coop_sessions, _ = _read_only_engine(source["database"])
            coop_client = httpx.AsyncClient(transport=_CountingASGITransport(_read_only_app(coop_sessions)),
                                           base_url="http://optional-coop-offers.local/")
            coop_resources.append((coop_client, coop_engine))
            coop_own = OwnGroceryPriceProvider("http://optional-coop-offers.local", client=coop_client,
                include_offers_only=True, include_conditional_offer_products=True,
                max_age_hours=max_price_age_hours, use_member_prices=False)
            provider = CoopMunicipalityOfferProvider(provider, coop_own, database=source["database"],
                inventory=source["inventory"], include_xtra=source.get("include_xtra", False))
        except (OSError, ValueError, sqlite3.Error) as exc:
            provider.coop_setup_error = type(exc).__name__
    citygross_resources, citygross_loaded = [], []
    citygross_errors = list(citygross_source_errors)
    if citygross_municipal_enabled:
        from app.providers.citygross_municipality import CityGrossMunicipalityProvider
        for source in citygross_sources:
            try:
                cg_engine, cg_sessions, _ = _read_only_engine(source["database"])
                cg_client = httpx.AsyncClient(
                    transport=_CountingASGITransport(_read_only_app(cg_sessions)),
                    base_url="http://municipal-citygross.local/")
                citygross_resources.append((cg_client, cg_engine))
                cg_own = OwnGroceryPriceProvider("http://municipal-citygross.local", client=cg_client,
                    include_offers_only=True, include_conditional_offer_products=True,
                    max_age_hours=max_price_age_hours, use_member_prices=False)
                citygross_loaded.append({**source, "own": cg_own})
            except (OSError, ValueError, sqlite3.Error) as exc:
                citygross_errors.append({"status": "source_setup_failed", "error_type": type(exc).__name__})
        provider = CityGrossMunicipalityProvider(provider, citygross_loaded,
                                               allow_empty_base=external_cache is None)
    lidl_resources, lidl_loaded = [], []
    lidl_errors = list(lidl_source_errors)
    if lidl_municipal_enabled:
        from app.providers.lidl_municipality import LidlMunicipalityProvider
        for source in lidl_sources:
            try:
                ld_engine, ld_sessions, _ = _read_only_engine(source["database"])
                ld_client = httpx.AsyncClient(
                    transport=_CountingASGITransport(_read_only_app(ld_sessions)),
                    base_url="http://municipal-lidl.local/")
                lidl_resources.append((ld_client, ld_engine))
                ld_own = OwnGroceryPriceProvider("http://municipal-lidl.local", client=ld_client,
                    include_offers_only=True, include_conditional_offer_products=True,
                    max_age_hours=max_price_age_hours, use_member_prices=False)
                lidl_loaded.append({**source, "own": ld_own})
            except (OSError, ValueError, sqlite3.Error) as exc:
                lidl_errors.append({"status": "source_setup_failed", "error_type": type(exc).__name__})
        provider = LidlMunicipalityProvider(provider, lidl_loaded,
                                               allow_empty_base=external_cache is None)
    willys_flyer_resources, willys_flyer_loaded = [], []
    willys_flyer_errors = list(willys_flyer_source_errors)
    if willys_flyer_enabled:
        from app.providers.willys_flyers import WillysFlyerProvider
        for source in willys_flyer_sources:
            try:
                wf_engine, wf_sessions, _ = _read_only_engine(source["database"])
                wf_client = httpx.AsyncClient(
                    transport=_CountingASGITransport(_read_only_app(wf_sessions)),
                    base_url="http://municipal-willys-flyer.local/")
                willys_flyer_resources.append((wf_client, wf_engine))
                wf_own = OwnGroceryPriceProvider("http://municipal-willys-flyer.local", client=wf_client,
                    include_offers_only=True, include_conditional_offer_products=True,
                    max_age_hours=max_price_age_hours, use_member_prices=False)
                willys_flyer_loaded.append({**source, "own": wf_own})
            except (OSError, ValueError, sqlite3.Error) as exc:
                willys_flyer_errors.append({"status": "source_setup_failed", "error_type": type(exc).__name__})
        provider = WillysFlyerProvider(provider, willys_flyer_loaded,
                                               allow_empty_base=external_cache is None)
    if coop_syd_base_inventory is not None:
        from app.providers.coop_syd_base import CoopSydBaseProvider

        provider = CoopSydBaseProvider(provider, own, inventory=coop_syd_base_inventory)
    setup_ms = (perf_counter() - setup_started) * 1000

    staging = output.with_name(f".{output.name}.{uuid4().hex}.candidate")
    staging_temporary = staging.with_name(staging.name + ".tmp")
    prepared = None
    network_attempts = 0
    build_ms = serialization_ms = validation_ms = 0.0
    performance = None
    try:
        service = MealPlanService(_build_settings())
        manager = PreparedPriceUniverseManager()
        from app.services.price_universe_runtime import SOURCE_STRATEGY_VERSION

        strategy_version = SOURCE_STRATEGY_VERSION
        if coop_syd_base_inventory is not None:
            from app.providers.coop_syd_base import assigned_stores

            from grocery_data.app.domain.coop_syd_base import POLICY_VERSION

            if assigned_stores(coop_syd_base_inventory):
                strategy_version += "+" + POLICY_VERSION
        build_started = perf_counter()
        with activate_performance_trace() as trace, _network_disabled() as attempts:
            try:
                prepared = await manager.build_and_activate(
                    city=normalized_city,
                    postal_codes=(normalized_postal,),
                    provider=provider,
                    memberships={chain.value: False for chain in Chain},
                    selector=service.economic_selector,
                    built_at=now,
                    source_strategy_version=strategy_version,
                )
            finally:
                network_attempts = attempts["count"]
        build_ms = (perf_counter() - build_started) * 1000
        performance = trace.snapshot()
        if network_attempts:
            raise NetworkAccessBlockedError("PriceUniverse build attempted live network access")
        if municipal_willys_stores is not None:
            represented = {s.source_store_id for s in prepared.stores if s.chain.casefold() == "willys"
                           and s.price_context_type == "online_store"}
            if represented != set(municipal_willys_stores):
                raise RuntimeError("municipal Willys source contexts missing from prepared universe")
        if database_before != _file_state(database):
            raise RuntimeError("database changed during immutable PriceUniverse build")
        if external_cache is not None and external_before != _file_state(external_cache):
            raise RuntimeError("external cache changed during PriceUniverse build")

        serialization_started = perf_counter()
        PreparedPriceUniverseManager.write_artifact(prepared, staging)
        serialization_ms = (perf_counter() - serialization_started) * 1000

        validation_started = perf_counter()
        artifact = PreparedPriceUniverseArtifact.model_validate_json(staging.read_bytes())
        restored = artifact.restore()
        if restored.universe.universe_id != prepared.universe.universe_id:
            raise RuntimeError("serialized PriceUniverse identity changed during validation")
        if len(restored.universe.products) != len(prepared.universe.products):
            raise RuntimeError("serialized PriceUniverse product count changed during validation")
        validation_ms = (perf_counter() - validation_started) * 1000

        if database_before != _file_state(database):
            raise RuntimeError("database changed before PriceUniverse artifact publication")
        if external_cache is not None and external_before != _file_state(external_cache):
            raise RuntimeError("external cache changed before PriceUniverse artifact publication")
        output.parent.mkdir(parents=True, exist_ok=True)
        staging.replace(output)

        status = prepared.status(now=now)
        diagnostics = [
            row.model_dump(mode="json")
            for row in (
                *federated_provider.diagnostics,
                *federated_provider.context_diagnostics,
            )
        ]
        return {
            "status": "PASS",
            "build": "production_price_universe",
            "persistent_activation": False,
            "mode": "federated" if external_cache is not None else "own_only",
            "city": normalized_city,
            "postal_code": normalized_postal,
            "price_universe_id": prepared.universe.universe_id,
            "built_at": prepared.universe.built_at,
            "snapshot_ids": list(prepared.universe.key.snapshot_ids),
            "stores": len(prepared.stores),
            "raw_products": prepared.universe.stats.raw_products,
            "eligible_products": prepared.universe.stats.eligible_products,
            "canonical_mappings": prepared.universe.stats.canonical_mappings,
            "post_pruning_products": prepared.universe.stats.post_pruning_products,
            "exact_menu_candidates": sum(
                len(rows) for rows in prepared.economic_pool.candidates_by_name.values()
            ),
            "oldest_price_age_hours": status.oldest_price_age_hours,
            "artifact": {
                "file": output.name,
                "bytes": output.stat().st_size,
                "schema_version": artifact.schema_version,
                "validated": True,
            },
            "timing_ms": {
                "setup": round(setup_ms, 3),
                "build": round(build_ms, 3),
                "serialization": round(serialization_ms, 3),
                "validation_load": round(validation_ms, 3),
                "total": round((perf_counter() - started) * 1000, 3),
                **performance.timings_ms,
            },
            "operation_counters": performance.operation_counters,
            "provider_metrics": {
                "own_asgi": transport.report(),
                "external_cache": frozen.report() if frozen is not None else None,
                "exact_identity_bridge": provider.report(),
                "source_resolution": diagnostics,
            },
            "network_attempts": network_attempts,
            "coop_optional_setup_error": getattr(provider, "coop_setup_error", None),
            "coop_source_errors": list(coop_offer_source_errors),
            "citygross_source_errors": citygross_errors,
            "lidl_source_errors": lidl_errors,
            "willys_flyer_source_errors": willys_flyer_errors,
            "database_read_only": True,
            "database_unchanged": database_before == _file_state(database),
            "external_cache_unchanged": (
                None
                if external_cache is None
                else external_before == _file_state(external_cache)
            ),
            "legacy_compatibility_view": compatibility_view,
        }
    finally:
        await provider.aclose()
        await client.aclose()
        if offer_client is not None:
            await offer_client.aclose()
        if offer_engine is not None:
            offer_engine.dispose()
        for ld_client, ld_engine in lidl_resources:
            await ld_client.aclose()
            ld_engine.dispose()
        for wf_client, wf_engine in willys_flyer_resources:
            await wf_client.aclose()
            wf_engine.dispose()
        for cg_client, cg_engine in citygross_resources:
            await cg_client.aclose()
            cg_engine.dispose()
        for coop_client, coop_engine in coop_resources:
            await coop_client.aclose()
            coop_engine.dispose()
        engine.dispose()
        staging.unlink(missing_ok=True)
        staging_temporary.unlink(missing_ok=True)


__all__ = ["NetworkAccessBlockedError", "build_city_price_universe"]
