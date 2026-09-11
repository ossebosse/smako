"""Shared frozen API/UI acceptance for booked-purchase revisions."""

from copy import deepcopy

from playwright.sync_api import expect


def check_integrated(browser, base, prepared, output, engine):
    from app.models.personal import ExtraNeed, MealSettings, MealSlot
    from app.models.recipe import RecipeIngredient

    from backend.tests.test_personal_planning_v2 import key_for, recipe, request

    context = browser.new_context(
        viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True
    )
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(base + "/personal")
    expect(page.locator("#personal-status")).to_have_text("")
    response = context.request.put(
        base + "/api/personal/pantry",
        data={
            "revision": 0,
            "items": [{"id": "initial-milk", "name": "mjölk", "quantity": 300, "unit": "ml"}],
        },
    )
    assert response.status == 200, response.text()
    stock = response.json()
    meals = [
        MealSettings(meal_type=t, count=1, servings=1) for t in ("dinner", "breakfast", "snack")
    ]
    slots = [
        MealSlot(
            id=t,
            day=1,
            meal_type=t,
            recipe=recipe(
                name=f"Fryst {t}",
                ingredients=[
                    RecipeIngredient(name="mjölk", quantity=200, unit="ml"),
                    RecipeIngredient(name="ris", quantity=200, unit="g"),
                ],
            ),
        )
        for t in ("dinner", "breakfast", "snack")
    ]
    req = request(
        slots=slots,
        meals=meals,
        pantry_revision=stock["revision"],
        extras=[
            ExtraNeed(query="mjölk", quantity=600, unit="ml", confirmed=True),
            ExtraNeed(
                kind="exact",
                query="servetter",
                quantity=50,
                unit="st",
                food=False,
                confirmed=True,
                product_key=key_for(prepared, "servetter"),
            ),
        ],
    )
    req.memberships = {"coop": True}
    response = context.request.post(base + "/api/plans", data=req.model_dump(mode="json"))
    assert response.status == 201, response.text()
    saved = response.json()
    plan_id = saved["plan_id"]
    assert saved["plan"]["optimized_basket"]["total"] == 61  # milk 16 + rice 30 + napkins 15
    assert saved["plan"]["optimized_basket"]["store_count"] == 2
    after_generation = context.request.get(base + "/api/personal/state").json()
    assert after_generation["items"][0]["quantity"] == 300
    assert len(after_generation["items"]) == 1
    page.goto(base + "/personal#plan=" + plan_id)
    page.reload()
    expect(page.locator("#plan-content .personal-total")).to_have_text("61,00 kr")
    page.get_by_role("button", name="Öppna inköpslistan", exact=True).click()
    page.get_by_role("button", name="Bekräfta att jag har köpt varorna", exact=True).click()
    expect(page.get_by_role("button", name="Inköpet är bokfört", exact=True)).to_be_visible()
    purchased = context.request.get(base + "/api/personal/state").json()
    purchase_history = deepcopy(purchased["ledger"])
    page.get_by_role("button", name="Inköpet är bokfört", exact=True).click()
    expect(page.locator("#personal-status")).to_have_text("")
    assert context.request.get(base + "/api/personal/state").json() == purchased
    page.get_by_role("button", name="Min plan", exact=True).click()
    page.get_by_role("button", name="Redigera", exact=True).first.click()
    page.get_by_label("Receptnamn", exact=True).fill("Ändrad efter bokfört köp")
    amounts = page.locator("#personal-dialog").get_by_label("Mängd", exact=True)
    amounts.nth(0).fill("600")
    amounts.nth(1).fill("700")
    with page.expect_response(lambda r: r.url.endswith("/change")) as event:
        page.get_by_role("button", name="Spara och räkna om hela korgen").click()
    changed = event.value.json()
    original_mutation = event.value.request.post_data_json
    assert event.value.status == 200, changed
    expect(page.get_by_role("heading", name="Ändrad efter bokfört köp")).to_be_visible()
    expect(page.locator("#plan-content .personal-total")).to_have_text("31,00 kr")
    assert changed["saved"]["revision"] == 2
    assert changed["saved"]["plan"]["optimized_basket"]["total"] == 31
    assert changed["state"]["ledger"] == purchase_history
    assert len(changed["state"]["items"]) == len(purchased["items"])
    assert [i["quantity"] for i in changed["state"]["items"]] == [
        i["quantity"] for i in purchased["items"]
    ]
    replay = context.request.post(
        base + f"/api/personal/plans/{plan_id}/change", data=original_mutation
    )
    assert replay.status == 200 and replay.json()["saved"]["revision"] == 2
    stale = {**original_mutation, "action": "remove", "recipe": None}
    assert (
        context.request.post(base + f"/api/personal/plans/{plan_id}/change", data=stale).status
        == 409
    )
    assert (
        context.request.get(base + f"/api/plans/{plan_id}?revision=1").json()["plan"][
            "optimized_basket"
        ]["total"]
        == 61
    )
    page.get_by_role("button", name="Öppna inköpslistan", exact=True).click()
    expect(page.locator("#shopping-content .personal-total")).to_contain_text("31,00 kr")
    page.get_by_text("Oföränderlig inköps- och förbrukningshistorik", exact=True).click()
    expect(
        page.get_by_role("heading", name="Bokfört inköp · planrevision 1 · 61,00 kr")
    ).to_be_visible()
    page.get_by_role("button", name="Bekräfta att jag har köpt varorna", exact=True).click()
    expect(page.get_by_role("button", name="Inköpet är bokfört", exact=True)).to_be_visible()
    topped = context.request.get(base + "/api/personal/state").json()
    assert [event["total"] for event in topped["ledger"]] == [61, 31]
    assert topped["ledger"][0] == purchase_history[0]
    expect(page.locator(".skip-link")).not_to_be_focused()
    assert page.locator(".skip-link").evaluate("e => e.getBoundingClientRect().bottom <= 0")
    page.screenshot(path=str(output / f"{engine}-viewport-after-edit.png"))
    page.screenshot(path=str(output / f"{engine}-after-purchase-edit.png"), full_page=True)
    page.get_by_role("button", name="Min plan", exact=True).click()
    page.get_by_role("button", name="Räkna om med aktuellt skafferi/pris").click()
    expect(page.locator("#plan-content .personal-total")).to_have_text("0,00 kr")
    final_state = context.request.get(base + "/api/personal/state").json()
    assert final_state["ledger"] == topped["ledger"]
    assert sum(i["available"] for i in final_state["items"] if i["unit"] == "ml") == 700
    assert sum(i["available"] for i in final_state["items"] if i["unit"] == "g") == 400
    assert not errors, errors
    context.close()
    return {
        "status": "PASS",
        "initial_cost": 61,
        "topup_cost": 31,
        "historical_cost": 92,
        "remaining_cost": 0,
        "existing_pantry_ml": 300,
        "surplus_milk_ml": 700,
        "surplus_rice_g": 400,
        "max_contexts": 2,
        "source": "FROZEN_SYNTHETIC_PRICES",
        "group_offer": "tested separately",
    }
