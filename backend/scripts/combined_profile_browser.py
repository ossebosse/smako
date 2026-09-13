"""Ordinary mobile form, separate disposable guests; no session data in evidence."""

import argparse
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


def validate(plan, request):
    meals = {m["meal_type"]: m for m in request["personal"]["meals"]}
    slots = plan["personal"]["slots"]
    assert len(slots) == sum(m["count"] for m in meals.values())
    assert plan["portions"] == sum(m["count"] * m["servings"] for m in meals.values())
    for row in plan["personal"]["checks"]["nutrition"]:
        slot = next(s for s in slots if s["id"] == row["slot_id"])
        meal = meals[slot["meal_type"]]
        assert slot["recipe"]["servings"] == meal["servings"]
        assert row["values"]["protein_g"] >= meal["limits"]["min_protein_g"]
    assert plan["optimized_basket"]["store_count"] <= request["max_stores"]
    assert plan["data"]["live_chain_requests"] == 0


def check(base, output, cases=("D",), engines=("chromium",), estimate_modes=(False, True)):
    output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        for engine in engines:
            browser = getattr(pw, engine).launch()
            for estimates in estimate_modes:
                for case in cases:
                    ctx = browser.new_context(
                        viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True
                    )
                    page = ctx.new_page()
                    page_errors = []
                    page.on("pageerror", lambda error, sink=page_errors: sink.append(str(error)))
                    page.goto(base + "/personal")
                    page.get_by_role("button", name="Mina val", exact=True).click()
                    assert not page.locator("#allow-nutrition-estimates").is_checked()
                    for n, (meal, servings, protein) in enumerate(
                        (("dinner", 2, 40), ("breakfast", 1, 30), ("snack", 1, 20))
                    ):
                        active = case == "D" or case == ("A", "B", "C")[n]
                        page.locator(f"#{meal}-count").fill("5" if active else "0")
                        page.locator(f"#{meal}-servings").fill(str(servings))
                        card = page.locator("#meal-settings > .personal-card").nth(n)
                        if active:
                            card.get_by_text(
                                "Fördelning, egna smakval och gränser", exact=True
                            ).click()
                            card.get_by_text("Portionsvikt och näringsgränser", exact=True).click()
                            page.locator(f"#{meal}-min_protein_g").fill(str(protein))
                    if estimates:
                        page.locator("#allow-nutrition-estimates").check()
                    stem = f"{engine}-{case}-{'on' if estimates else 'off'}"
                    page.screenshot(path=str(output / (stem + "-form.png")), full_page=True)
                    started = time.perf_counter()
                    with page.expect_response(
                        lambda r: r.url.endswith("/api/plans") and r.request.method == "POST",
                        timeout=660000,
                    ) as event:
                        page.locator("#generate-plan").click()
                    response = event.value
                    try:
                        body = response.json()
                    except ValueError as exc:
                        body = {
                            "detail": "Non-JSON server response",
                            "response_status": response.status,
                            "error_type": type(exc).__name__,
                        }
                    request = response.request.post_data_json
                    assert request["personal"]["allow_nutrition_estimates"] == estimates
                    for n, meal in enumerate(request["personal"]["meals"]):
                        assert meal["diet"] == "mixed"
                        assert meal["limits"]["max_kcal"] is None
                        if meal["count"]:
                            assert meal["limits"]["min_protein_g"] == (40, 30, 20)[n]
                    result = {
                        "case": case,
                        "estimates": estimates,
                        "http_status": response.status,
                        "request": request,
                        "seconds": time.perf_counter() - started,
                    }
                    if response.status == 201:
                        validate(body["plan"], request)
                        result.update(plan=body["plan"], interpreted=body["request"])
                        page.reload()
                        page.get_by_role("button", name="Mina val", exact=True).click()
                        assert page.locator("#allow-nutrition-estimates").is_checked() == estimates
                        for meal in request["personal"]["meals"]:
                            assert page.locator(f"#{meal['meal_type']}-count").input_value() == str(
                                meal["count"]
                            )
                            if meal["count"]:
                                assert (
                                    float(
                                        page.locator(
                                            f"#{meal['meal_type']}-min_protein_g"
                                        ).input_value()
                                    )
                                    == meal["limits"]["min_protein_g"]
                                )
                        result["reload"] = True
                        page.get_by_role("button", name="Min plan", exact=True).click()
                        if case == "D":
                            page.screenshot(path=str(output / (stem + "-menu-mobile.png")))
                            with page.expect_response(
                                lambda r: r.url.endswith("/change") and r.request.method == "POST",
                                timeout=660000,
                            ) as changed_event:
                                page.locator("article.personal-card").filter(
                                    has=page.get_by_text("Dag 4 · Middag", exact=True)
                                ).get_by_role("button", name="Byt recept", exact=True).click()
                            changed = changed_event.value
                            result["replacement_status"] = changed.status
                            if changed.status == 200:
                                replacement = changed.json()["saved"]
                                validate(replacement["plan"], request)
                                for original, updated in zip(
                                    body["request"]["personal"]["meals"],
                                    replacement["request"]["personal"]["meals"],
                                    strict=True,
                                ):
                                    assert original == updated
                                assert (
                                    body["request"]["personal"]["allow_nutrition_estimates"]
                                    == replacement["request"]["personal"][
                                        "allow_nutrition_estimates"
                                    ]
                                )
                                result["replacement"] = replacement["plan"]
                            else:
                                result["replacement_error"] = changed.json()
                    else:
                        result["error"] = body
                        offer = page.get_by_role(
                            "button", name="Visa valet för näringsuppskattningar", exact=True
                        )
                        if not estimates and case == "D" and offer.count():
                            offer.click()
                            assert not page.locator("#allow-nutrition-estimates").is_checked()
                            page.locator("fieldset").filter(
                                has=page.locator("#allow-nutrition-estimates")
                            ).screenshot(path=str(output / (stem + "-estimate-choice.png")))
                            result["estimate_offer_keeps_opt_in_off"] = True
                    assert not page_errors, page_errors
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
                    result["page_errors"] = page_errors
                    page.screenshot(path=str(output / (stem + "-result.png")), full_page=True)
                    (output / (stem + ".json")).write_text(
                        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf8"
                    )
                    print(
                        json.dumps({k: result[k] for k in ("case", "estimates", "http_status")}),
                        flush=True,
                    )
                    ctx.close()
            browser.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="https://beta.smako.nu")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--cases", default="D")
    p.add_argument("--estimates", choices=["both", "on", "off"], default="both")
    args = p.parse_args()
    check(
        args.base,
        args.output,
        args.cases.split(","),
        estimate_modes=(False, True) if args.estimates == "both" else (args.estimates == "on",),
    )
