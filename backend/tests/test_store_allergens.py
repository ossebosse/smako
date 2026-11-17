"""Owner decision 2026-11-17: allergy choices use the stores' own allergen data."""
import pytest
from app.models.personal import TasteProfile
from app.services.personal_policy import PolicyConflict, check_product
from app.services.personal_source_facts import project_raw_facts
from app.services.store_allergens import CHECKED, declared_allergens

from backend.tests.test_personal_planning_v2 import product


@pytest.mark.parametrize(("text", "present", "trace"), [
    ("Pastöriserad MJÖLK, salt, ystenzym.", {"mjölk"}, set()),
    ("Ingredienser: DURUMVETE. Kan innehålla spår av SOJA, ÄGG och SENAP.", {"gluten", "vete"}, {"soja", "ägg", "senap"}),
    ("Kokosmjölk 80 %, vatten.", set(), set()),
    ("Havredryck: vatten, HAVRE 10 %, rapsolja.", {"gluten"}, set()),
    ("Ostron, salt.", {"blötdjur"}, set()),
    ("ROSTAT MALET KAFFE.", set(), set()),
    ("JORDNÖTTER 98 %, salt. Kan innehålla spår av MANDEL.", {"jordnötter"}, {"nötter"}),
    ("Tomat, sellerirot, vin (SULFITER), räkor, lax.", {"selleri", "sulfit", "skaldjur", "fisk"}, set()),
    ("Vetemjöl, smör, sesamfrö, LUPINmjöl.", {"vete", "gluten", "mjölk", "sesam", "lupin"}, set()),
])
def test_the_declaration_names_present_allergens_and_traces(text, present, trace):
    checked, found, traces = declared_allergens(text)
    assert set(checked) == set(CHECKED)
    assert set(found) == present and set(traces) == trace


def test_unreadable_declarations_check_nothing():
    assert declared_allergens(None) is None and declared_allergens("  ") is None and declared_allergens("123") is None


def coop(text):
    return project_raw_facts({"id": "1", "name": "Vara", "listOfIngredients": text}, chain="coop",
                             product_id="sås", snapshot_id="v2-frozen", source_reference="test")


def test_an_allergy_accepts_a_composite_product_whose_declaration_lacks_the_allergen():
    sauce = product("tomatsås", 500, "g", 20)
    check_product(sauce, TasteProfile(allergies=["mjölk"]), coop("Tomat, lök, olivolja, salt."))
    with pytest.raises(PolicyConflict, match="innehåller eller kan innehålla spår av mjölk"):
        check_product(sauce, TasteProfile(allergies=["mjölk"]), coop("Tomat, GRÄDDE, salt."))
    with pytest.raises(PolicyConflict, match="spår av nötter"):
        check_product(sauce, TasteProfile(allergies=["nötter"]), coop("Tomat. Kan innehålla spår av HASSELNÖT."))


def test_a_composite_product_without_a_declaration_is_still_refused():
    with pytest.raises(PolicyConflict):
        check_product(product("tomatsås", 500, "g", 20), TasteProfile(allergies=["mjölk"]), None)
