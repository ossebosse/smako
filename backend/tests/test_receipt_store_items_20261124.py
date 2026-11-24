"""Owner decisions 2026-11-24: Smako learns store items from members' receipts.

A scanned item the store's list lacks becomes a temporary item; two different
members buying it at least seven days apart make it persistent, with bonus
points for the receipt that confirms it.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest
from app.models.product import ProductCandidate
from app.services import member_rewards as rewards
from app.services import receipt_prices
from app.services.plan_store import PlanStore
from app.services.planning_rules import PlanningRules
from app.services.user_pricing import price_candidate_for_context

from grocery_data.app.domain.promotion_pricing import UserPricingContext

KNOWN = [{"store_id": "context:hemkop:1", "name": "Hemköp Lund Karhögstorg", "chain": "hemkop"},
         {"store_id": "context:hemkop:2", "name": "Hemköp Lund Karhögstorg", "chain": "hemkop"}]
CATALOGUE = rewards.StoreProducts([
    {"name": "Kvarg Naturell 0,2% 900g", "brand": "Arla", "price": 31.95, "gtin": "7310865000001"},
    {"name": "Bakpulver Eko", "brand": "Garant Eko", "price": 12.0},
    {"name": "Mjölk 3% 1,5l", "brand": "Arla", "price": 19.95},
])
CHIPS = "7310000000777"
RULES = PlanningRules()


def receipt(day, *extra):
    lines = [{"description": "KVARG 900G NAT 0,2%", "price": 31.95}, {"description": "BAKPULVER EKO", "price": 12.0},
             {"description": "MJÖLK 3% 1,5L", "price": 19.95}, *extra]
    return {"store_text": "HEMKÖP KARHÖGSTORG", "purchased_on": day, "lines": lines}


def chips(price=15.0):
    return {"description": "OLW CHIPS GRILL 275G", "price": price, "gtin": CHIPS}


@pytest.fixture
def store(tmp_path):
    return PlanStore(tmp_path / "plans.sqlite")


def claim(store, owner, day, *extra):
    learned = lambda name: rewards.learned_items(store, name, RULES, today=day)
    result = rewards.evaluate(receipt(day, *extra), {}, RULES, KNOWN, store_products=lambda _: CATALOGUE,
                              learned_items=learned)
    return result, rewards.save_receipt(store, owner, None, result, RULES)


def test_an_unscanned_missing_item_needs_its_barcode_and_adds_nothing(store):
    result, done = claim(store, "member-a", "2026-11-20", {"description": "OLW CHIPS GRILL 275G", "price": 15.0})
    line = result["lines"][-1]
    assert line["missing_in_smako"] and line["needs_barcode"] and line["points"] == 0 and not line["new_item"]
    assert done["new_items"] == [] and rewards.store_items(store, RULES, include_hidden=True) == []


def test_a_scanned_missing_item_becomes_a_temporary_item_in_that_store(store):
    result, done = claim(store, "member-a", "2026-11-20", chips())
    line = result["lines"][-1]
    assert line["new_item"] and line["points"] == RULES.receipt_missing_points
    assert done["new_items"] == ["OLW CHIPS GRILL 275G"] and done["points"] == 10 + 5
    [item] = rewards.store_items(store, RULES, today="2026-11-21")
    assert item["state"] == "temporary" and item["temporary"] and item["days_left"] == 3
    assert item["store"] == "Hemköp Lund Karhögstorg" and item["store_ids"] == ["context:hemkop:1", "context:hemkop:2"]
    assert "Tillfälligt" in item["note"] and "20/11" in item["note"]
    assert rewards.planner_items(store, RULES, ["context:hemkop:2"], today="2026-11-21") == [item]
    assert rewards.planner_items(store, RULES, ["context:willys:1"], today="2026-11-21") == []
    # Hidden after the temporary days, but remembered.
    assert rewards.store_items(store, RULES, today="2026-11-25") == []
    [hidden] = rewards.store_items(store, RULES, include_hidden=True, today="2026-11-25")
    assert hidden["state"] == "dormant"


def test_the_same_item_again_gives_no_missing_points(store):
    claim(store, "member-a", "2026-11-20", chips())
    result, done = claim(store, "member-b", "2026-11-22", chips(14.0))
    line = result["lines"][-1]
    assert line["learned_item"] == "OLW CHIPS GRILL 275G" and line["learned_state"] == "temporary" and line["points"] == 0
    assert done["persistent_items"] == [] and done["bonus_points"] == 0  # only two days apart
    [item] = rewards.store_items(store, RULES, today="2026-11-22")
    assert item["state"] == "temporary" and item["price"] == 14.0 and item["members"] == 2


def test_two_members_seven_days_apart_make_it_persistent_with_bonus(store):
    claim(store, "member-a", "2026-11-01", chips())
    result, done = claim(store, "member-b", "2026-11-08", chips())
    assert result["lines"][-1]["learned_state"] == "dormant"
    assert done["persistent_items"] == ["OLW CHIPS GRILL 275G"] and done["bonus_points"] == RULES.receipt_item_persist_points
    assert done["points"] == 10 + RULES.receipt_item_persist_points
    assert any("Bekräftade varor" in h["reason"] for h in done["history"])
    [item] = rewards.store_items(store, RULES, today="2026-12-20")
    assert item["state"] == "persistent" and not item["temporary"] and "kvitton" in item["note"]
    # Forgotten when nobody has bought it for receipt_item_forget_days.
    assert rewards.store_items(store, RULES, today="2027-01-10") == []


def test_one_member_cannot_make_an_item_persistent(store):
    claim(store, "member-a", "2026-11-01", chips())
    _, done = claim(store, "member-a", "2026-11-15", chips())
    assert done["persistent_items"] == []
    [item] = rewards.store_items(store, RULES, include_hidden=True, today="2026-11-15")
    assert item["state"] == "temporary"


def test_a_barcode_smako_has_in_the_store_is_the_store_product(store):
    scanned = {"description": "KVARG 900G NAT 0,2%", "price": 29.0, "gtin": "7310865000001"}
    result = rewards.evaluate({**receipt("2026-11-20"), "lines": receipt("2026-11-20")["lines"][1:] + [scanned]}, {}, RULES,
                              KNOWN, store_products=lambda _: CATALOGUE)
    line = result["lines"][-1]
    assert line["smako_product"].startswith("Kvarg") and line["price_differs"] and not line["new_item"]


def test_a_barcode_for_another_product_than_the_text_suggests_is_a_new_item(store):
    # The receipt text looks like Smako's milk, but Smako's milk has another barcode.
    other = rewards.StoreProducts([{"name": "Mjölk 3% 1,5l", "brand": "Arla", "price": 19.95, "gtin": "7310865000099"}])
    line = {"description": "MJÖLK 3% 1,5L", "price": 17.95, "gtin": "7340000000123"}
    result = rewards.evaluate({**receipt("2026-11-20"), "lines": [line] * 3}, {}, RULES, KNOWN,
                              store_products=lambda _: other)
    assert all(l["new_item"] for l in result["lines"])


def test_erasing_a_member_removes_their_sightings(store):
    owner = "a" * 64
    claim(store, owner, "2026-11-20", chips())
    with store._connect() as db:
        assert db.execute("SELECT COUNT(*) FROM member_store_item_sightings WHERE owner=?", (owner,)).fetchone()[0] == 1
    store.erase_owned(owner_actor_hash=owner)
    with store._connect() as db:
        assert db.execute("SELECT COUNT(*) FROM member_store_item_sightings WHERE owner=?", (owner,)).fetchone()[0] == 0


def test_admin_can_forget_an_item(store):
    claim(store, "member-a", "2026-11-20", chips())
    [item] = rewards.store_items(store, RULES, include_hidden=True)
    assert rewards.remove_store_item(store, item["id"]) and rewards.store_items(store, RULES, include_hidden=True) == []


# Owner correction 2026-11-24: a local discount is often on a product Smako already has.
KVARG = "7310865000001"


def kvarg(price):
    return {"description": "KVARG 900G NAT 0,2%", "price": price, "gtin": KVARG}


def price_claim(store, owner, day, price):
    lines = [kvarg(price), {"description": "BAKPULVER EKO", "price": 12.0}, {"description": "MJÖLK 3% 1,5L", "price": 19.95}]
    learned = lambda name: rewards.learned_items(store, name, RULES, today=day)
    result = rewards.evaluate({**receipt(day), "lines": lines}, {}, RULES, KNOWN, store_products=lambda _: CATALOGUE,
                              learned_items=learned)
    return result, rewards.save_receipt(store, owner, None, result, RULES)


def test_a_scanned_lower_price_on_a_smako_product_becomes_a_temporary_store_price(store):
    result, done = price_claim(store, "member-a", "2026-11-20", 24.95)
    line = result["lines"][0]
    assert line["price_differs"] and line["local_price"] and not line["new_item"] and line["points"] == 2
    assert done["new_prices"] == ["Kvarg Naturell 0,2% 900g"] and done["new_items"] == []
    [item] = rewards.store_items(store, RULES, today="2026-11-21")
    assert item["kind"] == "price" and item["state"] == "temporary" and item["price"] == 24.95
    assert item["smako_price"] == 31.95 and "Tillfälligt pris" in item["note"]


def test_the_same_store_price_again_gives_no_points_but_counts_toward_persistence(store):
    price_claim(store, "member-a", "2026-11-01", 24.95)
    result, done = price_claim(store, "member-b", "2026-11-09", 24.95)
    line = result["lines"][0]
    assert line["learned_item"] and line["points"] == 0 and not line["local_price"]
    assert done["persistent_items"] == ["Kvarg Naturell 0,2% 900g"] and done["bonus_points"] == 3
    [item] = rewards.store_items(store, RULES, today="2026-11-20")
    assert item["state"] == "persistent" and "Butikens pris" in item["note"]


def test_another_price_starts_over(store):
    price_claim(store, "member-a", "2026-11-01", 24.95)
    result, done = price_claim(store, "member-b", "2026-11-09", 27.0)
    assert result["lines"][0]["local_price"] and result["lines"][0]["points"] == 2
    assert done["persistent_items"] == [] and done["new_prices"] == ["Kvarg Naturell 0,2% 900g"]
    [item] = rewards.store_items(store, RULES, today="2026-11-09")
    assert item["state"] == "temporary" and item["price"] == 27.0


def test_an_unscanned_other_price_teaches_no_store_price(store):
    lines = [{"description": "KVARG 900G NAT 0,2%", "price": 24.95}, {"description": "BAKPULVER EKO", "price": 12.0},
             {"description": "MJÖLK 3% 1,5L", "price": 19.95}]
    result = rewards.evaluate({**receipt("2026-11-20"), "lines": lines}, {}, RULES, KNOWN, store_products=lambda _: CATALOGUE)
    assert result["lines"][0]["price_differs"] and not result["lines"][0]["local_price"]
    rewards.save_receipt(store, "member-a", None, result, RULES)
    assert rewards.store_items(store, RULES, include_hidden=True) == []


# Owner decision 2026-11-24: what receipts teach reaches planning at once, without a rebuild.


@pytest.fixture
def live(store, monkeypatch):
    monkeypatch.setattr(receipt_prices, "_path", lambda: store.path)
    monkeypatch.setattr(receipt_prices, "REFRESH_SECONDS", 0)
    receipt_prices.reset_for_tests()
    yield store
    receipt_prices.reset_for_tests()


def product(store_id="context:hemkop:1", gtin=KVARG, price=31.95, name="Kvarg Naturell 0,2% 900g"):
    return ProductCandidate(product_id=f"{store_id}:kvarg", product_name=name, canonical_name="kvarg", store_id=store_id,
                            store_name="Hemköp Lund Karhögstorg", package_quantity=900, package_unit="g", price=price,
                            effective_price=price, match_score=1, gtin=gtin, chain="hemkop")


def priced(candidate, day):
    return price_candidate_for_context(candidate, UserPricingContext(), on_date=date.fromisoformat(day))


def test_a_temporary_receipt_price_is_planned_at_once_and_ends(live):
    assert receipt_prices.version() == 0
    price_claim(live, "member-a", "2026-11-20", 24.95)
    assert receipt_prices.version() == 1
    now = priced(product(), "2026-11-21")
    assert now.effective_price == 24.95
    [offer] = [o for o in now.offers if o.source_confidence == "member_receipt"]
    assert "Tillfälligt pris enligt kvitto 20/11" in offer.description and offer.valid_to == date(2026, 11, 24)
    assert priced(product(), "2026-11-25").effective_price == 31.95  # the deal is over
    assert priced(product(store_id="context:willys:1"), "2026-11-21").effective_price == 31.95  # another store


def test_a_confirmed_higher_store_price_replaces_smakos(live):
    price_claim(live, "member-a", "2026-11-01", 34.95)
    assert priced(product(), "2026-11-02").effective_price == 31.95  # temporary and higher: not used
    price_claim(live, "member-b", "2026-11-09", 34.95)
    assert priced(product(), "2026-11-10").effective_price == 34.95


def test_a_new_item_is_copied_from_the_store_that_has_its_barcode(live):
    claim(live, "member-a", "2026-11-20", chips())
    stores = [SimpleNamespace(store_id="context:hemkop:1", name="Hemköp Lund Karhögstorg", chain="hemkop"),
              SimpleNamespace(store_id="context:willys:1", name="Willys Lund", chain="willys")]
    twin = product(store_id="context:willys:1", gtin=CHIPS, price=22.9, name="OLW Grillchips 275g").model_copy(
        update={"chain": "willys"})
    [copy] = receipt_prices.store_copies(twin, {"context:hemkop:1", "context:hemkop:2"}, stores, date(2026, 11, 21))
    assert copy.store_id == "context:hemkop:1" and copy.chain == "hemkop" and copy.product_name == "OLW Grillchips 275g"
    planned = priced(copy, "2026-11-21")
    assert planned.effective_price == 15.0 and "Tillfälligt" in planned.offers[0].description
    assert receipt_prices.store_copies(twin, {"context:willys:1"}, stores, date(2026, 11, 21)) == []
    assert receipt_prices.store_copies(twin, {"context:hemkop:1"}, stores, date(2026, 11, 26)) == []  # hidden again


def test_removing_an_item_reaches_planning(live):
    price_claim(live, "member-a", "2026-11-20", 24.95)
    [item] = rewards.store_items(live, RULES, today="2026-11-21")
    rewards.remove_store_item(live, item["id"])
    assert priced(product(), "2026-11-21").effective_price == 31.95
