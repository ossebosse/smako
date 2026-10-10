"""Offline browser contract for the real controls with explicit fixture responses.

Does not claim collection, live prices or a successful meal calculation.
"""
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".local/verification/municipal-browser"
OUT.mkdir(parents=True, exist_ok=True)
rows = [
    {"municipality_code": "1281", "name": "Lund", "postal_code": "22350", "available": True},
    {"municipality_code": "1280", "name": "Malmö", "postal_code": "21120", "available": True},
    {"municipality_code": "1480", "name": "Göteborg", "postal_code": "41110", "available": False},
]
results = []
with sync_playwright() as pw:
    for engine in ("chromium", "webkit"):
        browser = getattr(pw, engine).launch()
        for personal in (False, True):
            context = browser.new_context(viewport={"width": 390, "height": 844},
                geolocation={"latitude": 55.6, "longitude": 13.0}, permissions=["geolocation"])
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error, errors=errors: errors.append(str(error)))

            def respond(route, personal=personal):
                url = urlsplit(route.request.url)
                if url.path == "/api/municipalities":
                    return route.fulfill(json={"municipalities": rows})
                if url.path == "/api/price-contexts":
                    query = parse_qs(url.query)
                    area = "malmo" if query["postal_code"] == ["21120"] else "lund"
                    return route.fulfill(json={"contexts": [{"context_id": area + str(i),
                        "display_name": area + " butik " + str(i), "address": "Testgatan " + str(i),
                        "price_scope_label": "onlinepris", "distance_km": i if "latitude" in query else None,
                        "distance_basis": "store"} for i in (1, 7)], "excluded": []})
                if url.path.startswith("/static/"):
                    path = ROOT / "backend/app/static" / url.path.removeprefix("/static/")
                    return route.fulfill(path=path)
                # Use both real postal markup shapes; the shared controls are unchanged.
                field = ('<label>Postnummer<input id="postal-code" value="22350"></label>' if personal else
                         '<div class="field"><label for="postal-code">Postnummer</label><input id="postal-code" value="22350"><span>Fem siffror</span></div>')
                return route.fulfill(content_type="text/html", body='<!doctype html><html lang="sv"><meta charset="utf-8"><link rel="stylesheet" href="/static/styles.css"><link rel="stylesheet" href="/static/complete-recipes.css"><body>'
                    + field + '<select id="recipes"><option value="5">5</option></select><input id="servings" value="4"><div id="controls"></div>'
                    + '<script src="/static/complete-recipes.js"></script><script src="/static/municipal-areas.js"></script>'
                    + '<script>window.controls=SmakoRecipes.controls(document.getElementById("controls"));controls.enabled(true);</script></body></html>')

            page.route("**/*", respond)
            page.goto("http://127.0.0.1:18392/")
            expect(page.locator("#municipality")).to_have_value("1281")
            expect(page.locator('#municipality option[value="1480"]')).to_be_disabled()
            expect(page.locator("#postal-code")).to_be_hidden()
            page.locator("#context-lund7").check()
            assert page.evaluate("controls.values().allowed_store_ids") == ["lund7"]
            page.locator("#municipality").select_option("1280")
            expect(page.locator("#context-malmo1")).to_be_visible()
            assert page.evaluate("controls.values().allowed_store_ids || []") == []
            page.get_by_role("button", name="Välj butiker nära mig").click()
            expect(page.locator("#context-malmo1")).to_be_checked()
            expect(page.locator("#context-malmo7")).not_to_be_checked()
            assert page.evaluate("controls.storeValues().allowed_store_ids") == ["malmo1"]
            page.locator("#municipality").select_option("1281")
            expect(page.locator("#context-lund7")).to_be_checked()
            page.locator("#municipality").select_option("1280")
            expect(page.locator("#context-malmo1")).to_be_checked()
            page.screenshot(path=OUT / f"{engine}-{'personal' if personal else 'public'}.png", full_page=True)
            assert not errors, errors
            results.append({"browser": engine, "postal_markup": "personal" if personal else "public", "status": "pass"})
            context.close()
        browser.close()
(OUT / "results.json").write_text(json.dumps({"evidence": "offline UI fixtures", "cases": results}, indent=2), encoding="utf-8")
print(json.dumps(results))
