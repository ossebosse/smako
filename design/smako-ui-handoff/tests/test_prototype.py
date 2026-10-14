"""UI-tester av den fristående referensen, INTE av Smakos backend.
Kör från paketets rot: python -m unittest discover -s tests -v
Kräver Python + Playwright samt installerad Chromium. Ingen testdata hämtas externt.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import unittest

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]


def build_html() -> str:
    """Läs de levererade källfilerna; inline för att undvika file://-policy i testmiljön."""
    folder = ROOT / "prototype"
    html = (folder / "index.html").read_text(encoding="utf-8")
    for name in ("tokens.css", "styles.css"):
        html = html.replace(f'<link rel="stylesheet" href="{name}">',
                            f'<style>{(folder / name).read_text(encoding="utf-8")}</style>')
    return html.replace('<script src="app.js"></script>',
                        f'<script>{(folder / "app.js").read_text(encoding="utf-8")}</script>')


class SmakoReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.playwright = sync_playwright().start()
        binary = os.getenv("CHROMIUM_EXECUTABLE") or shutil.which("chromium") or shutil.which("google-chrome")
        options = {"headless": True}
        if binary:
            options["executable_path"] = binary
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            options["args"] = ["--no-sandbox"]  # Endast isolerad root-testmiljö.
        cls.browser = cls.playwright.chromium.launch(**options)
        cls.html = build_html()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self) -> None:
        self.context = self.browser.new_context(viewport={"width": 390, "height": 844})
        self.page = self.context.new_page()
        self.errors: list[str] = []
        self.requests: list[str] = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.page.on("request", lambda request: self.requests.append(request.url))
        self.page.set_content(self.html)

    def tearDown(self) -> None:
        self.context.close()
        self.assertEqual(self.errors, [], "Ohanterade JavaScript-fel")
        self.assertEqual(self.requests, [], "Prototypen ska inte hämta externa resurser eller API-data")

    def activate(self, kind: str) -> None:
        if not self.page.locator("#extras").evaluate("el => el.open"):
            self.page.locator("#extras > summary").click()
        self.page.locator(f"#enable-{kind}").check()

    def open_modal(self, meal: str, kind: str) -> None:
        self.page.locator(f'[data-modal="{meal}|{kind}"]').click()
        expect(self.page.locator("#settings-dialog")).to_be_visible()

    def cancel(self) -> None:
        self.page.keyboard.press("Escape")
        expect(self.page.locator("#settings-dialog")).not_to_be_visible()

    def save(self) -> None:
        self.page.locator("#modal-save").click()
        expect(self.page.locator("#settings-dialog")).not_to_be_visible()

    def lookup(self) -> None:
        self.page.locator("#postcode").fill("222 25")
        self.page.locator("#find-stores").click()
        expect(self.page.locator("#location-details")).to_be_visible()

    def snapshot(self) -> dict:
        self.page.locator("#generate").click()
        value = json.loads(self.page.locator("#snapshot").inner_text())
        self.cancel()
        return value

    def test_01_initial_and_guard(self) -> None:
        expect(self.page.locator("#meal-dinner")).to_be_visible()
        expect(self.page.locator("#meal-breakfast")).to_have_count(0)
        expect(self.page.locator("#meal-snack")).to_have_count(0)
        self.page.locator("#generate").click()
        expect(self.page.locator("#plan-error")).to_contain_text("postnummer")

    def test_02_steps_and_invalid_numbers(self) -> None:
        self.page.locator('[data-step="dinner|count|1"]').click()
        expect(self.page.locator("#dinner-count")).to_have_value("6")
        self.page.locator("#dinner-count").fill("8")
        expect(self.page.locator("#dinner-field-error")).to_contain_text("heltal")
        self.page.locator("#dinner-portions").fill("2")
        expect(self.page.locator("#dinner-field-error")).to_contain_text("heltal")
        self.page.locator("#dinner-count").fill("5")
        expect(self.page.locator("#dinner-field-error")).to_be_empty()
        # Första klicket efter direktinmatning ska kunna öppna en modal.
        self.open_modal("dinner", "weight")
        self.cancel()

    def test_03_optional_meals_independent_and_retained(self) -> None:
        self.activate("snack")
        expect(self.page.locator("#meal-breakfast")).to_have_count(0)
        expect(self.page.locator("#meal-snack")).to_be_visible()
        self.page.locator("#snack-count").fill("3")
        self.activate("breakfast")
        ids = self.page.locator(".meal-card").evaluate_all("els => els.map(el => el.id)")
        self.assertEqual(ids, ["meal-dinner", "meal-breakfast", "meal-snack"])
        self.page.locator("#enable-snack").uncheck()
        expect(self.page.locator("#meal-snack")).to_have_count(0)
        self.page.locator("#enable-snack").check()
        expect(self.page.locator("#snack-count")).to_have_value("3")
        expect(self.page.locator("#dinner-count")).to_have_value("5")

    def test_04_nutrition_scope_and_positions(self) -> None:
        self.activate("breakfast")
        self.activate("snack")
        self.open_modal("breakfast", "nutrition")
        self.page.locator("#protein-min").fill("10")
        self.page.locator("#protein-max").fill("30")
        track = self.page.locator('[data-range-key="protein"] .range-track')
        self.assertEqual(track.evaluate("el => el.style.getPropertyValue('--low')"), "10")
        self.assertEqual(track.evaluate("el => el.style.getPropertyValue('--high')"), "30")
        self.save()
        for meal in ("dinner", "snack"):
            self.open_modal(meal, "nutrition")
            expect(self.page.locator("#protein-min")).to_have_value("")
            expect(self.page.locator("#protein-max")).to_have_value("")
            self.cancel()
        self.open_modal("breakfast", "nutrition")
        expect(self.page.locator("#protein-min")).to_have_value("10")
        expect(self.page.locator("#protein-max")).to_have_value("30")
        self.cancel()

    def test_05_zero_null_and_disabled_meal_payload(self) -> None:
        self.lookup()
        self.open_modal("dinner", "weight")
        self.page.locator("#weight-min").fill("0")
        self.save()
        self.activate("breakfast")
        self.open_modal("breakfast", "nutrition")
        self.page.locator("#protein-min").fill("20")
        self.save()
        self.page.locator("#enable-breakfast").uncheck()
        data = self.snapshot()
        self.assertEqual(data["meals"]["dinner"]["weight"], {"min": 0, "max": None})
        self.assertNotIn("breakfast", data["meals"])
        self.assertNotIn("snack", data["meals"])

    def test_06_invalid_range_blocks_save(self) -> None:
        self.open_modal("dinner", "nutrition")
        self.page.locator("#protein-min").fill("50")
        self.page.locator("#protein-max").fill("30")
        expect(self.page.locator("#modal-save")).to_be_disabled()
        expect(self.page.locator("#protein-range-error")).to_contain_text("Min får inte")
        self.page.locator("#protein-min").fill("-1")
        expect(self.page.locator("#modal-save")).to_be_disabled()
        self.page.locator("#protein-min").fill("10")
        expect(self.page.locator("#modal-save")).to_be_enabled()
        self.page.locator("#protein-max").fill("101")
        expect(self.page.locator("#modal-save")).to_be_disabled()
        self.cancel()

    def test_07_slider_keyboard_and_real_pointer_drag(self) -> None:
        self.open_modal("dinner", "nutrition")
        self.page.locator("#protein-min").fill("10")
        self.page.locator("#protein-max").fill("60")
        slider = self.page.locator('[data-range-slider="protein|min"]')
        slider.focus()
        self.page.keyboard.press("ArrowRight")
        expect(self.page.locator("#protein-min")).to_have_value("11")
        box = slider.bounding_box()
        assert box is not None
        start_x = box["x"] + 13 + (box["width"] - 26) * .11
        end_x = box["x"] + 13 + (box["width"] - 26) * .25
        y = box["y"] + box["height"] / 2
        self.page.mouse.move(start_x, y)
        self.page.mouse.down()
        self.page.mouse.move(end_x, y, steps=12)
        self.page.mouse.up()
        self.assertAlmostEqual(int(self.page.locator("#protein-min").input_value()), 25, delta=1)
        self.cancel()

    def test_08_cancel_and_reset_are_drafts(self) -> None:
        self.open_modal("dinner", "nutrition")
        self.page.locator("#protein-min").fill("20")
        self.page.locator("#carbs-max").fill("90")
        self.save()
        self.open_modal("dinner", "nutrition")
        self.page.locator('[data-range-reset="protein"]').click()
        expect(self.page.locator("#protein-min")).to_have_value("")
        expect(self.page.locator("#carbs-max")).to_have_value("90")
        self.cancel()
        self.open_modal("dinner", "nutrition")
        expect(self.page.locator("#protein-min")).to_have_value("20")
        self.page.locator('[data-range-reset="protein"]').click()
        self.save()
        self.open_modal("dinner", "nutrition")
        expect(self.page.locator("#protein-min")).to_have_value("")
        expect(self.page.locator("#carbs-max")).to_have_value("90")
        self.cancel()

    def test_09_distribution_sums_and_limits(self) -> None:
        self.open_modal("dinner", "distribution")
        self.page.locator("#dist-vegetarian").fill("1")
        self.page.locator("#dist-chicken").fill("2")
        self.page.locator("#dist-fish").fill("1")
        expect(self.page.locator("#allocation-status")).to_have_text("4 av 5 måltider fördelade · 1 kvar")
        self.page.locator("#dist-vegetarian").fill("3")
        expect(self.page.locator("#modal-save")).to_be_disabled()
        self.page.locator("#dist-fish").fill("")
        expect(self.page.locator("#allocation-status")).to_have_text("5 av 5 måltider fördelade · 0 kvar")
        self.save()
        self.page.locator("#dinner-count").fill("4")
        expect(self.page.locator("#dinner-distribution-error")).to_contain_text("5 av 4")
        self.open_modal("dinner", "distribution")
        expect(self.page.locator("#dist-vegetarian")).to_have_value("3")
        expect(self.page.locator("#dist-chicken")).to_have_value("2")
        self.cancel()

    def test_10_distribution_standard_zero_and_diet(self) -> None:
        self.lookup()
        self.open_modal("dinner", "distribution")
        self.page.locator("#dist-vegetarian").fill("0")
        self.page.locator("#dist-chicken").fill("1")
        self.page.locator("#diet").select_option("vegetarian")
        expect(self.page.locator("#modal-save")).to_be_disabled()
        self.page.locator('[data-dist-reset="chicken"]').click()
        expect(self.page.locator("#modal-save")).to_be_enabled()
        self.save()
        counts = self.snapshot()["meals"]["dinner"]["distribution"]["counts"]
        self.assertEqual(counts, {"vegetarian": 0, "chicken": None, "fish": None})

    def test_11_geography_selection_and_max_stores(self) -> None:
        self.lookup()
        expect(self.page.locator("#store-count")).to_contain_text("3 exempelbutiker")
        self.page.locator("#radius").select_option("1")
        expect(self.page.locator("#store-count")).to_contain_text("1 exempelbutiker")
        self.page.locator("#scope").select_option("municipality")
        expect(self.page.locator("#store-count")).to_contain_text("5 exempelbutiker")
        self.page.locator("#choose-stores").click()
        for el in self.page.locator("[data-store]").all():
            el.uncheck()
        expect(self.page.locator("#modal-save")).to_be_disabled()
        self.page.locator('[data-store="demo-o"]').check()
        self.save()
        expect(self.page.locator("#scope")).to_have_value("manual")
        self.page.locator('[data-limit="3"]').click()
        data = self.snapshot()
        self.assertEqual(data["maxStores"], 3)
        self.assertEqual(data["location"]["selectedDemoStoreIds"], ["demo-o"])

    def test_12_postcode_validation_and_stale_response(self) -> None:
        self.page.locator("#postcode").fill("12")
        self.page.locator("#find-stores").click()
        expect(self.page.locator("#location-error")).to_contain_text("fem siffror")
        self.page.locator("#postcode").fill("12345")
        self.page.locator("#find-stores").click()
        expect(self.page.locator("#location-error")).to_contain_text("bara exempeldata")
        self.page.locator("#postcode").fill("22225")
        self.page.locator("#find-stores").click()
        self.page.locator("#postcode").fill("11111")
        self.page.wait_for_timeout(400)
        expect(self.page.locator("#location-details")).not_to_be_visible()
        expect(self.page.locator("#postcode")).to_have_value("11111")
        expect(self.page.locator("#find-stores")).to_be_enabled()

    def test_13_preference_review_and_safe_text(self) -> None:
        self.page.locator("#extras > summary").click()
        self.page.locator("#use-example").click()
        self.page.locator("#interpret").click()
        expect(self.page.locator("#review-excluded")).to_have_value("jordnötter")
        expect(self.page.locator("#review-allergies")).to_have_value("")
        self.cancel()
        expect(self.page.locator("#preference-tags")).to_be_empty()
        self.page.locator("#interpret").click()
        self.page.locator("#review-allergies").fill('mjölk, <img src=x onerror="alert(1)">')
        self.save()
        expect(self.page.locator("#preference-tags")).to_contain_text("jordnötter")
        expect(self.page.locator("#preference-tags img")).to_have_count(0)
        expect(self.page.locator("#preference-tags")).to_contain_text("<img")

    def test_14_all_modal_combinations_focus_and_escape(self) -> None:
        self.activate("breakfast")
        self.activate("snack")
        names = {"dinner": "Middag", "breakfast": "Frukost", "snack": "Mellanmål"}
        titles = {"weight": "Portionsvikt", "nutrition": "Näringsvärden", "distribution": "Fördelning"}
        for meal, name in names.items():
            for kind, title in titles.items():
                self.open_modal(meal, kind)
                expect(self.page.locator("#dialog-title")).to_have_text(f"{name} · {title}")
                for _ in range(30):
                    self.page.keyboard.press("Tab")
                    self.assertTrue(self.page.evaluate("document.querySelector('dialog').contains(document.activeElement)"))
                self.cancel()
                self.assertEqual(self.page.evaluate("document.activeElement.dataset.modal"), f"{meal}|{kind}")

    def test_15_layout_widths_and_modal_footer(self) -> None:
        self.activate("breakfast")
        self.activate("snack")
        for width in (320, 375, 390, 430, 768, 1440):
            self.page.set_viewport_size({"width": width, "height": 844})
            self.assertLessEqual(self.page.evaluate("document.documentElement.scrollWidth"), width)
            for kind in ("nutrition", "weight", "distribution"):
                self.open_modal("breakfast", kind)
                overflow = self.page.locator(".dialog-body").evaluate("el => el.scrollWidth > el.clientWidth + 1")
                self.assertFalse(overflow, f"Modal-overflow vid {width}/{kind}")
                self.cancel()
        self.page.set_viewport_size({"width": 390, "height": 568})
        self.open_modal("snack", "nutrition")
        footer = self.page.locator(".dialog-footer").bounding_box()
        self.assertIsNotNone(footer)
        self.assertLessEqual(footer["y"] + footer["height"], 568)
        self.assertGreaterEqual(footer["y"], 0)
        self.assertTrue(self.page.locator(".dialog-body").evaluate("el => el.scrollHeight > el.clientHeight"))
        self.cancel()

    def test_16_eco_and_surplus_demo_values(self) -> None:
        self.lookup()
        self.page.locator("#extras > summary").click()
        self.page.locator("#eco-number").fill("101")
        expect(self.page.locator("#eco-error")).to_contain_text("mellan 0 och 100")
        self.page.locator("#eco-number").fill("40")
        expect(self.page.locator("#eco-range")).to_have_value("40")
        self.page.locator("#organic-animal").check()
        self.page.locator("#surplus").select_option("strategic-demo")
        data = self.snapshot()
        self.assertEqual(data["ecoCostPercent"], 40)
        self.assertTrue(data["organicAnimal"])
        self.assertEqual(data["surplus"], "strategic-demo")

    def test_17_modal_close_does_not_save_weight(self) -> None:
        self.open_modal("dinner", "weight")
        self.page.locator("#weight-min").fill("450")
        self.page.locator("#weight-max").fill("750")
        self.page.locator(".dialog-header [data-cancel]").click()
        self.open_modal("dinner", "weight")
        expect(self.page.locator("#weight-min")).to_have_value("")
        self.cancel()

    def test_18_zero_dinners_allows_breakfast_not_empty_plan(self) -> None:
        self.lookup()
        self.page.locator("#dinner-count").fill("0")
        self.page.locator("#generate").click()
        expect(self.page.locator("#plan-error")).to_contain_text("minst en måltid")
        self.activate("breakfast")
        data = self.snapshot()
        self.assertEqual(data["meals"]["dinner"]["count"], 0)
        self.assertEqual(data["meals"]["breakfast"]["count"], 5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
