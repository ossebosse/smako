"""Ordinary HTTPS mobile form: click-to-painted result, one submission and swap."""

import argparse
import json
import time
from pathlib import Path

from playwright.sync_api import Error, expect, sync_playwright

from backend.scripts.combined_profile_browser import validate


def ready(page):
    page.locator('[data-view="plan"]').wait_for(state="visible", timeout=180000)
    expect(page.locator("#generate-plan")).to_be_enabled(timeout=180000)
    page.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="https://beta.smako.nu")
    parser.add_argument("--output", type=Path, default=Path("reports/performance-403020/mobile"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(
            viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True
        )
        page = context.new_page()
        posts, errors = [], []
        page.on(
            "request",
            lambda r: (
                posts.append(time.perf_counter())
                if r.url.endswith("/api/plans") and r.method == "POST"
                else None
            ),
        )
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(args.base + "/personal")
        page.get_by_role("button", name="Mina val", exact=True).click()
        for n, (meal, servings, minimum) in enumerate(
            (("dinner", 2, 40), ("breakfast", 1, 30), ("snack", 1, 20))
        ):
            page.locator(f"#{meal}-count").fill("5")
            page.locator(f"#{meal}-servings").fill(str(servings))
            card = page.locator("#meal-settings > .personal-card").nth(n)
            card.get_by_text("Fördelning, egna smakval och gränser", exact=True).click()
            card.get_by_text("Portionsvikt och näringsgränser", exact=True).click()
            page.locator(f"#{meal}-min_protein_g").fill(str(minimum))
        page.locator("#allow-nutrition-estimates").check()
        page.screenshot(path=str(args.output / "form.png"), full_page=True)
        start = time.perf_counter()
        with page.expect_response(
            lambda r: r.url.endswith("/api/plans") and r.request.method == "POST", timeout=180000
        ) as event:
            page.locator("#generate-plan").dblclick()
        response = event.value
        payload = response.json()
        response_time = time.perf_counter() - start
        assert response.status == 201
        request = response.request.post_data_json
        validate(payload["plan"], request)
        ready(page)
        rendered_time = time.perf_counter() - start
        assert len(posts) == 1, "Double-click started more than one plan"
        page.screenshot(path=str(args.output / "plan.png"), full_page=True)
        output = {
            "https": args.base.startswith("https://"),
            "viewport": [390, 844],
            "request": request,
            "plan": payload["plan"],
            "status": response.status,
            "response_seconds": response_time,
            "click_to_usable_seconds": rendered_time,
            "submission_count_after_double_click": len(posts),
        }
        start = time.perf_counter()
        with page.expect_response(
            lambda r: r.url.endswith("/change") and r.request.method == "POST", timeout=180000
        ) as event:
            page.locator("article.personal-card").filter(
                has=page.get_by_text("Dag 4 · Middag", exact=True)
            ).get_by_role("button", name="Byt recept", exact=True).click()
        changed = event.value
        body = changed.json()
        output["swap_response_seconds"] = time.perf_counter() - start
        assert changed.status == 200
        validate(body["saved"]["plan"], request)
        ready(page)
        output.update(
            swap_click_to_usable_seconds=time.perf_counter() - start,
            swap_status=changed.status,
            swap_plan=body["saved"]["plan"],
        )
        page.screenshot(path=str(args.output / "swap.png"), full_page=True)
        page.reload()
        ready(page)
        page.get_by_role("button", name="Mina val", exact=True).click()
        assert page.locator("#allow-nutrition-estimates").is_checked()
        for meal, minimum in (("dinner", 40), ("breakfast", 30), ("snack", 20)):
            assert page.locator(f"#{meal}-min_protein_g").input_value() == str(minimum)
        output["reload_preserved_requirements"] = True
        assert len(posts) == 1
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
        assert not errors

        # Browser-only failure probes hold the request before it reaches the
        # server. No additional heavy production plan is started by these tests.
        held_routes = []
        page.route("**/api/plans", lambda route: held_routes.append(route))
        page.locator("#generate-plan").click()
        page.wait_for_timeout(200)
        page.goto(args.base + "/personal")
        ready(page)
        page.wait_for_timeout(200)
        assert len(posts) == 2  # One intercepted manual submission, no retry.
        output["leave_and_return"] = {
            "automatic_retries": 0,
            "last_received_plan_retained": True,
            "probe": "request held before server dispatch",
        }
        page.add_init_script(
            "const original=window.setTimeout; window.setTimeout=(f,t,...args)=>original(f,t===600000?100:t,...args);"
        )
        page.reload()
        ready(page)
        page.get_by_role("button", name="Mina val", exact=True).click()
        page.locator("#generate-plan").click()
        page.get_by_text(
            "Svarstiden överskreds. Senaste fungerande plan är kvar. Läs om innan du försöker igen.",
            exact=True,
        ).wait_for(timeout=5000)
        page.wait_for_timeout(300)
        assert len(posts) == 3
        output["timeout_probe"] = {
            "configured_ms": 600000,
            "test_clock_ms": 100,
            "automatic_retries": 0,
            "server_work_started": False,
        }
        output["page_errors"] = errors
        output["already_closed_probe_routes"] = 0
        for route in held_routes:
            try:
                route.abort("aborted")
            except Error:
                output["already_closed_probe_routes"] += 1
        page.unroute_all(behavior="ignoreErrors")
        (args.output / "acceptance.json").write_text(
            json.dumps(output, ensure_ascii=False, indent=2), encoding="utf8"
        )
        print(
            json.dumps(
                {
                    k: output[k]
                    for k in (
                        "status",
                        "click_to_usable_seconds",
                        "response_seconds",
                        "swap_status",
                        "swap_click_to_usable_seconds",
                    )
                }
            ),
            flush=True,
        )
        context.close()
        browser.close()


if __name__ == "__main__":
    main()
