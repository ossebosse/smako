"""Owner request 2026-11-21: inputs without any reviewed product in Lund or
Malmö are matched by label, shelf, composition and exact package mass."""
from types import SimpleNamespace

import pytest
from app.models.product import QuantityConfidence
from app.services.complete_recipes import declared_drained
from app.services.intake_product_links import PACKAGE_WEIGHT_IDENTITIES, compatible, entries


def key(name, form):
    return next(k for k, row in entries().items() if row["name"] == name and row["form"] == form)


def item(name, category, grams=200.0, **changes):
    values = {"name": name, "brand": None, "gtin": None, "product_id": "p", "store_id": "context:coop:x",
              "category": category, "sale_model": "fixed_package", "purchase_terms": None,
              "package_quantity": grams, "package_unit": "g", "usable_quantity": grams, "usable_unit": "g",
              "quantity_confidence": QuantityConfidence.EXACT, "source_provenance": None}
    return SimpleNamespace(**(values | changes))


def fact(*ingredients):
    return SimpleNamespace(ingredients=list(ingredients), field_sources={}, conflicts=())


ACCEPTED = [
    ("mozzarella", "preserved_drained", "Mozzarella Minibollar", "Ost > Mozzarella", None),
    ("halloumi", "as_sold", "Halloumi 26%", "Ost > Grillost", None),
    ("polenta", "dry", "Polenta Majsgryn", "Skafferi > Matgryner", fact("majsgryn")),
    ("majsgryn", "dry", "Glutenfri Polenta Eko", "Gryn", fact("ekologisk polenta")),
    ("räkor", "cooked_drained", "Räkor Handskalade", "Fisk > Räkor", fact("räkor", "vatten", "salt")),
    ("kronärtskocka", "preserved_drained", "Kronärtskockshjärtan", "Grönsakskonserver", fact("kronärtskockor", "vatten", "salt")),
    ("sushiris", "dry", "Sushi Rice", "Ris & Nudlar", fact("ris")),
    ("surkål", "preserved_drained", "Surkål", "Konserver > Grönsaker", fact("vitkål", "salt")),
    ("sardiner", "preserved_drained", "Sardiner Olja", "Fiskkonserver", fact("sardiner", "solrosolja", "salt")),
    ("vinblad", "preserved_drained", "Vinblad i Lag", "Skafferi > Grönsakskonserver", None),
    ("gelatinblad", "as_sold", "Gelatinblad", "Övrigt till baket", fact("gelatin")),
    ("svart te", "dry", "Svart te Yellow Label 100-pack", "Te > Svart te", fact("svart te")),
    ("vattenkastanjer", "preserved_drained", "Vattenkastanjer skivade", "Grönsakskonserver", fact("vattenkastanjer", "vatten")),
    ("musslor", "cooked_drained", "Musslor i Vatten", "Skafferi", fact("blåmusslor", "vatten", "salt")),
    ("böngroddar", "raw_edible", "Böngroddar Ekologisk", "Frukt & grönt", None),
    ("groddade mungbönor", "as_sold", "Böngroddar Ekologisk", "Frukt & grönt", None),
    ("salsa verde av tomatillo", "as_sold", "Salsa Verde mild", "Sås & Salsa", fact("gröna tomatillos", "vatten", "chili")),
    ("lufttorkad skinka", "as_sold", "Prosciutto Crudo", "Lufttorkat", fact("skinka", "salt")),
    ("gröna linser", "cooked_drained", "Gröna linser Eko", "Linser", fact("gröna linser", "vatten", "salt")),
    ("råa räkor", "raw_edible", "Scampi Vannameiräka", "Räkor", fact("råa skalade vannamei räkor", "vatten")),
    ("silkestofu", "as_sold", "Tofu Silkesmjuk Eko", "Tofu", fact("vatten", "sojabönor")),
    ("vegansk smördeg", "as_sold", "Smördeg", "Pajer", fact("vetemjöl", "vatten", "palmolja", "salt")),
    ("matjessill", "preserved_drained", "Matjessill Klassisk", "Sill & Ansjovis", fact("sill", "socker", "salt", "ättika")),
    ("nori", "as_sold", "Sjögräs Sushi nori", "Tillbehör", fact("sjögräs")),
    ("ghee", "as_sold", "Ghee Nötig", "Kryddor & smaksättare > Matolja", fact("klarnat smör")),
    ("saltgurka", "preserved_drained", "Saltgurka Hel", "Gurka", fact("gurka", "vatten", "salt", "ättika")),
]


@pytest.mark.parametrize("name,form,label,category,declaration", ACCEPTED)
def test_the_plain_identity_on_its_shelf_is_accepted(name, form, label, category, declaration):
    assert compatible(key(name, form), item(label, category), declaration)


REJECTED = [
    ("mozzarella", "preserved_drained", "Mozzarella Riven", "Ost > Riven ost", None),
    ("räkor", "cooked_drained", "Räkor Panerade", "Fisk > Räkor", None),
    ("räkor", "cooked_drained", "Räkor med skal", "Fisk > Räkor", None),
    ("sardiner", "preserved_drained", "Sardiner i Tomatsås", "Fiskkonserver", fact("sardiner", "tomatsås")),
    ("svart te", "dry", "Svart te Earl Grey 25-pack", "Te > Svart te", fact("svart te", "arom")),
    ("musslor", "cooked_drained", "Musslor", "Havsdelikatesser", fact("chilenska blåmusslor")),
    ("böngroddar", "raw_edible", "Böngroddar", "Grönsakskonserver", fact("böngroddar", "vatten", "salt")),
    ("gröna linser", "cooked_drained", "Gröna Linser", "Skafferi", fact("torkade gröna linser")),
    ("råa räkor", "raw_edible", "Räkor Skalade", "Räkor", fact("räkor", "salt")),
    ("vegansk smördeg", "as_sold", "Smördeg", "Pajer", fact("vetemjöl", "smör 30 %", "vatten")),
    ("matjessill", "preserved_drained", "Matjesfilé", "Sill & Ansjovis", fact("sill", "tomatpuré")),
    ("ghee", "as_sold", "Ghee", "Matfett", fact("rapsolja", "palmolja")),
    ("surkål", "preserved_drained", "Surkål", "Konserver", None),
]


@pytest.mark.parametrize("name,form,label,category,declaration", REJECTED)
def test_other_foods_forms_and_compositions_stay_rejected(name, form, label, category, declaration):
    product = item(label, category, 900.0 if name == "surkål" else 200.0,
                   quantity_confidence=QuantityConfidence.ESTIMATED if name == "surkål" else QuantityConfidence.EXACT)
    assert not compatible(key(name, form), product, declaration)


def test_every_new_identity_has_an_intake_row_that_reaches_the_gate():
    rows = {(r["name"], r["form"]): r for r in entries().values() if (r["name"], r["form"]) in PACKAGE_WEIGHT_IDENTITIES}
    assert {(n, f) for n, f, *_ in ACCEPTED} <= set(rows)


def test_package_mass_of_a_drained_form_still_gets_the_shopping_list_notice():
    k = key("sardiner", "preserved_drained")
    requirements = (f"pack:{k}",)
    product, declaration = item("Sardiner Olja", "Fiskkonserver", 120.0), fact("sardiner", "solrosolja", "salt")
    assert declared_drained("sardiner", "preserved_drained", requirements, product, declaration)
    assert not declared_drained("sardiner", "preserved_drained", requirements, product, declaration, package_weight=False)


def test_a_labelled_package_is_retrieved_under_the_recipe_name():
    """Retailers index "Glutenfri Polenta Eko" under polenta; the recipe asks for majsgryn."""
    from app.services.intake_product_links import search_positions
    products = [item("Glutenfri Polenta Eko", "Gryn", 500.0), item("Böngroddar Ekologisk", "Frukt & grönt", 180.0),
                item("Majsmjöl", "Mjöl", 500.0)]
    prepared = SimpleNamespace(universe=SimpleNamespace(products=products),
                               product_search_cache=SimpleNamespace(get_or_compute=lambda _key, compute: compute()))
    positions = search_positions(prepared)
    assert 0 in positions["majsgryn"] and 0 in positions["polenta"]
    assert 1 in positions["groddade mungbönor"] and 1 in positions["böngroddar"]
    assert not any(2 in found for found in positions.values())
