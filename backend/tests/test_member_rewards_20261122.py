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


KNOWN = [{"store_id": "context:hemkop:1", "name": "Hemköp Lund Karhögstorg", "chain": "hemkop"},
         {"store_id": "context:hemkop:2", "name": "Hemköp Lund Karhögstorg", "chain": "hemkop"},
         {"store_id": "context:willys:1", "name": "Willys Lund", "chain": "willys"}]
CATALOGUE = rewards.StoreProducts([
    {"name": "Kvarg Naturell 0,2% 900g", "brand": "Arla", "price": 31.95},
    {"name": "Ägg 18p Frigående Utomhus", "brand": "Garant", "price": 59.95},
    {"name": "Ägg 18p Frigående Inomhus", "brand": "Garant", "price": 49.95},
    {"name": "Kesella kvarg naturell", "brand": "Arla", "price": 12.95, "sizes": {"g": 500}},
    {"name": "Minutkyckling", "brand": "Kronfågel", "price": 69.95},
    {"name": "Bakpulver Eko", "brand": "Garant Eko", "price": 12.0, "gtin": "7340011400000"},
    {"name": "Ägg 6p Frigående Large Eko", "brand": "Garant Eko", "price": 29.95},
])
# Owner's receipt 2026-11-22 (Hemköp Karhögstorg), as the phone read it.
HEMKOP = {"store_text": "HEMKÖP KARHÖGSTORG", "purchased_on": None, "lines": [
    {"description": "KVARG 900G NAT 0,2%", "price": 31.95}, {"description": "ÄGG 18P UTE", "price": 61.57},
    {"description": "MINUTFILÉ", "price": 69.95}, {"description": "BAKPULVER EKO", "price": 12.0},
    {"description": "VISPGRÄDDE 40%", "price": 10.98}, {"description": "SMÅBLADSMIX EKO", "price": 20.95}]}


def test_items_need_not_be_on_the_list_and_score_by_smako_prices():
    """Owner decision 2026-11-22: missing in Smako +5, another price +2, same price 0."""
    result = rewards.evaluate(HEMKOP, basket(), PlanningRules(), KNOWN, store_products=lambda _: CATALOGUE)
    assert result["store_known"] and result["store"] == "Hemköp Lund Karhögstorg" and result["qualifies"]
    by = {l["description"]: l for l in result["lines"]}
    assert by["KVARG 900G NAT 0,2%"]["smako_product"].startswith("Kvarg") and by["KVARG 900G NAT 0,2%"]["points"] == 0
    assert by["ÄGG 18P UTE"]["price_differs"] and by["ÄGG 18P UTE"]["points"] == 2
    assert by["BAKPULVER EKO"]["smako_product"] == "Bakpulver Eko"  # never the eggs because of "eko"
    for name in ("MINUTFILÉ", "VISPGRÄDDE 40%", "SMÅBLADSMIX EKO"):
        assert by[name]["missing_in_smako"] and by[name]["points"] == 5
    assert result["points"] == 10 + 2 + 3 * 5


def test_a_store_missing_from_smako_gives_extra_points_for_every_item():
    result = rewards.evaluate(rewards.parse_receipt(OCR_TEXT), basket(), PlanningRules(), KNOWN)
    assert not result["store_known"] and result["qualifies"]
    assert all(l["missing_in_smako"] and l["points"] == 5 for l in result["lines"])
    assert result["points"] == min(100, 10 + 5 * len(result["lines"]))
    assert {l["item"] for l in result["lines"] if l["item"]} >= {"Bröd Varsågod Skivad", "Tonfisk i vatten"}


def test_points_have_a_ceiling_and_too_few_lines_give_none():
    rules = PlanningRules(receipt_max_points=20)
    assert rewards.evaluate(rewards.parse_receipt(OCR_TEXT), basket(), rules, [])["points"] == 20
    parsed = {"store_text": "Pressbyrån", "lines": [{"description": "Kaffe", "price": 30.0}], "purchased_on": None}
    result = rewards.evaluate(parsed, basket(), PlanningRules(), [])
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


# Owner's second Hemköp receipt (2026-11-17), as saved, and Smako's products
# in the store on 2026-11-22. All three "other prices" were Smako's own club
# prices or a second size; the comparison, not the data, was wrong.
def _product(name, brand, price, size, offers=()):
    return {"name": name, "brand": brand, "price": price, "effective_price": price, "member_price": None,
            "sizes": rewards.sizes(size), "offer_prices": rewards.offer_prices(list(offers))}


HEMKOP_STORE = rewards.StoreProducts([
    _product("Minutfilé", "Kronfågel", 89.0, "600 g", [{"price": 69.95, "description": "Klubbpris"}]),
    _product("Jordnötssmör Creamy Ekologiskt", "Garant Eko", 36.86, "350 g", [{"price": 28.0, "description": "Klubbpris"}]),
    _product("Småbladsmix Ruccola Röd/grön Klass 1", "Garant Eko", 31.95, "175 g"),
    _product("Småbladsmix Ruccola Röd/grön Klass 1", "Garant Eko", 20.95, "65 g"),
    _product("Ryggfilé Alaska Pollock", "Royal Foods", 64.3, "300 g", [{"price": 39.95, "description": "Klubbpris"}]),
    _product("Barista Havredryck 3%", "Garant", 18.45, "1000 ml", [{"price": 32.0, "description": "2 för"}]),
    _product("Bearnaise Lätt Crème Fraiche 10%", "Arla Köket", 18.82, "200 ml"),
    _product("Björnbär Hallon Lättdryck", "Bob", 8.99, "200 ml", [{"price": 28.0, "description": "4 för"}]),
    _product("Gurka med Dill", "Krakus", 31.18, "450 g"),
    _product("Gurka Eko Klass 1", None, 20.95, "300 g"),
    _product("Grönkål Eko", "Garant Eko", 25.0, "200 g"),
    _product("Zucchini Klass 1", None, 13.95, "1 st"),
    _product("Rice Papper 22 Cm", "Exotic", 20.0, "100 g"),
])
SECOND = {"store_text": "HEMKÖP KARHÖGSTORG", "purchased_on": "2026-11-17", "lines": [
    {"description": "MINUTFILÉ", "price": 69.95},
    {"description": "RYGGFILE ALASK POLL", "price": 119.85, "quantity": 3.0, "unit": "st", "unit_price": 64.3},
    {"description": "HAVREDRYCK BARISTA", "price": 32.0, "quantity": 2.0, "unit": "st", "unit_price": 18.45},
    {"description": "LÄTT CREM FR BEA 10%", "price": 28.0, "quantity": 2.0, "unit": "st", "unit_price": 18.82},
    {"description": "BJÖRNBÄR 125G", "price": 10.0, "quantity": 2.0, "unit": "st", "unit_price": 5.0},
    {"description": "GURKA EKO ST", "price": 20.95},
    {"description": "ZUCCHINI GRÖN", "price": 8.35, "quantity": 0.226, "unit": "kg", "unit_price": 36.95},
    {"description": "JORDNÖTSSMÖR CRE EKO", "price": 28.0},
    {"description": "SMÅBLADSMIX EKO", "price": 20.95}]}


def test_club_prices_multibuys_and_sizes_are_smakos_prices_too():
    result = rewards.evaluate(SECOND, {}, PlanningRules(), KNOWN, store_products=lambda _: HEMKOP_STORE)
    by = {l["description"]: l for l in result["lines"]}
    for name in ("MINUTFILÉ", "JORDNÖTSSMÖR CRE EKO", "SMÅBLADSMIX EKO", "RYGGFILE ALASK POLL", "HAVREDRYCK BARISTA"):
        assert by[name]["smako_product"] and not by[name]["price_differs"] and by[name]["points"] == 0, name
    assert by["GURKA EKO ST"]["smako_product"] == "Gurka Eko Klass 1" and by["GURKA EKO ST"]["points"] == 0
    # "2 för 28" that Smako does not know: a real other price.
    assert by["LÄTT CREM FR BEA 10%"]["price_differs"] and by["LÄTT CREM FR BEA 10%"]["planned_price"] == 18.82
    # Fresh blackberries are not the drink; zucchini is not kale.
    assert by["BJÖRNBÄR 125G"]["missing_in_smako"] and by["BJÖRNBÄR 125G"]["points"] == 5
    assert by["ZUCCHINI GRÖN"]["smako_product"] == "Zucchini Klass 1" and not by["ZUCCHINI GRÖN"]["missing_in_smako"]


def test_carrier_bags_and_deposits_are_not_items():
    parsed = rewards.parse_receipt("HEMKÖP KARHÖGSTORG\nMJÖLK 3% 1L   17,95\nPAPPERSKASSE   4,00\nPANT   2,00\nTotalt 23,95")
    assert [l["description"] for l in parsed["lines"]] == ["MJÖLK 3% 1L"]


# Owner's third Hemköp receipt (2026-11-22) and Smako's products in the store.
THIRD_STORE = rewards.StoreProducts([
    _product("Tomatketchup", "Heinz", 28.34, "570 g"), _product("Tomatketchup", "Heinz", 34.97, "1000 g"),
    _product("Tomatketchup -50%", "Heinz", 37.41, "960 g"),
    _product("Baby Dry 5 11-17+kg Byxblöjor", "Pampers", 119.0, "37 st", [{"price": 89.95, "description": "Klubbpris"}]),
    _product("Päronsplitt Flerpack Glass", "Gb Glace", 51.05, "10 st"),
    _product("Päron Kl 1", None, 34.95, "1 kg"),
    _product("Bakpotatis Klass 1", None, 12.25, "375 g", [{"price": 10.0, "description": "MixMatchPricePromotion"}]),
    _product("Potatissallad", "Garant", 24.95, "500 g"),
    _product("Potatis Fast Eko Klass 2", "Garant", 17.95, "900 g"),
    _product("Ägg 18p Frigående Utomhus Medium/large", "Garant", 61.57, "18 st"),
])
THIRD_TEXT = """HEMKÖP KARHÖGSTORG
2026-11-22
HEINZ KETCHUP 700G        37,80
PÄRONSPLIT                 7,80
4 st x 1,95
ÄGG 18P UTE               61,57
1,015kg x 24,45kr/kg      24,82
POTATIS FAST EKO          24,82
POTATIS BAK               61,25
5 st x 12,25
5 för 50                 -11,25
BABYDRY S6 13-19+KG      238,00
2 st x 119,00
Klubbpris                -58,10
PAPPERSKASSE               4,00
Totalt                   429,52"""


def test_quantity_lines_go_to_the_item_whose_price_they_explain():
    lines = {l["description"]: l for l in rewards.parse_receipt(THIRD_TEXT)["lines"]}
    assert lines["ÄGG 18P UTE"]["price"] == 61.57 and "quantity" not in lines["ÄGG 18P UTE"]
    assert (lines["POTATIS FAST EKO"]["quantity"], lines["POTATIS FAST EKO"]["unit"]) == (1.015, "kg")
    assert lines["POTATIS BAK"]["price"] == 50.0 and lines["POTATIS BAK"]["quantity"] == 5
    assert lines["PÄRONSPLIT"]["quantity"] == 4 and "PAPPERSKASSE" not in lines


def test_the_third_receipt_scores_by_what_smako_really_lacks():
    parsed = rewards.parse_receipt(THIRD_TEXT)
    result = rewards.evaluate(parsed, {}, PlanningRules(), KNOWN, store_products=lambda _: THIRD_STORE)
    by = {l["description"]: l for l in result["lines"]}
    assert by["HEINZ KETCHUP 700G"]["missing_in_smako"]  # Smako has 570 g, 960 g and 1 kg
    assert by["BABYDRY S6 13-19+KG"]["missing_in_smako"]  # Smako has size 5 only
    assert by["POTATIS BAK"]["smako_product"] == "Bakpotatis Klass 1" and by["POTATIS BAK"]["points"] == 0  # 5 för 50
    assert by["PÄRONSPLIT"]["smako_product"] != "Päron Kl 1" and by["PÄRONSPLIT"]["points"] == 0  # single vs 10-pack
    assert by["ÄGG 18P UTE"]["points"] == 0 and not by["ÄGG 18P UTE"]["price_differs"]
