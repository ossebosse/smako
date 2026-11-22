"""Owner request 2026-11-22: members rate dishes and get points for receipts."""

from __future__ import annotations

import json
import secrets

import pytest
from app.api import account, member, personal, plan
from app.config import Settings
from app.services import member_rewards as rewards
from app.services.plan_store import PlanStore
from app.services.planning_rules import PlanningRules
from fastapi import FastAPI
from fastapi.testclient import TestClient

PASSWORD = "a long test password 123"
# Text recognised by tesseract.js (swe) from a photographed test receipt.
OCR_TEXT = """ICA Nära Klostergården
Klostergårdsvägen 12, Lund
Org.nr 556123-4567
2026-11-21 17:42  Kassa 2
Bröd Varsågod Skivad        27,90
Fast Potatis 2kg           24,95
Körsbärstomater 250g         21,90
Ägg 12p Frigående          42,90
Koriander                 15,90
Tonfisk i vatten            14,50
2 st x 14,50            29,00
Gul lök 1kg               14,90
Lösgodis                 19,90
Rabatt                   -5,00
Totalt                  197,45
Kort                    197,45
Moms 129                21,15
Tack för besöket!"""


def basket(store_name="Willys Lund", store_id="context:willys:1"):
    def item(name, ingredient, price, **extra):
        return {"product_name": name, "ingredient": f"{ingredient} [1]", "product_id": name, "chain": "willys",
                "unit_price": price, "total_price": price, "packages_needed": 1, **extra}
    return {"postal_code": "22350", "optimized_basket": {"stores": [{"store_id": store_id, "store_name": store_name, "items": [
        item("Bröd Varsågod Skivad", "bröd", 25.51), item("Fast potatis i påse", "potatis", 24.95),
        item("Körsbärstomater hela", "tomat", 19.90), item("Ägg 12p Frigående Inomhus", "ägg", 42.90),
        item("Tonfisk i vatten", "tonfisk", 14.50), item("Gul lök", "gul lök", 14.90)]}]}}


def test_the_receipt_text_becomes_lines():
    parsed = rewards.parse_receipt(OCR_TEXT)
    assert parsed["chain"] == "ica" and parsed["purchased_on"] == "2026-11-21"
    assert parsed["store_text"] == "ICA Nära Klostergården"
    names = [l["description"] for l in parsed["lines"]]
    assert names[:3] == ["Bröd Varsågod Skivad", "Fast Potatis 2kg", "Körsbärstomater 250g"]
    assert not any(n.lower().startswith(("totalt", "kort", "moms", "rabatt")) for n in names)
    tuna = next(l for l in parsed["lines"] if l["description"] == "Tonfisk i vatten")
    assert (tuna["quantity"], tuna["unit_price"], tuna["price"]) == (2, 14.5, 29.0)
    sweets = next(l for l in parsed["lines"] if l["description"] == "Lösgodis")
    assert sweets["price"] == 14.9  # the discount below it


def test_a_store_missing_from_smako_gives_extra_points():
    rules = PlanningRules()
    result = rewards.evaluate(rewards.parse_receipt(OCR_TEXT), basket(), rules, known_stores=[])
    assert not result["store_known"] and result["qualifies"]
    matched = [l for l in result["lines"] if l["item"]]
    assert {l["item"] for l in matched} >= {"Bröd Varsågod Skivad", "Fast potatis i påse", "Tonfisk i vatten", "Gul lök"}
    assert all(l["missing_in_smako"] and l["points"] == 5 for l in matched)
    assert not next(l for l in result["lines"] if l["description"] == "Lösgodis")["item"]
    assert result["points"] == 10 + 5 * len(matched)


def test_a_price_that_differs_at_the_planned_store_gives_two_points():
    text = OCR_TEXT.replace("ICA Nära Klostergården", "WILLYS LUND")
    result = rewards.evaluate(rewards.parse_receipt(text), basket(), PlanningRules(), known_stores=[])
    assert result["store_known"] and result["store"] == "Willys Lund"
    by_item = {l["item"]: l for l in result["lines"] if l["item"]}
    assert by_item["Bröd Varsågod Skivad"]["price_differs"] and by_item["Bröd Varsågod Skivad"]["points"] == 2
    assert not by_item["Fast potatis i påse"]["price_differs"] and by_item["Fast potatis i påse"]["points"] == 0
    assert by_item["Tonfisk i vatten"]["points"] == 0  # 2 x 14,50 as planned per package
    assert result["points"] == 10 + 2 * sum(l["price_differs"] for l in by_item.values())


def test_too_few_list_items_give_no_points():
    parsed = {"store_text": "Pressbyrån", "lines": [{"description": "Kaffe", "price": 30.0}], "purchased_on": None}
    result = rewards.evaluate(parsed, basket(), PlanningRules(), known_stores=[])
    assert not result["qualifies"] and result["points"] == 0


@pytest.fixture
def app(tmp_path, monkeypatch):
    settings = Settings(price_provider="mock", plan_store_path=tmp_path / "plans.sqlite", public_base_url="https://smako.test")
    for module in (account, personal, plan, member):
        monkeypatch.setattr(module, "get_settings", lambda: settings)
    monkeypatch.setenv("PLAN_STORE_PATH", str(tmp_path / "plans.sqlite"))
    for key in account.ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    application = FastAPI()
    application.state.plan_store = PlanStore(settings.plan_store_path)
    account.install_account(application)
    application.include_router(member.router)

    @application.middleware("http")
    async def guest_session(request, call_next):
        guest = request.cookies.get("test_guest") or secrets.token_hex(16)
        request.state.anonymous_session_id = guest
        response = await call_next(request)
        response.set_cookie("test_guest", guest)
        return response

    return application


def browser(app, email):
    client = TestClient(app, base_url="https://smako.test")
    assert client.post("/api/account/register", json={"email": email, "password": PASSWORD}).status_code == 201
    return client


def own_plan(app, client, plan_id="plan-1"):
    store = app.state.plan_store
    from app.services.member_accounts import COOKIE, MemberAccounts

    owner = MemberAccounts(store).owner(client.cookies.get(COOKIE))
    with store._connect() as db:
        db.execute("""INSERT INTO consumer_plan_revisions (plan_id, revision, created_at, operation, request_json,
                      response_json, diversity_mode, diet_preference, max_stores, meal_count, servings, owner_actor_hash)
                      VALUES (?, 1, '2026-11-22T10:00:00+00:00', 'created', '{}', ?, 'balanced', 'mixed', 2, 5, 4, ?)""",
                   (plan_id, json.dumps(basket()), owner))
    return owner


def test_members_rate_dishes_and_everyone_sees_the_counts(app):
    guest = TestClient(app, base_url="https://smako.test")
    assert guest.put("/api/member/recipe-ratings/arakas", json={"value": 1}).status_code == 401
    first, second = browser(app, "a@example.test"), browser(app, "b@example.test")
    assert first.put("/api/member/recipe-ratings/arakas", json={"value": 1}).json()["ratings"]["arakas"]["mine"] == 1
    second.put("/api/member/recipe-ratings/arakas", json={"value": -1})
    second.put("/api/member/recipe-ratings/croquetas", json={"value": 1})
    seen = guest.get("/api/member/recipe-ratings?ids=arakas,croquetas,unknown").json()["ratings"]
    assert seen["arakas"] == {"likes": 1, "dislikes": 1, "mine": 0} and seen["croquetas"]["likes"] == 1
    first.put("/api/member/recipe-ratings/arakas", json={"value": 0})
    assert guest.get("/api/member/recipe-ratings?ids=arakas").json()["ratings"]["arakas"]["likes"] == 0
    assert first.put("/api/member/recipe-ratings/arakas", json={"value": 1},
                     headers={"Origin": "https://evil.test"}).status_code == 403
    liked, disliked = rewards.member_choices(app.state.plan_store, own_plan(app, second, "p-b"))
    assert liked == ["croquetas"] and disliked == ["arakas"]


def test_a_receipt_gives_points_once(app):
    client = browser(app, "c@example.test")
    own_plan(app, client)
    preview = client.post("/api/member/receipts/preview", json={"plan_id": "plan-1", "text": OCR_TEXT}).json()
    assert preview["qualifies"] and preview["points"] > 10
    lines = [{k: l[k] for k in ("description", "price") } for l in preview["lines"]]
    body = {"plan_id": "plan-1", "store_text": preview["store_text"], "purchased_on": preview["purchased_on"], "lines": lines}
    done = client.post("/api/member/receipts", json=body)
    assert done.status_code == 201 and done.json()["balance"] == preview["points"]
    again = client.post("/api/member/receipts", json=body)
    assert again.status_code == 422 and "redan" in again.json()["detail"]
    assert client.get("/api/member/points").json()["balance"] == preview["points"]
    other = browser(app, "d@example.test")
    assert other.post("/api/member/receipts/preview", json={"plan_id": "plan-1", "text": OCR_TEXT}).status_code == 422


def test_the_member_choices_reach_a_new_plan(app):
    from app.models.plan import PlanRequest
    from app.models.personal import MealSettings, PersonalPlanning
    from app.services.plan_variation import apply_variation

    client = browser(app, "e@example.test")
    client.put("/api/member/recipe-ratings/liked-dish", json={"value": 1})
    client.put("/api/member/recipe-ratings/disliked-dish", json={"value": -1})
    owner = own_plan(app, client, "p-e")
    request = PlanRequest(recipes=2, servings=2, personal=PersonalPlanning(meals=[MealSettings(count=2, servings=2)]))
    bound = apply_variation(request, store=app.state.plan_store, owner=owner, state={}, member=True)
    assert bound.personal.liked_recipes == ["liked-dish"] and bound.personal.disliked_recipes == ["disliked-dish"]
    guest = apply_variation(request, store=app.state.plan_store, owner=owner, state={}, member=False)
    assert not guest.personal.disliked_recipes
