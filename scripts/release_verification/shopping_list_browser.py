"""Packaged local UI verification. Isolated replay input is configured externally.
No production operations, cookies or credentials are written by this helper.
"""

import argparse
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

sys.path.insert(0, str(Path("scripts/release_verification").resolve()))
from complete_recipe_browser import open_view, record_response, wait_operation
from transport_evidence import classify_navigation_aborts

parser = argparse.ArgumentParser(
    description="Real private shopping UI against an isolated packaged app"
)
parser.add_argument("--base", default="http://127.0.0.1:18129")
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--restart-container")
parser.add_argument("--browser", choices=["chromium", "webkit", "both"], default="both")
args = parser.parse_args()
assert urlsplit(args.base).hostname in {"127.0.0.1", "localhost"}, "isolated target only"
if args.restart_container:
    assert args.restart_container.startswith("smako-shopping-")
r = args.output
r.mkdir(parents=True, exist_ok=False)
base = args.base.rstrip("/")
with sync_playwright() as pw:
    for engine in ["chromium", "webkit"] if args.browser == "both" else [args.browser]:
        browser = getattr(pw, engine).launch()
        context = browser.new_context(viewport={"width": 390, "height": 844})
        traces = []
        context.expose_binding(
            "__shoppingTrace", lambda source, data, traces=traces: traces.append(data)
        )
        context.add_init_script(
            "window.addEventListener('smako:plan-transport',e=>{window.__shoppingTrace(e.detail).catch(()=>{});});"
        )
        page = context.new_page()
        phase = ["initial load"]
        errors = []
        failed = []
        observed = []
        page.on("pageerror", lambda e, errors=errors: errors.append(str(e)))
        page.on(
            "requestfailed",
            lambda q, failed=failed, phase=phase: failed.append(
                {
                    "url": q.url,
                    "method": q.method,
                    "request_id": q.headers.get("x-request-id"),
                    "error": q.failure,
                    "phase": phase[0],
                }
            ),
        )
        page.on("response", lambda response, observed=observed: record_response(response, observed))
        context.expose_binding(
            "__shoppingUnhandled",
            lambda source, message, errors=errors: errors.append("unhandledrejection: " + message),
        )
        context.add_init_script(
            "window.addEventListener('unhandledrejection',e=>{window.__shoppingUnhandled(String(e.reason?.message||e.reason)).catch(()=>{});});"
        )
        page.goto(base + "/personal#shopping")
        expect(page.locator("#calculate-own-list")).to_be_enabled(timeout=90000)
        page.wait_for_load_state("networkidle")
        page.locator("#shopping-query").fill("spaghetti")
        # A generic item is added in one tap with its shown amount.
        page.locator("#shopping-generic-results").get_by_role(
            "button", name="Lägg till Spaghetti · 500 g", exact=True
        ).click()
        expect(page.locator("#extras-list article")).to_have_count(1)
        with page.expect_response(
            lambda response: "/shopping-suggestions?" in response.url and "mj" in response.url
        ) as response:
            page.locator("#shopping-query").fill("mjölk")
        data = response.value.json()
        products = [
            row
            for row in data["products"]
            if len(row["matches"]) == 1
            and row["package_unit"] == "ml"
            and row["package_quantity"]
            and row["package_quantity"] <= 2000
        ]
        assert len(products) >= 2, data
        assert not any("price" in key for row in data["products"] for key in row)
        first, second = products[:2]
        page.locator("#shopping-suggestions").get_by_role(
            "button", name=first["display_name"] + " · " + first["package"], exact=True
        ).first.click()
        page.get_by_role("button", name="Bekräfta och lägg till", exact=True).click()
        expect(page.locator("#extras-list article")).to_have_count(2)
        page.get_by_role(
            "button", name="Lägg till ett antingen-eller-alternativ", exact=True
        ).click()
        page.locator("#shopping-suggestions").get_by_role(
            "button", name=second["display_name"] + " · " + second["package"], exact=True
        ).first.click()
        page.get_by_role("button", name="Godkänn alternativet", exact=True).click()
        expect(page.locator("#extras-list")).to_contain_text(second["name"])
        state = page.request.get(base + "/api/personal/state").json()
        assert len(state["shopping_items"]) == 2 and state["shopping_items"][1]["kind"] == "one_of"
        page.wait_for_load_state("networkidle")
        phase[0] = "first reload"
        page.reload()
        expect(page.locator("#calculate-own-list")).to_be_enabled(timeout=90000)
        expect(page.locator("#extras-list article")).to_have_count(2)
        open_view(page, "shopping")
        page.wait_for_load_state("networkidle")
        begin = len(observed)
        phase[0] = "standalone"
        page.locator("#calculate-own-list").dblclick()
        outcome = wait_operation(page, observed, begin, timeout=180)
        r.joinpath(engine + "-operation.json").write_text(
            json.dumps(outcome[0], ensure_ascii=False, indent=2), encoding="utf8"
        )
        expect(page.locator("#shopping-content .personal-total")).to_be_visible(timeout=180000)
        starts = [
            x
            for x in observed[begin:]
            if x.request.method == "POST" and x.url.endswith("/api/plans")
        ]
        assert len(starts) == 1
        terminals = [
            x.captured_body for x in observed[begin:] if x.status == 201 and x.captured_body
        ]
        assert terminals
        saved = terminals[-1].get("saved", terminals[-1])
        assert saved["plan"]["recipes"] == [] and saved["plan"]["portions"] == 0
        assert (
            saved["request"]["personal"]["extras"][1]["alternatives"]
            == state["shopping_items"][1]["alternatives"]
        )
        other = browser.new_context()
        assert other.request.get(base + "/api/plans/" + saved["plan_id"]).status == 403
        other.close()
        loaded = page.request.get(base + "/api/plans/" + saved["plan_id"]).json()
        assert loaded["plan"] == saved["plan"]
        assert saved["plan"]["personal"]["checks"]["checkout_audit"]["passed"]
        phase[0] = "recalculate"
        open_view(page, "plan")
        begin = len(observed)
        page.get_by_role("button", name="Räkna om med aktuellt skafferi/pris", exact=True).click()
        wait_operation(page, observed, begin, timeout=180)
        expect(page.locator(".recipe-plan-revision")).to_contain_text("Revision 2", timeout=180000)
        revised = page.request.get(base + "/api/plans/" + saved["plan_id"]).json()
        assert revised["revision"] == 2
        assert revised["request"]["personal"]["extras"] == saved["request"]["personal"]["extras"]
        assert revised["plan"]["personal"]["checks"]["checkout_audit"]["passed"]
        phase[0] = "restart"
        if args.restart_container:
            subprocess.run(
                ["docker", "restart", args.restart_container], check=True, capture_output=True
            )
            for _ in range(120):
                try:
                    with urllib.request.urlopen(base + "/ready", timeout=3) as response:
                        ready = json.load(response)
                    if ready["status"] == "ready":
                        break
                except OSError:
                    pass
                time.sleep(1)
            else:
                raise TimeoutError("isolated restart readiness")
            for revision, expected in [(1, saved), (2, revised)]:
                loaded = page.request.get(
                    base + "/api/plans/" + saved["plan_id"] + "?revision=" + str(revision)
                ).json()
                assert loaded["plan"] == expected["plan"]
        mixed = None
        mixed_generation = None
        if engine == "chromium":
            open_view(page, "choices")
            page.locator("#recipe-style").select_option("library")
            page.locator("#meal-dinner-level").select_option("simple")
            page.locator("#dinner-count").fill("1")
            page.locator("#dinner-servings").fill("2")
            page.locator("#breakfast-count").fill("0")
            page.locator("#snack-count").fill("0")
            page.locator("#allow-nutrition-estimates").check()
            page.locator("#purchase-planning-mode").select_option("estimated")
            page.locator("#mode").select_option("cheapest")
            begin = len(observed)
            page.locator("#generate-plan").click()
            mixed_generation, _ = wait_operation(page, observed, begin, timeout=300, reload_after=3)
            expect(page.locator("#plan-content .personal-total")).to_be_visible(timeout=300000)
            terminals = [
                x.captured_body for x in observed[begin:] if x.status == 201 and x.captured_body
            ]
            assert terminals
            mixed = terminals[-1].get("saved", terminals[-1])
            assert len(mixed["plan"]["recipes"]) == 1 and mixed["plan"]["portions"] == 2
            assert (
                len(mixed["request"]["personal"]["extras"]) == 2
                and mixed["plan"]["personal"]["checks"]["checkout_audit"]["passed"]
            )
        open_view(page, "shopping")
        page.wait_for_load_state("networkidle")
        page.screenshot(path=str(r / (engine + "-shopping.png")), full_page=True)
        grouped = None
        if engine == "webkit":
            # Clearing a saved draft must not resurrect old extras from the last plan.
            phase[0] = "clear"
            for count in (1, 0):
                page.locator("#extras-list").get_by_role(
                    "button", name="Ta bort extrarad", exact=True
                ).first.click()
                expect(page.locator("#extras-list article")).to_have_count(count)
            page.wait_for_load_state("networkidle")
            phase[0] = "clear reload"
            page.reload()
            expect(page.locator("#calculate-own-list")).to_be_enabled(timeout=90000)
            expect(page.locator("#extras-list article")).to_have_count(0)
            open_view(page, "shopping")
            page.wait_for_load_state("networkidle")
            phase[0] = "group suggestions"
            with page.expect_response(
                lambda response: (
                    "/shopping-suggestions?" in response.url and "spaghetti" in response.url
                )
            ) as response:
                page.locator("#shopping-query").fill("spaghetti")
            suggestions = response.value.json()["products"]
            labels = [row["display_name"] + " · " + row["package"] for row in suggestions]
            assert len(labels) == len(set(labels))
            choice = next(
                row
                for row in suggestions
                if 2 <= len(row["matches"]) <= 8 and row["package_unit"] == "g"
            )
            page.locator(".shopping-exact-toggle").click()
            page.locator("#shopping-specific-results").get_by_role(
                "button", name=choice["display_name"] + " · " + choice["package"], exact=True
            ).click()
            page.get_by_role("button", name="Bekräfta och lägg till", exact=True).click()
            expect(page.locator("#extras-list article")).to_have_count(1)
            begin = len(observed)
            phase[0] = "group calculate"
            page.locator("#calculate-own-list").click()
            wait_operation(page, observed, begin, timeout=180)
            expect(page.locator("#shopping-content .personal-total")).to_be_visible(timeout=180000)
            terminals = [
                x.captured_body for x in observed[begin:] if x.status == 201 and x.captured_body
            ]
            grouped = terminals[-1].get("saved", terminals[-1])
            assert grouped["plan"]["personal"]["checks"]["checkout_audit"]["passed"]
            assert set(grouped["request"]["personal"]["extras"][0]["alternatives"]) == {
                row["product_key"] for row in choice["matches"]
            }
        r.joinpath(engine + "-transport.json").write_text(
            json.dumps(
                {"failures": failed, "events": traces, "errors": errors},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf8",
        )
        assert not errors, errors
        assert not [response.status for response in observed if response.status >= 500]
        expected_aborts = classify_navigation_aborts(failed, traces, mixed_generation)
        report = {
            "outcome": "PASS",
            "browser": engine,
            "physical_device": False,
            "errors": errors,
            "network_failures": failed,
            "expected_navigation_aborts": expected_aborts,
            "mixed_generation": mixed_generation,
            "start_posts": len(starts),
            "shopping_rows": len(state["shopping_items"]),
            "frequent_choices": len(state["shopping_common"]),
            "saved": saved,
            "revised": revised,
            "mixed": mixed,
            "grouped_identity_consent": grouped,
            "restart": bool(args.restart_container),
            "offline_injected_seconds": 0,
        }
        r.joinpath(engine + "-report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8"
        )
        print(engine, "PASS", flush=True)
        browser.close()
