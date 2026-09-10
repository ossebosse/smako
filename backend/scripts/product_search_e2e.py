"""Mobile browser acceptance against deterministic product contracts or public beta."""

import argparse
import json
import mimetypes
import threading
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from fastapi.encoders import jsonable_encoder
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "backend/app/static"


def fixture_server():
    from app.services.product_lookup import lookup_gtin
    from app.services.product_search import ProductSearchRequest

    from backend.tests.test_product_search import NOW, offer, prepare, product

    prepared = prepare(
        product(offers=[offer()]),
        product(
            "b", "coop", price=45, offers=[offer(kind="member", price=29.9, member_program="coop")]
        ),
        product(
            "milk",
            name="Arla mellanmjölk",
            brand="Arla",
            category="Mjölk",
            gtin=None,
            package_unit="ml",
            package_quantity=1500,
        ),
        product("alternative", name="Garant bryggkaffe", brand="Garant", gtin=None, price=55),
        product(
            "willys-coffee", "willys", name="Garant bryggkaffe", brand="Garant", gtin=None, price=55
        ),
        product("old-ica", "ica").model_copy(
            update={
                "source_provenance": product(store="ica").source_provenance.model_copy(
                    update={"source_observed_at": NOW - timedelta(hours=49)}
                )
            }
        ),
    )

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send(self, data, content_type="application/json"):
            body = data if isinstance(data, bytes) else json.dumps(jsonable_encoder(data)).encode()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = urlparse(self.path).path
            if path in {"/ready", "/health"}:
                return self.send({"status": "ready", "build_id": "fixture"})
            if path.startswith("/api/products/"):
                return self.send(
                    lookup_gtin(prepared, path.rsplit("/", 1)[-1]).model_dump(mode="json")
                )
            if path == "/":
                file = STATIC / "index.html"
            elif path == "/service-worker.js":
                file = STATIC / "service-worker.js"
            elif path.startswith("/static/"):
                file = STATIC / path.removeprefix("/static/")
            elif path == "/scanner-assets/physical-barcode-scanner.js":
                file = ROOT / "grocery_data/app/static/physical-barcode-scanner.js"
            else:
                return self.send({})
            return self.send(file.read_bytes(), mimetypes.guess_type(file)[0] or "text/plain")

        def do_POST(self):
            data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            if self.path == "/api/product-search":
                return self.send(
                    prepared.product_search_index.search(
                        ProductSearchRequest.model_validate(data), now=NOW
                    )
                )
            return self.send({})

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--webkit")
    parser.add_argument("--gtin", default="7311043007851")
    args = parser.parse_args()
    args.output.mkdir(exist_ok=True, parents=True)
    server = None if args.base_url else fixture_server()
    origin = args.base_url or f"http://127.0.0.1:{server.server_port}"
    reports = []
    with sync_playwright() as pw:
        for engine in ("chromium", "webkit"):
            kwargs = {"executable_path": args.webkit} if engine == "webkit" and args.webkit else {}
            browser = getattr(pw, engine).launch(**kwargs)
            context = browser.new_context(
                viewport={"width": 390, "height": 844}, device_scale_factor=3
            )
            page = context.new_page()
            errors, requests, checks = [], [], []
            page.on("pageerror", lambda e, errors=errors: errors.append(str(e)))
            page.on("request", lambda r, requests=requests: requests.append(r.url))
            page.goto(origin)
            page.locator("#onboarding-cta").click()
            page.locator("#product-query").fill("kaffe")
            page.locator("#product-search-form").evaluate("f=>f.requestSubmit()")
            page.wait_for_function(
                "() => document.querySelector('#product-search-form').getAttribute('aria-busy')==='false'"
            )
            assert page.locator(".product-result").count() > 0
            checks.append("mobile_generic_coffee")
            coverage = page.locator("#product-search-coverage")
            assert coverage.is_visible() and "Jämför just nu:" in coverage.inner_text()
            if not args.base_url:
                assert "Willys" in coverage.inner_text()
                assert "ICA jämförs inte: prisunderlag för gammalt" in coverage.inner_text()
            coverage.locator("summary").click()
            assert "Coop:" in coverage.inner_text() and "Hemköp:" in coverage.inner_text()
            checks.append("chain_coverage_and_reason_disclosure")
            first = page.locator(".product-result").first
            first.locator("summary").first.click()
            assert first.locator(".product-context").first.is_visible()
            checks.append("result_expansion")
            first.locator(".product-context details summary").first.click()
            assert "inte lagerbesked" in first.inner_text()
            checks.append("source_and_no_inventory_claim")
            page.locator("#product-search").screenshot(
                path=str(args.output / f"{engine}-coffee.png")
            )
            if not args.base_url:
                assert "39,90 kr" in first.inner_text()
                checkbox = page.locator('input[name="membership"][value="COOP_MEMBER"]')
                checkbox.evaluate(
                    "el => { let p=el.parentElement; while(p) {if(p.tagName==='DETAILS') p.open=true; p=p.parentElement;} }"
                )
                checkbox.check()
                page.wait_for_function(
                    "() => document.querySelector('.product-result-price')?.textContent==='29,90 kr'"
                )
                checks.append("selected_membership_reprices_same_identity")
            page.locator("#product-query").fill("mjölk")
            page.locator("#product-search-form").evaluate("f=>f.requestSubmit()")
            page.wait_for_function(
                "() => document.querySelector('#product-search-form').getAttribute('aria-busy')==='false'"
            )
            assert page.locator(".product-result").count() > 0
            checks.append("swedish_milk")
            if not args.base_url:
                coverage.locator("summary").click()
                assert "Willys: Ingen relevant träff" in coverage.inner_text()
                assert "ICA jämförs inte: prisunderlag för gammalt" in coverage.inner_text()
                checks.append("no_match_is_distinct_from_stale_source")
            page.locator("#scan-entry-button").click()
            page.locator("#manual-gtin").fill(args.gtin)
            page.locator("#manual-gtin-submit").click()
            page.get_by_role("button", name="Jämför priser och kampanjer").click()
            page.wait_for_function(
                "() => document.querySelector('#product-search-form').getAttribute('aria-busy')==='false'"
            )
            assert page.locator(".product-result").count() > 0
            assert page.locator("#product-query").input_value() == args.gtin
            checks.append("scanner_exact_gtin_comparison")
            # One barcode can retain separate groups when source package
            # evidence is absent or contradictory. Expand before sharing.
            comparison = page.locator(".product-result > details").first
            if comparison.get_attribute("open") is None:
                comparison.locator("summary").first.click()
            page.get_by_role("link", name="Öppna produktjämförelse").first.click()
            page.wait_for_function("() => location.search.includes('product=')")
            page.reload()
            page.wait_for_function(
                "() => document.querySelector('#product-search-form').getAttribute('aria-busy')==='false'"
            )
            assert page.locator(".product-result details").first.get_attribute("open") is not None
            checks.append("shareable_detail_reload")
            page.locator("#product-query").fill("4006381333931")
            page.locator("#product-search-form").evaluate("f=>f.requestSubmit()")
            page.wait_for_function(
                "() => document.querySelector('#product-search-form').getAttribute('aria-busy')==='false'"
            )
            assert "Ingen exakt träff" in page.locator("#product-search-status").inner_text()
            checks.append("unknown_barcode_no_fuzzy_identity")
            assert page.evaluate("document.documentElement.scrollWidth<=innerWidth+1")
            checks.append("no_mobile_horizontal_overflow")
            assert not errors, errors
            assert all(url.startswith(origin) for url in requests), requests
            checks.append("no_external_browser_requests")
            reports.append({"engine": engine, "checks": checks, "errors": errors})
            browser.close()
    if server:
        server.shutdown()
    (args.output / "results.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")
    print(json.dumps(reports))


if __name__ == "__main__":
    main()
