"""Real mobile choices -> actual HTTPS calculation, with no API shortcut."""

import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

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
        page.goto("https://beta.smako.nu/personal")
        page.get_by_role("button", name="Mina val", exact=True).click()
        page.locator("#dinner-count").fill("0")
        page.locator("#breakfast-count").fill("1")
        page.locator("#breakfast-servings").fill("2")
        page.locator("#mode").select_option("cheapest")
        page.locator("#max-stores").select_option("2")
        page.locator("#organic-percent").fill("30")
        card = page.locator("#meal-settings > .personal-card").nth(1)
        card.get_by_text("Fördelning, egna smakval och gränser", exact=True).click()
        card.get_by_text("Portionsvikt och näringsgränser", exact=True).click()
        limits = {
            "min_protein_g": 15,
            "min_carbs_g": 30,
            "max_carbs_g": 90,
            "min_fat_g": 5,
            "max_fat_g": 30,
            "max_kcal": 600,
        }
        for key, value in limits.items():
            page.locator("#breakfast-" + key).fill(str(value))
        with page.expect_response(
            lambda r: r.url.endswith("/api/plans") and r.request.method == "POST", timeout=180000
        ) as event:
            page.get_by_role("button", name="Skapa plan och inköpslista", exact=True).click()
        response = event.value
        assert response.status == 201, response.text()
        saved = response.json()
        plan = saved["plan"]
        assert plan["optimized_basket"]["total"] == 81.96
        assert plan["data"]["live_chain_requests"] == 0
        submitted = response.request.post_data_json
        assert submitted["personal"]["organic_percent"] == 30
        assert all(submitted["personal"]["meals"][1]["limits"][k] == v for k, v in limits.items())
        assert submitted["personal"]["meals"][1]["limits"]["min_weight_g"] is None
        expect(page.locator("#plan-content .personal-total")).to_contain_text("81,96")
        page.screenshot(path=f"reports/personal-v2-qualified/https/{engine}-choices-result.png")
        results.append(
            {
                "engine": engine,
                "status": "PASS",
                "full_cost": 81.96,
                "submitted_limits": limits,
                "no_cooked_weight_required": True,
                "live_provider_requests": 0,
                "build": plan["build_id"],
            }
        )
        browser.close()
Path("reports/personal-v2-qualified/https/choices.json").write_text(json.dumps(results, indent=2))
print(json.dumps(results))
