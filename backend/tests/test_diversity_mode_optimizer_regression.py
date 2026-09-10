from __future__ import annotations

from collections.abc import Iterable
from itertools import combinations

from app.models.product import (
    ProductCandidate,
    QuantityConfidence,
    SemanticConfidence,
)
from app.models.recipe import Recipe, RecipeIngredient
from app.models.store import Store
from app.services.menu_optimizer import DiversityConstraints, MenuOptimizer


def _store() -> Store:
    return Store(
        store_id="lund",
        name="Testbutik Lund",
        chain="Testkedjan",
        city="Lund",
        postal_code="22350",
    )


def _product(
    ingredient: str,
    price: float,
    *,
    package_quantity: float = 5000,
) -> ProductCandidate:
    return ProductCandidate(
        product_id=f"lund-{ingredient}",
        product_name=f"{ingredient} testförpackning",
        canonical_name=ingredient,
        store_id="lund",
        store_name="Testbutik Lund",
        package_quantity=package_quantity,
        package_unit="g",
        usable_quantity=package_quantity,
        usable_unit="g",
        quantity_confidence=QuantityConfidence.EXACT,
        semantic_confidence=SemanticConfidence.HIGH,
        price=price,
        effective_price=price,
        match_score=1,
    )


def _recipe(
    name: str,
    ingredients: Iterable[tuple[str, float]],
) -> Recipe:
    return Recipe(
        name=name,
        servings=4,
        ingredients=[
            RecipeIngredient(
                name=ingredient,
                canonical_name=ingredient,
                quantity=quantity,
                unit="g",
            )
            for ingredient, quantity in ingredients
        ],
        instructions=["Tillaga till en komplett middag."],
    )


def test_cheapest_may_repeat_shared_rice_tofu_menu_while_varied_pays_exact_premium() -> None:
    similar = [
        _recipe(
            f"Billig tofu-ris-panna {index}",
            [
                ("tofu", 350 + index * 10),
                ("ris", 280 + index * 10),
                ("gul lök", 120 + index * 10),
            ],
        )
        for index in range(1, 5)
    ]
    alternatives = [
        _recipe("Linsgryta med potatis", [("linser", 300), ("potatis", 800), ("vitkål", 400)]),
        _recipe("Kycklingpasta med morot", [("kyckling", 600), ("pasta", 350), ("morot", 400)]),
        _recipe("Äggcouscous med broccoli", [("ägg", 400), ("couscous", 350), ("broccoli", 400)]),
    ]
    recipes = [*similar, *alternatives]
    products = {
        "tofu": [_product("tofu", 40)],
        "ris": [_product("ris", 30)],
        "gul lök": [_product("gul lök", 30)],
        # Each alternative contributes exactly 10 SEK and does not share a
        # package with another family.
        "linser": [_product("linser", 4)],
        "potatis": [_product("potatis", 3)],
        "vitkål": [_product("vitkål", 3)],
        "kyckling": [_product("kyckling", 4)],
        "pasta": [_product("pasta", 3)],
        "morot": [_product("morot", 3)],
        "ägg": [_product("ägg", 4)],
        "couscous": [_product("couscous", 3)],
        "broccoli": [_product("broccoli", 3)],
    }

    similar_names = {recipe.name for recipe in similar}
    families = {
        **{name: "tofu-ris-panna" for name in similar_names},
        alternatives[0].name: "linsgryta",
        alternatives[1].name: "kycklingpasta",
        alternatives[2].name: "äggcouscous",
    }
    primary = {
        **{name: "tofu" for name in similar_names},
        alternatives[0].name: "linser",
        alternatives[1].name: "kyckling",
        alternatives[2].name: "ägg",
    }
    carbohydrates = {
        **{name: "ris" for name in similar_names},
        alternatives[0].name: "potatis",
        alternatives[1].name: "pasta",
        alternatives[2].name: "couscous",
    }
    cooking_methods = {
        **{name: "pan" for name in similar_names},
        alternatives[0].name: "simmer",
        alternatives[1].name: "boil",
        alternatives[2].name: "steam",
    }
    dish_forms = {
        **{name: "one-pan" for name in similar_names},
        alternatives[0].name: "stew",
        alternatives[1].name: "pasta",
        alternatives[2].name: "grain-bowl",
    }
    pairwise = {
        tuple(sorted((left.name.casefold(), right.name.casefold()))): (
            0.90 if left in similar and right in similar else 0.10
        )
        for left, right in combinations(recipes, 2)
    }
    common = {
        "recipe_families": families,
        "primary_ingredients": primary,
        "carbohydrates": carbohydrates,
        "cooking_methods": cooking_methods,
        "dish_forms": dish_forms,
        "pairwise_recipe_similarities": pairwise,
    }

    variants = MenuOptimizer().optimize_variants(
        recipes,
        products,
        [_store()],
        {
            "cheapest": DiversityConstraints(
                max_same_recipe_family=None,
                max_same_primary_ingredient_meals=None,
                max_same_carbohydrate_meals=None,
                max_same_cooking_method=None,
                max_same_dish_form=None,
                max_pairwise_recipe_similarity=None,
                **common,
            ),
            "varied": DiversityConstraints(
                max_same_recipe_family=1,
                max_same_primary_ingredient_meals=2,
                max_same_carbohydrate_meals=2,
                max_same_cooking_method=2,
                max_same_dish_form=1,
                max_pairwise_recipe_similarity=0.45,
                **common,
            ),
        },
        recipe_count=4,
        max_stores=1,
        beam_width=50,
    )

    assert variants.errors == {}
    cheapest = variants.results["cheapest"]
    varied = variants.results["varied"]
    assert {recipe.name for recipe in cheapest.recipes} == similar_names
    assert cheapest.basket.total == 100
    assert cheapest.basket_audit.passed is True

    varied_names = {recipe.name for recipe in varied.recipes}
    assert len(varied_names & similar_names) == 1
    assert varied_names >= {recipe.name for recipe in alternatives}
    assert varied.basket.total == 130
    assert varied.basket.total - cheapest.basket.total == 30
    assert varied.basket_audit.passed is True
    assert (
        max(
            pairwise[tuple(sorted((left.casefold(), right.casefold())))]
            for left, right in combinations(varied_names, 2)
        )
        < 0.45
    )
    assert varied.stats.diversity_rejections > 0
