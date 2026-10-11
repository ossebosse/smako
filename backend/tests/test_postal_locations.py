"""Geographic eligibility over retained shared artifacts, without network I/O."""
from dataclasses import replace
from math import degrees

import pytest
from app.api import plan
from app.config import Settings
from app.services.postal_locations import lookup_postcode, postal_data
from app.services.price_universe_runtime import PreparedPriceUniverseManager
from fastapi import HTTPException

from backend.tests.test_municipal_runtime import build
from backend.tests.test_price_universe_runtime import NON_FRESHNESS_TEST_MAX_AGE_HOURS
from grocery_data.app.domain.municipality import municipality_name


def test_postal_reference_data_and_unknown_are_explicit():
    lund = lookup_postcode("223 50")
    assert lund["municipality_code"] == "1281"
    assert lund["distance_basis"] == "postcode_reference_point"
    assert lookup_postcode("21120")["municipality_name"] == "Malmö"
    assert lookup_postcode("99999")["status"] == "unknown_postcode"
    with pytest.raises(ValueError, match="fem siffror"):
        lookup_postcode("ab22350")
    for rows in postal_data()["postcodes"].values():
        for lat, lon, code in rows:
            assert 54 < lat < 70 and 10 < lon < 25
            assert municipality_name(code)


@pytest.mark.asyncio
@pytest.mark.parametrize(("distance", "expected"), [(9.999, "eligible"), (10.001, "outside_coverage")])
async def test_ten_km_gate_does_not_round_outside_store_inside(monkeypatch, distance, expected):
    manager = PreparedPriceUniverseManager()
    prepared = await build(manager, "Lund", "22350", ["own:hemkop:test"])
    location = lookup_postcode("22350")
    store = prepared.stores[0].model_copy(update={
        "latitude": location["latitude"] + degrees(distance / 6371.0088),
        "longitude": location["longitude"],
    })
    manager.activate(replace(prepared, stores=(store,)))
    monkeypatch.setattr(plan, "GLOBAL_PREPARED_PRICE_UNIVERSES", manager)
    monkeypatch.setattr(plan, "get_settings", lambda: Settings(max_price_age_hours=NON_FRESHNESS_TEST_MAX_AGE_HOURS))

    async def areas():
        return {"municipalities": [{"municipality_code": "1281", "name": "Lund", "postal_code": "22350", "available": True}]}

    monkeypatch.setattr(plan, "available_municipalities", areas)
    result = await plan.shopping_location("223 50")
    assert result["status"] == expected
    assert result["nearest_distance_km"] == pytest.approx(distance)
    if expected == "eligible":
        assert result["area_postal_code"] == "22350"
        assert result["contexts"][0]["distance_km"] == pytest.approx(distance)
    # Online fulfillment's warehouse must never make this postcode eligible.
    warehouse = store.model_copy(update={"latitude": location["latitude"], "price_context_type": "online_fulfillment", "pickup_options": ()})
    manager.activate(replace(prepared, stores=(warehouse,)))
    assert (await plan.shopping_location("22350"))["status"] == "unavailable"


@pytest.mark.asyncio
async def test_postal_endpoint_does_not_fallback_for_unknown_or_invalid():
    assert (await plan.shopping_location("99999"))["status"] == "unknown_postcode"
    with pytest.raises(HTTPException) as error:
        await plan.shopping_location("22!350")
    assert error.value.status_code == 422
