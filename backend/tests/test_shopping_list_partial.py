"""One own item nobody sells does not stop the rest of the shopping list."""
import pytest
from app.models.personal import ExtraNeed
from app.services.personal_policy import PolicyConflict

from backend.tests.test_personal_planning_v2 import prepared, product, request, run


def test_the_list_is_bought_and_the_missing_item_is_named():
    p = prepared(product("mjölk", 1000, "ml", 12), product("bröd", 500, "g", 25))
    req = request(extras=[ExtraNeed(query="mjölk", quantity=1000, unit="ml", confirmed=True),
                          ExtraNeed(query="kattmat", quantity=85, unit="g", confirmed=True)])
    result = run(p, req)
    assert result.optimized_basket.total == 12
    missing = result.personal.checks["missing_extras"]
    assert [m["name"] for m in missing] == ["kattmat"] and "Vi hittar ingen vara" in missing[0]["reason"]


def test_a_list_with_only_unknown_items_still_says_why():
    p = prepared(product("mjölk", 1000, "ml", 12))
    with pytest.raises(PolicyConflict, match="Vi hittar ingen vara att köpa för kattmat"):
        run(p, request(extras=[ExtraNeed(query="kattmat", quantity=85, unit="g", confirmed=True)]))
