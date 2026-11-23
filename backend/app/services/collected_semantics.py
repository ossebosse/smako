"""Classify a product the way Smako's own collection does.

Smako's own sources are classified when collected (grocery_data
``ProductNormalizer``) and read back by ``OwnGroceryPriceProvider``, which maps
the stored identity onto the backend's food names.  Products that reach Smako
another way, such as Primat's ICA catalogue, get the same classification here,
so the recipe matcher treats them like collected products.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.models.product import SemanticConfidence
from app.services.product_semantics import is_non_human_food

from grocery_data.app.domain import Confidence
from grocery_data.app.normalization import food_identity


def collected_semantics(
    name: str,
    category_path: Sequence[str],
) -> dict[str, object]:
    """``canonical_food``, ``product_role``, ``product_form``, ``semantic_confidence``."""

    from app.providers.own import OwnGroceryPriceProvider

    categories = tuple(str(part).strip() for part in category_path if str(part).strip())
    category = " > ".join(categories)
    if is_non_human_food(name, category):
        return {
            "canonical_food": "non_human_food",
            "product_role": "non_human_food",
            "product_form": "pet_food",
            "semantic_confidence": SemanticConfidence.REJECTED,
        }
    identity, confidence = food_identity(name, categories)
    canonical_food, product_role = OwnGroceryPriceProvider._backend_semantics(
        identity, None, name
    )
    return {
        "canonical_food": canonical_food,
        "product_role": product_role,
        "product_form": None,
        "semantic_confidence": (
            SemanticConfidence.HIGH
            if canonical_food is not None and confidence == Confidence.HIGH
            else SemanticConfidence.LOW
        ),
    }


__all__ = ["collected_semantics"]
