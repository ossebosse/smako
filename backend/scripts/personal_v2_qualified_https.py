"""Actual HTTPS A–E and mobile UI, synthetic guests only; never deletes data."""

import json
from copy import deepcopy
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE = "https://beta.smako.nu"
OUT = Path("reports/personal-v2-qualified/https")
OUT.mkdir(parents=True, exist_ok=True)
frozen = json.loads(Path("reports/personal-v2-qualified/frozen.json").read_bytes())
results = []
with sync_playwright() as pw:
    for engine in ("chromium", "webkit"):
        browser = getattr(pw, engine).launch(
            **(
                {
                    "executable_path": None
                }
                if engine == "webkit"
                else {}
            )
        )
        ctx = browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=2,
            is_mobile=True,
            has_touch=True,
        )
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda error, errors=errors: errors.append(str(error)))
        page.goto(BASE + "/personal")

        def state(ctx=ctx):
            return ctx.request.get(BASE + "/api/personal/state").json()

        cases = {}
        for name in ("A", "B", "C", "D", "E") if engine == "chromium" else ("E", "D"):
            req = deepcopy(frozen["cases"][name]["settings"])
            req["personal"]["pantry_revision"] = state()["revision"]
            response = ctx.request.post(BASE + "/api/plans", data=req, timeout=180000)
            if name == "D":
                assert response.status == 422, response.text()
                assert response.json()["code"] == "DATA_BLOCKED"
                cases[name] = response.json()
                continue
            assert response.status == 201, response.text()
            saved = response.json()
            plan = saved["plan"]
            assert plan["build_id"] == "personal-v2-qualified-20260911b"
            assert plan["personal"]["checks"]["facts_version"] == frozen["facts_after"]
            assert (
                plan["optimized_basket"]["total"]
                == frozen["cases"][name]["plan"]["optimized_basket"]["total"]
            )
            assert plan["data"]["live_chain_requests"] == 0
            assert state()["items"] == []
            cases[name] = {"settings": req, "plan": plan}
            if name == "E":
                last = saved
        (OUT / f"{engine}-api.json").write_text(
            json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        page.goto(BASE + "/personal#plan=" + last["plan_id"])
        page.reload()
        expect(page.locator("#plan-content .personal-total")).to_contain_text("81,96")
        page.get_by_text("Krav och databegränsningar", exact=True).click()
        expect(page.get_by_text("Protein:", exact=False).first).to_be_visible()
        expect(page.get_by_text("serverade utan värmning", exact=False)).to_be_visible()
        expect(
            page.get_by_text("Skafferi, avgifter och andra varor ingår inte.", exact=False)
        ).to_be_visible()
        expect(page.get_by_text("Animaliskt eko: ej kontrollerat.", exact=True)).to_be_visible()
        page.screenshot(path=str(OUT / f"{engine}-requirements.png"))
        page.get_by_role("button", name="Öppna inköpslistan", exact=True).click()
        expect(page.get_by_role("heading", name="Getmjölk", exact=True)).to_be_visible()
        # Large text and safe-area layout. This is emulation, not physical iPhone acceptance.
        page.add_style_tag(content="html{font-size:24px !important}")
        page.screenshot(path=str(OUT / f"{engine}-shopping-large-text.png"))
        assert page.evaluate("document.documentElement.scrollWidth<=window.innerWidth+2")
        page.reload()
        expect(page.locator("#plan-content .personal-total")).to_contain_text("81,96")
        # Hard unknown allergen stays blocked; the successful historical plan survives.
        req = deepcopy(frozen["cases"]["E"]["settings"])
        req["personal"]["pantry_revision"] = state()["revision"]
        req["personal"]["profile"]["allergies"] = ["jordnötter"]
        response = ctx.request.post(BASE + "/api/plans", data=req, timeout=180000)
        assert response.status == 422 and response.json()["code"] == "DATA_BLOCKED"
        preserved = ctx.request.get(BASE + "/api/plans/" + last["plan_id"]).json()
        assert preserved["plan"] == last["plan"]
        assert not errors, errors
        results.append(
            {
                "engine": engine,
                "status": "PASS",
                "cases": cases,
                "unknown_allergen": "DATA_BLOCKED",
                "plan_preserved_on_failure": True,
                "no_stock_created": True,
                "page_errors": errors,
                "physical_iphone": "NOT_TESTED",
            }
        )
        print(
            json.dumps(
                {
                    "engine": engine,
                    "status": "PASS",
                    "cost": last["plan"]["optimized_basket"]["total"],
                }
            ),
            flush=True,
        )
        browser.close()
(OUT / "results.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
)
