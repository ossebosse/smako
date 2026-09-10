"""Browser regression for planner ownership; fixture HTTP only, no provider calls.
Run with --fixture a sanitized PlanResponse JSON and --output an owned scratch path.
Use --old-script for the pre-fix regression; it must fail at saved_plan_reload.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "backend/app/static"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--webkit", type=str)
    parser.add_argument("--old-script", type=Path)
    parser.add_argument("--previous-dir", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    fixture = json.loads(args.fixture.read_bytes())
    envelope = {
        "plan": fixture,
        "plan_id": "own-fixture",
        "request": {"postal_code": "22350", "recipes": 5, "servings": 4, "max_stores": 2},
    }
    previous_script = args.old_script or (
        args.previous_dir / "app-before.js" if args.previous_dir else None
    )
    state = {"posts": 0, "next": None, "old": bool(args.old_script)}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send(self, status=200, data=None, content_type="application/json", headers=None):
            body = data if isinstance(data, bytes) else json.dumps(data or {}).encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for key, value in (headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/ready":
                return self.send(data={"status": "ready", "build_id": "fixture"})
            if path.startswith("/api/plans/"):
                return self.send(data=envelope)
            if path == "/offline-check":
                # Simulate origin connection loss, including on Windows WebKit
                # where context.set_offline navigation raises an internal engine error.
                self.connection.shutdown(socket.SHUT_RDWR)
                self.connection.close()
                return
            if path == "/away":
                return self.send(data=b'<a href="/">Back</a>', content_type="text/html")
            if path == "/":
                file = STATIC / "index.html"
            elif path == "/service-worker.js":
                file = STATIC / "service-worker.js"
            elif path.startswith("/static/"):
                file = STATIC / path.removeprefix("/static/")
            else:
                return self.send(data={})
            if state["old"] and path == "/static/app.js":
                file = previous_script
            if state["old"] and path == "/service-worker.js":
                file = previous_script.parent / "sw-before.js"
            if state["old"] and path == "/":
                html = file.read_text(encoding="utf-8")
                html = html.replace("/static/app.js?v=product-search-20260909", "/static/app.js")
                html = html.replace(
                    '<script src="/static/frontend-bootstrap.js?v=loading-hotfix-20260909" defer></script>',
                    "",
                )
                return self.send(data=html.encode(), content_type="text/html")
            if not file or not file.is_file():
                return self.send(404)
            return self.send(
                data=file.read_bytes(), content_type=mimetypes.guess_type(file)[0] or "text/plain"
            )

        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            if urlparse(self.path).path == "/api/plans":
                state["posts"] += 1
                if state["next"]:
                    status, data, type_, headers = state["next"]
                    state["next"] = None
                    return self.send(status, data, type_, headers)
                return self.send(data=envelope)
            return self.send(data={})

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    origin = f"http://127.0.0.1:{server.server_port}"
    reports = []
    with sync_playwright() as pw:
        for browser_name in ("chromium", "webkit"):
            checks = []
            errors = []
            state["posts"] = 0
            state["next"] = None
            kwargs = (
                {"ignore_default_args": ["--disable-back-forward-cache"]}
                if browser_name == "chromium"
                else {}
            )
            if browser_name == "webkit" and args.webkit:
                kwargs["executable_path"] = args.webkit
            try:
                browser = getattr(pw, browser_name).launch(**kwargs)
            except (AssertionError, PlaywrightError, OSError, ValueError) as exc:
                reports.append(
                    {
                        "browser": browser_name,
                        "status": "UNAVAILABLE",
                        "reason": str(exc).splitlines()[0],
                    }
                )
                continue
            context = browser.new_context(
                viewport={"width": 390, "height": 844}, service_workers="block"
            )
            context.add_init_script(
                "localStorage.setItem('grocery-beta-onboarding-seen-v1','true')"
            )
            page = context.new_page()
            page.on("pageerror", lambda err, errors=errors: errors.append(str(err)))

            def ready(page=page):
                page.wait_for_function(
                    "!document.querySelector('#submit-button').disabled && document.querySelector('#plan-form').getAttribute('aria-busy') !== 'true'"
                )
                assert "Skapar" not in page.locator("#submit-button").inner_text()

            def submit(page=page):
                page.locator("#plan-form").evaluate("f => f.requestSubmit()")

            def done(page=page, ready=ready):
                page.locator("#results").wait_for(state="visible")
                ready()

            def check(name, checks=checks):
                checks.append(name)

            try:
                page.goto(origin)
                ready()
                assert state["posts"] == 0
                check("fresh_ready_no_post")
                page.evaluate("localStorage.setItem('grocery-last-plan-id-v1','own-fixture')")
                page.reload()
                page.locator("#results").wait_for(state="visible")
                # This is the actual pre-fix failure: GET completed, result visible, busy forever.
                assert not page.locator("#submit-button").is_disabled(), (
                    "saved_plan_reload leaves button busy without POST"
                )
                ready()
                assert state["posts"] == 0
                check("saved_plan_reload")
                comparison = fixture.get("plans", {}).get("varied", {}).get("inter_plan_distance")
                if comparison:
                    card = page.locator('.plan-option-card[data-plan-mode="varied"]')
                    text = card.inner_text()
                    assert (f"{comparison['structurally_different_dinners']} av "
                            f"{comparison['dinner_count']} middagar skiljer sig från Balanserad") in text
                    assert "Rättfamiljer" in text and "Tillagningssätt" in text
                    assert "dyrare totalt" in text or "Samma totalpris" in text or "billigare totalt" in text
                    assert "huvudråvara_" not in text and "pan_cook" not in text
                    if not comparison["target_met"]:
                        assert "middagar kunde ändras" in text
                    check("conditioned_varied_consumer_card")
                for _ in range(2):
                    submit()
                    done()
                assert state["posts"] == 2
                check("create_result_create_again")
                before = state["posts"]
                page.locator("#plan-form").evaluate(
                    "f=>{f.dispatchEvent(new Event('submit',{cancelable:true}));f.dispatchEvent(new Event('submit',{cancelable:true}));}"
                )
                done()
                assert state["posts"] == before + 1
                check("double_submit_one_job")
                for status, body, type_, headers, expected in (
                    (
                        422,
                        {"detail": [{"msg": "raw validation"}]},
                        "application/json",
                        {},
                        "Kontrollera dina val",
                    ),
                    (429, {}, "application/json", {"Retry-After": "55"}, "55 sekunder"),
                    (
                        503,
                        {},
                        "application/json",
                        {"Retry-After": "55", "X-Error-Code": "planner_admission_full"},
                        "55 sekunder",
                    ),
                    (504, b"<html>gateway</html>", "text/html", {}, "svarade inte i tid"),
                    (200, b"<html>not a plan</html>", "text/html", {}, "ogiltigt"),
                    (200, b"{broken", "application/json", {}, "ogiltigt"),
                    (200, {}, "application/json", {}, "ogiltigt"),
                ):
                    state["next"] = (status, body, type_, headers)
                    before = state["posts"]
                    submit()
                    page.locator("#error-state").wait_for(state="visible")
                    ready()
                    assert expected in page.locator("#error-message").inner_text()
                    assert (
                        state["posts"] == before + 1
                        and page.locator("#postal-code").input_value() == "22350"
                    )
                    check(f"http_{status}_{expected}")
                page.evaluate(
                    """() => {window.originalFetch=window.fetch; window.fetch=(url,opts)=>url==='/api/plans'?Promise.reject(new TypeError('Load failed')):originalFetch(url,opts)}"""
                )
                submit()
                page.locator("#error-state").wait_for(state="visible")
                ready()
                assert "anslutningen" in page.locator("#error-message").inner_text()
                check("network_failure_webkit_and_chromium_copy")
                page.evaluate("window.fetch=window.originalFetch")
                page.evaluate(
                    """() => {const node=document.querySelector('#recipes-list');const original=node.replaceChildren;node.replaceChildren=function(...args){node.replaceChildren=original;throw new TypeError('injected render failure')}}"""
                )
                submit()
                page.locator("#error-state").wait_for(state="visible")
                ready()
                assert "kunde inte visas" in page.locator("#error-message").inner_text()
                check("render_failure_cleanup")
                # Ignore abort in a test transport to prove late completion cannot mutate the next request.
                page.evaluate(
                    """() => {window.pending=[];window.fetch=(url,opts)=>url==='/api/plans'?new Promise(resolve=>pending.push(resolve)):originalFetch(url,opts)}"""
                )
                submit()
                page.wait_for_function("pending.length===1")
                page.evaluate(
                    "window.dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true}));document.dispatchEvent(new Event('visibilitychange'))"
                )
                assert page.locator("#submit-button").is_disabled()
                check("active_job_survives_return")
                page.evaluate(
                    """() => {window.realNow=Date.now;Date.now=()=>realNow()+91000;window.dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true}))}"""
                )
                page.locator("#error-state").wait_for(state="visible")
                ready()
                assert "Servern kan fortfarande" in page.locator("#error-message").inner_text()
                check("deadline_on_background_return")
                page.evaluate("Date.now=window.realNow")
                submit()
                page.wait_for_function("pending.length===2")
                page.evaluate(
                    '(body)=>pending[0](new Response(JSON.stringify(body),{headers:{"Content-Type":"application/json"}}))',
                    envelope,
                )
                page.wait_for_timeout(100)
                assert page.locator("#submit-button").is_disabled()
                check("late_response_cannot_release_new_request")
                page.evaluate(
                    '(body)=>pending[1](new Response(JSON.stringify(body),{headers:{"Content-Type":"application/json"}}))',
                    envelope,
                )
                done()
                submit()
                page.wait_for_function("pending.length===3")
                page.evaluate(
                    "window.dispatchEvent(new PageTransitionEvent('pagehide',{persisted:false}))"
                )
                page.locator("#error-state").wait_for(state="visible")
                ready()
                assert "avbröts" in page.locator("#error-message").inner_text()
                check("abort_cleanup")
                page.evaluate("window.fetch=window.originalFetch")
                page.evaluate(
                    "document.querySelector('#plan-form').setAttribute('aria-busy','true');document.querySelector('#submit-button').disabled=true;document.querySelector('.button-label').textContent='Skapar veckomenyn…';window.dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true}))"
                )
                ready()
                check("orphan_dom_reconciled")
                before = state["posts"]
                page.goto(origin + "/away")
                page.go_back()
                page.locator("#results").wait_for(state="visible")
                ready()
                page.go_forward()
                page.go_back()
                ready()
                assert state["posts"] == before
                check("actual_back_forward_no_post")
                # New navigation has a pending saved read, superseded by an explicit planning click.
                page.add_init_script(
                    """(() => {const orig=window.fetch;window.fetch=(url,opts)=>String(url).startsWith('/api/plans/')?new Promise(resolve=>window.oldRestore=resolve):orig(url,opts)})()"""
                )
                page.reload()
                ready()
                page.wait_for_function('typeof oldRestore === "function"')
                submit()
                done()
                page.evaluate(
                    '(body)=>oldRestore(new Response(JSON.stringify({...body,plan:{...body.plan,location:"OBSOLETE RESTORE"}}),{headers:{"Content-Type":"application/json"}}))',
                    envelope,
                )
                page.wait_for_timeout(100)
                assert "OBSOLETE" not in page.locator("#result-location").inner_text()
                ready()
                check("late_saved_read_cannot_overwrite_new_plan")
                page.evaluate(
                    """() => {const timerOriginalFetch=window.fetch;window.fetch=(url,opts)=>url==='/api/plans'?new Promise(()=>{}):timerOriginalFetch(url,opts)}"""
                )
                page.clock.install()
                submit()
                page.clock.fast_forward(90001)
                page.locator("#error-state").wait_for(state="visible")
                ready()
                assert "för lång tid" in page.locator("#error-message").inner_text()
                check("finite_90_second_timer")
                page.locator(".planner-card").screenshot(
                    path=str(args.output / (browser_name + "-ready.png"))
                )
                assert not errors, errors
                # A failed app download must produce recovery, not an invented job.
                recovery = browser.new_context(service_workers="block")
                recovery.route("**/static/app.js*", lambda route: route.abort())
                rp = recovery.new_page()
                rp.goto(origin)
                rp.get_by_text("Sidan kunde inte starta", exact=True).wait_for()
                assert rp.locator("#plan-form").get_attribute("aria-busy") == "false"
                assert "Skapar" not in rp.locator("#submit-button").inner_text()
                recovery.close()
                check("initialization_failure_recovery")
                if args.previous_dir:
                    state["old"] = True
                    upgrade = browser.new_context(service_workers="allow")
                    up = upgrade.new_page()
                    up.goto(origin)
                    up.evaluate(
                        "localStorage.setItem('grocery-beta-onboarding-seen-v1','true');localStorage.setItem('grocery-last-plan-id-v1','own-fixture')"
                    )
                    up.evaluate("navigator.serviceWorker.ready")
                    up.reload()
                    up.locator("#results").wait_for(state="visible")
                    assert up.locator("#submit-button").is_disabled()
                    before_storage = up.evaluate("JSON.stringify({...localStorage})")
                    up.evaluate(
                        "caches.open('unrelated-owned-cache').then(c=>c.put('/keep',new Response('keep')))"
                    )
                    state["old"] = False
                    up.evaluate("navigator.serviceWorker.getRegistration().then(r=>r.update())")
                    up.wait_for_function(
                        "async()=> (await caches.keys()).includes('billigaste-veckomenyn-shell-v7')"
                    )
                    up.wait_for_function("async()=>{const r=await navigator.serviceWorker.getRegistration();return r?.active?.state==='activated' && !r.installing && !r.waiting && (await caches.keys()).filter(k=>k.startsWith('billigaste-veckomenyn-shell-')).every(k=>k.endsWith('v5'))}")
                    up.reload()
                    up.wait_for_function(
                        "document.documentElement.dataset.frontendVersion==='loading-hotfix-20260909'"
                    )
                    up.locator("#results").wait_for(state="visible")
                    up.wait_for_function("!document.querySelector('#submit-button').disabled")
                    assert up.evaluate("JSON.stringify({...localStorage})") == before_storage
                    assert up.evaluate("caches.has('unrelated-owned-cache')")
                    if browser_name == "chromium":
                        upgrade.set_offline(True)
                    up.goto(origin + "/offline-check")
                    up.get_by_text("Ingen anslutning just nu", exact=True).first.wait_for()
                    upgrade.close()
                    check("old_worker_updates_without_storage_erasure_and_keeps_offline")
                reports.append(
                    {
                        "browser": browser_name,
                        "status": "PASS",
                        "checks": checks,
                        "page_errors": errors,
                        "scope": "real browser, isolated fixture HTTP; lifecycle events include explicit bfcache simulation",
                    }
                )
            except (AssertionError, PlaywrightError, OSError, ValueError) as exc:
                reports.append(
                    {
                        "browser": browser_name,
                        "status": "FAIL",
                        "checks": checks,
                        "error": str(exc),
                        "page_errors": errors,
                    }
                )
            finally:
                context.close()
                browser.close()
    server.shutdown()
    (args.output / "browser-regression.json").write_text(
        json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(reports, ensure_ascii=True))
    return 0 if all(r["status"] == "PASS" for r in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
