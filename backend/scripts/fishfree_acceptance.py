"""Ordinary form/API acceptance with immutable public data and synthetic guests."""

import json
import os
import socket
import tempfile
import threading
import time
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import uvicorn
from playwright.sync_api import expect, sync_playwright

from backend.scripts.personal_v2_cost_audit import inputs
from backend.scripts.personal_v2_dinners_probe import fixture

OUTPUT = Path("reports/fishfree-20260913")


def validate(plan):
    assert len(plan["recipes"]) == 5
    assert len(plan["optimized_basket"]["stores"]) <= 2
    assert plan["data"]["live_chain_requests"] == 0
    assert plan["personal"]["checks"]["allergy"] == "NOT_REQUESTED"
    assert plan["personal"]["checks"]["ingredient_exclusions"]
    for n in plan["personal"]["checks"]["nutrition"]:
        assert n["values"]["protein_g"] >= 20 and n["values"]["kcal"] <= 800
    assert (
        round(
            sum(i["total_price"] for s in plan["optimized_basket"]["stores"] for i in s["items"]), 2
        )
        == plan["optimized_basket"]["total"]
    )
    assert all(
        i["packages_needed"] == int(i["packages_needed"])
        for s in plan["optimized_basket"]["stores"]
        for i in s["items"]
    )


def check(base):
    output = {
        "transport": "ordinary Chromium form and API",
        "historical_price_time": True,
        "cases": {},
    }
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(
            viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True
        )
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(base + "/personal")
        page.get_by_role("button", name="Mina val", exact=True).click()
        expect(page.locator("#allow-nutrition-estimates")).not_to_be_checked()
        page.locator("#dinner-count").fill("5")
        page.locator("#dinner-servings").fill("4")
        page.locator("#mode").select_option("balanced")
        page.locator("#max-stores").select_option("2")
        page.locator("#profile-exclusions").fill("fisk")
        card = page.locator("#meal-settings > .personal-card").nth(0)
        card.get_by_text("Fördelning, egna smakval och gränser", exact=True).click()
        card.get_by_text("Portionsvikt och näringsgränser", exact=True).click()
        page.locator("#dinner-min_protein_g").fill("20")
        page.locator("#dinner-max_kcal").fill("800")
        page.locator("#allow-nutrition-estimates").check()
        with page.expect_response(
            lambda r: r.url.endswith("/api/plans") and r.request.method == "POST", timeout=180000
        ) as event:
            page.locator("#generate-plan").click()
        response = event.value
        assert response.status == 201, response.text()
        saved = response.json()
        plan = saved["plan"]
        validate(plan)
        submitted = response.request.post_data_json
        assert submitted["personal"]["profile"]["exclusions"] == ["fisk"]
        assert submitted["personal"]["profile"]["allergies"] == []
        assert not submitted["personal"].get("slots") and not submitted["personal"].get(
            "product_locks"
        )
        output["request"] = submitted
        output["cases"]["A"] = {"status": "PASS", "plan": plan}
        (OUTPUT / "acceptance-progress.json").write_text(
            json.dumps(output, ensure_ascii=False, indent=2), encoding="utf8"
        )
        expect(page.locator("#plan-content .personal-total")).to_be_visible()
        page.get_by_text("Ingredienskontroll för dina matval", exact=True).click()
        page.screenshot(path=str(OUTPUT / "form-menu.png"), full_page=True)
        print("A FORM PASS", plan["optimized_basket"]["total"], flush=True)
        with page.expect_response(
            lambda r: "/change" in r.url and r.request.method == "POST", timeout=180000
        ) as event:
            page.get_by_role("button", name="Byt recept", exact=True).first.click()
        response = event.value
        assert response.status == 200, response.text()
        swapped = response.json()["saved"]
        validate(swapped["plan"])
        assert swapped["plan"]["recipes"][0] != plan["recipes"][0]
        output["cases"]["B"] = {"status": "PASS", "plan": swapped["plan"]}
        print("B SWAP PASS", swapped["plan"]["optimized_basket"]["total"], flush=True)
        # A real stock lot with identity obtained from the freely generated basket.
        pantry = browser.new_context()
        api = pantry.request
        state = api.get(base + "/api/personal/state").json()
        rice = next(n for n in plan["personal"]["needs"] if n["name"] == "ris")
        rice_product = next(
            i
            for s in plan["optimized_basket"]["stores"]
            for i in s["items"]
            if i["ingredient"] == rice["key"]
        )
        stock = {
            "id": "acceptance-rice",
            "name": rice_product["product_name"],
            "quantity": 500,
            "unit": "g",
            "product_key": rice["selected_product_key"],
            "unusable": False,
            "food": True,
            "nutrition_reference": None,
        }
        response = api.put(
            base + "/api/personal/pantry", data={"revision": state["revision"], "items": [stock]}
        )
        assert response.status == 200, response.text()
        before = api.get(base + "/api/personal/state").json()
        req = deepcopy(submitted)
        req["personal"]["pantry_revision"] = before["revision"]
        response = api.post(base + "/api/plans", data=req, timeout=180000)
        assert response.status == 201, response.text()
        pantry_plan = response.json()["plan"]
        validate(pantry_plan)
        after = api.get(base + "/api/personal/state").json()
        assert [(i["id"], i["quantity"]) for i in before["items"]] == [
            (i["id"], i["quantity"]) for i in after["items"]
        ]
        assert sum(a["quantity"] for a in pantry_plan["personal"]["allocations"]) == 500
        output["cases"]["C"] = {
            "status": "PASS",
            "plan": pantry_plan,
            "stock": stock,
            "stock_unchanged": True,
            "reserved": 500,
        }
        print("C PANTRY PASS", pantry_plan["optimized_basket"]["total"], flush=True)
        # Allergy is independently conservative even where ingredient review succeeds.
        allergy = browser.new_context()
        api = allergy.request
        state = api.get(base + "/api/personal/state").json()
        req = deepcopy(submitted)
        req["personal"]["pantry_revision"] = state["revision"]
        req["personal"]["profile"]["exclusions"] = []
        req["personal"]["profile"]["allergies"] = ["fisk"]
        response = api.post(base + "/api/plans", data=req, timeout=180000)
        assert response.status == 422, response.text()
        assert response.json()["code"] == "DATA_BLOCKED"
        output["cases"]["E"] = {
            "status": "PASS_CONSERVATIVE_DATA_BLOCKED",
            "response": response.json(),
        }
        # A fish edit cannot replace the saved compliant revision.
        api = ctx.request
        state = api.get(base + "/api/personal/state").json()
        bad = deepcopy(swapped["plan"]["personal"]["slots"][0]["recipe"])
        bad["ingredients"][0]["name"] = "lax"
        response = api.post(
            base + "/api/personal/plans/" + swapped["plan_id"] + "/change",
            data={
                "action": "edit",
                "revision": swapped["revision"],
                "pantry_revision": state["revision"],
                "slot_id": swapped["plan"]["personal"]["slots"][0]["id"],
                "recipe": bad,
            },
            timeout=180000,
        )
        assert response.status == 422, response.text()
        restored = api.get(base + "/api/plans/" + swapped["plan_id"]).json()
        assert restored["revision"] == swapped["revision"]
        output["cases"]["edit_guard"] = {"status": "PASS", "response": response.json()}
        assert not errors, errors
        output["page_errors"] = errors
        browser.close()
    return output


def main():
    with tempfile.TemporaryDirectory(prefix="smako-fishfree-", ignore_cleanup_errors=True) as temp:
        root = Path(temp)
        os.environ.update(
            PLAN_STORE_PATH=str(root / "plans.sqlite"),
            PRICE_PROVIDER="mock",
            GROCERY_DATABASE_URL=f"sqlite+pysqlite:///{root.as_posix()}/grocery.sqlite",
        )
        from app.main import app
        from app.services.plan_store import PlanStore
        from app.services.price_universe_runtime import GLOBAL_PREPARED_PRICE_UNIVERSES

        from grocery_data.app.storage import (
            create_database_engine,
            create_schema,
            create_session_factory,
        )

        engine = create_database_engine(os.environ["GROCERY_DATABASE_URL"])
        create_schema(engine)
        app.state.community_session_factory = create_session_factory(engine)
        app.state.plan_store = PlanStore(root / "plans.sqlite")
        prepared, facts = fixture()
        GLOBAL_PREPARED_PRICE_UNIVERSES.activate(prepared)

        class FrozenDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return prepared.universe.built_at.astimezone(tz)

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
        original_connect = socket.socket.connect
        external = []

        def connect(sock, address):
            if isinstance(address, tuple) and address[0] not in {"127.0.0.1", "::1", "localhost"}:
                external.append(str(address))
                raise AssertionError("Consumer external call forbidden")
            return original_connect(sock, address)

        with (
            patch("app.services.personal_source_facts.load_retained_facts", return_value=facts),
            patch("app.services.personal_planner.datetime", FrozenDateTime),
            patch("socket.socket.connect", connect),
        ):
            thread.start()
            while not server.started:
                time.sleep(0.05)
            try:
                output = check(f"http://127.0.0.1:{port}")
                # Preserve the historical approved menu against its unchanged
                # historical ingredient observations, using the ordinary API.
                with patch(
                    "app.services.reviewed_ingredients.enrich_ingredients",
                    side_effect=lambda p, f: f,
                ):
                    _, historical_facts = fixture()
                with patch(
                    "app.services.personal_source_facts.load_retained_facts",
                    return_value=historical_facts,
                ):
                    _, cases = inputs()
                    with sync_playwright() as pw:
                        api = pw.request.new_context()
                        state = api.get(f"http://127.0.0.1:{port}/api/personal/state").json()
                        req = deepcopy(cases["same_menu"]["request"])
                        req["personal"]["pantry_revision"] = state["revision"]
                        response = api.post(
                            f"http://127.0.0.1:{port}/api/plans", data=req, timeout=180000
                        )
                        assert response.status == 201, response.text()
                        plan = response.json()["plan"]
                        assert plan["optimized_basket"]["total"] == 677.43
                        assert (
                            len(plan["recipes"]) == 5 and plan["data"]["live_chain_requests"] == 0
                        )
                        output["cases"]["D"] = {
                            "status": "PASS_HISTORICAL_UNCHANGED_FACTS",
                            "plan": plan,
                        }
                        print("D ORIGINAL FISH PASS", plan["optimized_basket"]["total"], flush=True)
                output.update(
                    price_version=prepared.universe.universe_id,
                    facts_version=facts.version,
                    external_consumer_calls=len(external),
                )
                assert not external
                (OUTPUT / "acceptance.json").write_text(
                    json.dumps(output, ensure_ascii=False, indent=2), encoding="utf8"
                )
            finally:
                server.should_exit = True
                thread.join(timeout=5)
                engine.dispose()


if __name__ == "__main__":
    main()
