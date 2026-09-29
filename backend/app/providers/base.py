from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from datetime import date

from ..models import OfferKind, Product, SaleModel, Store

_NON_FIXED_SALE_MODELS = {
    SaleModel.SOLD_BY_WEIGHT,
    SaleModel.SOLD_BY_PIECE,
    SaleModel.VARIABLE_WEIGHT_PACKAGE,
}


def _same_price(left: float, right: float) -> bool:
    return abs(left - right) <= 0.005


class GroceryPriceProvider(ABC):
    """Replaceable asynchronous boundary for grocery price sources."""

    def __init__(self, use_member_prices: bool = False) -> None:
        self.use_member_prices = use_member_prices

    @abstractmethod
    async def find_stores(self, postal_code: str) -> list[Store]:
        """Return relevant stores, ordered by relevance/distance."""

    @abstractmethod
    async def search_products(
        self,
        query: str,
        store_ids: list[str],
    ) -> list[Product]:
        """Search products in the selected stores."""

    @abstractmethod
    async def get_store_products(self, store_id: str) -> list[Product]:
        """Return all available products for one store."""

    @abstractmethod
    async def get_offers(self, store_id: str) -> list[Product]:
        """Return products having at least one active offer."""

    def apply_price_policy(
        self,
        products: Iterable[Product],
        on_date: date | None = None,
    ) -> list[Product]:
        """Set effective one-package prices without inventing price data.

        A multipack is not applied here: eligibility depends on the eventual
        package count and belongs in the basket calculator.
        """

        result: list[Product] = []
        for product in products:
            non_fixed = product.sale_model in _NON_FIXED_SALE_MODELS
            active_offers = product.active_offers(on_date)
            eligible_prices = [product.price] if product.price is not None else []
            for offer in active_offers:
                if offer.required_packages != 1:
                    continue
                if non_fixed and offer.max_quantity is not None:
                    # max_quantity is expressed in source purchase units. For
                    # weight/piece/variable products that cap cannot be mapped
                    # safely to the recipe quantity yet, so the conditional
                    # price remains diagnostic metadata and never becomes an
                    # unlimited checkout rate.
                    continue
                if offer.kind == OfferKind.CAMPAIGN or (
                    offer.kind == OfferKind.MEMBER and self.use_member_prices
                ):
                    eligible_prices.append(offer.price)
            if self.use_member_prices and product.member_price is not None:
                capped_member_price = non_fixed and any(
                    offer.max_quantity is not None
                    and offer.required_packages == 1
                    and offer.kind == OfferKind.MEMBER
                    and _same_price(offer.price, product.member_price)
                    for offer in active_offers
                )
                if not capped_member_price:
                    eligible_prices.append(product.member_price)
            if not eligible_prices:
                continue
            effective_price = min(eligible_prices)
            result.append(
                product.model_copy(update={"effective_price": effective_price}, deep=True)
            )
        return result
