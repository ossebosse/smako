"""Sanitized, read-only trace of the reviewed Lidl rows through existing stages."""
from app.models.ingredient import NormalizedIngredient
from app.models.product import ProductCandidate
from app.services.basket_calculator import BasketCalculator
from app.services.user_pricing import price_candidate_for_context

from grocery_data.app.domain.promotion_pricing import UserPricingContext


def trace_reviewed_offers(prepared, products, purchase_date, plan=None):
    pool = prepared.economic_pool
    stages = (
        "matched_candidates_by_name", "semantic_candidates_by_name", "candidates_by_name",
    )
    result = []
    for product in products:
        identity = (product.store_id, product.product_id)
        row = {"product_id": product.product_id, "store_id": product.store_id,
               "name": product.name, "ordinary_price": product.price,
               "source_observed_at": product.source_provenance.source_observed_at.isoformat(),
               "purchase_date": purchase_date.isoformat(), "stages": {}}
        for stage in stages:
            row["stages"][stage] = [
                canonical for canonical, candidates in getattr(pool, stage).items()
                if any((c.store_id, c.product_id) == identity for c in candidates)
            ]
        row["in_universe"] = any((p.store_id, p.product_id) == identity for p in prepared.universe.products)
        row["selected"] = False
        row["relevant_checkout_comparisons"] = []
        if plan:
            for store in plan.optimized_basket.stores:
                for item in store.items:
                    if (item.store_id, item.product_id) == identity:
                        row["selected"] = True
                    # This is diagnostic identity relevance, never a price join.
                    canonicals = row["stages"]["semantic_candidates_by_name"]
                    if not any(item.ingredient.split(" [")[0] == c for c in canonicals):
                        continue
                    need = NormalizedIngredient(canonical_name=item.ingredient,
                        required_quantity=item.required_quantity, unit=item.unit)
                    comparison = {"ingredient": item.ingredient, "required_quantity": item.required_quantity,
                                  "unit": item.unit, "selected_product_id": item.product_id,
                                  "selected_store_id": item.store_id, "selected_checkout": item.total_price}
                    try:
                        candidate = price_candidate_for_context(ProductCandidate.from_product(product, 1),
                            UserPricingContext(), on_date=purchase_date)
                        quote = BasketCalculator().quote_item(need, candidate)
                        comparison.update({"offer_checkout": float(quote.total_price),
                                           "whole_packages": quote.packages_needed,
                                           "surplus": quote.waste_quantity})
                    except ValueError as exc:
                        comparison["rejected_reason"] = str(exc)
                    row["relevant_checkout_comparisons"].append(comparison)
        result.append(row)
    return result


def add_reviewed_candidates_to_preserved_pool(baseline_pool, products, purchase_date):
    """Controlled A/B: preserve baseline generator signals and candidate rows.

    Adds only the optional store's candidates for already-existing ingredients
    through the existing matcher and selector. This deliberately does not test
    regeneration of economic signals or approval of additional recipe families.
    """
    from app.services.economic_ingredient_selector import EconomicIngredientSelector

    selector = EconomicIngredientSelector()
    maps = {stage: {key: list(value) for key, value in getattr(baseline_pool, stage).items()}
            for stage in ("matched_candidates_by_name", "semantic_candidates_by_name", "candidates_by_name")}
    allowed = {signal.canonical for signal in baseline_pool.ingredients}
    for entry in selector.taxonomy:
        if entry.canonical not in allowed:
            continue
        ingredient = NormalizedIngredient(canonical_name=entry.canonical,
            required_quantity=entry.typical_meal_quantity, unit=entry.expected_unit)
        matched = selector.matcher.match(ingredient, products)
        projected = []
        for candidate in matched:
            try:
                projected.append(price_candidate_for_context(candidate, UserPricingContext(), on_date=purchase_date))
            except ValueError:
                continue
        semantic = selector.validate_semantic_candidates(entry, projected)
        selected = selector._select_store_candidates(entry, semantic) if semantic else []
        for stage, rows in zip(maps, (projected, semantic, selected), strict=True):
            original = maps[stage].setdefault(entry.canonical, [])
            identities = {(c.store_id, c.product_id) for c in original}
            original.extend(c for c in rows if (c.store_id, c.product_id) not in identities)
    return baseline_pool.model_copy(update=maps)
