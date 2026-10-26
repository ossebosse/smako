"""A real Chromium button-to-shopping-list probe of the ordinary personal UI."""
import hashlib
import json
import re
import secrets
import threading
import time

import uvicorn
from app.services.meal_library_content import encoded
from playwright.sync_api import expect, sync_playwright
from smako_budget_context import arm_phase


def run(app, request, result, args, started, save):
    base = "http://127.0.0.1:18226"
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=18226, lifespan="off", log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.perf_counter() + 15
    while not server.started and time.perf_counter() < deadline:
        time.sleep(0.05)
    assert server.started
    errors, submitted = [], []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            context = browser.new_context(viewport={"width": 1280, "height": 900})
            registration = context.request.post(base + "/api/account/register", headers={"Origin": base},
                data={"email": secrets.token_hex(12) + "@example.invalid", "password": secrets.token_urlsafe(30)})
            assert registration.status == 201
            draft = request.model_dump(mode="json")
            # Use the app's own tab-local recovery path to restore real choices.
            # No price, location, plan or status route is replaced/intercepted.
            location = {"postcode": "21120", "area": draft["postal_code"], "mode": "specific", "radius": "3", "ids": draft["allowed_store_ids"]}
            context.add_init_script("sessionStorage.setItem('smako.personal.requestDraft'," + json.dumps(json.dumps(draft)) + ");sessionStorage.setItem('smako.personal.location'," + json.dumps(json.dumps(location)) + ");")
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))

            def observed(req):
                if req.method == "POST" and req.url == base + "/api/plans":
                    submitted.append(req.post_data_json)
                    (args.output.parent / "browser-submitted-request.json").write_bytes(encoded(req.post_data_json))

            page.on("request", observed)
            page.goto(base + "/personal#choices", wait_until="domcontentloaded")
            page.locator("#check-postcode").click()
            expect(page.locator("#confirm-location")).to_be_enabled(timeout=30000)
            page.locator("#confirm-location").click()
            expect(page.locator("#generate-plan")).to_be_enabled(timeout=30000)
            meal = draft["personal"]["meals"][0]
            for key, value in (meal.get("recipe_choices") or {}).items():
                if value is not None:
                    assert page.locator("#meal-dinner-" + key).input_value() == str(value)
            for cuisine in draft["recipe_preferences"]["cuisines"]:
                assert page.locator("#cuisine-" + cuisine).is_checked()
            result.update(preparation_seconds=time.perf_counter() - started, status="running",
                scope="Real Chromium UI, actual source/plan APIs, fresh test member; no mocked routes", browser="chromium")
            save()
            cancel = arm_phase(75)
            click = time.perf_counter()
            try:
                page.locator("#choice-submit").click()
                expect(page.locator("#plan-content .personal-total")).to_be_visible(timeout=73000)
                plan_visible = time.perf_counter() - click
                assert len(submitted) == 1
                payload = submitted[0]
                from app.models import PlanRequest
                actual = PlanRequest.model_validate(payload).model_dump(mode="json")
                expected = request.model_dump(mode="json")
                # Registration created an empty private pantry. The UI omits
                # the flag (True); the saved API draft explicitly has False.
                actual["personal"].pop("use_pantry", None)
                expected["personal"].pop("use_pantry", None)
                assert actual == expected, "UI changed normalized hard choices"
                assert set(payload["allowed_store_ids"]) == set(draft["allowed_store_ids"])
                plan_id = page.evaluate("localStorage.getItem('smako.personal.lastPlan')")
                read = context.request.get(base + "/api/plans/" + plan_id)
                assert read.status == 200
                saved = read.json()
                plan = saved["plan"]
                assert plan["personal"]["checks"]["checkout_audit"]["passed"]
                if args.expected_total is not None:
                    assert plan["optimized_basket"]["total"] == args.expected_total
                page.get_by_role("button", name="Öppna inköpslistan", exact=True).click()
                expect(page.locator("#personal-shopping")).to_be_visible()
                price = f"{plan['optimized_basket']['total']:.2f}".replace(".", "[,.]")
                expect(page.locator("#shopping-content")).to_contain_text(re.compile(price))
                elapsed = time.perf_counter() - click
                cancel()
                result.update(status="saved_and_read_back", valid_menu_delivered=True,
                    button_to_plan_visible_seconds=plan_visible, button_to_visible_list_and_GET_seconds=elapsed,
                    total=plan["optimized_basket"]["total"], checks=plan["personal"]["checks"],
                    plan_sha256=hashlib.sha256(encoded(plan)).hexdigest(), submitted_request=payload,
                    expensive_posts=len(submitted), page_errors=errors)
                (args.state / "browser-saved.json").write_bytes(encoded(saved))
                page.locator("#personal-shopping").screenshot(path=str(args.state / "browser-shopping.png"))
                page.reload(wait_until="domcontentloaded")
                expect(page.locator("#plan-content .personal-total")).to_be_visible(timeout=15000)
                assert len(submitted) == 1
                reread = context.request.get(base + "/api/plans/" + plan_id)
                assert reread.status == 200 and reread.json()["plan"] == plan
                result["reload_preserved_plan_without_recalculation"] = True
                assert not errors, errors
            except Exception as exc:
                result.update(status="browser_failed", valid_menu_delivered=False, reason=str(exc),
                    browser_seconds=time.perf_counter() - click, expensive_posts=len(submitted), page_errors=errors)
                save()
                raise
            finally:
                cancel()
                context.close()
                browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=3)
    save()
    print({k: result.get(k) for k in ("status", "button_to_visible_list_and_GET_seconds", "total")}, flush=True)
