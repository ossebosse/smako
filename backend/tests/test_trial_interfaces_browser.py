"""Both trial interfaces in a real browser against a small stand-in for the API.

Covers what the interfaces themselves do: the pantry (with the form recipes
need), the meat choice, registering a purchase, the account, and an item that
is not food. Planning and prices are covered by the server tests.
Set SMAKO_UI_SHOTS to a directory to keep screenshots.
"""
import json
import os
import re
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest
from playwright.sync_api import expect, sync_playwright

STATIC = Path(__file__).resolve().parents[1] / "app/static"
GUEST = {"status": "SIGN_IN_AVAILABLE", "membership": "guest", "message": "Du är gäst.", "guest_limits": {"recipes": 3, "servings": 2},
         "registration_available": True, "oidc_available": False}
MEMBER = {**GUEST, "status": "SIGNED_IN", "membership": "member", "message": "Du är medlem."}


class Fake:
    """One browser's server side: a guest owner and an account owner, as the real API keeps them."""

    def __init__(self):
        self.owner = "guest"
        self.states = {name: {"revision": 0, "items": [], "shopping_items": [], "ledger": []} for name in ("guest", "account")}
        self.calls = []

    @property
    def state(self):
        return self.states[self.owner]

    def public(self):
        s = self.state
        return {"revision": s["revision"], "profile": None, "items": [{**i, "available": i["quantity"], "reserved": 0} for i in s["items"]],
                "reservations": {}, "events": {}, "ledger": s["ledger"], "shopping_items": s["shopping_items"], "shopping_common": [],
                "shopping_initialized": True, "account": MEMBER if self.owner == "account" else GUEST, "pantry_checks": []}

    def plan(self, request, revision=1):
        rice = next((i for i in self.state["items"] if i["name"] == "ris" and i.get("form") == "dry"), None)
        rows = [{"store_id": "s1", "product_id": "p-fars", "ingredient": "nötfärs", "product_name": "Nötfärs 12%", "packages_needed": 1, "package_quantity": 500, "package_unit": "g",
                 "total_price": 59.9, "unit": "g", "purchased_unit": "g", "required_quantity": 400, "purchased_usable_quantity": 500, "quantity_confidence": "exact", "food_family": "meat"},
                {"store_id": "s1", "product_id": "p-lok", "ingredient": "gul lök", "product_name": "Gul lök lösvikt", "packages_needed": 1, "package_quantity": 1000, "package_unit": "g",
                 "total_price": 3.5, "unit": "g", "purchased_unit": "g", "required_quantity": 150, "purchased_usable_quantity": 180, "purchased_quantity": 180,
                 "quantity_confidence": "estimated", "sale_model": "sold_by_weight", "food_family": "allium"}]
        recipe = {"name": "Köttfärssås med ris", "servings": 2, "instructions": ["Stek färsen.", "Koka riset."],
                  "ingredients": [{"name": "nötfärs", "quantity": 400, "unit": "g"}, {"name": "gul lök", "quantity": 150, "unit": "g"}, {"name": "ris", "quantity": 200, "unit": "g"}]}
        return {"plan_id": "plan-1", "revision": revision, "request": request,
                "plan": {"personal": {"slots": [{"id": "dinner-1", "day": 1, "meal_type": "dinner", "recipe": recipe}], "checks": {},
                                      "needs": [{"key": "nötfärs"}, {"key": "gul lök"}],
                                      "allocations": [{"name": "ris", "quantity": 200, "unit": "g"}] if rice else []},
                         "optimized_basket": {"total": 63.4, "store_count": 1, "verification_status": "VERIFIED_WITH_ESTIMATES",
                                              "stores": [{"store_id": "s1", "store_name": "Testbutiken Lund", "subtotal": 63.4, "items": rows}]}}}

    def answer(self, method, path, query, body):
        self.calls.append((method, path, body))
        s = self.state
        if path == "personal/state":
            return 200, self.public()
        if path == "shopping-location":
            return 200, {"status": "eligible", "postal_code": "22350", "area_postal_code": "22350", "municipality_name": "Lund", "area_name": "Lund",
                         "contexts": [{"context_id": "s1", "display_name": "Testbutiken Lund", "address": "Storgatan 1", "distance_km": 1.2}]}
        if path == "personal/interpret-extra":
            match = re.fullmatch(r"(.+?)\s+(\d+)\s*(kg|g|st|l)", body["text"].strip())
            if not match:
                return 200, {"query": body["text"].strip(), "properties": [], "food": "tandborste" not in body["text"], "confirmed": False}
            factor, unit = {"kg": (1000, "g"), "g": (1, "g"), "st": (1, "st"), "l": (1000, "ml")}[match[3]]
            return 200, {"query": match[1], "quantity": int(match[2]) * factor, "unit": unit, "properties": [], "food": "tandborste" not in match[1], "confirmed": False}
        if path == "personal/shopping-suggestions":
            return 200, {"generics": [], "products": [], "usual": None, "status": "available"}
        if path == "personal/pantry-use":
            return 200, {"form": "dry", "unit": "g", "used_in_recipes": True, "food": True} if query.get("name") == "ris" else {"form": None, "unit": None, "used_in_recipes": False, "food": True}
        if path in {"personal/pantry", "personal/shopping-list"}:
            if body["revision"] != s["revision"]:
                return 409, {"detail": "Ändrat på annat håll."}
            s["items" if path.endswith("pantry") else "shopping_items"] = body["items"]
            s["revision"] += 1
            return 200, self.public()
        if path == "plans":
            return 200, self.plan(body)
        if path == "personal/plans/plan-1/change":
            if body["action"] == "purchase":
                if "s1|p-lok|gul lök" not in body.get("measured_purchase_quantities", {}):
                    return 409, {"detail": "Ange verklig användbar inköpsmängd som täcker behovet; annars räkna om planen."}
                s["items"] += [{"id": "bought-1", "name": "nötfärs", "quantity": 500, "unit": "g", "product_key": "a" * 32, "unusable": False, "food": True},
                               {"id": "bought-2", "name": "gul lök", "quantity": body["measured_purchase_quantities"]["s1|p-lok|gul lök"], "unit": "g", "product_key": "b" * 32, "unusable": False, "food": True}]
            if body["action"] == "consume":
                s["items"] = [i for i in s["items"] if not i["id"].startswith("bought")]
            s["ledger"].append({"plan_id": "plan-1", "revision": body["revision"], "action": body["action"], "operation_id": f"{body['action']}:{body['revision']}", "rows": []})
            s["revision"] += 1
            request = next(c[2] for c in self.calls if c[1] == "plans")
            return 200, {"saved": self.plan(request, body["revision"]), "state": self.public()}
        if path == "account/register":
            if len(body["password"]) < 12:
                return 422, {"detail": "Lösenordet ska vara mellan 12 och 128 tecken."}
            self.owner = "account"
            return 201, {"status": "SIGNED_IN", "recovery_code": "KOD-1234-5678"}
        if path == "account/login":
            self.owner = "account"
            return 200, {"status": "SIGNED_IN"}
        if path == "account/logout":
            self.owner = "guest"
            return 200, {"status": "SIGNED_OUT"}
        if path == "account/guest-migration-preview":
            guest, mine = self.states["guest"], self.states["account"]
            return 200, {"guest_revision": guest["revision"], "account_revision": mine["revision"], "guest_items": len(guest["items"]),
                         "guest_profile": False, "can_move": bool(guest["revision"] and not mine["revision"])}
        if path == "account/migrate-guest":
            self.states["account"] = {**self.states["guest"], "revision": self.states["guest"]["revision"] + 1}
            self.states["guest"] = {"revision": 0, "items": [], "shopping_items": [], "ledger": []}
            return 200, {"status": "MOVED"}
        return 404, {"detail": f"Saknas i teststödet: {path}"}


@pytest.fixture(params=["a", "b"])
def ui(request):
    class Handler(SimpleHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            self.path = re.sub(r"^/ui/([ab]).*", r"/next/\1.html", self.path).replace("/static/", "/")
            return super().do_GET()

    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Handler, directory=str(STATIC)))
    Thread(target=server.serve_forever, daemon=True).start()
    fake, errors = Fake(), []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 390, "height": 844})
        page.on("pageerror", lambda error: errors.append(str(error)))

        def api(route):
            url = route.request.url.split("/api/")[-1]
            path, _, raw = url.partition("?")
            query = dict(part.split("=", 1) for part in raw.split("&") if "=" in part)
            status, data = fake.answer(route.request.method, path, {k: v.replace("%20", " ") for k, v in query.items()}, route.request.post_data_json if route.request.post_data else None)
            route.fulfill(status=status, content_type="application/json", body=json.dumps(data))

        page.route("**/api/**", api)
        page.goto(f"http://127.0.0.1:{server.server_port}/ui/{request.param}")
        shots = os.environ.get("SMAKO_UI_SHOTS")

        def shot(name):
            if shots:
                page.screenshot(path=str(Path(shots) / f"{request.param}-{name}.png"), full_page=True)

        yield request.param, page, fake, shot
        browser.close()
    server.shutdown()
    assert not errors


def open_screen(name, page, screen):
    """The pantry and the account are a tab or a top link in A and buttons on the first screen in B."""
    if name == "a":
        page.goto(re.sub(r"#.*|$", f"#{screen}", page.url, count=1))
    else:
        page.locator("a.brand").click()
        page.get_by_role("button", name=re.compile("Skafferi" if screen == "skafferi" else "konto", re.IGNORECASE)).click()


def add_rice(name, page):
    open_screen(name, page, "skafferi")
    expect(page.get_by_role("heading", name="Skafferi", level=1)).to_be_visible()
    page.get_by_label("Lägg till i skafferiet").fill("ris 1 kg")
    page.get_by_role("button", name=re.compile("Ris · 1 kg")).click()
    # The form recipes use for rice is proposed and can be changed before saving.
    expect(page.get_by_role("radio", name=re.compile("^Torr"))).to_have_attribute("aria-checked", "true")
    page.get_by_role("button", name="Lägg i skafferiet", exact=True).click()
    expect(page.locator(".pantry .item-name")).to_have_text("Ris")


def plan_meat_dinners(name, page):
    if name == "a":
        page.goto(re.sub(r"#.*", "#mat", page.url))
        page.get_by_label("Ditt postnummer").fill("22350")
        page.get_by_role("button", name="Hitta butiker").click()
        page.get_by_role("radio", name=re.compile("^Kött")).click()
        page.get_by_role("button", name="Skapa matplan").click()
        expect(page.get_by_role("heading", name="Din matplan", exact=True)).to_be_visible()
        page.goto(re.sub(r"#.*", "#handla", page.url))
    else:
        page.locator("a.brand").click()
        page.get_by_role("button", name=re.compile("Planera mat och handla")).click()
        page.get_by_label("Ditt postnummer").fill("22350")
        page.get_by_role("button", name="Hitta butiker").click()
        page.get_by_role("button", name="Nästa").click()
        page.get_by_role("button", name="Nästa").click()
        page.get_by_role("radio", name=re.compile("^Kött")).click()
        expect(page.get_by_text("Skafferiet: 1 vara hemma används först.")).to_be_visible()
        page.get_by_role("button", name="Nästa").click()
        page.get_by_role("button", name="Skapa matplan").click()
        expect(page.get_by_role("heading", name="Veckans recept", exact=True)).to_be_visible()
        page.get_by_role("button", name="Visa handlingslistan").click()
    expect(page.get_by_role("heading", name="Handla", level=1)).to_be_visible()


def test_pantry_meat_choice_and_registered_purchase(ui):
    name, page, fake, shot = ui
    add_rice(name, page)
    shot("skafferi")
    saved = next(body for method, path, body in fake.calls if path == "personal/pantry")
    assert [(i["name"], i["quantity"], i["unit"], i["form"], i["product_key"]) for i in saved["items"]] == [("ris", 1000, "g", "dry", None)]

    plan_meat_dinners(name, page)
    sent = next(body for method, path, body in fake.calls if path == "plans")
    assert [m["diet"] for m in sent["personal"]["meals"]] == ["meat", "mixed", "mixed"]
    assert sent["personal"]["use_pantry"] is True and sent["personal"]["pantry_revision"] == fake.states["guest"]["revision"]
    expect(page.get_by_text("Från skafferiet, behöver inte köpas: ris 200 g.")).to_be_visible()
    shot("handla")

    page.get_by_role("button", name="Jag har handlat").click()
    weighed = page.get_by_role("spinbutton", name=re.compile("Gul lök lösvikt"))
    expect(weighed).to_have_value("180")
    weighed.fill("210")
    shot("matt")
    page.get_by_role("button", name="Spara i skafferiet").click()
    expect(page.get_by_text("Inköpet ligger i skafferiet.")).to_be_visible()
    bought = next(body for method, path, body in fake.calls if path.endswith("/change"))
    assert bought["action"] == "purchase" and bought["measured_purchase_quantities"] == {"s1|p-lok|gul lök": 210}
    page.get_by_role("button", name="Öppna skafferiet").click()
    expect(page.locator(".pantry .item-name")).to_have_text(["Ris", "Nötfärs", "Gul lök"])
    expect(page.locator(".pantry .item-kind").nth(1)).to_have_text("Bestämd vara")


def test_account_is_created_and_left_inside_the_interface(ui):
    name, page, fake, shot = ui
    add_rice(name, page)
    open_screen(name, page, "konto")
    expect(page.get_by_role("heading", name="Logga in")).to_be_visible()
    shot("konto")
    page.get_by_role("button", name="Skapa ett konto").click()
    page.get_by_label("E-postadress").fill("test@example.com")
    page.get_by_label(re.compile("Lösenord")).fill("ett-langt-losenord")
    page.get_by_role("button", name="Skapa konto", exact=True).click()
    expect(page.get_by_label("Din återställningskod")).to_have_value("KOD-1234-5678")
    page.get_by_role("button", name="Jag har sparat koden").click()
    # The guest's pantry is offered to the new account, never moved without asking.
    expect(page.get_by_role("heading", name="Ta med det du gjorde som gäst?")).to_be_visible()
    assert not any(path == "account/migrate-guest" for _, path, _ in fake.calls)
    page.get_by_role("button", name="Ja, flytta till kontot").click()
    expect(page.get_by_role("heading", name="Du är inloggad")).to_be_visible()
    expect(page.get_by_role("button", name="Öppna skafferiet (1 vara)")).to_be_visible()
    if name == "a":
        expect(page.locator("#account")).to_have_text("Konto")
    shot("inloggad")
    page.get_by_role("button", name="Logga ut").click()
    expect(page.get_by_role("heading", name="Logga in")).to_be_visible()
    assert fake.owner == "guest"
    assert "finns i vanliga Smako" not in page.content()


def test_toothbrush_is_saved_as_not_food_the_way_the_server_sees_it(ui):
    name, page, fake, _shot = ui
    if name == "a":
        page.goto(re.sub(r"#.*|$", "#lista", page.url, count=1))
    else:
        page.get_by_role("button", name=re.compile("Bara handla")).click()
        page.get_by_label("Ditt postnummer").fill("22350")
        page.get_by_role("button", name="Hitta butiker").click()
        page.get_by_role("button", name="Nästa").click()
    page.get_by_label("Lägg till vara").fill("tandborste 1 st")
    page.get_by_role("button", name=re.compile("Tandborste · 1 st")).click()
    expect(page.locator(".item-name").first).to_have_text("Tandborste")
    saved = next(body for method, path, body in fake.calls if path == "personal/shopping-list")
    assert [(i["query"], i["food"]) for i in saved["items"]] == [("tandborste", False)]
