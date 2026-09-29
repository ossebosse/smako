"""Deterministic, semantics-first matching of ingredients to grocery products."""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from difflib import SequenceMatcher

from app.models.ingredient import NormalizedIngredient
from app.models.product import (
    Product,
    ProductCandidate,
    QuantityConfidence,
    SaleModel,
    SemanticConfidence,
)
from app.services.ingredient_normalizer import (
    CANONICAL_ALIASES,
    _search_text,
    canonicalize_ingredient_name,
)
from app.services.performance_trace import increment_performance_counter
from app.services.product_semantics import (
    SemanticMatchResult,
    evaluate_product_semantics,
    is_non_human_food,
)
from app.services.purchase_quantity_resolver import PurchaseQuantityResolver

_CONFIDENCE_RANK: dict[SemanticConfidence, int] = {
    SemanticConfidence.REJECTED: 0,
    SemanticConfidence.LOW: 1,
    SemanticConfidence.MEDIUM: 2,
    SemanticConfidence.HIGH: 3,
    SemanticConfidence.EXACT: 4,
}


def _contains_phrase(text: str, phrase: str) -> bool:
    return f" {_search_text(phrase)} " in f" {text} "


def _explicit_offer_product(ingredient, product, semantic):
    """An exact requested whole product is not a request for its ingredients.

    Restricted to the existing qualified physical offer sources. No fuzzy name,
    GTIN, nutritional declaration, generic recipe substitution or price binding
    is inferred here; all source and checkout gates remain authoritative.
    """
    if semantic.compatible:
        return semantic
    prov = product.source_provenance
    literal = lambda value: re.sub(r'\s+', ' ', value).strip().casefold()
    if (not prov or prov.source_role != 'offers' or product.price_context_type != 'physical_store'
            or prov.retailer_id_namespace not in {'willys:flyer-document-ad', 'lidl:public-product'}
            or not product.offers or not all(o.campaign_evidence for o in product.offers)
            or literal(ingredient.canonical_name) in CANONICAL_ALIASES
            or literal(ingredient.canonical_name) != literal(product.name)
            or is_non_human_food(product.name, product.category or '')):
        return semantic
    return SemanticMatchResult(compatible=True, confidence=SemanticConfidence.EXACT,
        canonical_food='explicit_product:' + literal(product.name),
        product_role='explicit_whole_product', product_form='as_sold',
        evidence=['exact_requested_complete_product_name', 'qualified_physical_offer',
                  'not_generic_recipe_substitution', *semantic.evidence])


def _piece_count_from_name(target: str, name: str) -> float | None:
    """Read an explicit package count for narrowly approved piece goods."""

    if target != "tortillas":
        return None
    match = re.search(r"(?<!\d)(\d+)\s*(?:-|x\s*)?pack\b", name, flags=re.IGNORECASE)
    if match is None:
        return None
    count = int(match.group(1))
    return float(count) if count > 0 else None


def _lexical_score(
    target: str,
    product: Product,
    semantic: SemanticMatchResult,
) -> float:
    """Score lexical evidence only after food/role/form compatibility passed."""

    name = product.name
    category = product.category or ""
    product_text = _search_text(f"{name} {category}")
    target_text = _search_text(target)
    declared_canonical = canonicalize_ingredient_name(product.canonical_name)

    # Semantic confidence is the ceiling: fuzzy text can never upgrade a weak
    # or rejected semantic interpretation into a production candidate.
    confidence_ceiling = {
        SemanticConfidence.EXACT: 1.0,
        SemanticConfidence.HIGH: 0.98,
        SemanticConfidence.MEDIUM: 0.74,
        SemanticConfidence.LOW: 0.45,
        SemanticConfidence.REJECTED: 0.0,
    }[semantic.confidence]

    if declared_canonical == target and semantic.confidence in {
        SemanticConfidence.EXACT,
        SemanticConfidence.HIGH,
    }:
        return 1.0
    if declared_canonical == target and semantic.confidence == SemanticConfidence.MEDIUM:
        return confidence_ceiling

    aliases = CANONICAL_ALIASES.get(target, (target,))
    if any(_contains_phrase(product_text, alias) for alias in aliases):
        lexical = 0.94
    elif semantic.confidence in {SemanticConfidence.EXACT, SemanticConfidence.HIGH}:
        # Compound product identities such as Hushållsost and Kycklinglårfilé
        # have already passed an explicit food/role interpretation.
        lexical = 0.92
    else:
        target_tokens = set(target_text.split())
        product_tokens = set(product_text.split())
        union = target_tokens | product_tokens
        overlap = len(target_tokens & product_tokens) / len(union) if union else 0.0
        similarity = SequenceMatcher(None, target_text, product_text).ratio()
        lexical = max(0.32 + 0.58 * overlap, 0.74 * similarity)

    if target == "köttfärs" and semantic.product_role in {"beef_mince", "mixed_mince"}:
        lexical = max(lexical, 0.86)

    return round(min(max(lexical, 0.0), confidence_ceiling), 4)


class ProductMatcher:
    """Return only dimensionally and semantically valid product candidates.

    The default production policy accepts exact/high semantic confidence.
    Metadata-only medium matches are available for controlled experiments but
    never enabled implicitly. Price is only a final tie-break after semantic
    compatibility and textual evidence.
    """

    def __init__(
        self,
        minimum_score: float = 0.58,
        *,
        allow_medium_semantic: bool = False,
    ) -> None:
        if not 0 <= minimum_score <= 1:
            raise ValueError("minimum_score must be between zero and one")
        self.minimum_score = minimum_score
        self.allow_medium_semantic = allow_medium_semantic
        self.quantity_resolver = PurchaseQuantityResolver()

    @property
    def minimum_semantic_confidence(self) -> SemanticConfidence:
        return SemanticConfidence.MEDIUM if self.allow_medium_semantic else SemanticConfidence.HIGH

    def evaluate_semantics(
        self,
        ingredient: NormalizedIngredient,
        product: Product,
    ) -> SemanticMatchResult:
        """Expose the auditable decision even when a product is rejected."""

        # Preserve an exact upstream recipe identity for the semantic gate.
        # ``evaluate_product_semantics`` resolves the shared matcher canonical
        # itself, while still being able to enforce a narrower source identity
        # such as ``red_lentils`` before it is collapsed to generic ``linser``.
        return _explicit_offer_product(ingredient, product,
            evaluate_product_semantics(ingredient.canonical_name, product))

    def match(
        self,
        ingredient: NormalizedIngredient,
        products: Iterable[Product],
        store_ids: Iterable[str] | None = None,
    ) -> list[ProductCandidate]:
        target = canonicalize_ingredient_name(ingredient.canonical_name)
        allowed_stores = set(store_ids) if store_ids is not None else None
        candidates: list[ProductCandidate] = []

        for product in products:
            if product.purchase_terms and product.purchase_terms.usage in {"variant_selection_required", "blocked"}:
                continue
            if allowed_stores is not None and product.store_id not in allowed_stores:
                continue

            increment_performance_counter("semantic_comparisons")
            increment_performance_counter("product_match_calculations")

            semantic = self.evaluate_semantics(ingredient, product)
            if not semantic.compatible:
                continue
            if (
                _CONFIDENCE_RANK[semantic.confidence]
                < _CONFIDENCE_RANK[self.minimum_semantic_confidence]
            ):
                continue

            score = _lexical_score(target, product, semantic)
            if score < self.minimum_score:
                continue

            from app.services.purchase_quantity_resolver import project_purchase_shape

            interpreted = project_purchase_shape(product)
            resolution = self.quantity_resolver.resolve(
                interpreted,
                required_quantity=ingredient.required_quantity,
                required_unit=ingredient.unit,
            )
            if not resolution.resolved:
                piece_count = (
                    _piece_count_from_name(target, product.name)
                    if ingredient.unit == "st"
                    else None
                )
                if piece_count is None:
                    continue
                interpreted = Product.model_validate(
                    product.model_copy(
                        update={
                            "sale_model": SaleModel.FIXED_PACKAGE,
                            "package_quantity": piece_count,
                            "package_unit": "st",
                            "usable_quantity": piece_count,
                            "usable_unit": "st",
                            "quantity_confidence": QuantityConfidence.DERIVED,
                            "variable_weight": False,
                        }
                    ).model_dump()
                )
                resolution = self.quantity_resolver.resolve(
                    interpreted,
                    required_quantity=ingredient.required_quantity,
                    required_unit=ingredient.unit,
                )
                if not resolution.resolved:
                    continue

            effective_price = float(product.effective_price)
            regular_price = float(product.price) if product.price is not None else None
            if (
                not math.isfinite(effective_price)
                or effective_price <= 0
                or (regular_price is not None and (not math.isfinite(regular_price) or regular_price <= 0))
            ):
                continue

            update: dict[str, object] = {
                "canonical_name": target,
                "quantity_confidence": resolution.quantity_confidence,
                "match_score": score,
                "canonical_food": semantic.canonical_food,
                "food_family": semantic.food_family,
                "product_role": semantic.product_role,
                "product_form": semantic.product_form,
                "semantic_confidence": semantic.confidence,
            }
            # The coordinated model adds this field to candidates. Keeping the
            # check makes the matcher compatible with independently versioned
            # fixtures during migration.
            if "semantic_evidence" in ProductCandidate.model_fields:
                update["semantic_evidence"] = semantic.evidence

            candidate = ProductCandidate.from_product(interpreted, match_score=score).model_copy(
                update=update
            )
            # model_copy deliberately avoids revalidation; all adjusted fields
            # above were normalized explicitly, but round-trip once to enforce
            # the complete candidate schema and future invariants.
            candidates.append(ProductCandidate.model_validate(candidate.model_dump()))

        ordered = sorted(
            candidates,
            key=lambda candidate: (
                -_CONFIDENCE_RANK[candidate.semantic_confidence],
                -candidate.match_score,
                candidate.effective_price,
                candidate.product_name.casefold(),
                candidate.store_id,
                candidate.product_id,
            ),
        )
        increment_performance_counter("semantic_candidates_returned", len(ordered))
        return ordered


def match_products(
    ingredient: NormalizedIngredient,
    products: Iterable[Product],
    store_ids: Iterable[str] | None = None,
    minimum_score: float = 0.58,
    *,
    allow_medium_semantic: bool = False,
) -> list[ProductCandidate]:
    """Functional wrapper for candidate matching."""

    return ProductMatcher(
        minimum_score=minimum_score,
        allow_medium_semantic=allow_medium_semantic,
    ).match(ingredient, products, store_ids=store_ids)


__all__ = ["ProductMatcher", "match_products"]
