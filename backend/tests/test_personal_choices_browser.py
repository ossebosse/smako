"""Offline browser coverage for choices, request semantics and draft migration."""

import json
import subprocess
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
    page.locator("#choice-submit").click()
    expect(page.locator("#personal-status")).to_contain_text("Testet fångar")
    assert len(captured) == before + 1
    # Validate against the actual API contracts, not a copy of frontend rules.
    PlanRequest.model_validate(captured[-1])
    return captured[-1]


def test_current_variation_origins_and_deliberate_old_draft_migration(choices):
    page,url,captured=choices
    page.route('**/api/recipe-library',lambda route:route.fulfill(content_type='application/json',
        body=json.dumps({'enabled':True,'variation_intent_enabled':True})))
    page.goto(url);choose_location(page)
    fresh=submit(page,captured)
    assert set(fresh['variation_intent']['field_origins'].values())=={'default'}
    assert 'max_same_primary_ingredient_meals' not in fresh
    old={'postal_code':'22350','max_same_primary_ingredient_meals':2,'max_pairwise_recipe_similarity':.6,
         'personal':{'meals':[{'meal_type':'dinner','count':3,'servings':2}]}}
    page.evaluate('(draft)=>sessionStorage.setItem("smako.personal.requestDraft",JSON.stringify(draft))',old)
    page.reload();choose_location(page)
    page.locator('#extra-choices>summary').click()
    control=page.locator('#recipe-inherited-variation')
    expect(control).not_to_be_checked()
    restored=submit(page,captured)
    assert restored['variation_intent']['field_origins']['max_same_primary_ingredient_meals']=='unknown'
    assert restored['max_same_primary_ingredient_meals']==2 and restored['max_pairwise_recipe_similarity']==.6
    control.check()
    changed=submit(page,captured)
    assert changed['variation_intent']['field_origins']['max_same_primary_ingredient_meals']=='default'
    assert 'max_same_primary_ingredient_meals' not in changed
    assert changed['max_pairwise_recipe_similarity']==.6


@pytest.mark.parametrize("source", ["field", "override"])
def test_current_explicit_primary_limit_is_retained_by_ui(choices, source):
    page,url,captured=choices
    page.route('**/api/recipe-library',lambda route:route.fulfill(content_type='application/json',
        body=json.dumps({'enabled':True,'variation_intent_enabled':True})))
    draft={'postal_code':'22350','max_same_primary_ingredient_meals':2,
        'variation_intent':{'version':'explicit-over-default-v2','field_origins':{'max_same_primary_ingredient_meals':'explicit'}},
        'personal':{'meals':[{'meal_type':'dinner','count':3,'servings':2}]}}
    if source == 'override':
        del draft['max_same_primary_ingredient_meals']
        draft['variation_intent']['field_origins']['max_same_primary_ingredient_meals']='default'
        draft['recipe_diversity_overrides']={'max_same_primary_ingredient_meals':2}
    page.add_init_script('sessionStorage.setItem("smako.personal.requestDraft",'+json.dumps(json.dumps(draft))+');')
    page.goto(url);choose_location(page)
    page.locator('#extra-choices>summary').click()
    expect(page.locator('#recipe-inherited-variation')).to_be_disabled()
    expect(page.locator('#recipe-inherited-variation')).not_to_be_checked()
    posted=submit(page,captured)
    if source == 'field':
        assert posted['max_same_primary_ingredient_meals']==2
        assert posted['variation_intent']['field_origins']['max_same_primary_ingredient_meals']=='explicit'
    else:
        assert posted['recipe_diversity_overrides']=={'max_same_primary_ingredient_meals':2}
        assert posted['variation_intent']['field_origins']['max_same_primary_ingredient_meals']=='default'


def test_saved_current_intent_is_not_dropped_when_feature_is_unavailable(choices):
    page,url,captured=choices
    draft={'postal_code':'22350','variation_intent':{'version':'explicit-over-default-v2',
        'field_origins':{'max_same_primary_ingredient_meals':'default'}},
        'personal':{'meals':[{'meal_type':'dinner','count':3,'servings':2}]}}
    page.add_init_script('sessionStorage.setItem("smako.personal.requestDraft",'+json.dumps(json.dumps(draft))+');')
    page.goto(url);choose_location(page)
    posted=submit(page,captured)
    assert posted['variation_intent']['version']=='explicit-over-default-v2'
    assert posted['variation_intent']['field_origins']['max_same_primary_ingredient_meals']=='default'


def test_explicit_pantry_choice_survives_draft_and_can_be_changed_deliberately(choices):
    page,url,captured=choices
    draft={'postal_code':'22350','personal':{'use_pantry':False,
        'meals':[{'meal_type':'dinner','count':3,'servings':2}]}}
    page.add_init_script('sessionStorage.setItem("smako.personal.requestDraft",'+json.dumps(json.dumps(draft))+');')
    page.goto(url);choose_location(page)
    posted=submit(page,captured)
    assert posted['personal']['use_pantry'] is False
    page.locator('#extra-choices>summary').click()
    expect(page.locator('#planning-use-pantry')).not_to_be_checked()
    page.locator('#planning-use-pantry').check()
    assert submit(page,captured)['personal']['use_pantry'] is True


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
    expect(page.locator("#dinner-count")).to_have_value("3")
    expect(page.locator("#dinner-servings")).to_have_value("2")
    expect(page.locator("#max-stores")).to_have_value("2")
    expect(page.locator("#breakfast-count")).not_to_be_visible()
    expect(page.locator("#dinner-servings")).to_have_attribute("max", "8")
    page.locator("#dinner-servings").focus()
    page.keyboard.press("ArrowRight")
    expect(page.locator("#dinner-servings")).to_have_value("3")
    initial = submit(page, captured)
    assert initial["purchase_planning_mode"] == "estimated"
    assert initial["varied_budget_percent"] == 25
    assert initial["personal"]["allow_nutrition_estimates"] is True
    assert [m["count"] for m in initial["personal"]["meals"]] == [3, 0, 0]
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
    page.locator("#breakfast-nutrition-open").click()
    page.locator("#breakfast-min_protein_g-value").fill("30")
    page.locator("#breakfast-nutrition-dialog").get_by_role("button", name="Klart", exact=True).click()
    selected = submit(page, captured)
    assert [m["count"] for m in selected["personal"]["meals"]] == [3, 3, 2]
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


def edit(page, control, value):
    page.locator(f"#{control}-value").fill(str(value))


def done(page, meal, kind):
    page.locator(f"#{meal}-{kind}-dialog").get_by_role("button", name="Klart", exact=True).click()


def test_distribution_conflict_preserves_explicit_values(choices):
    page, url, captured = choices
    page.goto(url)
    choose_location(page)
    edit(page, "dinner-count", 5)
    page.locator("#dinner-distribution-open").click()
    edit(page, "dinner-vegetarian", 3)
    edit(page, "dinner-chicken", 2)
    expect(page.locator("#dinner-distribution-dialog")).to_contain_text("5 av 5 måltider fördelade · 0 kvar")
    done(page, "dinner", "distribution")
    edit(page, "dinner-count", 4)
    expect(page.locator("#dinner-conflict")).to_contain_text("5 fördelade men bara 4")
    page.locator("#choice-submit").click()
    assert not captured
    page.locator("#dinner-distribution-open").click()
    expect(page.locator("#dinner-vegetarian-value")).to_have_value("3")
    expect(page.locator("#dinner-chicken-value")).to_have_value("2")
    done(page, "dinner", "distribution")
    expect(page.locator("#dinner-distribution-dialog")).to_be_visible()
    edit(page, "dinner-chicken", 1)
    edit(page, "dinner-fish", 0)
    done(page, "dinner", "distribution")
    meal = submit(page, captured)["personal"]["meals"][0]
    assert meal["distribution"] == {"vegetarian": 3, "chicken": 1, "fish": 0}
    page.locator("#dinner-distribution-open").click()
    page.locator("#dinner-diet").select_option("vegan")
    done(page, "dinner", "distribution")
    expect(page.locator("#dinner-distribution-dialog")).to_be_visible()
    page.keyboard.press("Escape")
    assert submit(page, captured)["personal"]["meals"][0]["diet"] == "mixed"


def test_all_nine_dialogs_are_independent_transactional_and_accessible(choices):
    page, url, captured = choices
    page.goto(url)
    choose_location(page)
    page.locator("#extra-choices>summary").click()
    page.locator("#enable-breakfast").check()
    page.locator("#enable-snack").check()
    for index, meal in enumerate(("dinner", "breakfast", "snack")):
        for kind in ("distribution", "weight", "nutrition"):
            page.locator(f"#{meal}-{kind}-open").click()
            dialog = page.locator(f"#{meal}-{kind}-dialog")
            expect(dialog).to_be_visible()
            assert page.locator("dialog[open]").count() == 1
            assert page.evaluate("getComputedStyle(document.documentElement).overflow") == "hidden"
            if kind == "distribution":
                edit(page, f"{meal}-vegetarian", index)
            else:
                key = "weight_g" if kind == "weight" else "protein_g"
                edit(page, f"{meal}-min_{key}", 10 + index)
                edit(page, f"{meal}-max_{key}", 30 + index)
            done(page, meal, kind)
            expect(page.locator(f"#{meal}-{kind}-open")).to_be_focused()
    meals = submit(page, captured)["personal"]["meals"]
    for index, meal in enumerate(meals):
        assert meal["distribution"]["vegetarian"] == index
        for key in ("weight_g", "protein_g"):
            assert meal["limits"][f"min_{key}"] == 10 + index
            assert meal["limits"][f"max_{key}"] == 30 + index
    for cancel in ("Avbryt", "Stäng utan att spara", "Escape"):
        page.locator("#breakfast-nutrition-open").click()
        dialog = page.locator("#breakfast-nutrition-dialog")
        dialog.locator(".choice-interval").first.get_by_role("button", name="Återställ standard").click()
        if cancel == "Escape":
            page.keyboard.press("Escape")
        else:
            dialog.get_by_role("button", name=cancel, exact=True).click()
        assert submit(page, captured)["personal"]["meals"][1]["limits"]["min_protein_g"] == 11


def test_ranges_validation_positions_precision_zero_and_reset(choices):
    page, url, captured = choices
    page.goto(url)
    choose_location(page)
    page.locator("#dinner-nutrition-open").click()
    edit(page, "dinner-min_protein_g", 10)
    edit(page, "dinner-max_protein_g", 30)
    track = page.locator("#dinner-nutrition-dialog .interval-track").first
    assert track.evaluate("n=>n.style.getPropertyValue('--start')") == "10%"
    assert track.evaluate("n=>n.style.getPropertyValue('--end')") == "30%"
    for value in ("5", "301", "abc", "-1", "Infinity"):
        edit(page, "dinner-max_protein_g", value)
        done(page, "dinner", "nutrition")
        expect(page.locator("#dinner-nutrition-dialog")).to_be_visible()
        assert page.locator("#dinner-max_protein_g-value").evaluate("n=>!n.checkValidity()")
    edit(page, "dinner-max_protein_g", "30,5")
    edit(page, "dinner-min_carbs_g", "0")
    edit(page, "dinner-max_kcal", "650")
    done(page, "dinner", "nutrition")
    limits = submit(page, captured)["personal"]["meals"][0]["limits"]
    assert limits["max_protein_g"] == 30.5
    assert limits["min_carbs_g"] == 0 and limits["max_carbs_g"] is None
    assert limits["max_kcal"] == 650 and "min_kcal" not in limits
    page.locator("#dinner-nutrition-open").click()
    page.locator("#dinner-nutrition-dialog .choice-interval").first.get_by_role("button", name="Återställ standard").click()
    done(page, "dinner", "nutrition")
    limits = submit(page, captured)["personal"]["meals"][0]["limits"]
    assert limits["min_protein_g"] is None and limits["max_protein_g"] is None
    assert limits["min_carbs_g"] == 0


def test_drag_keyboard_focus_and_modal_scroll(choices):
    page, url, captured = choices
    page.goto(url)
    choose_location(page)
    page.set_viewport_size({"width": 390, "height": 420})
    page.locator("#dinner-weight-open").click()
    dialog = page.locator("#dinner-weight-dialog")
    track = dialog.locator(".interval-track")
    track.scroll_into_view_if_needed()
    rect = track.bounding_box()
    y = rect["y"] + rect["height"] / 2
    for start, end in ((12, rect["width"] * .2), (rect["width"] - 12, rect["width"] * .75)):
        page.mouse.move(rect["x"] + start, y)
        page.mouse.down()
        page.mouse.move(rect["x"] + end, y, steps=8)
        page.mouse.up()
    assert 100 < float(page.locator("#dinner-min_weight_g-value").input_value()) < 1000
    assert 1500 < float(page.locator("#dinner-max_weight_g-value").input_value()) < 2800
    before = float(page.locator("#dinner-min_weight_g-value").input_value())
    page.locator("#dinner-min_weight_g").press("ArrowRight")
    assert float(page.locator("#dinner-min_weight_g-value").input_value()) == before + 1
    dialog.get_by_role("button", name="Klart", exact=True).focus()
    page.keyboard.press("Tab")
    expect(dialog.get_by_role("button", name="Stäng utan att spara")).to_be_focused()
    page.keyboard.press("Shift+Tab")
    expect(dialog.get_by_role("button", name="Klart", exact=True)).to_be_focused()
    page.keyboard.press("Escape")
    assert submit(page, captured)["personal"]["meals"][0]["limits"]["min_weight_g"] is None


def test_saved_limits_above_old_scale_and_servings_are_preserved(choices):
    page, url, captured = choices
    draft = {"postal_code": "22350", "personal": {"meals": [
        {"meal_type": "dinner", "count": 5, "servings": 8,
         "limits": {"min_protein_g": 120, "max_protein_g": 150, "max_carbs_g": 450}}]}}
    page.add_init_script("sessionStorage.setItem('smako.personal.requestDraft', "
                         + json.dumps(json.dumps(draft)) + ");")
    page.goto(url)
    choose_location(page)
    page.locator("#dinner-nutrition-open").click()
    expect(page.locator("#dinner-min_protein_g-value")).to_have_value("120")
    expect(page.locator("#dinner-max_protein_g-value")).to_have_value("150")
    expect(page.locator("#dinner-max_protein_g")).to_have_attribute("max", "150")
    page.keyboard.press("Escape")
    meal = submit(page, captured)["personal"]["meals"][0]
    assert meal["servings"] == 8
    assert (meal["limits"]["min_protein_g"], meal["limits"]["max_carbs_g"]) == (120, 450)


@pytest.mark.parametrize("seed", [None, {
    "postal_code": "22350", "max_stores": 3, "memberships": ["COOP_MEMBER"],
    "recipe_preferences": {"mode": "complete", "cuisines": ["italian", "swedish"],
                           "cuisine_distribution": "free", "allow_fish": False},
    "personal": {"organic_percent": 20, "organic_animals": True,
                 "surplus_mode": "allow_larger", "profile": {"allergies": ["jordnötter"]},
                 "extras": [], "meals": [
                     {"meal_type": "dinner", "count": 5, "servings": 3,
                      "distribution": {"vegetarian": 2, "chicken": 2, "fish": 0},
                      "limits": {"min_protein_g": 30.5, "max_weight_g": 650},
                      "recipe_choices": {"min_ingredients": 3, "max_ingredients": 8},
                      "max_same_base_meals": 2},
                     {"meal_type": "breakfast", "count": 2, "servings": 1,
                      "limits": {"max_carbs_g": 65}, "recipe_choices": {"max_active_minutes": 15}},
                     {"meal_type": "snack", "count": 1, "servings": 2,
                      "limits": {"max_kcal": 400}, "organic_animals": True}]}}])
def test_request_parity_against_pre_change_frontend(choices, seed):
    """Run the actual old serializer and compare all request fields, not a copy."""
    page, url, captured = choices
    root = Path(__file__).resolve().parents[2]
    old = {}
    for name in ("personal.html", "personal.js"):
        old[name] = subprocess.check_output(
            ["git", "show", f"ad23943:backend/app/static/{name}"], cwd=root).decode("utf-8")
    page.route("**/personal.html*", lambda route: route.fulfill(
        body=old["personal.html"], content_type="text/html"))
    page.route("**/static/personal.js*", lambda route: route.fulfill(
        body=old["personal.js"], content_type="application/javascript"))
    page.add_init_script("sessionStorage.clear();localStorage.clear();" + (
        "sessionStorage.setItem('smako.personal.requestDraft', " + json.dumps(json.dumps(seed)) + ");"
        if seed else ""))
    page.goto(url)
    choose_location(page)
    page.locator("#generate-plan").click()
    expect(page.locator("#personal-status")).to_contain_text("Testet fångar")
    before = captured[-1]
    page.unroute("**/personal.html*")
    page.unroute("**/static/personal.js*")
    page.reload()
    choose_location(page)
    after = submit(page, captured)
    if seed is None:
        # Membership intentionally changes only the initial guest menu size.
        before["recipes"], before["servings"] = 3, 2
        dinner = next(m for m in before["personal"]["meals"] if m["meal_type"] == "dinner")
        dinner["count"], dinner["servings"] = 3, 2
    # The old UI omitted this field; the API interpreted it as True. The
    # visible pantry choice now serializes that same default explicitly.
    assert "use_pantry" not in before["personal"]
    assert PlanRequest.model_validate(before).personal.use_pantry is True
    assert after["personal"]["use_pantry"] is True
    before["personal"]["use_pantry"] = True
    assert before == after


@pytest.mark.parametrize("status", [401, 403, 500])
def test_backend_error_keeps_choices_and_never_falls_back(choices, status):
    page, url, captured = choices
    page.goto(url)
    choose_location(page)
    edit(page, "dinner-count", 3)
    failed = []

    def reject(route):
        failed.append(route.request.post_data_json)
        route.fulfill(status=status, content_type="application/json",
                      headers={"X-Plan-Request-ID": route.request.headers["x-request-id"]},
                      body=json.dumps({"detail": "Testservern avvisade begäran."}))

    page.route("**/api/plans", reject)
    page.locator("#choice-submit").click()
    expect(page.locator("#personal-status")).not_to_be_empty()
    expect(page.locator("#choice-submit")).to_be_enabled()
    expect(page.locator("#dinner-count-value")).to_have_value("3")
    assert len(failed) == 1
    assert not captured
    expect(page.locator("#plan-content")).to_be_empty()


def test_profile_review_does_not_replace_confirmed_hard_requirements(choices):
    page, url, _captured = choices
    page.route("**/api/personal/interpret-profile", lambda route: route.fulfill(
        content_type="application/json", body=json.dumps({
            "profile": {"likes": ["kyckling"], "dislikes": [], "exclusions": [], "allergies": []},
            "unresolved": []})))
    page.goto(url)
    choose_location(page)
    page.locator("#extra-choices>summary").click()
    page.locator("#profile-allergies").fill("jordnötter")
    page.locator("#profile-exclusions").fill("fisk")
    page.locator("#profile-text").fill("Gillar kyckling")
    page.locator("#interpret-profile").click()
    expect(page.locator("#review-allergies")).to_have_value("jordnötter")
    expect(page.locator("#review-exclusions")).to_have_value("fisk")
    expect(page.locator("#profile-likes")).to_have_value("")
    page.locator("#personal-dialog").get_by_role("button", name="Tillämpa granskade val").click()
    expect(page.locator("#profile-likes")).to_have_value("kyckling")
    expect(page.locator("#profile-allergies")).to_have_value("jordnötter")


def test_snack_without_breakfast_and_zero_dinners(choices):
    page, url, captured = choices
    page.goto(url)
    choose_location(page)
    edit(page, "dinner-count", 0)
    page.locator("#choice-submit").click()
    expect(page.locator("#personal-status")).to_contain_text("minst ett måltidstillfälle")
    assert not captured
    page.locator("#extra-choices>summary").click()
    page.locator("#enable-snack").check()
    expect(page.locator("#breakfast-meals")).not_to_be_visible()
    expect(page.locator("#snack-meals")).to_be_visible()
    request = submit(page, captured)
    assert [m["count"] for m in request["personal"]["meals"]] == [0, 0, 3]


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
@pytest.mark.usefixtures("verified_smako_member")
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
