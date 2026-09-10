from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from grocery_data.app.connectors.ica.discovery import (
    DiscoveryBudget,
    IcaDiscoveryPlanner,
    SafePageNavigator,
)
from grocery_data.app.services.ica_recipe_coverage import (
    RECIPE_QUERY_ALIASES,
    RECIPE_RELEVANT_INGREDIENTS,
    RecipeCoverageReport,
    RecipeQueryCoverageBenchmark,
)
from grocery_data.app.services.ica_registry import IcaProductRegistry
from grocery_data.app.storage import IcaEnrichmentRunModel


@dataclass(frozen=True, slots=True)
class QueryEnrichmentResult:
    coverage: RecipeCoverageReport
    pages_visited: int
    observations_merged: int
    challenge_encountered: bool


class ICAQueryEnrichmentService:
    """Run a bounded public-page refresh; transport remains injectable and replayable."""

    def __init__(
        self,
        session: Session,
        navigator: SafePageNavigator,
        *,
        max_page_navigations: int = 10,
    ) -> None:
        self.session = session
        self.navigator = navigator
        self.max_page_navigations = max_page_navigations

    async def enrich(
        self,
        store_id: str,
        canonical_ingredients: list[str],
        *,
        max_price_age_days: int = 7,
    ) -> QueryEnrichmentResult:
        started_at = datetime.now(UTC)
        pages = [
            f"search?q={RECIPE_QUERY_ALIASES[item][0]}"
            for item in dict.fromkeys(canonical_ingredients)
            if item in RECIPE_QUERY_ALIASES
        ]
        planner = IcaDiscoveryPlanner(
            DiscoveryBudget(
                max_page_navigations=self.max_page_navigations,
                max_category_pages=0,
                max_search_pages=self.max_page_navigations,
            )
        )
        run = await planner.run(self.navigator, category_pages=[], search_pages=pages)
        merged = (
            IcaProductRegistry(self.session).ingest_many(run.observations)
            if run.observations
            else 0
        )
        coverage = RecipeQueryCoverageBenchmark(self.session).run(
            store_id,
            ingredients=tuple(
                item
                for item in RECIPE_RELEVANT_INGREDIENTS
                if item.canonical in canonical_ingredients
            ),
            max_price_age_days=max_price_age_days,
        )
        self.session.add(
            IcaEnrichmentRunModel(
                store_id=store_id,
                status="degraded" if run.challenge_encountered else "healthy",
                challenge_encountered=run.challenge_encountered,
                pages_visited=run.pages_visited,
                product_ids_seen=run.product_ids_seen,
                price_observations=run.price_observations,
                route_metrics=[],
                started_at=started_at,
                finished_at=datetime.now(UTC),
            )
        )
        self.session.flush()
        return QueryEnrichmentResult(
            coverage=coverage,
            pages_visited=run.pages_visited,
            observations_merged=merged,
            challenge_encountered=run.challenge_encountered,
        )
