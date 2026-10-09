"""Private list drafts, price-free retrieval and whole-basket alternatives."""
import json

import pytest
from app.models.personal import ExtraNeed, ShoppingWrite
from app.services.personal_policy import PolicyConflict
from app.services.personal_store import PersonalConflict, PersonalStore
from app.services.plan_store import PlanOwnerMismatchError, PlanStore
from app.services.shopping_list import generic_suggestions, price_free_products

from backend.tests.test_personal_planning_v2 import key_for, prepared, product, request, run


def test_one_of_chooses_whole_basket_not_locally_cheapest():
    p = prepared(product("Libero blöjor 6", 30, "st", 40, store="coop"),
                 product("Pampers blöjor 6", 40, "st", 45, store="ica"),
                 product("mjölk", 1000, "ml", 30, store="coop"),
                 product("mjölk", 1000, "ml", 10, store="ica"))
    choice = ExtraNeed(kind="one_of", query="blöjor 6", quantity=30, unit="st", food=False,
                      alternatives=[key_for(p, "Libero blöjor 6"), key_for(p, "Pampers blöjor 6")], confirmed=True)
    req = request(extras=[choice, ExtraNeed(query="mjölk", quantity=1000, unit="ml", confirmed=True)])
    req.max_stores = 1
    result = run(p, req)
    assert result.recipes == [] and result.portions == 0
    assert result.optimized_basket.total == 55
    assert result.optimized_basket.store_count == 1
    assert any(row.product_name == "Pampers blöjor 6" for store in result.optimized_basket.stores for row in store.items)
    assert result.personal.checks
    # Minimum amount is retained, not one arbitrary package per alternative.
    choice.quantity = 41
    req.personal.extras[0] = choice
    assert run(p, req).optimized_basket.total == 100


def test_unavailable_alternative_does_not_hide_valid_choice_or_change_unit():
    p = prepared(product("mjölk A", 1000, "ml", 20))
    choice = ExtraNeed(kind="one_of", query="mjölk", quantity=500, unit="ml", confirmed=True,
                      alternatives=[key_for(p, "mjölk A"), "f" * 32])
    assert run(p, request(extras=[choice])).optimized_basket.total == 20
    choice.unit = "g"
    with pytest.raises(PolicyConflict):
        run(p, request(extras=[choice]))


def test_exact_alternatives_allow_different_variants_but_shared_properties_bind():
    p = prepared(product("mjölk 1,5 %", 1000, "ml", 20), product("mjölk 3 %", 1000, "ml", 10))
    choice = ExtraNeed(kind="one_of", query="mjölk 1,5 %", quantity=500, unit="ml", confirmed=True,
                      alternatives=[key_for(p, "mjölk 1,5 %"), key_for(p, "mjölk 3 %")])
    assert run(p, request(extras=[choice])).optimized_basket.total == 10
    choice.properties = ["1,5 %"]
    assert run(p, request(extras=[choice])).optimized_basket.total == 20


def test_alternative_hard_policy_and_owner_revision_roundtrip(tmp_path):
    p = prepared(product("mjölk A", 1000, "ml", 20), product("mjölk B", 1000, "ml", 10))
    extra = ExtraNeed(kind="one_of", query="mjölk", quantity=500, unit="ml", confirmed=True,
                     alternatives=[key_for(p, "mjölk A"), key_for(p, "mjölk B")])
    req = request(extras=[extra])
    req.personal.profile.exclusions = ["mjölk"]
    with pytest.raises(PolicyConflict):
        run(p, req)
    req.personal.profile.exclusions = []
    store = PlanStore(tmp_path / "plans.sqlite")
    saved = store.create(req, run(p, req), owner_actor_hash="a" * 64)
    reopened = PlanStore(tmp_path / "plans.sqlite").get_owned(saved.plan_id, owner_actor_hash="a" * 64)
    assert reopened.request.personal.extras[0].alternatives == extra.alternatives
    assert reopened.plan.model_dump() == saved.plan.model_dump()
    with pytest.raises(PlanOwnerMismatchError):
        store.get_owned(saved.plan_id, owner_actor_hash="b" * 64)


def test_private_draft_frequent_choices_idempotence_and_conflict(tmp_path):
    plans = PlanStore(tmp_path / "plans.sqlite")
    store = PersonalStore(plans)
    item = ExtraNeed(query="kaffe", quantity=500, unit="g", confirmed=True)
    owner, other = "a" * 64, "b" * 64
    first = store.update_shopping(owner, 0, [item])
    assert first["shopping_common"][0]["count"] == 1
    assert store.update_shopping(owner, 0, [item]) == first
    assert not store.read(other).get("shopping_items")
    # A first explicit empty draft must be persisted, even for an old owner
    # whose last saved plan contains extras. Otherwise reload resurrects them.
    assert store.update_shopping(other, 0, [])["shopping_items"] == []
    assert "shopping_items" in store.read(other)
    with pytest.raises(PersonalConflict):
        store.update_shopping(owner, 0, [])
    second = store.update_shopping(owner, 1, [])
    third = store.update_shopping(owner, second["revision"], [item])
    assert third["shopping_common"][0]["count"] == 2
    assert not third["items"] and not third["reservations"]
    assert PersonalStore(PlanStore(tmp_path / "plans.sqlite")).read(owner) == third
    with pytest.raises(ValueError):
        ShoppingWrite(revision=0, items=[item, item])


def test_bounded_frequent_choices_and_legacy_empty_fields(tmp_path):
    store = PersonalStore(PlanStore(tmp_path / "plans.sqlite"))
    rows = [ExtraNeed(query=f"vara {i}", quantity=1, unit="st", confirmed=True) for i in range(60)]
    state = store.update_shopping("a" * 64, 0, rows)
    assert len(state["shopping_common"]) == 50
    assert "alternatives" not in rows[0].model_dump()
    assert "alternative_names" not in rows[0].model_dump()
    for kind, choices in [("generic", ["a" * 32]), ("one_of", ["a" * 32]), ("one_of", ["a" * 32] * 2)]:
        with pytest.raises(ValueError):
            ExtraNeed(kind=kind, alternatives=choices, query="test", quantity=1, unit="st", confirmed=True)


def test_generic_quantities_and_price_free_allowlist():
    rows = generic_suggestions("kaffe 0,5kg")
    assert {r["query"] for r in rows} == {"bryggkaffe", "kaffebönor"}
    assert all(r["quantity"] == 500 and r["unit"] == "g" for r in rows)
    assert generic_suggestions("mjölk 2l")[0]["quantity"] == 2000
    assert generic_suggestions("mjölk 500g") == []
    assert generic_suggestions("Spaghetti")[0]["properties"] == ["spaghetti"]
    with pytest.raises(ValueError):
        generic_suggestions("kaffe 0g")
    row = {"product_key": "a" * 32, "name": "Vara", "package": "500 g", "prices": [{"price": 50}], "best_price": 50}
    data = price_free_products({"results": [row]})
    assert "price" not in json.dumps(data)
    assert data[0]["package"] == "500 g"
    assert data[0]["matches"][0]["product_key"] == "a" * 32


def test_duplicate_display_labels_preserve_distinct_exact_keys():
    common = {"name": "Spaghetti", "brand": "Garant", "package": "1000 g",
              "package_quantity": 1000, "package_unit": "g", "identity_basis": "context_product"}
    first = {**common, "product_key": "a" * 32, "prices": [{"store_name": "Willys Lund", "price": 20}]}
    second = {**common, "product_key": "b" * 32, "prices": [{"store_name": "Hemköp", "price": 21}]}
    groups = price_free_products({"results": [first, second, first]})
    assert len(groups) == 1 and groups[0]["display_name"] == "Garant Spaghetti"
    assert "Willys" not in json.dumps(groups) and "Hemköp" not in json.dumps(groups, ensure_ascii=False)
    assert "source_label" not in json.dumps(groups)
    incomplete = {**first, "product_key": "c" * 32, "package": None, "package_quantity": None}
    ranked = price_free_products({"results": [incomplete, first]})
    assert ranked[0]["selectable"] and not ranked[-1]["selectable"]
    assert ranked[-1]["package"] == "Förpackningsstorlek saknas"
    assert [m["product_key"] for m in groups[0]["matches"]] == ["a" * 32, "b" * 32]
    assert "price" not in json.dumps(groups)
    assert len(price_free_products({"results": [first, {**second, "brand": "Barilla"}]})) == 2


def test_shopping_api_ownership_origin_validation_and_no_price(monkeypatch, tmp_path, caplog):
    from app.api import account, personal, plan
    from fastapi.testclient import TestClient

    from backend.tests.test_privacy_erasure import _application

    application, factory, settings = _application(tmp_path)
    for module in (account, personal, plan):
        monkeypatch.setattr(module, "get_settings", lambda: settings)
    application.include_router(personal.router)
    personal.install_handlers(application)
    p = prepared(product("kaffe", 500, "g", 50))
    monkeypatch.setattr(personal.GLOBAL_PREPARED_PRICE_UNIVERSES, "get_for_request", lambda *_: p)
    with TestClient(application) as first, TestClient(application) as second:
        item = ExtraNeed(query="privat-testvara", quantity=500, unit="g", confirmed=True).model_dump()
        response = first.put("/api/personal/shopping-list", json={"revision": 0, "items": [item]})
        assert response.status_code == 200
        assert response.headers["cache-control"] == "private, no-store"
        assert second.get("/api/personal/state").json()["shopping_items"] == []
        assert first.get("/api/personal/state").json()["shopping_items"] == [item]
        assert first.put("/api/personal/shopping-list", json={"revision": 0, "items": []}).status_code == 409
        assert first.put("/api/personal/shopping-list", json={"revision": 1, "items": []},
                         headers={"Origin": "https://attacker.example"}).status_code == 403
        assert first.get("/api/personal/shopping-suggestions?q=kaffe%200g").status_code == 422
        suggestions = first.get("/api/personal/shopping-suggestions?q=kaffe%20500g")
        assert suggestions.status_code == 200
        assert "best_price" not in suggestions.text and '"prices"' not in suggestions.text
        parsed = first.post("/api/personal/interpret-extra", json={"text": "kaffe 0,5kg"}).json()
        assert (parsed["query"], parsed["quantity"], parsed["unit"]) == ("kaffe", 500, "g")
        queries = []
        def search_suggestions(request, **kwargs):
            queries.append(request.query)
            row = {"product_key": ("a" if request.query.startswith("brygg") else "b") * 32,
                   "name": request.query, "brand": "Test", "package": "500 g",
                   "package_quantity": 500, "package_unit": "g", "identity_basis": "context_product"}
            return {"results": [row]}
        monkeypatch.setattr(p.product_search_index, "search", search_suggestions)
        ranked = first.get("/api/personal/shopping-suggestions?q=kaffe%20500g").json()
        assert queries == ["bryggkaffe 500 g", "kaffe 500g"]
        assert [row["product_key"] for row in ranked["products"]] == ["a" * 32, "b" * 32]

    assert "privat-testvara" not in caplog.text
    factory.kw["bind"].dispose()


def test_shopping_draft_moves_only_to_verified_account(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from app.api import account, plan
    from app.config import Settings
    from app.services.beta_observability import pseudonymous_actor
    from fastapi import HTTPException
    from starlette.requests import Request

    settings = Settings(plan_store_path=tmp_path / "migration.sqlite", secret_key="test-shopping-account-migration-key")
    plans = PlanStore(settings.plan_store_path)
    for module in (account, plan):
        monkeypatch.setattr(module, "get_settings", lambda: settings)
    req = Request({"type": "http", "method": "POST", "scheme": "https", "path": "/api/account/migrate-guest",
                   "headers": [], "server": ("testserver", 443), "session": {},
                   "app": SimpleNamespace(state=SimpleNamespace(plan_store=plans))})
    req.state.anonymous_session_id = "test-shopping-guest"
    guest = pseudonymous_actor(req.state.anonymous_session_id, settings)
    private = PersonalStore(plans)
    source = private.update_shopping(guest, 0, [ExtraNeed(query="spaghetti", quantity=500, unit="g", confirmed=True)])
    payload = account.MigrationRequest(guest_revision=1, account_revision=0, confirm_move_to_verified_account=True)
    with pytest.raises(HTTPException):
        account.migrate_guest(payload, req)
    req.scope["session"]["account_owner"] = "a" * 64  # verified middleware output, not a client field
    assert account.migrate_guest(payload, req)["status"] == "MOVED"
    moved = private.read("a" * 64)
    assert moved["shopping_items"] == source["shopping_items"]
    assert moved["shopping_common"] == source["shopping_common"]
    assert not private.read(guest).get("shopping_items")
