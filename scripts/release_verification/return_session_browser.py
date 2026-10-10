"""Bounded return/session regression on a real isolated app; transport injection is labelled.

No production URL is accepted. Real saved results are produced by the normal planner.
Use --before-ref to execute the same assertions against earlier static source.
"""

import argparse
import json
import subprocess
import time
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument("--base", default="http://127.0.0.1:18130")
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--before-ref")
a = parser.parse_args()
assert a.base.startswith("http://127.0.0.1:")
a.output.mkdir(parents=True, exist_ok=False)
reports = []
with sync_playwright() as pw:
    for engine in ("chromium", "webkit"):
        browser = getattr(pw, engine).launch()
        context = browser.new_context(viewport={"width": 390, "height": 844})
        if a.before_ref:
            for name in ("personal.js", "complete-recipes.js"):
                source = subprocess.check_output(
                    ["git", "show", f"{a.before_ref}:backend/app/static/{name}"]
                )
                context.route(
                    "**/static/" + name + "*",
                    lambda route, *, source=source: route.fulfill(
                        body=source, content_type="application/javascript"
                    ),
                )
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda e, *, errors=errors: errors.append(str(e)))
        page.goto(a.base + "/personal#shopping")
        expect(page.locator("#add-shopping-item")).to_be_enabled(timeout=120000)
        page.wait_for_load_state("networkidle")
        page.locator("#shopping-query").fill("mjölk")
        page.locator("#shopping-generic-results button").first.click()
        page.get_by_label("Önskad mängd", exact=True).fill("500")
        page.get_by_role("button", name="Bekräfta och lägg till", exact=True).click()
        expect(page.locator("#extras-list article")).to_have_count(1)
        page.wait_for_load_state("networkidle")
        # A complete real shopping job, double click, independent audit and saved GET.
        starts = []
        job_urls = []
        page.on(
            "request",
            lambda r, *, job_urls=job_urls: (
                job_urls.append(r.url) if "/api/plan-jobs/" in r.url else None
            ),
        )
        page.on(
            "request",
            lambda r, *, starts=starts: (
                starts.append(r) if r.method == "POST" and r.url.endswith("/api/plans") else None
            ),
        )
        page.locator("#calculate-own-list").dblclick()
        expect(page.locator("#shopping-content .personal-total")).to_be_visible(timeout=180000)
        assert len(starts) == 1
        real_job_url = job_urls[-1].removeprefix(a.base)
        plan_id = page.evaluate("localStorage.getItem('smako.personal.lastPlan')")
        saved = page.request.get(a.base + "/api/plans/" + plan_id).json()
        assert saved["plan"]["personal"]["checks"]["checkout_audit"]["passed"]
        other = browser.new_context()
        assert other.request.get(a.base + "/api/plans/" + plan_id).status == 403
        other.close()
        report = {
            "browser": engine,
            "real_audit": True,
            "double_start_posts": len(starts),
            "owner_isolation": 403,
            "cases": {},
        }
        reports.append(report)
        # Exact production response: this is a planning gate, not a lost response.
        blocks = []

        def blocked(route, *, blocks=blocks):
            blocks.append(route.request.method)
            route.fulfill(
                status=503,
                content_type="application/json",
                headers={"X-Error-Code": "price_universe_unusable"},
                body=json.dumps(
                    {"detail": "active local PriceUniverse is not usable for consumer planning"}
                ),
            )

        page.route("**/api/plans", blocked)
        page.locator("#calculate-own-list").click()
        try:
            expect(page.locator("#personal-status")).to_contain_text(
                "Prisunderlaget behöver uppdateras", timeout=5000
            )
            expect(page.locator("#calculate-own-list")).to_be_enabled()
            assert page.evaluate("SmakoRecipes.pendingJob('personal')") is None
            assert len(blocks) == 1
            expect(page.locator("#shopping-content .personal-total")).to_be_visible()
            report["cases"]["price_gate"] = "PASS"
        except AssertionError:
            report["cases"]["price_gate"] = {
                "result": "FAIL",
                "status": page.locator("#personal-status").inner_text(),
                "posts": len(blocks),
                "pending": bool(page.evaluate("SmakoRecipes.pendingJob('personal')")),
            }
            if not a.before_ref:
                raise
        page.unroute("**/api/plans", blocked)
        # Restoring a completed saved revision must happen before an old job lookup.
        # The two server 404 contracts are tested separately, never a new POST.
        for marker_kind in ("job", "unconfirmed"):
            marker = {
                "requestId": "11111111-1111-1111-1111-111111111111",
                "started_at": int((time.time() - 7200) * 1000),
            }
            if marker_kind == "job":
                marker["url"] = "/api/plan-jobs/" + "1" * 32
            page.evaluate("m => SmakoRecipes.storage.set('smako.planJob.personal', m)", marker)
            seen_saved = []

            def missing(route, *, seen_saved=seen_saved, page=page):
                seen_saved.append(page.locator("#shopping-content .personal-total").count() > 0)
                route.fulfill(
                    status=404,
                    content_type="application/json",
                    headers={"X-Error-Code": "planner_job_expired"},
                    body=json.dumps({"detail": "Jobbet saknas eller har gått ut."}),
                )

            page.route("**/api/plan-jobs/*", missing)
            page.route("**/api/plan-job-requests/*", missing)
            before = len(starts)
            page.goto(a.base + "/personal?return_case=" + marker_kind + "#shopping")
            page.wait_for_load_state("networkidle")
            try:
                expect(page.locator("#personal-status")).to_contain_text("gått ut", timeout=5000)
                expect(page.locator("#shopping-content .personal-total")).to_be_visible(
                    timeout=5000
                )
                expect(page.locator("#calculate-own-list")).to_be_enabled()
                assert page.evaluate("SmakoRecipes.pendingJob('personal')") is None
                assert seen_saved == [True], (
                    marker_kind,
                    seen_saved,
                    page.locator("#personal-status").inner_text(),
                )
                assert len(starts) == before
                expect(page.locator("#extras-list article")).to_have_count(1)
                expect(page.locator("#personal-status")).to_contain_text("gått ut")
                report["cases"][marker_kind + "_expired"] = "PASS"
            except AssertionError:
                report["cases"][marker_kind + "_expired"] = {
                    "result": "FAIL",
                    "saved_before_status": seen_saved,
                    "pending": bool(page.evaluate("SmakoRecipes.pendingJob('personal')")),
                }
                if not a.before_ref:
                    raise
            page.unroute("**/api/plan-jobs/*", missing)
            page.unroute("**/api/plan-job-requests/*", missing)
        if not a.before_ref:
            # Reopen the actual completed job after an injected failed status GET.
            # The saved revision is visible during retry; no start POST is allowed.
            marker = {
                "requestId": "22222222-2222-2222-2222-222222222222",
                "url": real_job_url,
                "started_at": int(time.time() * 1000),
            }
            page.evaluate("m => SmakoRecipes.storage.set('smako.planJob.personal', m)", marker)
            reconnect_calls = []

            def reset_once(route, *, reconnect_calls=reconnect_calls):
                reconnect_calls.append(route.request.method)
                if len(reconnect_calls) == 1:
                    route.abort("connectionreset")
                else:
                    route.continue_()

            page.route("**" + real_job_url, reset_once)
            before = len(starts)
            page.goto(a.base + "/personal?return_case=real_job#shopping")
            expect(page.locator("#shopping-content .personal-total")).to_be_visible()
            expect(page.get_by_role("button", name="Min plan", exact=True)).to_be_enabled()
            page.wait_for_function("!SmakoRecipes.pendingJob('personal')", timeout=15000)
            expect(page.locator("#calculate-own-list")).to_be_enabled()
            assert reconnect_calls == ["GET", "GET"] and len(starts) == before
            assert page.request.get(a.base + "/api/plans/" + plan_id).json() == saved
            report["cases"]["real_job_reconnect"] = {
                "result": "PASS",
                "injected_status_reset": 1,
                "same_job": True,
                "extra_posts": 0,
            }
            page.unroute("**" + real_job_url, reset_once)
        if not a.before_ref:
            # Transport-only controls, using the actual shared reader. They do not
            # count as successful planner jobs and cannot reach the backend POST.
            for case, codes in (
                ("unauthorized", [401]),
                ("forbidden", [403]),
                ("temporary_503", [503, 422]),
                ("invalid_body", [200]),
                ("lost_start", [0, 404]),
            ):
                calls = []

                def inject(route, *, calls=calls, codes=codes, case=case):
                    calls.append(route.request.method)
                    code = codes[min(len(calls) - 1, len(codes) - 1)]
                    if code == 0:
                        route.abort("connectionreset")
                    elif case == "invalid_body":
                        route.fulfill(
                            status=200, content_type="text/html", body="unexpected proxy body"
                        )
                    else:
                        route.fulfill(
                            status=code,
                            content_type="application/json",
                            body=json.dumps({"detail": "injected " + case}),
                        )

                page.route("**/api/plans", inject)
                page.route("**/api/plan-job-requests/*", inject)
                result = page.evaluate("""async () => {
                    SmakoRecipes.forgetJob('probe');
                    try {const r=await SmakoRecipes.jobRequest({scope:'probe',url:'/api/plans',payload:{},onProgress:()=>{}});return {status:r.status,pending:!!SmakoRecipes.pendingJob('probe')};}
                    catch(e){return {schema:!!e.schema,pending:!!SmakoRecipes.pendingJob('probe')};}
                }""")
                if case in ("unauthorized", "forbidden"):
                    assert len(calls) == 1 and not result["pending"]
                elif case == "temporary_503":
                    assert (
                        calls == ["POST", "POST"]
                        and result["status"] == 422
                        and not result["pending"]
                    )
                elif case == "invalid_body":
                    assert calls == ["POST"] and result["schema"]
                else:
                    assert calls[0] == "POST" and set(calls[1:]) == {"GET"}
                    assert result["status"] == 404 and not result["pending"]
                report["cases"][case] = {"result": "PASS", "injected": True, "methods": calls}
                page.unroute("**/api/plans", inject)
                page.unroute("**/api/plan-job-requests/*", inject)
                page.evaluate("SmakoRecipes.forgetJob('probe')")
        assert page.request.get(a.base + "/api/plans/" + plan_id).json() == saved
        report["saved_revision_unchanged"] = True
        report["page_errors"] = errors
        assert not errors
        (a.output / (engine + ".json")).write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8"
        )
        print(engine, json.dumps(report["cases"], ensure_ascii=False), flush=True)
        browser.close()
(a.output / "results.json").write_text(
    json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf8"
)
