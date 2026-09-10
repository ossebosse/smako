"""Primat v3 price provider.

The adapter deliberately keeps Primat response parsing at the boundary. The
rest of the application only sees canonical package units and explicit price
fields, and can therefore run unchanged with the mock provider.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import islice
from math import inf, isfinite
from typing import Any, Self
from uuid import uuid4
from zoneinfo import ZoneInfo

import httpx
from app.errors import (
    PriceProviderAccessChallengeError,
    PriceProviderAuthenticationError,
    PriceProviderError,
    PriceProviderRateLimitError,
)
from app.models import OfferKind, OfferMetadata, Product, SourceProvenance, Store
from app.models.product import QuantityConfidence, SaleModel
from app.services.ingredient_normalizer import _search_text, canonicalize_ingredient_name

from grocery_data.app.domain.identifiers import InvalidGtinError, normalize_gtin
from grocery_data.app.domain.promotion_pricing import (
    MembershipProgram,
    PromotionEligibility,
    PromotionMechanism,
)

from .base import GroceryPriceProvider


def _chunks(values: list[str], size: int) -> Iterable[list[str]]:
    iterator = iter(values)
    while chunk := list(islice(iterator, size)):
        yield chunk


_NON_CUSTOMER_NAME_PHRASES = (
    "endast personal",
    "endast for personal",
    "personalbutik",
    "staff only",
    "employees only",
    "employee only",
    "internal only",
    "ej kundbutik",
)
_NON_CUSTOMER_ACCESS_VALUES = {
    "employee_only",
    "employees_only",
    "internal",
    "internal_only",
    "non_customer",
    "personal_only",
    "staff",
    "staff_only",
}
_ACCESS_CHALLENGE_MARKERS = (
    "access denied",
    "captcha",
    "cloudflare",
    "human verification",
    "verify you are human",
    "waf challenge",
)


@dataclass(frozen=True, slots=True)
class PrimatStoreResolution:
    """Parsed, credential-free facts from one `/stores/resolve` response."""

    postal_code: str
    place_city: str | None
    raw_rows: int
    selected_context_ids: frozenset[str]
    stores: tuple[Store, ...]
    observed_at: datetime
    source_snapshot_id: str
    response_sha256: str
    response_status: int
    response_content_type: str
    response_host: str
    response_path: str


def _explicit_boolean(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    normalized = str(value or "").strip().casefold()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    return None


def _is_customer_context(row: dict[str, Any]) -> bool:
    """Fail closed for contexts explicitly reserved for staff/internal use.

    Store tiers describe data breadth, not whether a context is a legitimate
    customer destination.  Only explicit access facts and unambiguous phrases
    are considered; ordinary names such as ``Personalvägen`` remain valid.
    """

    for field in ("customer_accessible", "customer_facing", "is_customer_facing", "public"):
        if _explicit_boolean(row.get(field)) is False:
            return False
    for field in ("employee_only", "internal", "staff_only"):
        if _explicit_boolean(row.get(field)) is True:
            return False

    access_values = {
        _search_text(str(row.get(field) or "")).replace(" ", "_")
        for field in ("access", "access_type", "audience", "context_type", "store_type")
    }
    if access_values & _NON_CUSTOMER_ACCESS_VALUES:
        return False

    name = _search_text(str(row.get("name") or ""))
    padded_name = f" {name} "
    return not any(
        f" {_search_text(phrase)} " in padded_name for phrase in _NON_CUSTOMER_NAME_PHRASES
    )


class PrimatPriceProvider(GroceryPriceProvider):
    """Async adapter for the documented ``https://primat.nu/api/v3`` API."""

    source_name = "primat"
    attribution_text = "Prisdata från primat.nu"
    attribution_url = "https://primat.nu"

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://primat.nu/api/v3",
        use_member_prices: bool = False,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("PRIMAT_API_KEY must not be empty")
        super().__init__(use_member_prices=use_member_prices)
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=base_url.rstrip("/") + "/",
            timeout=httpx.Timeout(20.0, connect=10.0),
        )
        # Keep authentication at the provider boundary even when a caller
        # injects an AsyncClient (for example a MockTransport in contract tests).
        self._client.headers["Authorization"] = f"Bearer {api_key}"
        self._client.headers["Accept"] = "application/json"
        self._client.headers["User-Agent"] = "billigaste-veckomenyn-poc/1.0"
        self._observation_id = f"primat-request-{uuid4().hex}"
        self._observed_at = datetime.now(tz=UTC)
        self._stores: dict[str, Store] = {}
        self._last_response_report: dict[str, Any] | None = None
        # A provider instance belongs to one plan request. Cheap-product
        # discovery and final ingredient matching often repeat the same ranked
        # catalogue search, so retain successful immutable domain rows for the
        # lifetime of that request instead of spending another API call.
        self._product_search_cache: dict[tuple[str, tuple[str, ...]], tuple[Product, ...]] = {}

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    def _redact_secrets(self, value: object) -> str:
        """Keep credentials out of upstream errors and exception messages."""

        message = str(value)
        authorization = self._client.headers.get("Authorization", "")
        api_key = authorization.removeprefix("Bearer ").strip()
        for secret in (authorization, api_key):
            if secret:
                message = message.replace(secret, "[REDACTED]")
        return message

    def _error_message(self, response: httpx.Response) -> str:
        try:
            body = response.json()
            detail = body.get("detail") or body.get("error") or body.get("message")
            if isinstance(detail, dict):
                detail = detail.get("message") or detail.get("code")
            if detail:
                return self._redact_secrets(detail)
        except (ValueError, TypeError):
            pass
        return self._redact_secrets(response.text[:300] or response.reason_phrase)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            response = await self._client.request(
                method, path.lstrip("/"), params=params, json=json
            )
        except httpx.HTTPError as exc:
            raise PriceProviderError(f"Primat kunde inte nås: {self._redact_secrets(exc)}") from exc
        if response.status_code in {401, 403}:
            raise PriceProviderAuthenticationError(
                f"Primat avvisade API-nyckeln: {self._error_message(response)}"
            )
        if response.status_code == 429:
            raise PriceProviderRateLimitError(
                f"Primats anropsgräns är nådd: {self._error_message(response)}"
            )
        content_type = response.headers.get("content-type", "").casefold()
        challenge_body = response.text[:4096].casefold()
        if "html" in content_type and any(
            marker in challenge_body for marker in _ACCESS_CHALLENGE_MARKERS
        ):
            raise PriceProviderAccessChallengeError(
                "Primat returnerade en access challenge; anropet stoppades utan bypass"
            )
        if response.is_error:
            raise PriceProviderError(
                f"Primat svarade {response.status_code}: {self._error_message(response)}"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise PriceProviderError("Primat returnerade ogiltig JSON") from exc
        if not isinstance(payload, dict):
            raise PriceProviderError("Primat returnerade ett oväntat svarsformat")
        challenge_detail = " ".join(
            str(payload.get(field) or "") for field in ("challenge", "error", "message", "detail")
        ).casefold()
        if any(marker in challenge_detail for marker in _ACCESS_CHALLENGE_MARKERS):
            raise PriceProviderAccessChallengeError(
                "Primat returnerade en access challenge; anropet stoppades utan bypass"
            )
        self._last_response_report = {
            "method": response.request.method,
            "host": response.request.url.host or "",
            "path": response.request.url.path,
            "status": response.status_code,
            "content_type": response.headers.get("content-type", "application/json"),
            "response_sha256": hashlib.sha256(response.content).hexdigest(),
        }
        return payload

    def last_response_metadata(self) -> dict[str, Any]:
        """Return only allowlisted transport facts for replay envelopes."""

        if self._last_response_report is None:
            raise PriceProviderError("Primat has no completed response metadata")
        return dict(self._last_response_report)

    def _parse_resolved_store(
        self,
        row: dict[str, Any],
        *,
        place: dict[str, Any],
    ) -> Store | None:
        if not _is_customer_context(row):
            return None
        chain = str(row.get("chain") or "").strip()
        native_id = str(row.get("store_id") or "").strip()
        key = str(row.get("key") or f"{chain}:{native_id}")
        if not chain or not native_id:
            return None
        try:
            return Store(
                store_id=key,
                name=str(row.get("name") or key),
                chain=chain,
                city=str(row.get("city") or place.get("locality") or "Lund"),
                # ``place`` describes the requested user location, not the
                # selected store. Never copy its postal code or centroid into
                # store identity fields used for physical mapping.
                postal_code=(str(row.get("postal_code")) if row.get("postal_code") else None),
                address=row.get("address"),
                latitude=row.get("latitude"),
                longitude=row.get("longitude"),
                distance_km=row.get("km"),
                tier=row.get("tier"),
                source_store_id=native_id,
                coverage=(
                    str(row.get("coverage")).strip() or None if row.get("coverage") else None
                ),
                price_context_type=(
                    str(row.get("price_context_type")).strip() or None
                    if row.get("price_context_type")
                    else None
                ),
                source_provenance=SourceProvenance(
                    source_provider=self.source_name,
                    source_channel="catalog",
                    source_snapshot_id=self._observation_id,
                    source_observed_at=self._observed_at,
                    chain=chain.casefold(),
                    store_id=key,
                    store_name=str(row.get("name") or key),
                    provider_store_id=native_id,
                    price_context=(
                        str(row.get("price_context_type")).strip() or None
                        if row.get("price_context_type")
                        else None
                    ),
                    coverage=(
                        str(row.get("coverage")).strip() or None if row.get("coverage") else None
                    ),
                ),
            )
        except (TypeError, ValueError):
            return None

    async def resolve_store_candidates(self, postal_code: str) -> PrimatStoreResolution:
        """Return every public customer context from one bounded resolve call.

        `find_stores` retains the consumer-facing default-selection behavior.
        This supplemental method exists for bounded identity discovery and does
        not silently convert unselected contexts into optimizer stores.
        """

        digits = "".join(character for character in postal_code if character.isdigit())
        if len(digits) != 5:
            raise ValueError("postal_code must contain exactly five digits")
        payload = await self._request("GET", "/stores/resolve", params={"postcode": digits})
        place = payload.get("place") or {}
        rows = payload.get("stores") or []
        if not isinstance(place, dict) or not isinstance(rows, list):
            raise PriceProviderError("Primat returnerade ett oväntat butikssvarsformat")
        selected = {
            str(value).strip()
            for value in (payload.get("default_selection") or [])
            if str(value).strip()
        }
        stores: list[Store] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            store = self._parse_resolved_store(row, place=place)
            if store is None:
                continue
            if row.get("selected") is True:
                selected.add(store.store_id)
            self._stores[store.store_id] = store
            stores.append(store)
        if not stores:
            raise PriceProviderError(f"Primat hittade inga publika butiker för {digits}")
        report = self._last_response_report
        if report is None:
            raise PriceProviderError("Primat saknar saniterad transportmetadata")
        return PrimatStoreResolution(
            postal_code=digits,
            place_city=(str(place.get("locality")) if place.get("locality") else None),
            raw_rows=len(rows),
            selected_context_ids=frozenset(selected),
            stores=tuple(store.model_copy(deep=True) for store in stores),
            observed_at=self._observed_at,
            source_snapshot_id=self._observation_id,
            response_sha256=str(report["response_sha256"]),
            response_status=int(report["status"]),
            response_content_type=str(report["content_type"]),
            response_host=str(report["host"]),
            response_path=str(report["path"]),
        )

    async def find_stores(self, postal_code: str) -> list[Store]:
        resolution = await self.resolve_store_candidates(postal_code)
        stores = list(resolution.stores)
        if resolution.selected_context_ids:
            stores = [
                store for store in stores if store.store_id in resolution.selected_context_ids
            ]
        if not stores:
            raise PriceProviderError(
                f"Primat hittade inga valda butiker för {resolution.postal_code}"
            )
        self._stores = {store.store_id: store for store in stores}
        return [store.model_copy(deep=True) for store in stores]

    def request_scoped_product_snapshot(self) -> tuple[Product, ...]:
        """Return one immutable, de-duplicated view of successful cached searches.

        This accessor deliberately exposes parsed domain products only. Query
        parameters, request headers, cookies and the bearer credential never
        enter the snapshot and callers cannot mutate the provider cache.
        """

        products: dict[tuple[str, str], Product] = {}
        for rows in self._product_search_cache.values():
            for product in rows:
                key = (product.store_id, product.product_id)
                previous = products.get(key)
                if previous is not None and previous != product:
                    raise PriceProviderError(
                        "Primats request-cache innehåller motstridiga produktrader"
                    )
                products[key] = product
        return tuple(
            products[key].model_copy(deep=True)
            for key in sorted(
                products,
                key=lambda item: (item[0].casefold(), item[1].casefold()),
            )
        )

    @staticmethod
    def _normalise_package(
        amount: Any,
        unit: Any,
        package: Any,
        name: str,
    ) -> tuple[float, str, QuantityConfidence] | None:
        conversions = {
            "g": (1, "g"),
            "gram": (1, "g"),
            "kg": (1000, "g"),
            "ml": (1, "ml"),
            "l": (1000, "ml"),
            "liter": (1000, "ml"),
            "dl": (100, "ml"),
            "cl": (10, "ml"),
            "st": (1, "st"),
            "styck": (1, "st"),
            "pcs": (1, "st"),
        }
        multiplicative_pattern = re.compile(
            r"(?<!\d)(\d+)\s*[x×]\s*(\d+(?:[.,]\d+)?)\s*"
            r"(kg|g|ml|cl|dl|l|st)(?![a-zåäö])",
            flags=re.IGNORECASE,
        )
        quantity_pattern = re.compile(
            r"(?<!\d)(\d+(?:[.,]\d+)?)\s*(kg|g|ml|cl|dl|l|st)(?![a-zåäö])",
            flags=re.IGNORECASE,
        )

        def visible_quantities(
            text: str,
        ) -> tuple[list[tuple[float, str, float]], list[tuple[float, str]]]:
            """Return multipacks and standalone quantities from one source field.

            Package and product-name text are kept separate so repeated catalogue
            metadata is harmless, while a genuinely composite name such as
            ``Matkit pasta 500 g sås 200 g`` remains visibly ambiguous.
            """

            multipacks: list[tuple[float, str, float]] = []
            spans: list[tuple[int, int]] = []
            for match in multiplicative_pattern.finditer(text):
                count = int(match.group(1))
                per_item = float(match.group(2).replace(",", "."))
                multiplier, canonical_unit = conversions[match.group(3).casefold()]
                if count > 0 and per_item > 0:
                    multipacks.append(
                        (count * per_item * multiplier, canonical_unit, per_item * multiplier)
                    )
                    spans.append(match.span())

            standalone: list[tuple[float, str]] = []
            for match in quantity_pattern.finditer(text):
                if any(start <= match.start() and match.end() <= end for start, end in spans):
                    continue
                parsed = float(match.group(1).replace(",", "."))
                multiplier, canonical_unit = conversions[match.group(2).casefold()]
                if parsed > 0:
                    standalone.append((parsed * multiplier, canonical_unit))
            return multipacks, standalone

        sources = [visible_quantities(str(value)) for value in (package, name) if value]
        multiplicative = {item for source_multipacks, _ in sources for item in source_multipacks}
        # Repeated package/name text is harmless, but conflicting multiplicative
        # quantities are not safe to guess between.
        if len({(total, canonical_unit) for total, canonical_unit, _ in multiplicative}) > 1:
            return None
        multipack = next(iter(multiplicative), None)

        try:
            quantity = float(str(amount).replace(",", "."))
        except (TypeError, ValueError):
            quantity = 0
        unit_key = str(unit or "").casefold().strip().rstrip(".")
        if amount is not None and (
            not isfinite(quantity) or quantity <= 0 or unit_key not in conversions
        ):
            return None

        def reasonable(value, base):
            return isfinite(value) and (
                1 <= value <= 1000 and value.is_integer()
                if base == "st"
                else 0.1 <= value <= 100000
            )

        if quantity > 0 and unit_key in conversions:
            multiplier, canonical_unit = conversions[unit_key]
            structured = quantity * multiplier
            if multipack is not None:
                total, multipack_unit, per_item = multipack
                if canonical_unit != multipack_unit:
                    return None
                if abs(structured - total) <= max(1e-6, total * 1e-9):
                    confidence = QuantityConfidence.EXACT
                elif abs(structured - per_item) <= max(1e-6, per_item * 1e-9):
                    structured = total
                    confidence = QuantityConfidence.DERIVED
                else:
                    return None
            else:
                confidence = QuantityConfidence.EXACT

            def source_supports_structured(
                _source_multipacks: list[tuple[float, str, float]],
                standalone: list[tuple[float, str]],
            ) -> bool:
                allowed = {structured}
                if multipack is not None:
                    allowed.add(multipack[2])
                if any(unit != canonical_unit for _, unit in standalone):
                    return False
                values = [value for value, _ in standalone]
                if not values:
                    return True
                if len(values) == 1 and all(
                    any(
                        abs(value - candidate) <= max(1e-6, candidate * 1e-9)
                        for candidate in allowed
                    )
                    for value in values
                ):
                    return True

                # A structured total can safely resolve named components only
                # when those components reconcile exactly to that total. If the
                # structured amount is also printed, exclude that one total
                # before summing the component amounts.
                components = [
                    value
                    for value in values
                    if abs(value - structured) > max(1e-6, structured * 1e-9)
                ]
                return bool(components) and abs(sum(components) - structured) <= max(
                    1e-6, structured * 1e-9
                )

            if not all(source_supports_structured(*source) for source in sources):
                return None
            if not reasonable(float(structured), canonical_unit):
                return None
            return structured, canonical_unit, confidence

        if multipack is not None:
            total, canonical_unit, per_item = multipack
            for _, standalone in sources:
                if any(unit != canonical_unit for _, unit in standalone):
                    return None
                if any(
                    abs(value - total) > max(1e-6, total * 1e-9)
                    and abs(value - per_item) > max(1e-6, per_item * 1e-9)
                    for value, _ in standalone
                ):
                    return None
            if not package or not reasonable(float(total), canonical_unit):
                return None
            return total, canonical_unit, QuantityConfidence.DERIVED

        candidates: set[tuple[float, str]] = set()
        for _, standalone in sources:
            if not standalone:
                continue
            # Without a structured total, choosing one component from a
            # multi-quantity product name would manufacture package semantics.
            if len(standalone) != 1:
                return None
            candidates.add(standalone[0])
        if len(candidates) != 1:
            return None
        parsed, canonical_unit = next(iter(candidates))
        if not package or not reasonable(float(parsed), canonical_unit):
            return None
        return parsed, canonical_unit, QuantityConfidence.DERIVED

    @staticmethod
    def _positive_float(value: Any) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if isfinite(number) and number > 0 else None

    @classmethod
    def _comparison_metadata(
        cls,
        row: dict[str, Any],
        prices: dict[str, Any],
    ) -> tuple[float | None, str | None]:
        """Preserve a comparison rate without turning it into package metadata."""

        comparison = prices.get("comparison")
        if not isinstance(comparison, dict):
            comparison = row.get("comparison")
        if not isinstance(comparison, dict):
            comparison = {}
        price = cls._positive_float(comparison.get("price") or row.get("comparison_price"))
        raw_unit = (
            str(comparison.get("unit") or row.get("comparison_unit") or "").casefold().strip()
        )
        compact_unit = re.sub(r"\s+", "", raw_unit).replace("sek", "kr")
        aliases = {
            "kg": "kg",
            "kr/kg": "kg",
            "l": "liter",
            "liter": "liter",
            "kr/l": "liter",
            "kr/liter": "liter",
            "st": "st",
            "styck": "st",
            "kr/st": "st",
            "kr/styck": "st",
        }
        unit = aliases.get(compact_unit)
        # ProductSemantics requires price and unit to travel as one fact. An
        # unrecognised unit is safer to omit than to silently reinterpret.
        if price is None or unit is None:
            return None, None
        return price, unit

    @staticmethod
    def _offer_sale_unit(label: str) -> str | None:
        """Return a unit only when an offer explicitly says how it is sold."""

        folded = label.casefold()
        if re.search(r"(?:kr|:-)?\s*/\s*kg(?=\s|[^a-zåäö]|$)", folded) or re.search(
            r"\bper\s*kg\b", folded
        ):
            return "kg"
        if re.search(r"(?:kr|:-)?\s*/\s*(?:st|styck)(?=\s|[^a-zåäö]|$)", folded) or re.search(
            r"\bper\s*(?:st|styck)\b", folded
        ):
            return "st"
        return None

    @staticmethod
    def _source_sale_unit(value: Any) -> str | None:
        """Normalize only an explicitly declared checkout-rate unit."""

        compact = re.sub(r"\s+", "", str(value or "").casefold()).replace("sek", "kr")
        aliases = {
            "kg": "kg",
            "kr/kg": "kg",
            "st": "st",
            "styck": "st",
            "kr/st": "st",
            "kr/styck": "st",
        }
        return aliases.get(compact)

    @staticmethod
    def _valid_gtin13(value: Any) -> str | None:
        digits = str(value or "").strip()
        if len(digits) != 13 or not digits.isdigit():
            return None
        weighted = sum(
            int(character) * (1 if index % 2 == 0 else 3)
            for index, character in enumerate(digits[:12])
        )
        expected = (10 - weighted % 10) % 10
        return digits if int(digits[-1]) == expected else None

    @classmethod
    def _gtin_kind(cls, row: dict[str, Any], product_id: str) -> str | None:
        gtin = cls._valid_gtin13(row.get("gtin")) or cls._valid_gtin13(product_id)
        if gtin is None:
            return None
        return "variable_measure" if 20 <= int(gtin[:2]) <= 29 else "fixed_item"

    @classmethod
    def _offer_purchase_semantics(
        cls,
        row: dict[str, Any],
        *,
        name: str,
        product_id: str,
        offer_label: str,
        eligible_offer_price: float | None,
        comparison_price: float | None,
        comparison_unit: str | None,
    ) -> tuple[str | None, bool]:
        """Separate a package fact from a checkout-rate fact in one label.

        Primat can expose a label such as ``1.5 kg | /kg`` while ``offer.price``
        is the total price of that 1.5 kg package. The ``/kg`` fragment alone
        must not turn that package total into a kg rate. Matching source, label
        and fixed-GTIN quantities establish the physical package; reconciliation
        against the independent comparison rate determines whether offer.price
        is the package total or a genuine rate.
        """

        offer_unit = cls._offer_sale_unit(offer_label)
        source_package = cls._normalise_package(
            row.get("amount"), row.get("unit"), row.get("package"), name
        )
        label_package = cls._normalise_package(None, None, offer_label, "")
        quantities_match = (
            source_package is not None
            and label_package is not None
            and source_package[1] == label_package[1]
            and abs(source_package[0] - label_package[0]) <= max(1e-6, source_package[0] * 1e-9)
        )
        fixed_package_evidence = bool(
            quantities_match and cls._gtin_kind(row, product_id) == "fixed_item"
        )
        if (
            offer_unit == "kg"
            and fixed_package_evidence
            and source_package is not None
            and source_package[1] == "g"
            and eligible_offer_price is not None
            and comparison_price is not None
            and comparison_unit == "kg"
        ):
            package_total = comparison_price * source_package[0] / 1000
            if abs(eligible_offer_price - package_total) <= max(0.05, eligible_offer_price * 0.02):
                return None, True
        return offer_unit, fixed_package_evidence

    @classmethod
    def _fresh_product_kind(cls, name: str, category: Any) -> str | None:
        folded_name = _search_text(name)
        folded_category = _search_text(str(category or ""))
        # The broad ICA root includes cheese but also milk, eggs and butter.
        # Only the actual descendant category can establish cheese semantics.
        segments = str(category or "").split(">")
        if len(segments) > 1 and _search_text(segments[0]).strip() == "mejeri ost":
            folded_category = _search_text(" > ".join(segments[1:]))
        name_tokens = set(folded_name.split())
        produce_tokens = {
            "paprika",
            "paprikor",
            "spetspaprika",
            "spetspaprikor",
            "morot",
            "morotter",
            "lok",
            "lokar",
            "matlok",
            "matlokar",
            "rodlok",
            "rodlokar",
            "vitlok",
            "vitlokar",
            "purjolok",
            "purjolokar",
            "potatis",
            "potatisar",
            "avokado",
            "avokador",
            "avokados",
            "avocado",
            "avocados",
            "aubergine",
            "auberginer",
            "zucchini",
            "zucchinier",
            "gurka",
            "gurkor",
            "tomat",
            "tomater",
            "apple",
            "applen",
            "paron",
            "banan",
            "bananer",
            "apelsin",
            "apelsiner",
            "citron",
            "citroner",
            "lime",
            "broccoli",
            "blomkal",
            "vitkal",
            "kalrot",
            "rotselleri",
            "palsternacka",
        }
        processed_tokens = {
            "baguett",
            "baguetter",
            "chips",
            "juice",
            "krossade",
            "must",
            "pulver",
            "pure",
            "sallad",
            "sas",
            "snack",
            "soppa",
        }

        # Whole-produce identity is stronger than Primat's category depth. A
        # live row such as ``Små morötter`` can carry an unfamiliar, nested
        # category; its normal catalogue GTIN and structured 400 g amount still
        # do not prove that shoppers buy one fixed 400 g package. Conversely,
        # frozen/processed or visibly packaged products are catalogue packages,
        # so their structured quantity may be used by the fixed-item path.
        clearly_non_loose = bool(
            name_tokens & processed_tokens
            or cls._looks_explicitly_packaged(name, None)
            or name_tokens
            & {
                "fryst",
                "frysta",
                "frozen",
                "djupfryst",
                "konserv",
                "konserverad",
                "inlagd",
                "torkad",
            }
            or any(
                marker in folded_category
                for marker in (
                    "frys",
                    "fryst",
                    "djupfryst",
                    "konserv",
                    "inlagd",
                    "forpackad",
                    "forpackat",
                )
            )
        )
        named_whole_produce = bool(name_tokens & produce_tokens)
        categorised_as_produce = any(
            marker in folded_category for marker in ("frukt", "grönt", "gront", "blommor")
        )
        if (
            (named_whole_produce or categorised_as_produce)
            and not name_tokens & processed_tokens
            and not clearly_non_loose
        ):
            return "produce"
        if any(
            marker in folded_category
            for marker in (
                "kött",
                "kott",
                "fågel",
                "fagel",
                "fisk",
                "skaldjur",
                "ost",
            )
        ):
            return "variable_package"
        # Some live rows have a shallow category. These strong food names are
        # used only after a verified variable-measure GTIN, never on their own.
        if any(marker in folded_name for marker in ("kyckling", "lax", "torsk")):
            return "variable_package"
        return None

    @classmethod
    def _looks_explicitly_packaged(cls, name: str, package: Any) -> bool:
        # A quantity visible in the consumer-facing name ("Morötter 1 kg")
        # is package evidence. A structured ``amount``/``package`` value alone
        # is not: live class-1 produce rows use those fields for price reference
        # weights even when shoppers are not buying that fixed package.
        if cls._normalise_package(None, None, name, "") is not None:
            return True
        folded = _search_text(f"{name} {package or ''}")
        packaging_token = re.search(r"(?:^|\s)(?:pase|forpackning|ask|nat|trag)(?=\s|$)", folded)
        explicit_multipack = re.search(r"(?:^|\s)\d+\s*pack(?=\s|$)", folded)
        return packaging_token is not None or explicit_multipack is not None

    @staticmethod
    def _is_drainable_food(row: dict[str, Any], name: str) -> bool:
        folded_name = _search_text(name)
        category_text = _search_text(str(row.get("category") or ""))
        folded = f"{folded_name} {category_text}"
        drainable = any(
            marker in folded
            for marker in (
                "bönor",
                "bonor",
                "kikärtor",
                "kikartor",
                "majs",
                "ärtor",
                "artor",
                "tonfisk",
            )
        ) or any(
            marker in category_text
            for marker in ("gronsakskonserv", "inlagda gronsaker", "picklade gronsaker")
        )
        if "lins" in folded_name and not any(
            marker in folded_name for marker in ("kokt", "färdigkokt", "burk", "tetra", "konserv")
        ):
            return False
        return drainable

    @classmethod
    def _usable_quantity_metadata(
        cls,
        row: dict[str, Any],
        name: str,
        package_quantity: float,
        package_unit: str,
        package_confidence: QuantityConfidence,
        *,
        regular_price: float,
        comparison_price: float | None,
        comparison_unit: str | None,
    ) -> tuple[float, str, float, str, QuantityConfidence, bool]:
        """Return gross and usable quantities without claiming unavailable facts."""

        explicit_usable: tuple[float, str, QuantityConfidence] | None = None
        for amount_key, unit_key in (
            ("usable_quantity", "usable_unit"),
            ("drained_weight", "drained_unit"),
            ("drained_amount", "drained_unit"),
        ):
            value = row.get(amount_key)
            if value is None:
                continue
            explicit_usable = cls._normalise_package(
                value,
                row.get(unit_key) or package_unit,
                value if isinstance(value, str) else None,
                "",
            )
            if explicit_usable is not None:
                explicit_usable = (
                    explicit_usable[0],
                    explicit_usable[1],
                    QuantityConfidence.EXACT,
                )
                break

        usable_quantity = explicit_usable[0] if explicit_usable is not None else package_quantity
        usable_unit = explicit_usable[1] if explicit_usable is not None else package_unit
        confidence = explicit_usable[2] if explicit_usable is not None else package_confidence

        # Primat's comparison amount can be the drained weight while the
        # consumer-facing product name still carries the gross can weight.
        # Only treat that larger visible quantity as gross for clearly
        # drainable foods; otherwise a second number in a name may describe a
        # serving or prepared yield.
        drainable = cls._is_drainable_food(row, name)
        # A whole vegetable placed in Primat's vegetable-preserve category is
        # normally packed in brine or another liquid.  Its catalogue amount
        # proves the checkout package, not the drained recipe quantity.  Keep
        # this role-based (whole produce + preserve category) rather than a
        # product-name blacklist so equivalent carrots, onions, peppers, etc.
        # fail closed in the same way when no drained-weight field is present.
        # Primat categories can be broad (for example "bönor och linser")
        # and are shared by dry bags and canned goods. A visibly dry lentil
        # product must therefore not inherit the category's drained-weight
        # heuristic. Canned/cooked lentils remain eligible when the product
        # name itself says so.
        visible = cls._normalise_package(None, None, name, "")
        if (
            explicit_usable is None
            and drainable
            and visible is not None
            and visible[1] == package_unit
            and visible[0] > package_quantity
        ):
            usable_quantity = package_quantity
            usable_unit = package_unit
            package_quantity = visible[0]
            confidence = QuantityConfidence.DERIVED
        elif explicit_usable is None and drainable and package_unit in {"g", "ml"}:
            # Price arithmetic cannot prove whether Primat's amount is gross,
            # drained or merely the comparison basis. Without an explicit
            # usable field or an independently visible larger gross quantity,
            # preserve the amount as metadata but keep it outside verified
            # baskets. UNKNOWN is safer than circularly "proving" quantity from
            # regular_price / comparison_price.
            usable_quantity = package_quantity
            usable_unit = package_unit
            confidence = QuantityConfidence.UNKNOWN

        variable_weight = any(
            row.get(key) is True
            for key in ("variable_weight", "is_variable_weight", "sold_by_weight")
        )

        return (
            package_quantity,
            package_unit,
            usable_quantity,
            usable_unit,
            confidence,
            variable_weight,
        )

    @classmethod
    def _purchase_metadata(
        cls,
        row: dict[str, Any],
        *,
        name: str,
        product_id: str,
        regular_price: float,
        comparison_price: float | None,
        comparison_unit: str | None,
        explicit_offer_unit: str | None,
        offer_package_evidence: bool,
        active_offer_price: float | None,
    ) -> dict[str, Any]:
        """Interpret Primat sale facts without confusing rates and packages."""

        package = cls._normalise_package(
            row.get("amount"), row.get("unit"), row.get("package"), name
        )
        if package is None and cls._is_drainable_food(row, name):
            # Drainable catalogue rows can explicitly expose usable amount in
            # ``amount`` while their name exposes a larger gross can weight.
            # Recover only that role-specific, one-directional relationship;
            # generic conflicts (for example Pasta amount=500 g, name=1 kg)
            # remain UNKNOWN.
            structured = cls._normalise_package(row.get("amount"), row.get("unit"), None, "")
            visible_gross = cls._normalise_package(None, None, name, "")
            if (
                structured is not None
                and visible_gross is not None
                and structured[1] == visible_gross[1]
                and visible_gross[0] > structured[0]
            ):
                package = structured
        gtin_kind = cls._gtin_kind(row, product_id)
        fresh_kind = cls._fresh_product_kind(name, row.get("category"))
        raw_explicit_model = row.get("sale_model")
        explicit_model_text = str(raw_explicit_model or "").casefold().strip()
        explicit_model_present = raw_explicit_model is not None and bool(
            str(raw_explicit_model).strip()
        )
        try:
            explicit_model = SaleModel(explicit_model_text) if explicit_model_present else None
        except ValueError:
            explicit_model = None
        source_sale_unit = cls._source_sale_unit(row.get("sale_unit") or row.get("price_unit"))
        source_piece_price = cls._positive_float(row.get("piece_price"))

        variable_rate_evidence = (
            package is not None
            and package[1] == "g"
            and comparison_price is not None
            and comparison_unit == "kg"
            and abs(comparison_price * package[0] / 1000 - regular_price)
            <= max(0.05, regular_price * 0.02)
        )
        produce_rate_evidence = (
            comparison_price is not None
            and comparison_unit == "kg"
            and abs(comparison_price - regular_price) <= max(0.05, regular_price * 0.02)
        )
        source_declares_fixed = (
            explicit_model == SaleModel.FIXED_PACKAGE or row.get("fixed_package") is True
        )
        # A normal fixed-item GTIN identifies a catalogue item, not the
        # physical meaning of Primat's amount field. Fresh produce still needs
        # visible quantity/packaging evidence or an explicit source declaration
        # before it can be costed as a fixed package.
        safe_fresh_package = (
            cls._looks_explicitly_packaged(name, row.get("package")) or offer_package_evidence
        )
        fixed_from_amount = package is not None and (
            source_declares_fixed or fresh_kind is None or safe_fresh_package
        )

        if explicit_model_present:
            # An explicit source contract wins over heuristics. Unsupported or
            # explicit UNKNOWN values remain unknown rather than falling through
            # to an amount-based guess. Model-specific evidence is checked below.
            sale_model = explicit_model or SaleModel.UNKNOWN
        elif row.get("fixed_package") is True:
            sale_model = SaleModel.FIXED_PACKAGE
        elif (
            gtin_kind == "variable_measure"
            and fresh_kind == "variable_package"
            and variable_rate_evidence
        ):
            sale_model = SaleModel.VARIABLE_WEIGHT_PACKAGE
        elif (
            gtin_kind == "variable_measure" and fresh_kind == "produce" and produce_rate_evidence
        ) or row.get("sold_by_weight") is True:
            sale_model = SaleModel.SOLD_BY_WEIGHT
        elif row.get("variable_weight") is True or row.get("is_variable_weight") is True:
            sale_model = SaleModel.VARIABLE_WEIGHT_PACKAGE
        elif fixed_from_amount:
            # A rate label describes the offer, not the physical sale model.
            # ``80 kr/kg`` on a visibly fixed 500 g package must remain one
            # 500 g package; the rate can be converted to its package price
            # later when the dimensions make that deterministic.
            sale_model = SaleModel.FIXED_PACKAGE
        elif explicit_offer_unit == "st":
            sale_model = SaleModel.SOLD_BY_PIECE
        elif explicit_offer_unit == "kg":
            sale_model = SaleModel.SOLD_BY_WEIGHT
        else:
            sale_model = SaleModel.UNKNOWN

        common: dict[str, Any] = {
            "sale_model": sale_model,
            "sale_price": regular_price,
            "sale_unit": None,
            "package_quantity": None,
            "package_unit": None,
            "usable_quantity": None,
            "usable_unit": None,
            "piece_price": None,
            "estimated_piece_weight": None,
            "quantity_confidence": QuantityConfidence.UNKNOWN,
            "variable_weight": False,
            "comparison_price": comparison_price,
            "comparison_unit": comparison_unit,
        }

        if sale_model == SaleModel.UNKNOWN:
            return common

        if sale_model == SaleModel.SOLD_BY_WEIGHT:
            rate: float | None = None
            if explicit_offer_unit == "kg" and active_offer_price is not None:
                rate = active_offer_price
            elif comparison_price is not None and comparison_unit == "kg":
                rate = comparison_price
            elif source_sale_unit == "kg":
                rate = regular_price
            if rate is None:
                # ``sold_by_weight`` identifies the physical sale model, but an
                # ordinary item/package price without a rate unit is not kr/kg.
                common["sale_model"] = SaleModel.UNKNOWN
                return common
            common.update(
                sale_price=rate,
                sale_unit="kg",
                quantity_confidence=QuantityConfidence.DERIVED,
                variable_weight=True,
            )
            return common

        if sale_model == SaleModel.SOLD_BY_PIECE:
            piece_price: float | None = None
            if explicit_offer_unit == "st" and active_offer_price is not None:
                piece_price = active_offer_price
            elif source_piece_price is not None:
                piece_price = source_piece_price
            elif source_sale_unit == "st":
                piece_price = regular_price
            elif comparison_price is not None and comparison_unit == "st":
                piece_price = comparison_price
            if piece_price is None or (
                package is not None and package[1] == "st" and package[0] != 1
            ):
                common["sale_model"] = SaleModel.UNKNOWN
                return common
            if package is not None and package[1] in {"g", "ml"}:
                common.update(
                    package_quantity=1,
                    package_unit="st",
                    usable_quantity=package[0],
                    usable_unit=package[1],
                    estimated_piece_weight=package[0],
                    estimated_piece_weight_unit=package[1],
                    quantity_confidence=QuantityConfidence.ESTIMATED,
                )
            else:
                common.update(
                    package_quantity=1,
                    package_unit="st",
                    usable_quantity=1,
                    usable_unit="st",
                    quantity_confidence=QuantityConfidence.DERIVED,
                )
            common.update(
                sale_price=piece_price,
                sale_unit="st",
                piece_price=piece_price,
            )
            return common

        if sale_model == SaleModel.VARIABLE_WEIGHT_PACKAGE:
            if package is None or package[1] != "g":
                common["sale_model"] = SaleModel.UNKNOWN
                return common
            rate: float | None = None
            if explicit_offer_unit == "kg" and active_offer_price is not None:
                rate = active_offer_price
            elif comparison_price is not None and comparison_unit == "kg":
                rate = comparison_price
            elif source_sale_unit == "kg":
                rate = regular_price
            common.update(
                package_quantity=package[0],
                package_unit=package[1],
                usable_quantity=package[0],
                usable_unit=package[1],
                # With a rate, sale_price is kr/kg. Otherwise regular_price is
                # retained as the representative package/item price. Never tag
                # that ordinary price as kg and accidentally prorate it.
                sale_price=rate if rate is not None else regular_price,
                sale_unit="kg" if rate is not None else "package",
                quantity_confidence=QuantityConfidence.ESTIMATED,
                variable_weight=True,
            )
            return common

        if package is None:
            common["sale_model"] = SaleModel.UNKNOWN
            return common
        (
            package_quantity,
            package_unit,
            usable_quantity,
            usable_unit,
            quantity_confidence,
            _,
        ) = cls._usable_quantity_metadata(
            row,
            name,
            package[0],
            package[1],
            package[2],
            regular_price=regular_price,
            comparison_price=comparison_price,
            comparison_unit=comparison_unit,
        )
        common.update(
            package_quantity=package_quantity,
            package_unit=package_unit,
            usable_quantity=usable_quantity,
            usable_unit=usable_unit,
            sale_price=regular_price,
            sale_unit="package",
            quantity_confidence=quantity_confidence,
        )
        return common

    @classmethod
    def _fixed_package_offer_price(
        cls,
        purchase: dict[str, Any],
        *,
        offer_unit: str | None,
        offer_price: float | None,
    ) -> float | None:
        """Convert an explicit unit-rate offer to one fixed package.

        ``kr/st`` means one catalogue item (for example one 12-pack of eggs),
        not one internal recipe piece. A ``kr/kg`` rate can only be converted
        when the fixed package has an explicit gram quantity. Any dimensional
        mismatch is ignored rather than guessed.
        """

        if (
            purchase.get("sale_model") != SaleModel.FIXED_PACKAGE
            or offer_unit is None
            or offer_price is None
        ):
            return None
        if offer_unit == "st":
            return offer_price
        if offer_unit == "kg" and purchase.get("package_unit") == "g":
            quantity = cls._positive_float(purchase.get("package_quantity"))
            if quantity is not None:
                return round(offer_price * quantity / 1000, 4)
        return None

    @staticmethod
    def _promotion_rejection(row: dict[str, Any]) -> str | None:
        prices = row.get("prices") if isinstance(row.get("prices"), dict) else {}
        offer = prices.get("offer") if isinstance(prices.get("offer"), dict) else {}
        axes = [
            str(obj.get(key) or "").casefold()
            for obj in (row, offer)
            for key in ("eligibility", "audience", "scope", "type")
        ]
        label = _search_text(str(offer.get("label") or row.get("offer_label") or ""))
        if any(x in {"user_specific", "personal", "personalized"} for x in axes) or re.search(
            r"\b(personligt|personlig|utvalt for dig)\b", label
        ):
            return "user_specific"
        if any(x in {"category", "category_level"} for x in axes) or re.search(
            r"\b(hela sortimentet|alla varor|valfria|utvalda)\b", label
        ):
            return "category_applicability_unproven"
        # Label-only group prices have been seen on category-linked ICA rows.
        # They cannot become a normal single package campaign. Require the
        # documented structured quantity and matching per-unit price as well.
        multibuy = re.search(r"\b(\d+)\s+for\s+(\d+(?:[.,]\d+)?)", label)
        if multibuy:
            count = int(multibuy[1])
            total = float(multibuy[2].replace(",", "."))
            supported = False
            for key in ("multiprice", "member_multiprice"):
                facts = prices.get(key) or {}
                if not isinstance(facts, dict):
                    continue
                per_unit = PrimatPriceProvider._positive_float(facts.get("price"))
                if (
                    count >= 2
                    and facts.get("quantity") == count
                    and per_unit is not None
                    and abs(per_unit * count - total) <= 0.05
                ):
                    supported = True
            if not supported:
                return "multibuy_without_structured_quantity"
        for field in ("valid_from", "valid_until"):
            value = offer.get(field)
            if value:
                try:
                    datetime.fromisoformat(str(value))
                except ValueError:
                    return "invalid_promotion_date"
        return None

    def _parse_product(
        self,
        row: dict[str, Any],
    ) -> Product | None:
        name = str(row.get("name") or "").strip()
        chain = str(row.get("chain") or "").strip()
        native_store_id = str(row.get("store_id") or "").strip()
        product_id = str(row.get("product_id") or row.get("id") or "").strip()
        if not all((name, chain, native_store_id, product_id)):
            return None
        if row.get("available") is False:
            return None
        if str(row.get("eligibility") or "").casefold() == "user_specific":
            return None
        store_id = f"{chain}:{native_store_id}"

        prices = row.get("prices") if isinstance(row.get("prices"), dict) else {}
        offer = prices.get("offer") if isinstance(prices.get("offer"), dict) else {}
        multiprice = prices.get("multiprice") if isinstance(prices.get("multiprice"), dict) else {}
        member_multiprice = (
            prices.get("member_multiprice")
            if isinstance(prices.get("member_multiprice"), dict)
            else {}
        )

        regular = self._positive_float(prices.get("regular") or row.get("price"))
        offer_price = self._positive_float(offer.get("price") or row.get("offer_price"))
        member_price = self._positive_float(prices.get("member") or row.get("member_price"))
        multi_unit_price = self._positive_float(multiprice.get("price") or row.get("multi_price"))
        multi_count = multiprice.get("quantity") or row.get("multi_count")
        try:
            multi_count = int(multi_count)
        except (TypeError, ValueError):
            multi_count = 0
        member_multi_unit = self._positive_float(
            member_multiprice.get("price") or row.get("member_multi_price")
        )
        member_multi_count = member_multiprice.get("quantity") or row.get("member_multi_count")
        try:
            member_multi_count = int(member_multi_count)
        except (TypeError, ValueError):
            member_multi_count = 0

        # ``prices.offer`` describes the active promotion and repeats its
        # per-unit price. It is not necessarily an unconditional package price:
        # it can point at member, multiprice, or member_multiprice. Classify it
        # against those structured facts before creating a campaign offer.
        def same_price(left: float | None, right: float | None) -> bool:
            return left is not None and right is not None and abs(left - right) < 0.005

        offer_is_public_multi = multi_count >= 2 and same_price(offer_price, multi_unit_price)
        offer_is_member_multi = member_multi_count >= 2 and same_price(
            offer_price, member_multi_unit
        )
        offer_is_member = (
            not offer_is_public_multi
            and not offer_is_member_multi
            and same_price(offer_price, member_price)
        )
        offer_is_public_single = (
            offer_price is not None
            and not offer_is_public_multi
            and not offer_is_member_multi
            and not offer_is_member
        )
        offer_label = str(offer.get("label") or row.get("offer_label") or "").strip()
        promotion_rejection = self._promotion_rejection(row)
        if promotion_rejection:
            offer_price = member_price = multi_unit_price = member_multi_unit = None
            offer_is_public_single = offer_is_member = False
            offer_is_public_multi = offer_is_member_multi = False
        raw_max_quantity = offer.get("max_quantity") or row.get("offer_max_quantity")
        try:
            max_quantity = int(raw_max_quantity) if raw_max_quantity is not None else None
        except (TypeError, ValueError, OverflowError):
            max_quantity = None
        if max_quantity is not None and max_quantity < 1:
            max_quantity = None
        valid_from = offer.get("valid_from")
        valid_to = offer.get("valid_until") or row.get("offer_valid_until")

        def local_date(value):
            if not value:
                return None
            parsed = datetime.fromisoformat(str(value))
            return (
                parsed.astimezone(ZoneInfo("Europe/Stockholm")).date()
                if parsed.tzinfo
                else parsed.date()
            )

        try:
            from_date = local_date(valid_from)
        except ValueError:
            from_date = None
        try:
            to_date = local_date(valid_to)
        except ValueError:
            to_date = None
        today = datetime.now(tz=ZoneInfo("Europe/Stockholm")).date()
        offer_is_active = not (
            (from_date is not None and today < from_date)
            or (to_date is not None and today > to_date)
        )
        eligible_offer_price = (
            offer_price
            if offer_is_active
            and (offer_is_public_single or self.use_member_prices and offer_is_member)
            else None
        )
        comparison_price, comparison_unit = self._comparison_metadata(row, prices)
        explicit_offer_unit, offer_package_evidence = self._offer_purchase_semantics(
            row,
            name=name,
            product_id=product_id,
            offer_label=offer_label,
            eligible_offer_price=eligible_offer_price,
            comparison_price=comparison_price,
            comparison_unit=comparison_unit,
        )

        # Offer-only stores can lack a regular fact. A standalone public package
        # offer is safely purchasable; a genuine unit-rate offer cannot become a
        # package price until the model supplies an independent ordinary fact.
        if (
            regular is None
            and offer_is_public_single
            and offer_is_active
            and explicit_offer_unit is None
        ):
            regular = offer_price
        if regular is None:
            return None

        active_unit_offer_price = eligible_offer_price if explicit_offer_unit is not None else None
        purchase = self._purchase_metadata(
            row,
            name=name,
            product_id=product_id,
            regular_price=regular,
            comparison_price=comparison_price,
            comparison_unit=comparison_unit,
            explicit_offer_unit=explicit_offer_unit,
            offer_package_evidence=offer_package_evidence,
            active_offer_price=active_unit_offer_price,
        )
        fixed_unit_offer_price = self._fixed_package_offer_price(
            purchase,
            offer_unit=explicit_offer_unit,
            offer_price=offer_price,
        )
        public_checkout_offer_price = (
            offer_price if explicit_offer_unit is None else fixed_unit_offer_price
        )

        offers: list[OfferMetadata] = []
        if (
            offer_is_public_single
            and public_checkout_offer_price is not None
            and public_checkout_offer_price <= regular
        ):
            offers.append(
                OfferMetadata(
                    kind=OfferKind.CAMPAIGN,
                    description=offer_label or "Kampanjpris",
                    price=public_checkout_offer_price,
                    max_quantity=max_quantity,
                    valid_from=from_date,
                    valid_to=to_date,
                )
            )
        if member_price is not None and explicit_offer_unit is None:
            offers.append(
                OfferMetadata(
                    kind=OfferKind.MEMBER,
                    description=(offer_label if offer_is_member and offer_label else "Medlemspris"),
                    price=member_price,
                    max_quantity=max_quantity,
                    eligibility=PromotionEligibility.MEMBER,
                    mechanism=PromotionMechanism.SALE_PRICE,
                    membership_program=MembershipProgram.from_value(chain),
                    member_program=f"{chain} medlem",
                    valid_from=from_date if offer_is_member else None,
                    valid_to=to_date if offer_is_member else None,
                )
            )
        if multi_unit_price is not None and multi_count >= 2:
            offers.append(
                OfferMetadata(
                    kind=OfferKind.MULTIPACK,
                    description=(
                        offer_label
                        if offer_is_public_multi and offer_label
                        else f"{multi_count} för {multi_unit_price * multi_count:.2f} kr"
                    ),
                    # Domain semantics: price covers the complete qualifying group.
                    price=multi_unit_price * multi_count,
                    required_packages=multi_count,
                    max_quantity=max_quantity,
                    valid_from=from_date if offer_is_public_multi else None,
                    valid_to=to_date if offer_is_public_multi else None,
                )
            )
        if member_multi_unit is not None and member_multi_count >= 2:
            offers.append(
                OfferMetadata(
                    kind=OfferKind.MULTIPACK,
                    description=(
                        offer_label
                        if offer_is_member_multi and offer_label
                        else (
                            f"Medlemspris: {member_multi_count} för "
                            f"{member_multi_unit * member_multi_count:.2f} kr"
                        )
                    ),
                    price=member_multi_unit * member_multi_count,
                    required_packages=member_multi_count,
                    max_quantity=max_quantity,
                    eligibility=PromotionEligibility.MEMBER,
                    mechanism=PromotionMechanism.MULTIBUY,
                    membership_program=MembershipProgram.from_value(chain),
                    member_program=f"{chain} medlem",
                    valid_from=from_date if offer_is_member_multi else None,
                    valid_to=to_date if offer_is_member_multi else None,
                )
            )

        store = self._stores.get(store_id)
        # A ranked catalogue search can legitimately return adjacent products
        # (for example taco sauce for a ``tortillas`` query).  The query is not
        # product metadata and must therefore never be used as the product's
        # canonical identity.  ProductMatcher subsequently verifies the
        # ingredient against the product name and category.
        canonical = canonicalize_ingredient_name(name)
        try:
            gtin = normalize_gtin(row.get("gtin") or row.get("ean")).normalized_gtin
        except InvalidGtinError:
            gtin = None
        provenance = SourceProvenance(
            source_provider=self.source_name,
            source_channel="catalog",
            source_snapshot_id=self._observation_id,
            source_observed_at=self._observed_at,
            chain=chain.casefold(),
            store_id=store_id,
            store_name=store.name if store else store_id,
            provider_store_id=native_store_id,
            price_context=store.price_context_type if store else None,
            coverage=store.coverage or store.tier if store else None,
            semantic_confidence=str(purchase.get("semantic_confidence") or "").casefold() or None,
            quantity_confidence=str(purchase.get("quantity_confidence") or "").casefold() or None,
        )
        try:
            product = Product(
                product_id=product_id,
                name=name,
                canonical_name=canonical,
                category=str(row.get("category") or canonical),
                store_id=store_id,
                store_name=store.name if store else store_id,
                price=regular,
                effective_price=regular,
                member_price=(member_price if explicit_offer_unit is None else None),
                offers=offers,
                brand=row.get("brand"),
                chain=chain.casefold(),
                gtin=gtin,
                price_context_type=store.price_context_type if store else None,
                coverage=store.coverage or store.tier if store else None,
                search_terms=[str(row.get("brand") or ""), str(row.get("category") or "")],
                source_provenance=provenance,
                **purchase,
            )
        except (TypeError, ValueError):
            return None
        return self.apply_price_policy([product])[0]

    async def search_products(self, query: str, store_ids: list[str]) -> list[Product]:
        if not query.strip() or not store_ids:
            return []
        unique_store_ids = list(dict.fromkeys(store_ids))
        cache_key = (_search_text(query), tuple(sorted(unique_store_ids)))
        cached = self._product_search_cache.get(cache_key)
        if cached is not None:
            return list(cached)

        products: dict[tuple[str, str], Product] = {}
        for store_batch in _chunks(unique_store_ids, 15):
            payload = await self._request(
                "GET",
                "/products",
                params={"q": query.strip(), "stores": ",".join(store_batch), "limit": 100},
            )
            for row in payload.get("data") or []:
                if not isinstance(row, dict):
                    continue
                product = self._parse_product(row)
                if product is not None:
                    products[(product.store_id, product.product_id)] = product
        result = sorted(
            products.values(),
            key=lambda product: (
                (
                    product.normalized_unit_price
                    if product.normalized_unit_price is not None
                    else inf
                ),
                product.store_name.casefold(),
                product.name.casefold(),
            ),
        )
        self._product_search_cache[cache_key] = tuple(result)
        return result

    async def get_store_products(self, store_id: str) -> list[Product]:
        """Read the paginated price catalogue and keep rows with safe package metadata.

        Primat's flat ``/prices`` rows currently omit explicit amount/unit fields.
        The adapter therefore only exposes rows whose package can be parsed from
        the structured package/name text; the meal pipeline uses targeted
        ``/products`` searches, which include full metadata.
        """

        cursor: str | None = None
        products: list[Product] = []
        seen_cursors: set[str] = set()
        while True:
            params: dict[str, Any] = {"stores": store_id, "limit": 1000}
            if cursor:
                params["cursor"] = cursor
            payload = await self._request("GET", "/prices", params=params)
            for row in payload.get("data") or []:
                if isinstance(row, dict):
                    product = self._parse_product(row)
                    if product is not None:
                        products.append(product)
            next_cursor = payload.get("next_cursor")
            if not next_cursor or str(next_cursor) in seen_cursors:
                break
            cursor = str(next_cursor)
            seen_cursors.add(cursor)
        return products

    async def get_offers(self, store_id: str) -> list[Product]:
        payload = await self._request(
            "GET", "/deals", params={"stores": store_id, "limit": 500, "lookback_days": 14}
        )
        products: list[Product] = []
        for row in payload.get("data") or []:
            if isinstance(row, dict):
                product = self._parse_product(row)
                if product is not None:
                    products.append(product)
        return products

    async def get_cheap_products(self, store_ids: list[str], limit: int = 100) -> list[Product]:
        """Primat-specific fast path used by the cheap-products service when available."""

        products: dict[tuple[str, str], Product] = {}
        for store_batch in _chunks(list(dict.fromkeys(store_ids)), 15):
            payload = await self._request(
                "GET",
                "/cheap",
                params={"stores": ",".join(store_batch), "limit": min(max(limit, 1), 500)},
            )
            for row in payload.get("data") or []:
                if isinstance(row, dict):
                    product = self._parse_product(row)
                    if product is not None:
                        products[(product.store_id, product.product_id)] = product
        return list(products.values())
