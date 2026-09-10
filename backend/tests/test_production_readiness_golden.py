from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from scripts.benchmark_lund_phase_c import REPRESENTATIVE_REQUIREMENTS

FIXTURE = Path(__file__).parent / "fixtures" / "lund_production_golden_v1.json"


def test_lund_production_golden_captures_complete_deterministic_matrix() -> None:
    golden = json.loads(FIXTURE.read_text(encoding="utf-8"), parse_float=Decimal)

    assert golden["schema_version"] == "lund-production-golden-v1"
    assert len(golden["snapshot_ids"]) == 4
    assert len(REPRESENTATIVE_REQUIREMENTS) == 13
    assert set(golden["representative_basket"]) == {"1", "2", "3"}
    assert set(golden["menus"]) == {"cheapest", "balanced", "varied"}
    assert all(len(row["recipes"]) == 5 for row in golden["menus"].values())
    assert all(
        set(row).issuperset({"recipes", "1", "2"})
        for row in golden["menus"].values()
    )
    assert all(
        scenario["verification"] == "VERIFIED"
        for scenario in golden["representative_basket"].values()
    )
    assert golden["required_status"] == {
        "basket": "VERIFIED",
        "basket_audit": "PASS",
        "nutrition": "PASS",
        "diversity": "PASS",
        "provenance": "PASS",
    }


def test_lund_golden_totals_and_contexts_are_the_accepted_economic_contract() -> None:
    golden = json.loads(FIXTURE.read_text(encoding="utf-8"), parse_float=Decimal)

    assert [
        golden["representative_basket"][str(limit)]["total"]
        for limit in (1, 2, 3)
    ] == [Decimal("340.30"), Decimal("329.30"), Decimal("326.36")]
    assert {
        mode: [golden["menus"][mode][str(limit)]["total"] for limit in (1, 2)]
        for mode in ("cheapest", "balanced", "varied")
    } == {
        "cheapest": [Decimal("225.74"), Decimal("194.04")],
        "balanced": [Decimal("270.87"), Decimal("236.68")],
        "varied": [Decimal("271.73"), Decimal("238.72")],
    }
    assert golden["representative_basket"]["1"]["contexts"] == [
        "context:willys:383650ec6ff5a636"
    ]
    assert golden["menus"]["balanced"]["2"]["contexts"] == [
        "context:hemkop:756955d0e6e05f23",
        "context:willys:383650ec6ff5a636",
    ]
