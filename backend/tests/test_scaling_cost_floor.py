"""Historical offer dates must never turn the diagnostic floor into an overestimate."""
import runpy
from datetime import date
from decimal import Decimal
from pathlib import Path

from app.models.product import OfferMetadata
from app.services.product_matcher import ProductCandidate

from backend.tests.test_personal_planning_v2 import product

HELPERS = runpy.run_path(str(Path(__file__).parents[2] /
                            "reports/recipe-scaling-20261019/bound_tightness.py"))


def test_historical_multibuy_always_has_zero_floor():
    item = product("pasta", 500, "g", 20, offers=[
        OfferMetadata(kind="multipack", description="Historical 2 for 10",
                      price=10, required_packages=2,
                      valid_from=date(2020, 1, 1), valid_to=date(2020, 1, 7)),
    ])
    candidate = ProductCandidate.from_product(item, 1)
    assert HELPERS["floor"](candidate) == 0


def test_shared_product_is_counted_once_across_ingredient_groups():
    candidate = ProductCandidate.from_product(product("pasta", 500, "g", 20), 1)
    assert HELPERS["floor"](candidate) == Decimal(20)
    assert HELPERS["week_floor"]({"first": [candidate], "second": [candidate]}) == Decimal(20)
