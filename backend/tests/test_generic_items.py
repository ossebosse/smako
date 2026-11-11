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
