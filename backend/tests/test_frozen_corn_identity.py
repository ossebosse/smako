"""Frozen whole kernels must match without admitting cob, blend or snack food."""
import pytest
from app.models.ingredient import NormalizedIngredient
from app.models.personal import TasteProfile
from app.models.product import Product
from app.services.complete_recipes import _whole_food_identity
from app.services.personal_policy import PolicyConflict, ProductFacts, check_product
from app.services.product_matcher import ProductMatcher
from app.services.product_semantics import _frozen_corn_identity, evaluate_product_semantics


def corn(name="Majskorn Frysta", category="Fryst > Grönsaker & kryddor > Grönsaker"):
    return Product(product_id="synthetic-corn", store_id="synthetic-store", store_name="Test",
        name=name, canonical_name="majs", canonical_food="corn", category=category,
        package_quantity=450, package_unit="g", usable_quantity=450, usable_unit="g", price=17)


def test_whole_frozen_kernels_reach_real_matcher_with_exact_amount_and_price():
    p = corn()
    decision = evaluate_product_semantics("majs", p)
    assert decision.compatible and decision.confidence == "high"
    matches = ProductMatcher().match(NormalizedIngredient(canonical_name="majs", required_quantity=400, unit="g"), [p])
    assert len(matches) == 1
    assert matches[0].usable_quantity == 450 and matches[0].price == 17
    assert matches[0].store_id == "synthetic-store"
    assert _whole_food_identity("majs", "as_sold", p, None, ["frozen", "plain"])


@pytest.mark.parametrize("name", ["Majskolv Bitar Fryst", "Ärter Majs Paprika Fryst", "Majskorn Smör",
    "Majskakor", "Majsstärkelse", "Majskyckling Bröstfilé Fryst", "Majskorn Frysta färdigrätt", "Majs", "Sockermajs"])
def test_corn_rule_never_accepts_other_shapes_or_compounds(name):
    assert _frozen_corn_identity(name.casefold(), "fryst") is None
    if name not in {"Majs", "Sockermajs"}:
        assert not _whole_food_identity("majs", "as_sold", corn(name), None, ["frozen", "plain"])


def test_changed_category_does_not_reuse_frozen_identity():
    assert _frozen_corn_identity("majskorn", "skafferiet konserver") is None
    assert _frozen_corn_identity("majskorn ekologisk", "fryst grönsaker") is not None
    assert not evaluate_product_semantics("majs", corn(category="Djurfoder fryst")).compatible


@pytest.mark.parametrize("declaration", ["Majskorn, smör", "Majskorn, salt", "Ärtor, majskorn, paprika", "Majskorn, vatten", "Majskorn (smör)", "Majskorn (Ungern, smör)"])
@pytest.mark.parametrize("requirements", [[], ["plain"], ["plain", "frozen"]])
def test_changed_facts_cannot_keep_plain_kernel_approval(declaration, requirements):
    fact = ProductFacts(source="synthetic", source_product_id="synthetic-corn", source_snapshot_id="synthetic-snapshot",
                        ingredients=(declaration,), ingredients_complete=True)
    assert not _whole_food_identity("majs", "as_sold", corn(), fact, requirements)


def test_kernel_identity_is_not_a_positive_allergy_certificate():
    fact = ProductFacts(source="synthetic", source_product_id="synthetic-corn", source_snapshot_id="synthetic-snapshot",
                        ingredients=("INGREDIENSER: Majskorn* (*Ekologisk råvara)",), ingredients_complete=False)
    assert _whole_food_identity("majs", "as_sold", corn(), fact, ["plain", "frozen"])
    with pytest.raises(PolicyConflict):
        check_product(corn(), TasteProfile(allergies=["mjölk"]), fact)
