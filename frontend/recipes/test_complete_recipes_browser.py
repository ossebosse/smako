"""Frontend contract/layout tests with explicitly synthetic API responses.

This does not qualify recipes or claim live end-to-end pricing acceptance.
Run: py -3.12 frontend/recipes/test_complete_recipes_browser.py
"""
from __future__ import annotations

import argparse
import json
import mimetypes
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

STATIC = Path(__file__).resolve().parents[2] / "backend" / "app" / "static"
PROFILE = {"likes": [], "dislikes": [], "exclusions": [], "allergies": []}
STATE = {"revision": 0, "items": [], "reservations": {}, "ledger": [], "profile": PROFILE,
         "account": {"message": "Isolerat frontendprov"}}
JOB = "/api/plan-jobs/" + "a" * 32
DIAGNOSTICS = {"raw_recipe_pool": 20, "singleton_passed": 1, "not_singleton_evaluated": 0,
               "candidate_rejections": [{"stage": "nutrition", "label": "Näringskrav", "rejected": 8}],
               "candidate_details": [{"recipe": "Testbiffar", "stage": "nutrition", "reason": "Befintlig strukturell måltidskontroll: {'violations': ('estimate_confidence_below_minimum',)}"}],
               "search": [{"rejections": {"variation": 1}}], "counting": "Sökningen bevisar inte global omöjlighet."}


def run_case(browser, engine: str, mobile: bool, personal: bool, output: Path):
    context = browser.new_context(viewport={"width": 390 if mobile else 1280, "height": 844},
                                  is_mobile=mobile, has_touch=mobile, service_workers="block")
    page = context.new_page()
    errors, plans, feedback = [], [], []
    mode = {"enabled": True, "async": False, "polls": 0, "done": False}
    page.on("pageerror", lambda error: errors.append(str(error)))

    def route(req):
        path = urlsplit(req.request.url).path
        if path.startswith("/static/"):
            file = STATIC / path.removeprefix("/static/")
            req.fulfill(status=200, body=file.read_bytes(), content_type=mimetypes.guess_type(file)[0] or "text/plain")
            return
        if path in {"/", "/personal"}:
            req.fulfill(status=200, body=(STATIC / ("personal.html" if path == "/personal" else "index.html")).read_bytes(), content_type="text/html")
            return
        if path == "/ready":
            data = {"status": "ready", "build_id": "synthetic-frontend-contract", "features": {"complete_recipes_enabled": mode["enabled"]}}
        elif path == "/api/recipe-library":
            data = {"enabled": mode["enabled"]}
        elif path == "/api/personal/state":
            data = STATE
        elif path == "/api/account/status":
            data = {"status": "GUEST"}
        elif path == "/api/price-contexts":
            data = {"contexts": [{"context_id": "context-one", "display_name": "Testbutik", "price_scope_label": "Butikspris"},
                                 {"context_id": "context-two", "display_name": "Test online", "price_scope_label": "Onlinepris"}]}
        elif path == "/api/feedback":
            feedback.append(req.request.post_data_json)
            data = {"status": "saved"}
        elif path == "/api/plans" and req.request.method == "POST":
            plans.append(req.request.post_data_json)
            if mode["async"]:
                req.fulfill(status=202, json={"status": "pending", "status_url": JOB, "stage": "candidate_qualification"})
                return
            req.fulfill(status=422, json={"detail": "Testets oförenliga val: öka tillagningstiden eller sänk proteinmålet.", "code": "POLICY_CONFLICT", "planning_diagnostics": DIAGNOSTICS})
            return
        elif path == JOB:
            mode["polls"] += 1
            if mode["done"]:
                req.fulfill(status=422, json={"detail": "Det återanslutna testjobbet har avslutats.", "planning_diagnostics": DIAGNOSTICS})
            else:
                req.fulfill(status=202, json={"status": "pending", "status_url": JOB, "stage": "week_search"})
            return
        elif path.startswith("/scanner-assets/"):
            req.fulfill(status=200, content_type="text/javascript", body="")
            return
        else:
            data = {}
        req.fulfill(status=200, json=data)

    page.route("**/*", route)
    page.goto("https://smako.test/personal" if personal else "https://smako.test/")
    if personal:
        page.locator('[data-open="choices"]').first.click()
        expect(page.locator("#generate-plan")).to_be_enabled()
    else:
        page.locator("#onboarding-cta").click()
        expect(page.locator("#submit-button")).to_be_enabled()
    page.locator("#recipe-style").select_option("complete")
    page.locator("#cuisine-greek").check()
    page.locator("#cuisine-mexican").check()
    page.locator("#recipe-max-minutes").fill("40")
    page.locator("#recipe-min-protein").fill("40")
    page.locator("#recipe-allow-fish").uncheck()
    page.locator('#recipe-price-contexts input[value="context-one"]').check()
    page.locator("#recipe-ingredient-preset").select_option("custom")
    page.locator("#recipe-min-ingredients").fill("15")
    page.locator("#recipe-max-ingredients").fill("10")
    assert page.locator("#recipe-max-ingredients").evaluate("el => !el.checkValidity()")
    page.locator("#recipe-ingredient-preset").select_option("10-15")
    page.locator("#allow-nutrition-estimates" if personal else "#recipe-nutrition-estimates").check()
    page.locator("#dinner-servings" if personal else "#servings").fill("2")
    submit = page.locator("#generate-plan" if personal else "#submit-button")
    status = page.locator("#personal-status" if personal else "#error-message")
    submit.click()
    expect(status).to_contain_text("oförenliga val")
    expect(page.locator(".recipe-planning-diagnostics")).to_contain_text("Blockeringsfördelning")
    expect(page.locator(".recipe-planning-diagnostics")).to_contain_text("Näringskrav: 8 avslag")
    expect(page.locator(".recipe-planning-diagnostics")).not_to_contain_text("estimate_confidence_below_minimum")
    assert len(plans) == 1
    assert plans[0]["recipe_preferences"] == {"mode": "complete", "cuisines": ["greek", "mexican"],
                                             "min_ingredients": 10, "max_ingredients": 15, "max_minutes": 40,
                                             "adaptation": "approved", "min_protein_g": 40, "allow_fish": False}
    assert plans[0]["allowed_store_ids"] == ["context-one"]
    assert (plans[0].get("personal") or plans[0])["allow_nutrition_estimates"] is True
    expect(page.locator("#recipe-min-protein")).to_have_value("40")
    expect(page.locator("#cuisine-greek")).to_be_checked()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "horizontal page overflow"
    if output:
        page.screenshot(path=str(output / f"{engine}-{'mobile' if mobile else 'desktop'}-{'personal' if personal else 'public'}.png"), full_page=True)

    page.locator("#recipe-style").select_option("legacy")
    submit.click()
    expect(status).to_contain_text("oförenliga val")
    page.wait_for_function("document.querySelector('#generate-plan, #submit-button').disabled === false")
    assert "recipe_preferences" not in plans[-1]
    assert "allowed_store_ids" not in plans[-1]

    # A real browser reload resumes a synthetic server job using GET, with no duplicate POST.
    mode["async"] = True
    page.locator("#recipe-style").select_option("complete")
    submit.click()
    scope = "personal" if personal else "public"
    page.wait_for_function("scope => sessionStorage.getItem('smako.planJob.' + scope) !== null", arg=scope)
    expected_posts = len(plans)
    mode["done"] = True
    page.reload()
    expect(status).to_contain_text("återanslutna", timeout=10000)
    assert len(plans) == expected_posts and mode["polls"] >= 1
    expect(page.locator("#recipe-style")).to_have_value("complete")
    expect(page.locator("#recipe-min-protein")).to_have_value("40")
    assert page.evaluate("scope => sessionStorage.getItem('smako.planJob.' + scope) === null", scope)

    # Feature off must hide and disable all new constraints even with a complete draft.
    mode["enabled"] = False
    page.reload()
    expect(page.locator("#recipe-style")).not_to_be_visible()
    assert page.evaluate("document.querySelector('.complete-recipe-options').disabled")
    recipe = {
        "name": "Testbiffar med potatis och yoghurtsås", "servings": 2,
        "ingredients": [{"name": "Färs", "canonical_name": "färs", "quantity": 400, "unit": "g", "form": "raw_edible", "component": "main"},
                        {"name": "Potatis", "canonical_name": "potatis", "quantity": 500, "unit": "g", "form": "raw_edible", "component": "side"},
                        {"name": "Yoghurt", "canonical_name": "yoghurt", "quantity": 100, "unit": "g", "form": "as_sold", "component": "sauce", "product_requirements": ["plain", "thick"]},
                        {"name": "Vitlök", "canonical_name": "vitlök", "quantity": 5, "unit": "g", "form": "raw_edible", "component": "main"},
                        {"name": "Vitlök", "canonical_name": "vitlök", "quantity": 5, "unit": "g", "form": "raw_edible", "component": "sauce"},
                        {"name": "Salt", "canonical_name": "salt", "quantity": 2, "unit": "g", "component": "main"}],
        "instructions": ["Tillaga potatisen och forma biffarna.", "Blanda yoghurtsåsen och servera allt tillsammans."],
        "design": {"base_id": "test-recipe", "version": "1.0.0", "variant_id": "base", "cuisines": ["greek"],
                   "ingredient_count": 4, "estimated_minutes": 35, "equipment": ["stekpanna", "ugn"],
                   "components": [{"id": "main", "name": "Biffar"}, {"id": "side", "name": "Potatis"}, {"id": "sauce", "name": "Yoghurtsås"}],
                   "steps": [{"id": "prepare", "duration_minutes": 25, "depends_on": [], "parallel_group": "cook"},
                             {"id": "serve", "duration_minutes": 5, "depends_on": ["prepare"]}],
                   "provenance": {"content_review": "reviewed", "machine_validation": "passed", "cooking_test": "not_cooked"}},
    }
    page.evaluate("""recipe => {
      window.testRecipe=recipe;
      const wrapper=document.createElement('article');wrapper.className='recipe-card';wrapper.style.maxWidth='1120px';wrapper.style.margin='20px auto';
      const content=document.createElement('div');content.className='recipe-content';wrapper.append(content);
      const node=SmakoRecipes.renderRecipe(recipe,{nutrition:{status:'ESTIMATED',values:{protein_g:40.123,kcal:650}}});
      node.id='contract-recipe-card';content.append(node);document.body.append(wrapper);
    }""", recipe)
    card = page.locator("#contract-recipe-card")
    expect(card).to_contain_text("4 ingredienser")
    expect(card).to_contain_text("Provlagning: inte genomförd")
    expect(card).to_contain_text("efter steg 1")
    expect(card).to_contain_text("rå, ätbar mängd")
    expect(card).to_contain_text("mängd som såld")
    expect(card).to_contain_text("naturell · tjock yoghurt, 5–10 % fetthalt")
    expect(card).not_to_contain_text("as_sold")
    assert card.locator(".recipe-component").count() == 3
    assert page.evaluate("SmakoRecipes.ingredientCount(window.testRecipe)") == 4
    ingredient_box = card.locator(".complete-recipe-ingredients").bounding_box()
    method_box = card.locator(".complete-recipe-method").bounding_box()
    assert ingredient_box and method_box
    if mobile:
        assert method_box["y"] >= ingredient_box["y"] + ingredient_box["height"]
    else:
        assert method_box["x"] >= ingredient_box["x"] + ingredient_box["width"]
        assert abs(method_box["y"] - ingredient_box["y"]) < 2
        assert card.bounding_box()["width"] >= 900
    rendered = page.evaluate("""() => {
      const demands=['färs','potatis','yoghurt','vitlök'].map((name,index)=>({name,source:'slot1',demand_key:String(index),quantity:100,original_quantity:100}));
      const personal={remaining_demands:demands,allocations:[{demand_key:'0',quantity:100},{demand_key:'1',quantity:25}],checks:{}};
      const counts=SmakoRecipes.renderRecipe(testRecipe,{personal,slotId:'slot1'}).textContent;
      personal.remaining_demands[0].quantity=0;
      const consumed=SmakoRecipes.renderRecipe(testRecipe,{personal,slotId:'slot1'}).textContent;
      const unknown=SmakoRecipes.renderRecipe(testRecipe,{nutrition:{status:'NOT_REQUESTED',values:{protein_g:null,kcal:null,fat_g:null,carbs_g:null},sources:[{quantity:null}]}}).textContent;
      const knownZero=SmakoRecipes.renderRecipe(testRecipe,{nutrition:{status:'ESTIMATED',values:{protein_g:0}}}).textContent;
      return {counts,consumed,unknown,knownZero};
    }""")
    assert "4 ingredienser: 3 behöver köpas och 1 finns helt hemma" in rendered["counts"]
    assert "Av de 3 som behöver köpas finns 1 redan delvis hemma" in rendered["counts"]
    assert "finns helt hemma" not in rendered["consumed"] and "bokförts som förbrukat" in rendered["consumed"]
    assert "inte beräknad – inget näringsmål valt" in rendered["unknown"]
    assert "Saknade näringsvärden är okända" in rendered["unknown"]
    assert "0 g protein" not in rendered["unknown"] and "0 kcal" not in rendered["unknown"]
    assert "Ingrediens: okänd" in rendered["unknown"]
    assert "Källstatus okänd" in rendered["unknown"] and "Spårbar uppskattning" not in rendered["unknown"]
    assert "0 g protein" in rendered["knownZero"]
    search_status = page.evaluate("""() => {
      const plan={recipes:[testRecipe],personal:{checks:{search_outcome:{budget_message:'En delberäkning nådde sökbudgeten. Menyn är fortfarande helt validerad.'}}}};
      return {cheapest:SmakoRecipes.searchNotice(plan,'cheapest').textContent,balanced:SmakoRecipes.searchNotice(plan,'balanced').textContent,legacy:SmakoRecipes.searchNotice({recipes:[{}]},'cheapest')};
    }""")
    assert "Lägsta hittade inköpskostnad inom dina val" in search_status["cheapest"]
    assert "Menyn är fortfarande helt validerad" in search_status["cheapest"]
    assert "balans mellan pris och variation" in search_status["balanced"]
    assert search_status["legacy"] is None
    page.evaluate("""() => {
      const node=SmakoRecipes.financials({optimized_basket:{total:123.45,verification_status:'VERIFIED'},personal:{allocations:[{name:'Ris',quantity:100,unit:'g'}],checks:{used_ingredient_cost:null,new_purchase_used_cost:100,used_cost_basis:{quantity_status:'VERIFIED',description:'Kostnadsfördelning, utan avdrag på betalningen.'}}}});
      node.id='contract-financials';document.body.append(node);
      const declaration=SmakoRecipes.productDetails({ingredients:[],ingredients_complete:false,allergens_present:[],allergens_trace:[]});declaration.id='contract-declaration';declaration.open=true;document.body.append(declaration);
    }""")
    expect(page.locator("#contract-financials")).to_contain_text("123,45 kr")
    expect(page.locator("#contract-financials")).to_contain_text("Kostnaden för allt som används är okänd")
    expect(page.locator("#contract-financials")).to_contain_text("100 kr")
    expect(page.locator("#contract-declaration")).to_contain_text("Detta bevisar inte frånvaro")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    if output:
        card.screenshot(path=str(output / f"{engine}-{'mobile' if mobile else 'desktop'}-{'personal' if personal else 'public'}-recipe.png"))
    previous_feedback_identity = page.evaluate("localStorage.getItem('grocery-anonymous-session-id')")
    page.evaluate("SmakoRecipes.recipeFeedback({recipe:window.testRecipe,recipeIndex:0,planId:'synthetic-plan',revision:3})")
    page.locator("#recipe-feedback-taste").select_option("5")
    page.locator("#recipe-feedback-difficulty").select_option("2")
    page.locator("#recipe-feedback-portion").select_option("right")
    page.locator("#recipe-feedback-minutes").fill("37")
    page.locator(".complete-feedback-dialog button[type=submit]").click()
    expect(page.locator(".complete-feedback-dialog [role=status]")).to_contain_text("receptversionen")
    assert feedback[-1]["recipe_feedback"] == {"revision": 3, "recipe_index": 0, "taste": 5, "difficulty": 2,
                                              "portion_size": "right", "actual_minutes": 37}
    # Public uses its existing capability; the personal-only flow creates one.
    # Do not write either value to test reports or logs.
    assert len(feedback[-1]["anonymous_session_id"]) >= 32
    assert feedback[-1]["anonymous_session_id"] == page.evaluate("localStorage.getItem('grocery-anonymous-session-id')")
    if previous_feedback_identity:
        assert feedback[-1]["anonymous_session_id"] == previous_feedback_identity
    page.evaluate("SmakoRecipes.clearPrivateDrafts()")
    assert page.evaluate("['smako.planJob.public','smako.planJob.personal','smako.recipeChoices.public','smako.recipeChoices.personal','smako.personal.requestDraft'].every(key=>sessionStorage.getItem(key)===null)")
    assert not errors, errors
    result = {"browser": engine, "mobile_emulation": mobile, "personal": personal,
              "posts": len(plans), "polls_after_reload": mode["polls"], "page_errors": errors,
              "synthetic_api_contract_test": True, "physical_device_test": False}
    context.close()
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path(".local/complete-ui-contract"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    results = []
    with sync_playwright() as pw:
        for engine in ("chromium", "webkit"):
            browser = getattr(pw, engine).launch()
            for mobile in (False, True):
                for personal in (False, True):
                    results.append(run_case(browser, engine, mobile, personal, args.output))
                    print(json.dumps(results[-1]), flush=True)
            browser.close()
    (args.output / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
