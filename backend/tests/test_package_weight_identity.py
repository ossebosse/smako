"""Owner decision 2026-11-07: plan firm avocado and brine-free mozzarella on
exact package mass when no edible/drained declaration exists."""
from types import SimpleNamespace

import pytest
from app.models.product import QuantityConfidence
from app.services.intake_product_links import compatible, entries, package_weight_alternative


def key_for(name, form):
    return next(k for k, row in entries().items()
                if row["name"] == name and row["form"] == form and row["kind"] == "definition_only")


AVOCADO = key_for("avokado", "raw_edible")
MOZZARELLA = key_for("mozzarella", "as_sold")


def item(name, category, grams=300.0, **changes):
    values = {"name": name, "brand": None, "gtin": None, "product_id": "p", "store_id": "context:citygross:x",
              "category": category, "sale_model": "fixed_package", "purchase_terms": None,
              "package_quantity": grams, "package_unit": "g", "usable_quantity": grams, "usable_unit": "g",
              "quantity_confidence": QuantityConfidence.EXACT, "source_provenance": None}
    return SimpleNamespace(**(values | changes))


FRUIT = "Frukt & grönt > Frukt > Avokado"
SHREDDED = "Mejeri, ost & ägg > Matlagningsost > Riven ost"


@pytest.mark.parametrize("key,product", [
    (AVOCADO, item("Avokado 2-Pack Eko Hass", FRUIT)), (AVOCADO, item("Avokado 3-Pack", FRUIT)),
    (AVOCADO, item("Avokado Hass", FRUIT, 700.0)), (AVOCADO, item("Avokado Klass 1", FRUIT)),
    (MOZZARELLA, item("Mozzarella Riven", SHREDDED, 150.0)),
    (MOZZARELLA, item("Mozzarella Familjefavoriter Riven 21%", SHREDDED, 500.0)),
])
def test_exact_package_mass_of_the_plain_identity_is_accepted(key, product):
    assert compatible(key, product)


@pytest.mark.parametrize("key,product", [
    (AVOCADO, item("Avokado Tärningar", "Fryst > Frysta grönsaker & kryddor > Grönsaker")),
    (AVOCADO, item("Avokado Ätmogen", FRUIT)),
    (AVOCADO, item("Avokado Stor", FRUIT, quantity_confidence=QuantityConfidence.ESTIMATED)),
    (AVOCADO, item("Avokado", FRUIT, sale_model="sold_by_piece", package_unit="st", usable_unit="st")),
    (AVOCADO, item("Guacamole Avokado", "Kylt > Dipp")),
    (MOZZARELLA, item("Mozzarella", "Mejeri, ost & ägg > Matlagningsost > Mozzarella", 125.0)),
    (MOZZARELLA, item("Mozzarella Bufala Campana", "Mejeri > Matlagningsost > Mozzarella", 260.0,
                      usable_quantity=125.0, quantity_confidence=QuantityConfidence.DERIVED)),
    (MOZZARELLA, item("Mozzarella Sticks", "Fryst färdigmat > Flerportionsrätter")),
    (MOZZARELLA, item("Pizzaost Mozzarella Riven", SHREDDED)),
])
def test_other_forms_estimates_and_composites_stay_rejected(key, product):
    assert not compatible(key, product)


def test_composition_with_brine_or_seasoning_is_rejected():
    assert not compatible(MOZZARELLA, item("Mozzarella Riven", SHREDDED), SimpleNamespace(ingredients=["mozzarella", "lag"], field_sources={}, conflicts=()))
    assert not compatible(AVOCADO, item("Avokado Hass", FRUIT), SimpleNamespace(ingredients=["avokado", "citronsyra"], field_sources={}, conflicts=()))


def test_only_listed_identities_use_package_mass():
    other = next(r for r in entries().values() if r["kind"] == "definition_only" and r["name"] == "purjolök")
    assert not package_weight_alternative(other, item("Purjolök Klass 1", "Frukt & grönt", 200.0))
