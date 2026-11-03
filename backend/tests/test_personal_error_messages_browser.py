"""/personal never shows the browser's JSON or network error text."""

from __future__ import annotations

import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest
from playwright.sync_api import expect, sync_playwright

STATIC = Path(__file__).resolve().parents[1] / "app/static"
HTML_ERROR = "<!DOCTYPE html><html><body>502 Bad Gateway</body></html>"
RAW_TEXT = ("Unexpected token", "is not valid JSON", "Failed to fetch", "Load failed", "SyntaxError")


@pytest.fixture
def site():
    class Handler(SimpleHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            self.path = self.path.replace("/static/", "/")
            return super().do_GET()

    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Handler, directory=str(STATIC)))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/personal.html"
    server.shutdown()
    server.server_close()
    thread.join()


def open_page(pw, url, state):
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={"width": 390, "height": 900})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))

    def api(route):
        path = route.request.url.split("/api/")[-1].split("?")[0]
        if path == "personal/state":
            return state(route)
        if path == "shopping-location":
            return route.fulfill(status=200, content_type="text/html", body=HTML_ERROR)
        body = {"enabled": True} if path == "recipe-library" else {}
        return route.fulfill(status=200, content_type="application/json", body=json.dumps(body))

    page.route("**/api/**", api)
    page.route("**/scanner-assets/**", lambda route: route.fulfill(body=""))
    page.goto(url)
    return browser, page, errors


@pytest.mark.parametrize("state,expected", [
    (lambda r: r.fulfill(status=502, content_type="text/html", body=HTML_ERROR),
     "Servern svarar inte just nu"),
    (lambda r: r.fulfill(status=200, content_type="text/html", body=HTML_ERROR),
     "Servern svarade på ett oväntat sätt"),
    (lambda r: r.abort(), "Vi får ingen kontakt med servern"),
], ids=["html-502", "html-200", "offline"])
def test_api_failures_show_plain_swedish(site, state, expected):
    with sync_playwright() as pw:
        browser, page, errors = open_page(pw, site, state)
        expect(page.locator("body")).to_contain_text(expected)
        text = page.locator("body").inner_text()
        assert not any(raw in text for raw in RAW_TEXT), text[:600]
        assert not errors
        browser.close()


def test_postcode_lookup_with_html_response_is_plain(site):
    ok = {"revision": 0, "items": [], "reservations": {}, "profile": {}, "account": {"message": "Gäst"}}
    with sync_playwright() as pw:
        browser, page, errors = open_page(
            pw, site + "#choices",
            lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(ok)))
        page.locator("#customer-postcode").fill("22350")
        page.locator("#check-postcode").click()
        expect(page.locator("#location-status")).to_contain_text("Servern svarade på ett oväntat sätt")
        assert not any(raw in page.locator("#location-status").inner_text() for raw in RAW_TEXT)
        assert not errors
        browser.close()
