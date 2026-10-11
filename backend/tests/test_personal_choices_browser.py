"""Offline browser coverage for choices, request semantics and draft migration."""

import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from types import SimpleNamespace

import pytest
from app.models.personal import PersonalMutation
from app.models.plan import PlanRequest
from playwright.sync_api import expect, sync_playwright
from pydantic import ValidationError


@pytest.fixture(params=["chromium", "webkit"])
def choices(request):
    static = Path(__file__).resolve().parents[1] / "app/static"

    class Handler(SimpleHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            self.path = self.path.replace("/static/", "/")
            return super().do_GET()

    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Handler, directory=str(static)))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    captured = []
    errors = []
    with sync_playwright() as pw:
        browser = getattr(pw, request.param).launch()
        page = browser.new_page(viewport={"width": 1280, "height": 1000})
        page.on("pageerror", lambda error: errors.append(str(error)))

        def api(route):
            path = route.request.url.split("/api/")[-1].split("?")[0]
            data = {}
            status = 200
            headers = {}
            if path == "personal/state":
                data = {"revision": 0, "items": [], "reservations": {}, "profile": {},
                        "account": {"message": "Privat testgäst"}}
            elif path == "recipe-library":
                data = {"enabled": True}
            elif path == "municipalities":
                data = {"municipalities": [{"name": "Lund", "municipality_code": "1281",
                                           "postal_code": "22350", "available": True}]}
            elif path == "price-contexts":
                data = {"contexts": []}
            elif path == "plans":
                captured.append(route.request.post_data_json)
                status = 422
                data = {"detail": "Testet fångar valen utan att skapa en plan."}
                headers = {"X-Plan-Request-ID": route.request.headers["x-request-id"]}
            route.fulfill(status=status, content_type="application/json",
                          body=json.dumps(data), headers=headers)

        page.route("**/api/**", api)
        page.route("**/scanner-assets/**", lambda route: route.fulfill(body=""))
        yield page, f"http://127.0.0.1:{server.server_port}/personal.html#choices", captured
        assert not errors
        browser.close()
    server.shutdown()
    server.server_close()
    thread.join()


def submit(page, captured):
    before = len(captured)
    page.locator("#generate-plan").click()
    expect(page.locator("#personal-status")).to_contain_text("Testet fångar")
    assert len(captured) == before + 1
    # Validate against the actual API contracts, not a copy of frontend rules.
    PlanRequest.model_validate(captured[-1])
    return captured[-1]


def test_primary_sliders_optional_meals_and_default_request(choices):
    page, url, captured = choices
    page.goto(url)
    expect(page.locator("#generate-plan")).to_be_enabled()
    expect(page.locator("#extra-choices")).not_to_have_attribute("open", "")
    expect(page.locator("#dinner-count")).to_have_value("5")
    expect(page.locator("#dinner-servings")).to_have_value("4")
    expect(page.locator("#max-stores")).to_have_value("2")
    expect(page.locator("#breakfast-count")).not_to_be_visible()
    expect(page.locator("#dinner-servings")).to_have_attribute("max", "6")
    page.locator("#dinner-servings").focus()
    page.keyboard.press("ArrowRight")
    expect(page.locator("#dinner-servings")).to_have_value("5")
    initial = submit(page, captured)
    assert initial["purchase_planning_mode"] == "estimated"
    assert initial["varied_budget_percent"] == 25
    assert initial["personal"]["allow_nutrition_estimates"] is True
    assert [m["count"] for m in initial["personal"]["meals"]] == [5, 0, 0]
    assert all(v is None for v in initial["personal"]["meals"][0]["limits"].values())
    page.locator("#extra-choices>summary").click()
    page.locator("#enable-breakfast").check()
    expect(page.locator("#breakfast-count")).to_be_visible()
    page.locator("#breakfast-count").focus()
    page.keyboard.press("Home")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("ArrowRight")
    page.locator("#breakfast-servings").focus()
    page.keyboard.press("ArrowRight")
    page.locator("#enable-snack").check()
    page.locator("#snack-count").focus()
    page.keyboard.press("ArrowLeft")
    page.locator("#recipe-style").select_option("library")
    expect(page.locator('[data-meal-type="breakfast"]')).to_be_visible()
    page.locator("#breakfast-min_protein_g").evaluate("node => node.value = 30")
    selected = submit(page, captured)
    assert [m["count"] for m in selected["personal"]["meals"]] == [5, 3, 4]
    assert selected["personal"]["meals"][1]["limits"]["min_protein_g"] == 30
    page.locator("#enable-breakfast").uncheck()
    expect(page.locator('[data-meal-type="breakfast"]')).not_to_be_visible()
    disabled = submit(page, captured)
    assert disabled["personal"]["meals"][1]["count"] == 0
    assert disabled["personal"]["meals"][1]["limits"] == {}
    page.locator("#enable-breakfast").check()
    expect(page.locator("#breakfast-count")).to_have_value("3")
    expect(page.locator("#breakfast-min_protein_g")).to_have_value("30")


def test_draft_restores_sliders_and_consolidates_hard_requirements(choices):
    page, url, captured = choices
    draft = {"max_stores": 3, "postal_code": "22350", "purchase_planning_mode": "exact",
             "personal": {"allow_nutrition_estimates": False,
                          "profile": {"allergies": ["jordnötter"]},
                          "meals": [{"meal_type": "dinner", "count": 4, "servings": 2,
                                     "profile": {"exclusions": ["fisk"]},
                                     "limits": {"min_protein_g": 30.5}},
                                    {"meal_type": "snack", "count": 2, "servings": 1}]}}
    page.add_init_script("sessionStorage.setItem('smako.personal.requestDraft', "
                         + json.dumps(json.dumps(draft)) + ");")
    page.goto(url)
    expect(page.locator("#dinner-count")).to_have_value("4")
    expect(page.locator("#snack-count")).to_be_visible()
    page.locator("#extra-choices>summary").click()
    expect(page.locator("#profile-allergies")).to_have_value("jordnötter")
    expect(page.locator("#profile-exclusions")).to_have_value("fisk")
    expect(page.locator("#dinner-allergies")).to_have_count(0)
    expect(page.locator("#dinner-min_protein_g")).to_have_value("30.5")
    for width in (1280, 390):
        page.set_viewport_size({"width": width, "height": 1000})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    restored = submit(page, captured)
    assert restored["purchase_planning_mode"] == "estimated"
    assert restored["personal"]["allow_nutrition_estimates"] is True
    assert restored["personal"]["profile"]["exclusions"] == ["fisk"]
    assert restored["personal"]["profile"]["allergies"] == ["jordnötter"]
    assert restored["personal"]["meals"][0]["limits"]["min_protein_g"] == 30.5


def test_estimate_change_only_applies_to_explicit_recalculation():
    for action in ("recalculate", "extras"):
        value = PersonalMutation(revision=1, pantry_revision=0, action=action,
                                 allow_nutrition_estimates=True)
        assert value.allow_nutrition_estimates is True
    for action in ("purchase", "consume", "release", "restore_revision"):
        with pytest.raises(ValidationError):
            PersonalMutation(revision=1, pantry_revision=0, action=action,
                             allow_nutrition_estimates=True)
    assert "allow_nutrition_estimates" not in PersonalMutation(
        revision=1, pantry_revision=0, action="purchase").model_dump()


@pytest.mark.asyncio
async def test_recalculation_passes_estimates_without_rewriting_saved_history(tmp_path, monkeypatch):
    from app.api import personal as api
    from app.config import Settings

    from backend.tests.test_personal_booked_revisions import OWNER, setup_plan

    prepared, plans, private, saved, stock = setup_plan(tmp_path)
    original = saved.model_dump_json()
    monkeypatch.setattr(api, "context", lambda *_: (Settings(), plans, OWNER))
    monkeypatch.setattr(api, "GLOBAL_PREPARED_PRICE_UNIVERSES",
                        SimpleNamespace(get_for_request=lambda *_: prepared))
    captured = []

    class CapturedRequest(Exception):
        pass

    async def capture(plan_request, *_args, **_kwargs):
        captured.append(plan_request)
        raise CapturedRequest

    monkeypatch.setattr(api, "_run_personal_work", capture)
    with pytest.raises(CapturedRequest):
        await api._change_plan(saved.plan_id, PersonalMutation(
            revision=saved.revision, pantry_revision=stock["revision"], action="recalculate",
            purchase_planning_mode="estimated", allow_nutrition_estimates=True), None, None)
    assert captured[0].personal.allow_nutrition_estimates is True
    assert captured[0].purchase_planning_mode == "estimated"
    assert plans.get_owned(saved.plan_id, owner_actor_hash=OWNER).model_dump_json() == original
    assert private.read(OWNER) == stock
