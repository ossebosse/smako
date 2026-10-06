"""Real browser acceptance against an isolated Smako app; real planner jobs. Optional faults affect transport/lifecycle only.

Examples:
  py -3.12 scripts/release_verification/complete_recipe_browser.py --base http://127.0.0.1:8087 --output .local/recipe-browser --browser both --viewport both --view both --allow-nutrition-estimates

The optional restart handshake writes restart-ready-CASE.json. Restart the
isolated app externally, then write restart-continue-CASE.json containing the
same run_id. The browser, owner session and immutable revision checks persist.
This runner never restarts services or changes production configuration.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

from playwright.sync_api import Error as BrowserError
from playwright.sync_api import TimeoutError as BrowserTimeout
from playwright.sync_api import expect, sync_playwright


def dump(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def digest(envelope):
    return hashlib.sha256(json.dumps({"plan": envelope["plan"], "request": envelope["request"]},
                                     sort_keys=True).encode()).hexdigest()


def is_operation_response(response):
    path = urlsplit(response.url).path
    return (response.request.method == "POST" and
            (path in {"/api/plans", "/api/plan"} or path.endswith(("/change", "/replace-recipe")))) or path.startswith(("/api/plan-jobs/", "/api/plan-job-requests/"))


def record_response(response, observed):
    """Retain real response data before an intentional reload releases it.

    A cancelled poll is transport evidence, not a planner failure. Keep it and
    await the ordinary resumed job polling; never fabricate a terminal result.
    """
    if not is_operation_response(response):
        return
    body, error = None, None
    try:
        body = response.json()
    except BrowserError as exc:
        error = str(exc)
    observed.append(SimpleNamespace(
        url=response.url, status=response.status, headers=response.headers,
        request=SimpleNamespace(method=response.request.method,
            post_data_json=response.request.post_data_json, timing=response.request.timing),
        captured_body=body, body_error=error,
    ))


def wait_operation(page, observed, begin, *, timeout, reload_after=None, offline_seconds=0, fault=None):
    started = time.monotonic()
    consumed = begin
    rows, terminal, pending_urls = [], None, set()
    reloaded = False
    network_interrupted = False
    while time.monotonic() - started < timeout:
        while consumed < len(observed):
            response = observed[consumed]
            consumed += 1
            if not is_operation_response(response):
                continue
            body = response.captured_body
            row = {"url": response.url, "method": response.request.method, "status": response.status,
                   "request_id": response.headers.get("x-request-id"),
                   "error_code": response.headers.get("x-error-code"),
                   "response_ms": response.request.timing.get("responseEnd"),
                   "observed_after_seconds": round(time.monotonic() - started, 3)}
            if response.body_error:
                row.update(body_available=False, transport_error=response.body_error)
                rows.append(row)
                continue
            if response.status == 202:
                pending_urls.add(body["status_url"])
                row["stage"] = body.get("stage")
            else:
                terminal = (response, body)
            rows.append(row)
        if terminal:
            break
        if fault and pending_urls:
            scenario=fault['scenario']
            if scenario in {'away','hidden'} and not fault.get('lifecycle_done'):
                if scenario=='away':
                    page.goto(fault['away_url'],wait_until='domcontentloaded');page.go_back(wait_until='domcontentloaded')
                else:
                    page.evaluate("Object.defineProperty(document,'hidden',{configurable:true,get:()=>true});document.dispatchEvent(new Event('visibilitychange'))")
                    page.wait_for_timeout(1000)
                    page.evaluate("Object.defineProperty(document,'hidden',{configurable:true,get:()=>false});document.dispatchEvent(new Event('visibilitychange'))")
                fault['lifecycle_done']=True
            if scenario=='long-outage' and fault.get('aborts',0)>=8 and not fault.get('manual_resume'):
                control=page.get_by_role('button',name='Återuppta statuskontrollen',exact=True).last
                if control.is_visible() and control.is_enabled():
                    fault['enabled']=False;control.click();fault['manual_resume']=True
            if scenario=='timeout' and fault.get('held_at') and time.monotonic()-fault['held_at']>22:
                for route in fault.pop('held',[]):
                    try:route.abort('timedout')
                    except BrowserError:pass
        can_reload=not fault or fault['scenario']!='delayed-reload' or fault.get('held_at')
        if can_reload and pending_urls and reload_after is not None and not reloaded and time.monotonic() - started >= reload_after:
            page.reload(wait_until="domcontentloaded")
            reloaded = True
            if fault and fault['scenario']=='delayed-reload':
                fault['reloaded_with_inflight']=True
                for route in fault.pop('held',[]):
                    try:route.abort('aborted')
                    except BrowserError:pass
        if pending_urls and offline_seconds and not network_interrupted and (reload_after is None or reloaded):
            page.context.set_offline(True)
            try:
                page.wait_for_timeout(offline_seconds * 1000)
            finally:
                page.context.set_offline(False)
            network_interrupted = True
        page.wait_for_timeout(250)
    if terminal is None:
        raise AssertionError(f"No terminal planning response in {timeout} seconds; transport={rows[-4:]}")
    response, body = terminal
    envelope = body.get("saved", body)
    result = {"seconds": round(time.monotonic() - started, 3), "status": response.status,
              "transport": rows, "job_count": len(pending_urls), "reloaded_during_job": reloaded,
              "browser_network_interrupted_seconds": offline_seconds if network_interrupted else 0,
              "longer_than_minute": time.monotonic() - started > 60,
              "expensive_post_count": sum(row["method"] == "POST" for row in rows),
              "all_status_gets_under_10_seconds": all((row["response_ms"] or 0) < 10000
                                                      for row in rows if row["method"] == "GET" and row.get("body_available", True)),
              "unavailable_transport_bodies": sum(not row.get("body_available", True) for row in rows)}
    return result, envelope


def read_saved(context, base, plan_id, revision=None):
    url = f"{base}/api/plans/{plan_id}"
    if revision is not None:
        url += f"?revision={revision}"
    response = context.request.get(url, timeout=30000)
    assert response.ok, f"Saved readback returned {response.status}"
    return response.json()


def observe_layout(page):
    return page.evaluate("""() => ({
      viewport: {width:innerWidth,height:innerHeight},
      documentWidth:document.documentElement.scrollWidth,
      noHorizontalPageOverflow:document.documentElement.scrollWidth <= innerWidth,
      skipLink:(()=>{const el=document.querySelector('.skip-link');if(!el)return null;const r=el.getBoundingClientRect();return {focused:el===document.activeElement,top:r.top,bottom:r.bottom,overlapsViewport:r.bottom>0&&r.top<innerHeight};})(),
      overflowingControls:[...document.querySelectorAll('input,select,button')].filter(el=>{
        const r=el.getBoundingClientRect();return r.width && getComputedStyle(el).visibility!=='hidden' && (r.right>innerWidth+1||r.left < -1);
      }).map(el=>({id:el.id,text:(el.textContent||'').slice(0,100)}))
    })""")


def wait_render(page, personal):
    if personal:
        expect(page.locator("#plan-content h1")).to_have_text("Din plan", timeout=15000)
        expect(page.locator("#generate-plan")).to_be_enabled(timeout=15000)
    else:
        expect(page.locator("#results")).to_be_visible(timeout=15000)
        expect(page.locator("#submit-button")).to_be_enabled(timeout=15000)


def open_recipes(page, personal):
    if personal:
        summaries = page.locator("#plan-content details > summary").filter(has_text="Öppna recept")
    else:
        summaries = page.locator("#recipes-list .recipe-card > summary")
    for summary in summaries.all():
        if summary.evaluate("el=>!el.parentElement.open"):
            summary.click()
    return summaries.count()


def assert_recipe_result(envelope, args):
    plan = envelope["plan"]
    recipes = plan["recipes"]
    basket = plan["optimized_basket"]
    assert len(recipes) == args.dinners and all(recipe["servings"] == args.servings for recipe in recipes)
    assert 0 <= basket["store_count"] <= args.max_stores
    assert basket["total_reconciled"] and basket["verification_status"] in {"VERIFIED", "VERIFIED_WITH_ESTIMATES"}
    for recipe in recipes:
        assert recipe["ingredients"] and recipe["instructions"] and all(step.strip() for step in recipe["instructions"])
        assert all(ingredient["quantity"] > 0 and ingredient["unit"] for ingredient in recipe["ingredients"])
        if args.recipe_mode == "complete":
            design = recipe["design"]
            assert args.min_ingredients <= design["ingredient_count"] <= args.max_ingredients
            if args.cuisines:
                assert set(design["cuisines"]) & set(args.cuisines)
            if args.max_minutes:
                assert design["estimated_minutes"] <= args.max_minutes
            if not args.allow_fish:
                assert design["fish"] is False
            assert design["base_id"] and design["version"] and design["variant_id"]
    if args.recipe_mode == "complete":
        preferences = envelope["request"]["recipe_preferences"]
        assert set(preferences["cuisines"]) == set(args.cuisines)
        assert preferences["min_ingredients"] == args.min_ingredients
        assert preferences["max_ingredients"] == args.max_ingredients
        assert preferences["max_minutes"] == args.max_minutes
        assert preferences["min_protein_g"] == args.min_protein
        expected_distribution = "minimum" if args.more_variety else args.cuisine_distribution
        assert preferences.get("cuisine_distribution", "free") == expected_distribution
        if expected_distribution == "minimum":
            assert preferences["min_distinct_cuisines"] == (3 if args.more_variety else args.min_distinct_cuisines)
        assert preferences.get("max_same_main_protein_dinners") == (2 if args.more_variety else args.main_protein_cap)
        distribution = plan["personal"]["checks"]["week_distribution"]
        if expected_distribution == "minimum":
            assert distribution["distinct_cuisines"] >= (3 if args.more_variety else args.min_distinct_cuisines)
        elif expected_distribution == "each_selected":
            assert set(args.cuisines) <= set(distribution["cuisines"])
        cap = 2 if args.more_variety else args.main_protein_cap
        if cap is not None:
            assert all(count <= cap for count in distribution["main_proteins"].values())
        if args.min_protein is not None:
            nutrition = plan["personal"]["checks"]["nutrition"]
            assert len(nutrition) == args.dinners
            assert all(row["values"]["protein_g"] >= args.min_protein for row in nutrition)
    return {"recipe_names": [recipe["name"] for recipe in recipes], "total": basket["total"],
            "store_count": basket["store_count"], "verification_status": basket["verification_status"],
            "used_ingredient_cost": plan.get("personal", {}).get("checks", {}).get("used_ingredient_cost"),
            "estimated_rows": sum(row.get("quantity_confidence") == "estimated" for store in basket["stores"] for row in store["items"]),
            "campaign_rows": sum(row.get("price_mechanism") not in {None, "regular"} or bool(row.get("group_applications"))
                                 for store in basket["stores"] for row in store["items"])}


def run_case(browser, engine, mobile, personal, args):
    case = f"{engine}-{'mobile' if mobile else 'desktop'}-{'personal' if personal else 'public'}"
    target = args.output / case
    target.mkdir(parents=True, exist_ok=True)
    report = {"case": case, "base": args.base, "started_utc": datetime.now(UTC).isoformat(),
              "physical_device_test": False, "mocked_routes": False, "run_id": uuid.uuid4().hex}
    context = browser.new_context(viewport={"width": 390 if mobile else 1280, "height": 844 if mobile else 900},
                                  is_mobile=mobile, has_touch=mobile, ignore_https_errors=args.ignore_https_errors)
    page = context.new_page()
    observed, errors, failures = [], [], []
    error_events = []
    navigation_events = []
    traces=[];injected=[]
    fault={'scenario':args.transport_fault,'enabled':True,'aborts':0,'away_url':args.base+('/' if personal else '/personal')}
    context.expose_binding('__smakoTrace',lambda source,data:traces.append({**data,'observed_utc':datetime.now(UTC).isoformat()}))
    context.add_init_script("window.addEventListener('smako:plan-transport',e=>{window.__smakoTrace(e.detail).catch(()=>{});});")
    def inject(route):
        req=route.request;path=urlsplit(req.url).path
        scenario=fault['scenario']
        if scenario=='lost-start' and req.method=='POST' and path=='/api/plans' and not fault.get('accepted'):
            accepted=route.fetch(timeout=30000);body=accepted.json();assert accepted.status==202
            fault['accepted']=body['status_url']
            injected.append({'kind':'lost_accepted_start_response','job_url':body['status_url'],'request_id':req.headers.get('x-request-id'),'at_utc':datetime.now(UTC).isoformat()})
            observed.append(SimpleNamespace(url=req.url,status=accepted.status,headers=accepted.headers,request=SimpleNamespace(method=req.method,post_data_json=req.post_data_json,timing=req.timing),captured_body=body,body_error=None))
            route.abort('connectionreset');return
        if path.startswith('/api/plan-jobs/') and fault['enabled']:
            if scenario in {'reset','long-outage'} and (not fault['aborts'] or scenario=='long-outage'):
                fault['aborts']+=1;injected.append({'kind':'connectionreset','url':req.url,'request_id':req.headers.get('x-request-id'),'at_utc':datetime.now(UTC).isoformat()});route.abort('connectionreset');return
            if scenario in {'delayed-reload','timeout'} and not fault.get('held_at'):
                accepted=route.fetch(timeout=30000);assert accepted.status in {202,201}
                fault['held_at']=time.monotonic();fault['held']=[route]
                injected.append({'kind':'delayed_real_status_response','url':req.url,'request_id':req.headers.get('x-request-id'),'backend_status':accepted.status,'at_utc':datetime.now(UTC).isoformat()});return
        route.continue_()
    if args.transport_fault!='none':context.route('**/api/**',inject)
    def record_page_error(error):
        errors.append(str(error))
        error_events.append({"message": str(error), "stack": getattr(error, "stack", None),
                             "at_utc": datetime.now(UTC).isoformat(), "page_url": page.url})
    page.on("response", lambda response: record_response(response, observed))
    page.on("pageerror", record_page_error)
    page.on("framenavigated", lambda frame: navigation_events.append(
        {"at_utc": datetime.now(UTC).isoformat(), "url": frame.url}) if frame.parent_frame is None else None)
    page.on("requestfailed", lambda request: failures.append({"url": request.url, "method": request.method, "failure": request.failure}))
    try:
        page.goto(args.base + ("/personal" if personal else "/"), wait_until="domcontentloaded")
        if personal:
            expect(page.locator("#generate-plan")).to_be_enabled(timeout=30000)
            page.locator('[data-open="choices"]').first.click()
        elif page.locator("#onboarding-dialog").is_visible():
            page.locator("#onboarding-cta").click()
        page.locator("#postal-code").fill(args.postal_code)
        page.locator("#max-stores").select_option(str(args.max_stores))
        page.locator("#purchase-planning-mode").select_option(args.purchase_mode)
        if personal:
            page.locator("#dinner-count").fill(str(args.dinners))
            page.locator("#dinner-servings").fill(str(args.servings))
            page.locator("#dinner-diet").select_option(args.diet)
            page.locator("#mode").select_option(args.mode)
            page.locator("#allow-nutrition-estimates").set_checked(args.allow_nutrition_estimates)
            if args.exclusions:
                page.locator("#profile-exclusions").fill(", ".join(args.exclusions))
        else:
            page.locator("#recipes").select_option(str(args.dinners))
            page.locator("#servings").fill(str(args.servings))
            page.locator("#diet-preference").select_option(args.diet)
            page.locator("#diversity-" + args.mode).check()
            if args.memberships or args.exclusions:
                page.locator("details.advanced-options > summary").click()
            if args.exclusions:
                page.locator("#excluded-ingredients").fill(", ".join(args.exclusions))
        for membership in args.memberships:
            page.locator(f'input[name="membership"][value="{membership}"]').check()
        if args.recipe_mode == "complete":
            expect(page.locator("#recipe-style")).to_be_visible(timeout=30000)
            page.locator("#recipe-style").select_option("complete")
            for cuisine in args.cuisines:
                page.locator("#cuisine-" + cuisine).check()
            if args.more_variety:
                page.get_by_role("button", name=re.compile("Mer omväxling")).click()
                assert page.locator("#recipe-cuisine-distribution").input_value() == "minimum"
                assert page.locator("#recipe-min-cuisines").input_value() == "3"
                assert page.locator("#recipe-main-protein-cap").input_value() == "2"
            else:
                page.locator("#recipe-cuisine-distribution").select_option(args.cuisine_distribution)
                if args.cuisine_distribution == "minimum":
                    page.locator("#recipe-min-cuisines").fill(str(args.min_distinct_cuisines))
                if args.main_protein_cap is not None:
                    page.locator("#recipe-main-protein-cap").fill(str(args.main_protein_cap))
            page.locator("#recipe-ingredient-preset").select_option("custom")
            page.locator("#recipe-min-ingredients").fill(str(args.min_ingredients))
            page.locator("#recipe-max-ingredients").fill(str(args.max_ingredients))
            if args.max_minutes:
                page.locator("#recipe-max-minutes").fill(str(args.max_minutes))
            if args.min_protein is not None:
                page.locator("#recipe-min-protein").fill(str(args.min_protein))
            page.locator("#recipe-adaptation").select_option(args.adaptation)
            page.locator("#recipe-allow-fish").set_checked(args.allow_fish)
            for store_context in args.store_contexts:
                page.locator(f'#recipe-price-contexts input[value="{store_context}"]').check()
            if not personal:
                page.locator("#recipe-nutrition-estimates").set_checked(args.allow_nutrition_estimates)
        page.screenshot(path=str(target / "choices.png"), full_page=True)
        report["form_layout"] = observe_layout(page)
        assert report["form_layout"]["noHorizontalPageOverflow"]
        start = len(observed)
        clicked_at = time.monotonic()
        page.locator("#generate-plan" if personal else "#submit-button").dblclick()
        generation, envelope = wait_operation(page, observed, start, timeout=args.timeout, reload_after=args.reload_after, offline_seconds=args.offline_seconds, fault=fault)
        report["generation"] = generation
        submitted = next((response.request.post_data_json for response in observed[start:]
                          if response.request.method == "POST" and urlsplit(response.url).path == "/api/plans"), None)
        report["submitted_request"] = submitted
        dump(target / "generated.json", envelope)
        assert generation["status"] < 400, envelope
        assert generation["expensive_post_count"] == 1
        assert generation["all_status_gets_under_10_seconds"]
        if args.require_long_job:
            assert generation["longer_than_minute"], "Generation was faster than one minute; long-job condition not exercised"
        if args.require_pending_reload:
            assert generation["reloaded_during_job"], "Generation completed before a pending-job reload"
        report["acceptance"] = assert_recipe_result(envelope, args)
        wait_render(page, personal)
        generation['click_to_render_seconds'] = round(time.monotonic() - clicked_at, 3)
        assert open_recipes(page, personal) == args.dinners
        report["recipe_text"] = page.locator("#plan-content" if personal else "#recipes-list").inner_text()
        if args.expect_refined_recipes:
            assert not re.search(r'\d+\.\d{6,}', report['recipe_text']), 'Raw numeric artifact visible'
            assert 'Huvudproteinkälla: Vegetariska' not in report['recipe_text']
            assert 'Protein före visningsavrundning' not in report['recipe_text']
            assert page.locator('.recipe-nutrition-info:visible').count() == args.dinners
            for method in page.locator('.complete-recipe-method:visible').all():
                assert 'Endast dricksvatten får tillkomma' not in method.inner_text()
                assert 'inte ett provlagningsresultat' not in method.inner_text()
            report['refined_recipe_text_checked'] = True
        report["recipe_layout"] = observe_layout(page)
        assert report["recipe_layout"]["noHorizontalPageOverflow"]
        skip_link = report["recipe_layout"]["skipLink"]
        assert not skip_link or skip_link["focused"] or not skip_link["overlapsViewport"]
        if args.recipe_mode == "complete":
            assert page.locator(".complete-recipe-content:visible").count() == args.dinners
            assert page.locator(".recipe-component:visible").count() >= args.dinners
            page.locator(".complete-recipe-content:visible").first.screenshot(path=str(target / "first-recipe.png"))
            page.locator(".complete-recipe-content:visible").first.evaluate("el=>el.scrollIntoView({block:'start',behavior:'instant'})")
            page.screenshot(path=str(target / "first-recipe-viewport.png"))
        page.locator("#plan-content" if personal else "#menu-section").screenshot(path=str(target / "recipes.png"))
        if personal:
            page.get_by_role("button", name="Öppna inköpslistan", exact=True).click()
        report["shopping_text"] = page.locator("#shopping-content" if personal else "#shopping-section").inner_text()
        page.locator("#shopping-content" if personal else "#shopping-section").screenshot(path=str(target / "shopping.png"))
        originals = {envelope["revision"]: envelope}
        assert digest(read_saved(context, args.base, envelope["plan_id"])) == digest(envelope)
        if args.recipe_mode == "complete":
            if personal:
                page.locator('.personal-nav [data-open="plan"]').click()
            open_recipes(page, personal)
            page.get_by_role("button", name="Så blev rätten", exact=True).first.click()
            page.locator("#recipe-feedback-taste").select_option("4")
            page.locator("#recipe-feedback-difficulty").select_option("2")
            page.locator("#recipe-feedback-portion").select_option("right")
            page.locator("#recipe-feedback-minutes").fill("37")
            page.locator(".complete-feedback-dialog textarea").fill(
                "Automatiserat gränssnittsprov i isolerad miljö. Betyg och tid är syntetiska testvärden; detta är inte provlagning.")
            with page.expect_response(lambda response: response.request.method == "POST" and urlsplit(response.url).path == "/api/feedback") as received:
                page.locator(".complete-feedback-dialog button[type=submit]").click()
            feedback_response = received.value
            expected = {"revision": envelope["revision"], "recipe_index": 0, "taste": 4, "difficulty": 2,
                        "portion_size": "right", "actual_minutes": 37}
            assert feedback_response.status == 201
            assert feedback_response.request.post_data_json["recipe_feedback"] == expected
            expect(page.locator(".complete-feedback-dialog [role=status]")).to_contain_text("receptversionen")
            report["recipe_feedback"] = {"request": expected, "response": feedback_response.json(),
                                         "expected_bound_design": envelope["plan"]["recipes"][0]["design"],
                                         "synthetic_ratings_not_cooking_evidence": True,
                                         "persisted_binding_requires_feedback_store_readback": True}
            page.locator(".complete-feedback-dialog").get_by_role("button", name="Stäng", exact=True).click()
            assert digest(read_saved(context, args.base, envelope["plan_id"])) == digest(envelope)
        page.reload(wait_until="domcontentloaded")
        wait_render(page, personal)
        report["identical_saved_reload"] = digest(read_saved(context, args.base, envelope["plan_id"])) == digest(envelope)
        assert report["identical_saved_reload"]
        if not args.skip_mutations:
            if personal:
                page.locator('.personal-nav [data-open="plan"]').click()
            open_recipes(page, personal)
            previous = envelope
            start = len(observed)
            page.get_by_role("button", name="Byt recept och räkna om inköpen", exact=True).first.click()
            replacement, envelope = wait_operation(page, observed, start, timeout=args.timeout)
            report["replacement"] = replacement
            dump(target / "replacement.json", envelope)
            assert replacement["status"] < 400, envelope
            assert envelope["plan_id"] == previous["plan_id"] and envelope["revision"] > previous["revision"]
            assert envelope["plan"]["recipes"] != previous["plan"]["recipes"]
            if args.recipe_mode == "complete":
                report["replacement_changed_base_recipe"] = (
                    envelope["plan"]["recipes"][0]["design"]["base_id"] != previous["plan"]["recipes"][0]["design"]["base_id"])
                assert report["replacement_changed_base_recipe"], "Automatic recipe replacement returned another variant of the same base dish"
            assert_recipe_result(envelope, args)
            originals[envelope["revision"]] = envelope
            wait_render(page, personal)
            previous = envelope
            start = len(observed)
            page.get_by_role("button", name="Räkna om med aktuellt skafferi/pris" if personal else "Räkna om inköpslistan", exact=True).click()
            recalculation, envelope = wait_operation(page, observed, start, timeout=args.timeout)
            report["recalculation"] = recalculation
            dump(target / "recalculated.json", envelope)
            assert recalculation["status"] < 400, envelope
            assert envelope["plan_id"] == previous["plan_id"] and envelope["revision"] > previous["revision"]
            assert_recipe_result(envelope, args)
            originals[envelope["revision"]] = envelope
            wait_render(page, personal)
        report["revision_hashes"] = {str(revision): digest(value) for revision, value in originals.items()}
        for revision, value in originals.items():
            assert digest(read_saved(context, args.base, envelope["plan_id"], revision)) == digest(value)
        if args.restart_handshake:
            ready = args.output / f"restart-ready-{case}.json"
            resume = args.output / f"restart-continue-{case}.json"
            dump(ready, {"run_id": report["run_id"], "case": case, "plan_id": envelope["plan_id"],
                         "revision_hashes": report["revision_hashes"], "continue_path": str(resume)})
            print(json.dumps({"waiting_for_isolated_restart": str(ready), "run_id": report["run_id"]}), flush=True)
            deadline = time.monotonic() + args.timeout
            while time.monotonic() < deadline:
                try:
                    if json.loads(resume.read_text(encoding="utf-8"))["run_id"] == report["run_id"]:
                        break
                except (FileNotFoundError, ValueError, KeyError):
                    pass
                page.wait_for_timeout(500)
            else:
                raise AssertionError("Isolated restart handshake not completed")
            page.reload(wait_until="domcontentloaded")
            wait_render(page, personal)
            for revision, value in originals.items():
                assert digest(read_saved(context, args.base, envelope["plan_id"], revision)) == digest(value)
            report["identical_after_external_app_restart"] = True
            if args.expect_flag_off_after_restart:
                metadata = context.request.get(args.base + "/api/recipe-library", timeout=30000).json()
                assert metadata["enabled"] is False
                expect(page.locator("#recipe-style")).to_be_hidden(timeout=15000)
                assert open_recipes(page, personal) == args.dinners
                assert page.locator(".complete-recipe-content:visible").count() == args.dinners
                report["saved_recipes_readable_with_feature_disabled"] = True
                page.screenshot(path=str(target / "flag-off-saved-plan.png"), full_page=True)
        # A separate clean owner must not gain access to the saved private result.
        other = browser.new_context(ignore_https_errors=args.ignore_https_errors)
        other.request.get(args.base + "/", timeout=30000)
        denied = other.request.get(f"{args.base}/api/plans/{envelope['plan_id']}", timeout=30000)
        report["other_owner_status"] = denied.status
        assert denied.status in {403, 404}
        job_urls = {response.url for response in observed if urlsplit(response.url).path.startswith("/api/plan-jobs/")}
        report["other_owner_job_statuses"] = [other.request.get(url, timeout=30000).status for url in sorted(job_urls)]
        assert all(status in {403, 404} for status in report["other_owner_job_statuses"])
        other.close()
        assert not errors, errors
        report["outcome"] = "PASS"
    except Exception as error:  # noqa: BLE001 - retain first-stop evidence even for unexpected browser errors
        report["outcome"] = "FAIL"
        report["first_stop"] = str(error)
        try:
            report["failure_visible_text"] = page.locator("body").inner_text(timeout=3000)
            report["failure_form"] = page.locator("#personal-form input, #personal-form select, #plan-form input, #plan-form select").evaluate_all(
                "nodes=>nodes.map(n=>({id:n.id,name:n.name,type:n.type,value:n.value,checked:n.checked,disabled:n.disabled}))")
            report["failure_layout"] = observe_layout(page)
            report["failure_submit_enabled"] = page.locator("#generate-plan" if personal else "#submit-button").is_enabled()
            values = {row["id"]: row["value"] for row in report["failure_form"] if row["id"]}
            report["failure_core_choices_retained"] = (
                values.get("dinner-servings" if personal else "servings") == str(args.servings)
                and values.get("max-stores") == str(args.max_stores)
                and (args.recipe_mode != "complete" or (
                    values.get("recipe-style") == "complete"
                    and values.get("recipe-min-ingredients") == str(args.min_ingredients)
                    and values.get("recipe-max-ingredients") == str(args.max_ingredients)
                    and {row["value"] for row in report["failure_form"] if row["id"].startswith("cuisine-") and row["checked"]} == set(args.cuisines))))
            page.screenshot(path=str(target / "failure.png"), full_page=True, timeout=10000)
        except BrowserTimeout:
            pass
    finally:
        report['transport_fault']=args.transport_fault
        report['injected_events']=injected
        report['transport_lifecycle_events']=traces
        report['fault_assertions']={k:v for k,v in fault.items() if k not in {'held','away_url'}}
        report["page_errors"] = errors
        report["page_error_events"] = error_events
        report["navigation_events"] = navigation_events
        report["network_failures"] = failures
        report["finished_utc"] = datetime.now(UTC).isoformat()
        dump(target / "report.json", report)
        print(json.dumps({"case": case, "outcome": report["outcome"], "first_stop": (report.get("first_stop") or "")[:500],
                          "seconds": report.get("generation", {}).get("seconds"), "report": str(target / "report.json")}), flush=True)
        context.close()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--output", type=Path, required=True, help="Private ignored evidence directory")
    parser.add_argument("--browser", choices=["chromium", "webkit", "both"], default="chromium")
    parser.add_argument("--viewport", choices=["desktop", "mobile", "both"], default="mobile")
    parser.add_argument("--view", choices=["public", "personal", "both"], default="public")
    parser.add_argument("--postal-code", default="22350")
    parser.add_argument("--dinners", type=int, default=5)
    parser.add_argument("--servings", type=int, default=2)
    parser.add_argument("--max-stores", type=int, default=2)
    parser.add_argument("--recipe-mode", choices=["legacy", "complete"], default="complete")
    parser.add_argument("--cuisines", nargs="*", default=["greek", "mexican"])
    parser.add_argument("--cuisine-distribution", choices=["free", "minimum", "each_selected"], default="free")
    parser.add_argument("--min-distinct-cuisines", type=int)
    parser.add_argument("--main-protein-cap", type=int)
    parser.add_argument("--more-variety", action="store_true")
    parser.add_argument("--min-ingredients", type=int, default=10)
    parser.add_argument("--max-ingredients", type=int, default=15)
    parser.add_argument("--max-minutes", type=int)
    parser.add_argument("--min-protein", type=float)
    parser.add_argument("--adaptation", choices=["products", "approved"], default="approved")
    parser.add_argument("--allow-fish", action="store_true")
    parser.add_argument("--allow-nutrition-estimates", action="store_true")
    parser.add_argument("--mode", choices=["cheapest", "balanced", "varied"], default="cheapest")
    parser.add_argument("--diet", choices=["mixed", "vegetarian", "vegan"], default="mixed")
    parser.add_argument("--purchase-mode", choices=["exact", "estimated"], default="exact")
    parser.add_argument("--memberships", nargs="*", default=[])
    parser.add_argument("--store-contexts", nargs="*", default=[], help="Exact currently published context IDs to select through the form")
    parser.add_argument("--exclusions", nargs="*", default=[])
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument('--transport-fault',choices=['none','reset','lost-start','delayed-reload','timeout','away','hidden','long-outage'],default='none')
    parser.add_argument("--reload-after", type=float, default=3)
    parser.add_argument("--offline-seconds", type=float, default=0, help="Temporarily disable the browser network during the pending job, at most 30 seconds")
    parser.add_argument("--require-long-job", action="store_true")
    parser.add_argument("--require-pending-reload", action="store_true")
    parser.add_argument("--skip-mutations", action="store_true")
    parser.add_argument("--expect-refined-recipes", action="store_true")
    parser.add_argument("--restart-handshake", action="store_true")
    parser.add_argument("--expect-flag-off-after-restart", action="store_true", help="With restart handshake, require disabled creation controls and readable immutable complete recipes")
    parser.add_argument("--ignore-https-errors", action="store_true")
    parser.add_argument("--allow-nonlocal-isolated-target", action="store_true")
    args = parser.parse_args()
    args.base = args.base.rstrip("/")
    if not 0 <= args.offline_seconds <= 30:
        parser.error("--offline-seconds must be between 0 and 30")
    if args.expect_flag_off_after_restart and not args.restart_handshake:
        parser.error("--expect-flag-off-after-restart requires --restart-handshake")
    if not args.allow_nonlocal_isolated_target and urlsplit(args.base).hostname not in {"localhost", "127.0.0.1", "::1"}:
        parser.error("Use an isolated local app, or explicitly identify a nonlocal isolated target with --allow-nonlocal-isolated-target")
    if args.recipe_mode == "legacy" and not args.skip_mutations:
        parser.error("Legacy long-job coverage uses --skip-mutations; complete revision controls apply to complete mode")
    args.output.mkdir(parents=True, exist_ok=True)
    results = []
    with sync_playwright() as pw:
        for engine in ("chromium", "webkit") if args.browser == "both" else (args.browser,):
            browser = getattr(pw, engine).launch()
            for mobile in (False, True) if args.viewport == "both" else (args.viewport == "mobile",):
                for personal in (False, True) if args.view == "both" else (args.view == "personal",):
                    results.append(run_case(browser, engine, mobile, personal, args))
            browser.close()
    dump(args.output / "summary.json", [{key: row.get(key) for key in ("case", "outcome", "first_stop", "generation", "acceptance")} for row in results])
    raise SystemExit(0 if all(row["outcome"] == "PASS" for row in results) else 1)


if __name__ == "__main__":
    main()
