"""Every shopping row falls under a generic; exact choices are checked, never guessed."""

import pytest
from app.config import Settings
from app.models import PlanRequest, Product
from app.models.personal import ExtraNeed, GenericRef, PersonalPlanning
from app.services.personal_planner import PersonalPlanner
from app.services.personal_policy import PolicyConflict, interpretation
from app.services.personal_store import PersonalConflict, PersonalStore
from app.services.plan_store import PlanStore
from app.services.shopping_list import classify_products, falls_under, price_free_products
from pydantic import ValidationError

from backend.tests.test_comparability_sales_units import ROWS, prepare
from backend.tests.test_product_search import search
from backend.tests.test_weight_offers import NOW


def _foil():
    product = next(Product.model_validate(p) for p in ROWS if "aluminiumfolie" in p["name"].casefold())
    prepared = prepare(product)
    choice = price_free_products(search(prepared, "Aluminiumfolie", now=NOW))[0]
    return product, prepared, choice["product_key"]


def test_exact_product_is_classified_under_the_typed_generic():
    _product, prepared, key = _foil()
    generic = classify_products(prepared, "aluminiumfolie", [key])
    assert generic is not None and generic["query"] == "aluminiumfolie"
    assert falls_under(prepared, [key], generic)


@pytest.mark.parametrize("generic", [
    {"query": "kaffe", "properties": []},  # unrelated name: no similarity attach
    {"query": "aluminiumfolie", "properties": ["99 %"]},  # property not established
])
def test_product_outside_the_generic_is_refused(generic):
    _product, prepared, key = _foil()
    assert not falls_under(prepared, [key], generic)
    assert classify_products(prepared, "kaffe", [key]) is None


def _plan(prepared, extra):
    request = PlanRequest(recipes=0, personal=PersonalPlanning(extras=[extra]))
    state = {"id": "generic-test", "revision": 0, "items": [], "reservations": {}, "events": {}}
    return PersonalPlanner(request, Settings(price_provider="mock"), prepared, state, now=NOW).create()


def test_planner_checks_the_generic_of_an_exact_row():
    product, prepared, key = _foil()
    base = {"kind": "exact", "query": product.name, "quantity": 2, "unit": "st", "purchase_units": True,
            "product_key": key, "properties": interpretation(product.name), "confirmed": True}
    assert _plan(prepared, ExtraNeed(**base, generic=GenericRef(query="aluminiumfolie"))).optimized_basket.total > 0
    with pytest.raises(PolicyConflict, match="hör inte till"):
        _plan(prepared, ExtraNeed(**base, generic=GenericRef(query="kaffe")))


def test_generic_row_cannot_point_to_another_generic():
    with pytest.raises(ValidationError):
        ExtraNeed(query="Mjölk", quantity=1000, unit="ml", confirmed=True, generic=GenericRef(query="mjölk"))


def test_old_rows_keep_their_json_without_the_link():
    row = ExtraNeed(kind="exact", query="Mjölk", quantity=1000, unit="ml", product_key="a" * 32, confirmed=True)
    assert "generic" not in row.model_dump(mode="json")


def test_new_exact_rows_need_a_generic_but_saved_rows_stay_editable(tmp_path):
    store = PersonalStore(PlanStore(tmp_path / "plans.sqlite"))
    owner = "a" * 64
    exact = {"kind": "exact", "query": "Mjölk", "quantity": 1000, "unit": "ml", "product_key": "a" * 32,
             "confirmed": True}
    with pytest.raises(PersonalConflict, match="generisk vara"):
        store.update_shopping(owner, 0, [ExtraNeed(**exact)])
    linked = ExtraNeed(**exact, generic=GenericRef(query="mjölk", properties=["1,5 %"]))
    state = store.update_shopping(owner, 0, [linked])
    assert state["shopping_items"][0]["generic"] == {"query": "mjölk", "properties": ["1,5 %"]}
    # A row saved before the link existed can still be edited.
    legacy = {**exact, "id": "legacy"}
    with store.plans._connect() as connection:
        from app.services.personal_store import read_state, write_state
        current = read_state(connection, owner)
        current["shopping_items"] = [ExtraNeed(**legacy).model_dump()]
        state = write_state(connection, owner, current, state["revision"])
    edited = ExtraNeed(**{**legacy, "quantity": 2000})
    assert store.update_shopping(owner, state["revision"], [edited])["shopping_items"][0]["quantity"] == 2000


def test_product_generic_api_classifies_checks_and_refuses(monkeypatch, tmp_path):
    from app.api import account, personal, plan
    from fastapi.testclient import TestClient

    from backend.tests.test_privacy_erasure import _application

    application, factory, settings = _application(tmp_path)
    for module in (account, personal, plan):
        monkeypatch.setattr(module, "get_settings", lambda: settings)
    application.include_router(personal.router)
    personal.install_handlers(application)
    _product, prepared, key = _foil()
    monkeypatch.setattr(personal.GLOBAL_PREPARED_PRICE_UNIVERSES, "get_for_request", lambda *_: prepared)
    body = {"query": "aluminiumfolie", "postal_code": "22350", "product_keys": [key]}
    with TestClient(application) as client:
        found = client.post("/api/personal/product-generic", json=body)
        assert found.status_code == 200 and found.json()["generic"]["query"] == "aluminiumfolie"
        same = client.post("/api/personal/product-generic", json={**body, "generic": found.json()["generic"]})
        assert same.status_code == 200
        other = client.post("/api/personal/product-generic", json={**body, "generic": {"query": "kaffe"}})
        assert other.status_code == 422 and "hör inte till" in other.json()["detail"]
        assert client.post("/api/personal/product-generic", json={**body, "query": "kaffe"}).status_code == 422
        assert client.post("/api/personal/product-generic", json={**body, "product_keys": ["x"]}).status_code == 422
    factory.kw["bind"].dispose()
