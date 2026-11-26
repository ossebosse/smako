from types import SimpleNamespace

import pytest

from app.services import stock_concentrate as stock


def product(name, brand="Touch Of Taste", quantity=180.0, unit="ml"):
    return SimpleNamespace(name=name, brand=brand, package_quantity=quantity, package_unit=unit,
                           usable_quantity=quantity, usable_unit=unit)


def fact(ingredients="Vatten, salt, vitt vin, grönsakskoncentrat (morot 3,0%)"):
    return SimpleNamespace(ingredients=(ingredients,), conflicts=(), nutrition={"kcal": 1.0})


@pytest.mark.parametrize("name, brand, key", [
    ("Grönsaksfond", "Touch Of Taste", "grönsaksfond"),
    ("Grönsaksfond", "Bong Touch of Taste", "grönsaksfond"),
    ("Grönsaksfond Eko", "Bong Touch of Taste", "ekologisk grönsaksfond"),
    ("Grönsaksfond Ekologiskt", "Touch Of Taste", "ekologisk grönsaksfond"),
    ("Touch of Taste Grönsaksfond 180 ml", "", "grönsaksfond"),
])
def test_liquid_concentrate_is_recognised(name, brand, key):
    assert stock.identity(product(name, brand), fact()) == key


@pytest.mark.parametrize("item", [
    product("Grönsaksfond 4-pack", "Knorr", 112.0, "g"),
    product("Grönsaksfond 4-pack", "Touch of Taste", 112.0, "g"),
    product("Grönsaksbuljong 12-pack", "Coop", 6000.0),
    product("Grönsak Buljong Tärning", "Eldorado", 6000.0),
    product("Grönsaksfond", "Fantasty", 180.0),
    product("Kycklingfond", "Touch Of Taste", 180.0),
])
def test_cubes_powder_pots_other_brands_and_other_stocks_are_not(item):
    assert stock.identity(item, fact()) is None


def test_a_ready_to_drink_composition_is_not_concentrate():
    assert stock.identity(product("Grönsaksfond"), fact("Grönsaksbuljong 98 %, salt")) is None


def test_concentrate_nutrition_follows_the_manufacturer_dose():
    assert stock.dilution_factor() == pytest.approx(522.5 / 22.5)
    found = stock.evidence(product("Grönsaksfond"), fact())
    assert found.nutrition_unit == "ml" and found.evidence_kind == "manufacturer_dilution_estimate"
    assert found.nutrition["kcal"] == pytest.approx(23.22, abs=0.01)
    assert found.nutrition["carbs_g"] == pytest.approx(found.nutrition["kcal"] / 4, abs=0.01)
    assert found.nutrition["protein_g"] == 0 and found.nutrition["fat_g"] == 0
    eko = stock.evidence(product("Grönsaksfond Eko", "Bong Touch of Taste"), fact())
    assert eko.nutrition["kcal"] == pytest.approx(46.44, abs=0.01)
    # 35 ml concentrate in a four-portion dish: about 2 kcal per portion.
    assert found.nutrition["kcal"] * 35 / 100 / 4 < 2.1
