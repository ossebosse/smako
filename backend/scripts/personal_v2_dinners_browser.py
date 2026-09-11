"""Actual forms and API: frozen local / deployed HTTPS; synthetic guests only."""

import argparse
import json
from copy import deepcopy
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def check(base, output):
    output.mkdir(parents=True, exist_ok=True)
    frozen = json.loads(Path("reports/personal-v2-dinners/frozen.json").read_bytes())
    results = []
    with sync_playwright() as pw:
        for engine in ("chromium", "webkit"):
            browser = getattr(pw, engine).launch(
                **(
                    {
                        "executable_path": "D:/codex-smako-loading-hotfix-20260909/browsers/webkit-2336/Playwright.exe"
                    }
                    if engine == "webkit"
                    else {}
                )
            )
            ctx = browser.new_context(
                viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True
            )
            page = ctx.new_page()
            errors = []
            page.on("pageerror", lambda e, sink=errors: sink.append(str(e)))
            page.goto(base + "/personal")
            page.get_by_role("button", name="Mina val", exact=True).click()
            expect(page.locator("#allow-nutrition-estimates")).not_to_be_checked()
            page.locator("#dinner-count").fill("5")
            page.locator("#dinner-servings").fill("4")
            page.locator("#mode").select_option("balanced")
            page.locator("#max-stores").select_option("2")
            card = page.locator("#meal-settings > .personal-card").nth(0)
            card.get_by_text("Fördelning, egna smakval och gränser", exact=True).click()
            card.get_by_text("Portionsvikt och näringsgränser", exact=True).click()
            page.locator("#dinner-min_protein_g").fill("20")
            page.locator("#dinner-max_kcal").fill("800")
            page.locator("#allow-nutrition-estimates").check()

            def generate(page=page):
                with page.expect_response(
                    lambda event_response: (
                        event_response.url.endswith("/api/plans") and event_response.request.method == "POST"
                    ),
                    timeout=180000,
                ) as event:
                    page.locator("#generate-plan").click()
                return event.value

            blocked = generate()
            assert blocked.status == 422, blocked.text()
            assert blocked.json().get("code") == "SEARCH_BLOCKED", blocked.text()
            expect(page.locator("#personal-status")).to_contain_text("Inga krav har sänkts")
            page.locator("#dinner-count").fill("3")
            r = generate()
            assert r.status == 201, r.text()
            saved = r.json()
            plan = saved["plan"]
            assert (
                plan["optimized_basket"]["total"]
                == frozen["cases"]["B3"]["plan"]["optimized_basket"]["total"]
            )
            assert plan["data"]["live_chain_requests"] == 0
            submitted = r.request.post_data_json
            assert submitted["personal"]["allow_nutrition_estimates"] is True
            assert len(plan["recipes"]) == 3
            expect(page.locator("#plan-content .personal-total")).to_be_visible()
            page.get_by_text("Krav och databegränsningar", exact=True).click()
            expect(
                page.get_by_text(
                    "Gränser uppfyllda enligt beräkningen · spårbara uppskattningar används.",
                    exact=True,
                ).first
            ).to_be_visible()
            page.screenshot(path=str(output / f"{engine}-nutrition.png"), full_page=True)
            for row in plan["personal"]["checks"]["nutrition"]:
                assert (
                    row["status"] == "ESTIMATED"
                    and row["values"]["protein_g"] >= 20
                    and row["values"]["kcal"] <= 800
                )
            page.get_by_role("button", name="Skafferi", exact=True).click()
            page.locator("#add-pantry").click()
            page.get_by_label("Vara", exact=True).fill("ris")
            page.get_by_label("Faktisk mängd hemma", exact=True).fill("500")
            page.get_by_label("Enhet", exact=True).select_option("g")
            page.get_by_label(
                "Bekräfta livsmedel och rå/torr/avrunnen form för näringsuppskattning", exact=True
            ).select_option("slv:2481:dry")
            page.get_by_role("button", name="Spara skafferivara", exact=True).click()
            expect(page.get_by_text("Faktiskt lager 500 g", exact=False)).to_be_visible()
            before = ctx.request.get(base + "/api/personal/state").json()
            page.get_by_role("button", name="Mina val", exact=True).click()
            r = generate()
            assert r.status == 201, r.text()
            pantry_saved = r.json()
            after = ctx.request.get(base + "/api/personal/state").json()
            assert [(i["id"], i["quantity"]) for i in before["items"]] == [
                (i["id"], i["quantity"]) for i in after["items"]
            ]
            assert (
                pantry_saved["plan"]["optimized_basket"]["total"]
                == frozen["cases"]["C3"]["plan"]["optimized_basket"]["total"]
            )
            assert any(a["quantity"] > 0 for a in pantry_saved["plan"]["personal"]["allocations"])
            assert any(
                s["origin"] == "pantry"
                for n in pantry_saved["plan"]["personal"]["checks"]["nutrition"]
                for s in n["sources"]
            )
            page.reload()
            page.get_by_role("button", name="Mina val", exact=True).click()
            expect(page.locator("#allow-nutrition-estimates")).to_be_checked()
            page.add_style_tag(content="html{font-size:24px!important}")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth+1")
            page.screenshot(path=str(output / f"{engine}-large-text.png"), full_page=True)
            # Separate owner: strict and organic examples must not borrow this guest's pantry.
            other = browser.new_context(
                viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True
            )
            api_cases = {}
            for case in ("A2", "D", "E3"):
                req = deepcopy(frozen["cases"][case]["settings"])
                state = other.request.get(base + "/api/personal/state").json()
                req["personal"]["pantry_revision"] = state["revision"]
                response = other.request.post(base + "/api/plans", data=req, timeout=180000)
                assert response.status == 201, response.text()
                value = response.json()["plan"]
                assert value["data"]["live_chain_requests"] == 0
                assert (
                    value["optimized_basket"]["total"]
                    == frozen["cases"][case]["plan"]["optimized_basket"]["total"]
                )
                if case == "A2":
                    assert value["personal"]["checks"]["nutrition"][0]["status"] == "VERIFIED"
                if case == "E3":
                    assert value["personal"]["checks"]["organic_cost_percent"] >= 25
                api_cases[case] = value
            assert other.request.get(base + "/api/personal/state").json()["items"] == []
            assert not errors, errors
            artifact = {
                "engine": engine,
                "status": "PASS",
                "submitted": submitted,
                "B3": plan,
                "C3": pantry_saved["plan"],
                "B5": blocked.json(),
                "other_cases": api_cases,
                "stock_before": [(i["name"], i["quantity"]) for i in before["items"]],
                "stock_after": [(i["name"], i["quantity"]) for i in after["items"]],
                "page_errors": errors,
            }
            (output / f"{engine}.json").write_text(
                json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf8"
            )
            results.append(
                {
                    "engine": engine,
                    "status": "PASS",
                    "build": plan["build_id"],
                    "cost": plan["optimized_basket"]["total"],
                    "external_consumer_calls": 0,
                }
            )
            browser.close()
    (output / "results.json").write_text(json.dumps(results, indent=2), encoding="utf8")
    print(json.dumps(results))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="https://beta.smako.nu")
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    check(a.base, a.output)
