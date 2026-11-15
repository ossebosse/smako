"""Owner decision 2026-11-14: Ät inte and fresh produce without a declaration.

Ät inte is checked on names, compound words included, and on the declaration
when one exists; only composite products need a declaration. An allergy still
needs a complete declaration, except for fresh produce, which under EU
1169/2011 article 19 is its own single ingredient.
"""
from types import SimpleNamespace

import pytest
from app.models.personal import TasteProfile
from app.services.personal_policy import (
    PolicyConflict,
    check_product,
    is_composite,
    mentions,
    single_ingredient_by_rule,
)


def item(name, category="Skafferi", canonical=None):
    return SimpleNamespace(name=name, canonical_name=canonical or name.casefold(), category=category, food_family=None)


@pytest.mark.parametrize("term,text", [("lök", "Rödlök"), ("lök", "Lökpulver"), ("fläsk", "Fläskfilé"), ("ost", "Prästost"),
                                       ("mjölk", "Mellanmjölk"), ("koriander", "Korianderfrö"), ("gul lök", "Gul lök 1 kg")])
def test_compound_words_name_what_they_are_made_of(term, text):
    assert mentions(term, text)


@pytest.mark.parametrize("term,text", [("ost", "Ostron"), ("gluten", "Glutenfri pasta"), ("mjölk", "Laktosfri havredryck mjölkfri"),
                                       ("ägg", "Pasta utan ägg"), ("lök", "Potatis"), ("ris", "Pris")])
def test_free_from_and_lookalikes_are_not_mentions(term, text):
    assert not mentions(term, text)


def test_avoided_plain_products_are_checked_by_name_and_composites_need_a_declaration():
    avoid = TasteProfile(exclusions=["koriander"])
    for plain in (item("Potatis", "Frukt & grönt"), item("Kycklingfilé", "Kött, fågel & chark > Kyckling"), item("Jasminris")):
        check_product(plain, avoid, None)
    with pytest.raises(PolicyConflict, match="valt bort"):
        check_product(item("Koriander i kruka", "Frukt & grönt"), avoid, None)
    for composite in (item("Kycklingbuljong"), item("Tacokrydda"), item("Thai Röd Currypasta"), item("Lasagne", "Färdigmat")):
        with pytest.raises(PolicyConflict) as error:
            check_product(composite, avoid, None)
        assert error.value.code == "DATA_BLOCKED", composite.name
        assert is_composite(composite)


def test_allergy_accepts_only_fresh_produce_without_a_declaration():
    allergy = TasteProfile(allergies=["gluten"])
    for produce in (item("Potatis", "Frukt & grönt"), item("Gul lök", "Frukt & grönt > Lök"), item("Broccoli", "Frukt & Grönt")):
        assert single_ingredient_by_rule(produce)
        check_product(produce, allergy, None)
    for other in (item("Jasminris"), item("Kycklingfilé", "Kött, fågel & chark"), item("Torkade aprikoser", "Frukt & grönt"),
                  item("Valnötter", "Frukt & grönt"), item("Sallad mix", "Frukt & grönt"), item("Edamamebönor", "Frukt & grönt")):
        assert not single_ingredient_by_rule(other), other.name
    with pytest.raises(PolicyConflict) as error:
        check_product(item("Jasminris"), allergy, None)
    assert error.value.code == "DATA_BLOCKED"
    with pytest.raises(PolicyConflict, match="valt bort"):
        check_product(item("Stjälkselleri", "Frukt & grönt"), TasteProfile(allergies=["selleri"]), None)
