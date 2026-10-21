"""Real credential/session flows, owner isolation and planner admission boundaries."""

import secrets
from types import SimpleNamespace

import pytest
from app.api import account, personal, plan
from app.config import Settings
from app.models import PlanRequest
from app.models.personal import MealSettings, MealSlot, PersonalMutation, PersonalPlanning
from app.models.recipe import Recipe
from app.services.member_accounts import COOKIE, MemberAccounts, digest
from app.services.membership import require_membership_limits
from app.services.plan_store import PlanStore
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

PASSWORD = "a long test password 123"


@pytest.fixture
def membership(tmp_path, monkeypatch):
    settings = Settings(price_provider="mock", plan_store_path=tmp_path / "plans.sqlite", public_base_url="https://smako.test")
    for module in (account, personal, plan):
        monkeypatch.setattr(module, "get_settings", lambda: settings)
    for key in account.ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    app = FastAPI()
    app.state.plan_store = PlanStore(settings.plan_store_path)
    account.install_account(app)
    app.include_router(personal.router)
    app.include_router(plan.router)
    personal.install_handlers(app)

    @app.middleware("http")
    async def guest_session(request, call_next):
        guest = request.cookies.get("test_guest") or secrets.token_hex(16)
        request.state.anonymous_session_id = guest
        request.state.request_id = "membership-test"
        response = await call_next(request)
        response.set_cookie("test_guest", guest)
        return response

    return app


def client(app):
    return TestClient(app, base_url="https://smako.test")


def register(browser, email="member@example.test"):
    return browser.post("/api/account/register", json={"email": email, "password": PASSWORD})


def test_registration_pantry_migration_logout_login_and_account_isolation(membership):
    first, second, stranger = client(membership), client(membership), client(membership)
    guest = first.get("/api/personal/state").json()
    assert guest["account"]["membership"] == "guest"
    pantry = [{"id": "rice", "name": "ris", "quantity": 500, "unit": "g"}]
    assert first.put("/api/personal/pantry", json={"revision": 0, "items": pantry}).status_code == 200
    response = register(first, " Member@Example.Test ")
    assert response.status_code == 201
    assert response.json()["recovery_code"]
    cookie = response.headers["set-cookie"].lower()
    assert all(flag in cookie for flag in ("httponly", "secure", "samesite=lax"))
    assert response.headers["cache-control"] == "private, no-store"
    assert first.get("/api/personal/state").json()["items"] == []
    preview = first.get("/api/account/guest-migration-preview").json()
    assert preview["can_move"] and preview["guest_items"] == 1
    moved = first.post("/api/account/migrate-guest", json={
        "guest_revision": preview["guest_revision"], "account_revision": preview["account_revision"],
        "confirm_move_to_verified_account": True,
    })
    assert moved.status_code == 200
    assert second.post("/api/account/login", json={"email": "member@example.test", "password": PASSWORD}).status_code == 200
    assert second.get("/api/personal/state").json()["items"][0]["name"] == "ris"
    register(stranger, "another@example.test")
    assert stranger.get("/api/personal/state").json()["items"] == []
    token = first.cookies.get(COOKIE)
    first.post("/api/account/logout")
    assert first.get("/api/account/status").json()["membership"] == "guest"
    assert first.get("/api/personal/state").json()["items"] == []
    first.cookies.set(COOKIE, token)
    assert first.get("/api/account/status").json()["membership"] == "guest"
    assert second.get("/api/account/status").json()["membership"] == "member"
    # Stored credentials and session values are not plaintext.
    with membership.state.plan_store._connect() as db:
        row = db.execute("SELECT * FROM member_accounts WHERE email='member@example.test'").fetchone()
        assert PASSWORD not in row["password_hash"]
        assert response.json()["recovery_code"] != row["recovery_hash"]
        assert not db.execute("SELECT 1 FROM member_sessions WHERE token_hash=?", (token,)).fetchone()


def test_wrong_credentials_csrf_duplicates_recovery_and_expiry(membership):
    browser = client(membership)
    code = register(browser).json()["recovery_code"]
    assert register(browser).status_code == 409
    assert browser.post("/api/account/login", json={"email": "member@example.test", "password": "wrong but long enough"}).status_code == 401
    assert browser.post("/api/account/logout", headers={"Origin": "https://evil.test"}).status_code == 403
    assert browser.post("/api/account/register", headers={"Origin": "https://evil.test"}, json={"email": "csrf@example.test", "password": PASSWORD}).status_code == 403
    assert register(client(membership), "invalid").status_code == 422
    reset = browser.post("/api/account/recover", json={"email": "member@example.test", "password": "replacement password 456", "recovery_code": code})
    assert reset.status_code == 200 and reset.json()["recovery_code"] != code
    assert browser.get("/api/account/status").json()["membership"] == "guest"
    assert browser.post("/api/account/recover", json={"email": "member@example.test", "password": PASSWORD, "recovery_code": code}).status_code == 401
    assert browser.post("/api/account/login", json={"email": "member@example.test", "password": "replacement password 456"}).status_code == 200
    with membership.state.plan_store._connect() as db:
        db.execute("UPDATE member_sessions SET expires_at=0")
    assert browser.get("/api/account/status").json()["membership"] == "guest"


def test_persistent_throttle_and_no_secret_validation_echo(membership):
    browser = client(membership)
    for _ in range(12):
        response = browser.post("/api/account/login", json={"email": "missing@example.test", "password": PASSWORD})
        assert response.status_code == 401
    response = client(membership).post("/api/account/login", json={"email": "missing@example.test", "password": PASSWORD})
    assert response.status_code == 429 and response.headers["retry-after"] == "900"
    assert PASSWORD not in response.text
    response = browser.post("/api/account/register", json={"email": "x@example.test", "password": "secret"})
    assert response.status_code == 422 and "secret" not in response.text
    response = browser.post("/api/account/register", json=[{"password": PASSWORD}])
    assert response.status_code == 422 and PASSWORD not in response.text


@pytest.mark.parametrize("path", ["/api/plan", "/api/plans"])
@pytest.mark.parametrize("recipes,servings", [(4, 2), (3, 3), (7, 8)])
def test_guest_limits_before_planning_or_async_admission(membership, path, recipes, servings):
    response = client(membership).post(path, json={"recipes": recipes, "servings": servings}, headers={"Prefer": "respond-async"})
    assert response.status_code == 403
    assert response.headers["x-error-code"] == "membership_required"
    assert not hasattr(membership.state, "plan_jobs")


def test_combined_counts_supplied_recipe_portions_and_member_entitlement(membership):
    guest_request = SimpleNamespace(cookies={}, scope={})
    allowed = PlanRequest(personal=PersonalPlanning(meals=[MealSettings(count=3, servings=2)]))
    require_membership_limits(allowed, guest_request)
    require_membership_limits(PlanRequest(recipes=3, servings=2), guest_request)
    require_membership_limits(PlanRequest(personal=PersonalPlanning()), guest_request)
    combined = allowed.model_copy(deep=True)
    combined.personal.meals.append(MealSettings(meal_type="breakfast", count=1, servings=1))
    with pytest.raises(HTTPException):
        require_membership_limits(combined, guest_request)
    response = client(membership).post("/api/plans", json=combined.model_dump(mode="json"))
    assert response.status_code == 403
    # Client grocery memberships confer no Smako entitlement.
    assert client(membership).post("/api/plans", json={"recipes": 5, "servings": 4, "memberships": {"coop": True}}).status_code == 403
    browser = client(membership)
    register(browser)
    store = MemberAccounts(membership.state.plan_store)
    member_request = SimpleNamespace(cookies={}, scope={"session": {"account_owner": store.owner(browser.cookies.get(COOKIE))}})
    require_membership_limits(combined, member_request)
    saved = SimpleNamespace(request=allowed, plan=SimpleNamespace(personal=SimpleNamespace(slots=[])))
    with pytest.raises(HTTPException):
        personal._check_membership_change(saved, PersonalMutation(revision=1, pantry_revision=0, action="add_recipe"), guest_request, None, None)


def test_custom_recipe_portions_cannot_bypass_meal_portion_limit(membership):
    recipe = Recipe(name="Ris", servings=3,
                    ingredients=[{"name": "ris", "quantity": 100, "unit": "g"}],
                    instructions=["Koka riset."])
    spec = PersonalPlanning(meals=[MealSettings(count=1, servings=2)], slots=[
        MealSlot(id="dinner-1", day=1, meal_type="dinner", recipe=recipe),
    ])
    browser = client(membership)
    assert browser.post("/api/plans", json={"personal": spec.model_dump()}).status_code == 403
    guest = SimpleNamespace(cookies={}, scope={})
    saved = SimpleNamespace(request=PlanRequest(personal=spec),
                            plan=SimpleNamespace(personal=SimpleNamespace(slots=spec.slots)))
    with pytest.raises(HTTPException) as caught:
        personal._check_membership_change(saved, PersonalMutation(
            revision=1, pantry_revision=0, action="edit", slot_id="dinner-1", recipe=recipe,
        ), guest, None, None)
    assert caught.value.headers["X-Error-Code"] == "membership_required"


@pytest.mark.parametrize("path", ["/api/plan", "/api/plans"])
def test_guests_at_boundary_and_signed_in_members_reach_planner(membership, monkeypatch, path):
    async def reached(*args):
        raise HTTPException(418, "planner reached")

    monkeypatch.setattr(plan, "_run_admitted_plan", reached)
    browser = client(membership)
    assert browser.post(path, json={"recipes": 3, "servings": 2}).status_code == 418
    assert browser.post(path, json={"recipes": 5, "servings": 4}).status_code == 403
    register(browser)
    assert browser.post(path, json={"recipes": 5, "servings": 4}).status_code == 418
    browser.post("/api/account/logout")
    assert browser.post(path, json={"recipes": 5, "servings": 4}).status_code == 403


def test_existing_account_pantry_is_not_overwritten_by_guest_migration(membership):
    browser = client(membership)
    register(browser)
    browser.put("/api/personal/pantry", json={"revision": 0, "items": [{"name": "ris", "quantity": 100, "unit": "g"}]})
    browser.post("/api/account/logout")
    browser.put("/api/personal/pantry", json={"revision": 0, "items": [{"name": "pasta", "quantity": 200, "unit": "g"}]})
    browser.post("/api/account/login", json={"email": "member@example.test", "password": PASSWORD})
    preview = browser.get("/api/account/guest-migration-preview").json()
    assert not preview["can_move"]
    assert browser.post("/api/account/migrate-guest", json={"guest_revision": preview["guest_revision"], "account_revision": preview["account_revision"], "confirm_move_to_verified_account": True}).status_code == 409
    assert browser.get("/api/personal/state").json()["items"][0]["name"] == "ris"
    browser.post("/api/account/logout")
    assert browser.get("/api/personal/state").json()["items"][0]["name"] == "pasta"


def test_session_survives_store_reopen(membership):
    browser = client(membership)
    register(browser)
    token = browser.cookies.get(COOKIE)
    original = MemberAccounts(membership.state.plan_store).owner(token)
    reopened = MemberAccounts(PlanStore(membership.state.plan_store.path))
    assert reopened.owner(token) == original
    with membership.state.plan_store._connect() as db:
        assert db.execute("SELECT owner FROM member_sessions WHERE token_hash=?", (digest(token),)).fetchone()[0] == original


def test_reset_prevents_in_flight_old_password_login_from_creating_session(membership):
    store = MemberAccounts(membership.state.plan_store)
    owner, recovery = store.register("race@example.test", PASSWORD)
    identity, proof = store.authenticate("race@example.test", PASSWORD)
    assert identity == owner
    assert store.recover("race@example.test", recovery, "a different password 789")
    assert store.create_session(owner, expected_password_hash=proof) is None


@pytest.mark.parametrize("browser_name,width", [("chromium", 1280), ("webkit", 390)])
def test_browser_guest_registration_pantry_migration_and_sign_in(membership, browser_name, width, monkeypatch):
    import socket
    import time
    from pathlib import Path
    from threading import Thread

    import uvicorn
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles
    from playwright.sync_api import expect, sync_playwright

    static = Path(__file__).resolve().parents[1] / "app/static"
    membership.mount("/static", StaticFiles(directory=static))

    @membership.get("/personal")
    def page_html():
        return FileResponse(static / "personal.html")

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    base = f"http://127.0.0.1:{sock.getsockname()[1]}"
    from dataclasses import replace
    settings = replace(account.get_settings(), public_base_url=base)
    for module in (account, personal, plan):
        monkeypatch.setattr(module, "get_settings", lambda: settings)
    server = uvicorn.Server(uvicorn.Config(membership, log_level="error", lifespan="off"))
    thread = Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    thread.start()
    try:
        for _ in range(100):
            if server.started:
                break
            time.sleep(.05)
        assert server.started
        with sync_playwright() as pw:
            browser = getattr(pw, browser_name).launch()
            page = browser.new_page(viewport={"width": width, "height": 900})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.route("**/scanner-assets/**", lambda route: route.fulfill(body=""))
            page.route("**/api/recipe-library", lambda route: route.fulfill(json={"enabled": False}))
            page.route("**/api/municipalities", lambda route: route.fulfill(json={"municipalities": []}))
            page.goto(base + "/personal#pantry")
            page.get_by_role("button", name="Lägg till manuellt").click()
            dialog = page.locator("#personal-dialog")
            dialog.get_by_label("Vara", exact=True).fill("Ris")
            dialog.get_by_label("Faktisk mängd hemma").fill("500")
            dialog.get_by_role("button", name="Spara skafferivara").click()
            expect(page.locator("#pantry-list")).to_contain_text("Ris")
            page.get_by_role("button", name="Spara skafferiet på mitt konto").click()
            page.get_by_role("button", name="Skapa ett konto", exact=True).click()
            page.get_by_label("E-postadress", exact=True).fill("browser@example.test")
            page.get_by_label("Lösenord (minst 12 tecken)", exact=True).fill(PASSWORD)
            page.get_by_role("button", name="Skapa konto", exact=True).click()
            expect(page.get_by_label("Din återställningskod")).to_be_visible()
            assert page.get_by_label("Din återställningskod").input_value()
            page.get_by_role("button", name="Jag har sparat koden – fortsätt").click()
            page.get_by_role("button", name="Spara mitt gästskafferi", exact=False).click()
            page.get_by_role("button", name="Öppna mitt skafferi").click()
            expect(page.locator("#pantry-list")).to_contain_text("Ris")
            page.locator("#account-nav").click()
            out = Path(".local/membership")
            out.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(out / f"account-{browser_name}.png"), full_page=True)
            page.get_by_role("button", name="Logga ut", exact=True).click()
            expect(page.get_by_role("button", name="Logga in", exact=True)).to_be_visible()
            page.get_by_label("E-postadress", exact=True).fill("browser@example.test")
            page.get_by_label("Lösenord (minst 12 tecken)", exact=True).fill(PASSWORD)
            page.get_by_role("button", name="Logga in", exact=True).click()
            page.get_by_role("button", name="Öppna mitt skafferi").click()
            expect(page.locator("#pantry-list")).to_contain_text("Ris")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert not errors
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        sock.close()
