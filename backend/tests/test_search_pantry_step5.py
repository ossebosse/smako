"""Step 5: search people see and the pantry (docs/PLANNING-ARCHITECTURE.md, steg 5)."""
from app.services.pantry_usage import usual_recipe_use
from app.services.product_search import ProductSearchRequest
from app.services.shopping_list import generic_suggestions

from backend.tests.test_personal_planning_v2 import NOW, prepared, product


def item(name, price=10, **change):
    return product(name, 500, "g", price, identity=name).model_copy(update=change)


INDEX = prepared(
    item("Isbergssallat"), item("Sallad Isberg", 12), item("Ärter Frysta"), item("Druvor Gröna Klass 1"),
    item("Blandfärs 20%"), item("Köttfärspaj", 30), item("Ägg 6p Medium", 25), item("Pasta utan ägg", 5),
    item("Lax Back Loin", 60), item("Lax Mousse", 4, category="Husdjur > Katt > Kattmat", product_role="non_human_food"),
    item("Ris Långkornigt", 20), item("Ris Kyckling & Grönsaker", 3, category="Barn > Barnmat"),
    item("Jordgubbssylt", 22), item("Frukostflingor", 1), item("Mjöl Fioreglut", 30), item("Vetemjöl", 15),
).product_search_index


def names(query):
    result = INDEX.search(ProductSearchRequest(query=query), now=NOW, stale_hours=10**6, warning_hours=10**6)
    return [row["name"] for row in result["results"]]


def test_other_spellings_synonyms_and_compound_words_are_found():
    assert {"Isbergssallat", "Sallad Isberg"} <= set(names("isbergssallad"))
    assert names("frysta ärtor") == ["Ärter Frysta"]
    assert names("vindruvor") == ["Druvor Gröna Klass 1"]
    assert "Blandfärs 20%" in names("köttfärs")
    assert names("sylt") == ["Jordgubbssylt"]
    assert "Vetemjöl" in names("mjöl")
    assert "Frukostflingor" not in names("ost")


def test_whole_words_come_before_cheaper_partial_matches():
    assert names("ägg") == ["Ägg 6p Medium", "Pasta utan ägg"]  # "utan ägg" is last, even if cheaper
    assert names("mjöl")[0] == "Mjöl Fioreglut"


def test_pet_and_baby_food_only_when_asked_for():
    assert names("lax") == ["Lax Back Loin"]
    assert "Lax Mousse" in names("kattmat lax") or "Lax Mousse" in names("lax katt")
    assert names("ris") == ["Ris Långkornigt"]
    assert "Ris Kyckling & Grönsaker" in names("barnmat ris")
    # Nothing else matches: the product is still found.
    assert names("mousse") == ["Lax Mousse"]


def test_recipe_retrieval_is_unchanged():
    keys, _exact, _barcode = INDEX.retrieve(ProductSearchRequest(query="isbergssallad"))
    assert not keys  # Recipes and baskets never gain products from search words.


def test_a_food_word_is_not_suggested_as_a_longer_generic():
    assert "Mjölk" in [g["name"] for g in generic_suggestions("mjö")]
    assert "Mjölk" not in [g["name"] for g in generic_suggestions("mjöl", INDEX.postings)]
    assert "Bryggkaffe" in [g["name"] for g in generic_suggestions("kaffe", {"kaffe"})]


def test_pantry_asks_for_egg_size_and_the_kind_of_broad_words():
    eggs = usual_recipe_use("ägg")
    assert eggs["unit"] == "g" and eggs["egg_grams"] == {"S": 42.0, "M": 51.0, "L": 60.0}
    rice = usual_recipe_use("ris")
    assert rice["usable"][0] < rice["usable"][1] / 2
    assert [k["name"] for k in rice["kinds"]] == ["långkornigt ris", "jasminris", "basmatiris"]
    assert all(k["usable"][0] == k["usable"][1] for k in rice["kinds"])
    assert [k["name"] for k in usual_recipe_use("lök")["kinds"]][:1] == ["gul lök"]
    # Exact-product requirements still need a chosen product (owner decision 2026-11-13).
    assert usual_recipe_use("olivolja")["kinds"] == []
    assert usual_recipe_use("jasminris")["kinds"] == [] and usual_recipe_use("ris")["egg_grams"] is None


def test_the_shops_category_ranks_the_food_above_dishes_that_mention_it():
    index = prepared(
        item("Ost & Broccoli Soppa", 5, category="Soppor"), item("Hushållsost 26%", 60, category="Mejeri > Ost"),
        item("Ost Riven Mild", 30, category="Mejeri > Ost > Riven ost"),
    ).product_search_index
    result = index.search(ProductSearchRequest(query="ost"), now=NOW, stale_hours=10**6, warning_hours=10**6)
    assert [r["name"] for r in result["results"]] == ["Ost Riven Mild", "Hushållsost 26%", "Ost & Broccoli Soppa"]
