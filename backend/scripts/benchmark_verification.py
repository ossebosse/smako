"""Shared verification policy for standalone search benchmarks.

The application wires this policy through :class:`MealPlanService`. Benchmark
scripts instantiate the lower-level optimizers directly, so they must do the
same explicitly instead of inheriting ``BasketOptimizer``'s legacy-compatible
constructor default.
"""

from __future__ import annotations

from app.services.basket_optimizer import BasketOptimizer, BasketVerificationPolicy
from app.services.menu_optimizer import MenuOptimizer


def strict_live_basket_optimizer() -> BasketOptimizer:
    """Return an optimizer with the API's default live confidence gates."""

    return BasketOptimizer(
        verification_policy=BasketVerificationPolicy.strict_live(),
    )


def strict_live_menu_optimizer() -> MenuOptimizer:
    """Return a menu optimizer that cannot select unknown purchase facts."""

    return MenuOptimizer(basket_optimizer=strict_live_basket_optimizer())


__all__ = ["strict_live_basket_optimizer", "strict_live_menu_optimizer"]
