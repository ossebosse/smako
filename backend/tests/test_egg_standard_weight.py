
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
    ("Ägg 6p XL", 60.0),
    ("Ägg 10p Frigående Inomhus Small/medium", 42.0),
    ("Ägg 6p Frigående Inomhus Small", 42.0),
    ("Ägg", 42.0),
])
def test_every_size_class_has_a_lower_bound_standard_weight(name, weight):
    """Owner decision 2026-10-22: every whole-egg pack counts; unknown size uses S."""
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


def test_composite_eggs_get_no_mass():
    for name, ingredients in [("Ägg 10-pack M/L", ("Ägg, socker",)), ("Äggvita Flytande", ("Äggvita.",)),
                              ("Kokta Ägg 6-pack", ("Ägg.",))]:
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


@pytest.mark.parametrize(("name", "brand", "ingredients", "expected"), [
    ("Ägg 12p Frigående Inomhus Medium/large", None, ("ägg.",), True),
    ("Ägg 10-pack M/L Frigående utomhus", None, ("ägg.",), True),
    ("Brunchägg Frigående L/XL 6-pack", None, ("ÄGG från frigående höns inomhus",), True),
    ("Ägg 18p Frigående Inomhus Medium / Large", None, (), True),
    ("Ägg 15p Frigående Inne Medium/large", None, (), True),
    ("Ägg 10p Eko Ekologisk Produktion Medium/large", None, (), True),
    ("Ägg 10p Klimat Frigående Utomhus Medium/large", None, (), True),
    ("Ägg 15p Familj Frigående Inomhus Medium/large", None, (), True),
    ("Ägg 6pack Frigående Inomhus Medium/large", None, (), True),
    ("Stora Ägg 12P Frigående Inomhus", None, (), True),
    ("Små Ägg 15P Frigående Inomhus", None, (), True),
    ("Familjens Ägg 10-pack S/M Frigående Inomhus", None, ("Ägg",), True),
    ("Skåneägg 15p Frigående Inomhus Medium", "Skåneägg", (), True),
    ("Skåneägg Eko 10-pack", None, ("Ägg * Krav-ekologisk ingrediens",), True),
    ("Västgötaägg 10-pack Frigående inomhus", None, ("ÄGG",), True),
    ("Utehönsägg Skåne M/L", None, ("ÄGG",), True),
    ("Ägg 10P Eko 10P", None, (), True),
    ("Äggsallad 12p", None, ("ägg.",), False),
    ("Ägg 12p medium/large", None, ("ägg, majonnäs",), False),
    ("Äggvitor", None, ("Pastöriserade ÄGGVITOR (90%)",), False),
    ("Äggvita Frigående Inne Flytande, Sport", None, (), False),
    ("Äggnudlar", None, ("VETEmjöl, vatten, ÄGG, salt",), False),
    ("Pappardelle Ägg Pasta", None, (), False),
    ("Chokladägg Barbie 3-pack", None, ("socker, kakaosmör",), False),
    ("Kinderägg 3-pack", None, (), False),
    ("Äggersättning Eko", None, ("LUPINMJÖL, majsstärkelse",), False),
    ("Fläsklägg Rimmad", None, (), False),
    ("Diskunderlägg Grå", None, (), False),
    ("Äggskärare", None, (), False),
    ("Kokta Ägg 6-pack", None, ("ägg.",), False),
])
def test_every_whole_shell_egg_pack_is_a_recipe_egg(name, brand, ingredients, expected):
    """Owner decision 2026-10-22: all packs of whole eggs, no egg products."""
    from app.services.official_product_facts import is_plain_shell_egg

    assert is_plain_shell_egg(name, brand, ingredients) is expected
