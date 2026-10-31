"""Real quick-menu UI against an isolated ordinary application."""

import argparse
import json
import time
import urllib.request
from pathlib import Path

from complete_recipe_browser import open_view, record_response, wait_operation
from playwright.sync_api import expect, sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument("--base", default="http://127.0.0.1:18130")
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--expected-build", required=True)
a = parser.parse_args()
assert a.base.startswith("http://127.0.0.1:")
a.output.mkdir(parents=True, exist_ok=False)
for attempt in range(120):
    try:
        with urllib.request.urlopen(a.base + "/ready", timeout=3) as response:
            ready = json.load(response)
        if ready["build_id"] == a.expected_build and ready["status"] == "ready":
            break
    except OSError:
        pass
    time.sleep(1)
else:
    raise TimeoutError("Expected isolated runtime was not ready")
with sync_playwright() as pw:
    for engine in ("chromium", "webkit"):
        browser = getattr(pw, engine).launch()
        context = browser.new_context(viewport={"width": 390, "height": 844})
        page = context.new_page()
        errors = []
        failed = []
        observed = []
        page.on("pageerror", lambda e, errors=errors: errors.append(str(e)))
        page.on(
            "requestfailed",
            lambda r, failed=failed: failed.append({"url": r.url, "error": r.failure}),
        )
        page.on("response", lambda r, observed=observed: record_response(r, observed))
        page.goto(a.base + "/personal#shopping")
        expect(page.locator("#add-shopping-item")).to_be_enabled(timeout=120000)
        page.wait_for_load_state("networkidle")
        expect(page.locator("#generic-extra")).to_have_count(0)
        expect(page.locator('#personal-shopping [data-open="product-search"]')).to_have_count(0)
        expect(page.locator("#shopping-suggestions")).to_be_hidden()
        page.get_by_role("button", name="Lägg till vara", exact=True).click()
        expect(page.locator("#shopping-query")).to_be_focused()

        def search(text, page=page):
            with page.expect_response(lambda response: "/shopping-suggestions?" in response.url) as response:
                page.locator("#shopping-query").fill(text)
            data = response.value.json()
            page.wait_for_load_state("networkidle")
            expect(page.locator("#shopping-suggestions")).to_be_visible()
            assert "source_label" not in json.dumps(data) and '"prices"' not in json.dumps(data)
            assert not any(
                x in page.locator("#shopping-suggestions").inner_text()
                for x in ("Willys", "Hemköp", "Coop Online")
            )
            return data

        coffee = search("Kaffe")
        expect(page.locator("#shopping-suggestions button").first).to_have_text(
            "Lägg till ”Kaffe” – välj mängd"
        )
        expect(page.locator("#shopping-generic-results")).to_contain_text("Lägg till Bryggkaffe · 500 g")
        labels = page.locator("#shopping-specific-results button").all_text_contents()
        assert labels and len(labels) == len(set(labels))
        assert "Bryggkaffe" in labels[0] and "null" not in " ".join(labels)
        page.locator("#shopping-query").evaluate("element => element.scrollIntoView({block: 'start'})")
        page.screenshot(path=str(a.output / (engine + "-coffee.png")))
        page.locator("#shopping-query").press("ArrowDown")
        expect(page.locator("#shopping-generic-results button").first).to_be_focused()
        page.keyboard.press("Enter")
        page.get_by_label("Önskad mängd", exact=True).fill("600")
        page.get_by_role("button", name="Bekräfta och lägg till", exact=True).click()
        expect(page.locator("#extras-list article")).to_have_count(1)
        page.get_by_role("button", name="Ändra vara", exact=True).click()
        page.get_by_label("Enhet", exact=True).select_option("st")
        page.get_by_label("Önskad mängd", exact=True).fill("2")
        page.get_by_role("button", name="Spara vara", exact=True).click()
        expect(page.locator("#extras-list")).to_contain_text("2 st")
        state = page.request.get(a.base + "/api/personal/state").json()
        assert len(state["shopping_items"]) == 1 and state["shopping_items"][0]["unit"] == "st"
        page.get_by_role("button", name="Ta bort extrarad", exact=True).click()
        expect(page.locator("#extras-list article")).to_have_count(0)
        milk = search("mjölk")
        product = next(
            p for p in milk["products"] if p["package_unit"] == "ml" and len(p["matches"]) == 1
        )
        page.locator(".shopping-exact-toggle").click()
        page.locator("#shopping-specific-results").get_by_role(
            "button", name=product["display_name"] + " · " + product["package"], exact=True
        ).click()
        page.get_by_role("button", name="Tillbaka till generisk vara", exact=True).click()
        expect(page.get_by_label("Vara", exact=True)).to_have_value("mjölk")
        page.get_by_label("Önskad mängd", exact=True).fill("500")
        page.get_by_role("button", name="Bekräfta och lägg till", exact=True).click()
        expect(page.locator("#extras-list article")).to_have_count(1)
        pasta = search("spaghetti")
        product = next(
            p for p in pasta["products"] if 1 < len(p["matches"]) <= 8 and p["package_unit"] == "g"
        )
        page.locator(".shopping-exact-toggle").click()
        page.locator("#shopping-specific-results").get_by_role(
            "button", name=product["display_name"] + " · " + product["package"], exact=True
        ).click()
        expect(page.locator("#dialog-body")).not_to_contain_text("Willys")
        expect(page.locator("#dialog-body")).to_contain_text("separata produktidentiteter")
        page.get_by_role("button", name="Bekräfta och lägg till", exact=True).click()
        expect(page.locator("#extras-list article")).to_have_count(2)
        state = page.request.get(a.base + "/api/personal/state").json()
        assert set(state["shopping_items"][1]["alternatives"]) == {
            m["product_key"] for m in product["matches"]
        }
        page.wait_for_load_state("networkidle")
        page.reload()
        page.wait_for_load_state("networkidle")
        expect(page.locator("#extras-list article")).to_have_count(2)
        open_view(page, "shopping")
        page.wait_for_load_state("networkidle")
        begin = len(observed)
        page.locator("#calculate-own-list").dblclick()
        operation, _ = wait_operation(page, observed, begin, timeout=180)
        expect(page.locator("#shopping-content .personal-total")).to_be_visible(timeout=180000)
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
        assert saved["plan"]["personal"]["checks"]["checkout_audit"]["passed"]
        assert (
            page.request.get(a.base + "/api/plans/" + saved["plan_id"]).json()["plan"]
            == saved["plan"]
        )
        other = browser.new_context()
        assert other.request.get(a.base + "/api/plans/" + saved["plan_id"]).status == 403
        other.close()
        report = {
            "browser": engine,
            "errors": errors,
            "failed_requests": failed,
            "operation": operation,
            "coffee_labels": labels,
            "group_members": len(product["matches"]),
            "audit_passed": True,
            "start_posts": len(starts),
            "saved_get_equal": True,
            "owner_isolation": 403,
        }
        (a.output / (engine + ".json")).write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8"
        )
        assert not errors and not failed, (errors, failed)
        assert not [r.status for r in observed if r.status >= 500]
        print(engine, "PASS", flush=True)
        browser.close()
