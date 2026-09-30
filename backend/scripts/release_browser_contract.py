"""Exercise the weekly planner form in real browsers without retailer calls.

The small local server serves checked-in UI files and records submitted JSON.
HTTP plan execution is verified separately against the packaged server.
"""

import argparse
import json
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar

from playwright.sync_api import sync_playwright

STATIC = Path(__file__).resolve().parents[1] / "app" / "static"


class Handler(SimpleHTTPRequestHandler):
    submitted: ClassVar[list[dict]] = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC), **kwargs)

    def log_message(self, *_args):
        pass

    def do_GET(self):
        if self.path == "/ready":
            self._json(200, {"status": "ready", "build_id": "ui-contract"})
            return
        if self.path.startswith("/static/"):
            self.path = self.path[len("/static") :]
        if self.path == "/":
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self):
        if self.path == "/api/plans":
            length = int(self.headers["Content-Length"])
            self.submitted.append(json.loads(self.rfile.read(length)))
            self._json(503, {"detail": "Isolerat UI-kontraktsprov"})
            return
        self._json(404, {"detail": "No route"})

    def _json(self, status, body):
        encoded = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    results = []
    try:
        with sync_playwright() as playwright:
            for browser_name in ("chromium", "webkit"):
                browser = getattr(playwright, browser_name).launch()
                try:
                    for mode, members in (
                        ("exact", ()),
                        ("estimated", ("LIDL_PLUS", "WILLYS_PLUS")),
                    ):
                        context = browser.new_context(viewport={"width": 390, "height": 844})
                        page = context.new_page()
                        errors = []
                        page.on("pageerror", lambda error, sink=errors: sink.append(str(error)))
                        page.goto(f"http://127.0.0.1:{server.server_port}/")
                        if page.locator("#onboarding-dialog").is_visible():
                            page.locator("#onboarding-cta").click()
                        page.locator("#submit-button").wait_for(state="visible")
                        page.wait_for_function("!document.querySelector('#submit-button').disabled")
                        page.locator("#max-stores").select_option("1" if members else "2")
                        page.locator("#purchase-planning-mode").select_option(mode)
                        if members:
                            page.locator("details.advanced-options summary").click()
                            for member in members:
                                page.locator(f'input[name="membership"][value="{member}"]').check()
                        page.screenshot(
                            path=str(args.output / f"{browser_name}-{mode}.png"), full_page=True
                        )
                        prior = len(Handler.submitted)
                        page.locator("#submit-button").click()
                        for _ in range(100):
                            if len(Handler.submitted) > prior:
                                break
                            page.wait_for_timeout(50)
                        assert len(Handler.submitted) == prior + 1
                        submitted = Handler.submitted[-1]
                        assert submitted["purchase_planning_mode"] == mode
                        assert submitted["max_stores"] == (1 if members else 2)
                        assert submitted["memberships"] == list(members)
                        assert not errors, errors
                        results.append(
                            {
                                "browser": browser_name,
                                "mode": mode,
                                "max_stores": submitted["max_stores"],
                                "memberships": submitted["memberships"],
                                "page_errors": errors,
                                "contract": "form JSON only; HTTP pricing verified separately",
                            }
                        )
                        context.close()
                finally:
                    browser.close()
    finally:
        server.shutdown()
        thread.join(10)
    target = args.output / "ui-contract.json"
    target.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results))


if __name__ == "__main__":
    main()
