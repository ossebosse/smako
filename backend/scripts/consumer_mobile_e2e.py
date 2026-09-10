"""Repeatable, community-evidence-safe mobile smoke test against a running server.

The flow creates a saved plan through the normal consumer endpoint but never
submits community evidence. Receipt, optimizer and provider internals are not
used by this test.
"""

from __future__ import annotations

import argparse
import json
import re
import ssl
import sys
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

from playwright.sync_api import Page, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_OUTPUT = Path("reports/consumer-product")
VIEWPORT = {"width": 390, "height": 844}
PLAN_TIMEOUT_SECONDS = 45.0
TEST_GTIN = "7311043007851"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--plan-timeout", type=float, default=PLAN_TIMEOUT_SECONDS)
    parser.add_argument(
        "--landing-only",
        action="store_true",
        help="Validate the initial mobile shell without submitting a plan.",
    )
    parser.add_argument("--headed", action="store_true")
    parser.add_argument(
        "--ignore-https-errors",
        action="store_true",
        help="Allow a local test CA; never use this to approve a public TLS failure.",
    )
    return parser.parse_args()


def server_health(
    base_url: str,
    *,
    ignore_https_errors: bool = False,
) -> dict[str, Any]:
    tls_context: ssl.SSLContext | None = None
    if ignore_https_errors:
        # Explicit local-test escape hatch only. Public acceptance must run
        # without this flag so ACME/hostname verification is genuinely tested.
        tls_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        tls_context.check_hostname = False
        tls_context.verify_mode = ssl.CERT_NONE
    try:
        with urlopen(
            f"{base_url.rstrip('/')}/health",
            timeout=5,
            context=tls_context,
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return {
                "http_status": response.status,
                "payload": payload,
                "tls_verification_bypassed": ignore_https_errors,
            }
    except (OSError, URLError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Servern svarar inte på {base_url}: {exc}") from exc


def horizontal_metrics(page: Page) -> dict[str, int | bool]:
    metrics = page.evaluate(
        """() => ({
          viewport: window.innerWidth,
          document: document.documentElement.scrollWidth,
          body: document.body.scrollWidth,
        })"""
    )
    metrics["has_overflow"] = max(metrics["document"], metrics["body"]) > metrics["viewport"] + 1
    return metrics


def assert_check(
    checks: list[dict[str, Any]],
    name: str,
    condition: bool,
    detail: Any,
) -> None:
    checks.append({"name": name, "passed": bool(condition), "detail": detail})
    if not condition:
        raise AssertionError(f"{name}: {detail}")


def screenshot(page: Page, directory: Path, name: str) -> str:
    path = directory / f"mobile-e2e-{name}.png"
    page.screenshot(path=str(path), full_page=True)
    return path.as_posix()


def markdown_report(result: dict[str, Any]) -> str:
    status = result["status"]
    lines = [
        "# Consumer mobile E2E",
        "",
        f"- Status: **{status}**",
        f"- Generated UTC: `{result['generated_at_utc']}`",
        f"- URL: `{result['base_url']}`",
        f"- Viewport: `{result['viewport']['width']}x{result['viewport']['height']}`",
        f"- Scope: `{result['scope']}`",
    ]
    if result.get("plan_runtime_seconds") is not None:
        lines.append(f"- Plan runtime: `{result['plan_runtime_seconds']:.3f} s`")
    lines.extend(["", "## Checks", "", "| Check | Result | Detail |", "|---|---:|---|"])
    for check in result["checks"]:
        detail = str(check.get("detail", "")).replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {check['name']} | {'PASS' if check['passed'] else 'FAIL'} | {detail} |")
    if result.get("summary"):
        lines.extend(["", "## Consumer result", ""])
        for key, value in result["summary"].items():
            lines.append(f"- {key}: `{value}`")
    if result.get("screenshots"):
        lines.extend(["", "## Screenshots", ""])
        lines.extend(f"- `{path}`" for path in result["screenshots"])
    if result.get("error"):
        lines.extend(["", "## Error", "", f"```text\n{result['error']}\n```"])
    return "\n".join(lines) + "\n"


def write_result(output_dir: Path, result: dict[str, Any]) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    json_path = output_dir / f"consumer-mobile-e2e-{stamp}.json"
    markdown_path = output_dir / f"consumer-mobile-e2e-{stamp}.md"
    rendered_json = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    rendered_markdown = markdown_report(result)
    json_path.write_text(rendered_json, encoding="utf-8")
    markdown_path.write_text(rendered_markdown, encoding="utf-8")
    (output_dir / "consumer-mobile-e2e-latest.json").write_text(rendered_json, encoding="utf-8")
    (output_dir / "consumer-mobile-e2e-latest.md").write_text(
        rendered_markdown,
        encoding="utf-8",
    )
    return json_path, markdown_path


def run_e2e(args: argparse.Namespace) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    screenshots: list[str] = []
    console_errors: list[str] = []
    ignored_console_errors: list[str] = []
    page_errors: list[str] = []
    community_writes: list[str] = []
    plan_runtime: float | None = None
    summary: dict[str, Any] = {}
    error: str | None = None
    status = "FAILED"
    base_url = args.base_url.rstrip("/")
    health = server_health(
        base_url,
        ignore_https_errors=args.ignore_https_errors,
    )
    screenshot_dir = args.output_dir / "screenshots"
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=not args.headed,
                args=[
                    "--use-fake-device-for-media-stream",
                    "--use-fake-ui-for-media-stream",
                ],
            )
            context = browser.new_context(
                viewport=VIEWPORT,
                device_scale_factor=1,
                is_mobile=True,
                has_touch=True,
                locale="sv-SE",
                ignore_https_errors=args.ignore_https_errors,
                permissions=["camera"],
            )
            page = context.new_page()
            page.set_default_timeout(10_000)
            page.on(
                "console",
                lambda message: console_errors.append(message.text)
                if message.type == "error"
                else None,
            )
            page.on("pageerror", lambda exception: page_errors.append(str(exception)))

            def guard_community_write(route: Any) -> None:
                request = route.request
                if request.method == "POST":
                    community_writes.append(request.url)
                    route.abort()
                else:
                    route.continue_()

            page.route("**/api/community-evidence**", guard_community_write)
            page.goto(base_url, wait_until="domcontentloaded")
            page.locator("#plan-form").wait_for(state="visible")

            onboarding = page.locator("#onboarding-dialog")
            assert_check(
                checks,
                "first_visit_onboarding_opens",
                onboarding.get_attribute("open") is not None,
                onboarding.locator("#onboarding-title").inner_text(),
            )
            assert_check(
                checks,
                "onboarding_has_three_ideas",
                onboarding.locator(".onboarding-steps li").count() == 3,
                onboarding.locator(".onboarding-steps li").count(),
            )
            screenshots.append(screenshot(page, screenshot_dir, "onboarding"))
            page.locator("#onboarding-cta").click()
            assert_check(
                checks,
                "onboarding_closes",
                onboarding.get_attribute("open") is None,
                "closed",
            )

            secure_context = page.evaluate(
                """() => ({
                  secure: window.isSecureContext,
                  cameraApi: typeof navigator.mediaDevices?.getUserMedia === 'function',
                  serviceWorkerApi: 'serviceWorker' in navigator,
                  manifest: document.querySelector('link[rel="manifest"]')?.href || null,
                })"""
            )
            assert_check(checks, "secure_context", secure_context["secure"], secure_context)
            assert_check(checks, "camera_api_available", secure_context["cameraApi"], secure_context)
            assert_check(
                checks,
                "pwa_manifest_and_worker_available",
                secure_context["serviceWorkerApi"] and bool(secure_context["manifest"]),
                secure_context,
            )

            landing_overflow = horizontal_metrics(page)
            assert_check(checks, "landing_no_horizontal_overflow", not landing_overflow["has_overflow"], landing_overflow)
            assert_check(checks, "default_postal_code", page.locator("#postal-code").input_value() == "22350", page.locator("#postal-code").input_value())
            assert_check(checks, "default_meals", page.locator("#recipes").input_value() == "5", page.locator("#recipes").input_value())
            assert_check(checks, "default_servings", page.locator("#servings").input_value() == "4", page.locator("#servings").input_value())
            assert_check(checks, "default_store_cap", page.locator("#max-stores").input_value() == "2", page.locator("#max-stores").input_value())
            assert_check(checks, "default_diet", page.locator("#diet-preference").input_value() == "mixed", page.locator("#diet-preference").input_value())
            assert_check(checks, "default_mode_balanced", page.locator("#diversity-balanced").is_checked(), "balanced")

            page.locator("details.advanced-options summary").click()
            memberships = page.locator('input[name="membership"]')
            for index in range(memberships.count()):
                memberships.nth(index).check()
            selected_memberships = memberships.evaluate_all(
                "items => items.filter(item => item.checked).map(item => item.value)"
            )
            assert_check(checks, "all_memberships_selected", len(selected_memberships) == memberships.count(), selected_memberships)
            screenshots.append(screenshot(page, screenshot_dir, "landing"))

            if args.landing_only:
                assert_check(checks, "no_console_errors", not console_errors, console_errors)
                assert_check(checks, "no_page_errors", not page_errors, page_errors)
                status = "PASSED"
                browser.close()
                return {
                    "status": status,
                    "scope": "landing_only",
                    "base_url": base_url,
                    "viewport": VIEWPORT,
                    "generated_at_utc": datetime.now(UTC).isoformat(),
                    "server_health": health,
                    "checks": checks,
                    "screenshots": screenshots,
                    "console_errors": console_errors,
                    "page_errors": page_errors,
                    "community_write_attempts": community_writes,
                    "plan_runtime_seconds": None,
                    "summary": summary,
                    "error": None,
                }

            start = time.perf_counter()
            page.locator("#submit-button").click()
            try:
                page.locator("#results").wait_for(
                    state="visible",
                    timeout=int(args.plan_timeout * 1000),
                )
            except PlaywrightTimeoutError as exc:
                plan_runtime = time.perf_counter() - start
                raise AssertionError(
                    f"Planen blev inte klar inom {args.plan_timeout:.0f} sekunder "
                    f"({plan_runtime:.3f} s uppmätt)."
                ) from exc
            plan_runtime = time.perf_counter() - start
            assert_check(checks, "plan_under_timeout", plan_runtime <= args.plan_timeout, f"{plan_runtime:.3f} s")

            recipes = page.locator("#recipes-list details.recipe-card")
            assert_check(checks, "five_recipes", recipes.count() == 5, recipes.count())
            result_overflow = horizontal_metrics(page)
            assert_check(checks, "result_no_horizontal_overflow", not result_overflow["has_overflow"], result_overflow)

            store_count_text = page.locator("#summary-stores").inner_text().strip()
            total_text = page.locator("#summary-total").inner_text().strip()
            store_groups = page.locator("#store-groups article.store-group")
            assert_check(checks, "shopping_list_grouped_by_store", 1 <= store_groups.count() <= 2, store_groups.count())
            assert_check(checks, "actual_store_count_visible", store_count_text == str(store_groups.count()), store_count_text)
            assert_check(checks, "total_visible", bool(re.search(r"\d.*kr", total_text, re.IGNORECASE)), total_text)
            assert_check(checks, "shopping_list_has_products", page.locator("#store-groups tbody tr").count() > 0, page.locator("#store-groups tbody tr").count())
            screenshots.append(screenshot(page, screenshot_dir, "plan-result"))

            first_recipe = recipes.first
            first_recipe.locator("summary").click()
            assert_check(checks, "recipe_detail_open", first_recipe.get_attribute("open") is not None, first_recipe.locator(".recipe-name").inner_text())
            assert_check(checks, "recipe_has_ingredients", first_recipe.locator(".recipe-ingredients li").count() > 0, first_recipe.locator(".recipe-ingredients li").count())
            assert_check(checks, "recipe_has_instructions", first_recipe.locator(".instructions-list li").count() > 0, first_recipe.locator(".instructions-list li").count())
            first_recipe.scroll_into_view_if_needed()
            screenshots.append(screenshot(page, screenshot_dir, "recipe-detail"))

            report_button = page.locator("#store-groups .report-button").first
            report_button.scroll_into_view_if_needed()
            report_button.click()
            report_dialog = page.locator("#report-dialog")
            assert_check(checks, "report_dialog_opens", report_dialog.get_attribute("open") is not None, page.locator("#report-product-summary").inner_text())
            screenshots.append(screenshot(page, screenshot_dir, "report-dialog"))
            report_dialog.locator("[data-close-dialog]").first.click()
            assert_check(checks, "report_dialog_closes", report_dialog.get_attribute("open") is None, "closed without submit")
            assert_check(checks, "plan_remains_visible_after_report", page.locator("#results").is_visible(), "results visible")

            scanner_entry = page.locator("#scan-result-button")
            if not scanner_entry.is_visible():
                scanner_entry = page.locator("#scan-entry-button")
            scanner_entry.click()
            scanner_dialog = page.locator("#scanner-dialog")
            assert_check(checks, "scanner_dialog_opens", scanner_dialog.get_attribute("open") is not None, "manual GTIN available")
            page.locator("#scanner-start").click()
            page.locator("#scanner-camera").wait_for(state="visible", timeout=10_000)
            page.wait_for_function(
                """() => {
                  const video = document.querySelector('#scanner-video');
                  const status = document.querySelector('#scanner-status')?.textContent || '';
                  return Boolean(video?.srcObject)
                    || /kunde inte|nekades|manuellt/i.test(status);
                }""",
                timeout=10_000,
            )
            camera_state = page.evaluate(
                """() => ({
                  visible: !document.querySelector('#scanner-camera').hidden,
                  hasStream: Boolean(document.querySelector('#scanner-video').srcObject),
                })"""
            )
            assert_check(
                checks,
                "camera_permission_flow_starts",
                camera_state["visible"] and camera_state["hasStream"],
                camera_state,
            )
            page.locator("#scanner-cancel").click()
            page.locator("#manual-gtin").fill(TEST_GTIN)
            page.locator("#manual-gtin-submit").click()
            page.wait_for_function(
                """() => {
                  const status = document.querySelector('#scanner-status')?.textContent || '';
                  return status !== 'Söker efter varan…' && status !== 'Kameran startar först när du trycker på knappen.';
                }""",
                timeout=10_000,
            )
            scanner_status = page.locator("#scanner-status").inner_text().strip()
            assert_check(checks, "manual_gtin_lookup_completes", bool(scanner_status), scanner_status)
            assert_check(checks, "manual_gtin_normalized", page.locator("#manual-gtin").input_value() == TEST_GTIN, page.locator("#manual-gtin").input_value())
            screenshots.append(screenshot(page, screenshot_dir, "barcode-flow"))
            scanner_dialog.locator("[data-close-scanner]").first.click()
            assert_check(checks, "returns_to_plan_after_scanner", page.locator("#results").is_visible(), "results visible")
            assert_check(checks, "no_community_writes", not community_writes, community_writes)

            page.locator("#feedback-entry-button").click()
            feedback_dialog = page.locator("#feedback-dialog")
            assert_check(
                checks,
                "feedback_dialog_opens",
                feedback_dialog.get_attribute("open") is not None,
                "open",
            )
            page.locator("#feedback-category").select_option("suggestion")
            page.locator("#feedback-message").fill(
                "[E2E] Automatiskt acceptanstest för publik beta."
            )
            page.locator("#feedback-submit").click()
            page.locator("#feedback-status").filter(has_text="sparad").wait_for(
                state="visible",
                timeout=10_000,
            )
            assert_check(
                checks,
                "feedback_is_persisted",
                "sparad" in page.locator("#feedback-status").inner_text().casefold(),
                page.locator("#feedback-status").inner_text(),
            )
            page.wait_for_timeout(1_000)

            saved_plan_url = page.url
            assert_check(
                checks,
                "saved_plan_url_uses_private_fragment",
                "#plan=" in saved_plan_url and "?plan=" not in saved_plan_url,
                saved_plan_url,
            )
            page.reload(wait_until="domcontentloaded")
            page.locator("#results").wait_for(state="visible", timeout=15_000)
            restored_recipes = page.locator("#recipes-list details.recipe-card").count()
            assert_check(checks, "saved_plan_survives_reload", restored_recipes == 5, restored_recipes)
            assert_check(
                checks,
                "onboarding_not_repeated",
                page.locator("#onboarding-dialog").get_attribute("open") is None,
                "not reopened",
            )
            assert_check(
                checks,
                "preferences_survive_reload",
                page.locator('input[name="membership"]:checked').count()
                == memberships.count(),
                page.locator('input[name="membership"]:checked').count(),
            )
            effective_console_errors = list(console_errors)
            if args.ignore_https_errors:
                ignored_console_errors = [
                    message
                    for message in effective_console_errors
                    if message == "An SSL certificate error occurred when fetching the script."
                ]
                effective_console_errors = [
                    message
                    for message in effective_console_errors
                    if message not in ignored_console_errors
                ]
            assert_check(
                checks,
                "no_console_errors",
                not effective_console_errors,
                effective_console_errors,
            )
            assert_check(checks, "no_page_errors", not page_errors, page_errors)

            summary = {
                "recipes": recipes.count(),
                "stores": store_groups.count(),
                "total": total_text,
                "first_recipe": first_recipe.locator(".recipe-name").inner_text().strip(),
                "memberships": selected_memberships,
                "scanner_status": scanner_status,
                "saved_plan_reload": True,
                "secure_context": secure_context["secure"],
            }
            status = "PASSED"
            browser.close()
    except Exception:  # noqa: BLE001 - a runner must persist diagnostics for every failure.
        error = traceback.format_exc()
        status = "FAILED"

    return {
        "status": status,
        "scope": "full_consumer_flow",
        "base_url": base_url,
        "viewport": VIEWPORT,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "server_health": health,
        "checks": checks,
        "screenshots": screenshots,
            "console_errors": console_errors,
            "ignored_local_tls_console_errors": ignored_console_errors,
        "page_errors": page_errors,
        "community_write_attempts": community_writes,
        "plan_runtime_seconds": plan_runtime,
        "summary": summary,
        "error": error,
    }


def main() -> int:
    args = parse_args()
    result = run_e2e(args)
    json_path, markdown_path = write_result(args.output_dir, result)
    print(f"CONSUMER MOBILE E2E: {result['status']}")
    if result.get("plan_runtime_seconds") is not None:
        print(f"PLAN: {result['plan_runtime_seconds']:.3f} s")
    print(f"JSON: {json_path.resolve()}")
    print(f"MARKDOWN: {markdown_path.resolve()}")
    if result.get("error"):
        print(result["error"], file=sys.stderr)
    return 0 if result["status"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
