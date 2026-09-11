"""Synthetic engine output rendered by actual HTTPS UI; no fake live campaign."""
import json
import tempfile
from pathlib import Path

from app.services.plan_store import PlanStore
from playwright.sync_api import expect, sync_playwright

from backend.tests.test_personal_planning_v2 import request, run
from backend.tests.test_promotion_groups import catalog, extras, group

out = Path("reports/personal-v2-gaps/group-ui")
out.mkdir(parents=True, exist_ok=True)
results = []
with tempfile.TemporaryDirectory(prefix="smako-group-ui-") as directory:
    req = request(extras=extras())
    req.memberships = {"coop": True}
    plan = run(catalog(group(membership_program="COOP_MEMBER", max_groups=1)), req)
    saved = PlanStore(Path(directory)/"plans.sqlite").create(req, plan, owner_actor_hash="f"*64)
    with sync_playwright() as pw:
        for engine in ("chromium", "webkit"):
            browser = getattr(pw, engine).launch(**({"executable_path": "D:/codex-smako-loading-hotfix-20260909/browsers/webkit-2336/Playwright.exe"} if engine == "webkit" else {}))
            ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
            ctx.route("**/api/plans/"+saved.plan_id, lambda route: route.fulfill(json=saved.model_dump(mode="json")))
            page = ctx.new_page()
            page.goto("https://beta.smako.nu/personal#plan="+saved.plan_id)
            expect(page.locator("#plan-content .personal-total")).to_have_text("75,00 kr")
            page.get_by_role("button", name="Öppna inköpslistan", exact=True).click()
            expect(page.get_by_text("3 valfria i kampanjen för 75,00 kr", exact=True)).to_have_count(3)
            expect(page.get_by_text("1 förpackning · 25,00 kr", exact=True)).to_have_count(3)
            text = page.locator("#shopping-content").inner_text()
            assert "2026-09-01 – 2026-10-01" in text and "Kräver COOP_MEMBER" in text
            assert "Max 1 kampanjgrupper" in text
            assert all("1 × "+name in text for name in ("mjölk", "bröd", "ris"))
            page.screenshot(path=str(out/f"{engine}.png"))
            results.append({"engine": engine, "status": "PASS", "source": "SYNTHETIC_ENGINE_RESPONSE", "basket_total": 75, "row_total": 25, "packages": 3, "live_group_data": False})
            browser.close()
(out/"results.json").write_text(json.dumps(results, indent=2))
print(json.dumps(results))
