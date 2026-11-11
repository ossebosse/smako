"""Generic shopping-list rows are bought as the goods they name, at the lowest price."""
import pytest
from app.models.personal import ExtraNeed
from app.models.product import Product
from app.services.generic_items import generic_item_index, same_word, usual_amount, word_forms
from app.services.personal_policy import PolicyConflict

from backend.tests.test_personal_planning_v2 import prepared, request, run
from backend.tests.test_personal_planning_v2 import product as base_product


def product(name, quantity, unit, price, *, store="willys", category="Skafferi", brand=None, gtin=None, **extra):
    row = base_product(name, quantity, unit, price, store=store, identity=f"{store}:{brand}:{name}").model_dump()
    row.update(category=category, brand=brand, gtin=gtin, chain=store, **extra)
    return Product(**row)


def loose(name, grams, kilo_price, **kwargs):
    return product(name, grams, "g", kilo_price, sale_model="variable_weight_package", usable_quantity=grams,
                   usable_unit="g", sale_price=kilo_price, sale_unit="kg", comparison_price=kilo_price,
                   comparison_unit="kg", quantity_confidence="estimated", variable_weight=True, **kwargs)


def bought(result):
    return sorted(row.product_name for store in result.optimized_basket.stores for row in store.items)


def plan(p, *extras, **kwargs):
    req = request(extras=[ExtraNeed(confirmed=True, **extra) for extra in extras], **kwargs)
    req.purchase_planning_mode = "estimated"
    return run(p, req)


def test_banana_is_fruit_not_banana_yoghurt():
    p = prepared(
        loose("Banan Klass 1", 180, 21.9, category="Frukt & Grönt > Frukt > Bananer"),
        product("Banan & Vanilj Yo-ghurt 0,1%", 1000, "g", 18.45, category="Mejeri, ost & ägg > Filmjölk & Yoghurt > Smaksatt yoghurt"),
        product("Smoothie Banan, äpple & kokos", 90, "g", 9.42, store="coop", category="Mellanmål"),
        product("Banan Familjefavoriter Yoghurt 1,8%", 1500, "g", 24.9, category="Mejeri, ost & ägg > Filmjölk & Yoghurt > Smaksatt yoghurt"),
    )
    result = plan(p, {"query": "banan", "quantity": 500, "unit": "g"})
    assert bought(result) == ["Banan Klass 1"]
    assert result.optimized_basket.total == pytest.approx(11.83, abs=0.02)
    assert bought(plan(p, {"query": "bananer", "quantity": 500, "unit": "g"})) == ["Banan Klass 1"]


def test_coffee_includes_ground_coffee_compounds_and_takes_the_cheapest():
    p = prepared(
        product("Bryggkaffe Mellanrost", 500, "g", 44.5, store="coop", category="Bryggkaffe", brand="Xtra"),
        product("Kaffe Espresso Rossa", 250, "g", 53.42, store="coop", category="Espressokaffe", brand="Lavazza"),
        product("Glass Kaffe", 400, "g", 54.85, store="coop", category="Glasspaket", brand="Häagen-Dazs"),
        product("Choklad Kaffe Dadelboll", 90, "g", 23.9, category="Skafferi > Torkad frukt"),
        product("Havredryck Till Kaffe", 1000, "g", 19.9, store="coop", category="Kaffemjölk & baristamjölk"),
    )
    result = plan(p, {"query": "kaffe", "quantity": 500, "unit": "g"})
    assert bought(result) == ["Bryggkaffe Mellanrost"] and result.optimized_basket.total == 44.5


def test_butter_is_not_a_blend_a_flavour_or_peanut_butter():
    p = prepared(
        product("Havssalt med Smör 70%", 500, "g", 33.5, brand="Flora", category="Mejeri, ost & ägg > Smör, margarin & jäst > Matfett"),
        product("Smör & Raps Normalsaltat", 500, "g", 30, store="coop", brand="Coop", category="Bordsask smör & Margarin"),
        product("Mikropopcorn Extra Stora Smör 3-pack", 270, "g", 18.5, category="Glass, godis & snacks > Chips, snacks & dip > Popcorn & salta pinnar"),
        product("Chips Brynt smör & chili", 275, "g", 20, store="coop", category="Okategoriserad"),
        product("Jordnötssmör Crunchy", 500, "g", 25, store="coop", category="Jordnötssmör"),
        product("Smör Normalsaltat 82%", 500, "g", 49.9, brand="Garant", category="Mejeri, ost & ägg > Smör, margarin & jäst > Matfett"),
    )
    assert bought(plan(p, {"query": "smör", "quantity": 500, "unit": "g"})) == ["Smör Normalsaltat 82%"]


def test_category_evidence_follows_the_product_to_a_chain_with_broad_categories():
    p = prepared(
        product("Mikropopcorn Smör", 270, "g", 18.5, gtin="7310000000017", category="Glass, godis & snacks > Popcorn"),
        product("Mikropopcorn Smör", 270, "g", 17, store="hemkop", gtin="7310000000017", category="Godis, snacks & glass"),
        product("Smör Normalsaltat", 500, "g", 52, store="hemkop", category="Mejeri, ost & ägg"),
        product("Fusilli Pasta", 500, "g", 7.9, brand="Monte Castello", category="Skafferi > Pasta, ris & matgryn > Pasta > Kort pasta"),
        product("Pasta Bolognese", 390, "g", 5, store="coop", brand="Findus", category="Övrig färdigmat"),
    )
    index = generic_item_index(p)
    by_name = {(row.name, row.store_id): i for i, row in enumerate(p.universe.products)}
    assert not index.accepts("smör", by_name["Mikropopcorn Smör", "hemkop"])
    assert index.accepts("smör", by_name["Smör Normalsaltat", "hemkop"])
    assert bought(plan(p, {"query": "pasta", "quantity": 500, "unit": "g"})) == ["Fusilli Pasta"]


def test_curated_generic_leaves_out_preserved_forms_also_when_typed_in_plural():
    p = prepared(
        product("Tomater Krossade", 390, "g", 7.84, store="coop", brand="Xtra", category="Tomat"),
        product("Passerade tomater", 500, "g", 11.95, store="coop", category="Tomat"),
        product("Tomater Kvist", 500, "g", 24.9, store="coop", category="Tomat"),
        product("Gurka Tunnskivad Mor Annas", 590, "g", 9, store="coop", category="Gurka"),
        product("Gurka", 280, "g", 15.9, store="coop", category="Gurka"),
    )
    assert bought(plan(p, {"query": "tomat", "quantity": 500, "unit": "g"})) == ["Tomater Kvist"]
    assert bought(plan(p, {"query": "tomater", "quantity": 500, "unit": "g"})) == ["Tomater Kvist"]
    assert bought(plan(p, {"query": "gurka", "quantity": 250, "unit": "g"})) == ["Gurka"]


def test_brand_rows_and_plain_variant_at_the_same_price():
    cola = {"brand": "Coca-cola", "category": "Dryck > Läsk > Läsk stor"}
    p = prepared(
        product("Coca-cola Lemon Zero Läsk Pet", 1500, "ml", 19.4, **cola),
        product("Coca-cola Läsk Pet", 1500, "ml", 19.4, **cola),
        product("Coca-cola Zero Läsk Pet", 1500, "ml", 19.4, **cola),
        product("Cola Läsk", 1500, "ml", 9.9, brand="Eldorado", category="Dryck > Läsk > Läsk stor"),
        product("Bryggkaffe Mörkrost Skånerost", 500, "g", 79, brand="ZOÉGAS", store="coop", category="Bryggkaffe"),
    )
    assert bought(plan(p, {"query": "coca cola", "quantity": 1500, "unit": "ml"})) == ["Coca-cola Läsk Pet"]
    assert bought(plan(p, {"query": "Zoégas Skånerost", "quantity": 500, "unit": "g"})) == ["Bryggkaffe Mörkrost Skånerost"]


def test_generic_without_any_matching_goods_is_reported_not_substituted():
    p = prepared(product("Yoghurt Päron & äpple 0,1%", 1000, "g", 19.68, category="Smaksatt yoghurt", store="coop"))
    with pytest.raises(PolicyConflict, match="äpple"):
        plan(p, {"query": "äpple", "quantity": 500, "unit": "g"})


def test_word_forms_and_usual_amount():
    assert same_word("banan", "bananer") and same_word("gurka", "gurkor") and same_word("apple", "applen")
    assert not same_word("smor", "smorgas") and not same_word("ris", "risotto") and not same_word("ost", "ostkaka")
    assert {"banan", "bananer"} <= set(word_forms("bananer"))
    assert {"kaffe", "bryggkaffe"} <= set(word_forms("kaffe"))
    p = prepared(
        product("Pasta Penne", 500, "g", 7.95, category="Formpasta", store="coop"),
        product("Pasta Fusilli", 500, "g", 7.95, category="Formpasta", store="coop"),
        product("Pasta Gnocchi", 1000, "g", 20, category="Formpasta", store="coop"),
        loose("Banan Klass 1", 180, 21.9, category="Frukt & Grönt > Frukt > Bananer"),
    )
    assert usual_amount(p, "pasta") == {"quantity": 500.0, "unit": "g"}
    assert usual_amount(p, "banan") == {"quantity": 500.0, "unit": "g"}
    assert usual_amount(p, "tvättmedel") is None


def test_cuts_count_as_the_goods_and_equal_offers_keep_the_plain_name():
    p = prepared(
        product("Laxportioner skinnfri", 400, "g", 73.77, store="coop", category="Färsk & Fryst lax > Fryst lax"),
        product("Kattmat Vuxen Lax", 400, "g", 20, store="coop", category="Torrfoder"),
        product("Gravlaxsås", 200, "g", 15, store="coop", category="Färdig sås"),
    )
    assert bought(plan(p, {"query": "lax", "quantity": 400, "unit": "g"})) == ["Laxportioner skinnfri"]


def test_own_items_are_bought_with_recipe_facts_loaded():
    """With meals in the plan Smako loads product facts; a loose banana must still be buyable."""
    p = prepared(
        loose("Banan Klass 1", 180, 21.9, category="Frukt & Grönt > Frukt > Bananer", semantic_confidence="low"),
        product("Bryggkaffe Mellanrost", 500, "g", 44.5, store="coop", category="Bryggkaffe", semantic_confidence="low"),
    )
    req = request(extras=[ExtraNeed(confirmed=True, query="banan", quantity=500, unit="g"),
                          ExtraNeed(confirmed=True, query="kaffe", quantity=500, unit="g")])
    req.purchase_planning_mode = "estimated"
    from app.services.personal_policy import ProductFacts

    facts = {("other", "row"): ProductFacts(source="test", source_product_id="row", source_snapshot_id="other")}
    assert bought(run(p, req, facts=facts)) == ["Banan Klass 1", "Bryggkaffe Mellanrost"]


def test_own_item_takes_cheaper_loose_weight_but_recipe_keeps_exact_package():
    """Owner decision 2026-11-11: the cheapest wins for own items, recipes keep exact packages first."""
    from app.models.personal import MealSettings, MealSlot
    from app.models.recipe import Recipe, RecipeIngredient

    p = prepared(
        loose("Äpple Röda Klass 1", 170, 14.9, category="Frukt & Grönt > Frukt > Äpplen"),
        product("Äpple Royal Gala i påse", 1000, "g", 24.9, category="Frukt & Grönt > Frukt > Äpplen"),
    )
    own = plan(p, {"query": "äpple", "quantity": 500, "unit": "g"})
    assert bought(own) == ["Äpple Röda Klass 1"]
    assert own.optimized_basket.verification_status.value == "VERIFIED_WITH_ESTIMATES"
    pie = Recipe(name="Äppelsnitt", servings=1, ingredients=[RecipeIngredient(name="äpple", quantity=500, unit="g")],
                 instructions=["Skiva äpplena."])
    req = request(slots=[MealSlot(id="dinner", day=1, meal_type="dinner", recipe=pie)],
                  meals=[MealSettings(meal_type="dinner", count=1, servings=1)])
    req.purchase_planning_mode = "estimated"
    assert bought(run(p, req)) == ["Äpple Royal Gala i påse"]


def test_same_product_in_other_chains_is_found_by_brand_words_and_package():
    from app.services.generic_items import same_product_index

    p = prepared(
        product("Bryggkaffe Mörkrost Skånerost", 500, "g", 82.5, store="coop", brand="ZOÉGAS", category="Bryggkaffe"),
        product("Skånerost Bryggkaffe Mörkrost", 500, "g", 81.9, store="willys", brand="Zoégas", category="Dryck > Kaffe"),
        product("Zoégas Skånerost Bryggkaffe Mörkrost", 500, "g", 88, store="hemkop", brand="Zoégas", category="Skafferi"),
        product("Skånerost Hela Bönor", 800, "g", 120, store="willys", brand="Zoégas", category="Dryck > Kaffe"),
        product("Skånerost Bryggkaffe Mörkrost", 450, "g", 70, store="ica", brand="Zoégas", category="Kaffe"),
        product("Bryggkaffe Mörkrost", 500, "g", 50, store="ica", brand="Gevalia", category="Kaffe"),
    )
    by_store = {row.store_id: key for key, rows in p.product_search_index.groups.items() for row in [p.universe.products[rows[0]]]
                if "Bryggkaffe" in row.name and row.brand.casefold().startswith("zo")}
    others = same_product_index(p).others([by_store["coop"]])
    assert set(others) == {by_store["willys"], by_store["hemkop"]}  # not 450 g, not beans, not Gevalia


def test_same_product_api_offers_other_chains(monkeypatch):
    from app.main import app
    from app.services import price_universe_runtime
    from fastapi.testclient import TestClient

    p = prepared(
        product("Bryggkaffe Mörkrost Skånerost", 500, "g", 82.5, store="coop", brand="ZOÉGAS", category="Bryggkaffe"),
        product("Skånerost Bryggkaffe Mörkrost", 500, "g", 81.9, store="willys", brand="Zoégas", category="Dryck > Kaffe > Bryggkaffe"),
    )
    monkeypatch.setattr(price_universe_runtime.GLOBAL_PREPARED_PRICE_UNIVERSES, "get_for_request", lambda *_a, **_k: p)
    coop = next(k for k, rows in p.product_search_index.groups.items() if p.universe.products[rows[0]].store_id == "coop")
    client = TestClient(app, headers={"Origin": "http://testserver"})
    response = client.post("/api/personal/same-product", json={"query": "kaffe", "postal_code": "22350", "product_keys": [coop],
                                                              "generic": {"query": "kaffe", "properties": []}})
    assert response.status_code == 200, response.text
    rows = response.json()["products"]
    assert [row["chains"] for row in rows] == [["Willys"]] and "Skånerost" in rows[0]["display_name"]


def test_same_product_skips_a_different_barcode():
    from app.services.generic_items import same_product_index

    p = prepared(
        product("Vispgrädde 40%", 500, "ml", 30, store="coop", brand="Skånemejerier", gtin="7310867003285", category="Grädde"),
        product("Vispgrädde 40%", 500, "ml", 31, store="ica", brand="Skånemejerier", gtin="7310867003339", category="Grädde"),
        product("Vispgrädde 40%", 500, "ml", 29, store="hemkop", brand="Skånemejerier", category="Mejeri"),
    )
    keys = {p.universe.products[rows[0]].store_id: key for key, rows in p.product_search_index.groups.items()}
    assert same_product_index(p).others([keys["coop"]]) == [keys["hemkop"]]
