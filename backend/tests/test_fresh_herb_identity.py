"""Fresh herbs, coarse pepper and fine salt match by identity (2026-11-07).

The reviewed registry listed only frozen chopped coriander/chives, so every
authored fresh-leaf recipe rejected plain fresh bunches with exact package
mass. Identity may widen; quantity, shelf and composition gates may not.
"""
from types import SimpleNamespace

import pytest
from app.models.product import QuantityConfidence
from app.services.content_pack_requirements import additional_whole_identity
from app.services.content_pack_requirements import compatible as pack_compatible
from app.services.intake_product_links import compatible, entries, fresh_herb_alternative
from app.services.product_semantics import _culinary_label_match


def key_for(name):
    return next(k for k, row in entries().items() if row["name"] == name and row["kind"] == "frozen_edible")


def herb(name="Koriander Klass 1", grams=25.0, category="Frukt & grönt", **changes):
    values = {"name": name, "brand": None, "gtin": None, "product_id": "p", "store_id": "context:willys:x",
              "category": category, "sale_model": "fixed_package", "purchase_terms": None,
              "package_quantity": grams, "package_unit": "g", "usable_quantity": grams, "usable_unit": "g",
              "quantity_confidence": QuantityConfidence.EXACT, "source_provenance": None}
    return SimpleNamespace(**(values | changes))


@pytest.mark.parametrize("canonical,name", [
    ("koriander", "Koriander"), ("koriander", "Koriander Klass 1"), ("koriander", "Koriander Eko"),
    ("koriander", "Koriander ,"), ("gräslök", "Gräslök Klass 1"), ("gräslök", "Gräslök Knippe"),
])
def test_plain_fresh_bunch_with_exact_mass_is_the_authored_fresh_herb(canonical, name):
    key = key_for(canonical)
    assert compatible(key, herb(name))
    assert pack_compatible([key], herb(name), None)


@pytest.mark.parametrize("product", [
    herb("Koriander Malen"), herb("Koriander Burk", category="Skafferi"), herb("Korianderfrö Hel"),
    herb("Koriandersås"), herb("Koriander", category="Okategoriserad"),
    herb("Koriander", category="Fryst > Grönsaker & kryddor"), herb("Koriander i Kruka"),
    herb("Koriander", grams=429.0), herb("Koriander", quantity_confidence=QuantityConfidence.ESTIMATED),
    herb("Koriander", sale_model="sold_by_weight"), herb("Koriander", usable_unit="st", package_unit="st"),
    herb("Koriander", usable_quantity=20.0), herb("Gräslök Light", category="Mejeri > Färskost"),
])
def test_dried_unclear_potted_implausible_or_estimated_rows_stay_rejected(product):
    assert not compatible(key_for("koriander"), product)
    assert not compatible(key_for("gräslök"), product)


def test_fresh_alternative_only_widens_frozen_herb_rows():
    other = next(row for row in entries().values() if row["kind"] != "frozen_edible")
    assert not fresh_herb_alternative(other, herb())


def test_salted_or_oiled_composition_is_not_a_plain_herb():
    fact = SimpleNamespace(ingredients=["koriander", "rapsolja", "salt"])
    assert not compatible(key_for("koriander"), herb("Koriander"), fact)


@pytest.mark.parametrize("name", ["Svartpeppar Grovmalen", "Svartpeppar Mellanmalen Påse", "Svartpeppar Malen"])
def test_any_ground_black_pepper_is_ground_black_pepper(name):
    p = herb(name, category="Skafferi > Kryddor")
    assert pack_compatible(["black_pepper"], p, None)
    assert additional_whole_identity("svartpeppar", "dry", name.casefold(), "")
    assert _culinary_label_match("svartpeppar", p).compatible


@pytest.mark.parametrize("name", ["Svartpeppar Hel", "Svartpeppar Crostini", "Citronpeppar Grovmalen"])
def test_whole_or_other_pepper_products_stay_rejected(name):
    p = herb(name, category="Skafferi > Kryddor")
    assert not (pack_compatible(["black_pepper"], p, None) and _culinary_label_match("svartpeppar", p).compatible)


def test_fine_salt_label_is_plain_salt():
    assert _culinary_label_match("salt", herb("Fint Salt med Jod", category="Skafferi")).compatible
