"""Owner request 2026-11-21: fill the remaining nutrition gaps with explicit
generic references, never by relabelling a supplier's table."""
from types import SimpleNamespace

import pytest
from app.models.recipe_preferences import RecipePreferences
from app.services.nutrition_reference import product_reference, reference_evidence
from app.services.personal_policy import ProductFacts
from app.services.recipe_library import candidates
from app.services.recipe_preparation import input_evidence
from app.services.recipe_volume_nutrition import volume_evidence


def product(name, category="Skafferi > Konserver & burkar > Bönor & baljväxter", quantity=230.0, unit="g"):
    return SimpleNamespace(name=name, category=category, offers=[], sale_model="fixed_package",
                           purchase_terms=None, package_quantity=quantity, package_unit=unit,
                           usable_quantity=quantity, usable_unit=unit, quantity_confidence="exact")


def facts(composition, nutrition=None, unit="g", conflicts=(), preparation="as_sold"):
    return ProductFacts(source="retained-supplier", source_product_id="p", source_snapshot_id="s",
                        ingredients=(composition,) if composition else (), nutrition_unit=unit if nutrition else None,
                        nutrition_basis="supplier per 100" if nutrition else None,
                        nutrition_preparation=preparation, nutrition=nutrition or {}, conflicts=conflicts)


def recipe_with(name, form):
    return next(r for r in candidates(RecipePreferences(mode="complete"), 2)
                if any(i.canonical_name == name and i.form == form for i in r.ingredients))


@pytest.mark.parametrize("label,composition,name,food", [
    ("Kikärtor Eko", "INGREDIENSER: Ekologiska kikärtor**(Italien), vatten, salt.**KRAV-ekologisk ingrediens. "
     "KRAV-märkningen verifieras av KIWA.", "kikärtor", 3815),
    ("Kikärter", "INGREDIENSER: Kokta kikärter 60%, vatten, salt, antioxidationsmedel (E300).", "kikärtor", 3815),
    ("Vita Bönor Stora Naturella", "INGREDIENSER Stora vita bönor*, vatten, salt. *Ekologisk ingrediens.", "bönor", 3761),
])
def test_plain_canned_legumes_bought_by_package_weight_use_the_drained_reference(label, composition, name, food):
    recipe = recipe_with(name, "cooked_drained")
    table = {"kcal": 105, "protein_g": 6.1, "fat_g": 2.8, "carbs_g": 11}
    evidence = input_evidence(recipe, product(label), name, "g", False, facts(composition, table))
    assert evidence is not None
    assert evidence.nutrition == reference_evidence(food).nutrition
    assert evidence.evidence_kind != "product_declaration"


def test_flavoured_or_sauced_legumes_still_have_no_drained_reference():
    recipe = recipe_with("bönor", "cooked_drained")
    table = {"kcal": 83, "protein_g": 3.8, "fat_g": 0.6, "carbs_g": 14}
    sauced = facts("Vita bönor 51%, vatten, tomatpuré, socker, salt", table)
    assert input_evidence(recipe, product("Vita Bönor i Tomatsås"), "bönor", "g", False, sauced) is None


def test_household_cheese_without_a_table_uses_hard_cheese_at_the_stated_fat():
    cheese = "Mejeri, ost & ägg > Ost"
    assert product_reference(product("Hushållsost 26%", cheese), "ost", None) == 79
    assert product_reference(product("Hushållsost Mild 17%", cheese), "ost", None) == 95
    assert product_reference(product("Hushållsost Göten Skivad", cheese), "ost", None) == 79
    assert product_reference(product("Hushållsost 38%", cheese), "ost", None) is None
    assert product_reference(product("Hushållsost med kummin", cheese), "ost", None) is None
    assert product_reference(product("Prästost 31%", cheese), "ost", None) is None


def test_plain_beef_and_pork_mince_uses_the_half_and_half_reference():
    meat = "Kött, fågel & chark"
    assert product_reference(product("Blandfärs", meat), "blandfärs", None) == 2499
    assert product_reference(product("Blandfärs Färsk 50/50 22% ca", meat), "blandfärs", None) == 2499
    assert product_reference(product("Blandfärs Färsk 70/30", meat), "blandfärs", None) is None
    assert product_reference(product("Blandfärs Taco", meat), "blandfärs", None) is None
    lamb = facts("Lammkött 50%, nötkött 50%")
    assert product_reference(product("Blandfärs", meat), "blandfärs", lamb) is None


def test_pure_lemon_juice_with_a_contradictory_table_uses_fresh_lemon_juice():
    bottle = product("Citronjuice", "Skafferi", 200.0, "ml")
    contradictory = facts("Ingredienser: Citronjuice 99,9%, eterisk olja (från citronskal), "
                          "antioxidationsmedel: kaliumdiSULFIT",
                          {"kcal": 28, "fat_g": 0.1, "carbs_g": 2.0, "protein_g": 0.3}, unit="ml",
                          conflicts=("supplier_nutrition_conflict",))
    evidence = volume_evidence(bottle, "citronjuice", contradictory)
    assert evidence is not None and evidence.nutrition_unit == "ml"
    assert evidence.nutrition["kcal"] == pytest.approx(29 * 1.038)
    concentrate = facts("Citronjuice från koncentrat, vatten", {"kcal": 20}, conflicts=("x",))
    assert volume_evidence(bottle, "citronjuice", concentrate) is None
    assert volume_evidence(product("Citrondryck", "Skafferi", 200.0, "ml"), "citronjuice", contradictory) is None
