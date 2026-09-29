from __future__ import annotations

import pytest
from app.models.ingredient import NormalizedIngredient
from app.models.product import (
    Product,
    QuantityConfidence,
    SaleModel,
    SemanticConfidence,
)
from app.services.ingredient_normalizer import canonicalize_ingredient_name
from app.services.product_matcher import ProductMatcher
from app.services.product_semantics import evaluate_product_semantics, semantic_requirement


def _ingredient(name: str) -> NormalizedIngredient:
    return NormalizedIngredient(canonical_name=name, required_quantity=500, unit="g")


def test_salad_cheese_flavour_is_not_a_garlic_bulb():
    p = _product("synthetic", "Vitost Tärnad Vitlök & persilja", "vitlök",
                 category="Fetaost & Salladsost")
    assert not evaluate_product_semantics("vitlök", p).compatible


def _product(
    product_id: str,
    name: str,
    canonical_name: str,
    *,
    price: float = 50,
    category: str = "Mat",
) -> Product:
    return Product(
        product_id=product_id,
        name=name,
        canonical_name=canonical_name,
        category=category,
        store_id="store",
        store_name="Store",
        package_quantity=500,
        package_unit="g",
        price=price,
    )


def test_generic_chicken_means_meat_and_rejects_heart() -> None:
    ingredient = _ingredient("kyckling")
    products = [
        _product("heart", "Kycklinghjärta Fryst", "kyckling", price=25),
        _product("thigh", "Kycklinglårfilé", "kyckling", price=69),
        _product("breast", "Kycklingfilé", "kyckling", price=89),
    ]

    matches = ProductMatcher().match(ingredient, products)

    assert [match.product_id for match in matches] == ["thigh", "breast"]
    assert [match.product_role for match in matches] == ["thigh", "breast"]
    assert all(match.semantic_confidence == SemanticConfidence.HIGH for match in matches)
    assert all("visible_food:chicken" in match.semantic_evidence for match in matches)

    rejected = evaluate_product_semantics("kyckling", products[0])
    assert rejected.confidence == SemanticConfidence.REJECTED
    assert rejected.product_role == "heart"
    assert "excluded_role:heart" in rejected.evidence


def test_explicit_chicken_heart_matches_heart_but_not_ordinary_chicken() -> None:
    ingredient = _ingredient("chicken_heart")
    products = [
        _product("heart", "Kycklinghjärta Fryst", "kyckling"),
        _product("breast", "Kycklingfilé", "kyckling"),
    ]

    matches = ProductMatcher().match(ingredient, products)

    assert canonicalize_ingredient_name("chicken_heart") == "kycklinghjärta"
    assert [match.product_id for match in matches] == ["heart"]
    assert matches[0].canonical_name == "kycklinghjärta"
    assert matches[0].canonical_food == "chicken"
    assert matches[0].product_role == "heart"
    assert matches[0].semantic_confidence == SemanticConfidence.HIGH


def test_a_cheaper_organ_product_cannot_win_generic_chicken_matching() -> None:
    matches = ProductMatcher().match(
        _ingredient("kyckling"),
        [
            _product("heart", "Kycklinghjärta Fryst", "kyckling", price=1),
            _product("thigh", "Kycklinglårfilé", "kyckling", price=200),
        ],
    )

    assert [match.product_id for match in matches] == ["thigh"]


@pytest.mark.parametrize(
    ("ingredient", "name", "source_food", "expected_food", "expected_role"),
    [
        (
            "kyckling",
            "Kycklingbröst Filé Import",
            "chicken_meat",
            "chicken",
            "breast",
        ),
        ("nötfärs", "Nötfärs 12%", "minced_beef", "meat_mince", "beef_mince"),
    ],
)
def test_exact_meat_identity_outranks_broad_charcuterie_ancestor_category(
    ingredient: str,
    name: str,
    source_food: str,
    expected_food: str,
    expected_role: str,
) -> None:
    product = _product(
        "meat",
        name,
        ingredient,
        category="Kött, chark & fågel",
    ).model_copy(update={"canonical_food": source_food})

    decision = evaluate_product_semantics(ingredient, product)
    matches = ProductMatcher().match(_ingredient(ingredient), [product])

    assert decision.compatible is True
    assert decision.canonical_food == expected_food
    assert decision.product_role == expected_role
    assert "primary_product_identity:charcuterie" not in decision.evidence
    assert [match.product_id for match in matches] == ["meat"]


@pytest.mark.parametrize(
    ("name", "category"),
    [
        ("Adult Kyckling-potatis Torrfoder Hund", "Mat"),
        ("Adult Kyckling-potatis Våtfoder Hund", "Mat"),
        ("Chicken Heart Kycklinghjärta Naturals Hundgodis", "Mat"),
        ("Kycklingfilé 500 g", "Djur > Hund > Foder"),
        ("Chicken Breast Dog Treats", "Pet food"),
    ],
)
def test_generic_chicken_rejects_visible_pet_food_even_with_chicken_metadata(
    name: str,
    category: str,
) -> None:
    pet_food = _product("pet", name, "kyckling", category=category, price=1).model_copy(
        update={
            "canonical_food": "chicken",
            "product_role": "generic_meat",
            "semantic_confidence": SemanticConfidence.HIGH,
        }
    )
    chicken = _product("human", "Kycklingfilé", "kyckling", price=100)

    rejected = evaluate_product_semantics("kyckling", pet_food)
    matches = ProductMatcher().match(_ingredient("kyckling"), [pet_food, chicken])

    assert rejected.compatible is False
    assert rejected.confidence == SemanticConfidence.REJECTED
    assert rejected.evidence == ["excluded_audience:non_human_food"]
    assert [match.product_id for match in matches] == ["human"]


def test_hot_dog_is_not_misclassified_as_pet_food() -> None:
    hot_dog = _product("hot-dog", "Chicken hotdog", "korv", category="Chark > Korv")

    decision = evaluate_product_semantics("korv", hot_dog)

    assert decision.compatible is True
    assert decision.confidence == SemanticConfidence.HIGH
    assert decision.canonical_food == "korv"


def test_teriyaki_chicken_skewer_cannot_beat_raw_chicken_cuts() -> None:
    ingredient = _ingredient("kyckling")
    skewer = _product(
        "skewer",
        "Kycklingspett Teriyaki",
        "kyckling",
        category="Fryst > Kött och kyckling > Kyckling och övrig fågel",
        price=1,
    )
    thigh = _product("thigh", "Kycklinglårfilé", "kyckling", price=69)
    fillet = _product("fillet", "Kycklingfilé", "kyckling", price=89)

    rejected = evaluate_product_semantics("kyckling", skewer)
    raw_decisions = [evaluate_product_semantics("kyckling", product) for product in (thigh, fillet)]
    matches = ProductMatcher().match(ingredient, [skewer, thigh, fillet])

    assert rejected.compatible is False
    assert rejected.confidence == SemanticConfidence.REJECTED
    assert rejected.canonical_food == "chicken"
    assert rejected.product_role == "prepared_skewer"
    assert rejected.product_form == "skewer"
    assert "visible_prepared_form:skewer" in rejected.evidence
    assert any(reason.startswith("role_mismatch:") for reason in rejected.evidence)
    assert all(decision.compatible is True for decision in raw_decisions)
    assert all(decision.confidence == SemanticConfidence.HIGH for decision in raw_decisions)
    assert [match.product_id for match in matches] == ["thigh", "fillet"]


@pytest.mark.parametrize(
    ("product_name", "expected_form", "expected_role"),
    [
        ("Kycklingfilé Marinerad", "marinated", "marinated_product"),
        ("Kycklingfilé Tandoori", "seasoned", "seasoned_product"),
        ("Chicken Breast BBQ", "seasoned", "seasoned_product"),
    ],
)
def test_marinated_or_seasoned_chicken_is_not_unqualified_raw_chicken(
    product_name: str,
    expected_form: str,
    expected_role: str,
) -> None:
    product = _product("processed", product_name, "kyckling")

    decision = evaluate_product_semantics("kyckling", product)

    assert decision.compatible is False
    assert decision.confidence == SemanticConfidence.REJECTED
    assert decision.product_form == expected_form
    assert decision.product_role == expected_role
    assert f"visible_prepared_form:{expected_form}" in decision.evidence
    assert any(reason.startswith("role_mismatch:") for reason in decision.evidence)


def test_gyros_and_chicken_sticks_cannot_beat_raw_chicken_cuts() -> None:
    ingredient = _ingredient("kyckling")
    traps = [
        _product("gyros", "Kycklinggyros Fryst", "kyckling", price=1),
        _product("sticks", "Kycklingpinnar", "kyckling", price=2),
    ]
    thigh = _product("thigh", "Kycklinglårfilé", "kyckling", price=69)
    fillet = _product("fillet", "Kycklingfilé", "kyckling", price=89)

    rejected = [evaluate_product_semantics("kyckling", product) for product in traps]
    matches = ProductMatcher().match(ingredient, [*traps, thigh, fillet])

    assert [(decision.product_role, decision.product_form) for decision in rejected] == [
        ("processed_kebab", "gyros"),
        ("processed_stick", "processed_stick"),
    ]
    assert all(decision.confidence == SemanticConfidence.REJECTED for decision in rejected)
    assert [match.product_id for match in matches] == ["thigh", "fillet"]


@pytest.mark.parametrize(
    ("canonical", "product_name", "role"),
    [
        ("kycklinggyros", "Kycklinggyros Fryst", "processed_kebab"),
        ("kycklingpinnar", "Kycklingpinnar", "processed_stick"),
    ],
)
def test_explicit_processed_chicken_canonical_remains_matchable(
    canonical: str,
    product_name: str,
    role: str,
) -> None:
    product = _product("explicit", product_name, canonical)

    decision = evaluate_product_semantics(canonical, product)

    assert decision.compatible is True
    assert decision.confidence == SemanticConfidence.HIGH
    assert decision.canonical_food == "chicken"
    assert decision.product_role == role
    assert [
        match.product_id for match in ProductMatcher().match(_ingredient(canonical), [product])
    ] == ["explicit"]


@pytest.mark.parametrize("broth_name", ["Ramenbuljong Kyckling", "Buljong Kyckling"])
def test_reversed_chicken_broth_names_cannot_match_generic_chicken(
    broth_name: str,
) -> None:
    broth = _product("broth", broth_name, "kyckling", price=1)
    thigh = _product("thigh", "Kycklinglårfilé", "kyckling", price=200)

    rejected = evaluate_product_semantics("kyckling", broth)
    matches = ProductMatcher().match(_ingredient("kyckling"), [broth, thigh])

    assert rejected.compatible is False
    assert rejected.confidence == SemanticConfidence.REJECTED
    assert rejected.canonical_food == "broth"
    assert rejected.product_role == "broth"
    assert rejected.product_form == "liquid"
    assert [match.product_id for match in matches] == ["thigh"]


@pytest.mark.parametrize(
    "broth_name",
    ["Kycklingbuljong", "Ramenbuljong Kyckling", "Buljong Kyckling"],
)
def test_explicit_broth_canonical_accepts_chicken_broth_in_any_word_order(
    broth_name: str,
) -> None:
    broth = _product("broth", broth_name, "buljong")

    decision = evaluate_product_semantics("buljong", broth)
    matches = ProductMatcher().match(_ingredient("buljong"), [broth])

    assert canonicalize_ingredient_name("kycklingbuljong") == "buljong"
    assert decision.compatible is True
    assert decision.confidence == SemanticConfidence.HIGH
    assert decision.canonical_food == "broth"
    assert decision.product_role == "broth"
    assert decision.product_form == "liquid"
    assert [match.product_id for match in matches] == ["broth"]


@pytest.mark.parametrize(
    ("product_name", "rejected_role"),
    [
        ("Kyckling hjärta Fryst", "heart"),
        ("Kyckling lever Fryst", "liver"),
        ("Kycklingkrås Fryst", "gizzard"),
        ("Kycklinginälvor Fryst", "organ_mix"),
        ("Kyckling buljong", "broth"),
        ("Kyckling skinn", "skin_only"),
        ("Kycklingkorv", "processed_sausage"),
        ("Kycklingkebab", "processed_kebab"),
        ("Kycklingburgare", "processed_burger"),
        ("Kycklingfärs", "minced_meat"),
    ],
)
def test_generic_chicken_rejects_organs_and_processed_roles(
    product_name: str,
    rejected_role: str,
) -> None:
    wrong = _product("wrong", product_name, "kyckling", price=1)

    decision = evaluate_product_semantics("kyckling", wrong)

    assert decision.compatible is False
    assert decision.confidence == SemanticConfidence.REJECTED
    assert decision.product_role == rejected_role
    assert ProductMatcher().match(_ingredient("kyckling"), [wrong]) == []


def test_explicit_spaced_chicken_heart_remains_valid() -> None:
    matches = ProductMatcher().match(
        _ingredient("kyckling hjärta"),
        [
            _product("heart", "Kyckling hjärta Fryst", "kycklinghjärta"),
            _product("breast", "Kycklingfilé", "kyckling"),
        ],
    )

    assert [match.product_id for match in matches] == ["heart"]
    assert matches[0].product_role == "heart"
    assert matches[0].semantic_confidence == SemanticConfidence.HIGH


@pytest.mark.parametrize(
    ("canonical", "product_name", "expected_role"),
    [
        ("kycklingkrås", "Kycklingkrås Fryst", "gizzard"),
        ("kycklinginälvor", "Kycklinginälvor Fryst", "organ_mix"),
    ],
)
def test_explicit_chicken_offal_canonical_remains_matchable(
    canonical: str,
    product_name: str,
    expected_role: str,
) -> None:
    product = _product("offal", product_name, canonical)

    matches = ProductMatcher().match(_ingredient(canonical), [product])

    assert canonicalize_ingredient_name(canonical) == canonical
    assert [match.product_id for match in matches] == ["offal"]
    assert matches[0].product_role == expected_role
    assert matches[0].semantic_confidence == SemanticConfidence.HIGH


@pytest.mark.parametrize(
    "wrong_name",
    ["Kycklinglårfilé", "Kycklingvingar", "Hel kyckling", "Kyckling färsk"],
)
def test_chicken_breast_requirement_is_stricter_than_generic_chicken(
    wrong_name: str,
) -> None:
    ingredient = _ingredient("chicken_breast")
    breast = _product("breast", "Kycklingfilé", "kyckling")
    wrong = _product("wrong", wrong_name, "kyckling", price=1)

    matches = ProductMatcher().match(ingredient, [wrong, breast])
    rejected = evaluate_product_semantics("chicken_breast", wrong)

    assert canonicalize_ingredient_name("chicken_breast") == "chicken_breast"
    assert canonicalize_ingredient_name("kycklingfilé") == "kyckling"
    assert [match.product_id for match in matches] == ["breast"]
    assert matches[0].product_role == "breast"
    assert rejected.confidence == SemanticConfidence.REJECTED


@pytest.mark.parametrize(
    ("ingredient", "wrong", "right", "rejected_role"),
    [
        ("vitlök", "Baguetter Vitlök 2-pack", "Vitlök", "bread"),
        ("vitlök", "Vitlöksbaguette 2-pack", "Vitlök", "bread"),
        ("ris", "Grötris 1 kg", "Jasminris 1 kg", "pudding_rice"),
        ("ost", "Grillost Original", "Hushållsost Mild", "grilling_cheese"),
        ("ost", "Ostsås Cheddar", "Gouda", "cheese_sauce"),
        ("ost", "Ostbågar", "Cheddar", "cheese_flavoured_snack"),
    ],
)
def test_product_roles_block_known_semantic_traps(
    ingredient: str,
    wrong: str,
    right: str,
    rejected_role: str,
) -> None:
    wrong_product = _product("wrong", wrong, ingredient, price=1)
    right_product = _product("right", right, right, price=100)

    matches = ProductMatcher().match(_ingredient(ingredient), [wrong_product, right_product])
    rejected = evaluate_product_semantics(ingredient, wrong_product)

    assert [match.product_id for match in matches] == ["right"]
    assert rejected.confidence == SemanticConfidence.REJECTED
    assert rejected.product_role == rejected_role


@pytest.mark.parametrize(
    ("ingredient", "wrong", "right", "rejected_role"),
    [
        ("ost", "Grill ost Original", "Hushållsost Mild", "grilling_cheese"),
        ("ost", "Ost sås Cheddar", "Gouda", "cheese_sauce"),
        ("ris", "Ris gryn 1 kg", "Jasminris 1 kg", "pudding_rice"),
        ("ris", "Ris pudding 1 kg", "Basmatiris 1 kg", "pudding_rice"),
        ("ris", "Pudding rice 1 kg", "Jasminris 1 kg", "pudding_rice"),
    ],
)
def test_spaced_semantic_forms_are_classified_before_price(
    ingredient: str,
    wrong: str,
    right: str,
    rejected_role: str,
) -> None:
    wrong_product = _product("wrong", wrong, ingredient, price=1)
    right_product = _product("right", right, ingredient, price=100)

    matches = ProductMatcher().match(_ingredient(ingredient), [wrong_product, right_product])
    rejected = evaluate_product_semantics(ingredient, wrong_product)

    assert [match.product_id for match in matches] == ["right"]
    assert rejected.confidence == SemanticConfidence.REJECTED
    assert rejected.product_role == rejected_role


@pytest.mark.parametrize(
    ("ingredient", "wrong", "right", "rejected_role"),
    [
        ("fisk", "Fiskbullar i dillsås", "Fiskfilé", "fish_balls"),
        ("fisk", "Fiskburgare", "Fiskfilé", "fish_burger"),
        ("fisk", "Fiskkakor", "Fiskfilé", "fish_cakes"),
        ("köttfärs", "Köttfärssås", "Köttfärs500g", "processed_ready_meal"),
        ("köttfärs", "Köttfärspaj", "Köttfärs500g", "processed_ready_meal"),
        (
            "köttfärs",
            "Köttfärslasagne",
            "Köttfärs500g",
            "processed_ready_meal",
        ),
    ],
)
def test_fish_and_mince_prepared_products_are_not_raw_ingredients(
    ingredient: str,
    wrong: str,
    right: str,
    rejected_role: str,
) -> None:
    wrong_product = _product("wrong", wrong, ingredient, price=1)
    right_product = _product("right", right, ingredient, price=100)

    matches = ProductMatcher().match(_ingredient(ingredient), [wrong_product, right_product])
    rejected = evaluate_product_semantics(ingredient, wrong_product)

    assert [match.product_id for match in matches] == ["right"]
    assert rejected.confidence == SemanticConfidence.REJECTED
    assert rejected.product_role == rejected_role


@pytest.mark.parametrize(
    ("ingredient", "prepared", "raw"),
    [
        ("nötfärs", "Nötfärssås", "Nötfärs 12% 500 g"),
        ("nötfärs", "Nötfärspaj", "Nötfärs 12% 500 g"),
        ("blandfärs", "Blandfärslimpa", "Blandfärs 500 g"),
        ("lax", "Laxburgare", "Laxfilé 500 g"),
        ("lax", "Laxpudding", "Laxfilé 500 g"),
        ("lax", "Laxpaj", "Laxfilé 500 g"),
        ("fläskkött", "Fläskköttbullar", "Fläskytterfilé 500 g"),
        ("fläskkött", "Fläskkött korv", "Fläskytterfilé 500 g"),
        ("ost", "Ost & skinkpaj", "Hushållsost 500 g"),
        ("ost", "Ost paj", "Hushållsost 500 g"),
        ("ost", "Ost gratäng", "Hushållsost 500 g"),
        ("pasta", "Pasta Bolognese färdigrätt", "Penne pasta 500 g"),
        ("pasta", "Pastasallad", "Penne pasta 500 g"),
        ("pasta", "Pasta sallad", "Penne pasta 500 g"),
        ("paprika", "Paprikapulver", "Paprika Röd"),
        ("paprika", "Paprika pulver", "Paprika Röd"),
        ("broccoli", "Broccolisoppa", "Broccoli Fryst"),
        ("broccoli", "Broccoli soppa", "Broccoli Fryst"),
        ("morot", "Morotssoppa", "Morötter 1 kg"),
        ("morot", "Morot soppa", "Morötter 1 kg"),
        ("kidneybönor", "Kidneybönburgare", "Kidneybönor Naturella"),
        ("svarta bönor", "Svartbönburgare", "Svarta Bönor Naturella"),
        ("nudlar", "Nudelsoppa", "Äggnudlar 250 g"),
        ("couscous", "Couscoussallad", "Couscous 500 g"),
    ],
)
def test_raw_recipe_ingredients_reject_central_prepared_forms(
    ingredient: str,
    prepared: str,
    raw: str,
) -> None:
    cheap_prepared = _product("prepared", prepared, ingredient, price=1)
    expensive_raw = _product("raw", raw, ingredient, price=100)

    matches = ProductMatcher().match(
        _ingredient(ingredient),
        [cheap_prepared, expensive_raw],
    )
    rejected = evaluate_product_semantics(ingredient, cheap_prepared)

    assert [match.product_id for match in matches] == ["raw"]
    assert rejected.confidence == SemanticConfidence.REJECTED
    assert rejected.product_form in {
        "burger",
        "loaf",
        "meatballs",
        "pie",
        "powder",
        "ready_meal",
        "salad",
        "sauce",
        "sausage",
        "soup",
        "pudding",
    }


def test_plain_canned_beans_are_not_mistaken_for_a_prepared_dish() -> None:
    canned = _product(
        "beans",
        "Kidneybönor Naturella i lake 380 g",
        "kidneybönor",
    )

    matches = ProductMatcher().match(_ingredient("kidneybönor"), [canned])

    assert [match.product_id for match in matches] == ["beans"]
    assert matches[0].semantic_confidence == SemanticConfidence.HIGH


@pytest.mark.parametrize(
    ("ingredient", "processed_name", "raw_name", "processed_role", "processed_form"),
    [
        (
            "morot",
            "Surkål Med Morötter",
            "Morötter 1 kg",
            "fermented_vegetable_mixture",
            "fermented",
        ),
        (
            "morot",
            "Inlagda Morötter",
            "Morötter 1 kg",
            "pickled_vegetable_mixture",
            "pickled",
        ),
        ("vitlök", "Salsa Vitlök Medium", "Vitlök", "condiment", "condiment"),
    ],
)
def test_raw_carrot_and_garlic_reject_processed_mixtures_before_price(
    ingredient: str,
    processed_name: str,
    raw_name: str,
    processed_role: str,
    processed_form: str,
) -> None:
    cheap_processed = _product("processed", processed_name, ingredient, price=1)
    raw = _product("raw", raw_name, ingredient, price=100)

    rejected = evaluate_product_semantics(ingredient, cheap_processed)
    matches = ProductMatcher().match(_ingredient(ingredient), [cheap_processed, raw])

    assert rejected.compatible is False
    assert rejected.confidence == SemanticConfidence.REJECTED
    assert rejected.product_role == processed_role
    assert rejected.product_form == processed_form
    assert f"visible_prepared_form:{processed_form}" in rejected.evidence
    assert [match.product_id for match in matches] == ["raw"]
    assert matches[0].product_name == raw_name
    if ingredient == "morot":
        assert matches[0].product_role == "whole_vegetable"
        assert matches[0].product_form == "fresh"
    else:
        assert matches[0].product_role == "bulb"
        assert matches[0].product_form == "fresh"


@pytest.mark.parametrize(
    ("supplement_name", "category"),
    [
        ("Vitlökstabletter 120 st", "Kosttillskott"),
        ("Vitlökskapslar 90 st", "Vitaminer och mineraler"),
        ("Vitlök Kapslar Kosttillskott 100 g", "Mat"),
    ],
)
def test_garlic_supplements_cannot_match_raw_garlic(
    supplement_name: str,
    category: str,
) -> None:
    supplement = _product(
        "supplement",
        supplement_name,
        "vitlök",
        category=category,
        price=1,
    )
    raw = _product("raw", "Vitlök Kapsel Klass 1", "vitlök", price=100)

    rejected = evaluate_product_semantics("vitlök", supplement)
    matches = ProductMatcher().match(_ingredient("vitlök"), [supplement, raw])

    assert rejected.compatible is False
    assert rejected.canonical_food == "supplement"
    assert rejected.product_role == "supplement"
    assert [match.product_id for match in matches] == ["raw"]
    assert matches[0].product_role == "bulb"


def test_explicit_condiment_canonical_is_not_rejected_as_raw_garlic() -> None:
    salsa = _product("salsa", "Salsa Vitlök Medium", "salsa")

    decision = evaluate_product_semantics("salsa", salsa)

    assert decision.compatible is True
    assert decision.confidence == SemanticConfidence.HIGH


def test_generic_fish_rejects_canned_tuna_before_price() -> None:
    canned = _product(
        "canned",
        "Tonfisk i solrosolja 3-pack",
        "fisk",
        price=1,
    )
    raw = _product("raw", "Fiskfilé", "fisk", price=100)

    rejected = evaluate_product_semantics("fisk", canned)
    matches = ProductMatcher().match(_ingredient("fisk"), [canned, raw])

    assert rejected.compatible is False
    assert rejected.confidence == SemanticConfidence.REJECTED
    assert rejected.product_role == "canned_tuna"
    assert rejected.product_form == "preserved_in_oil"
    assert [match.product_id for match in matches] == ["raw"]
    assert matches[0].product_role == "generic_fish"
    assert matches[0].product_form == "meat"


def test_explicit_tuna_requirement_can_match_canned_tuna() -> None:
    canned = _product(
        "canned",
        "Tonfisk i solrosolja 3-pack",
        "tonfisk",
    )

    matches = ProductMatcher().match(_ingredient("tonfisk"), [canned])

    assert [match.product_id for match in matches] == ["canned"]
    assert matches[0].product_role == "canned_tuna"
    assert matches[0].product_form == "preserved_in_oil"
    assert matches[0].semantic_confidence == SemanticConfidence.HIGH


def test_raw_broccoli_rejects_ambiguous_mix_before_price() -> None:
    mixture = _product("mix", "Broccoli Mix", "broccoli", price=1)
    raw = _product("raw", "Broccoli Fryst", "broccoli", price=100)

    rejected = evaluate_product_semantics("broccoli", mixture)
    matches = ProductMatcher().match(_ingredient("broccoli"), [mixture, raw])

    assert rejected.compatible is False
    assert rejected.confidence == SemanticConfidence.REJECTED
    assert rejected.canonical_food == "vegetable_mixture"
    assert rejected.product_role == "ambiguous_mixture"
    assert rejected.product_form == "mixture"
    assert [match.product_id for match in matches] == ["raw"]
    assert matches[0].product_name == "Broccoli Fryst"
    assert matches[0].product_role == "whole_vegetable"
    assert matches[0].product_form == "frozen"


def test_explicit_vegetable_mixture_can_match_broccoli_mix() -> None:
    mixture = _product(
        "mix",
        "Broccoli Mix",
        "frysta grönsaker",
    )

    matches = ProductMatcher().match(_ingredient("frysta grönsaker"), [mixture])

    assert [match.product_id for match in matches] == ["mix"]
    assert matches[0].canonical_food == "vegetable_mixture"
    assert matches[0].product_role == "vegetable_mixture"
    assert matches[0].product_form == "mixture"


@pytest.mark.parametrize(
    ("olive_name", "olive_role", "olive_form"),
    [
        ("Snacksoliver Vitlök Fyllda", "stuffed_olive", "stuffed"),
        ("Oliver med vitlök", "preserved_olive", "preserved"),
        ("Vitlöksmarinerade oliver", "marinated_olive", "marinated"),
    ],
)
def test_generic_garlic_rejects_olive_products_before_price(
    olive_name: str,
    olive_role: str,
    olive_form: str,
) -> None:
    olive = _product("olive", olive_name, "vitlök", price=1)
    garlic = _product("garlic", "Vitlök", "vitlök", price=100)

    rejected = evaluate_product_semantics("vitlök", olive)
    matches = ProductMatcher().match(_ingredient("vitlök"), [olive, garlic])

    assert rejected.compatible is False
    assert rejected.confidence == SemanticConfidence.REJECTED
    assert rejected.canonical_food == "olive"
    assert rejected.product_role == olive_role
    assert rejected.product_form == olive_form
    assert [match.product_id for match in matches] == ["garlic"]
    assert matches[0].product_role == "bulb"
    assert matches[0].product_form == "fresh"


def test_explicit_olive_canonical_remains_valid() -> None:
    olive = _product("olive", "Snacksoliver Vitlök Fyllda", "oliver")

    matches = ProductMatcher().match(_ingredient("oliver"), [olive])

    assert [match.product_id for match in matches] == ["olive"]
    assert matches[0].canonical_food == "olive"
    assert matches[0].product_role == "stuffed_olive"
    assert matches[0].product_form == "stuffed"


def test_ambiguous_lentil_name_does_not_claim_dry_form() -> None:
    ambiguous = _product(
        "ambiguous",
        "Röda linser Eko 380 g",
        "linser",
        category="Skafferi > Bönor och linser",
    )

    decision = evaluate_product_semantics("linser", ambiguous)

    assert decision.compatible is False
    assert decision.confidence == SemanticConfidence.REJECTED
    assert decision.product_role == "unknown_lentil_form"
    assert decision.product_form == "unknown"
    assert ProductMatcher().match(_ingredient("linser"), [ambiguous]) == []


def test_explicit_dry_lentil_category_is_valid_for_generic_recipe_lentils() -> None:
    dry = _product(
        "dry",
        "Röda linser Eko 500 g",
        "linser",
        category="Skafferi > Torra baljväxter",
    )

    matches = ProductMatcher().match(_ingredient("linser"), [dry])

    assert [match.product_id for match in matches] == ["dry"]
    assert matches[0].product_role == "dry_staple"
    assert matches[0].product_form == "dry"


def test_source_explicit_red_lentils_with_fixed_gram_package_default_to_dry() -> None:
    product = _product(
        "red-lentils",
        "Linser Röda 400 g",
        "linser",
        category="Skafferi > Bönor och linser",
    ).model_copy(
        update={
            "canonical_food": "red_lentils",
            "sale_model": SaleModel.FIXED_PACKAGE,
            "quantity_confidence": QuantityConfidence.EXACT,
        }
    )

    decision = evaluate_product_semantics("red_lentils", product)
    matches = ProductMatcher().match(_ingredient("red_lentils"), [product])

    assert decision.compatible is True
    assert decision.canonical_food == "lentil"
    assert decision.product_role == "dry_staple"
    assert decision.product_form == "dry"
    assert "structured_red_lentils_dry_package" in decision.evidence
    assert [match.product_id for match in matches] == ["red-lentils"]


def test_exact_red_lentil_requirement_rejects_green_legacy_lentil_row() -> None:
    green = _product(
        "green-lentils",
        "Gröna Linser 400 g",
        "linser",
        category="Skafferi > Torra baljväxter",
    ).model_copy(
        update={
            "canonical_food": "lentil",
            "sale_model": SaleModel.FIXED_PACKAGE,
            "quantity_confidence": QuantityConfidence.EXACT,
        }
    )

    decision = evaluate_product_semantics("red_lentils", green)
    matches = ProductMatcher().match(_ingredient("red_lentils"), [green])

    assert decision.compatible is False
    assert decision.confidence == SemanticConfidence.REJECTED
    assert "variant_mismatch:requires_red_lentils" in decision.evidence
    assert matches == []


def test_generic_lentil_requirement_still_accepts_green_dry_lentils() -> None:
    green = _product(
        "green-lentils",
        "Gröna Linser 400 g",
        "linser",
        category="Skafferi > Torra baljväxter",
    )

    matches = ProductMatcher().match(_ingredient("linser"), [green])

    assert [match.product_id for match in matches] == ["green-lentils"]


@pytest.mark.parametrize(
    ("name", "category", "expected_role"),
    [
        (
            "Röda Linser Färdigkokta Tetra 380 g",
            "Konserver > Bönor och linser",
            "canned_staple",
        ),
        ("Linssoppa Röda Linser 400 g", "Färdigmat", "processed_ready_meal"),
    ],
)
def test_source_explicit_red_lentils_never_override_preserved_or_prepared_signals(
    name: str,
    category: str,
    expected_role: str,
) -> None:
    product = _product("prepared", name, "linser", category=category).model_copy(
        update={
            "canonical_food": "red_lentils",
            "sale_model": SaleModel.FIXED_PACKAGE,
            "quantity_confidence": QuantityConfidence.EXACT,
        }
    )

    decision = evaluate_product_semantics("red_lentils", product)

    assert decision.compatible is False
    assert decision.confidence == SemanticConfidence.REJECTED
    assert decision.product_role == expected_role
    assert "structured_red_lentils_dry_package" not in decision.evidence


def test_source_explicit_red_lentils_need_compatible_package_evidence() -> None:
    product = Product(
        product_id="red-lentils-unknown-package",
        name="Linser Röda",
        canonical_name="linser",
        canonical_food="red_lentils",
        category="Skafferi > Bönor och linser",
        store_id="store",
        store_name="Store",
        price=50,
        quantity_confidence=QuantityConfidence.UNKNOWN,
    )

    decision = evaluate_product_semantics("red_lentils", product)

    assert decision.compatible is False
    assert decision.product_role == "unknown_lentil_form"
    assert decision.product_form == "unknown"
    assert "structured_red_lentils_dry_package" not in decision.evidence


@pytest.mark.parametrize(
    ("ingredient", "name", "category", "role", "form"),
    [
        (
            "kokta linser",
            "Färdigkokta Röda Linser Tetra 380 g",
            "Konserver > Bönor och linser",
            "canned_staple",
            "canned",
        ),
        (
            "torra linser",
            "Torkade Röda Linser 500 g",
            "Torra baljväxter",
            "dry_staple",
            "dry",
        ),
    ],
)
def test_explicit_lentil_form_canonicals_remain_valid(
    ingredient: str,
    name: str,
    category: str,
    role: str,
    form: str,
) -> None:
    product = _product("lentils", name, ingredient, category=category)

    matches = ProductMatcher().match(_ingredient(ingredient), [product])

    assert [match.product_id for match in matches] == ["lentils"]
    assert matches[0].product_role == role
    assert matches[0].product_form == form


def test_generic_dry_lentil_requirement_rejects_explicit_cooked_product() -> None:
    cooked = _product(
        "cooked",
        "Färdigkokta Röda Linser Tetra 380 g",
        "kokta linser",
        category="Konserver > Bönor och linser",
        price=1,
    )
    dry = _product(
        "dry",
        "Torkade Röda Linser 500 g",
        "linser",
        category="Torra baljväxter",
        price=100,
    )

    matches = ProductMatcher().match(_ingredient("linser"), [cooked, dry])

    assert [match.product_id for match in matches] == ["dry"]


@pytest.mark.parametrize(
    ("ingredient", "secondary_product", "primary_product"),
    [
        ("kyckling", "Pizza med kyckling", "Kycklingfilé"),
        ("lax", "Sushi med lax", "Laxfilé"),
        ("fisk", "Wrap med torsk", "Fiskfilé"),
        ("paprika", "Hummus med paprika", "Paprika Röd"),
        ("morot", "Hummus med morot", "Morötter"),
        ("tomat", "Hummus med tomat", "Tomater"),
        ("ris", "Chips med ris", "Jasminris"),
        ("potatis", "Chips med potatis", "Potatis"),
        ("gul lök", "Chips med lök", "Gul lök"),
        ("majs", "Chips med majs", "Majs"),
        ("ost", "Pesto med parmesan", "Hushållsost"),
        ("smör", "Kex bakat med smör", "Smör"),
        ("tofu", "Wok med tofu", "Tofu Naturell"),
        ("nudlar", "Wok med nudlar", "Äggnudlar"),
        ("couscous", "Tabbouleh med couscous", "Couscous"),
        ("kidneybönor", "Pasta med kidneybönor", "Kidneybönor Naturella"),
        ("svarta bönor", "Chips med svarta bönor", "Svarta bönor Naturella"),
        ("bönor", "Chili med vita bönor", "Vita bönor Naturella"),
    ],
)
def test_raw_ingredient_must_be_primary_not_only_a_secondary_component(
    ingredient: str,
    secondary_product: str,
    primary_product: str,
) -> None:
    secondary = _product("secondary", secondary_product, ingredient, price=1)
    primary = _product("primary", primary_product, ingredient, price=100)

    rejected = evaluate_product_semantics(ingredient, secondary)
    matches = ProductMatcher().match(_ingredient(ingredient), [secondary, primary])

    assert rejected.compatible is False
    assert rejected.confidence == SemanticConfidence.REJECTED
    assert rejected.product_role == "secondary_component"
    assert rejected.product_form == "secondary_component"
    assert rejected.evidence == ["secondary_component_after_cue"]
    assert [match.product_id for match in matches] == ["primary"]


def test_primary_food_before_component_cue_remains_valid() -> None:
    chicken = _product(
        "chicken",
        "Kycklingfilé med citron",
        "kyckling",
    )

    matches = ProductMatcher().match(_ingredient("kyckling"), [chicken])

    assert [match.product_id for match in matches] == ["chicken"]
    assert matches[0].product_role == "breast"
    assert matches[0].product_form == "fillet"


@pytest.mark.parametrize(
    ("ingredient", "product_name", "category", "primary_food"),
    [
        ("vitlök", "Tomater Krossade Vitlök", "Grönsakskonserver", "krossade_tomater"),
        ("vitlök", "Bratwurst Kummin & vitlök", "Korv", "korv"),
        ("vitlök", "Cambozola Vitlök", "Mejeri > Ost", "cheese"),
        ("vitlök", "Gnocchi Vitlök&mozzarella", "Färsk pasta", "gnocchi"),
        ("vitlök", "Labneh Vitlök&mynta", "Mejeri", "labneh"),
        ("vitlök", "Risotto Svamp & vitlök", "Färdigrätter", "risotto"),
        ("kyckling", "Kyckling Couscous Från 8 månader", "Barnmat", "baby_food"),
        ("kyckling", "Couscous Kyckling & Grönsaker", "Färdigrätter", "couscous"),
        ("kyckling", "Ginger Chicken Cup Noodles", "Snabbmat", "nudlar"),
        ("kyckling", "Koppnudlar Kyckling", "Snabbmat", "nudlar"),
        ("kyckling", "Chicken Flavor Bouillon", "Buljong", "broth"),
        ("kyckling", "Noodles Chicken Teriyaki", "Snabbmat", "nudlar"),
        (
            "ägg",
            "Kaviar ägg randig",
            "Fisk & Skaldjur > Kaviar & Rom > Kaviar",
            "fish_roe",
        ),
        ("ost", "Jalapeno & Cheddar Majskakor", "Snacks", "grain_snack"),
        ("ost", "Majskakor Ost", "Snacks", "grain_snack"),
        ("ost", "Riskakor Ost", "Snacks", "grain_snack"),
        ("ost", "Parmesan Lätt Crème Fraiche", "Mejeri", "creme_fraiche"),
        ("ris", "Majs/ris Glutenfri Couscous", "Skafferi", "couscous"),
    ],
)
def test_raw_ingredient_rejects_a_different_primary_product_identity(
    ingredient: str,
    product_name: str,
    category: str,
    primary_food: str,
) -> None:
    product = _product("wrong", product_name, ingredient, category=category, price=1)

    rejected = evaluate_product_semantics(ingredient, product)

    assert rejected.compatible is False
    assert rejected.confidence == SemanticConfidence.REJECTED
    assert rejected.canonical_food == primary_food
    assert f"primary_product_identity:{primary_food}" in rejected.evidence or (
        primary_food == "broth" and "visible_food:broth" in rejected.evidence
    )
    assert ProductMatcher().match(_ingredient(ingredient), [product]) == []


@pytest.mark.parametrize(
    ("ingredient", "product_name", "category", "primary_food", "primary_role"),
    [
        ("vitlök", "Vitlökssalami", "Chark > Salami", "korv", "processed_sausage"),
        ("vitlök", "Färskost Vitlök", "Mejeri > Färskost", "cheese", "cream_cheese"),
        (
            "vitlök",
            "Vitlöksmajonnäs",
            "Såser > Majonnäs",
            "mayonnaise",
            "condiment",
        ),
        ("vitlök", "Vitlöksolja", "Skafferi > Matolja", "cooking_oil", "cooking_oil"),
        ("kyckling", "Kycklingsalami", "Chark > Salami", "korv", "processed_sausage"),
        ("kyckling", "Chicken hotdog", "Chark", "korv", "processed_sausage"),
        ("kyckling", "Chicken bacon", "Chark", "charcuterie", "processed_deli_meat"),
        (
            "kyckling",
            "Chicken bacon",
            "Kött, chark & fågel",
            "charcuterie",
            "processed_deli_meat",
        ),
    ],
)
def test_raw_food_flavour_does_not_replace_the_sold_product_class(
    ingredient: str,
    product_name: str,
    category: str,
    primary_food: str,
    primary_role: str,
) -> None:
    product = _product("wrong", product_name, ingredient, category=category, price=1)

    decision = evaluate_product_semantics(ingredient, product)

    assert decision.compatible is False
    assert decision.confidence == SemanticConfidence.REJECTED
    assert decision.canonical_food == primary_food
    assert decision.product_role == primary_role
    assert f"primary_product_identity:{primary_food}" in decision.evidence
    assert ProductMatcher().match(_ingredient(ingredient), [product]) == []


@pytest.mark.parametrize("product_name", ["Kycklingsalami", "Chicken hotdog", "Bratwurst"])
def test_explicit_sausage_requirement_preserves_supported_sausage_products(
    product_name: str,
) -> None:
    product = _product("sausage", product_name, "korv", category="Chark > Korv")

    decision = evaluate_product_semantics("korv", product)

    assert decision.compatible is True
    assert decision.confidence == SemanticConfidence.HIGH
    assert decision.canonical_food == "korv"
    assert decision.product_role == "processed_sausage"
    assert [
        match.product_id for match in ProductMatcher().match(_ingredient("korv"), [product])
    ] == ["sausage"]


@pytest.mark.parametrize(
    ("ingredient", "product_name"),
    [
        ("vitlök", "Vitlök Hackad Fryst"),
        ("kyckling", "Kycklinglårfilé"),
        ("kyckling", "Kycklingfilé"),
        ("ost", "Hushållsost"),
        ("ris", "Basmatiris"),
        ("couscous", "Couscous"),
        ("nudlar", "Äggnudlar"),
        ("krossade tomater", "Tomater Krossade"),
        ("korv", "Bratwurst"),
    ],
)
def test_primary_identity_gate_preserves_the_product_itself(
    ingredient: str,
    product_name: str,
) -> None:
    product = _product("correct", product_name, ingredient)

    decision = evaluate_product_semantics(ingredient, product)

    assert decision.compatible is True
    assert decision.confidence == SemanticConfidence.HIGH
    assert [
        match.product_id for match in ProductMatcher().match(_ingredient(ingredient), [product])
    ] == ["correct"]


@pytest.mark.parametrize(
    ("trap_name", "trap_food"),
    [
        ("Havreris Svenskt", "oat"),
        ("Svenskt Havreris", "oat"),
        ("Kornris Svenskt", "barley"),
        ("Svenskt Kornris", "barley"),
    ],
)
def test_oat_and_barley_rice_cannot_beat_ordinary_rice(
    trap_name: str,
    trap_food: str,
) -> None:
    trap = _product("trap", trap_name, "ris", price=1)
    basmati = _product("basmati", "Basmatiris", "ris", price=100)

    rejected = evaluate_product_semantics("ris", trap)
    matches = ProductMatcher().match(_ingredient("ris"), [trap, basmati])

    assert rejected.compatible is False
    assert rejected.confidence == SemanticConfidence.REJECTED
    assert rejected.canonical_food == trap_food
    assert rejected.product_role == "cooking_staple"
    assert f"primary_product_identity:{trap_food}" in rejected.evidence
    assert [match.product_id for match in matches] == ["basmati"]


@pytest.mark.parametrize(
    ("canonical", "product_name", "food"),
    [
        ("havreris", "Havreris Svenskt", "oat"),
        ("kornris", "Kornris Svenskt", "barley"),
    ],
)
def test_explicit_oat_or_barley_rice_canonical_remains_matchable(
    canonical: str,
    product_name: str,
    food: str,
) -> None:
    product = _product("grain", product_name, canonical)

    decision = evaluate_product_semantics(canonical, product)

    assert decision.compatible is True
    assert decision.confidence == SemanticConfidence.HIGH
    assert decision.canonical_food == food
    assert [
        match.product_id for match in ProductMatcher().match(_ingredient(canonical), [product])
    ] == ["grain"]


@pytest.mark.parametrize("mesost_name", ["Mesost Gudbrandsdalen 28%", "Mesost Norsk"])
def test_whey_cheese_cannot_beat_ordinary_cooking_cheese(mesost_name: str) -> None:
    mesost = _product("mesost", mesost_name, "ost", price=1)
    household = _product("household", "Hushållsost", "ost", price=100)

    rejected = evaluate_product_semantics("ost", mesost)
    matches = ProductMatcher().match(_ingredient("ost"), [mesost, household])

    assert rejected.compatible is False
    assert rejected.confidence == SemanticConfidence.REJECTED
    assert rejected.canonical_food == "whey_cheese"
    assert rejected.product_role == "whey_cheese"
    assert "primary_product_identity:whey_cheese" in rejected.evidence
    assert [match.product_id for match in matches] == ["household"]


def test_explicit_whey_cheese_canonical_remains_matchable() -> None:
    mesost = _product("mesost", "Mesost Norsk", "mesost")

    decision = evaluate_product_semantics("mesost", mesost)

    assert decision.compatible is True
    assert decision.confidence == SemanticConfidence.HIGH
    assert decision.canonical_food == "whey_cheese"
    assert decision.product_role == "whey_cheese"
    assert [
        match.product_id for match in ProductMatcher().match(_ingredient("mesost"), [mesost])
    ] == ["mesost"]


def test_preserved_produce_category_cannot_masquerade_as_fresh_carrot() -> None:
    preserved = _product(
        "preserved",
        "Små morötter",
        "morot",
        category="Skafferi > Grönsakskonserver",
        price=1,
    )

    rejected = evaluate_product_semantics("morot", preserved)

    assert rejected.compatible is False
    assert rejected.confidence == SemanticConfidence.REJECTED
    assert rejected.product_role == "preserved_product"
    assert rejected.product_form == "canned"
    assert "visible_prepared_form:canned" in rejected.evidence
    assert ProductMatcher().match(_ingredient("morot"), [preserved]) == []


@pytest.mark.parametrize(
    ("ingredient", "product_name", "expected_food", "expected_role"),
    [
        ("gurka", "Gurka", "cucumber", "preserved_product"),
        ("champinjoner", "Champinjoner", "mushroom", "preserved_product"),
    ],
)
def test_exact_drained_quantity_cannot_make_preserved_produce_match_a_raw_canonical(
    ingredient: str,
    product_name: str,
    expected_food: str,
    expected_role: str,
) -> None:
    preserved = Product(
        product_id="preserved",
        name=product_name,
        canonical_name=ingredient,
        category="Skafferi > Grönsakskonserver",
        store_id="store",
        store_name="Store",
        sale_model=SaleModel.FIXED_PACKAGE,
        package_quantity=400,
        package_unit="g",
        usable_quantity=240,
        usable_unit="g",
        quantity_confidence=QuantityConfidence.EXACT,
        price=19.90,
    )

    rejected = evaluate_product_semantics(ingredient, preserved)

    # The quantity model is deliberately fully resolved; only semantics can
    # prevent this preserved product from appearing as a verified raw item.
    assert preserved.quantity_confidence == QuantityConfidence.EXACT
    assert preserved.usable_quantity == 240
    assert rejected.compatible is False
    assert rejected.confidence == SemanticConfidence.REJECTED
    assert rejected.canonical_food == expected_food
    assert rejected.product_role == expected_role
    assert rejected.product_form == "canned"
    assert "visible_prepared_form:canned" in rejected.evidence
    assert ProductMatcher().match(_ingredient(ingredient), [preserved]) == []


def test_preserved_category_does_not_reject_an_explicit_preserved_canonical() -> None:
    preserved = Product(
        product_id="tomatoes",
        name="Tomater Krossade",
        canonical_name="krossade tomater",
        category="Skafferi > Grönsakskonserver",
        store_id="store",
        store_name="Store",
        sale_model=SaleModel.FIXED_PACKAGE,
        package_quantity=400,
        package_unit="g",
        usable_quantity=400,
        usable_unit="g",
        quantity_confidence=QuantityConfidence.EXACT,
        price=14.90,
    )

    decision = evaluate_product_semantics("krossade tomater", preserved)

    assert decision.compatible is True
    assert decision.confidence == SemanticConfidence.HIGH
    assert decision.canonical_food == "krossade_tomater"
    assert [
        match.product_id
        for match in ProductMatcher().match(_ingredient("krossade tomater"), [preserved])
    ] == ["tomatoes"]


@pytest.mark.parametrize(
    ("ingredient", "composite_product", "raw_product", "composite_form"),
    [
        ("kyckling", "Kycklingpizza", "Kycklingfilé", "pizza"),
        ("kyckling", "Kycklingpålägg", "Kycklingfilé", "deli_product"),
        ("lax", "Rökt lax pålägg", "Laxfilé", "deli_product"),
        ("lax", "Rökt laxfilé", "Laxfilé", "smoked"),
        ("lax", "Laxsushi", "Laxfilé", "sushi"),
        ("fisk", "Torsk wrap", "Fiskfilé", "wrap"),
        ("paprika", "Paprika hummus", "Paprika Röd", "hummus"),
        ("tomat", "Tomat hummus", "Tomater", "hummus"),
        ("pasta", "Pasta pesto", "Penne pasta", "pesto"),
        ("nudlar", "Nudlar wok", "Äggnudlar", "wok_dish"),
        ("tofu", "Wok tofu", "Tofu Naturell", "wok_dish"),
        ("tofu", "Marinerad tofu", "Tofu Naturell", "marinated"),
        ("kidneybönor", "Kidneybönor pasta", "Kidneybönor Naturella", "pasta_dish"),
        ("svarta bönor", "Snacks svarta bönor", "Svarta bönor Naturella", "snack"),
        ("bönor", "Chili vita bönor", "Vita bönor Naturella", "chili_dish"),
        ("ost", "Pesto parmesan", "Hushållsost", "pesto"),
        ("smör", "Kex smör", "Smör", "cracker"),
        ("potatis", "Chips potatis", "Potatis", "snack"),
        ("majs", "Snacks majs", "Majs", "snack"),
    ],
)
def test_raw_ingredients_reject_no_cue_composite_products(
    ingredient: str,
    composite_product: str,
    raw_product: str,
    composite_form: str,
) -> None:
    composite = _product("composite", composite_product, ingredient, price=1)
    raw = _product("raw", raw_product, ingredient, price=100)

    rejected = evaluate_product_semantics(ingredient, composite)
    matches = ProductMatcher().match(_ingredient(ingredient), [composite, raw])

    assert rejected.compatible is False
    assert rejected.confidence == SemanticConfidence.REJECTED
    assert rejected.product_form == composite_form
    assert [match.product_id for match in matches] == ["raw"]


def test_explicit_processed_canonical_is_exempt_from_secondary_component_gate() -> None:
    pizza = _product("pizza", "Pizza med kyckling", "pizza")

    decision = evaluate_product_semantics("pizza", pizza)

    assert decision.compatible is True
    assert decision.confidence == SemanticConfidence.HIGH


@pytest.mark.parametrize(
    ("ingredient", "secondary_product", "primary_product"),
    [
        ("krossade tomater", "Pasta med krossade tomater", "Krossade tomater"),
        ("kokosmjölk", "Curry med kokosmjölk", "Kokosmjölk"),
        ("tomatpuré", "Sås med tomatpuré", "Tomatpuré"),
        ("sojasås", "Marinad med sojasås", "Sojasås"),
        ("buljong", "Soppa med buljong", "Grönsaksbuljong"),
        ("oliver", "Pizza med oliver", "Oliver"),
    ],
)
def test_processed_ingredient_must_also_be_primary_not_a_secondary_component(
    ingredient: str,
    secondary_product: str,
    primary_product: str,
) -> None:
    secondary = _product("secondary", secondary_product, ingredient, price=1)
    primary = _product("primary", primary_product, ingredient, price=100)

    rejected = evaluate_product_semantics(ingredient, secondary)
    matches = ProductMatcher().match(_ingredient(ingredient), [secondary, primary])

    assert rejected.product_role == "secondary_component"
    assert rejected.product_form == "secondary_component"
    assert rejected.confidence == SemanticConfidence.REJECTED
    assert [match.product_id for match in matches] == ["primary"]


@pytest.mark.parametrize(
    ("ingredient", "name", "role", "form"),
    [
        ("kidneybönor", "Kidneybönor Tetra 380 g", "canned_bean", "canned"),
        ("svarta bönor", "Svarta bönor Naturella", "plain_bean", "plain"),
        ("bönor", "Vita bönor Naturella", "plain_bean", "plain"),
    ],
)
def test_plain_and_explicit_canned_bean_identities_remain_valid(
    ingredient: str,
    name: str,
    role: str,
    form: str,
) -> None:
    product = _product("beans", name, ingredient)

    matches = ProductMatcher().match(_ingredient(ingredient), [product])

    assert [match.product_id for match in matches] == ["beans"]
    assert matches[0].product_role == role
    assert matches[0].product_form == form


@pytest.mark.parametrize(
    ("wrong_name", "wrong_canonical"),
    [
        ("Kikärtor 400 g", "linser"),
        ("Ärter Gula 500 g", "linser"),
        ("Potatissallad Crème Fraiche", "crème fraiche"),
    ],
)
def test_search_metadata_cannot_override_visible_food_or_role(
    wrong_name: str,
    wrong_canonical: str,
) -> None:
    matches = ProductMatcher().match(
        _ingredient(wrong_canonical),
        [_product("wrong", wrong_name, wrong_canonical, price=1)],
    )

    assert matches == []


def test_semantic_requirements_keep_public_chicken_name_but_require_meat_roles() -> None:
    requirement = semantic_requirement("kyckling")

    assert requirement.canonical_name == "kyckling"
    assert requirement.canonical_food == "chicken"
    assert {"breast", "thigh", "generic_meat"} <= requirement.allowed_roles
    assert {"heart", "liver", "gizzard", "feet", "broth"} <= requirement.excluded_roles


def test_metadata_only_medium_matches_are_configurable_and_rejected_by_default() -> None:
    ingredient = _ingredient("smör")
    metadata_only = _product("unknown", "Artikel 500 g", "smör")

    decision = evaluate_product_semantics("smör", metadata_only)

    assert decision.compatible is True
    assert decision.confidence == SemanticConfidence.MEDIUM
    assert ProductMatcher().match(ingredient, [metadata_only]) == []
    assert [
        match.product_id
        for match in ProductMatcher(allow_medium_semantic=True).match(ingredient, [metadata_only])
    ] == ["unknown"]
