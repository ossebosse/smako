"""Real HTTPS mobile acceptance, isolated new guest sessions; no data deletion."""
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import expect, sync_playwright

BASE = "https://beta.smako.nu"
OUT = Path("reports/personal-v2/https-browser")
OUT.mkdir(parents=True, exist_ok=True)
results = []
with sync_playwright() as pw:
    for name in ("chromium", "webkit"):
        browser = getattr(pw, name).launch(**({"executable_path": None} if name == "webkit" else {}))
        ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
        page = ctx.new_page()
        page.set_default_timeout(15000)
        errors = []
        page.on("pageerror", lambda e, sink=errors: sink.append(str(e)))
        page.goto(BASE + "/personal")
        expect(page.locator("#personal-status")).to_have_text("", timeout=90000)
        state = ctx.request.get(BASE + "/api/personal/state").json()
        assert state["items"] == [] and state["account"]["status"] == "DATA_BLOCKED"
        assert page.locator(".personal-nav [data-open]").count() == 5
        page.get_by_role("button", name="Skafferi", exact=True).click()
        page.locator("#add-pantry").click()
        page.get_by_label("Vara", exact=True).fill("mjölk")
        page.get_by_label("Faktisk mängd hemma").fill("300")
        page.get_by_label("Enhet", exact=True).select_option("ml")
        page.get_by_role("button", name="Spara skafferivara").click()
        page.get_by_text("Faktiskt lager 300 ml", exact=False).wait_for()
        page.get_by_role("button", name="Sök varor", exact=True).click()
        page.locator("#product-query").fill("mjölk 1,5 %")
        page.locator("#product-search-form button").click()
        page.get_by_role("button", name="Lägg till i inköpslistan", exact=True).first.click()
        page.get_by_label("Önskad mängd").fill("200")
        page.get_by_label("Enhet", exact=True).select_option("ml")
        page.get_by_role("button", name="Bekräfta och lägg till").click()
        page.get_by_role("button", name="Beräkna inköpslistan").click()
        page.wait_for_url("**/personal#plan=*", timeout=90000)
        expect(page.locator("#personal-status")).to_have_text("", timeout=90000)
        plan_id = parse_qs(urlparse(page.url).fragment)["plan"][0]
        saved = ctx.request.get(BASE + "/api/plans/" + plan_id).json()
        assert len(saved["request"]["personal"]["extras"]) == 1
        assert saved["request"]["personal"]["extras"][0]["kind"] == "exact"
        assert saved["plan"]["recipes"] == []
        assert not saved["plan"]["personal"]["allocations"]
        assert saved["plan"]["optimized_basket"]["store_count"] <= 2
        assert ctx.request.get(BASE + "/api/personal/state").json()["items"][0]["quantity"] == 300
        page.screenshot(path=str(OUT / f"{name}-exact-basket.png"), full_page=True)
        stranger = browser.new_context()
        assert stranger.request.get(BASE + "/api/plans/" + plan_id).status == 403
        assert stranger.request.get(BASE + "/api/personal/state").json()["items"] == []
        stranger.close()
        page.reload()
        expect(page.locator("#personal-status")).to_have_text("", timeout=90000)
        assert not page.locator("#generate-plan").is_disabled()
        page.get_by_role("button", name="Mina val", exact=True).click()
        page.locator("#dinner-count").fill("0")
        page.locator("#breakfast-count").fill("1")
        page.locator("#snack-count").fill("1")
        page.get_by_role("button", name="Skapa plan och inköpslista").click()
        page.get_by_text("0 middagar · 2 övriga måltider · 2 portioner", exact=False).wait_for(timeout=90000)
        new_id = parse_qs(urlparse(page.url).fragment)["plan"][0]
        combined = ctx.request.get(BASE + "/api/plans/" + new_id).json()
        assert len(combined["plan"]["recipes"]) == 2
        assert combined["plan"]["optimized_basket"]["store_count"] <= 2
        assert combined["plan"]["data"]["live_chain_requests"] == 0
        assert ctx.request.get(BASE + "/api/personal/state").json()["items"][0]["quantity"] == 300
        page.get_by_role("button", name="Redigera", exact=True).first.click()
        page.get_by_label("Receptnamn", exact=True).fill("Verifierad mobilfrukost")
        page.get_by_role("button", name="Spara och räkna om hela korgen").click()
        page.get_by_role("heading", name="Verifierad mobilfrukost").wait_for(timeout=90000)
        page.screenshot(path=str(OUT / f"{name}-plan.png"), full_page=True)
        page.get_by_role("button", name="Mina val", exact=True).click()
        page.locator("#organic-percent").fill("50")
        page.get_by_role("button", name="Skapa plan och inköpslista").click()
        page.get_by_text("Underlag saknas:", exact=False).wait_for()
        page.add_style_tag(content="html {font-size:24px !important;}")
        assert page.evaluate("() => document.documentElement.scrollWidth <= innerWidth + 1")
        assert not errors, errors
        results.append({"engine": name, "status": "PASS", "checks": 22, "page_errors": errors, "exact_basket_total": saved["plan"]["optimized_basket"]["total"], "breakfast_snack_extra_total": combined["plan"]["optimized_basket"]["total"], "version": combined["plan"]["app_version"], "live_requests": 0})
        browser.close()
(OUT / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
print(json.dumps(results))
