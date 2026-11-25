"""Fix 2026-11-25: scanning a barcode on a receipt line works, and typing it works when the camera does not."""

import re

import pytest
from playwright.sync_api import expect

from backend.tests.test_trial_interfaces_browser import Fake, open_screen, ui  # noqa: F401  (fixture)

GTIN = "7310865004703"
SCANNER = """window.GroceryBarcodeScanner = {
  createBarcodeScanner(options) {
    return { start() {
      if (window.__cameraFails) setTimeout(() => options.onError(new Error("ingen kamera"), { recoverable: false }), 20);
      else setTimeout(() => options.onResult({ normalized_gtin: "%s" }), 20);
      return Promise.resolve(this);
    }, stop() { window.__stopped = (window.__stopped || 0) + 1; } };
  },
  normalizeGtin(raw) {
    const digits = String(raw).replace(/\\s/g, "");
    if (!/^\\d{8}$|^\\d{12,13}$/.test(digits)) throw new Error("Streckkoden måste vara EAN-13, EAN-8, UPC-A eller UPC-E.");
    return { normalized_gtin: digits.padStart(14, "0").slice(-13) };
  },
};""" % GTIN


def receipt(lines):
    return {"store_text": "Willys Lund", "purchased_on": "2026-11-25", "store_known": True, "store": "Willys Lund",
            "qualifies": True, "points": 5, "max_points": 50, "needed": 3, "lines": lines,
            "needs_barcode": sum(1 for line in lines if line.get("needs_barcode"))}


def line(gtin=None):
    base = {"description": "Okänd sås", "price": 24.9, "quantity": 1, "unit": "st", "unit_price": None, "gtin": gtin,
            "missing_in_smako": True, "item": None, "points": 0, "unsure": False, "price_differs": False}
    return {**base, "needs_barcode": True} if gtin is None else {**base, "needs_barcode": False, "new_item": True, "points": 3}


def open_receipt(page, fake, fails):
    previews = []
    plain = fake.answer

    def answer(method, path, query, body):
        if path == "member/points":
            return 200, {"balance": 10, "history": []}
        if path == "member/receipts/preview":
            previews.append(body)
            gtin = next((l.get("gtin") for l in (body.get("lines") or []) if l.get("gtin")), None)
            return 200, receipt([line(gtin)])
        return plain(method, path, query, body)

    fake.answer = answer
    # The PDF goes up as raw bytes, which the shared JSON route cannot read.
    page.route("**/api/member/receipts/pdf-text", lambda route: route.fulfill(
        content_type="application/json", body='{"text": "Willys Lund\\nOkänd sås 24,90"}'))
    page.route("**/scanner-assets/**", lambda route: route.fulfill(content_type="application/javascript", body=SCANNER))
    page.add_init_script(f"window.__cameraFails = {'true' if fails else 'false'};")
    fake.owner = "account"
    page.goto(re.sub(r"#.*|$", "#mat", page.url, count=1))
    page.reload()
    page.get_by_label("Ditt postnummer").fill("22350")
    page.get_by_role("button", name="Hitta butiker").click()
    page.get_by_role("button", name="Skapa matplan").click()
    expect(page.get_by_role("heading", name="Din matplan", exact=True)).to_be_visible()
    open_screen("a", page, "konto")
    page.get_by_role("button", name="Skanna kvitto").click()
    page.locator('dialog.receipt-dialog input[accept="application/pdf"]').set_input_files(
        files=[{"name": "kvitto.pdf", "mimeType": "application/pdf", "buffer": b"%PDF-1.4"}])
    expect(page.get_by_role("button", name="Skanna varans streckkod")).to_be_visible()
    return previews


def test_a_scanned_barcode_is_sent_with_the_receipt_line(ui):  # noqa: F811
    name, page, fake, _ = ui
    if name == "b":
        pytest.skip("The receipt dialog is the same code in both interfaces")
    previews = open_receipt(page, fake, fails=False)
    page.get_by_role("button", name="Skanna varans streckkod").click()
    expect(page.get_by_text(f"streckkod {GTIN}")).to_be_visible()
    assert previews[-1]["lines"][0]["gtin"] == GTIN
    expect(page.locator("dialog.receipt-dialog video")).to_have_count(0)


def test_typing_the_barcode_works_when_the_camera_cannot_read_it(ui):  # noqa: F811
    name, page, fake, _ = ui
    if name == "b":
        pytest.skip("The receipt dialog is the same code in both interfaces")
    previews = open_receipt(page, fake, fails=True)
    page.get_by_role("button", name="Skanna varans streckkod").click()
    expect(page.get_by_text("Kameran kunde inte läsa streckkoden")).to_be_visible()
    entry = page.get_by_label("Streckkod")
    entry.fill("12345")
    page.get_by_role("button", name="Använd").click()
    expect(page.get_by_text("Streckkoden måste vara")).to_be_visible()
    entry.fill(GTIN)
    page.get_by_role("button", name="Använd").click()
    expect(page.get_by_text(f"streckkod {GTIN}")).to_be_visible()
    assert previews[-1]["lines"][0]["gtin"] == GTIN
