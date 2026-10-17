"""Brute-force one-store and bounded multi-store basket optimisation."""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from dataclasses import replace as dataclass_replace
from decimal import Decimal, getcontext
from itertools import combinations
from threading import RLock
from time import perf_counter
from typing import Any

from app.errors import IncompleteBasketError
from app.models.basket import (
    BasketItem,
    BasketVerificationStatus,
    OptimizedBasket,
    OptimizedStoreGroup,
    StoreBasket,
)
from app.models.ingredient import NormalizedIngredient
from app.models.product import (
    ProductCandidate,
    QuantityConfidence,
    SaleModel,
    SemanticConfidence,
)
from app.models.store import Store
from app.services.basket_calculator import (
    BasketCalculator,
    BasketItemQuote,
    GroupPricingError,
    money,
)
from app.services.ingredient_normalizer import (
    canonicalize_ingredient_name,
)
from app.services.performance_trace import (
    increment_performance_counter,
    record_performance_seconds,
)
from app.services.price_universe import PackageCostCache, PriceUniverse

type _CandidateFingerprint = tuple[object, ...]
type _QuoteCacheKey = tuple[str, Decimal, str, _CandidateFingerprint]
type _QuoteSetKey = tuple[str, Decimal, str, int]
type _QuoteSelectionKey = tuple[_QuoteSetKey, tuple[str, ...]]
type _QuoteSubsetVectorKey = tuple[_QuoteSetKey, tuple[str, ...], int]


_VERIFICATION_RANK: dict[BasketVerificationStatus, int] = {
    BasketVerificationStatus.VERIFIED: 0,
    BasketVerificationStatus.VERIFIED_WITH_ESTIMATES: 1,
    BasketVerificationStatus.UNVERIFIED: 2,
    BasketVerificationStatus.INVALID: 3,
}


_MAX_GROUP_COMBINATIONS = 200000
_MAX_PROMOTION_STRUCTURE_ROWS = 256
_MAX_PROMOTION_STRUCTURE_CANDIDATES = 32768


class QuoteSelectionRejected(IncompleteBasketError):
    """The exact winning checkout failed a caller's pre-materialization check."""


def _promotion_structure(rows, session=None):
    """Index only frozen candidate fields within the existing quote scope.

    Offer lists are mutable even on frozen candidates. Cache which candidates
    lack an ordinary price, but read their current offers/caps on every use.
    Source validation and joint checkout still run through their usual paths.
    """
    cacheable = session is not None and isinstance(rows, tuple)
    if cacheable:
        cached = session.promotion_structure_rows.get(id(rows))
        if cached is not None and cached[0] is rows:
            return cached[1], cached[2]
    grouped, offer_only = [], []
    for candidate in rows:
        cacheable = (cacheable and type(candidate) is ProductCandidate
                     and isinstance(candidate.promotion_groups, tuple))
        if candidate.promotion_groups:
            grouped.append(candidate)
        if candidate.price is None:
            offer_only.append(candidate)
    result = (tuple(grouped), tuple(offer_only))
    if cacheable and len(rows) <= _MAX_PROMOTION_STRUCTURE_CANDIDATES:
        if (len(session.promotion_structure_rows) >= _MAX_PROMOTION_STRUCTURE_ROWS
                or session.promotion_structure_candidates + len(rows)
                > _MAX_PROMOTION_STRUCTURE_CANDIDATES):
            session.promotion_structure_rows.clear()
            session.promotion_structure_candidates = 0
        session.promotion_structure_rows[id(rows)] = (rows, *result)
        session.promotion_structure_candidates += len(rows)
    return result


def _has_coupled_checkout(candidates_by_name, required_names=None, *, session=None):
    """Use joint search only where separate lines share a source constraint.

    A single normalized ingredient already aggregates all recipe quantities;
    its ordinary quote enforces an offer-only cap. Enumerating every store
    product combination merely because one such offer exists would destroy
    the bounded store-subset path without adding correctness.
    """
    # The shared municipal pool also contains aliases absent from this basket.
    # Follow the same direct/canonical lookup as _ingredient_candidates: only
    # two actual requested lines can jointly consume an offer's product cap.
    selected = None
    if required_names is not None:
        selected = set()
        for name in required_names:
            if name in candidates_by_name:
                selected.add(name)
            else:
                canonical = canonicalize_ingredient_name(str(name))
                match = next((key for key in candidates_by_name
                              if canonicalize_ingredient_name(str(key)) == canonical), None)
                if match is not None:
                    selected.add(match)
    constrained = set()
    for name, rows in candidates_by_name.items():
        identities = set()
        if session is not None and isinstance(rows, tuple):
            grouped, offer_only = _promotion_structure(rows, session)
            if grouped:
                return True
            candidates = offer_only
        else:
            candidates = rows
        for candidate in candidates:
            if candidate.promotion_groups:
                return True
            if (selected is None or name in selected) and candidate.price is None and any(o.max_quantity is not None for o in candidate.offers):
                identities.add((candidate.store_id, candidate.product_id))
        if constrained & identities:
            return True
        constrained.update(identities)
    return False


@dataclass(frozen=True, slots=True)
class BasketVerificationPolicy:
    """Eligibility policy applied before any price comparison.

    Field defaults are the strict production policy: exact/high semantics,
    known sale/quantity models, and estimates with an explicit warning status.
    ``BasketOptimizer`` uses :meth:`legacy_compatible` only when no policy is
    passed, preserving old hand-built fixtures while callers migrate.
    """

    allow_medium_semantic: bool = False
    allow_estimated_quantities: bool = True
    allow_unknown_quantities: bool = False
    allow_unknown_sale_model: bool = False
    allow_legacy_low_without_evidence: bool = False
    enforce_audit_verification: bool = True

    @classmethod
    def legacy_compatible(cls) -> BasketVerificationPolicy:
        """Compatibility policy for tests/callers created before confidence fields."""

        return cls(
            allow_medium_semantic=True,
            allow_estimated_quantities=True,
            allow_unknown_quantities=True,
            allow_unknown_sale_model=True,
            allow_legacy_low_without_evidence=True,
            enforce_audit_verification=False,
        )

    @classmethod
    def strict_live(
        cls,
        *,
        allow_medium_semantic: bool = False,
        allow_estimated_quantities: bool = True,
    ) -> BasketVerificationPolicy:
        return cls(
            allow_medium_semantic=allow_medium_semantic,
            allow_estimated_quantities=allow_estimated_quantities,
            allow_unknown_quantities=False,
            allow_unknown_sale_model=False,
            allow_legacy_low_without_evidence=False,
            enforce_audit_verification=True,
        )

    def status_for_quote(self, quote: BasketItemQuote) -> BasketVerificationStatus:
        if quote.semantic_confidence in {
            SemanticConfidence.LOW,
            SemanticConfidence.REJECTED,
        }:
            # Legacy fixtures may remain executable, but they stay explicitly
            # unverified in optimizer ordering rather than becoming trusted.
            if (
                quote.semantic_confidence == SemanticConfidence.LOW
                and self.allow_legacy_low_without_evidence
                and not quote.semantic_evidence
            ):
                return BasketVerificationStatus.UNVERIFIED
            return BasketVerificationStatus.INVALID
        if (
            quote.semantic_confidence == SemanticConfidence.MEDIUM
            and not self.allow_medium_semantic
        ):
            return BasketVerificationStatus.INVALID
        if (
            quote.sale_model == SaleModel.UNKNOWN
            or quote.quantity_confidence == QuantityConfidence.UNKNOWN
        ):
            return BasketVerificationStatus.UNVERIFIED
        if quote.conditional_variant_choice:
            return BasketVerificationStatus.UNVERIFIED
        if quote.quantity_confidence == QuantityConfidence.ESTIMATED:
            return BasketVerificationStatus.VERIFIED_WITH_ESTIMATES
        return BasketVerificationStatus.VERIFIED

    def allows_quote(self, quote: BasketItemQuote) -> bool:
        status = self.status_for_quote(quote)
        if status == BasketVerificationStatus.INVALID:
            return False
        if quote.semantic_confidence == SemanticConfidence.REJECTED or (
            quote.semantic_confidence == SemanticConfidence.LOW
            and not (self.allow_legacy_low_without_evidence and not quote.semantic_evidence)
        ):
            return False
        if quote.sale_model == SaleModel.UNKNOWN and not self.allow_unknown_sale_model:
            return False
        if (
            quote.quantity_confidence == QuantityConfidence.UNKNOWN
            and not self.allow_unknown_quantities
        ):
            return False
        return not (
            quote.quantity_confidence == QuantityConfidence.ESTIMATED
            and not self.allow_estimated_quantities
        )

    def rank_for_quote(self, quote: BasketItemQuote) -> int:
        return _VERIFICATION_RANK[self.status_for_quote(quote)]


@dataclass(slots=True)
class QuoteCacheStats:
    """Counters for one explicitly bounded quote-cache session."""

    hits: int = 0
    misses: int = 0
    quote_set_hits: int = 0
    quote_set_misses: int = 0
    selection_hits: int = 0
    selection_misses: int = 0
    per_store_selection_hits: int = 0
    per_store_selection_misses: int = 0
    subset_vector_hits: int = 0
    subset_vector_misses: int = 0
    subset_pattern_hits: int = 0
    subset_pattern_misses: int = 0
    store_subset_hits: int = 0
    store_subset_misses: int = 0
    same_depth_keys: int = 0
    optimistic_store_subset_evaluations: int = 0
    optimistic_store_subsets_infeasible: int = 0
    calculations: int = 0


@dataclass(frozen=True, slots=True)
class _QuoteSetCacheEntry:
    """Retain the exact candidate sequence so Python cannot reuse its id."""

    candidates: Sequence[ProductCandidate]
    quotes: tuple[BasketItemQuote, ...]


@dataclass(frozen=True, slots=True)
class _CompactQuoteSelection:
    """Checkout-identical winner plus its repeatedly aggregated key fields."""

    quote: BasketItemQuote | None
    verification_rank: int = 0
    total_price: Decimal = Decimal(0)
    store_id: str | None = None
    store_mask: int = 0


@dataclass(frozen=True, slots=True)
class StoreSubsetCacheStats:
    """Request-independent combinatorial subset memoization diagnostics."""

    hits: int
    misses: int
    entries: int


@dataclass(slots=True)
class _QuoteCacheSession:
    promotion_structure_rows: dict[int, tuple[tuple, tuple, tuple]] = field(default_factory=dict)
    promotion_structure_candidates: int = 0
    # Only the authoritative ordering of stores determines a subset's winner.
    # Rebind that structural pattern to current quotes; never cache prices here.
    subset_patterns: dict[tuple, tuple[str | None, ...]] = field(default_factory=dict)
    # Exact quotient of subset vectors, request-local like the source quotes.
    # A bit marks every store subset with that same rank/price/winning store.
    subset_partitions: dict[int, tuple[tuple, tuple, tuple, bool]] = field(default_factory=dict)
    subset_cap_masks: dict[int, tuple[tuple, tuple[int, ...]]] = field(default_factory=dict)
    base_candidate_rows: dict[
        int, tuple[tuple[ProductCandidate, ...], tuple[ProductCandidate, ...]]
    ] = field(default_factory=dict)
    quotes: dict[_QuoteCacheKey, BasketItemQuote] = field(default_factory=dict)
    candidate_fingerprints: dict[int, tuple[ProductCandidate, _CandidateFingerprint]] = field(
        default_factory=dict
    )
    quote_sets: dict[_QuoteSetKey, _QuoteSetCacheEntry] = field(default_factory=dict)
    selections: dict[_QuoteSelectionKey, BasketItemQuote | None] = field(
        default_factory=dict
    )
    per_store_selections: dict[_QuoteSetKey, dict[str, BasketItemQuote]] = field(
        default_factory=dict
    )
    per_store_compact: dict[
        _QuoteSetKey,
        dict[str, _CompactQuoteSelection],
    ] = field(default_factory=dict)
    subset_vectors: dict[
        _QuoteSubsetVectorKey,
        tuple[_CompactQuoteSelection, ...],
    ] = field(default_factory=dict)
    store_orders: dict[
        int,
        tuple[Sequence[Store], tuple[str, ...]],
    ] = field(default_factory=dict)
    stats: QuoteCacheStats = field(default_factory=QuoteCacheStats)
    price_universe: PriceUniverse | None = None
    persistent_cache: PackageCostCache | None = None
    calculator_version: str = "basket-calculator-v3-purchase-planning"


def _value(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _sum_items(items: Iterable[BasketItem]) -> Decimal:
    return money(sum((money(item.total_price) for item in items), Decimal(0)))


def _sum_quotes(quotes: Iterable[BasketItemQuote]) -> Decimal:
    return money(sum((quote.total_price for quote in quotes), Decimal(0)))


_QUOTE_LINE_SUFFIX = re.compile(r" \[\d+\]$")


def _named_quote(quote, ingredient):
    """A reused quote carries the current purchase line's name; nothing else differs."""
    if quote.ingredient == ingredient.canonical_name:
        return quote
    return dataclass_replace(quote, ingredient=ingredient.canonical_name)


class BasketOptimizer:
    """Choose products by actual package cost, never theoretical unit cost."""

    def __init__(
        self,
        calculator: BasketCalculator | None = None,
        *,
        verification_policy: BasketVerificationPolicy | None = None,
        memoize_store_subsets: bool = False,
    ) -> None:
        self.calculator = calculator or BasketCalculator()
        self.verification_policy = (
            verification_policy or BasketVerificationPolicy.legacy_compatible()
        )
        self._quote_cache_context: ContextVar[_QuoteCacheSession | None] = ContextVar(
            f"basket_quote_cache_{id(self)}",
            default=None,
        )
        self.memoize_store_subsets = memoize_store_subsets
        self._store_subset_lock = RLock()
        self._store_subsets: dict[
            tuple[tuple[str, ...], int], tuple[tuple[str, ...], ...]
        ] = {}
        self._store_subset_hits = 0
        self._store_subset_misses = 0

    def _eligible_store_subsets(
        self,
        ordered_store_ids: tuple[str, ...],
        limit: int,
    ) -> tuple[tuple[str, ...], ...]:
        key = (ordered_store_ids, limit)
        if not self.memoize_store_subsets:
            return tuple(
                subset
                for store_count in range(1, limit + 1)
                for subset in combinations(ordered_store_ids, store_count)
            )
        with self._store_subset_lock:
            cached = self._store_subsets.get(key)
            if cached is not None:
                self._store_subset_hits += 1
                session = self._quote_cache_context.get()
                if session is None:
                    increment_performance_counter("store_subset_cache_hits")
                else:
                    session.stats.store_subset_hits += 1
                return cached
            self._store_subset_misses += 1
            session = self._quote_cache_context.get()
            if session is None:
                increment_performance_counter("store_subset_cache_misses")
            else:
                session.stats.store_subset_misses += 1
            value = tuple(
                subset
                for store_count in range(1, limit + 1)
                for subset in combinations(ordered_store_ids, store_count)
            )
            self._store_subsets[key] = value
            return value

    @property
    def store_subset_cache_stats(self) -> StoreSubsetCacheStats:
        with self._store_subset_lock:
            return StoreSubsetCacheStats(
                hits=self._store_subset_hits,
                misses=self._store_subset_misses,
                entries=len(self._store_subsets),
            )

    @contextmanager
    def quote_cache(
        self,
        *,
        price_universe: PriceUniverse | None = None,
        persistent_cache: PackageCostCache | None = None,
        calculator_version: str = "basket-calculator-v3-purchase-planning",
        reuse_existing: bool = False,
    ) -> Iterator[QuoteCacheStats]:
        """Bound reusable quotes to the current menu-search/request context.

        The token reset prevents prices from surviving the caller's scope.
        Context-local state also prevents concurrent requests which share a
        service instance from observing each other's product snapshots.
        """

        if (price_universe is None) != (persistent_cache is None):
            raise ValueError("price_universe and persistent_cache must be supplied together")
        existing = self._quote_cache_context.get()
        if (reuse_existing and existing is not None
                and existing.price_universe is price_universe
                and existing.persistent_cache is persistent_cache
                and existing.calculator_version == calculator_version):
            # Reuse only within the enclosing request. Bound retained search
            # intermediates between baskets; eviction never alters an answer.
            maps = (existing.quotes, existing.candidate_fingerprints,
                    existing.quote_sets, existing.selections,
                    existing.per_store_selections, existing.per_store_compact,
                    existing.subset_vectors, existing.store_orders,
                    existing.subset_partitions, existing.subset_cap_masks, existing.base_candidate_rows,
                    existing.subset_patterns)
            if sum(map(len, maps)) > 32768:
                for mapping in maps:
                    mapping.clear()
                existing.promotion_structure_rows.clear()
                existing.promotion_structure_candidates = 0
            yield existing.stats
            return
        session = _QuoteCacheSession(
            price_universe=price_universe,
            persistent_cache=persistent_cache,
            calculator_version=calculator_version,
        )
        token = self._quote_cache_context.set(session)
        try:
            yield session.stats
        finally:
            # Hot-path events are accumulated as plain integers and published
            # once.  Recording every quote hit through the thread-safe trace
            # used to spend measurable cold-search time normalising metric
            # names and taking its lock, without adding diagnostic detail.
            counters = {
                "package_cache_hits": session.stats.hits,
                "package_cache_misses": session.stats.misses,
                "quote_set_cache_hits": session.stats.quote_set_hits,
                "quote_set_cache_misses": session.stats.quote_set_misses,
                "quote_selection_cache_hits": session.stats.selection_hits,
                "quote_selection_cache_misses": session.stats.selection_misses,
                "per_store_selection_cache_hits": (
                    session.stats.per_store_selection_hits
                ),
                "per_store_selection_cache_misses": (
                    session.stats.per_store_selection_misses
                ),
                "quote_subset_vector_cache_hits": session.stats.subset_vector_hits,
                "quote_subset_vector_cache_misses": session.stats.subset_vector_misses,
                "quote_subset_pattern_cache_hits": session.stats.subset_pattern_hits,
                "quote_subset_pattern_cache_misses": session.stats.subset_pattern_misses,
                "store_subset_cache_hits": session.stats.store_subset_hits,
                "store_subset_cache_misses": session.stats.store_subset_misses,
                "same_depth_store_limited_keys": session.stats.same_depth_keys,
                "optimistic_store_subset_evaluations": (
                    session.stats.optimistic_store_subset_evaluations
                ),
                "optimistic_store_subsets_infeasible": (
                    session.stats.optimistic_store_subsets_infeasible
                ),
                "package_calculations": session.stats.calculations,
                "cache_hits": (
                    session.stats.hits
                    + session.stats.quote_set_hits
                    + session.stats.selection_hits
                    + session.stats.per_store_selection_hits
                    + session.stats.subset_vector_hits
                    + session.stats.subset_pattern_hits
                    + session.stats.store_subset_hits
                ),
                "cache_misses": (
                    session.stats.misses
                    + session.stats.quote_set_misses
                    + session.stats.selection_misses
                    + session.stats.per_store_selection_misses
                    + session.stats.subset_vector_misses
                    + session.stats.subset_pattern_misses
                    + session.stats.store_subset_misses
                ),
            }
            for name, amount in counters.items():
                if amount:
                    increment_performance_counter(name, amount)
            self._quote_cache_context.reset(token)
            session.quotes.clear()
            session.quote_sets.clear()
            session.candidate_fingerprints.clear()
            session.selections.clear()
            session.per_store_selections.clear()
            session.per_store_compact.clear()
            session.subset_vectors.clear()
            session.subset_patterns.clear()
            session.store_orders.clear()
            session.subset_partitions.clear()
            session.subset_cap_masks.clear()
            session.base_candidate_rows.clear()
            session.promotion_structure_rows.clear()
            session.promotion_structure_candidates = 0

    @staticmethod
    def _build_candidate_fingerprint(
        candidate: ProductCandidate,
    ) -> _CandidateFingerprint:
        # Preserve every checkout-relevant offer field so cache hits cannot
        # erase source purchase caps or other eligibility differences.
        offers = tuple(
            (
                offer.kind,
                offer.description,
                offer.price,
                offer.required_packages,
                offer.max_quantity,
                offer.price_contract_id,
                offer.eligibility,
                offer.mechanism,
                offer.membership_program,
                offer.member_program,
                offer.percent_discount,
                offer.currency,
                offer.source_confidence,
                offer.semantic_confidence,
                offer.quantity_confidence,
                offer.valid_from,
                offer.valid_to,
            )
            for offer in candidate.offers
        )
        provenance = candidate.source_provenance
        return (
            candidate.product_id,
            candidate.chain,
            candidate.gtin,
            candidate.price_context_type,
            candidate.coverage,
            candidate.product_name,
            candidate.canonical_name,
            candidate.canonical_food,
            candidate.food_family,
            candidate.product_role,
            candidate.product_form,
            candidate.semantic_confidence,
            tuple(candidate.semantic_evidence),
            candidate.store_id,
            candidate.store_name,
            candidate.sale_model,
            candidate.sale_price,
            candidate.sale_unit,
            candidate.comparison_price,
            candidate.comparison_unit,
            candidate.piece_price,
            candidate.estimated_piece_weight,
            candidate.estimated_piece_weight_unit,
            candidate.package_quantity,
            candidate.package_unit,
            candidate.usable_quantity,
            candidate.usable_unit,
            candidate.quantity_confidence,
            candidate.variable_weight,
            candidate.price,
            candidate.purchase_date,
            candidate.effective_price,
            candidate.selected_price_contract_id,
            candidate.selected_price_eligibility,
            candidate.selected_price_mechanism,
            candidate.selected_membership_program,
            candidate.match_score,
            offers,
            tuple(g.model_dump_json() for g in candidate.promotion_groups),
            candidate.category,
            tuple(provenance.model_dump(mode="python").items()) if provenance is not None else None,
        )

    def _quote_cache_key(
        self,
        session: _QuoteCacheSession,
        ingredient: NormalizedIngredient,
        candidate: ProductCandidate,
    ) -> _QuoteCacheKey:
        # NormalizedIngredient accepts only the canonical g/ml/st dimensions;
        # repeating the general recipe-unit parser on every cache lookup is
        # redundant and dominated cold menu search.
        required_quantity = ingredient.required_quantity
        required_unit = ingredient.unit
        candidate_id = id(candidate)
        cached_fingerprint = session.candidate_fingerprints.get(candidate_id)
        if cached_fingerprint is not None and cached_fingerprint[0] is candidate:
            fingerprint = cached_fingerprint[1]
        else:
            fingerprint = self._build_candidate_fingerprint(candidate)
            # Retaining the model for this short scope prevents Python from
            # reusing its id for a different candidate.
            session.candidate_fingerprints[candidate_id] = (candidate, fingerprint)
        return (
            # Weekly purchase lines are named "<ingredient> [<line no>]"; the
            # line number depends on menu composition but never on the quote.
            _QUOTE_LINE_SUFFIX.sub("", ingredient.canonical_name),
            Decimal(str(required_quantity)).normalize(),
            required_unit,
            fingerprint,
        )

    @staticmethod
    def _ingredient_candidates(
        ingredient: NormalizedIngredient,
        candidates_by_name: Mapping[str, Sequence[ProductCandidate]],
    ) -> Sequence[ProductCandidate]:
        direct = candidates_by_name.get(ingredient.canonical_name)
        if direct is not None:
            return direct
        target = canonicalize_ingredient_name(ingredient.canonical_name)
        for key, candidates in candidates_by_name.items():
            if canonicalize_ingredient_name(str(key)) == target:
                return candidates
        return ()

    def _calculate_quote(
        self,
        ingredient: NormalizedIngredient,
        candidate: ProductCandidate,
    ) -> BasketItemQuote:
        """Reuse an exact quote inside an explicit request-local cache scope."""

        session = self._quote_cache_context.get()
        # Custom calculators remain fully compatible.  Since they may depend
        # on fields or mutable state unknown to this optimiser, they keep their
        # historical call-per-evaluation semantics instead of being cached by
        # an unsafe key.
        if session is None or type(self.calculator) is not BasketCalculator:
            return self._calculate_quote_uncached(ingredient, candidate)

        key = self._quote_cache_key(session, ingredient, candidate)
        cached = session.quotes.get(key)
        if cached is not None:
            session.stats.hits += 1
            return _named_quote(cached, ingredient)

        session.stats.misses += 1
        if session.price_universe is not None and session.persistent_cache is not None:
            quote = session.persistent_cache.get_or_compute(
                session.price_universe,
                candidate,
                required_quantity=ingredient.required_quantity,
                required_unit=ingredient.unit,
                calculator_version=session.calculator_version,
                factory=lambda: self._calculate_quote_uncached(ingredient, candidate),
            )
        else:
            quote = self._calculate_quote_uncached(ingredient, candidate)
        session.quotes[key] = quote
        # The persistent cache is keyed without the purchase-line name.
        return _named_quote(quote, ingredient)

    def _calculate_quote_uncached(
        self,
        ingredient: NormalizedIngredient,
        candidate: ProductCandidate,
    ) -> BasketItemQuote:
        """Use the fast quote path while respecting injected calculator overrides."""

        session = self._quote_cache_context.get()
        if session is None:
            increment_performance_counter("package_calculations")
        else:
            session.stats.calculations += 1

        calculator_type = type(self.calculator)
        calculate_implementation = getattr(calculator_type, "calculate_item", None)
        quote_implementation = getattr(calculator_type, "quote_item", None)

        # A pre-existing custom calculator may override only calculate_item.
        # Preserve that extension point instead of silently bypassing it with
        # BasketCalculator.quote_item.  The built-in path never constructs a
        # BasketItem here.
        quote_method = getattr(self.calculator, "quote_item", None)
        if not callable(quote_method) or (
            calculate_implementation is not BasketCalculator.calculate_item
            and quote_implementation is BasketCalculator.quote_item
        ):
            item = self.calculator.calculate_item(ingredient, candidate)
            regular_total = item.regular_total_price
            if regular_total is None and candidate.price is not None:
                regular_total = float(money(money(candidate.price) * item.packages_needed))
            return BasketItemQuote(
                ingredient=item.ingredient,
                product_id=item.product_id,
                product_name=item.product_name,
                gtin=item.gtin or candidate.gtin,
                chain=item.chain or candidate.chain,
                price_context_type=(
                    item.price_context_type or candidate.price_context_type
                ),
                coverage=item.coverage or candidate.coverage,
                store_id=item.store_id,
                store_name=item.store_name,
                match_score=candidate.match_score,
                required_quantity=item.required_quantity,
                unit=item.unit,
                canonical_food=item.canonical_food,
                food_family=item.food_family,
                product_role=item.product_role,
                product_form=item.product_form,
                semantic_confidence=item.semantic_confidence,
                semantic_evidence=tuple(item.semantic_evidence),
                sale_model=item.sale_model,
                sale_price=float(item.sale_price),
                sale_unit=item.sale_unit,
                comparison_price=item.comparison_price,
                comparison_unit=item.comparison_unit,
                piece_price=item.piece_price,
                estimated_piece_weight=item.estimated_piece_weight,
                estimated_piece_weight_unit=item.estimated_piece_weight_unit,
                package_quantity=item.package_quantity,
                package_unit=item.package_unit,
                usable_quantity=item.usable_quantity,
                usable_unit=item.usable_unit,
                quantity_confidence=item.quantity_confidence,
                variable_weight=item.variable_weight,
                packages_needed=item.packages_needed,
                purchased_quantity=item.purchased_quantity,
                purchased_unit=item.purchased_unit or item.unit,
                purchased_usable_quantity=item.purchased_usable_quantity,
                waste_quantity=item.waste_quantity,
                unit_price=money(item.unit_price),
                base_checkout_unit_price=(
                    money(item.base_checkout_unit_price)
                    if item.base_checkout_unit_price is not None
                    else None
                ),
                total_price=money(item.total_price),
                regular_total_price=money(regular_total) if regular_total is not None else None,
                purchase_date=candidate.purchase_date,
                regular_unit_price=money(
                    item.regular_unit_price
                    if item.regular_unit_price is not None
                    else candidate.price
                ) if candidate.price is not None else None,
                price_contract_id=item.price_contract_id,
                eligibility=item.eligibility,
                price_mechanism=item.price_mechanism,
                membership_program=item.membership_program,
                offer_description=item.offer_description,
                applied_offer=item.applied_offer,
                resolution_warning=None,
                source_provenance=item.source_provenance or candidate.source_provenance,
            )
        return quote_method(ingredient, candidate)

    def _candidate_quotes(
        self,
        ingredient: NormalizedIngredient,
        candidates: Sequence[ProductCandidate],
    ) -> tuple[BasketItemQuote, ...]:
        return self._candidate_quotes_with_key(ingredient, candidates)[0]

    def _candidate_quotes_with_key(
        self,
        ingredient: NormalizedIngredient,
        candidates: Sequence[ProductCandidate],
    ) -> tuple[tuple[BasketItemQuote, ...], _QuoteSetKey | None]:
        """Return an exact request-local quote set and its reusable identity.

        Menu search asks for the same canonical requirement many times while
        exploring different recipe combinations.  Package quotes were already
        cached individually, but rebuilding their tuple still walked every
        product on every state.  The candidate mapping is immutable for the
        explicitly bounded ``quote_cache`` scope, so retaining the sequence
        object together with its id makes this higher-level cache exact and
        prevents id reuse.  Custom calculators deliberately keep their legacy
        call-per-evaluation behaviour.
        """

        session = self._quote_cache_context.get()
        # Identity is an exact cache key only for an immutable container.
        # MenuOptimizer freezes its request-local candidate mapping when
        # search reuse is enabled.  Direct callers may still pass a mutable
        # list; those deliberately keep the safe slow path so replacing or
        # reordering a candidate in the same session can never return stale
        # prices.
        cacheable = (
            session is not None
            and type(self.calculator) is BasketCalculator
            and isinstance(candidates, tuple)
        )
        key: _QuoteSetKey | None = None
        if cacheable:
            required_quantity = ingredient.required_quantity
            required_unit = ingredient.unit
            key = (
                ingredient.canonical_name,
                Decimal(str(required_quantity)).normalize(),
                required_unit,
                id(candidates),
            )
            cached = session.quote_sets.get(key)
            if cached is not None and cached.candidates is candidates:
                session.stats.quote_set_hits += 1
                return cached.quotes, key

        if cacheable and session is not None:
            session.stats.quote_set_misses += 1
        calculated: list[BasketItemQuote] = []
        for candidate in candidates:
            try:
                quote = self._calculate_quote(ingredient, candidate)
            except ValueError:
                # A candidate in the wrong physical dimension is not a valid
                # product for this normalised requirement.
                continue
            if self.verification_policy.allows_quote(quote):
                calculated.append(quote)
        result = tuple(calculated)
        if key is not None and session is not None:
            session.quote_sets[key] = _QuoteSetCacheEntry(
                candidates=candidates,
                quotes=result,
            )
        return result, key

    def _cheapest_quote_for_set(
        self,
        quotes: tuple[BasketItemQuote, ...],
        allowed_store_ids: set[str],
        quote_set_key: _QuoteSetKey | None,
    ) -> BasketItemQuote | None:
        """Cache exact cheapest-quote selection for one requirement/subset."""

        return self._cheapest_quote_for_subset_key(
            quotes,
            tuple(sorted(allowed_store_ids)),
            quote_set_key,
        )

    def _cheapest_quote_for_subset_key(
        self,
        quotes: tuple[BasketItemQuote, ...],
        ordered_store_ids: tuple[str, ...],
        quote_set_key: _QuoteSetKey | None,
        *,
        per_store_quotes: Mapping[str, BasketItemQuote] | None = None,
    ) -> BasketItemQuote | None:
        """Return one exact subset winner without rebuilding its hot-path key.

        ``same_depth_store_limited_key`` already enumerates deterministic,
        sorted store tuples.  Keeping that tuple intact avoids millions of
        temporary sets/sorts.  On a cache miss the union winner is selected
        from each store's authoritative minimum; mathematically this is the
        same quote as scanning the full union, including every stable
        tie-breaker in :meth:`_quote_sort_key`.
        """

        session = self._quote_cache_context.get()
        if session is None or quote_set_key is None:
            return self._cheapest_quote(quotes, set(ordered_store_ids))
        key = (quote_set_key, ordered_store_ids)
        if key in session.selections:
            session.stats.selection_hits += 1
            return session.selections[key]
        session.stats.selection_misses += 1
        per_store = (
            per_store_quotes
            if per_store_quotes is not None
            else self._cheapest_quotes_by_store(quotes, quote_set_key)
        )
        eligible = tuple(
            per_store[store_id]
            for store_id in ordered_store_ids
            if store_id in per_store
        )
        result = min(eligible, key=self._quote_sort_key) if eligible else None
        session.selections[key] = result
        return result

    def _cheapest_quotes_by_store(
        self,
        quotes: tuple[BasketItemQuote, ...],
        quote_set_key: _QuoteSetKey | None,
    ) -> dict[str, BasketItemQuote]:
        """Return each store's exact winning quote after one linear scan.

        The cheapest quote from a union of stores is necessarily the minimum
        of the already-cheapest quote from each member store.  Building this
        vector once avoids rescanning the full product list for every store
        subset while preserving the authoritative quote ordering exactly.
        """

        session = self._quote_cache_context.get()
        if session is not None and quote_set_key is not None:
            cached = session.per_store_selections.get(quote_set_key)
            if cached is not None:
                session.stats.per_store_selection_hits += 1
                return cached

        if session is not None and quote_set_key is not None:
            session.stats.per_store_selection_misses += 1

        result: dict[str, BasketItemQuote] = {}
        for quote in quotes:
            current = result.get(quote.store_id)
            if current is None or self._quote_sort_key(quote) < self._quote_sort_key(
                current
            ):
                result[quote.store_id] = quote
        if session is not None and quote_set_key is not None:
            session.per_store_selections[quote_set_key] = result
        return result

    def _quote_subset_vector(
        self,
        quotes: tuple[BasketItemQuote, ...],
        quote_set_key: _QuoteSetKey | None,
        ordered_store_ids: tuple[str, ...],
        store_subsets: tuple[tuple[str, ...], ...],
        limit: int,
    ) -> tuple[_CompactQuoteSelection, ...]:
        """Precompute every exact subset winner for one quantity requirement.

        A menu search revisits the same normalized quantity across thousands
        of economic states.  The authoritative winning quote depends only on
        that quote set and the allowed store subset, so the complete vector is
        request-local immutable data.  Each row retains the real quote for
        equivalence/debugging and precomputes only fields already used by the
        same-depth aggregate key.
        """

        session = self._quote_cache_context.get()
        vector_key: _QuoteSubsetVectorKey | None = None
        if session is not None and quote_set_key is not None:
            vector_key = (quote_set_key, ordered_store_ids, limit)
            cached = session.subset_vectors.get(vector_key)
            if cached is not None:
                session.stats.subset_vector_hits += 1
                return cached
            session.stats.subset_vector_misses += 1

        per_store = self._cheapest_quotes_by_store(quotes, quote_set_key)
        store_bits = {
            store_id: 1 << index for index, store_id in enumerate(ordered_store_ids)
        }
        # The selected quote for a store is immutable in this quote-cache
        # session. Compute its sort key and compact representation once, not
        # once for every subset containing it (millions of repeated calls).
        sort_keys = {store_id: self._quote_sort_key(quote) for store_id, quote in per_store.items()}
        compact = {store_id: _CompactQuoteSelection(
            quote=quote,
            verification_rank=self.verification_policy.rank_for_quote(quote),
            total_price=quote.total_price,
            store_id=store_id,
            store_mask=store_bits.get(store_id, 0),
        ) for store_id, quote in per_store.items()}
        missing = _CompactQuoteSelection(quote=None)
        pattern_key = (ordered_store_ids, limit, tuple(sorted(per_store, key=sort_keys.__getitem__)))
        pattern = session.subset_patterns.get(pattern_key) if session else None
        if pattern is None:
            # Store ID is part of the authoritative quote key, so distinct
            # stores cannot tie. Changing quantity, price or policy recomputes
            # this order before reuse; current quote objects supply all values.
            ranks = {store_id: rank for rank, store_id in enumerate(pattern_key[2])}
            pattern = tuple(min((s for s in combo if s in ranks),
                                key=ranks.__getitem__, default=None) for combo in store_subsets)
            if session:
                session.stats.subset_pattern_misses += 1
                if len(session.subset_patterns) >= 256:
                    session.subset_patterns.pop(next(iter(session.subset_patterns)))
                session.subset_patterns[pattern_key] = pattern
        elif session:
            session.stats.subset_pattern_hits += 1
        result = tuple(compact.get(store_id, missing) for store_id in pattern)
        if vector_key is not None and session is not None:
            session.subset_vectors[vector_key] = result
        return result

    def _compact_quotes_by_store(
        self,
        quotes: tuple[BasketItemQuote, ...],
        quote_set_key: _QuoteSetKey | None,
    ) -> dict[str, _CompactQuoteSelection]:
        """Return cached rank/price fields for each store's exact winner."""

        session = self._quote_cache_context.get()
        if session is not None and quote_set_key is not None:
            cached = session.per_store_compact.get(quote_set_key)
            if cached is not None:
                return cached
        result = {
            store_id: _CompactQuoteSelection(
                quote=quote,
                verification_rank=self.verification_policy.rank_for_quote(quote),
                total_price=quote.total_price,
                store_id=store_id,
            )
            for store_id, quote in self._cheapest_quotes_by_store(
                quotes, quote_set_key
            ).items()
        }
        if session is not None and quote_set_key is not None:
            session.per_store_compact[quote_set_key] = result
        return result

    def optimistic_relaxed_key(
        self,
        ingredients: Sequence[NormalizedIngredient],
        candidates_by_name: Mapping[str, Sequence[ProductCandidate]],
        *,
        allowed_store_ids: Iterable[str],
    ) -> tuple[int, Decimal] | None:
        """Return an admissible verification/cost key without a store limit.

        Every quote uses the authoritative package, promotion, membership and
        maximum-quantity calculator.  The relaxation then lets each ingredient
        choose independently from every otherwise allowed context.  Ignoring
        the maximum store count can only make this total cheaper than (or equal
        to) a feasible basket.  Verification rank and money are minimized
        independently: this is intentionally optimistic and therefore safe for
        lazy beam ordering, never a checkout result exposed to callers.
        """

        allowed = set(allowed_store_ids)
        if not allowed and ingredients:
            return None
        verification_rank = _VERIFICATION_RANK[BasketVerificationStatus.VERIFIED]
        total = Decimal(0)
        for ingredient in ingredients:
            quotes, _quote_set_key = self._candidate_quotes_with_key(
                ingredient,
                self._ingredient_candidates(ingredient, candidates_by_name),
            )
            eligible = tuple(quote for quote in quotes if quote.store_id in allowed)
            if not eligible:
                return None
            verification_rank = max(
                verification_rank,
                min(self.verification_policy.rank_for_quote(quote) for quote in eligible),
            )
            total += min(money(quote.total_price) for quote in eligible)
        increment_performance_counter("optimistic_basket_bounds")
        # Independent line totals can overestimate a future group discount.
        # Zero is conservative even when multiple promotions compete.
        if _has_coupled_checkout(candidates_by_name, (i.canonical_name for i in ingredients), session=self._quote_cache_context.get()):
            total = Decimal(0)
        return verification_rank, money(total)

    def restriction_cost_bounds(
        self,
        ingredients: Sequence[NormalizedIngredient],
        candidates_by_name: Mapping[str, Sequence[ProductCandidate]],
        restricted_candidates: Mapping[str, Sequence[ProductCandidate]],
        *,
        allowed_store_ids: Iterable[str],
    ) -> dict[str, tuple[Decimal, Decimal]] | None:
        """Independent line lower bounds before/after candidate restrictions.

        Reuse the authoritative quote relaxation once per line, not once per
        combination. Summing these bounds is safe only without coupled checkout;
        a cross-line discount can invalidate even otherwise independent totals.
        Missing coverage and coupled campaigns fall back to ordinary checkout.
        These are cost bounds, never ranking keys or purchasable baskets.
        """
        if type(self.calculator) is not BasketCalculator:
            return None  # injected/stateful calculators retain ordinary calls
        names = tuple(i.canonical_name for i in ingredients)
        if _has_coupled_checkout(candidates_by_name, names, session=self._quote_cache_context.get()):
            return None
        allowed = frozenset(allowed_store_ids)
        result = {}
        for ingredient in ingredients:
            ordinary = self.optimistic_relaxed_key(
                [ingredient], candidates_by_name, allowed_store_ids=allowed)
            restricted = self.optimistic_relaxed_key(
                [ingredient], restricted_candidates, allowed_store_ids=allowed)
            if ordinary is None:
                return None
            # A line without a restricted candidate cannot be selected by the
            # caller's eligible-subset search; retain its unrestricted bound.
            result[ingredient.canonical_name] = (ordinary[1], restricted[1] if restricted else ordinary[1])
        return result

    def same_depth_nested_store_limited_keys(
        self,
        ingredients: Sequence[NormalizedIngredient],
        candidates_by_name: Mapping[str, Sequence[ProductCandidate]],
        stores: Sequence[Store],
        *,
        max_stores: int | None,
    ) -> tuple[tuple[int, Decimal, int] | None, ...]:
        """Return exact leading keys for every nested finite store cap.

        Store subsets for max N already contain every subset admissible for
        caps 1..N.  Accumulating their cumulative winners in one pass lets a
        menu search carry lower-cap frontiers without repeating the hottest
        quote/subset loop.  Each key uses the identical policy-approved quote
        and lexicographic verification/cost order as :meth:`optimize`, but
        skips BasketItem/Pydantic materialization and audit.  These keys are
        only for ranking states at the same beam depth, never checkout results
        or bounds across future recipe additions.
        """

        if _has_coupled_checkout(candidates_by_name, (i.canonical_name for i in ingredients), session=self._quote_cache_context.get()):
            return self._optimize_promotion_groups(
                ingredients, candidates_by_name, stores, max_stores,
                calculate_savings=False, nested_keys=True,
            )
        quoted_requirements = tuple(
            self._candidate_quotes_with_key(
                ingredient,
                self._ingredient_candidates(ingredient, candidates_by_name),
            )
            for ingredient in ingredients
        )
        return self._same_depth_nested_store_limited_quote_keys(
            quoted_requirements,
            stores,
            max_stores=max_stores,
        )

    def same_depth_nested_store_limited_requirement_keys(
        self,
        requirements: Sequence[tuple[object, ...]],
        candidates_by_name: Mapping[str, Sequence[ProductCandidate]],
        stores: Sequence[Store],
        *,
        max_stores: int | None,
    ) -> tuple[tuple[int, Decimal, int] | None, ...]:
        """Compact equivalent of ``same_depth_nested_store_limited_keys``.

        Menu search already owns an immutable canonical demand key.  Reading
        that key directly avoids constructing hundreds of thousands of
        temporary Pydantic ingredient rows merely to rediscover an existing
        request-local quote-set key.  A previously unseen quantity still goes
        through the authoritative calculator once; all price, promotion,
        membership and tie-breaking semantics remain shared with checkout.
        """

        if _has_coupled_checkout(candidates_by_name, (str(r[0]) for r in requirements), session=self._quote_cache_context.get()):
            return self.same_depth_nested_store_limited_keys(
                [NormalizedIngredient(canonical_name=str(r[0]), required_quantity=float(r[1]), unit=str(r[2])) for r in requirements],
                candidates_by_name, stores, max_stores=max_stores,
            )
        quoted_requirements: list[tuple[tuple[BasketItemQuote, ...], _QuoteSetKey | None]] = []
        for raw in requirements:
            if len(raw) != 3:
                raise ValueError("canonical requirement keys must have three fields")
            canonical = str(raw[0])
            quantity = Decimal(str(raw[1])).normalize()
            unit = str(raw[2])
            candidates = candidates_by_name.get(canonical)
            if candidates is None:
                target = canonicalize_ingredient_name(canonical)
                candidates = next(
                    (
                        rows
                        for key, rows in candidates_by_name.items()
                        if canonicalize_ingredient_name(str(key)) == target
                    ),
                    (),
                )

            session = self._quote_cache_context.get()
            cacheable = (
                session is not None
                and type(self.calculator) is BasketCalculator
                and isinstance(candidates, tuple)
            )
            quote_set_key: _QuoteSetKey | None = None
            if cacheable:
                quote_set_key = (canonical, quantity, unit, id(candidates))
                cached = session.quote_sets.get(quote_set_key)
                if cached is not None and cached.candidates is candidates:
                    session.stats.quote_set_hits += 1
                    quoted_requirements.append((cached.quotes, quote_set_key))
                    continue

            ingredient = NormalizedIngredient.model_construct(
                canonical_name=canonical,
                required_quantity=float(quantity),
                unit=unit,
                display_name=canonical,
                source_recipes=[],
            )
            quoted_requirements.append(
                self._candidate_quotes_with_key(ingredient, candidates)
            )

        return self._same_depth_nested_store_limited_quote_keys(
            quoted_requirements,
            stores,
            max_stores=max_stores,
        )

    def _same_depth_nested_store_limited_quote_keys(
        self,
        quoted_requirements: Sequence[
            tuple[tuple[BasketItemQuote, ...], _QuoteSetKey | None]
        ],
        stores: Sequence[Store],
        *,
        max_stores: int | None,
    ) -> tuple[tuple[int, Decimal, int] | None, ...]:
        """Aggregate exact cached quote sets for each nested store cap."""

        session = self._quote_cache_context.get()
        store_ids: tuple[str, ...] | None = None
        if session is not None and isinstance(stores, tuple):
            cached_order = session.store_orders.get(id(stores))
            if cached_order is not None and cached_order[0] is stores:
                store_ids = cached_order[1]
        if store_ids is None:
            stores_by_id: dict[str, Store] = {}
            for store in stores:
                stores_by_id.setdefault(str(_value(store, "store_id")), store)
            ordered_stores = sorted(
                stores_by_id.values(),
                key=lambda store: (
                    str(_value(store, "store_id")),
                    str(_value(store, "name")),
                ),
            )
            store_ids = tuple(
                str(_value(store, "store_id")) for store in ordered_stores
            )
            if session is not None and isinstance(stores, tuple):
                session.store_orders[id(stores)] = (stores, store_ids)
        if not store_ids:
            return ()
        unlimited = max_stores is None or max_stores <= 0
        limit = len(store_ids) if unlimited else min(max_stores, len(store_ids))
        if limit < 1:
            return ()

        requested_limit = limit
        if quoted_requirements:
            # Match optimize(): a store with no qualified quote cannot change
            # any winning purchase. Keep the caller's nested-cap result shape,
            # repeating the last key when a larger cap adds only empty stores.
            supplying = {q.store_id for quotes, _key in quoted_requirements for q in quotes}
            store_ids = tuple(s for s in store_ids if s in supplying)
            if not store_ids:
                return (None,) * requested_limit
            limit = min(limit, len(store_ids))

        if limit == 1:
            verification_ranks = [
                _VERIFICATION_RANK[BasketVerificationStatus.VERIFIED]
                for _store_id in store_ids
            ]
            totals = [Decimal(0) for _store_id in store_ids]
            feasible = [True for _store_id in store_ids]
            for quotes, quote_set_key in quoted_requirements:
                by_store = self._compact_quotes_by_store(quotes, quote_set_key)
                for index, store_id in enumerate(store_ids):
                    selection = by_store.get(store_id)
                    if selection is None:
                        feasible[index] = False
                        continue
                    if (  # noqa: PLR1730
                        selection.verification_rank > verification_ranks[index]
                    ):
                        verification_ranks[index] = selection.verification_rank
                    totals[index] += selection.total_price
            if not quoted_requirements:
                best: tuple[int, Decimal, int] | None = (0, Decimal("0.00"), 0)
            else:
                candidates = (
                    (verification_ranks[index], money(totals[index]), 1)
                    for index in range(len(store_ids))
                    if feasible[index]
                )
                best = min(candidates, default=None)
            infeasible_subsets = sum(not value for value in feasible)
            session = self._quote_cache_context.get()
            if session is not None:
                session.stats.optimistic_store_subset_evaluations += len(store_ids)
                session.stats.optimistic_store_subsets_infeasible += infeasible_subsets
                session.stats.same_depth_keys += 1
            else:
                increment_performance_counter(
                    "optimistic_store_subset_evaluations", len(store_ids)
                )
                increment_performance_counter(
                    "optimistic_store_subsets_infeasible", infeasible_subsets
                )
                increment_performance_counter("same_depth_store_limited_keys")
            return (best,) * requested_limit

        store_subsets = self._eligible_store_subsets(store_ids, limit)
        subset_vectors = tuple(
            self._quote_subset_vector(
                quotes,
                quote_set_key,
                store_ids,
                store_subsets,
                limit,
            )
            for quotes, quote_set_key in quoted_requirements
        )
        best_by_cap, infeasible_subsets = self._grouped_subset_keys(
            subset_vectors, store_subsets, limit, session
        )
        session = self._quote_cache_context.get()
        if session is not None:
            session.stats.optimistic_store_subset_evaluations += len(store_subsets)
            session.stats.optimistic_store_subsets_infeasible += infeasible_subsets
        else:
            increment_performance_counter(
                "optimistic_store_subset_evaluations",
                len(store_subsets),
            )
            increment_performance_counter(
                "optimistic_store_subsets_infeasible",
                infeasible_subsets,
            )
        session = self._quote_cache_context.get()
        if session is None:
            increment_performance_counter("same_depth_store_limited_keys")
        else:
            session.stats.same_depth_keys += 1
        return tuple(best_by_cap) + (best_by_cap[-1],) * (requested_limit - limit)

    @staticmethod
    def _grouped_subset_keys(subset_vectors, store_subsets, limit, session=None, *, winning_mask=False,
                             _integer_prices=True):
        """Aggregate every exact subset once per distinct winning-quote pattern.

        Store IDs and quote contracts are not collapsed. Bit partitions merely
        group positions of the existing vectors which have identical operands.
        Refining by intersection gives precisely the scalar loop's feasible
        subsets, Decimal sums, max ranks and union of winning stores, including
        every nested cap. No float, heuristic pruning or weaker bound is used.
        """
        if not store_subsets:
            result = ([None] * limit, 0)
            return (*result, 0) if winning_mask else result
        subset_vectors = tuple(subset_vectors)
        context = getcontext()
        # Checkout has already applied every price contract and rounding rule.
        # Compile only nonnegative, two-decimal totals with <=22 coefficient
        # digits. At most 10,000 operands then sum to <10**26 cents, exactly
        # representable in this context. No flags, traps or rounding change.
        # Unusual precision/exponents retain the original Decimal algorithm.
        integer_prices = (_integer_prices and 0 < len(subset_vectors) <= 10000
                          and context.prec >= 28 and context.Emax >= 28
                          and context.Emin <= -2 and not context.clamp)
        partitions = []
        for vector in subset_vectors:
            cached = session.subset_partitions.get(id(vector)) if session else None
            if cached is not None and cached[0] is vector and cached[3] == integer_prices:
                groups = cached[1]
                positions = cached[2]
            else:
                grouped = {}
                positions = []
                operands = {}
                compiled_selections = {}
                for index, selection in enumerate(vector):
                    key = None
                    if selection.store_id is not None:
                        if integer_prices and id(selection) in compiled_selections:
                            key = compiled_selections[id(selection)]
                            grouped[key] = grouped.get(key, 0) | (1 << index)
                            positions.append(key)
                            continue
                        price = selection.total_price
                        if integer_prices:
                            parts = price.as_tuple() if isinstance(price, Decimal) else None
                            if parts is None or parts.sign or parts.exponent != -2 or len(parts.digits) > 22:
                                return BasketOptimizer._grouped_subset_keys(
                                    subset_vectors, store_subsets, limit, session,
                                    winning_mask=winning_mask, _integer_prices=False,
                                )
                            price = int(price.scaleb(2))
                        key = (selection.verification_rank, price, selection.store_mask)
                        key = operands.setdefault(key, key)
                        if integer_prices:
                            compiled_selections[id(selection)] = key
                        grouped[key] = grouped.get(key, 0) | (1 << index)
                    positions.append(key)
                groups = tuple(grouped.items())
                positions = tuple(positions)
                if session:
                    session.subset_partitions[id(vector)] = (vector, groups, positions, integer_prices)
            partitions.append((groups, positions))
        # Small partitions first reduces intermediate intersections without
        # changing the commutative arithmetic or quote selection.
        partitions.sort(key=lambda partition: len(partition[0]))
        states = {(0, 0 if integer_prices else Decimal(0), 0): (1 << len(store_subsets)) - 1}
        settled = {}
        for partition_index, (groups, positions) in enumerate(partitions):
            refined = {}
            # Every singleton at this depth traverses the same suffix. Build
            # it once, without changing the order of Decimal additions.
            remaining_positions_by_partition = tuple(
                part[1] for part in partitions[partition_index:]
            )
            for (rank, total, stores), mask in states.items():
                if mask & (mask - 1) == 0:
                    # A singleton cannot split again. Finish its remaining
                    # operands directly, in the same arithmetic order, rather
                    # than reinsert it into every intermediate partition map.
                    position = mask.bit_length() - 1
                    for remaining_positions in remaining_positions_by_partition:
                        selection = remaining_positions[position]
                        if selection is None:
                            break
                        line_rank, line_total, line_store = selection
                        if line_rank > rank:  # noqa: PLR1730 -- measured hot loop
                            rank = line_rank
                        total += line_total
                        stores |= line_store
                    else:
                        key = (rank, total, stores)
                        settled[key] = settled.get(key, 0) | mask
                    continue
                # Sparse intersections can visit actual positions instead of
                # testing unrelated groups. Both routes retain every exact
                # intersection, Decimal sum, rank and winning store identity.
                if mask.bit_count() * 2 < len(groups):
                    overlaps = {}
                    remaining = mask
                    while remaining:
                        bit = remaining & -remaining
                        remaining ^= bit
                        selection = positions[bit.bit_length() - 1]
                        if selection is not None:
                            overlaps[selection] = overlaps.get(selection, 0) | bit
                    candidates = overlaps.items()
                else:
                    candidates = groups
                for (line_rank, line_total, line_store), line_mask in candidates:
                    overlap = mask & line_mask
                    if overlap:
                        key = (line_rank if line_rank > rank else rank,  # noqa: FURB136
                               total + line_total, stores | line_store)
                        refined[key] = refined.get(key, 0) | overlap
            states = refined
            if not states:
                break
        for key, mask in settled.items():
            states[key] = states.get(key, 0) | mask
        cached = session.subset_cap_masks.get(id(store_subsets)) if session else None
        if cached is not None and cached[0] is store_subsets:
            cap_masks = cached[1]
        else:
            masks = [0] * limit
            for index, combo in enumerate(store_subsets):
                masks[len(combo) - 1] |= 1 << index
            cap_masks = tuple(masks)
            if session:
                session.subset_cap_masks[id(store_subsets)] = (store_subsets, cap_masks)
        best_by_cap = [None] * limit
        feasible_mask = 0
        for (rank, total, stores), mask in states.items():
            feasible_mask |= mask
            key = (rank, total, stores.bit_count())
            first_cap = next(i for i, cap_mask in enumerate(cap_masks) if cap_mask & mask)
            for cap in range(first_cap, limit):
                if best_by_cap[cap] is None or key < best_by_cap[cap]:
                    best_by_cap[cap] = key
        infeasible = len(store_subsets) - feasible_mask.bit_count()
        if winning_mask:
            winners = 0
            for (rank, total, stores), mask in states.items():
                if (rank, total, stores.bit_count()) == best_by_cap[-1]:
                    winners |= mask
            if integer_prices:
                best_by_cap = [None if key is None else (key[0], Decimal(key[1]).scaleb(-2), key[2])
                               for key in best_by_cap]
            return best_by_cap, infeasible, winners
        if integer_prices:
            best_by_cap = [None if key is None else (key[0], Decimal(key[1]).scaleb(-2), key[2])
                           for key in best_by_cap]
        return best_by_cap, infeasible

    def same_depth_store_limited_key(
        self,
        ingredients: Sequence[NormalizedIngredient],
        candidates_by_name: Mapping[str, Sequence[ProductCandidate]],
        stores: Sequence[Store],
        *,
        max_stores: int | None,
    ) -> tuple[int, Decimal, int] | None:
        """Return the requested cap's exact leading same-depth order key."""

        nested = self.same_depth_nested_store_limited_keys(
            ingredients,
            candidates_by_name,
            stores,
            max_stores=max_stores,
        )
        return nested[-1] if nested else None

    def _cheapest_quote(
        self,
        quotes: Iterable[BasketItemQuote],
        allowed_store_ids: set[str],
    ) -> BasketItemQuote | None:
        eligible = (quote for quote in quotes if quote.store_id in allowed_store_ids)
        try:
            return min(eligible, key=self._quote_sort_key)
        except ValueError:
            return None

    def _quote_sort_key(self, quote: BasketItemQuote) -> tuple[object, ...]:
        """Authoritative deterministic order for competing checkout quotes."""

        return (
            self.verification_policy.rank_for_quote(quote),
            money(quote.total_price),
            -quote.match_score,
            quote.waste_quantity,
            quote.product_name.casefold(),
            quote.store_id,
            quote.product_id,
        )

    def _cheapest_item(
        self,
        ingredient: NormalizedIngredient,
        candidates: Sequence[ProductCandidate],
        allowed_store_ids: set[str],
    ) -> BasketItem | None:
        """Compatibility helper which materialises only the winning quote."""

        quote = self._cheapest_quote(
            self._candidate_quotes(ingredient, candidates), allowed_store_ids
        )
        return quote.to_basket_item() if quote is not None else None

    def _quotes_verification_rank(self, quotes: Iterable[BasketItemQuote]) -> int:
        return max(
            (self.verification_policy.rank_for_quote(quote) for quote in quotes),
            default=_VERIFICATION_RANK[BasketVerificationStatus.VERIFIED],
        )

    def single_store_options(
        self,
        ingredients: Sequence[NormalizedIngredient],
        candidates_by_name: Mapping[str, Sequence[ProductCandidate]],
        stores: Sequence[Store],
    ) -> list[StoreBasket]:
        if _has_coupled_checkout(candidates_by_name, (i.canonical_name for i in ingredients), session=self._quote_cache_context.get()):
            options = []
            for store in stores:
                try:
                    basket = self._optimize_promotion_groups(
                        ingredients, candidates_by_name, [store], 1, calculate_savings=False
                    )
                    options.append(StoreBasket(store_id=store.store_id, store_name=store.name,
                                               total=basket.total,
                                               items=[i for g in basket.stores for i in g.items]))
                except IncompleteBasketError:
                    options.append(StoreBasket(store_id=store.store_id, store_name=store.name,
                                               total=0, items=[], is_complete=False,
                                               missing_ingredients=[i.canonical_name for i in ingredients]))
            return sorted(options, key=lambda o: (not o.is_complete, o.total, o.store_id))
        started = perf_counter()
        increment_performance_counter("basket_calculations")
        quoted_ingredients = [
            (
                ingredient,
                *self._candidate_quotes_with_key(
                    ingredient,
                    self._ingredient_candidates(ingredient, candidates_by_name),
                ),
            )
            for ingredient in ingredients
        ]
        options: list[StoreBasket] = []
        for store in stores:
            store_id = str(_value(store, "store_id"))
            store_name = str(_value(store, "name", store_id))
            selected_quotes: list[BasketItemQuote] = []
            missing: list[str] = []
            for ingredient, quotes, quote_set_key in quoted_ingredients:
                quote = self._cheapest_quote_for_set(
                    quotes,
                    {store_id},
                    quote_set_key,
                )
                if quote is None:
                    missing.append(ingredient.canonical_name)
                else:
                    selected_quotes.append(quote)
            items = [quote.to_basket_item() for quote in selected_quotes]
            options.append(
                StoreBasket(
                    store_id=store_id,
                    store_name=store_name,
                    total=float(_sum_quotes(selected_quotes)),
                    items=sorted(
                        items,
                        key=lambda item: (item.ingredient, item.product_name, item.product_id),
                    ),
                    missing_ingredients=missing,
                    is_complete=not missing,
                )
            )

        # Incomplete stores follow all complete alternatives; their partial
        # totals must never appear cheaper than a complete basket.
        result = sorted(
            options,
            key=lambda option: (
                not option.is_complete,
                _VERIFICATION_RANK[option.verification_status],
                money(option.total),
                len(option.missing_ingredients),
                option.store_name.casefold(),
                option.store_id,
            ),
        )
        record_performance_seconds("basket_optimization", perf_counter() - started)
        return result

    def optimize(
        self,
        ingredients: Sequence[NormalizedIngredient],
        candidates_by_name: Mapping[str, Sequence[ProductCandidate]],
        stores: Sequence[Store],
        max_stores: int | None,
        *,
        calculate_savings: bool = True,
        _accept_quote_selection=None,
    ) -> OptimizedBasket:
        if _has_coupled_checkout(candidates_by_name, (i.canonical_name for i in ingredients), session=self._quote_cache_context.get()):
            return self._optimize_promotion_groups(
                ingredients,
                candidates_by_name,
                stores,
                max_stores,
                calculate_savings=calculate_savings,
            )
        started = perf_counter()
        increment_performance_counter("basket_calculations")
        if not ingredients:
            result = OptimizedBasket(
                total=0,
                stores=[],
                max_stores=max_stores if max_stores and max_stores > 0 else None,
                savings_vs_single_store=0,
            )
            record_performance_seconds("basket_optimization", perf_counter() - started)
            return result

        # Deduplicate provider results by ID and sort before combinations so
        # iteration order cannot affect ties.
        stores_by_id: dict[str, Store] = {}
        for store in stores:
            stores_by_id.setdefault(str(_value(store, "store_id")), store)
        ordered_stores = sorted(
            stores_by_id.values(),
            key=lambda store: (str(_value(store, "store_id")), str(_value(store, "name"))),
        )
        if not ordered_stores:
            raise IncompleteBasketError("No stores are available for basket optimisation")

        unlimited = max_stores is None or max_stores <= 0
        limit = len(ordered_stores) if unlimited else min(max_stores, len(ordered_stores))
        if limit < 1:
            raise ValueError("max_stores must be at least one, or None for unlimited")

        quoted_ingredients = [
            (
                ingredient,
                *self._candidate_quotes_with_key(
                    ingredient,
                    self._ingredient_candidates(ingredient, candidates_by_name),
                ),
            )
            for ingredient in ingredients
        ]
        # A store with no qualified quote for any requested ingredient can
        # never supply a line. Removing it only removes duplicate unions of
        # exactly the same winning quotes (or incomplete baskets). Keep every
        # supplying store, product and contract, in the original order. This
        # is deliberately after qualification and outside coupled promotions.
        supplying_stores = {quote.store_id for _, quotes, _ in quoted_ingredients for quote in quotes}
        ordered_stores = [store for store in ordered_stores
                          if str(_value(store, "store_id")) in supplying_stores]
        limit = min(limit, len(ordered_stores))
        best_key: tuple[int, Decimal, int, tuple[str, ...], tuple[str, ...]] | None = None
        best_quotes: tuple[BasketItemQuote, ...] | None = None
        best_single_total: Decimal | None = None
        best_single_key: tuple[int, Decimal] | None = None
        store_ids = tuple(str(_value(store, "store_id")) for store in ordered_stores)
        store_subsets = self._eligible_store_subsets(store_ids, limit)
        # Same exact per-store minima and deterministic tie breakers as the
        # scalar subset loop. Reuse the existing bounded, request-local quote
        # vectors instead of millions of repeated dictionary lookups and rank
        # calculations. Coupled campaigns take their separate joint path above.
        store_combinations = len(store_subsets)
        vectors = None
        if any(key is None for _ingredient, _quotes, key in quoted_ingredients):
            # Nutrition alternatives often make one-off baskets with very few
            # feasible subsets. Without reusable quote identities, full vectors
            # repeats work for every impossible subset. Use the same exact
            # scalar checkout, rejecting only proven missing ingredient cover.
            store_bits = {store_id: 1 << index for index, store_id in enumerate(store_ids)}
            ingredient_store_masks = tuple(
                sum({store_bits[q.store_id] for q in quotes if q.store_id in store_bits})
                for _ingredient, quotes, _key in quoted_ingredients
            )
            winning_positions = (1 << store_combinations) - 1
            infeasible_store_combinations = 0
        else:
            vectors = tuple(self._quote_subset_vector(quotes, key, store_ids, store_subsets, limit)
                            for _ingredient, quotes, key in quoted_ingredients)
            leading, infeasible_store_combinations, winning_positions = self._grouped_subset_keys(
                vectors, store_subsets, limit, self._quote_cache_context.get(), winning_mask=True)
            if leading and leading[0] is not None:
                best_single_key, best_single_total = leading[0][:2], leading[0][1]
        # With vectors every subset was included in exact aggregation; inspect
        # only ties on its proven best leading key. The scalar path visits all
        # subsets here. Both preserve ascending order and every tie breaker;
        # neither reduces the menu search budget or prunes by comparison price.
        while winning_positions:
            bit = winning_positions & -winning_positions
            position = bit.bit_length() - 1
            winning_positions ^= bit
            combo_ids = store_subsets[position]
            if vectors is None:
                combo_mask = sum(store_bits[s] for s in combo_ids)
                if any(mask & combo_mask == 0 for mask in ingredient_store_masks):
                    infeasible_store_combinations += 1
                    continue
                chosen = tuple(self._cheapest_quote_for_subset_key(quotes, combo_ids, key)
                               for _ingredient, quotes, key in quoted_ingredients)
                if any(quote is None for quote in chosen):
                    continue
                total = _sum_quotes(chosen)
                verification_rank = self._quotes_verification_rank(chosen)
            else:
                selections = tuple(vector[position] for vector in vectors)
                chosen = tuple(selection.quote for selection in selections)
                total = money(sum((selection.total_price for selection in selections), Decimal(0)))
                verification_rank = max((selection.verification_rank for selection in selections),
                                        default=_VERIFICATION_RANK[BasketVerificationStatus.VERIFIED])
            used_store_ids = tuple(sorted({quote.store_id for quote in chosen}))
            leading_key = (
                verification_rank,
                total,
                len(used_store_ids),
                used_store_ids,
            )
            # Product identity is only the final deterministic tie-breaker.
            # Constructing and sorting those strings for every feasible store
            # subset cannot affect a strict leading-key loser, so defer the
            # work until a subset can actually replace the incumbent.
            if best_key is None or leading_key <= best_key[:4]:
                product_key = tuple(
                    f"{quote.ingredient}:{quote.unit}:{quote.store_id}:"
                    f"{quote.product_id}:{quote.packages_needed}"
                    for quote in sorted(
                        chosen,
                        key=lambda quote: (
                            quote.ingredient,
                            quote.unit,
                            quote.store_id,
                            quote.product_id,
                        ),
                    )
                )
                plan_key = (*leading_key, product_key)
                if best_key is None or plan_key < best_key:
                    best_key = plan_key
                    best_quotes = tuple(chosen)
            single_key = (verification_rank, total)
            if len(combo_ids) == 1 and (
                best_single_key is None or single_key < best_single_key
            ):
                best_single_key = single_key
                best_single_total = total

        increment_performance_counter("store_combinations", store_combinations)
        increment_performance_counter(
            "store_combinations_pruned_infeasible",
            infeasible_store_combinations,
        )

        if best_key is None or best_quotes is None:
            missing = [
                ingredient.canonical_name
                for ingredient in ingredients
                if not self._ingredient_candidates(ingredient, candidates_by_name)
            ]
            detail = f" Missing: {', '.join(missing)}." if missing else ""
            raise IncompleteBasketError(
                "No complete basket can be built with the selected stores." + detail
            )

        # A search caller can reject this exact winner before building public
        # models. This never selects another product/store or alters pricing.
        # Coupled promotions retain the full checkout path above.
        if _accept_quote_selection is not None and not _accept_quote_selection(best_quotes):
            increment_performance_counter("basket_quote_selections_rejected")
            record_performance_seconds("basket_optimization", perf_counter() - started)
            raise QuoteSelectionRejected("Exact checkout rejected before materialization")
        total = best_key[1]
        grouped: dict[str, list[BasketItem]] = {}
        for quote in best_quotes:
            item = quote.to_basket_item()
            grouped.setdefault(item.store_id, []).append(item)

        groups: list[OptimizedStoreGroup] = []
        for store_id in sorted(grouped):
            group_items = sorted(
                grouped[store_id],
                key=lambda item: (item.ingredient, item.product_name, item.product_id),
            )
            source_store = stores_by_id[store_id]
            groups.append(
                OptimizedStoreGroup(
                    store_id=store_id,
                    store_name=str(_value(source_store, "name", store_id)),
                    items=group_items,
                    subtotal=float(_sum_items(group_items)),
                )
            )

        savings: float | None = None
        if calculate_savings and best_single_total is not None:
            savings = float(max(Decimal(0), money(best_single_total - total)))

        result = OptimizedBasket(
            total=float(total),
            stores=groups,
            max_stores=None if unlimited else max_stores,
            savings_vs_single_store=savings,
        )
        record_performance_seconds("basket_optimization", perf_counter() - started)
        return result

    def _optimize_promotion_groups(
        self, ingredients, candidates_by_name, stores, max_stores, *, calculate_savings=True, nested_keys=False
    ):
        """Group interactions require joint product selection within each store cap.

        Keep the existing fast path byte-for-byte for baskets without groups.
        Enumerate only independent ungrouped winners plus all group candidates;
        never silently approximate an oversized interacting promotion problem.
        """
        from itertools import product
        from math import prod

        source_stores = {s.store_id: s for s in stores}
        limit = len(stores) if not max_stores or max_stores < 0 else min(max_stores, len(stores))
        nested_winners = [None] * limit if nested_keys else []
        source_groups = {}
        session = self._quote_cache_context.get()
        for rows in candidates_by_name.values():
            grouped_candidates, _offer_only = _promotion_structure(rows, session)
            for candidate in grouped_candidates:
                for group in candidate.promotion_groups:
                    key = (group.store_id, group.group_id)
                    if key in source_groups and source_groups[key] != group:
                        raise GroupPricingError("Conflicting source promotion group definitions")
                    provenance = candidate.source_provenance
                    if (group.store_id != candidate.store_id or group.chain != candidate.chain
                            or candidate.product_id not in group.eligible_product_ids
                            or not provenance or group.source_snapshot_id != provenance.source_snapshot_id
                            or group.source != provenance.source_provider):
                        raise GroupPricingError("Promotion group lacks exact product/context/source evidence")
                    source_groups[key] = group
        choices = []
        for ingredient in ingredients:
            group_quotes, plain = [], {}
            for candidate in self._ingredient_candidates(ingredient, candidates_by_name):
                if candidate.store_id not in source_stores:
                    continue
                groups = tuple(g for g in source_groups.values()
                               if g.store_id == candidate.store_id
                               and candidate.product_id in g.eligible_product_ids
                               and candidate.source_provenance
                               and g.source_snapshot_id == candidate.source_provenance.source_snapshot_id) if source_groups else ()
                if groups:
                    candidate = candidate.model_copy(update={"promotion_groups": groups})
                if groups and type(self.calculator) is BasketCalculator:
                    try:
                        quote = self.calculator.quote_item(ingredient, candidate, defer_group_checkout=True)
                    except ValueError:
                        continue
                    if not self.verification_policy.allows_quote(quote):
                        continue
                else:
                    quotes = self._candidate_quotes(ingredient, [candidate])
                    if not quotes:
                        continue
                    quote = quotes[0]
                if candidate.promotion_groups or candidate.price is None:
                    if candidate.sale_model != SaleModel.FIXED_PACKAGE:
                        raise GroupPricingError("Kampanjgrupper kräver verifierade fasta förpackningar.")
                    group_quotes.append((quote, candidate))
                elif candidate.store_id not in plain or self._quote_sort_key(
                    quote
                ) < self._quote_sort_key(plain[candidate.store_id][0]):
                    plain[candidate.store_id] = (quote, candidate)
            choices.append([*group_quotes, *plain.values()])
        if any(not c for c in choices):
            if nested_keys:
                return tuple(nested_winners)
            raise IncompleteBasketError("No complete basket can be built with the selected stores.")
        # The exact search counts every Cartesian choice, including store-cap
        # exclusions. Its size is known before pricing: do not burn the entire
        # budget on a search that provably cannot finish within that budget.
        if prod(len(c) for c in choices) > _MAX_GROUP_COMBINATIONS:
            # Optional offers must not make an independently valid base
            # basket unavailable. Keep the exact-search limit unchanged;
            # never approximate campaign groups or relax purchase caps.
            base_candidates = {}
            session = self._quote_cache_context.get()
            for name, rows in candidates_by_name.items():
                cached = session.base_candidate_rows.get(id(rows)) if session is not None and isinstance(rows, tuple) else None
                if cached is not None and cached[0] is rows:
                    base_candidates[name] = cached[1]
                else:
                    filtered = tuple(c for c in rows if c.coverage != "offers_only")
                    base_candidates[name] = filtered
                    # Retain both tuples in the existing request-local scope:
                    # immutable identities stay cacheable; mutable callers never
                    # reuse a filtered result or another request's prices.
                    if session is not None and isinstance(rows, tuple):
                        session.base_candidate_rows[id(rows)] = (rows, filtered)
            if any(len(base_candidates[name]) != len(rows)
                   for name, rows in candidates_by_name.items()):
                if nested_keys:
                    # Same existing verified-base fallback, using the compact
                    # one-pass cap ranking rather than materializing 1/2/3 baskets.
                    return self.same_depth_nested_store_limited_keys(
                        ingredients, base_candidates, stores, max_stores=max_stores
                    )
                basket = self.optimize(ingredients, base_candidates, stores, max_stores,
                                       calculate_savings=False)
                return basket.model_copy(update={"savings_vs_single_store": None,
                    "verification_warnings": [*basket.verification_warnings,
                        "Erbjudandesökningen nådde beräkningsgränsen. Korgen använder verifierade baspriser; erbjudandetilläggen har utelämnats."]})
            raise GroupPricingError("Kampanjkombinationen är för stor för verifierad exakt beräkning.")
        best, best_items, single = None, None, None
        for combination in product(*choices):
            used_stores = {q.store_id for q, _ in combination}
            if max_stores and len(used_stores) > max_stores:
                continue
            items = [
                q.to_basket_item().model_copy(
                    update={
                        "promotion_groups": c.promotion_groups,
                        "checkout_offers": tuple(c.offers),
                    }
                )
                for q, c in combination
            ]
            try:
                priced = self.calculator.quote_group_basket(items)
            except ValueError:
                # This product combination exceeds a source contract; other
                # verified choices within the same store cap remain eligible.
                continue
            total = _sum_items(priced)
            rank = self._quotes_verification_rank(q for q, _ in combination)
            key = (
                rank,
                total,
                len(used_stores),
                tuple(sorted(used_stores)),
                tuple((i.product_id, i.packages_needed) for i in priced),
            )
            if nested_keys:
                # Every combination valid for cap K is also valid for K+1.
                # Enumerate and price once, retaining identical exact winners.
                for cap in range(max(1, len(used_stores)), limit + 1):
                    previous = nested_winners[cap - 1]
                    leading = (rank, total, len(used_stores))
                    if previous is None or leading < previous:
                        nested_winners[cap - 1] = leading
            if best is None or key < best:
                best, best_items = key, priced
            if len(used_stores) == 1 and (single is None or (rank, total) < single):
                single = (rank, total)
        if nested_keys:
            return tuple(nested_winners)
        if best is None:
            raise IncompleteBasketError("No complete basket can be built with the selected stores.")
        grouped = []
        for store_id in sorted({i.store_id for i in best_items}):
            rows = [i for i in best_items if i.store_id == store_id]
            grouped.append(
                OptimizedStoreGroup(
                    store_id=store_id,
                    store_name=source_stores[store_id].name,
                    items=rows,
                    subtotal=float(_sum_items(rows)),
                )
            )
        return OptimizedBasket(
            total=float(best[1]),
            stores=grouped,
            max_stores=max_stores,
            savings_vs_single_store=float(max(0, single[1] - best[1]))
            if calculate_savings and single
            else None,
        )


def single_store_options(
    ingredients: Sequence[NormalizedIngredient],
    candidates_by_name: Mapping[str, Sequence[ProductCandidate]],
    stores: Sequence[Store],
) -> list[StoreBasket]:
    return BasketOptimizer().single_store_options(ingredients, candidates_by_name, stores)


def optimize_basket(
    ingredients: Sequence[NormalizedIngredient],
    candidates_by_name: Mapping[str, Sequence[ProductCandidate]],
    stores: Sequence[Store],
    max_stores: int | None,
) -> OptimizedBasket:
    return BasketOptimizer().optimize(
        ingredients, candidates_by_name, stores, max_stores=max_stores
    )


__all__ = [
    "BasketOptimizer",
    "BasketVerificationPolicy",
    "QuoteCacheStats",
    "StoreSubsetCacheStats",
    "optimize_basket",
    "single_store_options",
]
