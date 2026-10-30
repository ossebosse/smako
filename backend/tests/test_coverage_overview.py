"""Coverage must preserve denominators, actual decisions and unknown outcomes."""
import csv
import gzip
import json
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from check_coverage_overview import baseline, compare, validate, validate_product_details
from coverage_overview import (
    CoverageTrace,
    gap_queries,
    product_counts,
    rank_blockers,
    recipe_totals,
)
from coverage_reference_asset import review_projection, sha, unpack


def test_actual_rejection_is_not_inferred_from_nonselection_or_missing_recipe():
    products = [SimpleNamespace(store_id="s", product_id=str(i)) for i in range(4)]
    trace = CoverageTrace(products)
    for _ in range(3):
        trace.event(products[0], None, "rice", "recipe_match", "stopped", "wrong form")
    trace.event(products[1], None, "rice", "quantity_unit", "stopped", "unknown grams")
    trace.event(products[1], None, "milk", "recipe_match", "stopped", "wrong food")
    # Product 0 qualifies in another real recipe; 2 was never examined.
    accepted = {("s", "0"), ("s", "3")}
    result = product_counts(products, accepted, trace)
    assert result["retained_product_rows"] == 4
    assert result["recipe_candidate_rows"] == 2
    assert result["rejected_in_tested_paths_rows"] == 1
    assert result["not_demonstrated_rows"] == 1
    assert [r["product_rows"] for r in result["rejection_reasons"]] == [1, 1]
    trace.collect = False
    trace.event(products[2], None, "rice", "recipe_match", "stopped", "generic probe")
    assert ("s", "2") not in trace.reached


def test_blockers_count_unique_recipes_and_do_not_add_overlapping_gains():
    scopes = {"a1": {"group": "rice|dry|g"}, "a2": {"group": "rice|dry|g"},
              "b": {"group": "milk|as_sold|ml"}}
    rows = [{"id": "r1", "blocking_scope_ids": ["a1", "a2"]},
            {"id": "r2", "blocking_scope_ids": ["a1", "b"]},
            {"id": "r3", "blocking_scope_ids": []}]
    ranking = rank_blockers(rows, scopes)
    assert ranking[0]["blocked_recipes"] == 2
    assert ranking[0]["sole_input_blocker_recipes"] == 1
    assert ranking[1]["blocked_recipes"] == 1
    assert ranking[1]["sole_input_blocker_recipes"] == 0


def test_collector_ids_do_not_create_false_missing_recipe_suggestions():
    recipe = SimpleNamespace(ingredients=[SimpleNamespace(name="mjölk"), SimpleNamespace(name="ost")])
    names, used = gap_queries([("recipe", recipe)])
    assert {"mjölk", "ost"} <= names
    assert "cheese" not in names and "milk" not in names
    assert "mjölk" in used and "ost" in used


def report_fixture():
    scope = {key: value for key, value in (
        ("universe_sha256", "u"), ("facts_sha256", "f"), ("clock", "2026-10-23T00:00:00+00:00"),
        ("store_ids", ["s"]), ("max_stores", 2), ("servings", {"dinner": 4}), ("pantry", False),
        ("conditions", {"exact": {}, "estimated": {}}), ("imported_reference_ids_sha256", "ids"))}
    rows = [{"id": str(i), "base_id": "base-" + str(i), "original_import_id": "original-" + str(i), "blocking_scope_ids": [],
             "basket": "verified", "checkout": {"audit_passed": True, "store_count": 1, "evidence_sha256": "receipt"}}
            for i in range(2200)]
    rows[-1].update(basket="data_blocked", blocking_scope_ids=["missing"])
    data = {"products": {"retained_product_rows": 3, "recipe_candidate_rows": 1,
                         "rejected_in_tested_paths_rows": 1, "not_demonstrated_rows": 1},
            "recipes": rows, "all_recipes": recipe_totals(rows), "imported_recipes": recipe_totals(rows)}
    return {"schema": "smako-coverage-overview-v1", "status": "complete", "code_revision": "test",
            "scope": scope, "active_recipe_count": 2200, "imported_recipe_count": 2200,
            "modes": {"exact": deepcopy(data), "estimated": deepcopy(data)}}


def recount(report):
    for data in report["modes"].values():
        data.update(all_recipes=recipe_totals(data["recipes"]), imported_recipes=recipe_totals(data["recipes"]))


def test_same_coverage_count_cannot_hide_a_lost_original_recipe():
    report = report_fixture()
    previous = baseline(report)
    rows = report["modes"]["exact"]["recipes"]
    rows[0].update(basket="data_blocked", blocking_scope_ids=["new-missing"])
    rows[-1].update(basket="verified", blocking_scope_ids=[])
    recount(report)
    result = compare(report, previous)
    assert not result["passed"]
    assert result["regressions"]["exact"]["inputs_lost"] == ["original-0"]
    assert result["gains"]["exact"]["inputs"] == ["original-2199"]


def test_timeout_is_unknown_and_never_a_fast_success_or_proven_impossibility():
    report = report_fixture()
    previous = baseline(report)
    report["modes"]["estimated"]["recipes"][0].update(basket="search_incomplete", checkout={"seconds": 3})
    recount(report)
    result = compare(report, previous)
    assert result["passed"] and not result["fully_checked"]
    assert result["incomplete"]["estimated"] == ["original-0"]
    assert result["regressions"]["estimated"]["baskets_lost"] == []


@pytest.mark.parametrize("key", ["universe_sha256", "facts_sha256", "clock", "store_ids", "conditions", "max_stores", "servings"])
def test_reference_drift_requires_an_explicit_new_baseline(key):
    report = report_fixture()
    previous = baseline(report)
    report["scope"][key] = "changed"
    with pytest.raises(ValueError):
        compare(report, previous)


@pytest.mark.parametrize("change", ["denominator", "duplicate", "false_audit", "too_many_stores", "summary", "partial"])
def test_invalid_or_incomplete_report_cannot_pass_ci(change):
    report = report_fixture()
    data = report["modes"]["exact"]
    if change == "denominator":
        report["imported_recipe_count"] -= 1
    elif change == "duplicate":
        data["recipes"][0]["original_import_id"] = data["recipes"][1]["original_import_id"]
    elif change == "false_audit":
        data["recipes"][0]["checkout"]["audit_passed"] = False
    elif change == "too_many_stores":
        data["recipes"][0]["checkout"]["store_count"] = 3
    elif change == "summary":
        data["imported_recipes"]["inputs_resolved"] += 1
    else:
        report["status"] = "in_progress"
    with pytest.raises(ValueError):
        validate(report)


@pytest.mark.parametrize("damage", [None, "compressed_hash", "content_hash", "expansion", "size"])
def test_asset_hashes_and_bounded_expansion_preserve_previous_input(tmp_path, damage):
    payload = b'{"public": "reference"}'
    source, target = tmp_path / "reference.gz", tmp_path / "reference.json"
    source.write_bytes(gzip.compress(payload))
    original = tmp_path / "original.json"
    original.write_bytes(payload)
    spec = {"compressed_sha256": sha(source), "compressed_bytes": source.stat().st_size,
            "sha256": sha(original), "bytes": len(payload)}
    target.write_text("existing")
    if damage == "compressed_hash":
        spec["compressed_sha256"] = "wrong"
    elif damage == "content_hash":
        spec["sha256"] = "wrong"
    elif damage == "expansion":
        spec["bytes"] -= 1
    elif damage == "size":
        spec["bytes"] += 1
    if damage:
        with pytest.raises(ValueError):
            unpack(source, target, spec)
        assert target.read_text() == "existing"
    else:
        unpack(source, target, spec)
        assert json.loads(target.read_bytes()) == {"public": "reference"}


@pytest.mark.parametrize("document", [{"accounts": []}, {"facts_version": "x", "facts": [{"cookie": "private"}]},
                                      {"facts_version": "x", "facts": [], "unexpected": "raw"}])
def test_reference_packaging_rejects_private_or_unrelated_payloads(tmp_path, document):
    path = tmp_path / "input.json"
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError):
        review_projection(path, "facts")


@pytest.mark.parametrize("damage", [None, "duplicate", "wrong_index", "missing_edge", "wrong_breadth", "false_whole_recipe"])
def test_product_recipe_links_are_checked_against_actual_report_rows(tmp_path, damage):
    rows = [{"store_id": "s", "product_id": str(i), "status": status, "recipe_indexes": "0" if i == 0 else "",
             "recipe_variants": 1 if i == 0 else 0, "base_dishes": 1 if i == 0 else 0,
             "candidate_in_verified_recipe": "True" if i == 0 else "False"}
            for i, status in enumerate(["recipe_candidate", "rejected_in_tested_paths", "not_demonstrated"])]
    if damage == "duplicate":
        rows.append(rows[0])
    elif damage == "wrong_index":
        rows[0]["recipe_indexes"] = "2200"
    elif damage == "missing_edge":
        rows[0].update(recipe_indexes="", recipe_variants=0, base_dishes=0)
    elif damage == "wrong_breadth":
        rows[0]["base_dishes"] = 2
    elif damage == "false_whole_recipe":
        rows[0]["candidate_in_verified_recipe"] = "False"
    for mode in ("exact", "estimated"):
        with gzip.open(tmp_path / (mode + "-products.csv.gz"), "wt", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    if damage:
        with pytest.raises(ValueError):
            validate_product_details(report_fixture(), tmp_path)
    else:
        validate_product_details(report_fixture(), tmp_path)


def test_real_resolver_trace_is_not_limited_to_production_campaign_sample():
    from app.config import Settings
    from app.models import PlanRequest
    from app.services.personal_planner import PersonalPlanner

    from backend.tests.test_personal_planning_v2 import NOW, prepared, product, state
    products = [product("mjölk", 1000, "ml", 15, identity=str(i)) for i in range(270)]
    products.append(product("hundmat", 500, "g", 10, identity="dog"))
    frozen = prepared(*products)
    planner = PersonalPlanner(PlanRequest(recipes=1, personal={}), Settings(price_provider="mock"), frozen, state(), now=NOW)
    trace = CoverageTrace(frozen.universe.products)
    planner.product_trace = trace
    candidates = planner.resolve("mjölk", 200, "ml", profile=planner.spec.profile)
    accepted = {(c.store_id, c.product_id) for _, c in candidates}
    result = product_counts(frozen.universe.products, accepted, trace)
    assert result["recipe_candidate_rows"] == 270
    assert result["not_demonstrated_rows"] == 1
    assert result["rejected_in_tested_paths_rows"] == 0
    assert len(trace.reached) == 270
