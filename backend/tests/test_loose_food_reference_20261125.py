"""Owner decision 2026-11-25: loose meat and produce get public reference nutrition."""

from types import SimpleNamespace

import pytest

from app.services import loose_food_reference as loose
from app.services.nutrition_reference import reference_data


def product(name):
    return SimpleNamespace(name=name, category="", product_id="p", store_id="s")


def test_reference_data_loads_with_the_new_foods():
    data = reference_data()
    assert {"5066", "978", "290", "3938"} <= data["foods"].keys()


@pytest.mark.parametrize("name, label, expected", [
    ("nötkött", "Högrev Bit Sverige", 953),
    ("nötkött", "Grytbitar Nöt Sverige", 961),
    ("nötkött", "Nötkött", 5066),
    ("fläskkött", "Grytbitar Fläsk Sverige", 977),
    ("fläskkött", "Fläskfilé", 970),
    ("fläskkarré", "Fläskkarré Skivad", 978),
    ("lammkött", "Lammstek Fransyska", 924),
    ("sallad", "Isbergssallad", 340),
    ("sallad", "Huvudsallat", 3938),
    ("rädisa", "Rädisor i knippe", 293),
    ("mynta", "Mynta i kruka", 7194),
    ("salladslök", "Salladslök knippe", "mvt:salladslök"),
    ("kyckling", "Kyckling Lårfilé", 1174),
])
def test_a_plain_loose_food_gets_its_reference(name, label, expected):
    assert loose.identity(name, label) == expected


@pytest.mark.parametrize("name, label", [
    ("nötkött", "Marinerad Biff"), ("fläskkött", "Pulled Pork Färdig"), ("sallad", "Sallad med dressing sås"),
    ("nötkött", "Rökt Nötkött"), ("okänd", "Något"),
])
def test_another_food_than_the_plain_one_gets_nothing(name, label):
    assert loose.identity(name, label) is None


def test_evidence_needs_no_own_table_and_a_matching_form():
    raw = loose.evidence(product("Grytbitar Nöt"), "nötkött", None, "raw_edible")
    assert raw.nutrition["protein_g"] == pytest.approx(20.6)
    own_table = SimpleNamespace(conflicts=(), nutrition={"kcal": 150, "protein_g": 20.0, "fat_g": 7, "carbs_g": 0})
    assert loose.evidence(product("Grytbitar Nöt"), "nötkött", own_table, "raw_edible") is None
    partial = SimpleNamespace(conflicts=(), nutrition={"protein_g": 20.0})
    assert loose.evidence(product("Grytbitar Nöt"), "nötkött", partial, "raw_edible") is not None
    assert loose.evidence(product("Grytbitar Nöt"), "nötkött", None, "dry") is None
    onion = loose.evidence(product("Salladslök"), "salladslök", None, "raw_edible")
    assert onion.nutrition["protein_g"] == pytest.approx(1.8) and "Matvaretabellen" in onion.source


@pytest.mark.parametrize("name, label, form, source, protein", [
    ("chiliflakes", "Chiliflakes", "dry", "Matvaretabellen", None),
    ("garam masala", "Garam Masala", "dry", "Matvaretabellen", None),
    ("kapris", "Kapris i lag", "preserved_drained", "Matvaretabellen", None),
    ("röd currypasta", "Röd Currypasta", "as_sold", "Matvaretabellen", None),
    ("citrongräs", "Citrongräs", "as_sold", "FoodData Central", 1.82),
    ("breda risnudlar", "Risnudlar breda", "dry", "Livsmedelsverket", None),
    ("sardeller", "Ansjovisfiléer Sardeller", "preserved_drained", "Livsmedelsverket", None),
    ("surkål", "Surkål", "preserved_drained", "Livsmedelsverket", None),
])
def test_spices_preserves_and_noodles_have_a_reference(name, label, form, source, protein):
    found = loose.evidence(product(label), name, None, form)
    assert found is not None and source in found.source
    assert set(found.nutrition) == {"kcal", "protein_g", "fat_g", "carbs_g"}
    if protein is not None:
        assert found.nutrition["protein_g"] == pytest.approx(protein)
    assert loose.evidence(product(label), name, None, "raw_edible" if form != "raw_edible" else "dry") is None
