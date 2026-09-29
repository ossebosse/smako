"""Chromium/WebKit acceptance against the real ASGI routes with frozen source data.

Only synthetic guest data enters an isolated temporary database. No mocks of
personal request handlers, optimizer or inventory ledger. Never deletes live data.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import tempfile
import threading
import time
from pathlib import Path

import uvicorn
from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--webkit",
        default=None,
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="smako-personal-v2-", ignore_cleanup_errors=True
    ) as temp:
        root = Path(temp)
        os.environ.update(
            PLAN_STORE_PATH=str(root / "plans.sqlite3"),
            PRICE_PROVIDER="mock",
            GROCERY_DATABASE_URL=f"sqlite+pysqlite:///{root.as_posix()}/grocery.sqlite3",
        )
        from app.main import app
        from app.models.product import OfferMetadata
        from app.services.plan_store import PlanStore
        from app.services.price_universe_runtime import GLOBAL_PREPARED_PRICE_UNIVERSES

        from backend.scripts.personal_v2_integrated_check import check_integrated
        from backend.tests.test_personal_planning_v2 import prepared, product
        from grocery_data.app.storage import (
            create_database_engine,
            create_schema,
            create_session_factory,
        )

        engine = create_database_engine(os.environ["GROCERY_DATABASE_URL"])
        create_schema(engine)
        app.state.community_session_factory = create_session_factory(engine)
        app.state.plan_store = PlanStore(root / "plans.sqlite3")
        p = prepared(
            product("mjölk 1,5 %", 1000, "ml", 20, offers=[OfferMetadata(kind="member", description="Fryst medlemspris", price=16, membership_program="COOP_MEMBER")]),
            product("ris", 500, "g", 15),
            product("bröd", 500, "g", 25),
            product("ost", 500, "g", 40),
            product("tomat", 500, "g", 20),
            product("ägg", 6, "st", 25),
            product("morot", 1000, "g", 10),
            product("tofu", 400, "g", 30),
            product("kikärtor", 380, "g", 12),
            product("servetter", 50, "st", 15, store="ica"),
        )
        GLOBAL_PREPARED_PRICE_UNIVERSES.activate(p)
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        server = uvicorn.Server(
            uvicorn.Config(
                app,
                host="127.0.0.1",
                port=port,
                lifespan="off",
                log_level="error",
                access_log=False,
            )
        )
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        for _ in range(100):
            if server.started:
                break
            time.sleep(0.05)
        base = f"http://127.0.0.1:{port}"
        results = []
        try:
            with sync_playwright() as pw:
                for name in ("chromium", "webkit"):
                    browser = getattr(pw, name).launch(
                        **({"executable_path": args.webkit} if name == "webkit" else {})
                    )
                    context = browser.new_context(
                        viewport={"width": 390, "height": 844},
                        device_scale_factor=2,
                        is_mobile=True,
                        has_touch=True,
                    )
                    page = context.new_page()
                    page.set_default_timeout(10000)
                    errors = []
                    page.on("pageerror", lambda e, sink=errors: sink.append(str(e)))
                    page.goto(base + "/personal")
                    page.wait_for_function(
                        "document.querySelector('#personal-status').textContent === ''"
                    )
                    page.get_by_role("button", name="Inköpslista", exact=True).click()
                    page.get_by_role("button", name="Lägg till generisk vara", exact=True).click()
                    page.get_by_label("Vara", exact=True).fill("mjölk 1,5 %")
                    page.get_by_label("Önskad mängd").fill("1200")
                    page.get_by_label("Enhet", exact=True).select_option("ml")
                    page.get_by_role("button", name="Tolka egenskaper").click()
                    page.get_by_role("button", name="Bekräfta och lägg till").click()
                    page.get_by_role("button", name="Beräkna inköpslistan").click()
                    page.wait_for_function(
                        "document.querySelector('#shopping-content').textContent.includes('40,00 kr')",
                        timeout=30000,
                    )
                    plan_hash = page.evaluate("location.hash")
                    page.screenshot(path=str(args.output / f"{name}-basket.png"), full_page=True)
                    page.get_by_role("button", name="Bekräfta att jag har köpt varorna").click()
                    page.get_by_role("button", name="Inköpet är bokfört").wait_for()
                    page.get_by_role("button", name="Inköpet är bokfört").click()
                    page.get_by_role("button", name="Skafferi", exact=True).click()
                    page.get_by_text("Faktiskt lager 2 000 ml", exact=False).wait_for()
                    page.reload()
                    page.locator("#generate-plan").wait_for(state="attached")
                    page.wait_for_function(
                        "document.querySelector('#personal-status').textContent === ''"
                    )
                    assert page.evaluate("location.hash") == plan_hash
                    assert not page.locator("#generate-plan").is_disabled()
                    page.get_by_role("button", name="Mina val", exact=True).click()
                    page.locator("#dinner-count").fill("0")
                    page.locator("#breakfast-count").fill("1")
                    page.locator("#snack-count").fill("1")
                    page.get_by_role("button", name="Skapa plan och inköpslista").click()
                    page.locator("#personal-plan").wait_for(state="visible", timeout=30000)
                    page.get_by_text(
                        "0 middagar · 2 övriga måltider · 2 portioner", exact=False
                    ).wait_for()
                    page.get_by_role("button", name="Redigera", exact=True).first.click()
                    page.get_by_label("Receptnamn", exact=True).fill("Min redigerade frukost")
                    page.get_by_role("button", name="Spara och räkna om hela korgen").click()
                    page.get_by_role("heading", name="Min redigerade frukost").wait_for()
                    page.get_by_role("button", name="Ta bort", exact=True).first.click()
                    page.get_by_role("heading", name="Tomt måltidstillfälle").wait_for()
                    page.get_by_role("button", name="Föreslå recept").click()
                    page.get_by_role("heading", name="Tomt måltidstillfälle").wait_for(
                        state="detached"
                    )
                    page.get_by_role("button", name="Mina val", exact=True).click()
                    page.locator("#organic-percent").fill("50")
                    page.get_by_role("button", name="Skapa plan och inköpslista").click()
                    page.get_by_text("Underlag saknas:", exact=False).wait_for()
                    assert not page.locator("#generate-plan").is_disabled()
                    page.locator("#organic-percent").fill("0")
                    page.locator("#profile-text").fill(
                        "Gillar kyckling, ogillar koriander, måste undvika jordnötter"
                    )
                    page.get_by_role("button", name="Tolka och granska").click()
                    page.wait_for_function(
                        "document.querySelector('#profile-exclusions').value === 'jordnötter'"
                    )
                    assert page.locator("#profile-dislikes").input_value() == "koriander"
                    page.screenshot(path=str(args.output / f"{name}-choices.png"), full_page=True)
                    page.add_style_tag(content="html {font-size:24px !important;}")
                    assert page.evaluate(
                        "document.documentElement.scrollWidth <= window.innerWidth + 1"
                    )
                    page.screenshot(
                        path=str(args.output / f"{name}-large-text.png"), full_page=True
                    )
                    assert not errors, errors
                    results.append(
                        {"engine": name, "checks": 18, "status": "PASS", "page_errors": errors}
                    )
                    results[-1]["integrated_booked_edit"] = check_integrated(browser, base, p, args.output, name)
                    browser.close()
        finally:
            server.should_exit = True
            thread.join(timeout=5)
            engine.dispose()
        (args.output / "browser-results.json").write_text(
            json.dumps(results, indent=2), encoding="utf-8"
        )
        print(json.dumps(results))


if __name__ == "__main__":
    main()
