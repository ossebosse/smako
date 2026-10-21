
import pytest
from app.models.product import QuantityConfidence
from app.services.official_product_facts import (
    egg_standard_weight,
    project_usable_quantity,
    shell_egg_quantity_proofs,
)
from app.services.personal_policy import ProductFacts


@pytest.mark.parametrize(("name", "weight"), [
    ("Ägg 15-pack M Frigående inomhus", 51.0),
    ("Ägg 10-pack M/L Frigående utomhus", 51.0),
    ("Ägg 12p Frigående Inomhus Medium/large", 51.0),
    ("Ägg 6-pack L Eko", 60.0),
    ("Ägg 6p Frigående Inomhus Large/x-large", 60.0),
    ("Ägg 6p XL", None),
    ("Ägg 10p Frigående Inomhus Small/medium", None),
    ("Ägg", None),
])
def test_m_and_l_eggs_use_standard_weights(name, weight):
    assert egg_standard_weight(name) == weight


def _product(name, count=15):
    from app.models.product import Product
    return Product.model_validate({
        "product_id": "p1", "store_id": "s1", "store_name": "Butik", "chain": "coop", "name": name,
        "price": 39.9, "package_quantity": count, "package_unit": "st", "sale_model": "fixed_package",
        "usable_quantity": count, "usable_unit": "st", "category": "Ägg", "canonical_name": "ägg",
        "source_provenance": {"source_provider": "test", "source_snapshot_id": "snap", "source_channel": "online",
                              "source_observed_at": "2026-10-16T00:00:00+00:00"}})


def test_counted_pack_gets_the_standard_weight():
    product = _product("Ägg 15-pack M Frigående inomhus")
    facts = {("s1", "p1"): ProductFacts(source="test", source_product_id="p1", source_snapshot_id="snap", ingredients=("Ägg.",))}
    shell_egg_quantity_proofs([product], facts)
    projected = project_usable_quantity(product, facts[("s1", "p1")], required_unit="g")
    assert projected.usable_unit == "g"
    assert projected.usable_quantity == 15 * 51.0
    assert projected.quantity_confidence == QuantityConfidence.DERIVED


def test_small_unknown_or_composite_eggs_get_no_mass():
    for name, ingredients in [("Ägg 6p Frigående Inomhus Small", ("Ägg.",)), ("Ägg", ("Ägg.",)),
                              ("Ägg 10-pack M/L", ("Ägg, socker",))]:
        product = _product(name)
        facts = {("s1", "p1"): ProductFacts(source="test", source_product_id="p1", source_snapshot_id="snap", ingredients=ingredients)}
        shell_egg_quantity_proofs([product], facts)
        assert project_usable_quantity(product, facts[("s1", "p1")], required_unit="g").usable_unit == "st"


def test_production_method_words_do_not_block_a_plain_egg_pack():
    """Review 2026-10-18: Brunchägg L/XL with 'ÄGG från frigående höns inomhus'."""
    product = _product("Brunchägg Frigående L/XL 6-pack", count=6)
    facts = {("s1", "p1"): ProductFacts(source="test", source_product_id="p1", source_snapshot_id="snap",
                                        ingredients=("ÄGG från frigående höns inomhus",))}
    shell_egg_quantity_proofs([product], facts)
    projected = project_usable_quantity(product, facts[("s1", "p1")], required_unit="g")
    assert projected.usable_unit == "g" and projected.usable_quantity == 6 * 60.0


@pytest.mark.parametrize(("label", "ingredients", "expected"), [
    ("ägg 12p frigående inomhus medium/large", "ägg.", True),
    ("ägg 10-pack m/l frigående utomhus", "ägg.", True),
    ("brunchägg frigående l/xl 6-pack", "ägg från frigående höns inomhus", True),
    ("ägg 15-pack m frigående inomhus", "ägg.", True),
    ("ägg 18p frigående utomhus medium/large", "", True),
    ("ägg 18p frigående inomhus medium / large", "", True),
    ("äggsallad 12p", "ägg.", False),
    ("ägg 12p medium/large", "ägg, majonnäs", False),
])
def test_shelf_names_of_plain_egg_packs_are_recipe_eggs(label, ingredients, expected):
    """Malmö names such as '12p ... Medium/large' were not recognised as eggs."""
    from app.services.content_pack_requirements import additional_whole_identity

    assert bool(additional_whole_identity("ägg", "raw_edible", label, ingredients)) is expected
