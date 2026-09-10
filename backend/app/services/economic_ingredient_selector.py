"""Build a compact, meal-relevant economic ingredient pool from local prices."""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from time import perf_counter

from app.models.ingredient import NormalizedIngredient
from app.models.product import (
    CanonicalUnit,
    CheapIngredient,
    Product,
    ProductCandidate,
    QuantityConfidence,
    SaleModel,
)
from app.models.store import Store
from app.providers.base import GroceryPriceProvider
from app.services.basket_calculator import BasketCalculator
from app.services.basket_optimizer import BasketVerificationPolicy
from app.services.ingredient_normalizer import _search_text
from app.services.ingredient_taxonomy import (
    INGREDIENT_TAXONOMY,
    IngredientCategory,
    IngredientTaxonomyEntry,
)
from app.services.performance_trace import (
    increment_performance_counter,
    performance_span,
    record_performance_seconds,
)
from app.services.product_matcher import ProductMatcher
from pydantic import BaseModel, ConfigDict, Field

from grocery_data.app.domain.promotion_pricing import PromotionEligibility

NormalizedPriceUnit = str

# Preserve products that become checkout winners only after several dinners
# share an ingredient.  The order deliberately prioritises ordinary one-meal
# demand, a common multipack threshold, and the five- and seven-meal endpoints
# before an intermediate quantity. The configurable per-store cap remains the
# final hard bound.
_REPRESENTATIVE_REQUIREMENT_MULTIPLIERS: tuple[int, ...] = (1, 2, 5, 7, 3)
_SELECTOR_CACHE_VERSION = "membership-aware-economic-selector-v1"


class EconomicProductExample(BaseModel):
    """A real product illustrating the local price signal for an ingredient."""

    model_config = ConfigDict(frozen=True)

    product_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    store_id: str = Field(min_length=1)
    store: str = Field(min_length=1)
    package_quantity: float | None = Field(default=None, gt=0)
    package_unit: CanonicalUnit | None = None
    usable_quantity: float | None = Field(default=None, gt=0)
    usable_unit: CanonicalUnit | None = None
    quantity_confidence: QuantityConfidence
    price: float = Field(gt=0)
    effective_price: float = Field(gt=0)
    normalized_unit_price: float = Field(gt=0)
    normalized_unit: NormalizedPriceUnit
    match_score: float = Field(ge=0, le=1)
    economic_score: float = Field(gt=0)
    is_offer: bool = False


class EconomicIngredientSignal(BaseModel):
    """Ingredient-level signal safe to expose to a recipe generator or debug API."""

    model_config = ConfigDict(frozen=True)

    canonical: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    category: IngredientCategory
    best_local_unit_price: float = Field(gt=0)
    normalized_unit: NormalizedPriceUnit
    economic_score: float = Field(gt=0)
    is_offer: bool = False
    example_products: list[EconomicProductExample] = Field(min_length=1)

    @property
    def canonical_name(self) -> str:
        """Compatibility alias used by deterministic recipe generators."""

        return self.canonical

    @property
    def ingredient(self) -> str:
        """Compatibility alias matching the legacy ``CheapIngredient`` model."""

        return self.canonical


class EconomicIngredientPool(BaseModel):
    """Public ingredient signals plus exact internal purchasing candidates."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    ingredients: list[EconomicIngredientSignal] = Field(default_factory=list)
    candidates_by_name: dict[str, list[ProductCandidate]] = Field(
        default_factory=dict,
        exclude=True,
        repr=False,
    )
    semantic_candidates_by_name: dict[str, list[ProductCandidate]] = Field(
        default_factory=dict,
        exclude=True,
        repr=False,
        description=(
            "Full validated pre-pruning semantic cache for offline benchmarks and "
            "quantity-specific matching; meal search keeps using candidates_by_name."
        ),
    )
    matched_candidates_by_name: dict[str, list[ProductCandidate]] = Field(
        default_factory=dict,
        exclude=True,
        repr=False,
        description=(
            "Full ProductMatcher output before taxonomy/economic pruning, persisted "
            "for exact arbitrary-quantity basket replay."
        ),
    )
    projection_shortlist_support_by_name: dict[str, list[ProductCandidate]] = Field(
        default_factory=dict,
        exclude=True,
        repr=False,
        description=(
            "Process-local public top-K and quantity winners used for exact "
            "membership delta ranking."
        ),
    )
    projection_semantics_identity: str | None = Field(
        default=None,
        exclude=True,
        repr=False,
        description=(
            "Request-runtime marker for a full selector-validated semantic map; "
            "never part of the shared serialized artifact."
        ),
    )
    search_queries_executed: int = Field(default=0, ge=0)
    products_considered: int = Field(default=0, ge=0)

    @property
    def signal_by_name(self) -> dict[str, EconomicIngredientSignal]:
        return {signal.canonical: signal for signal in self.ingredients}

    def to_cheap_ingredients(self) -> list[CheapIngredient]:
        """Adapt the richer pool to the existing recipe-generator/API signal."""

        result: list[CheapIngredient] = []
        for signal in self.ingredients:
            product = signal.example_products[0]
            result.append(
                CheapIngredient(
                    ingredient=signal.canonical,
                    product=product.name,
                    product_id=product.product_id,
                    store=product.store,
                    store_id=product.store_id,
                    price=product.effective_price,
                    unit_price=product.normalized_unit_price,
                    unit=product.normalized_unit,  # type: ignore[arg-type]
                    is_offer=product.is_offer,
                )
            )
        return result


def _normalized_unit(candidate: ProductCandidate) -> str:
    sale_unit = (candidate.sale_unit or "").casefold().strip()
    comparison_unit = (candidate.comparison_unit or "").casefold().strip()
    if candidate.sale_model == SaleModel.SOLD_BY_PIECE:
        if candidate.estimated_piece_weight is None:
            return "st"
        return "liter" if candidate.estimated_piece_weight_unit == "ml" else "kg"
    rate_unit = sale_unit or comparison_unit
    if rate_unit == "kg":
        return "kg"
    if rate_unit in {"l", "liter", "litre"}:
        return "liter"
    if candidate.usable_unit is None:
        raise ValueError("candidate has no comparable purchase unit")
    return {"g": "kg", "ml": "liter", "st": "st"}[candidate.usable_unit]


def _normalized_unit_price(candidate: ProductCandidate) -> float:
    sale_unit = (candidate.sale_unit or "").casefold().strip()
    comparison_unit = (candidate.comparison_unit or "").casefold().strip()
    if candidate.sale_model in {
        SaleModel.SOLD_BY_WEIGHT,
        SaleModel.VARIABLE_WEIGHT_PACKAGE,
    }:
        if sale_unit in {"kg", "l", "liter", "litre"}:
            return candidate.sale_price
        if candidate.comparison_price is not None and comparison_unit in {
            "kg",
            "l",
            "liter",
            "litre",
        }:
            return candidate.comparison_price
    if candidate.sale_model == SaleModel.SOLD_BY_PIECE:
        piece_price = candidate.piece_price or candidate.effective_price
        if candidate.estimated_piece_weight is not None:
            multiplier = 1000 if candidate.estimated_piece_weight_unit in {"g", "ml"} else 1
            return piece_price * multiplier / candidate.estimated_piece_weight
        return piece_price
    if candidate.usable_quantity is None or candidate.usable_unit is None:
        raise ValueError("candidate has no comparable usable quantity")
    multiplier = 1000 if candidate.usable_unit in {"g", "ml"} else 1
    return float(candidate.effective_price) * multiplier / candidate.usable_quantity


def _has_active_offer(candidate: ProductCandidate) -> bool:
    return any(offer.is_active() for offer in candidate.offers)


def _economic_score(
    entry: IngredientTaxonomyEntry,
    candidate: ProductCandidate,
) -> float:
    """Blend comparable unit price, deal signal and likely package usefulness."""

    unit_price = _normalized_unit_price(candidate)
    requirement = NormalizedIngredient(
        canonical_name=entry.canonical,
        required_quantity=entry.typical_meal_quantity,
        unit=entry.expected_unit,
    )
    increment_performance_counter("package_calculations")
    quote = BasketCalculator().quote_item(requirement, candidate)
    member_offer_applied = (
        quote.applied_offer is not None
        and quote.applied_offer.eligibility is PromotionEligibility.MEMBER
    )
    if (
        member_offer_applied
        and candidate.sale_model is SaleModel.FIXED_PACKAGE
        and candidate.usable_quantity is not None
        and candidate.usable_unit is not None
    ):
        # ``effective_price`` is deliberately a one-package price, so a
        # conditional 3-for-30 contract must not be flattened into 10/st.
        # For ranking only, use the exact quote for the taxonomy's typical
        # requirement; BasketCalculator already enforces thresholds, residual
        # packages and promotion caps.
        multiplier = 1000 if candidate.usable_unit in {"g", "ml"} else 1
        unit_price = (
            float(quote.unit_price) * multiplier / candidate.usable_quantity
        )
    surplus_ratio = quote.waste_quantity / max(entry.typical_meal_quantity, 1)
    # Package fit is deliberately modest: exact basket calculation, not this
    # heuristic, makes the final purchasing decision.
    package_adjustment = 1 + min(surplus_ratio, 2.0) * 0.10
    eligible_deal_adjustment = (
        0.94
        if candidate.effective_price < candidate.price
        or member_offer_applied
        else 1.0
    )
    return unit_price * package_adjustment * eligible_deal_adjustment / entry.utility_weight


def _passes_taxonomy_identity(
    entry: IngredientTaxonomyEntry,
    candidate: ProductCandidate,
) -> bool:
    """Apply category/product-type evidence after the general matcher."""

    product_name = _search_text(candidate.product_name)
    if any(_search_text(term) in product_name for term in entry.exclusion_terms):
        return False
    if not entry.identity_terms:
        return True
    return any(_search_text(term) in product_name for term in entry.identity_terms)


def _candidate_key(
    entry: IngredientTaxonomyEntry,
    candidate: ProductCandidate,
) -> tuple[float, float, float, str, str]:
    return (
        _economic_score(entry, candidate),
        _normalized_unit_price(candidate),
        candidate.effective_price,
        candidate.product_name.casefold(),
        candidate.product_id,
    )


class EconomicIngredientSelector:
    """Select useful cheap ingredients without treating pantry fillers as meals."""

    def __init__(
        self,
        *,
        taxonomy: Sequence[IngredientTaxonomyEntry] = INGREDIENT_TAXONOMY,
        matcher: ProductMatcher | None = None,
        verification_policy: BasketVerificationPolicy | None = None,
        concurrency: int = 6,
        max_searches: int = 45,
        max_candidates_per_store: int = 4,
        max_examples_per_ingredient: int = 4,
        max_ingredients_per_category: Mapping[IngredientCategory | str, int] | None = None,
    ) -> None:
        if concurrency < 1:
            raise ValueError("concurrency must be at least one")
        if max_searches < 1:
            raise ValueError("max_searches must be at least one")
        if max_candidates_per_store < 1:
            raise ValueError("max_candidates_per_store must be at least one")
        if max_examples_per_ingredient < 1:
            raise ValueError("max_examples_per_ingredient must be at least one")

        entries = tuple(taxonomy)
        canonical_names = [entry.canonical for entry in entries]
        if len(set(canonical_names)) != len(canonical_names):
            raise ValueError("taxonomy contains duplicate canonical ingredients")
        unique_queries = {entry.search_query.casefold().strip() for entry in entries}
        if len(unique_queries) > max_searches:
            raise ValueError(
                f"taxonomy requires {len(unique_queries)} searches; limit is {max_searches}"
            )

        self.taxonomy = entries
        self.matcher = matcher or ProductMatcher()
        self.basket_calculator = BasketCalculator()
        self.verification_policy = (
            verification_policy or BasketVerificationPolicy.legacy_compatible()
        )
        self.concurrency = concurrency
        self.max_candidates_per_store = max_candidates_per_store
        self.max_examples_per_ingredient = max_examples_per_ingredient
        self.max_ingredients_per_category = {
            IngredientCategory(category): limit
            for category, limit in (max_ingredients_per_category or {}).items()
        }
        if any(limit < 1 for limit in self.max_ingredients_per_category.values()):
            raise ValueError("category limits must be at least one")

    @property
    def cache_identity(self) -> str:
        """Fingerprint every policy that can change a request-local shortlist."""

        payload = {
            "version": _SELECTOR_CACHE_VERSION,
            "taxonomy": [asdict(entry) for entry in self.taxonomy],
            "matcher": {
                "minimum_score": self.matcher.minimum_score,
                "allow_medium_semantic": self.matcher.allow_medium_semantic,
            },
            "verification_policy": asdict(self.verification_policy),
            "max_candidates_per_store": self.max_candidates_per_store,
            "max_examples_per_ingredient": self.max_examples_per_ingredient,
            "max_ingredients_per_category": {
                category.value: limit
                for category, limit in sorted(
                    self.max_ingredients_per_category.items(),
                    key=lambda row: row[0].value,
                )
            },
            "representative_requirement_multipliers": (
                _REPRESENTATIVE_REQUIREMENT_MULTIPLIERS
            ),
        }
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return f"economic-selector:{hashlib.sha256(encoded).hexdigest()}"

    async def select(
        self,
        provider: GroceryPriceProvider,
        stores: Sequence[Store],
    ) -> EconomicIngredientPool:
        started = perf_counter()
        store_ids = [store.store_id for store in stores]
        if not store_ids or not self.taxonomy:
            return EconomicIngredientPool()
        increment_performance_counter(
            "canonical_ingredients_considered",
            len(self.taxonomy),
        )

        # Several taxonomy entries may intentionally share a provider query.
        # Search it once and validate the result independently for each entry.
        query_order = tuple(dict.fromkeys(entry.search_query for entry in self.taxonomy))
        semaphore = asyncio.Semaphore(self.concurrency)

        async def search(query: str) -> tuple[str, list[Product]]:
            async with semaphore:
                return query, await provider.search_products(query, store_ids)

        with performance_span("source_reconciliation"):
            search_results = dict(await asyncio.gather(*(search(query) for query in query_order)))
        products_considered = sum(len(products) for products in search_results.values())
        increment_performance_counter("products_loaded", products_considered)

        signals_by_category: dict[
            IngredientCategory,
            list[
                tuple[
                    EconomicIngredientSignal,
                    list[ProductCandidate],
                    list[ProductCandidate],
                ]
            ],
        ] = defaultdict(list)
        matched_candidates_by_name: dict[str, list[ProductCandidate]] = {}

        for entry in self.taxonomy:
            products = search_results[entry.search_query]
            ingredient = NormalizedIngredient(
                canonical_name=entry.canonical,
                display_name=entry.display_name,
                required_quantity=entry.typical_meal_quantity,
                unit=entry.expected_unit,
            )
            with performance_span("canonical_matching"):
                matched = self.matcher.match(ingredient, products, store_ids=store_ids)
            matched_candidates_by_name[entry.canonical] = list(matched)
            all_semantic_candidates = self.validate_semantic_candidates(
                entry,
                matched,
            )
            if not all_semantic_candidates:
                continue

            # Preserve several alternatives in every store for exact package
            # optimization; never collapse the internal map to the cheapest row.
            by_store: dict[str, list[ProductCandidate]] = defaultdict(list)
            for candidate in all_semantic_candidates:
                by_store[candidate.store_id].append(candidate)

            candidates: list[ProductCandidate] = []
            for store_candidates in by_store.values():
                candidates.extend(self._select_store_candidates(entry, store_candidates))
            candidates.sort(key=lambda candidate: _candidate_key(entry, candidate))
            if not candidates:
                continue

            examples = self._select_examples(entry, candidates)
            best = examples[0]
            signal = EconomicIngredientSignal(
                canonical=entry.canonical,
                display_name=entry.display_name,
                category=entry.category,
                best_local_unit_price=best.normalized_unit_price,
                normalized_unit=best.normalized_unit,
                economic_score=best.economic_score,
                is_offer=best.is_offer,
                example_products=examples,
            )
            signals_by_category[entry.category].append(
                (signal, candidates, all_semantic_candidates)
            )

        ingredients: list[EconomicIngredientSignal] = []
        candidates_by_name: dict[str, list[ProductCandidate]] = {}
        semantic_candidates_by_name: dict[str, list[ProductCandidate]] = {}
        for category in IngredientCategory:
            rows = sorted(
                signals_by_category.get(category, []),
                key=lambda row: (row[0].economic_score, row[0].canonical),
            )
            limit = self.max_ingredients_per_category.get(category)
            if limit is not None:
                rows = rows[:limit]
            for signal, candidates, semantic_candidates in rows:
                ingredients.append(signal)
                candidates_by_name[signal.canonical] = candidates
                semantic_candidates_by_name[signal.canonical] = semantic_candidates

        pool = EconomicIngredientPool(
            ingredients=ingredients,
            candidates_by_name=candidates_by_name,
            semantic_candidates_by_name=semantic_candidates_by_name,
            matched_candidates_by_name=matched_candidates_by_name,
            search_queries_executed=len(query_order),
            products_considered=products_considered,
        )
        increment_performance_counter(
            "eligible_products",
            sum(len(rows) for rows in candidates_by_name.values()),
        )
        increment_performance_counter("canonical_mappings", len(candidates_by_name))
        record_performance_seconds("economic_ingredient_pool", perf_counter() - started)
        return pool

    def validate_semantic_candidates(
        self,
        entry: IngredientTaxonomyEntry,
        candidates: Sequence[ProductCandidate],
    ) -> list[ProductCandidate]:
        """Apply the selector's non-economic gates and stable identity dedupe.

        The prepared shared pool retains the full matcher output so a request-level
        pricing context can re-run economic ranking without copying PriceUniverse.
        Keeping taxonomy identity, quantity resolution and verification in this one
        method prevents the request projection from growing a second acceptance
        policy.
        """

        ingredient = NormalizedIngredient(
            canonical_name=entry.canonical,
            display_name=entry.display_name,
            required_quantity=entry.typical_meal_quantity,
            unit=entry.expected_unit,
        )
        validated: list[ProductCandidate] = []
        for candidate in candidates:
            if not _passes_taxonomy_identity(entry, candidate):
                continue
            try:
                increment_performance_counter("package_calculations")
                quote = self.basket_calculator.quote_item(ingredient, candidate)
            except ValueError:
                continue
            if self.verification_policy.allows_quote(quote):
                validated.append(candidate)

        deduplicated: dict[tuple[str, str], ProductCandidate] = {}
        for candidate in validated:
            key = (candidate.store_id, candidate.product_id)
            previous = deduplicated.get(key)
            if previous is None or _candidate_key(entry, candidate) < _candidate_key(
                entry,
                previous,
            ):
                deduplicated[key] = candidate
        return sorted(
            deduplicated.values(),
            key=lambda candidate: _candidate_key(entry, candidate),
        )

    def _select_store_candidates(
        self,
        entry: IngredientTaxonomyEntry,
        candidates: Sequence[ProductCandidate],
    ) -> list[ProductCandidate]:
        """Keep exact checkout winners for both meal and weekly quantities.

        Ranking only by a representative four-portion meal can discard a bulk
        package or conditional multipack that becomes cheapest once several
        recipes are aggregated.  Quote a few bounded requirement levels with
        the same deterministic calculator used by the basket optimizer, retain
        their winners, and fill any remaining slots by the economic heuristic.
        """

        selected, _support = self._select_store_candidates_with_support(
            entry,
            candidates,
        )
        return selected

    def _select_store_candidates_with_support(
        self,
        entry: IngredientTaxonomyEntry,
        candidates: Sequence[ProductCandidate],
    ) -> tuple[list[ProductCandidate], list[ProductCandidate]]:
        """Return the historical shortlist and its exact public support rows.

        Selection preserves the original early-stop rule byte-for-byte. The
        additional support set contains the public top-K ranking rows and the
        winner for every representative demand. It is advisory process-local
        state and cannot change the public shortlist itself.
        """

        ordered = sorted(candidates, key=lambda candidate: _candidate_key(entry, candidate))
        selected: dict[tuple[str, str], ProductCandidate] = {}
        support: dict[tuple[str, str], ProductCandidate] = {
            (candidate.store_id, candidate.product_id): candidate
            for candidate in ordered[: self.max_candidates_per_store]
        }
        selection_open = True
        for multiplier in _REPRESENTATIVE_REQUIREMENT_MULTIPLIERS:
            requirement = NormalizedIngredient(
                canonical_name=entry.canonical,
                display_name=entry.display_name,
                required_quantity=entry.typical_meal_quantity * multiplier,
                unit=entry.expected_unit,
            )
            quoted = []
            for candidate in ordered:
                try:
                    increment_performance_counter("package_calculations")
                    quote = self.basket_calculator.quote_item(requirement, candidate)
                except ValueError:
                    continue
                quoted.append((candidate, quote))
            if quoted:
                winner = min(
                    quoted,
                    key=lambda row: (
                        row[1].total_price,
                        -row[0].match_score,
                        row[1].waste_quantity,
                        row[0].product_name.casefold(),
                        row[0].store_id,
                        row[0].product_id,
                    ),
                )[0]
                identity = (winner.store_id, winner.product_id)
                support[identity] = winner
                if selection_open:
                    selected[identity] = winner
                    if len(selected) >= self.max_candidates_per_store:
                        selection_open = False

        for candidate in ordered:
            selected.setdefault((candidate.store_id, candidate.product_id), candidate)
            if len(selected) >= self.max_candidates_per_store:
                break
        return (
            sorted(selected.values(), key=lambda candidate: _candidate_key(entry, candidate)),
            sorted(support.values(), key=lambda candidate: _candidate_key(entry, candidate)),
        )

    def _select_examples(
        self,
        entry: IngredientTaxonomyEntry,
        candidates: Sequence[ProductCandidate],
    ) -> list[EconomicProductExample]:
        # Prefer geographic variety in public examples, then fill remaining
        # slots with other economical package sizes.
        chosen: list[ProductCandidate] = []
        used_stores: set[str] = set()
        for candidate in candidates:
            if candidate.store_id in used_stores:
                continue
            chosen.append(candidate)
            used_stores.add(candidate.store_id)
            if len(chosen) == self.max_examples_per_ingredient:
                break
        if len(chosen) < self.max_examples_per_ingredient:
            chosen_keys = {(item.store_id, item.product_id) for item in chosen}
            for candidate in candidates:
                if (candidate.store_id, candidate.product_id) in chosen_keys:
                    continue
                chosen.append(candidate)
                if len(chosen) == self.max_examples_per_ingredient:
                    break

        examples = [self._example(entry, candidate) for candidate in chosen]
        examples.sort(key=lambda example: (example.economic_score, example.product_id))
        return examples

    @staticmethod
    def _example(
        entry: IngredientTaxonomyEntry,
        candidate: ProductCandidate,
    ) -> EconomicProductExample:
        return EconomicProductExample(
            product_id=candidate.product_id,
            name=candidate.product_name,
            store_id=candidate.store_id,
            store=candidate.store_name,
            package_quantity=candidate.package_quantity,
            package_unit=candidate.package_unit,
            usable_quantity=candidate.usable_quantity,
            usable_unit=candidate.usable_unit,
            quantity_confidence=candidate.quantity_confidence,
            price=candidate.price,
            effective_price=candidate.effective_price,
            normalized_unit_price=round(_normalized_unit_price(candidate), 2),
            normalized_unit=_normalized_unit(candidate),
            match_score=candidate.match_score,
            economic_score=round(_economic_score(entry, candidate), 4),
            is_offer=(candidate.effective_price < candidate.price or _has_active_offer(candidate)),
        )


async def select_economic_ingredients(
    provider: GroceryPriceProvider,
    stores: Sequence[Store],
) -> EconomicIngredientPool:
    """Small functional wrapper for scripts and dependency wiring."""

    return await EconomicIngredientSelector().select(provider, stores)


__all__ = [
    "EconomicIngredientPool",
    "EconomicIngredientSelector",
    "EconomicIngredientSignal",
    "EconomicProductExample",
    "select_economic_ingredients",
]
