"""Verify real municipal controls, including deployed geolocation policy.

Uses isolated browser profiles and an explicitly supplied simulated position.
Does not generate plans, collect prices, or change existing user profiles.
"""

import argparse
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def open_view(page, view):
    """On mobile the main menu sits behind the top-left menu button."""
    toggle = page.locator(".menu-toggle")
    if toggle.is_visible():
        toggle.click()
    page.locator(f'.personal-nav [data-open="{view}"]').click()


def verify_case(browser, args, engine, path, label):
    context = browser.new_context(
        viewport={"width": 390, "height": 844},
        geolocation={"latitude": args.latitude, "longitude": args.longitude},
        permissions=["geolocation"],
    )
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    report = {"browser": engine, "page": label, "status": "failed"}
    try:
        response = page.goto(args.base.rstrip("/") + path)
        policy = response.headers.get("permissions-policy", "")
        report["permissions_policy"] = policy
        assert "geolocation=()" not in policy, "Deployed proxy denies geolocation"
        if label == "personal":
            open_view(page, "choices")
        if page.locator("#onboarding-dialog[open]").count():
            page.locator("#onboarding-cta").click()
        municipality = page.locator("#municipality")
        expect(municipality).to_be_visible(timeout=30000)
        municipality.select_option(args.baseline_municipality)
        expect(page.locator("#postal-code")).to_be_hidden()
        choices = page.locator('input[id^="context-"]')
        expect(choices.first).to_be_visible(timeout=30000)
        choices.first.check()
        baseline_store = choices.first.get_attribute("value")
        municipality.select_option(args.municipality)
        expect(page.locator("#postal-code")).to_have_value(args.postal_code)
        available = context.request.get(
            args.base.rstrip("/") + "/api/price-contexts",
            params={"postal_code": args.postal_code},
        )
        assert available.ok
        contexts = available.json()["contexts"]
        expect(choices).to_have_count(len(contexts), timeout=30000)
        target = next(
            row["context_id"] for row in contexts
            if row["chain"].casefold() == args.catalog_chain.casefold()
            and row["price_context_type"] == "online_store"
        )
        page.locator('[id="context-' + target + '"]').check()
        # Measure in one frame: separate bounding_box calls can span a layout shift.
        page.wait_for_function("""() => {
            const rows = [...document.querySelectorAll('input[id^="context-"]')]
                .map(input => input.parentElement.getBoundingClientRect());
            return rows.length > 1 && rows.every((row, index) =>
                index === 0 || row.top >= rows[index - 1].bottom);
        }""")
        municipality.select_option(args.baseline_municipality)
        expect(page.locator('[id="context-' + baseline_store + '"]')).to_be_checked()
        municipality.select_option(args.municipality)
        expect(page.locator('[id="context-' + target + '"]')).to_be_checked()
        page.locator("#store-radius").select_option(str(args.radius))
        with page.expect_response(
            lambda result: "/api/price-contexts?" in result.url and "latitude=" in result.url
        ) as located:
            page.get_by_role("button", name="Välj butiker nära mig").click()
        nearby = located.value.json()["contexts"]
        expected = sorted(
            row["context_id"] for row in nearby
            if row.get("distance_km") is not None and row["distance_km"] <= args.radius
        )
        assert 0 < len(expected) <= 40, "Choose a test position/radius with 1–40 contexts"
        checked = page.locator('input[id^="context-"]:checked')
        expect(checked).to_have_count(len(expected))
        assert sorted(checked.evaluate_all("xs => xs.map(x => x.value)")) == expected
        assert page.evaluate("""() => [localStorage, sessionStorage].every(storage =>
            Object.values(storage).every(value =>
                !value.includes('latitude') && !value.includes('longitude')))
        """)
        assert not errors, errors
        report.update(
            status="pass", contexts=len(contexts), manual_store=target,
            nearby_count=len(expected), municipality=args.municipality,
            geolocation="simulated position; actual API distance calculation",
        )
        return report
    finally:
        report["page_errors"] = errors
        report["store_status"] = page.locator("#recipe-price-contexts [role=status]").all_text_contents()
        page.screenshot(path=args.output / f"{engine}-{label}.png", full_page=True)
        (args.output / f"{engine}-{label}.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        context.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="https://beta.smako.nu")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--municipality", required=True)
    parser.add_argument("--postal-code", required=True)
    parser.add_argument("--baseline-municipality", default="1281")
    parser.add_argument("--latitude", type=float, required=True)
    parser.add_argument("--longitude", type=float, required=True)
    parser.add_argument("--radius", type=int, choices=(1, 3, 5, 10, 20), default=1)
    parser.add_argument("--catalog-chain", default="willys")
    args = parser.parse_args()
    assert args.municipality != args.baseline_municipality
    args.output.mkdir(parents=True, exist_ok=False)
    results = []
    with sync_playwright() as playwright:
        for engine in ("chromium", "webkit"):
            browser = getattr(playwright, engine).launch()
            try:
                for path, label in (("/klassisk", "public"), ("/personal#choices", "personal")):
                    results.append(verify_case(browser, args, engine, path, label))
            finally:
                browser.close()
    (args.output / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results))


if __name__ == "__main__":
    main()
