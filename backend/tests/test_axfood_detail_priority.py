"""Recipe demand orders the Axfood detail queue; nothing is fetched here."""
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
priority = importlib.import_module("axfood_detail_priority")


def test_products_with_a_declaration_are_not_queued():
    assert priority.needs_declaration(None)
    assert priority.needs_declaration(SimpleNamespace(nutrition={}, ingredients=("x",)))
    assert priority.needs_declaration(SimpleNamespace(nutrition={"kcal": 1}, ingredients=()))
    assert not priority.needs_declaration(SimpleNamespace(nutrition={"kcal": 1}, ingredients=("x",)))


def test_most_used_ingredients_first_and_shared_codes_once(monkeypatch):
    products = [
        SimpleNamespace(chain="willys", store_id="w", product_id="w-lok"),
        SimpleNamespace(chain="willys", store_id="w", product_id="w-salt"),
        SimpleNamespace(chain="hemkop", store_id="h", product_id="h-lok"),
        SimpleNamespace(chain="hemkop", store_id="h", product_id="h-dill"),
        SimpleNamespace(chain="willys", store_id="w", product_id="w-done"),
        SimpleNamespace(chain="citygross", store_id="c", product_id="c-lok"),
    ]
    index = [SimpleNamespace(key="lök", product_indexes=(0, 2, 4, 5)),
             SimpleNamespace(key="salt", product_indexes=(1,)),
             SimpleNamespace(key="dill", product_indexes=(3,))]
    prepared = SimpleNamespace(universe=SimpleNamespace(products=products,
                                                        indexes=SimpleNamespace(canonical=index)))
    monkeypatch.setattr("app.services.meal_prepared_artifacts.ingredient_search_positions",
                        lambda *args, **kwargs: ())
    monkeypatch.setattr("app.services.ingredient_normalizer.canonicalize_ingredient_name", lambda name: name)

    def fact(code, nutrition=None):
        return SimpleNamespace(retailer_product_id=code, nutrition=nutrition or {}, ingredients=())

    facts = {("w", "w-lok"): fact("101_ST"), ("w", "w-salt"): fact("202_ST"),
             ("h", "h-lok"): fact("101_ST"), ("h", "h-dill"): fact("303_ST"),
             ("w", "w-done"): SimpleNamespace(retailer_product_id="404_ST", nutrition={"kcal": 1},
                                             ingredients=("x",))}
    ingredient = lambda name: SimpleNamespace(canonical_name=name, name=name)
    recipes = [SimpleNamespace(ingredients=[ingredient("lök"), ingredient("salt")]),
               SimpleNamespace(ingredients=[ingredient("lök"), ingredient("dill")])]
    ordered = priority.priority_codes(prepared, facts, recipes)
    assert ordered["willys"] == ["101_ST", "202_ST"]
    assert ordered["hemkop"] == ["303_ST"]  # 101_ST is read via the Willys document.
