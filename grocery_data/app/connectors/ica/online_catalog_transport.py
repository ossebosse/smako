from __future__ import annotations

from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from typing import Protocol, runtime_checkable

from grocery_data.app.connectors.ica.online_catalog_models import (
    IcaBatchResult,
    IcaProductPage,
)
from grocery_data.app.domain import RawBatch, RawFetch


@runtime_checkable
class IcaOnlineCollectionTransport(Protocol):
    """Transport boundary for ICA's modern online-catalogue collector.

    Implementations may use ordinary anonymous HTTP or a fresh ephemeral
    browser context.  The connector and parser deliberately depend only on
    this high-level contract: both transports must return the same sanitized
    :class:`RawFetch` documents and parsed page/batch envelopes.  Replay never
    owns an implementation of this protocol and therefore remains completely
    network- and browser-free.

    The policy attributes are part of the boundary because the connector must
    audit full-crawl authority without inspecting HTTP- or browser-specific
    state.
    """

    @property
    def allow_full_crawl(self) -> bool: ...

    @property
    def max_categories(self) -> int | None: ...

    @property
    def max_pages_per_category(self) -> int | None: ...

    @property
    def max_batches_per_page(self) -> int | None: ...

    @property
    def product_batch_size(self) -> int | None: ...

    @property
    def requests_per_second(self) -> float: ...

    @property
    def max_concurrency(self) -> int: ...

    @property
    def allowed_context_ids(self) -> AbstractSet[str]: ...

    @property
    def context_mappings(self) -> Mapping[str, str]: ...

    async def fetch_context(self, region_id: str) -> RawBatch: ...

    async def fetch_product_page(
        self,
        region_id: str,
        category_id: str,
        *,
        page_token: str | None = None,
        page_index: int = 0,
    ) -> tuple[RawFetch, IcaProductPage]: ...

    async def fetch_product_batch(
        self,
        region_id: str,
        product_ids: Sequence[str],
        *,
        category_id: str,
        page_index: int,
        batch_index: int,
    ) -> tuple[RawFetch, IcaBatchResult]: ...

    async def fetch_catalog(self, region_id: str) -> RawBatch: ...

    async def aclose(self) -> None: ...


__all__ = ["IcaOnlineCollectionTransport"]
