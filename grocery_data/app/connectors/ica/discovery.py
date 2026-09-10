from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from grocery_data.app.domain import IcaRegistryObservation

DEFAULT_SEARCH_SEEDS = (
    "pasta",
    "ris",
    "potatis",
    "mjölk",
    "ägg",
    "kyckling",
    "kött",
    "fisk",
    "ost",
    "bröd",
    "frukt",
    "grönsaker",
    "dryck",
    "fryst",
)


@dataclass(frozen=True, slots=True)
class DiscoveryBudget:
    max_page_navigations: int = 5
    max_category_pages: int = 3
    max_search_pages: int = 2


@dataclass(frozen=True, slots=True)
class DiscoveryPageResult:
    page_identifier: str
    product_ids: frozenset[str]
    decorated_products: int
    price_observations: int
    challenge_detected: bool = False
    observations: tuple[IcaRegistryObservation, ...] = ()


class SafePageNavigator(Protocol):
    async def navigate(self, page_identifier: str) -> DiscoveryPageResult: ...


@dataclass(frozen=True, slots=True)
class DiscoveryRunResult:
    pages_visited: int
    product_ids_seen: int
    decorated_products: int
    price_observations: int
    challenge_encountered: bool
    stopped_early: bool
    observations: tuple[IcaRegistryObservation, ...] = ()


@dataclass(frozen=True, slots=True)
class EnrichmentCandidate:
    external_product_id: str
    recipe_relevant: bool
    semantic_score: float
    price_missing_or_stale: bool
    quantity_missing: bool


def prioritize_enrichment(
    candidates: list[EnrichmentCandidate],
    *,
    limit: int,
) -> list[EnrichmentCandidate]:
    """Select a small deterministic detail-page budget; no navigation occurs here."""

    return sorted(
        candidates,
        key=lambda item: (
            not item.recipe_relevant,
            -item.semantic_score,
            not item.price_missing_or_stale,
            not item.quantity_missing,
            item.external_product_id,
        ),
    )[:limit]


class IcaDiscoveryPlanner:
    """Low-budget deterministic scheduler; it never retries an access challenge."""

    def __init__(self, budget: DiscoveryBudget | None = None) -> None:
        self.budget = budget or DiscoveryBudget()

    async def run(
        self,
        navigator: SafePageNavigator,
        *,
        category_pages: list[str],
        search_pages: list[str],
    ) -> DiscoveryRunResult:
        planned = [
            *category_pages[: self.budget.max_category_pages],
            *search_pages[: self.budget.max_search_pages],
        ][: self.budget.max_page_navigations]
        seen: set[str] = set()
        decorated = prices = visited = 0
        challenge = False
        observations: list[IcaRegistryObservation] = []
        for page in planned:
            result = await navigator.navigate(page)
            visited += 1
            seen.update(result.product_ids)
            decorated += result.decorated_products
            prices += result.price_observations
            observations.extend(result.observations)
            if result.challenge_detected:
                challenge = True
                break
        return DiscoveryRunResult(
            pages_visited=visited,
            product_ids_seen=len(seen),
            decorated_products=decorated,
            price_observations=prices,
            challenge_encountered=challenge,
            stopped_early=challenge and visited < len(planned),
            observations=tuple(observations),
        )
