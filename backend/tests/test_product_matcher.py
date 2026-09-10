import pytest
from app.models.ingredient import NormalizedIngredient
from app.models.product import Product, QuantityConfidence
from app.services.basket_calculator import BasketCalculator
from app.services.product_matcher import ProductMatcher


def product(
    product_id: str,
    name: str,
    canonical_name: str,
    *,
    store_id: str = "s1",
    package_quantity: float = 500,
    package_unit: str = "g",
    price: float = 39.90,
    category: str = "test",
    usable_quantity: float | None = None,
    usable_unit: str | None = None,
    quantity_confidence: QuantityConfidence = QuantityConfidence.UNKNOWN,
) -> Product:
    return Product(
        product_id=product_id,
        name=name,
        canonical_name=canonical_name,
        category=category,
        store_id=store_id,
        store_name=store_id,
        package_quantity=package_quantity,
        package_unit=package_unit,
        usable_quantity=usable_quantity,
        usable_unit=usable_unit,
        quantity_confidence=quantity_confidence,
        price=price,
    )


def test_butter_matches_multiple_real_butters_but_not_spreads() -> None:
    ingredient = NormalizedIngredient(canonical_name="smör", required_quantity=400, unit="g")
    products = [
        product("arla", "Arla Svenskt Smör 500 g", "smör"),
        product("ica", "ICA Smör 500 g", "smör"),
        product("garant", "Garant Smör 500 g", "smör"),
        product("bregott", "Bregott Normalsaltat 500 g", "smör"),
        product("margarin", "Milda Margarin 500 g", "margarin"),
        product("lagom", "Lätt & Lagom 500 g", "matfettsblandning"),
    ]

    matches = ProductMatcher().match(ingredient, products)

    assert [match.product_id for match in matches] == ["arla", "garant", "ica"]
    assert all(match.match_score == 1 for match in matches)


def test_minced_beef_does_not_match_mixed_or_generic_mince() -> None:
    ingredient = NormalizedIngredient(canonical_name="nötfärs", required_quantity=700, unit="g")
    products = [
        product("beef", "ICA Nötfärs 12% 500 g", "nötfärs"),
        product("mixed", "ICA Blandfärs 500 g", "blandfärs"),
        product("generic", "Butikens Köttfärs 500 g", "köttfärs"),
        product("veggie", "Formbar vegofärs 500 g", "vegofärs"),
    ]

    matches = ProductMatcher().match(ingredient, products)

    assert [match.product_id for match in matches] == ["beef"]


def test_generic_meat_mince_can_use_beef_or_mixed_but_not_veggie() -> None:
    ingredient = NormalizedIngredient(canonical_name="köttfärs", required_quantity=700, unit="g")
    products = [
        product("beef", "Nötfärs 500 g", "nötfärs"),
        product("mixed", "Blandfärs 500 g", "blandfärs"),
        product("veggie", "Formbar vegofärs 500 g", "vegofärs"),
    ]

    matches = ProductMatcher().match(ingredient, products)

    assert {match.product_id for match in matches} == {"beef", "mixed"}


def test_matcher_filters_stores_and_incompatible_units() -> None:
    ingredient = NormalizedIngredient(canonical_name="mjölk", required_quantity=1000, unit="ml")
    products = [
        product(
            "milk-s1",
            "Standardmjölk 1 l",
            "mjölk",
            store_id="s1",
            package_quantity=1000,
            package_unit="ml",
        ),
        product(
            "milk-s2",
            "Standardmjölk 1 l",
            "mjölk",
            store_id="s2",
            package_quantity=1000,
            package_unit="ml",
        ),
        product("powder", "Mjölkpulver 500 g", "mjölk", package_unit="g"),
    ]

    matches = ProductMatcher().match(ingredient, products, store_ids=["s1"])

    assert [match.product_id for match in matches] == ["milk-s1"]


@pytest.mark.parametrize(
    ("recipe_canonical", "product_name", "source_food", "quantity", "unit"),
    [
        ("milk", "Hjordnära Ekologisk Lättmjölk 1 l", "milk", 1000, "ml"),
        ("cream", "Vispgrädde 5 dl", "cream", 500, "ml"),
        ("eggs", "Bruna Ägg 10-pack", "eggs", 10, "st"),
        ("pork_meat", "Fläskytterfilé 900 g", "pork_meat", 900, "g"),
        ("falukorv", "Falukorv 800 g", "falukorv", 800, "g"),
        ("fish_meat", "Ryggfilé Stillahavstorsk 400 g", "fish_meat", 400, "g"),
        ("chickpeas", "Kikärter 400 g", "chickpeas", 400, "g"),
        ("leek", "Purjolök Eko 500 g", "leek", 500, "g"),
        ("peas", "Små Fina Ärter 250 g", "peas", 250, "g"),
        ("celery", "Bladselleri 400 g", "celery", 400, "g"),
    ],
)
def test_recipe_taxonomy_ids_match_verified_structured_food_identities(
    recipe_canonical: str,
    product_name: str,
    source_food: str,
    quantity: float,
    unit: str,
) -> None:
    ingredient = NormalizedIngredient(
        canonical_name=recipe_canonical,
        required_quantity=min(quantity, 100),
        unit=unit,
    )
    candidate = product(
        source_food,
        product_name,
        product_name,
        package_quantity=quantity,
        package_unit=unit,
        quantity_confidence=QuantityConfidence.EXACT,
    ).model_copy(update={"canonical_food": source_food})

    matches = ProductMatcher().match(ingredient, [candidate])

    assert [match.product_id for match in matches] == [source_food]


@pytest.mark.parametrize(
    ("recipe_canonical", "product_name", "source_food"),
    [
        ("milk", "Kokosmjölk 400 ml", "coconut_milk"),
        ("cream", "Crème Fraiche 500 g", "creme_fraiche"),
        ("eggs", "Äggnudlar 250 g", "nudlar"),
        ("pork_meat", "Fläskfärs 500 g", "pork_meat"),
        ("falukorv", "Grillkorv 500 g", "korv"),
        ("fish_meat", "Fiskpinnar 450 g", "fish_meat"),
        ("chickpeas", "Hummus Kikärtor 200 g", "chickpeas"),
        ("leek", "Purjolökssoppa 500 g", "leek"),
        ("peas", "Gula Ärter 500 g", "peas"),
        ("celery", "Rotselleri 500 g", "celery"),
    ],
)
def test_recipe_taxonomy_bridge_does_not_relax_product_identity(
    recipe_canonical: str,
    product_name: str,
    source_food: str,
) -> None:
    ingredient = NormalizedIngredient(
        canonical_name=recipe_canonical,
        required_quantity=100,
        unit="g",
    )
    confounder = product(
        "confounder",
        product_name,
        product_name,
        quantity_confidence=QuantityConfidence.EXACT,
    ).model_copy(update={"canonical_food": source_food})

    assert ProductMatcher().match(ingredient, [confounder]) == []


@pytest.mark.parametrize(
    ("ingredient_name", "wrong_name", "right_name"),
    [
        ("linser", "Ärter Gula 500 g", "Röda Linser 500 g"),
        (
            "crème fraiche",
            "Potatissallad Crème Fraiche 400 g",
            "Arla Crème Fraiche 34% 500 g",
        ),
        ("ost", "Grillost Original 200 g", "Garant Hushållsost 500 g"),
        ("ris", "Grötris 1 kg", "Garant Jasminris 1 kg"),
    ],
)
def test_search_query_metadata_cannot_override_product_identity(
    ingredient_name: str, wrong_name: str, right_name: str
) -> None:
    """Regression for broad Primat results tagged with the requested query."""

    ingredient = NormalizedIngredient(
        canonical_name=ingredient_name, required_quantity=400, unit="g"
    )
    products = [
        product("wrong", wrong_name, ingredient_name),
        # A provider which derives canonical metadata from the actual product
        # name must work too; notably, Hushållsost is a compound word.
        product(
            "right",
            right_name,
            right_name,
            category=("Torra baljväxter" if ingredient_name == "linser" else "test"),
        ),
    ]

    matches = ProductMatcher().match(ingredient, products)

    assert [match.product_id for match in matches] == ["right"]


def test_broad_lentil_category_cannot_turn_chickpeas_into_lentils() -> None:
    ingredient = NormalizedIngredient(canonical_name="linser", required_quantity=300, unit="g")
    products = [
        product(
            "chickpeas",
            "Kikärtor 380 g",
            "kikärtor",
            package_quantity=380,
            category="Baljväxter / Linser",
        ),
        product(
            "lentils",
            "Röda Linser 400 g",
            "linser",
            package_quantity=400,
            category="Torra baljväxter",
        ),
    ]

    matches = ProductMatcher().match(ingredient, products)

    assert [match.product_id for match in matches] == ["lentils"]


@pytest.mark.parametrize(
    ("ingredient_name", "product_name"),
    [
        ("linser", "Ekologisk Linssoppa 500 g"),
        ("crème fraiche", "Dipmix Crème Fraiche 24 g"),
        ("ost", "Potatisgratäng med ost 800 g"),
        ("ris", "Blomkålsris 500 g"),
        ("vitlök", "Krossade Tomater Vitlök 390 g"),
        ("vitlök", "Baguetter Vitlök 2-pack 350 g"),
        ("vitlök", "Vitlök & Örter 28% 200 g"),
    ],
)
def test_ingredient_term_used_in_a_dish_or_flavour_is_not_product_identity(
    ingredient_name: str, product_name: str
) -> None:
    ingredient = NormalizedIngredient(
        canonical_name=ingredient_name, required_quantity=200, unit="g"
    )

    matches = ProductMatcher().match(
        ingredient, [product("prepared", product_name, ingredient_name)]
    )

    assert matches == []


def test_pet_food_flavour_cannot_match_recipe_meat() -> None:
    ingredient = NormalizedIngredient(canonical_name="nötfärs", required_quantity=500, unit="g")
    products = [
        product(
            "dog-food",
            "Nötfärs Potatis Lingon Hundmat Våt 550 g",
            "nötfärs",
            package_quantity=550,
            category="Hundmat",
        ),
        product("beef", "Nötfärs 12% 500 g", "nötfärs"),
    ]

    matches = ProductMatcher().match(ingredient, products)

    assert [match.product_id for match in matches] == ["beef"]


def test_tortilla_pack_count_can_safely_override_weight_metadata() -> None:
    ingredient = NormalizedIngredient(canonical_name="tortillas", required_quantity=16, unit="st")
    products = [
        product(
            "tortillas",
            "Santa Maria Tortilla Original Medium 8-pack 320 g",
            "tortillas",
            package_quantity=320,
            package_unit="g",
        ),
        product(
            "chips",
            "Tortilla Chips 8-pack 320 g",
            "tortillas",
            package_quantity=320,
            package_unit="g",
        ),
        product(
            "no-count",
            "Tortilla Original 320 g",
            "tortillas",
            package_quantity=320,
            package_unit="g",
        ),
    ]

    matches = ProductMatcher().match(ingredient, products)

    assert [match.product_id for match in matches] == ["tortillas"]
    assert matches[0].package_quantity == 8
    assert matches[0].package_unit == "st"


def test_matcher_preserves_drained_usable_quantity_through_checkout() -> None:
    ingredient = NormalizedIngredient(canonical_name="kidneybönor", required_quantity=350, unit="g")
    canned = product(
        "beans",
        "Kidneybönor 380 g",
        "kidneybönor",
        package_quantity=380,
        usable_quantity=230,
        usable_unit="g",
        quantity_confidence=QuantityConfidence.EXACT,
    )

    candidate = ProductMatcher().match(ingredient, [canned])[0]
    item = BasketCalculator().calculate_item(ingredient, candidate)

    assert candidate.package_quantity == 380
    assert candidate.usable_quantity == 230
    assert candidate.quantity_confidence == QuantityConfidence.EXACT
    assert item.packages_needed == 2
