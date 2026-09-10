"""Deterministic meal-planning services.

The modules in this package deliberately contain no network or LLM logic.  They
turn already structured recipes and price data into reproducible shopping
baskets.
"""

from .basket_calculator import BasketCalculator
from .basket_optimizer import BasketOptimizer
from .cheap_products import CheapProductsService
from .ingredient_normalizer import IngredientNormalizer
from .price_universe import (
    BasketResultCache,
    PackageCostCache,
    PriceUniverse,
    PriceUniverseBuilder,
    PriceUniverseKey,
    PriceUniverseManager,
    SemanticCandidateCache,
)
from .product_matcher import ProductMatcher

__all__ = [
    "BasketCalculator",
    "BasketOptimizer",
    "BasketResultCache",
    "CheapProductsService",
    "IngredientNormalizer",
    "PackageCostCache",
    "PriceUniverse",
    "PriceUniverseBuilder",
    "PriceUniverseKey",
    "PriceUniverseManager",
    "ProductMatcher",
    "SemanticCandidateCache",
]
