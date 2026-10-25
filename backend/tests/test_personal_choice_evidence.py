"""The bounded report keeps failures, full-list checks and budget provenance."""
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).parents[2] / "docs/reviews/personal-choice-latency-20261025"


def test_closed_budget_and_native_request_provenance():
    evidence = json.loads((ROOT / "evidence.json").read_bytes())
    charged = sum(row["wall_seconds"] for row in evidence["budget"])
    assert all(row["status"] == "closed" for row in evidence["budget"])
    assert charged <= 7200
    assert math.isclose(evidence["charged_wall_seconds"], charged)
    assert math.isclose(evidence["remaining_seconds"], 7200 - charged)
    digest = hashlib.sha256((ROOT / "requests.json").read_bytes()).hexdigest()
    for arm in evidence["arms"].values():
        if arm["product_comparison_eligible"]:
            assert arm["requests_sha256"] == digest
            assert arm["recipe_count"] == 262
            assert not arm["instrumented"]
            assert arm["resources"]["NanoCpus"] == 2_000_000_000
            assert arm["resources"]["Memory"] == 3 * 1024**3
            assert not arm["state"]["OOMKilled"]
            assert len(arm["probe_sha256"]) == 64


def test_pairs_retain_audited_outcomes_and_do_not_count_blocked_e_as_a_list():
    evidence = json.loads((ROOT / "evidence.json").read_bytes())
    for before, after in (("base-ui-normal", "final-ui-prefix"),
                          ("base-ui-target", "final-ui-target"),
                          ("base-ui-trial2", "final-ui-trial2")):
        old, new = (evidence["arms"][name] for name in (before, after))
        assert old["inputs"] == new["inputs"]
        assert old["library"] == new["library"]
        assert old["probe_sha256"] == new["probe_sha256"]
        assert len(old["records"]) == len(new["records"])
        for a, b in zip(old["records"], new["records"], strict=True):
            assert (a["case"], a["owner"], a["outcome"]) == (b["case"], b["owner"], b["outcome"])
            if a["outcome"] == "PASS":
                assert a["paid"] == b["paid"]
                assert a["semantic_sha256"] == b["semantic_sha256"]
                for row in (a, b):
                    assert row["audit_passed"] and row["history_read_passed"]
                    assert row["unknown_quantities"] == 0
                    assert row["through_get_seconds"] >= row["saved_response_seconds"]
            elif a["case"] == "E":
                for row in (a, b):
                    assert row["outcome"] == "BLOCKED"
                    assert row["error"]["code"] == "SEARCH_BLOCKED"
                    assert "through_get_seconds" not in row
                assert a["error"]["qualification"] == b["error"]["qualification"]
            else:
                assert a["case"] == "D" and a["outcome"] == "TIMEOUT"
    browser = json.loads((ROOT / "browser.json").read_bytes())[-1]
    assert browser["matches_frozen_E_except_actual_revision"]
    assert browser["status"] == "BLOCKED" and browser["http_status"] == 422
    assert not browser["exact_E_prepared"]
