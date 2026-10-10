"""Adapter for the replayable internal grocery-data HTTP API.

The collector is the source of truth for product and purchase semantics.  This
adapter deliberately maps only explicit normalized fields: comparison prices
never create package quantities and an incomplete purchase model stays
``UNKNOWN`` so it cannot win a verified basket downstream.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from math import isfinite
from typing import Any, Self
from urllib.parse import quote
from zoneinfo import ZoneInfo

import httpx
from app.errors import (
    PriceProviderAuthenticationError,
    PriceProviderError,
    PriceProviderRateLimitError,
)
from app.models import (
    OfferKind,
    OfferMetadata,
    Product,
    QuantityConfidence,
    SaleModel,
    SemanticConfidence,
    SourceProvenance,
    Store,
)
from app.services.ingredient_normalizer import (
    _search_text,
    canonicalize_ingredient_name,
    recipe_source_canonical_foods,
    recipe_source_query_aliases,
)
from app.services.product_semantics import is_non_human_food

from grocery_data.app.domain import CoverageLevel, is_complete_catalog_coverage
from grocery_data.app.domain.promotion_pricing import (
    MembershipProgram,
    PromotionEligibility,
    PromotionMechanism,
)

from .base import GroceryPriceProvider

_HEALTHY_STATUSES = {"healthy"}
_REJECTED_STATUSES = {
    "broken",
    "degraded",
    "invalid",
    "rejected",
    "stale",
    "unknown",
    "unavailable",
    "unverified",
}
_USABLE_COVERAGE = {
    coverage.value for coverage in CoverageLevel if is_complete_catalog_coverage(coverage)
}
_PAGE_LIMIT = 100


def _positive_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError):
        return None
    return result if isfinite(result) and result > 0 else None


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        result = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError):
        return None
    return result if isfinite(result) else None


def _parse_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, str) and value.strip():
        try:
            result = datetime.fromisoformat(value.strip())
        except ValueError:
            return None
    else:
        return None
    if result.tzinfo is None:
        return result.replace(tzinfo=UTC)
    return result.astimezone(UTC)


def _parse_date(value: object) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError:
        return None


def _text(value: object) -> str | None:
    if value is None:
        return None
    result = str(value).strip()
    return result or None


def _gtin(value: object) -> str | None:
    text = _text(value)
    if text is None:
        return None
    digits = "".join(character for character in text if character.isdigit())
    return digits if 8 <= len(digits) <= 14 and digits == text else None


class OwnGroceryPriceProvider(GroceryPriceProvider):
    """Consume only healthy, promoted/fresh data from our own collector API."""

    source_name = "own"
    attribution_text = "Prisdata från egen grocery-data-insamling"

    def __init__(
        self,
        base_url: str,
        use_member_prices: bool = False,
        *,
        max_age_hours: float = 48.0,
        include_offers_only: bool = False,
        include_conditional_offer_products: bool = False,
        client: httpx.AsyncClient | None = None,
        municipal_willys_stores: dict | None = None,
    ) -> None:
        if not base_url.strip():
            raise ValueError("OWN_GROCERY_BASE_URL must not be empty")
        if not isfinite(max_age_hours) or max_age_hours <= 0:
            raise ValueError("OWN_GROCERY_MAX_AGE_HOURS must be greater than zero")
        super().__init__(use_member_prices=use_member_prices)
        self.attribution_url = base_url.rstrip("/")
        self.max_age_hours = max_age_hours
        self._usable_coverage = set(_USABLE_COVERAGE)
        # This flag permits explicit offer diagnostics/enrichment only.  It
        # must never turn an offers-only feed into a catalogue that the meal
        # optimizer may treat as complete.
        self._include_offers_only = include_offers_only
        self._include_conditional_offer_products = include_offers_only and include_conditional_offer_products
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=base_url.rstrip("/") + "/",
            timeout=httpx.Timeout(20.0, connect=10.0),
        )
        self._client.headers["Accept"] = "application/json"
        self._client.headers["User-Agent"] = "billigaste-veckomenyn-own-provider/1.0"
        self._stores: dict[str, Store] = {}
        self._municipal_willys_stores = municipal_willys_stores
        self._store_freshness: dict[str, dict[str, Any]] = {}
        # Set only by the explicit ICA row-contract provider after reading
        # promoted OWN snapshot identity. Never affects ordinary catalogues.
        self.campaign_snapshot_ids: frozenset[str] = frozenset()
        self._catalog_cache: dict[str, tuple[Product, ...]] = {}
        self.offer_projection_diagnostics: dict[str, dict[str, int]] = {}
        self._product_search_cache: dict[tuple[str, tuple[str, ...]], tuple[Product, ...]] = {}

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def get_query_coverage(
        self,
        store: Store | str,
        canonical_ingredients: Sequence[str],
        *,
        max_price_age_days: int = 7,
    ) -> dict[str, Any]:
        """Return ICA registry completeness without treating it as full catalogue coverage."""

        store_id = store.id if isinstance(store, Store) else store
        response = await self._client.post(
            f"registry/ica/stores/{store_id}/basket-coverage",
            json={
                "canonical_foods": list(dict.fromkeys(canonical_ingredients)),
                "max_price_age_days": max_price_age_days,
            },
        )
        if response.status_code == 404:
            return {
                "requested_ingredients": len(set(canonical_ingredients)),
                "safely_priced_ingredients": 0,
                "coverage_ratio": 0.0,
                "complete_for_request": False,
                "missing_ingredients": list(dict.fromkeys(canonical_ingredients)),
            }
        if response.is_error:
            raise PriceProviderError(
                f"Egen prisdatatjänst kunde inte ge query coverage: {self._error_message(response)}"
            )
        payload = response.json()
        if not isinstance(payload, dict):
            raise PriceProviderError("Egen prisdatatjänst returnerade ogiltig query coverage")
        return payload

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    @staticmethod
    def _error_message(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return (response.text or response.reason_phrase)[:300]
        if isinstance(payload, Mapping):
            detail = payload.get("detail") or payload.get("error") or payload.get("message")
            if isinstance(detail, Mapping):
                detail = detail.get("message") or detail.get("code")
            if detail is not None:
                return str(detail)[:300]
        return response.reason_phrase[:300]

    async def _request(
        self,
        path: str,
        *,
        params: Mapping[str, object] | Sequence[tuple[str, object]] | None = None,
    ) -> dict[str, Any]:
        try:
            response = await self._client.get(path.lstrip("/"), params=params)
        except httpx.HTTPError as exc:
            raise PriceProviderError(f"Egen prisdatatjänst kunde inte nås: {exc}") from exc
        if response.status_code in {401, 403}:
            raise PriceProviderAuthenticationError(
                f"Egen prisdatatjänst avvisade anropet: {self._error_message(response)}"
            )
        if response.status_code == 429:
            raise PriceProviderRateLimitError(
                f"Egen prisdatatjänsts anropsgräns är nådd: {self._error_message(response)}"
            )
        if response.is_error:
            raise PriceProviderError(
                f"Egen prisdatatjänst svarade {response.status_code}: "
                f"{self._error_message(response)}"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise PriceProviderError("Egen prisdatatjänst returnerade ogiltig JSON") from exc
        if not isinstance(payload, dict):
            raise PriceProviderError("Egen prisdatatjänst returnerade ett oväntat svarsformat")
        return payload

    def _freshness_rows(
        self,
        payload: Mapping[str, Any],
        *,
        fallback_store_ids: Sequence[str] = (),
    ) -> list[Mapping[str, Any]]:
        raw_rows = payload.get("freshness")
        if isinstance(raw_rows, list):
            rows = [row for row in raw_rows if isinstance(row, Mapping)]
            if rows:
                return rows

        if any(
            payload.get(key) is not None
            for key in ("connector_status", "snapshot_id", "observed_at", "data_age_hours")
        ):
            return [payload]

        cached = [
            self._store_freshness[store_id]
            for store_id in fallback_store_ids
            if store_id in self._store_freshness
        ]
        if fallback_store_ids and len(cached) == len(set(fallback_store_ids)):
            return cached
        return []

    def _source_provenance(
        self,
        row: Mapping[str, Any],
        *,
        default_channel: str,
    ) -> SourceProvenance | None:
        snapshot_id = _text(row.get("source_snapshot_id") or row.get("snapshot_id"))
        observed_at = _parse_datetime(row.get("source_observed_at") or row.get("observed_at"))
        if snapshot_id is None or observed_at is None:
            return None
        return SourceProvenance(
            source_provider=_text(row.get("source_provider")) or self.source_name,
            source_channel=_text(row.get("source_channel")) or default_channel,
            source_snapshot_id=snapshot_id,
            source_observed_at=observed_at,
            chain=_text(row.get("chain")),
            store_id=_text(row.get("store_id") or row.get("id")),
            store_name=_text(row.get("store_name") or row.get("name")),
            provider_store_id=_text(
                row.get("external_store_id") or row.get("external_id") or row.get("store_id")
            ),
            retailer_id_namespace=("willys:flyer-document-ad"
                if row.get("willys_document_count_contract") is True else
                'lidl:public-product' if row.get('lidl_document_count_contract') is True else None),
            price_context=_text(row.get("price_context_type")),
            coverage=_text(row.get("coverage") or row.get("store_coverage")),
            semantic_confidence=_text(row.get("semantic_confidence")),
            quantity_confidence=_text(row.get("quantity_confidence")),
            collection_location=(
                "LOCAL_RELAY" if row.get("collection_location") == "LOCAL_RELAY" else None
            ),
        )

    def _validate_freshness(
        self,
        payload: Mapping[str, Any],
        *,
        fallback_store_ids: Sequence[str] = (),
    ) -> None:
        rows = self._freshness_rows(payload, fallback_store_ids=fallback_store_ids)
        if not rows:
            raise PriceProviderError(
                "Egen prisdatatjänst saknar verifierbar connectorstatus och färskhet"
            )

        now = datetime.now(tz=UTC)
        for row in rows:
            snapshot = _text(row.get("snapshot_id") or row.get("active_snapshot_id"))
            if snapshot in self.campaign_snapshot_ids:
                observed = _parse_datetime(row.get("observed_at"))
                if observed is None or observed > now:
                    raise PriceProviderError("Campaign source observation is unverified")
                # Each returned contract must still pass its own source-bound
                # date/identity checks in IcaAreaOfferProvider and checkout.
                continue
            status = str(row.get("connector_status") or row.get("status") or "unknown").lower()
            if status not in _HEALTHY_STATUSES:
                if status in _REJECTED_STATUSES:
                    raise PriceProviderError(
                        f"Egen prisdata är inte verifierad för användning (status={status})"
                    )
                raise PriceProviderError(
                    f"Egen prisdata har okänd connectorstatus ({status or 'saknas'})"
                )
            snapshot_id = _text(row.get("snapshot_id") or row.get("active_snapshot_id"))
            if snapshot_id is None:
                raise PriceProviderError("Egen prisdata saknar en aktiv promoterad snapshot")
            if row.get("is_stale") is True:
                raise PriceProviderError("Egen prisdata är markerad som inaktuell")

            reported_age = _optional_float(row.get("data_age_hours"))
            observed_at = _parse_datetime(
                row.get("observed_at") or row.get("last_success_at") or row.get("promoted_at")
            )
            if reported_age is None and observed_at is None:
                raise PriceProviderError("Egen prisdata saknar verifierbar observationstid")
            if reported_age is not None and (reported_age < 0 or reported_age > self.max_age_hours):
                raise PriceProviderError(f"Egen prisdata är för gammal ({reported_age:.1f} timmar)")
            if observed_at is not None:
                age_hours = (now - observed_at).total_seconds() / 3600
                if age_hours < -1:
                    raise PriceProviderError("Egen prisdata har en observationstid i framtiden")
                if age_hours > self.max_age_hours:
                    raise PriceProviderError(
                        f"Egen prisdata är för gammal ({age_hours:.1f} timmar)"
                    )

    @staticmethod
    def _records(payload: Mapping[str, Any], *keys: str) -> list[Mapping[str, Any]]:
        for key in keys:
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, Mapping)]
        data = payload.get("data")
        if isinstance(data, Mapping):
            for key in keys:
                value = data.get(key)
                if isinstance(value, list):
                    return [row for row in value if isinstance(row, Mapping)]
            value = data.get("items")
            if isinstance(value, list):
                return [row for row in value if isinstance(row, Mapping)]
        if isinstance(data, list):
            return [row for row in data if isinstance(row, Mapping)]
        return []

    async def _paginated(
        self,
        path: str,
        *,
        record_keys: tuple[str, ...],
        params: Sequence[tuple[str, object]] = (),
        page_size: int,
        fallback_store_ids: Sequence[str] = (),
    ) -> list[Mapping[str, Any]]:
        records: list[Mapping[str, Any]] = []
        for page in range(_PAGE_LIMIT):
            offset = page * page_size
            payload = await self._request(
                path,
                params=[*params, ("limit", page_size), ("offset", offset)],
            )
            self._validate_freshness(payload, fallback_store_ids=fallback_store_ids)
            rows = self._records(payload, *record_keys)
            inherited = {
                "source_provider": payload.get("source_provider") or self.source_name,
                "source_channel": payload.get("source_channel") or "catalog",
                "source_snapshot_id": payload.get("source_snapshot_id")
                or payload.get("snapshot_id"),
                "source_observed_at": payload.get("source_observed_at")
                or payload.get("observed_at"),
            }
            records.extend(
                {
                    **{key: value for key, value in inherited.items() if value is not None},
                    **row,
                }
                for row in rows
            )
            if len(rows) < page_size:
                return records
        raise PriceProviderError("Egen prisdatatjänsts paginering överskred säkerhetsgränsen")

    async def _find_stores_for_coverage(
        self,
        postal_code: str,
        *,
        accepted_coverage: set[str],
        empty_message: str,
        source_locality: str | None = None,
    ) -> list[Store]:
        digits = "".join(character for character in postal_code if character.isdigit())
        if source_locality is None and len(digits) != 5:
            raise ValueError("postal_code must contain exactly five digits")
        payload = await self._request(
            "/stores",
            params={**({"city": source_locality} if source_locality is not None else {"postal_code": digits}), "limit": 500, "offset": 0},
        )
        stores: list[Store] = []
        for row in self._records(payload, "stores", "items"):
            coverage = str(row.get("coverage") or "").lower()
            if coverage not in accepted_coverage or row.get("active") is False:
                continue
            chain = _text(row.get("chain"))
            external_id = _text(row.get("external_id"))
            source_id = _text(row.get("id") or row.get("store_id"))
            store_id = source_id or (f"{chain}:{external_id}" if chain and external_id else None)
            name = _text(row.get("name"))
            city = _text(row.get("city"))
            source_postal_code = _text(row.get("postal_code"))
            price_context_type = _text(row.get("price_context_type"))
            service_area = row.get("service_area")
            pickup_options = row.get("pickup_options")
            verified_pickup_scope = bool(
                price_context_type == "online_fulfillment"
                and _text(row.get("price_semantics")) == "online_price"
                and isinstance(service_area, Mapping)
                and service_area.get("availability_basis") == "verified_pickup_context"
                and _text(service_area.get("requested_postal_code")) == digits
                and isinstance(pickup_options, list)
                and pickup_options
                and all(
                    isinstance(option, Mapping)
                    and option.get("relation_type") == "pickup_context"
                    and _text(option.get("physical_store_id")) is not None
                    for option in pickup_options
                )
            )
            if not all((chain, store_id, name, city)):
                continue
            # Catalogue stores need a source postal code before they may enter
            # geographic basket optimization. A regional online fulfillment
            # context is the one exception: it may omit a physical postcode
            # only when the API explains the exact requested area through at
            # least one active, verified pickup relation. Offers-only stores are
            # diagnostic enrichment and may legitimately omit it.
            if (
                coverage != "offers_only"
                and source_postal_code is None
                and not verified_pickup_scope
            ):
                continue
            try:
                store = Store(
                    store_id=store_id,
                    name=name,
                    chain=chain,
                    city=city,
                    postal_code=source_postal_code,
                    address=_text(row.get("address")),
                    latitude=_optional_float(row.get("latitude")),
                    longitude=_optional_float(row.get("longitude")),
                    distance_km=_optional_float(row.get("distance_km")),
                    tier=coverage,
                    price_context_type=price_context_type,
                    physical_store_external_id=_text(row.get("physical_store_external_id")),
                    source_store_id=external_id,
                    coverage=coverage,
                    confirmed_at=_text(row.get("observed_at")),
                    price_semantics=_text(row.get("price_semantics")),
                    price_label=_text(row.get("price_label")),
                    service_area=service_area if isinstance(service_area, Mapping) else None,
                    pickup_options=(
                        tuple(pickup_options) if isinstance(pickup_options, list) else ()
                    ),
                    source_provenance=self._source_provenance(
                        row,
                        default_channel=("offers" if coverage == "offers_only" else "catalog"),
                    ),
                )
            except (TypeError, ValueError):
                continue
            freshness = {
                "connector_status": row.get("connector_status"),
                "snapshot_id": row.get("snapshot_id"),
                "observed_at": row.get("observed_at"),
                "data_age_hours": row.get("data_age_hours"),
                "is_stale": row.get("is_stale", False),
            }
            try:
                self._validate_freshness(freshness)
            except PriceProviderError:
                # Store discovery is deliberately isolated per connector. One
                # broken or stale chain must not make healthy promoted stores
                # from another chain unusable, but unsafe rows must never enter
                # the optimizer either.
                continue
            self._stores[store.store_id] = store
            self._store_freshness[store.store_id] = freshness
            stores.append(store)
        if not stores:
            raise PriceProviderError(f"{empty_message} {digits}")
        return stores

    async def find_stores(self, postal_code: str) -> list[Store]:
        """Return stores eligible for ordinary catalogue/basket operations."""

        try:
            stores = await self._find_stores_for_coverage(
                postal_code,
                accepted_coverage=self._usable_coverage,
                empty_message="Egen prisdatatjänst hittade inga användbara butiker för",
            )
        except PriceProviderError:
            if self._municipal_willys_stores is None:
                raise
            stores = []
        if self._municipal_willys_stores is None:
            return stores
        municipal = self._municipal_willys_stores
        result = {s.store_id: s for s in stores if s.chain.casefold() != "willys"}
        for locality in sorted({s.city for s in municipal.values() if s.city}):
            try:
                candidates = await self._find_stores_for_coverage(
                    postal_code, accepted_coverage=self._usable_coverage,
                    empty_message="Ingen godkänd kommunal katalog", source_locality=locality)
            except PriceProviderError:
                continue  # Remains absent/unusable; never substitutes another store.
            for candidate in candidates:
                evidence = municipal.get(candidate.source_store_id)
                if (candidate.chain.casefold() == "willys" and evidence is not None
                        and candidate.price_context_type == "online_store"
                        and candidate.physical_store_external_id == evidence.external_id
                        and candidate.address == evidence.address
                        and candidate.postal_code == "".join((evidence.postal_code or "").split())):
                    result[candidate.store_id] = candidate
        return list(result.values())

    async def find_offer_stores(self, postal_code: str) -> list[Store]:
        """Discover offers-only stores for explicit diagnostics/enrichment.

        This method intentionally is not part of ``GroceryPriceProvider``:
        callers cannot accidentally feed its result to the normal basket
        workflow through the provider abstraction.
        """

        if not self._include_offers_only:
            raise PriceProviderError(
                "Offer-only-butiker kräver explicit opt-in för offerdiagnostik"
            )
        return await self._find_stores_for_coverage(
            postal_code,
            accepted_coverage={"offers_only"},
            empty_message="Egen prisdatatjänst hittade inga offer-only-butiker för",
        )

    async def find_offer_stores_in_locality(self, locality: str) -> list[Store]:
        """Opt-in discovery by verified address locality, before exact inventory filtering.

        Locality is an API lookup key, never evidence of municipal membership.
        Existing postal discovery and user store selection remain unchanged.
        """
        if not self._include_offers_only or not locality.strip():
            raise PriceProviderError("Explicit offers-only locality discovery required")
        return await self._find_stores_for_coverage(
            "", accepted_coverage={"offers_only"}, source_locality=locality.strip(),
            empty_message="No qualified offers-only source in locality",
        )

    async def search_products(self, query: str, store_ids: list[str]) -> list[Product]:
        normalized_query = _search_text(query)
        if not normalized_query or not store_ids:
            return []
        cache_key = (normalized_query, tuple(sorted(set(store_ids))))
        cached = self._product_search_cache.get(cache_key)
        if cached is not None:
            return [product.model_copy(deep=True) for product in cached]

        # Query exact structured identities first. Old promoted snapshots may
        # predate one or more canonical-food normalizers, so stores with no
        # structured hit receive a bounded fallback over the authoritative
        # recipe aliases (including curated reversed word order). The union is
        # deduplicated by store/product identity and ProductMatcher remains the
        # final semantic gate; no fuzzy recall is introduced here.
        source_canonicals = recipe_source_canonical_foods(query)
        structured_rows: list[Mapping[str, Any]] = []
        if source_canonicals:
            for source_canonical in source_canonicals:
                structured_rows.extend(
                    await self._paginated(
                        "/products/search",
                        record_keys=("products", "items"),
                        params=[
                            ("q", source_canonical),
                            ("canonical_food", source_canonical),
                            *(("store_id", store_id) for store_id in cache_key[1]),
                        ],
                        page_size=500,
                        fallback_store_ids=cache_key[1],
                    )
                )
            structured_products = self._parse_products(structured_rows)
            represented_store_ids = {product.store_id for product in structured_products}
            fallback_store_ids = tuple(
                store_id for store_id in cache_key[1] if store_id not in represented_store_ids
            )
            literal_rows: list[Mapping[str, Any]] = []
            if fallback_store_ids:
                for alias in recipe_source_query_aliases(query):
                    literal_rows.extend(
                        await self._paginated(
                            "/products/search",
                            record_keys=("products", "items"),
                            params=[
                                ("q", alias),
                                *(("store_id", store_id) for store_id in fallback_store_ids),
                            ],
                            page_size=500,
                            fallback_store_ids=fallback_store_ids,
                        )
                    )
            products = [*structured_products, *self._parse_products(literal_rows)]
        else:
            rows = await self._paginated(
                "/products/search",
                record_keys=("products", "items"),
                params=[
                    ("q", query),
                    *(("store_id", store_id) for store_id in cache_key[1]),
                ],
                page_size=500,
                fallback_store_ids=cache_key[1],
            )
            products = self._parse_products(rows)

        deduplicated_products: dict[tuple[str, str], Product] = {}
        for product in products:
            deduplicated_products.setdefault(
                (product.store_id, product.product_id),
                product,
            )
        selected = [
            product
            for product in deduplicated_products.values()
            if product.store_id in set(store_ids)
            and (
                self._stores.get(product.store_id) is None
                or self._stores[product.store_id].tier != "offers_only"
            )
            and (
                product.source_provenance is None
                or product.source_provenance.source_channel != "offers"
            )
        ]
        priced = self.apply_price_policy(selected)
        self._product_search_cache[cache_key] = tuple(priced)
        return [product.model_copy(deep=True) for product in priced]

    async def get_store_products(self, store_id: str) -> list[Product]:
        store = self._stores.get(store_id)
        if store is not None and store.tier == "offers_only":
            raise PriceProviderError(
                "Offer-only-butiken saknar verifierad katalog och kan inte användas som basketbutik"
            )
        cached = self._catalog_cache.get(store_id)
        if cached is not None:
            return [product.model_copy(deep=True) for product in cached]
        rows = await self._paginated(
            f"/catalog/{quote(store_id, safe='')}",
            record_keys=("products", "items"),
            page_size=1000,
            fallback_store_ids=(store_id,),
        )
        products = [
            product for product in self._parse_products(rows) if product.store_id == store_id
        ]
        priced = self.apply_price_policy(products)
        self._catalog_cache[store_id] = tuple(priced)
        return [product.model_copy(deep=True) for product in priced]

    async def get_offers(self, store_id: str) -> list[Product]:
        offer_rows = await self._paginated(
            "/offers",
            record_keys=("offers", "items"),
            params=(("store_id", store_id), ("active_only", "false" if self.campaign_snapshot_ids else "true")),
            page_size=1000,
            fallback_store_ids=(store_id,),
        )
        if not offer_rows:
            return []

        offers_by_product: dict[str, list[OfferMetadata]] = {}
        embedded_products: dict[str, Product] = {}
        projection = {"source_offers": len(offer_rows), "invalid_or_incomplete_product": 0,
                      "missing_embedded_product": 0, "projected_products": 0}
        self.offer_projection_diagnostics[store_id] = projection
        offers_only_payload = False
        for row in offer_rows:
            if self._include_conditional_offer_products and not row.get("valid_from") and not row.get("campaign_evidence"):
                observed = _parse_datetime(row.get("source_observed_at"))
                if observed is not None:
                    row = {**row, "valid_from": observed.astimezone(ZoneInfo("Europe/Stockholm")).date().isoformat()}
            if str(row.get("store_coverage") or "").casefold() == "offers_only":
                offers_only_payload = True
            product_key = _text(row.get("product_id") or row.get("external_product_id"))
            offer = self._offer_from_row(row, chain=_text(row.get("chain")))
            if product_key and offer is not None:
                offers_by_product.setdefault(product_key, []).append(offer)

            product_row = row.get("product")
            if not isinstance(product_row, Mapping):
                projection["missing_embedded_product"] += 1
                continue
            if str(product_row.get("source_channel") or "").casefold() == "offers":
                offers_only_payload = True
            if self._include_conditional_offer_products and offer is not None:
                # /offers embeds product identity separately from the contract.
                # Supply that observed contract without recursively copying product.
                product_row = {**product_row, "coverage": row.get("store_coverage") or product_row.get("coverage"), "promotions": [
                    *self._promotion_rows(product_row),
                    {key: value for key, value in row.items() if key != "product"},
                ]}
            try:
                product = self._product_from_row(product_row)
            except (TypeError, ValueError):
                product = None
            if product is None:
                projection["invalid_or_incomplete_product"] += 1
                continue
            if (
                product.source_provenance is not None
                and product.source_provenance.source_channel == "offers"
                and not self._include_offers_only
            ):
                raise PriceProviderError(
                    "Offer-only-butiker kräver explicit opt-in för offerdiagnostik"
                )
            embedded_products[product.product_id] = product

        store = self._stores.get(store_id)
        if (
            offers_only_payload or store is not None and store.tier == "offers_only"
        ) and not self._include_offers_only:
            raise PriceProviderError(
                "Offer-only-butiker kräver explicit opt-in för offerdiagnostik"
            )

        # New API responses embed the normalized product beside each offer so
        # offers-only diagnostics never need to masquerade as a catalogue.
        # Retain a catalogue fallback solely for older full-catalogue APIs.
        products = list(embedded_products.values())
        if not products:
            if offers_only_payload or store is not None and store.tier == "offers_only":
                # A conditional offer without a separately observed product
                # price cannot safely be flattened into Product. The /offers
                # API remains the complete diagnostic surface; never consult
                # an unavailable offers-only catalogue to manufacture one.
                return []
            products = await self.get_store_products(store_id)

        result: list[Product] = []
        for product in products:
            joined = [
                *product.offers,
                *offers_by_product.get(product.product_id, ()),
            ]
            deduplicated = self._deduplicate_offers(joined)
            if not deduplicated:
                continue
            enriched = Product.model_validate(
                product.model_copy(update={"offers": deduplicated}).model_dump()
            )
            if self._include_conditional_offer_products:
                # Shared source material keeps contracts; personal membership,
                # purchase date and multibuy quantity are resolved at checkout.
                result.append(enriched)
            else:
                result.extend(self.apply_price_policy([enriched]))
        projection["projected_products"] = len(result)
        from app.services.source_promotion_groups import attach_source_groups
        return attach_source_groups(result, offer_rows)

    def _parse_products(self, rows: Sequence[Mapping[str, Any]]) -> list[Product]:
        products: list[Product] = []
        for row in rows:
            try:
                product = self._product_from_row(row)
            except (TypeError, ValueError):
                continue
            if product is not None:
                products.append(product)
        if rows and not products:
            raise PriceProviderError(
                "Egen prisdatatjänst returnerade produkter men ingen hade säker prisdata"
            )
        from app.services.source_promotion_groups import attach_source_groups
        return attach_source_groups(products, rows)

    def _product_from_row(self, row: Mapping[str, Any]) -> Product | None:
        availability = row.get("availability")
        if availability is False or str(availability).casefold() in {
            "false",
            "out_of_stock",
            "unavailable",
        }:
            return None

        name = _text(row.get("name") or row.get("product_name"))
        product_id = _text(
            row.get("id")
            or row.get("product_id")
            or row.get("source_product_key")
            or row.get("external_product_id")
            or row.get("gtin")
        )
        store_id = _text(row.get("store_id"))
        if not name or not product_id or not store_id:
            return None
        store = self._stores.get(store_id)
        store_name = _text(row.get("store_name")) or (store.name if store else store_id)
        chain = _text(row.get("chain")) or (store.chain if store else None)

        if row.get("physical_offer_qualified") is False:
            return None
        current_price = _positive_float(row.get("sale_price"))
        if current_price is None and self._include_conditional_offer_products:
            # Conditional amount is a ranking signal only. The offer contract
            # below retains its quantity; ordinary_price remains unknown.
            contract_prices = [o.price / o.required_packages
                               for r in self._promotion_rows(row)
                               if (o := self._offer_from_row(r, chain=chain)) is not None]
            current_price = min(contract_prices, default=None)
        comparison_price = _positive_float(row.get("comparison_price"))
        raw_sale_model = str(row.get("sale_model") or "unknown").casefold()
        try:
            sale_model = SaleModel(raw_sale_model)
        except ValueError:
            sale_model = SaleModel.UNKNOWN

        sale_unit = self._rate_unit(row.get("sale_unit"))
        comparison_unit = self._comparison_unit(row.get("comparison_unit"))
        # A comparison price is useful evidence only together with its source
        # unit.  Preserve explicit non-rate units (for example ``tvätt``) as
        # opaque display/provenance values, but never construct a half pair
        # that would reject the otherwise valid product and its price contracts.
        if comparison_unit is None:
            comparison_price = None
        if current_price is None and sale_model == SaleModel.SOLD_BY_WEIGHT:
            current_price = comparison_price
            sale_unit = sale_unit or comparison_unit
        if current_price is None:
            return None

        regular_price = _positive_float(row.get("regular_price"))
        source_fields = row.get("source_fields") or {}
        offer_only = ((store.coverage if store else row.get("coverage")) == "offers_only"
                      or row.get("source_channel") == "offers"
                      or source_fields.get("regular_price_current_verified") is False)
        ordinary_price = (None if source_fields.get("regular_price_current_verified") is False
                          else regular_price if offer_only
                          else max(current_price, regular_price or current_price))
        member_price = _positive_float(row.get("member_price"))
        if member_price is not None and ordinary_price is not None and member_price > ordinary_price:
            member_price = None

        package = self._canonical_quantity(row.get("package_quantity"), row.get("package_unit"))
        usable = self._canonical_quantity(row.get("usable_quantity"), row.get("usable_unit"))
        raw_quantity_confidence = str(row.get("quantity_confidence") or "unknown").casefold()
        quantity_confidence = self._quantity_confidence(raw_quantity_confidence)

        # An asserted purchase class with incomplete facts is not partially
        # repaired here. Keeping it UNKNOWN prevents comparison price or a lone
        # package field from becoming a fabricated purchasable package.
        if sale_model == SaleModel.FIXED_PACKAGE and (package is None or usable is None):
            sale_model = SaleModel.UNKNOWN
            package = usable = None
            quantity_confidence = QuantityConfidence.UNKNOWN
        elif sale_model == SaleModel.SOLD_BY_WEIGHT:
            if not (
                sale_unit in {"kg", "l"}
                or (comparison_price is not None and comparison_unit in {"kg", "l"})
            ):
                sale_model = SaleModel.UNKNOWN
                quantity_confidence = QuantityConfidence.UNKNOWN
            package = usable = None
        elif sale_model == SaleModel.SOLD_BY_PIECE:
            if sale_unit not in {None, "st"}:
                sale_model = SaleModel.UNKNOWN
                quantity_confidence = QuantityConfidence.UNKNOWN
            package = package if package and package[1] == "st" else None
            usable = usable if usable and usable[1] == "st" else None
        elif sale_model == SaleModel.VARIABLE_WEIGHT_PACKAGE and (
            package is None or usable is None
        ):
            sale_model = SaleModel.UNKNOWN
            package = usable = None
            quantity_confidence = QuantityConfidence.UNKNOWN
        elif sale_model == SaleModel.UNKNOWN:
            package = usable = None
            quantity_confidence = QuantityConfidence.UNKNOWN

        category_path = row.get("category_path")
        categories = (
            [str(value).strip() for value in category_path if str(value).strip()]
            if isinstance(category_path, list | tuple)
            else []
        )
        category = " > ".join(categories) or _text(row.get("category")) or "Okategoriserad"
        canonical_name = canonicalize_ingredient_name(name)
        canonical_food, product_role = self._backend_semantics(
            _text(row.get("canonical_food")),
            _text(row.get("product_role")),
            name,
        )
        semantic_confidence = self._semantic_confidence(row.get("semantic_confidence"))
        product_form = _text(row.get("product_form"))
        # Protect consumers of an older promoted snapshot as well as newly
        # normalized data.  Visible pet-food evidence always outranks stale
        # canonical metadata supplied by the collector.
        if is_non_human_food(name, category):
            # ProductSemantics maps a missing canonical_food from the legacy
            # canonical_name field.  Use an explicit sentinel so pet food can
            # never be silently remapped back to ``kyckling``.
            canonical_food = "non_human_food"
            product_role = "non_human_food"
            product_form = "pet_food"
            semantic_confidence = SemanticConfidence.REJECTED
        offers = [
            offer
            for source_offer in self._promotion_rows(row)
            if (offer := self._offer_from_row(source_offer, chain=chain)) is not None
        ]
        if ordinary_price is not None and current_price < ordinary_price and not any(
            offer.required_packages == 1
            and offer.kind == OfferKind.CAMPAIGN
            and abs(offer.price - current_price) < 0.005
            for offer in offers
        ):
            offers.append(
                OfferMetadata(
                    kind=OfferKind.CAMPAIGN,
                    description="Kampanjpris",
                    price=current_price,
                )
            )
        offers = self._deduplicate_offers(offers)

        eligible_single_prices = [current_price]
        eligible_single_prices.extend(
            offer.price
            for offer in offers
            if offer.required_packages == 1
            and offer.is_active()
            and (
                offer.kind == OfferKind.CAMPAIGN
                or offer.kind == OfferKind.MEMBER
                and self.use_member_prices
            )
        )
        if self.use_member_prices and member_price is not None:
            eligible_single_prices.append(member_price)
        effective_price = min(eligible_single_prices)
        purchase_sale_price = (
            current_price if sale_model == SaleModel.FIXED_PACKAGE else effective_price
        )
        if ordinary_price is None and sale_model == SaleModel.SOLD_BY_PIECE:
            # A multibuy quotient is only a ranking signal; no residual piece price.
            single_prices = [o.price for o in offers if o.required_packages == 1
                             and o.is_active() and (o.kind != OfferKind.MEMBER or self.use_member_prices)]
            purchase_sale_price = min(single_prices) if single_prices else None
        estimated_piece_weight = None
        average_weight_kg = _positive_float(row.get("average_weight_kg"))
        if average_weight_kg is not None:
            estimated_piece_weight = average_weight_kg * 1000

        fields: dict[str, Any] = {
            "product_id": product_id,
            "name": name,
            "canonical_name": canonical_name,
            "category": category,
            "store_id": store_id,
            "store_name": store_name,
            "price": ordinary_price,
            "conditional_price_signal": bool(ordinary_price is None and (
                row.get("physical_offer_qualified") is True
                or offer_only and self._include_conditional_offer_products
                and any(o.purchase_terms is not None for o in offers))),
            "effective_price": effective_price,
            "member_price": member_price,
            "offers": offers,
            "brand": _text(row.get("brand")),
            "chain": chain,
            "gtin": _gtin(row.get("gtin")),
            "price_context_type": (
                store.price_context_type
                if store is not None
                else _text(row.get("price_context_type"))
            ),
            "coverage": store.coverage if store is not None else _text(row.get("coverage")),
            "search_terms": [*categories, *filter(None, (canonical_food, _text(row.get("gtin"))))],
            "canonical_food": canonical_food,
            "food_family": _text(row.get("food_family")),
            "product_role": product_role,
            "product_form": product_form,
            "sale_model": sale_model,
            "sale_price": purchase_sale_price,
            "sale_unit": sale_unit,
            "comparison_price": comparison_price,
            "comparison_unit": comparison_unit,
            "semantic_confidence": semantic_confidence,
            "quantity_confidence": quantity_confidence,
            "variable_weight": sale_model
            in {SaleModel.SOLD_BY_WEIGHT, SaleModel.VARIABLE_WEIGHT_PACKAGE},
            "source_provenance": self._source_provenance(
                row,
                default_channel="catalog",
            ),
        }
        if package is not None:
            fields["package_quantity"], fields["package_unit"] = package
        if usable is not None:
            fields["usable_quantity"], fields["usable_unit"] = usable
        if sale_model == SaleModel.SOLD_BY_PIECE:
            fields["piece_price"] = purchase_sale_price
            if estimated_piece_weight is not None:
                fields["estimated_piece_weight"] = estimated_piece_weight
                fields["estimated_piece_weight_unit"] = "g"
        return Product(**fields)

    @staticmethod
    def _promotion_rows(row: Mapping[str, Any]) -> list[Mapping[str, Any]]:
        value = row.get("promotions") or row.get("offers")
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, Mapping)]

    def _offer_from_row(
        self,
        row: Mapping[str, Any],
        *,
        chain: str | None,
    ) -> OfferMetadata | None:
        kind = str(row.get("type") or row.get("kind") or "").casefold()
        # Membership does not make an unsupported source condition executable.
        if kind not in {"multibuy", "multipack", "member_price", "member", "sale_price", "campaign", "percent_discount"}:
            return None
        price = _positive_float(row.get("price"))
        if price is None:
            return None
        raw_quantity = row.get("quantity") or row.get("required_packages") or 1
        try:
            quantity = int(raw_quantity)
        except (TypeError, ValueError, OverflowError):
            return None
        if quantity < 1:
            return None
        raw_max_quantity = row.get("max_quantity")
        max_quantity: int | None = None
        if raw_max_quantity is not None:
            try:
                max_quantity = int(raw_max_quantity)
            except (TypeError, ValueError, OverflowError):
                return None
            if max_quantity < 1:
                return None
        member_only = row.get("member_only") is True or kind == "member_price"
        if kind in {"multibuy", "multipack"}:
            # A few source-native labels say "1 för X". Quantity one is not a
            # multibuy contract; the explicit total is an ordinary unit-sale
            # contract with the same eligibility.
            offer_kind = (
                OfferKind.MULTIPACK
                if quantity >= 2
                else (OfferKind.MEMBER if member_only else OfferKind.CAMPAIGN)
            )
        elif member_only:
            if quantity != 1:
                return None
            offer_kind = OfferKind.MEMBER
        elif kind in {"sale_price", "campaign", "percent_discount"}:
            if quantity != 1:
                return None
            offer_kind = OfferKind.CAMPAIGN
        else:
            return None
        description = (
            _text(row.get("description"))
            or {
                OfferKind.MULTIPACK: f"{quantity} för {price:g} kr",
                OfferKind.MEMBER: "Medlemspris",
                OfferKind.CAMPAIGN: "Kampanjpris",
            }[offer_kind]
        )
        percent_discount = (
            _positive_float(row.get("percent_discount") or row.get("percent"))
            if kind == "percent_discount"
            else None
        )
        return OfferMetadata(
            kind=offer_kind,
            description=description,
            price=price,
            price_basis_unit=row.get('price_basis_unit', 'package'),
            purchase_terms=row.get('purchase_terms'),
            limit_unit=row.get('limit_unit'),
            required_packages=quantity,
            deposit=row.get("deposit"),
            max_quantity=max_quantity,
            eligibility=(
                PromotionEligibility.MEMBER if member_only else PromotionEligibility.PUBLIC
            ),
            mechanism=(
                PromotionMechanism.MULTIBUY
                if offer_kind is OfferKind.MULTIPACK
                else (
                    PromotionMechanism.PERCENT_DISCOUNT
                    if percent_discount is not None
                    else PromotionMechanism.SALE_PRICE
                )
            ),
            membership_program=(
                MembershipProgram.from_value(chain) if member_only and chain else None
            ),
            percent_discount=percent_discount,
            member_program=(f"{chain} medlem" if member_only and chain else None),
            valid_from=_parse_date(row.get("valid_from")),
            valid_to=_parse_date(row.get("valid_to")),
            campaign_evidence=row.get("campaign_evidence"),
            price_contract_id=_text(row.get("price_contract_id")),
        )

    @staticmethod
    def _deduplicate_offers(offers: Sequence[OfferMetadata]) -> list[OfferMetadata]:
        result: list[OfferMetadata] = []
        seen: set[tuple[object, ...]] = set()
        for offer in offers:
            key = (
                offer.kind,
                round(offer.price, 4),
                offer.price_basis_unit,
                offer.required_packages,
                offer.max_quantity,
                offer.eligibility,
                offer.membership_program,
                offer.price_contract_id,
                offer.member_program,
                offer.valid_from,
                offer.valid_to,
                offer.deposit.model_dump_json() if offer.deposit else None,
            )
            if key not in seen:
                seen.add(key)
                result.append(offer)
        return result

    @staticmethod
    def _canonical_quantity(amount: object, unit: object) -> tuple[float, str] | None:
        quantity = _positive_float(amount)
        normalized = str(unit or "").strip().casefold().replace(".", "")
        definitions = {
            "g": (1.0, "g"),
            "gram": (1.0, "g"),
            "kg": (1000.0, "g"),
            "ml": (1.0, "ml"),
            "cl": (10.0, "ml"),
            "dl": (100.0, "ml"),
            "l": (1000.0, "ml"),
            "liter": (1000.0, "ml"),
            "litre": (1000.0, "ml"),
            "st": (1.0, "st"),
            "styck": (1.0, "st"),
            "piece": (1.0, "st"),
            "pcs": (1.0, "st"),
        }
        definition = definitions.get(normalized)
        if quantity is None or definition is None:
            return None
        return quantity * definition[0], definition[1]

    @staticmethod
    def _rate_unit(value: object) -> str | None:
        normalized = str(value or "").strip().casefold().replace(" ", "")
        for prefix in ("sek/", "kr/"):
            normalized = normalized.removeprefix(prefix)
        return {
            "kg": "kg",
            "l": "l",
            "liter": "l",
            "litre": "l",
            "st": "st",
            "styck": "st",
            "piece": "st",
        }.get(normalized)

    @classmethod
    def _comparison_unit(cls, value: object) -> str | None:
        """Normalize known rate units and retain safe source-native units.

        Only kg/l/st are consumed by purchase arithmetic.  Other explicit
        source units remain opaque (for example ``tvätt``) so provenance is
        not lost and a valid product is not discarded merely because its
        comparison basis is retailer-specific.
        """

        known = cls._rate_unit(value)
        if known is not None:
            return known
        normalized = " ".join(str(value or "").strip().casefold().split())
        for prefix in ("sek/", "kr/"):
            normalized = normalized.removeprefix(prefix).strip()
        if (
            not normalized
            or len(normalized) > 64
            or any(ord(character) < 32 for character in normalized)
        ):
            return None
        return normalized

    @staticmethod
    def _quantity_confidence(value: str) -> QuantityConfidence:
        return {
            "exact": QuantityConfidence.EXACT,
            "derived": QuantityConfidence.DERIVED,
            "estimated": QuantityConfidence.ESTIMATED,
        }.get(value, QuantityConfidence.UNKNOWN)

    @staticmethod
    def _semantic_confidence(value: object) -> SemanticConfidence:
        return {
            "exact": SemanticConfidence.EXACT,
            "high": SemanticConfidence.HIGH,
            "medium": SemanticConfidence.MEDIUM,
            "low": SemanticConfidence.LOW,
            "rejected": SemanticConfidence.REJECTED,
        }.get(str(value or "").casefold(), SemanticConfidence.LOW)

    @staticmethod
    def _backend_semantics(
        canonical_food: str | None,
        product_role: str | None,
        name: str,
    ) -> tuple[str | None, str | None]:
        if canonical_food is None:
            return None, product_role
        normalized = canonical_food.casefold().strip()
        mappings: dict[str, tuple[str, str | None]] = {
            "chicken_meat": ("chicken", product_role or "generic_meat"),
            "chicken_breast": ("chicken", product_role or "breast"),
            "chicken_thigh": ("chicken", product_role or "thigh"),
            "chicken_heart": ("chicken", product_role or "heart"),
            "red_pepper": ("pepper", product_role),
            "kidney_beans": ("kidney_bean", product_role),
            "lentils": ("lentil", product_role),
        }
        if normalized == "onion":
            visible = _search_text(name)
            if "rodlok" in visible or "rod lok" in visible:
                return "red_onion", product_role
            if "gul lok" in visible or "matlok" in visible:
                return "yellow_onion", product_role
            return None, product_role
        return mappings.get(normalized, (normalized, product_role))


__all__ = ["OwnGroceryPriceProvider"]
