"""Bounded public product-search UI check; no menu generation; beta requires explicit opt-in."""

import argparse
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

p = argparse.ArgumentParser()
p.add_argument("--base", required=True)
p.add_argument("--output", type=Path, required=True)
p.add_argument("--allow-beta", action="store_true", help="Explicitly authorized beta verification with new test identities")
a = p.parse_args()
assert a.base.startswith("http://127.0.0.1:") or (a.allow_beta and a.base == "https://beta.smako.nu")
a.output.mkdir(parents=True, exist_ok=False)
with sync_playwright() as pw:
    for engine in ["chromium", "webkit"]:
        browser = getattr(pw, engine).launch()
        page = browser.new_page(viewport={"width": 390, "height": 844})
        errors = []
        failed = []
        server_errors = []
        page.on("pageerror", lambda e, errors=errors: errors.append(str(e)))
        page.on("requestfailed", lambda r, failed=failed: failed.append(r.failure))
        page.on(
            "response",
            lambda r, server_errors=server_errors: (
                server_errors.append(r.status) if r.status >= 500 else None
            ),
        )
        result = {}
        try:
            page.goto(a.base + "/")
            page.wait_for_load_state("networkidle")
            page.locator("#onboarding-cta").click()
            page.locator("#product-query").fill("Aluminiumfolie")
            page.locator("#product-search-form button[type=submit]").click()
            expect(page.locator("#product-search-results")).to_contain_text(
                "/köpförpackning", timeout=30000
            )
            page.locator("#product-search-coverage summary").click()
            expect(page.locator("#product-search-coverage")).to_contain_text("City Gross")
            expect(page.locator("#product-search-coverage")).to_contain_text("underlag")
            page.screenshot(path=str(a.output / (engine + ".png")))
            assert not errors and not failed and not server_errors
            result = {
                "status": "PASS",
                "engine": engine,
                "pack_price_label": True,
                "coverage_gap": True,
                "page_errors": errors,
                "failed_requests": failed,
                "server_errors": server_errors,
            }
        except Exception as e:
            result = {
                "status": "FAIL",
                "error": repr(e),
                "page_errors": errors,
                "failed_requests": failed,
                "server_errors": server_errors,
            }
            raise
        finally:
            (a.output / (engine + ".json")).write_text(
                json.dumps(result, ensure_ascii=False, indent=2), encoding="utf8"
            )
            browser.close()
