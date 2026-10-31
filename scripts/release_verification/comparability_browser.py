"""Mobile ordinary shopping UI over isolated inputs, or explicitly authorized beta."""

import argparse
import json
import time
import urllib.request
from pathlib import Path

from complete_recipe_browser import open_view, record_response, wait_operation
from playwright.sync_api import expect, sync_playwright

p = argparse.ArgumentParser()
p.add_argument("--base", required=True)
p.add_argument("--expected-build", required=True)
p.add_argument("--output", type=Path, required=True)
p.add_argument("--allow-beta", action="store_true", help="Explicitly authorized beta verification with new test identities")
a = p.parse_args()
assert a.base.startswith("http://127.0.0.1:") or (a.allow_beta and a.base == "https://beta.smako.nu")
a.output.mkdir(parents=True, exist_ok=False)
for _ in range(120):
    try:
        ready = json.load(urllib.request.urlopen(a.base + "/ready", timeout=3))
        if ready["status"] == "ready" and ready["build_id"] == a.expected_build:
            break
    except OSError:
        pass
    time.sleep(1)
else:
    raise TimeoutError("not ready")
with sync_playwright() as pw:
    for engine in ("chromium", "webkit"):
        browser = getattr(pw, engine).launch()
        context = browser.new_context(viewport={"width": 390, "height": 844})
        page = context.new_page()
        errors = []
        failed = []
        observed = []
        report = {}
        page.on("pageerror", lambda e, errors=errors: errors.append(str(e)))
        page.on(
            "requestfailed",
            lambda r, failed=failed: failed.append({"url": r.url, "error": r.failure}),
        )
        page.on("response", lambda r, observed=observed: record_response(r, observed))
        try:
            page.goto(a.base + "/personal#shopping")
            expect(page.locator("#add-shopping-item")).to_be_enabled(timeout=120000)
            page.wait_for_load_state("networkidle")

            def choose(query, campaign=False, page=page):
                open_view(page, "shopping")
                page.get_by_role("button", name="Lägg till vara", exact=True).click()
                with page.expect_response(lambda r: "/shopping-suggestions?" in r.url) as response:
                    page.locator("#shopping-query").fill(query)
                data = response.value.json()
                choices = [
                    r
                    for r in data["products"]
                    if r["selectable"]
                    and r.get("campaign_choice", False) == campaign
                    and (campaign or r.get("purchase_units"))
                ]
                if not campaign:
                    choices = sorted(
                        choices, key=lambda r: not r["display_name"].startswith("Coop")
                    )
                assert choices, data
                row = choices[0]
                page.locator(".shopping-exact-toggle").click()
                page.locator("#shopping-specific-results").get_by_role(
                    "button", name=row["display_name"] + " · " + row["package"], exact=True
                ).first.click()
                return row

            row = choose("Aluminiumfolie")
            expect(page.get_by_label("Enhet", exact=True)).to_be_disabled()
            expect(page.locator("#dialog-body")).to_contain_text("Innehållets gram/liter är okända")
            page.get_by_label("Önskad mängd", exact=True).fill("2")
            page.get_by_role("button", name="Bekräfta och lägg till", exact=True).click()
            expect(page.locator("#extras-list article")).to_have_count(1)
            page.wait_for_load_state("networkidle")
            page.reload()
            page.wait_for_load_state("networkidle")
            expect(page.locator("#extras-list")).to_contain_text("2 köpförpackningar")
            open_view(page, "shopping")
            begin = len(observed)
            page.locator("#calculate-own-list").dblclick()
            operation, _ = wait_operation(page, observed, begin, timeout=180)
            expect(page.locator("#shopping-content .personal-total")).to_be_visible(timeout=30000)
            starts = [
                r
                for r in observed[begin:]
                if r.request.method == "POST" and r.url.endswith("/api/plans")
            ]
            assert len(starts) == 1
            terminals = [
                r.captured_body for r in observed[begin:] if r.status == 201 and r.captured_body
            ]
            saved = terminals[-1].get("saved", terminals[-1])
            plan_id = saved["plan_id"]
            assert saved["request"]["personal"]["extras"][0]["purchase_units"]
            assert saved["plan"]["personal"]["checks"]["checkout_audit"]["passed"]
            assert saved["plan"]["optimized_basket"]["stores"][0]["items"][0]["purchase_units"]
            expect(page.locator("#shopping-content")).to_contain_text("okänd innehållsmängd")
            assert (
                page.request.get(a.base + "/api/plans/" + plan_id).json()["plan"] == saved["plan"]
            )
            page.screenshot(path=str(a.output / (engine + "-packs.png")))
            choose("Crunchy", True)
            expect(page.locator("#dialog-body")).to_contain_text("Hela kampanjgrupper debiteras")
            page.get_by_role("button", name="Bekräfta och lägg till", exact=True).click()
            expect(page.locator("#extras-list article")).to_have_count(2)
            begin = len(observed)
            page.locator("#calculate-extras").click()
            wait_operation(page, observed, begin, timeout=180)
            expect(page.locator("#shopping-content .personal-total")).to_be_visible(timeout=30000)
            latest = page.request.get(a.base + "/api/plans/" + plan_id).json()
            assert latest["revision"] == saved["revision"] + 1
            assert latest["plan"]["personal"]["checks"]["checkout_audit"]["passed"]
            assert any(
                i["conditional_variant_choice"]
                for s in latest["plan"]["optimized_basket"]["stores"]
                for i in s["items"]
                if "conditional_variant_choice" in i
            )
            assert (
                page.request.get(a.base + "/api/plans/" + plan_id + "?revision=1").json()["plan"]
                == saved["plan"]
            )
            page.wait_for_load_state("networkidle")
            page.reload()
            page.wait_for_load_state("networkidle")
            open_view(page, "shopping")
            expect(page.locator("#shopping-content .personal-total")).to_be_visible(timeout=30000)
            page.screenshot(path=str(a.output / (engine + "-campaign.png")))
            other = browser.new_context()
            assert other.request.get(a.base + "/api/plans/" + plan_id).status == 403
            other.close()
            assert not errors and not failed, (errors, failed)
            assert not [r.status for r in observed if r.status >= 500]
            report = {
                "status": "PASS",
                "engine": engine,
                "build": a.expected_build,
                "pack_total": saved["plan"]["optimized_basket"]["total"],
                "combined_total": latest["plan"]["optimized_basket"]["total"],
                "job_starts": len(starts),
                "audit": True,
                "reload": True,
                "revision": latest["revision"],
                "old_revision_equal": True,
                "owner_isolation": 403,
                "page_errors": errors,
                "failed_requests": failed,
            }
            (a.output / (engine + "-saved.json")).write_text(
                json.dumps(latest, ensure_ascii=False), encoding="utf8"
            )
            print(engine, "PASS", flush=True)
        except Exception as e:
            report = {
                "status": "FAIL",
                "engine": engine,
                "error": repr(e),
                "page_errors": errors,
                "failed_requests": failed,
            }
            page.screenshot(path=str(a.output / (engine + "-fail.png")))
            raise
        finally:
            (a.output / (engine + ".json")).write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8"
            )
            browser.close()
