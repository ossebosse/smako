"""Summarize final evidence without replacing original logs or source observations."""
from __future__ import annotations

import copy
import hashlib
import json
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tests():
    files = ["tests-checkout-final.xml", "tests-cache-final.xml", "tests-groups-final.xml",
             "tests-source-bridge.xml", "tests-release.xml", "tests-artifact-compatibility.xml"]
    cases = {}
    for name in files:
        for case in ET.parse(OUT / name).findall(".//testcase"):
            cases[(case.get("classname"), case.get("name"))] = (case, name)
    problems = [(key, name) for key, (case, name) in cases.items()
                if any(case.find(tag) is not None for tag in ("failure", "error", "skipped"))]
    assert not problems, problems
    root = ET.Element("testsuites")
    suite = ET.SubElement(root, "testsuite", name="latest-unique-final-evidence",
                          tests=str(len(cases)), failures="0", errors="0", skipped="0")
    for case, _ in cases.values():
        suite.append(copy.deepcopy(case))
    ET.ElementTree(root).write(OUT / "tests-verified.xml", encoding="utf-8", xml_declaration=True)
    result = {"status": "PASS", "unique_cases": len(cases), "inputs_in_precedence_order": files,
              "deduplication": "latest result by classname and complete parametrized test name",
              "missing_historical_lidl_fixture": "OPEN, excluded: test_reviewed_lidl_nutrition.py / reports/source-implementation-20260915/lidl_offer_adapter.py",
              "intermediate_failed_runs_preserved": True,
              "ruff": (OUT / "ruff-final.log").read_text(encoding="utf-8").strip(),
              "provenance": [{"classname": k[0], "name": k[1], "evidence": n}
                             for k, (_, n) in sorted(cases.items())]}
    write("tests-verified.json", result)
    return result


def profile():
    arms = {}
    optional_snapshots = set()
    for folder in (ROOT / "reports/offer-expansion-20260924/willys-final-v2-1281",
                   ROOT / "reports/offer-expansion-20260924/lidl-v2-1281",
                   OUT / "final/willys-1281", OUT / "final/lidl-1281"):
        optional_snapshots.update(s["snapshot_id"] for s in read(folder / "coverage.json")["stores"]
                                  if s["status"] == "success")
    for arm in ("before", "after"):
        build = read(OUT / "profile" / f"{arm}-build.json")
        artifact = read(OUT / "profile" / f"{arm}-universe.json")
        required = set(read(OUT / "required-contexts.json"))
        contexts = {s["store_id"] for s in artifact["stores"]}
        assert required <= contexts
        modes = {}
        for mode in ("exact", "estimated"):
            label = f"{arm}-{mode}"
            result = read(OUT / "profile" / f"{label}-restored-original.json")
            inputs = read(OUT / "profile" / f"{label}-inputs.json")
            plan = read(OUT / "profile" / f"{label}-restored-original-plan.json")
            assert result["status"] == "PASS" and result["portions"] == 20 and result["slots"] == 15
            assert result["store_count"] <= 2 and result["active_manifest_unchanged"]
            basket = plan["optimized_basket"]
            modes[mode] = {k: result[k] for k in ("status", "cost", "verification", "portions", "slots", "store_count", "seconds")}
            modes[mode].update({
                "freshness_at_test_clock": inputs["status_at_test_clock"],
                "selected": [{"store": s["store_name"], "product": i["product_name"],
                              "cost": i["total_price"], "quantity_confidence": i.get("quantity_confidence"),
                              "warning": i.get("purchase_warning")}
                             for s in basket["stores"] for i in s["items"]],
                "request": result["request"],
            })
        oldest = datetime.fromisoformat(artifact["oldest_observed_at"].replace("Z", "+00:00"))
        arms[arm] = {"modes": modes, "required_base_contexts_present": True,
                     "contexts": sorted(contexts), "base_snapshot_ids": sorted(s for s in build["snapshot_ids"]
                         if s not in optional_snapshots),
                     "artifact_sha256": digest(OUT / "profile" / f"{arm}-universe.json"),
                     "network_attempts": build["network_attempts"],
                     "database_unchanged": build["database_unchanged"],
                     "external_cache_unchanged": build["external_cache_unchanged"],
                     "oldest_observed_at": oldest.isoformat(),
                     "oldest_age_hours_now": (datetime.now(UTC) - oldest).total_seconds() / 3600}
    requests = [arm["modes"][mode]["request"] for arm in arms.values() for mode in ("exact", "estimated")]
    standard = [{k: v for k, v in req.items() if k != "purchase_planning_mode"} for req in requests]
    assert all(req == standard[0] for req in standard)
    assert arms["before"]["base_snapshot_ids"] == arms["after"]["base_snapshot_ids"]
    assert arms["before"]["contexts"] == arms["after"]["contexts"]
    result = {"status": "PASS", "production_activation": False,
              "comparison": "same immutable complete base/cache, frozen purchase date and unchanged request; old/new source-qualified optional offers, final code in both arms",
              "clock": "2026-09-24T21:16:35.494010+00:00",
              "execution": "private native scheduler-image container, read-only code/root, network none, actual PersonalPlanner, not production HTTP endpoint",
              "intermediate_eight_context_runs": "not accepted as complete-base proof; federated clock was not frozen and omitted an aged required ICA context",
              "arms": arms}
    write("profile-summary.json", result)
    return result


def package():
    paths = []
    for folder in ("backend/app", "grocery_data/app", "grocery_data/scripts", "deploy/scripts"):
        paths.extend(p for p in (ROOT / folder).rglob("*")
                     if p.is_file() and "__pycache__" not in p.parts and p.suffix in {".py", ".json", ".js", ".html", ".css"})
    previous = ROOT / "reports/offer-expansion-20260924/PACKAGE.json"
    evidence = [p for p in OUT.iterdir() if p.is_file() and p.name in {
        "README.md", "RELEASE.md", "BLOCKERS.md", "VERIFICATION.md", "comparison.json", "willys-denominator.json",
        "lidl-denominator.json", "STORES.md", "STORES.json", "tests-verified.json", "tests-verified.xml", "profile-summary.json",
        "lidl-recovery-verification.json", "arla-purchase-and-nutrition.json", "runtime_verify.py", "profile_job.py", "remote_profile.py"}]
    evidence += list((OUT / "sources").glob("*"))
    evidence += [OUT / "runtime-1280/ACCEPTANCE.json", OUT / "quality-final.json",
                 OUT / "next-source-checks.json", OUT / "previous-release-preserved.json",
                 ROOT / "docs/purchase-planning.md", ROOT / "docs/HANDOFF.md"]
    runtime = read(OUT / "runtime-1280/ACCEPTANCE.json")
    for path, expected in runtime["final_code_hashes"].items():
        assert digest(ROOT / path) == expected, path
    test_files = {ROOT / (r["classname"].replace(".", "/") + ".py")
                  for r in read(OUT / "tests-verified.json")["provenance"]}
    test_files = {p for p in test_files if p.is_file()}
    write("PACKAGE.json", {
        "created_at": datetime.now(UTC).isoformat(), "status": "verified_shared_planning_partial_source_coverage",
        "production_activation": False, "previous_release": previous.relative_to(ROOT).as_posix(),
        "previous_package_sha256": digest(previous), "baseline_hashes": read(OUT / "baseline.json"),
        "hash_scope": "dependency closure of current preserved worktree, not a claim that every listed file changed in this stage",
        "code_and_data_hashes": {p.relative_to(ROOT).as_posix(): digest(p) for p in sorted(set(paths))},
        "test_code_hashes": {p.relative_to(ROOT).as_posix(): digest(p) for p in sorted(test_files)},
        "evidence_hashes": {p.relative_to(ROOT).as_posix(): digest(p) for p in sorted(evidence)},
        "runtime_final_code_hashes_verified": True,
        "new_price_network_requests": 0, "new_official_nutrition_requests": 5,
        "open": ["current fresh complete base before any publication", "full current complete-base Malmo integration",
                 "historical missing Lidl fixture", "independent unseen real campaign holdout", "source blockers retained in BLOCKERS.md"],
    })


if __name__ == "__main__":
    import sys
    action = sys.argv[1]
    result = {"tests": tests, "profile": profile, "package": package}[action]()
    print(action, "PASS", result.get("unique_cases", "") if result else "")
