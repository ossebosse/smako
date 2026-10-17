
import pytest
from app.models.product import QuantityConfidence
from app.services.official_product_facts import (
    egg_size_class_minimum,
    project_usable_quantity,
    shell_egg_quantity_proofs,
)
from app.services.personal_policy import ProductFacts


@pytest.mark.parametrize(("name", "minimum"), [
    ("Ägg 15-pack M Frigående inomhus", 53.0),
    ("Ägg 10-pack M/L Frigående utomhus", 53.0),
    ("Ägg 12p Frigående Inomhus Medium/large", 53.0),
    ("Ägg 6p Frigående Inomhus Large/x-large", 63.0),
    ("Brunchägg Frigående L/XL 6-pack", 63.0),
    ("Ägg 10p Frigående Inomhus Small/medium", None),
    ("Ägg 6p Frigående Inomhus Small", None),
    ("Ägg", None),
])
def test_weight_class_minimum_uses_the_smallest_named_class(name, minimum):
    assert egg_size_class_minimum(name) == minimum


def _product(name, count=15):
    from app.models.product import Product
    return Product.model_validate({
        "product_id": "p1", "store_id": "s1", "store_name": "Butik", "chain": "coop", "name": name,
        "price": 39.9, "package_quantity": count, "package_unit": "st", "sale_model": "fixed_package",
        "usable_quantity": count, "usable_unit": "st", "category": "Ägg", "canonical_name": "ägg",
        "source_provenance": {"source_provider": "test", "source_snapshot_id": "snap", "source_channel": "online",
                              "source_observed_at": "2026-10-16T00:00:00+00:00"}})


def test_counted_pack_gets_a_conservative_derived_mass():
    product = _product("Ägg 15-pack M Frigående inomhus")
    facts = {("s1", "p1"): ProductFacts(source="test", source_product_id="p1", source_snapshot_id="snap", ingredients=("Ägg.",))}
    shell_egg_quantity_proofs([product], facts)
    projected = project_usable_quantity(product, facts[("s1", "p1")], required_unit="g")
    assert projected.usable_unit == "g"
    assert projected.usable_quantity == pytest.approx(15 * 53 * 0.88, abs=0.1)
    assert projected.quantity_confidence == QuantityConfidence.DERIVED


def test_small_unknown_or_composite_eggs_get_no_mass():
    for name, ingredients in [("Ägg 6p Frigående Inomhus Small", ("Ägg.",)), ("Ägg", ("Ägg.",)),
                              ("Ägg 10-pack M/L", ("Ägg, socker",))]:
        product = _product(name)
        facts = {("s1", "p1"): ProductFacts(source="test", source_product_id="p1", source_snapshot_id="snap", ingredients=ingredients)}
        shell_egg_quantity_proofs([product], facts)
        assert project_usable_quantity(product, facts[("s1", "p1")], required_unit="g").usable_unit == "st"
