"""Actual HTTPS, current retained prices, isolated synthetic guests; no deletion."""
import json
from copy import deepcopy
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE = "https://beta.smako.nu"
OUT = Path("reports/personal-v2-gaps/https")
OUT.mkdir(parents=True, exist_ok=True)


def money(value):
    return f"{value:.2f}".replace(".", ",") + " kr"


results = []
with sync_playwright() as pw:
    for engine in ("chromium", "webkit"):
        browser = getattr(pw, engine).launch(**({"executable_path": "D:/codex-smako-loading-hotfix-20260909/browsers/webkit-2336/Playwright.exe"} if engine == "webkit" else {}))
        ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
        page = ctx.new_page()
        page.set_default_timeout(90000)
        errors = []
        page.on("pageerror", lambda error, sink=errors: sink.append(str(error)))
        page.goto(BASE + "/personal")
        expect(page.locator("#personal-status")).to_have_text("")
        assert page.locator(".personal-nav [data-open]").count() == 5
        def state(ctx=ctx):
            return ctx.request.get(BASE + "/api/personal/state").json()
        assert state()["items"] == []
        response = ctx.request.put(BASE + "/api/personal/pantry", data={"revision": 0, "items": [{"id": "synthetic-milk", "name": "mjölk", "quantity": 300, "unit": "ml"}]})
        assert response.status == 200
        search = ctx.request.post(BASE + "/api/product-search", data={"query": "servetter", "limit": 40}).json()
        exact = next(r for r in search["results"] if r["package_unit"] == "st" and r["best_price"] is not None)
        meals = [{"meal_type": t, "count": 1, "servings": 1} for t in ("dinner", "breakfast", "snack")]
        slots = [{"id": t, "day": 1, "meal_type": t, "recipe": {"name": name, "servings": 1, "ingredients": [{"name": "mjölk", "quantity": 200, "unit": "ml"}, {"name": "ris", "quantity": 200, "unit": "g"}], "instructions": ["Syntetiskt acceptansrecept: tillaga riset och tillsätt mjölken."]}} for t, name in (("dinner", "Acceptans – risrätt"), ("breakfast", "Acceptans – risgrynsfrukost"), ("snack", "Acceptans – risgrynsmål"))]
        req = {"recipes": 0, "servings": 1, "max_stores": 2, "diversity_mode": "balanced", "memberships": {"coop": True, "willys": True, "hemkop": True}, "personal": {"pantry_revision": state()["revision"], "meals": meals, "slots": slots, "extras": [{"id": "extra-milk", "query": "mjölk 1,5 %", "properties": ["1,5 %"], "quantity": 600, "unit": "ml", "confirmed": True}, {"id": "exact-nonfood", "kind": "exact", "query": exact["name"], "product_key": exact["product_key"], "quantity": 50, "unit": "st", "food": False, "confirmed": True}]}}
        response = ctx.request.post(BASE + "/api/plans", data=req, timeout=180000)
        assert response.status == 201, response.text()
        saved = response.json()
        plan_id = saved["plan_id"]
        initial = saved["plan"]["optimized_basket"]["total"]
        assert saved["plan"]["personal"]["version"] == "personal-v2-2"
        assert saved["plan"]["optimized_basket"]["store_count"] <= 2
        assert len(state()["items"]) == 1 and state()["items"][0]["quantity"] == 300
        assert sum(a["quantity"] for a in saved["plan"]["personal"]["allocations"]) == 300
        page.goto(BASE + "/personal#plan=" + plan_id)
        page.reload()
        expect(page.locator("#plan-content .personal-total")).to_have_text(money(initial))
        expect(page.get_by_text("1 middagar · 2 övriga måltider · 3 portioner", exact=False)).to_be_visible()
        page.get_by_role("button", name="Öppna inköpslistan", exact=True).click()
        page.get_by_role("button", name="Bekräfta att jag har köpt varorna", exact=True).click()
        expect(page.get_by_role("button", name="Inköpet är bokfört", exact=True)).to_be_visible()
        bought = state()
        history = deepcopy(bought["ledger"])
        page.get_by_role("button", name="Inköpet är bokfört", exact=True).click()
        expect(page.locator("#personal-status")).to_have_text("")
        assert state() == bought
        quantities = {u: sum(i["quantity"] for i in bought["items"] if i["unit"] == u) for u in ("ml", "g")}
        page.get_by_role("button", name="Min plan", exact=True).click()
        page.get_by_role("button", name="Redigera", exact=True).first.click()
        page.get_by_label("Receptnamn", exact=True).fill("Ändrad efter bokfört köp")
        amounts = page.locator("#personal-dialog").get_by_label("Mängd", exact=True)
        amounts.nth(0).fill(str(quantities["ml"] + 200))
        amounts.nth(1).fill(str(quantities["g"] + 200))
        with page.expect_response(lambda r: r.url.endswith("/change")) as event:
            page.get_by_role("button", name="Spara och räkna om hela korgen").click()
        assert event.value.status == 200, event.value.text()
        changed = event.value.json()
        mutation = event.value.request.post_data_json
        topup = changed["saved"]["plan"]["optimized_basket"]["total"]
        assert topup > 0
        assert changed["state"]["ledger"] == history
        assert [i["quantity"] for i in changed["state"]["items"]] == [i["quantity"] for i in bought["items"]]
        expect(page.locator("#plan-content .personal-total")).to_have_text(money(topup))
        endpoint = BASE + f"/api/personal/plans/{plan_id}/change"
        assert ctx.request.post(endpoint, data=mutation).json()["saved"]["revision"] == 2
        assert ctx.request.post(endpoint, data={**mutation, "action": "remove", "recipe": None}).status == 409
        assert ctx.request.get(BASE + f"/api/plans/{plan_id}?revision=1").json()["plan"]["optimized_basket"]["total"] == initial
        assert [s["recipe"] for s in changed["saved"]["plan"]["personal"]["slots"]][1:] == [s["recipe"] for s in saved["plan"]["personal"]["slots"]][1:]
        page.get_by_role("button", name="Öppna inköpslistan", exact=True).click()
        expect(page.locator("#shopping-content .personal-total")).to_contain_text(money(topup))
        page.get_by_text("Oföränderlig inköps- och förbrukningshistorik", exact=True).click()
        expect(page.get_by_role("heading", name=f"Bokfört inköp · planrevision 1 · {money(initial)}")).to_be_visible()
        page.get_by_role("button", name="Bekräfta att jag har köpt varorna", exact=True).click()
        expect(page.get_by_role("button", name="Inköpet är bokfört", exact=True)).to_be_visible()
        assert [e["total"] for e in state()["ledger"]] == [initial, topup]
        page.screenshot(path=str(OUT / f"{engine}-topup-viewport.png"))
        page.get_by_role("button", name="Min plan", exact=True).click()
        page.get_by_role("button", name="Räkna om med aktuellt skafferi/pris").click()
        expect(page.locator("#plan-content .personal-total")).to_have_text("0,00 kr")
        final = state()
        assert final["ledger"][0] == history[0]
        page.reload()
        expect(page.locator("#personal-status")).to_have_text("")
        assert not page.locator("#generate-plan").is_disabled()
        stranger = browser.new_context()
        assert stranger.request.get(BASE + f"/api/plans/{plan_id}").status == 403
        assert stranger.request.get(BASE + "/api/personal/state").json()["items"] == []
        stranger.close()
        # A real missing cooked-yield constraint must remain blocked in UI.
        page.get_by_role("button", name="Mina val", exact=True).click()
        page.locator("#dinner-count").fill("0")
        page.locator("#breakfast-count").fill("1")
        breakfast = page.locator("#meal-settings > .personal-card").filter(has=page.get_by_role("heading", name="Frukost", exact=True))
        breakfast.get_by_text("Fördelning, egna smakval och gränser", exact=True).click()
        breakfast.get_by_text("Portionsvikt och näringsgränser", exact=True).click()
        page.locator("#breakfast-min_weight_g").fill("1")
        page.get_by_role("button", name="Skapa plan och inköpslista").click()
        page.get_by_text("Underlag saknas:", exact=False).wait_for()
        expect(page.get_by_role("button", name="Ändra mina val", exact=True)).to_be_visible()
        page.screenshot(path=str(OUT / f"{engine}-data-blocked.png"))
        page.add_style_tag(content="html {font-size:24px !important;}")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
        assert not errors, errors
        results.append({"engine": engine, "status": "PASS", "initial_cost": initial, "topup_cost": topup, "historical_paid": round(initial + topup, 2), "remaining_cost": 0, "initial_pantry_ml": 300, "available_surplus": {u: sum(i["available"] for i in final["items"] if i["unit"] == u) for u in ("ml", "g")}, "contexts": [g["store_name"] for g in saved["plan"]["optimized_basket"]["stores"]], "membership_applied": [i["membership_program"] for g in saved["plan"]["optimized_basket"]["stores"] for i in g["items"] if i.get("membership_program")], "live_requests": saved["plan"]["data"]["live_chain_requests"], "version": saved["plan"]["app_version"], "mix_and_match": "LIVE_DATA_UNAVAILABLE", "errors": errors})
        (OUT / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(results[-1]), flush=True)
        browser.close()
