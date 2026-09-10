"""Identify economical local products before recipe generation."""

from __future__ import annotations

import asyncio
import re
import unicodedata
from collections import defaultdict
from collections.abc import Sequence

from app.models.product import CheapIngredient, Product
from app.models.store import Store
from app.providers.base import GroceryPriceProvider
from app.services.ingredient_normalizer import canonicalize_ingredient_name

SEARCH_GROUPS: dict[str, tuple[str, ...]] = {
    "protein": (
        "kyckling",
        "nötfärs",
        "fläsk",
        "korv",
        "fisk",
        "ägg",
        "bönor",
        "linser",
    ),
    "kolhydrater": ("pasta", "ris", "potatis", "couscous", "nudlar"),
    "grönsaker": (
        "lök",
        "morot",
        "tomat",
        "paprika",
        "broccoli",
        "kål",
        "frysta grönsaker",
    ),
    "mejeri": ("mjölk", "grädde", "crème fraiche", "ost"),
    "övrigt": ("krossade tomater", "kokosmjölk", "tortillas"),
}


def _search_text(value: str) -> str:
    """Return a stable ASCII-like form for narrow product-name checks."""

    decomposed = unicodedata.normalize("NFKD", value.casefold())
    unaccented = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return re.sub(r"[^a-z0-9]+", " ", unaccented).strip()


def _is_relevant_for_query(query: str, product: Product) -> bool:
    """Reject known broad-search false positives before comparing prices.

    Primat's text search can deliberately return nearby category matches. That
    is useful for most ingredients, so this is not a general exact-name filter.
    The three policies below only cover queries where a nearby match changes
    the kind of ingredient sent to the recipe generator.
    """

    canonical_query = canonicalize_ingredient_name(query)
    if canonical_query not in {"korv", "linser", "bönor"}:
        return True

    name = _search_text(product.name)
    words = name.split()

    if canonical_query == "korv":
        # A sausage name normally ends in "-korv". Korvbröd (including the
        # uncommon split spelling "korv bröd") is a bakery product instead.
        if "brod" in words or any(word.endswith("korvbrod") for word in words):
            return False
        return any(word.endswith("korv") for word in words)

    if canonical_query == "linser":
        # Examples accepted: "röda linser", "belugalinser", "grön lins".
        # Category-neighbour products such as gula ärter have no lins-word.
        return any(word.endswith(("lins", "linser")) for word in words)

    # Here "bönor" means the protein staple (kidney-, vita, svarta etc.), not
    # green beans sold as a vegetable. Keep this exception deliberately small.
    if "grona" in words or any(
        phrase in f" {name} " for phrase in (" haricots verts ", " brytbonor ", " vaxbonor ")
    ):
        return False
    return any(word.endswith(("bona", "bonor")) for word in words)


def _matches_cheap_query(query: str, product: Product) -> bool:
    """Match an unscoped /cheap row to one configured ingredient query."""

    canonical_query = canonicalize_ingredient_name(query)
    if canonical_query in {"korv", "linser", "bönor"}:
        return _is_relevant_for_query(query, product)
    return canonicalize_ingredient_name(product.canonical_name) == canonical_query


class CheapProductsService:
    """Build compact, structured economic signals for a recipe generator."""

    async def find(
        self,
        provider: GroceryPriceProvider,
        stores: Sequence[Store],
        limit_per_group: int = 6,
    ) -> list[CheapIngredient]:
        if limit_per_group < 1:
            raise ValueError("limit_per_group must be at least one")
        store_ids = [store.store_id for store in stores]
        if not store_ids:
            return []

        semaphore = asyncio.Semaphore(6)

        async def search(group: str, query: str) -> tuple[str, str, list[Product]]:
            async with semaphore:
                return group, query, await provider.search_products(query, store_ids)

        results = await asyncio.gather(
            *(search(group, query) for group, queries in SEARCH_GROUPS.items() for query in queries)
        )

        by_group: dict[str, dict[tuple[str, str], Product]] = defaultdict(dict)
        for group, query, products in results:
            for product in products:
                if not _is_relevant_for_query(query, product):
                    continue
                if product.normalized_unit_price is None or product.normalized_unit is None:
                    # Unknown purchase semantics are not an economic signal.
                    # Keeping them out is safer than inventing a package or
                    # comparison-unit conversion here.
                    continue
                key = (product.store_id, product.product_id)
                previous = by_group[group].get(key)
                if previous is None or (
                    product.normalized_unit_price,
                    float(product.effective_price),
                    product.name.casefold(),
                ) < (
                    previous.normalized_unit_price,
                    float(previous.effective_price),
                    previous.name.casefold(),
                ):
                    by_group[group][key] = product

        # Primat exposes a comparison-price sorted /cheap endpoint. Providers
        # may offer this optional fast path; its rows are still bucketed and
        # filtered locally before becoming an LLM signal.
        cheap_loader = getattr(provider, "get_cheap_products", None)
        if cheap_loader is not None:
            cheap_rows = await cheap_loader(store_ids, limit=100)
            for product in cheap_rows:
                if product.normalized_unit_price is None or product.normalized_unit is None:
                    continue
                for group, queries in SEARCH_GROUPS.items():
                    if any(_matches_cheap_query(query, product) for query in queries):
                        by_group[group].setdefault((product.store_id, product.product_id), product)

        signals: list[CheapIngredient] = []
        for group in SEARCH_GROUPS:
            products = sorted(
                by_group.get(group, {}).values(),
                key=lambda product: (
                    product.normalized_unit_price,
                    float(product.effective_price),
                    product.canonical_name.casefold(),
                    product.store_name.casefold(),
                    product.product_id,
                ),
            )

            # Do not let several package variants of one ingredient crowd all
            # other useful cheap ingredients out of the LLM context.
            cheapest_by_ingredient: dict[str, Product] = {}
            for product in products:
                cheapest_by_ingredient.setdefault(product.canonical_name, product)
            selected = sorted(
                cheapest_by_ingredient.values(),
                key=lambda product: (
                    product.normalized_unit_price,
                    float(product.effective_price),
                    product.canonical_name.casefold(),
                    product.store_name.casefold(),
                    product.product_id,
                ),
            )[:limit_per_group]

            for product in selected:
                signals.append(
                    CheapIngredient(
                        ingredient=product.canonical_name,
                        product=product.name,
                        product_id=product.product_id,
                        store=product.store_name,
                        store_id=product.store_id,
                        price=float(product.effective_price),
                        unit_price=product.normalized_unit_price,
                        unit=product.normalized_unit,
                        is_offer=(
                            float(product.effective_price) < product.price
                            or bool(product.active_offers())
                        ),
                    )
                )
        return signals


async def find_cheap_products(
    provider: GroceryPriceProvider,
    stores: Sequence[Store],
    limit_per_group: int = 6,
) -> list[CheapIngredient]:
    return await CheapProductsService().find(provider, stores, limit_per_group=limit_per_group)


__all__ = ["SEARCH_GROUPS", "CheapProductsService", "find_cheap_products"]
