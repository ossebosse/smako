"""The seed and refinement caps are heuristics: they must never make a menu dearer.

The unit tests check the comparison itself. The evidence test plans real
profiles twice, capped (defaults) and over the whole qualified library, and
fails if the capped plan pays more or changes outcome. It needs a frozen
universe: set SMAKO_REVIEW_DATA to a folder with prepared-universe.json and
product-facts.json (the review bundle's data/lund). Without it it is skipped.
Slow (several minutes per profile on one CPU); run it before changing caps or
adding many recipes, and on the server with the acceptance matrix's
``--uncapped`` / ``--uncapped-reference`` options.
"""
import json
import os
import socket
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.scripts.planner_acceptance_matrix import cap_regression, full_library_search_limits

PROFILES = os.environ.get("SMAKO_CAP_PROFILES", "standard,distribution").split(",")


def test_cap_regression_accepts_equal_or_cheaper_and_same_failures():
    assert cap_regression({"outcome": "PASS", "paid": 548.76}, {"outcome": "PASS", "paid": 548.76}) == "ok"
    assert cap_regression({"outcome": "BLOCKED", "code": "X", "stage": "s"},
                          {"outcome": "BLOCKED", "code": "X", "stage": "s"}) == "ok"


def test_cap_regression_reports_a_dearer_menu_or_changed_outcome():
    assert "771.26" in cap_regression({"outcome": "PASS", "paid": 771.26}, {"outcome": "PASS", "paid": 766.11})
    assert "outcome" in cap_regression({"outcome": "BLOCKED", "code": "X"}, {"outcome": "PASS", "paid": 1})


@pytest.mark.skipif(not os.environ.get("SMAKO_REVIEW_DATA"), reason="Kräver SMAKO_REVIEW_DATA med fryst prisunderlag")
@pytest.mark.parametrize("case", PROFILES)
def test_capped_search_never_pays_more_than_the_whole_library(case):
    from app.config import Settings
    from app.services.personal_planner import PersonalPlanner
    from app.services.personal_policy import PolicyConflict, ProductFacts
    from app.services.personal_source_facts import FactsCollection
    from app.services.price_universe_runtime import PreparedPriceUniverseArtifact

    from backend.scripts.planner_acceptance_matrix import matrix_request

    data = Path(os.environ["SMAKO_REVIEW_DATA"])
    prepared = PreparedPriceUniverseArtifact.model_validate_json((data / "prepared-universe.json").read_bytes()).restore()
    raw = json.loads((data / "product-facts.json").read_bytes())
    facts = FactsCollection({(r["store_id"], r["product_id"]): ProductFacts(**r["facts"]) for r in raw["rows"]})
    facts.version = raw["facts_version"]
    request = matrix_request({"recipe_preferences": {"mode": "complete"}, "purchase_planning_mode": "estimated",
                              "max_stores": 2, "allowed_store_ids": [s.store_id for s in prepared.stores]}, case)
    now = datetime.fromisoformat(os.environ.get("SMAKO_REVIEW_CLOCK", "2026-10-16T18:12:49.613708+00:00"))
    capped = Settings(complete_recipes_enabled=True, price_provider="own")
    rows = []
    for settings in (capped, full_library_search_limits(capped)):
        with patch.object(socket.socket, "connect", side_effect=AssertionError("Network forbidden")):
            try:
                plan = PersonalPlanner(request, settings, prepared, {"revision": 0, "items": [], "reservations": {},
                                       "events": {}}, facts=facts, now=now).create()
                rows.append({"outcome": "PASS", "paid": plan.optimized_basket.total})
            except PolicyConflict as exc:
                rows.append({"outcome": "BLOCKED", "code": exc.code, "stage": exc.stage})
    assert cap_regression(*rows) == "ok"
