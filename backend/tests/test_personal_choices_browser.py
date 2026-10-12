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
            elif path == "shopping-location":
                data = {"status": "eligible", "postal_code": "22350", "area_postal_code": "22350",
                        "municipality_name": "Lund", "area_name": "Lund", "municipality_available": True,
                        "nearest_distance_km": 1.5, "contexts": [
                            {"context_id": "near", "display_name": "Nära butik", "distance_km": 1.5},
                            {"context_id": "far", "display_name": "Bortre butik", "distance_km": 4.5},
                            {"context_id": "unknown", "display_name": "Okänd position", "distance_km": None}]}
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


def choose_location(page):
    expect(page.locator("#check-postcode")).to_be_enabled()
    expect(page.locator("#dinner-count")).not_to_be_visible()
    page.locator("#customer-postcode").fill("223 50")
    page.locator("#check-postcode").click()
    expect(page.locator("#location-status")).to_contain_text("Lund kommun")
    page.locator("#confirm-location").click()
    expect(page.locator("#dinner-count")).to_be_visible()


def test_primary_sliders_optional_meals_and_default_request(choices):
    page, url, captured = choices
    page.goto(url)
    choose_location(page)
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
    expect(page.locator("#recipe-style")).to_have_count(0)
    expect(page.locator("#meal-dinner-level")).to_have_count(0)
    expect(page.locator("#recipe-price-contexts")).to_have_count(0)
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
    choose_location(page)
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


def test_ingredient_interval_drives_candidates_and_survives_reload(choices):
    from app.services.recipe_library import ingredient_count, meal_candidates

    page, url, captured = choices
    page.goto(url)
    choose_location(page)
    page.locator("#extra-choices>summary").click()
    minimum = page.locator("#meal-dinner-min_ingredients")
    maximum = page.locator("#meal-dinner-max_ingredients")
    expect(minimum).to_be_visible()
    expect(maximum).to_be_visible()
    minimum.fill("15")
    maximum.fill("10")
    assert maximum.evaluate("node => !node.checkValidity()")
    for low, high in ((3, 5), (10, 15)):
        minimum.fill(str(low))
        maximum.fill(str(high))
        payload = submit(page, captured)
        request = PlanRequest.model_validate(payload)
        dinner = request.personal.meals[0]
        assert dinner.recipe_choices.dinner_level is None
        candidates = meal_candidates(dinner, request.recipe_preferences)
        assert candidates
        assert all(low <= ingredient_count(recipe) <= high for recipe in candidates)
    page.reload()
    choose_location(page)
    page.locator("#extra-choices>summary").click()
    expect(minimum).to_have_value("10")
    expect(maximum).to_have_value("15")
    minimum.fill("")
    maximum.fill("")
    payload = submit(page, captured)
    request = PlanRequest.model_validate(payload)
    candidates = meal_candidates(request.personal.meals[0], request.recipe_preferences)
    assert {r.design.dinner_level for r in candidates} >= {"simple", "crafted"}
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


@pytest.mark.parametrize("old_choices", [None, {"dinner_level": "simple",
                                              "min_ingredients": 4, "max_ingredients": 12}])
def test_old_recipe_styles_migrate_to_visible_ingredient_limits(choices, old_choices):
    page, url, captured = choices
    draft = {"postal_code": "22350", "recipe_preferences": {
        "mode": "complete", "min_ingredients": 11, "max_ingredients": 14,
        "max_minutes": 45}, "personal": {"meals": [{
            "meal_type": "dinner", "count": 5, "servings": 2,
            "recipe_choices": old_choices}]}}
    page.add_init_script("sessionStorage.setItem('smako.personal.requestDraft', "
                         + json.dumps(json.dumps(draft)) + ");")
    page.goto(url)
    choose_location(page)
    page.locator("#extra-choices>summary").click()
    low, high = (4, 12) if old_choices else (11, 14)
    expect(page.locator("#meal-dinner-min_ingredients")).to_have_value(str(low))
    expect(page.locator("#meal-dinner-max_ingredients")).to_have_value(str(high))
    payload = submit(page, captured)
    dinner = payload["personal"]["meals"][0]["recipe_choices"]
    assert "dinner_level" not in dinner
    assert (dinner["min_ingredients"], dinner["max_ingredients"]) == (low, high)
    assert dinner["max_total_minutes"] == (None if old_choices else 45)


def test_meal_dialogs_intervals_and_shared_distribution_budget(choices):
    page, url, captured = choices
    page.goto(url)
    choose_location(page)
    page.locator("#dinner-distribution-open").click()
    expect(page.locator("#dinner-distribution-dialog")).to_be_visible()
    page.locator("#dinner-fish").focus()
    page.keyboard.press("End")
    expect(page.locator("#dinner-fish")).to_have_value("5")
    for kind in ("vegetarian", "chicken", "meat"):
        expect(page.locator(f"#dinner-{kind}")).to_have_attribute("max", "5")
        page.locator(f"#dinner-{kind}").focus()
        page.keyboard.press("End")
        expect(page.locator(f"#dinner-{kind}")).to_have_value("0")
    page.keyboard.press("Escape")
    expect(page.locator("#dinner-distribution-open")).to_be_focused()
    page.locator("#dinner-count").focus()
    page.keyboard.press("ArrowLeft")
    expect(page.locator("#dinner-fish")).to_have_value("4")
    page.locator("#dinner-weight-open").click()
    page.locator("#dinner-min_weight_g").focus()
    page.keyboard.press("ArrowRight")
    page.locator("#dinner-max_weight_g").focus()
    page.keyboard.press("Home")
    expect(page.locator("#dinner-max_weight_g")).to_have_value("0")
    page.locator("#dinner-min_weight_g").focus()
    page.keyboard.press("End")
    expect(page.locator("#dinner-min_weight_g")).to_have_value("0")
    page.locator("#dinner-weight-dialog").get_by_role("button", name="Återställ standard").click()
    track = page.locator("#dinner-weight-dialog .interval-track").bounding_box()
    y = track["y"] + track["height"] / 2
    for start, end in ((12, track["width"] * .2), (track["width"] - 12, track["width"] * .75)):
        page.mouse.move(track["x"] + start, y)
        page.mouse.down()
        page.mouse.move(track["x"] + end, y, steps=8)
        page.mouse.up()
    assert 100 < float(page.locator("#dinner-min_weight_g").input_value()) < 1000
    assert 1500 < float(page.locator("#dinner-max_weight_g").input_value()) < 2800
    page.locator("#dinner-weight-dialog").get_by_role("button", name="Återställ standard").click()
    page.locator("#dinner-weight-dialog").get_by_role("button", name="Klart").click()
    page.locator("#dinner-nutrition-open").click()
    page.locator("#dinner-min_protein_g").evaluate("n=>{n.value=30;n.dispatchEvent(new Event('input',{bubbles:true}));}")
    page.locator("#dinner-max_protein_g").evaluate("n=>{n.value=60;n.dispatchEvent(new Event('input',{bubbles:true}));}")
    for width in (1280, 390):
        page.set_viewport_size({"width": width, "height": 800})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert page.locator("#dinner-nutrition-dialog").evaluate("n=>n.scrollWidth<=n.clientWidth")
    page.keyboard.press("Escape")
    payload = submit(page, captured)
    meal = payload["personal"]["meals"][0]
    assert meal["distribution"] == {"vegetarian": 0, "chicken": 0, "fish": 4, "meat": 0}
    assert meal["limits"]["min_weight_g"] is None and meal["limits"]["max_weight_g"] is None
    assert (meal["limits"]["min_protein_g"], meal["limits"]["max_protein_g"]) == (30, 60)


def test_fixed_distribution_and_editable_values(choices):
    page, url, captured = choices
    page.goto(url)
    choose_location(page)

    def enter(control, value):
        editor = page.locator(f"#{control}-value")
        editor.fill(value)
        editor.press("Enter")

    # Every thumb has its own accessible keyboard editor, including optional meals.
    assert page.locator('input[type="range"]').evaluate_all(
        "nodes=>nodes.every(n=>document.getElementById(n.id+'-value')?.getAttribute('aria-label'))")
    enter("dinner-servings", "9")
    expect(page.locator("#dinner-servings")).to_have_value("6")
    enter("max-stores", "1")
    page.locator("#dinner-distribution-open").click()
    enter("dinner-vegetarian", "2")
    page.locator("#dinner-chicken").focus()
    page.keyboard.press("End")
    expect(page.locator("#dinner-chicken")).to_have_value("3")
    expect(page.locator("#dinner-vegetarian")).to_have_value("2")
    # Editing an earlier category must not displace the later one either.
    enter("dinner-vegetarian", "5")
    expect(page.locator("#dinner-vegetarian-value")).to_have_value("2")
    expect(page.locator("#dinner-chicken")).to_have_value("3")
    for kind in ("vegetarian", "chicken", "fish", "meat"):
        expect(page.locator(f"#dinner-{kind}")).to_have_attribute("max", "5")
    enter("dinner-fish", "4")
    expect(page.locator("#dinner-fish")).to_have_value("0")
    enter("dinner-fish", "")
    expect(page.locator("#dinner-fish")).to_have_value("-1")
    page.locator("#dinner-diet").select_option("vegetarian")
    expect(page.locator("#dinner-chicken-value")).to_be_disabled()
    expect(page.locator("#dinner-chicken")).to_have_attribute("max", "5")
    page.keyboard.press("Escape")
    page.locator("#dinner-nutrition-open").click()
    enter("dinner-min_protein_g", "30,5")
    enter("dinner-max_protein_g", "500")
    expect(page.locator("#dinner-max_protein_g-value")).to_have_value("100")
    enter("dinner-max_carbs_g", "500")
    expect(page.locator("#dinner-max_carbs_g-value")).to_have_value("400")
    enter("dinner-max_protein_g", "20")
    expect(page.locator("#dinner-max_protein_g-value")).to_have_value("30.5")
    enter("dinner-max_protein_g", "")
    enter("dinner-max_kcal", "650")
    for width in (390, 1280):
        page.set_viewport_size({"width": width, "height": 800})
        assert page.locator("#dinner-nutrition-dialog").evaluate("n=>n.scrollWidth<=n.clientWidth")
    page.keyboard.press("Escape")
    page.locator("#extra-choices>summary").click()
    expect(page.locator("#extra-choices")).not_to_contain_text("Medlemspriser")
    # Blur also commits; invalid text and Escape leave the last valid value.
    page.locator("#organic-percent-value").fill("25")
    page.locator("#organic-percent-value").press("Tab")
    enter("organic-percent", "abc")
    page.locator("#organic-percent-value").fill("80")
    page.locator("#organic-percent-value").press("Escape")
    expect(page.locator("#organic-percent-value")).to_have_value("25")
    assert not captured, "Enter in a value editor must not submit the plan"
    payload = submit(page, captured)
    assert payload["membership_price_policy"] == "all_advertised"
    assert payload["max_stores"] == 1 and payload["personal"]["organic_percent"] == 25
    meal = payload["personal"]["meals"][0]
    assert meal["servings"] == 6
    assert meal["distribution"] == {"vegetarian": 5, "chicken": 0, "fish": 0, "meat": 0}
    assert meal["limits"]["min_protein_g"] == 30.5
    assert meal["limits"]["max_protein_g"] is None
    assert meal["limits"]["max_carbs_g"] == 400 and meal["limits"]["max_kcal"] == 650


def test_saved_limits_above_new_scale_are_not_silently_lost(choices):
    page, url, captured = choices
    draft = {"postal_code": "22350", "personal": {"meals": [
        {"meal_type": "dinner", "count": 5, "servings": 2,
         "limits": {"min_protein_g": 120, "max_protein_g": 150, "max_carbs_g": 450}}]}}
    page.add_init_script("sessionStorage.setItem('smako.personal.requestDraft', "
                         + json.dumps(json.dumps(draft)) + ");")
    page.goto(url)
    choose_location(page)
    page.locator("#dinner-nutrition-open").click()
    expect(page.locator("#dinner-min_protein_g-value")).to_have_value("120")
    expect(page.locator("#dinner-max_protein_g-value")).to_have_value("150")
    expect(page.locator("#dinner-nutrition-dialog")).to_contain_text("Tidigare sparad gräns över 100 g behålls")
    page.keyboard.press("Escape")
    limits = submit(page, captured)["personal"]["meals"][0]["limits"]
    assert (limits["min_protein_g"], limits["max_protein_g"], limits["max_carbs_g"]) == (120, 150, 450)
    page.locator("#dinner-nutrition-open").click()
    editor = page.locator("#dinner-max_protein_g-value")
    editor.fill("50")
    editor.press("Enter")
    expect(editor).to_have_value("150")
    editor.fill("")
    editor.press("Enter")
    page.locator("#dinner-max_protein_g").focus()
    page.keyboard.press("ArrowLeft")
    expect(editor).to_have_value("")
    page.keyboard.press("Escape")
    limits = submit(page, captured)["personal"]["meals"][0]["limits"]
    assert limits["min_protein_g"] == 120 and limits["max_protein_g"] is None


def test_location_radius_municipality_manual_and_invalidation(choices):
    page, url, captured = choices
    page.goto(url)
    choose_location(page)
    assert submit(page, captured)["allowed_store_ids"] == ["near"]
    page.locator("#location-radius").select_option("1")
    expect(page.locator("#dinner-count")).not_to_be_visible()

    expect(page.locator("#confirm-location")).to_be_disabled()
    page.locator("#location-radius").select_option("5")
    page.locator("#confirm-location").click()
    assert submit(page, captured)["allowed_store_ids"] == ["near", "far"]
    page.locator("#location-store-mode").select_option("municipality")
    page.locator("#confirm-location").click()
    assert submit(page, captured)["allowed_store_ids"] == ["near", "far", "unknown"]
    page.locator("#choose-specific-stores").click()
    page.locator("#context-near").uncheck()
    page.locator("#context-far").uncheck()
    page.locator("#context-unknown").uncheck()
    page.locator("#location-stores-done").click()
    expect(page.locator("#confirm-location")).to_be_disabled()
    page.locator("#choose-specific-stores").click()
    page.locator("#context-far").check()
    page.keyboard.press("Escape")
    page.locator("#confirm-location").click()
    assert submit(page, captured)["allowed_store_ids"] == ["far"]
    page.locator("#customer-postcode").fill("99999")
    expect(page.locator("#dinner-count")).not_to_be_visible()
    expect(page.locator("#location-store-settings")).not_to_be_visible()
    page.route("**/api/shopping-location?**", lambda route: route.fulfill(
        content_type="application/json", body=json.dumps({"status": "outside_coverage"})))
    page.locator("#check-postcode").click()
    expect(page.locator("#location-status")).to_contain_text("ingen kartlagd butik")
    expect(page.locator("#dinner-count")).not_to_be_visible()


def test_late_postcode_response_cannot_replace_newer_location(choices):
    page, url, _captured = choices
    pending = []

    def location_reply(route):
        if "22350" in route.request.url:
            pending.append(route)
        else:
            route.fulfill(content_type="application/json", body=json.dumps({
                "status": "eligible", "postal_code": "21120", "area_postal_code": "21120",
                "municipality_name": "Malmö", "area_name": "Malmö", "municipality_available": True,
                "nearest_distance_km": 1, "contexts": [{"context_id": "malmo", "display_name": "Malmöbutik", "distance_km": 1}]}))

    page.route("**/api/shopping-location?**", location_reply)
    page.goto(url)
    expect(page.locator("#check-postcode")).to_be_enabled()
    page.locator("#customer-postcode").fill("22350")
    with page.expect_request("**/api/shopping-location?**"):
        page.locator("#check-postcode").click()
    page.locator("#customer-postcode").fill("21120")
    page.locator("#check-postcode").click()
    expect(page.locator("#location-status")).to_contain_text("Malmö kommun")
    assert len(pending) == 1
    pending[0].fulfill(content_type="application/json", body=json.dumps({"status": "outside_coverage"}))
    page.locator("#confirm-location").click()
    expect(page.locator("#location-status")).to_contain_text("Malmö kommun")
    expect(page.locator("#postal-code")).to_have_value("21120")
    expect(page.locator("#dinner-count")).to_be_visible()


def test_full_municipality_and_radius_can_select_more_than_forty_stores(choices):
    page, url, captured = choices
    rows = [{"context_id": f"store-{i}", "display_name": f"Butik {i}", "distance_km": i / 10} for i in range(63)]
    page.route("**/api/shopping-location?**", lambda route: route.fulfill(
        content_type="application/json", body=json.dumps({
            "status": "eligible", "postal_code": "22350", "area_postal_code": "22350",
            "municipality_name": "Lund", "area_name": "Lund", "municipality_available": True,
            "nearest_distance_km": 0, "contexts": rows})))
    page.goto(url)
    choose_location(page)
    page.locator("#location-radius").select_option("5")
    page.locator("#confirm-location").click()
    assert len(submit(page, captured)["allowed_store_ids"]) == 51
    page.locator("#location-store-mode").select_option("municipality")
    page.locator("#confirm-location").click()
    assert len(submit(page, captured)["allowed_store_ids"]) == 63


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
