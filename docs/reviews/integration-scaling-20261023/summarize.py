"""Summarize completed pinned reports; missing measurements stay unknown."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from pathlib import Path

CASES = ("standard", "protein40", "all-macros", "vegan", "distribution",
         "organic-share", "breakfast-snack-weight")
CITIES = ("lund", "malmo")
SIZES = (262, 1000, 2000, 5000)
ARMS = ("main", "geo16", "geo32", "geo48")
SOURCE_COMMITS = {
    "f211cf4a197f0a7cf78b05a1026ea9309e2395e7a71dd14c7894f10044183b37": "c9390ddb9fbc362548a4b93261168b4764e44c16",
    "b84ccfab6c612e42a91ab5a79e2ccde4bebcfe310f9834c42fbf2d244a340bf9": "b139cd4630c03bc4e01f4c5c0ba0e7ead7e50314",
}


def read(path):
    if not path.exists():
        return None
    raw = path.read_bytes()
    report = json.loads(raw)
    report["report_sha256"] = hashlib.sha256(raw).hexdigest()
    return report


def outcome(row):
    return tuple(row.get(key) for key in ("outcome", "paid", "semantic_sha256", "code", "stage"))


def regression(current, baseline):
    if baseline["outcome"] == "PASS":
        if current["outcome"] != "PASS":
            return "lost a valid menu"
        if round(current["paid"], 2) > round(baseline["paid"], 2):
            return "dearer menu"
    elif current["outcome"] != "PASS" and (current.get("code"), current.get("stage")) != (baseline.get("code"), baseline.get("stage")):
        return "blocking reason changed; review required"
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    summary = {"schema": "smako-integration-scaling-review-v2", "default_merge_generations": False,
               "server_pairs": [], "grid_records": [], "grid_gates": {}, "missing": [],
               "reference262_comparisons": [], "resource_observations": {}}
    for city in CITIES:
        for case in CASES:
            reports = [read(args.evidence / "server-matrix" / f"{city}-{arm}-{case}.json") for arm in ("previous", "main")]
            row = {"city": city, "case": case, "complete": all(d and len(d["records"]) == 3 for d in reports)}
            if row["complete"]:
                before, after = reports
                row.update(same_inputs=before["inputs"] == after["inputs"],
                           same_results=all(outcome(x) == outcome(y) for x, y in zip(before["records"], after["records"], strict=True)),
                           inputs=after["inputs"], method_signature=after["method_signature"],
                           source_commit="2efb62f219b31fa6a81c16ba71363b4207cb2dfe", arms={})
                for arm, report in zip(("previous", "main"), reports, strict=True):
                    row["arms"][arm] = {"report_sha256": report["report_sha256"], "search_limits": report["search_limits"],
                                       "warm_median_seconds": statistics.median(r["wall_seconds"] for r in report["records"][1:]),
                                       "records": [{key: record.get(key) for key in (
                                           "outcome", "paid", "semantic_sha256", "code", "stage", "audit_passed",
                                           "wall_seconds", "cpu_seconds", "rss_bytes", "process_peak_rss_bytes",
                                           "cache_mode", "preparation_stats")} for record in report["records"]]}
            summary["server_pairs"].append(row)
    cells = {}
    for city in CITIES:
        for size in SIZES:
            for case in CASES:
                for arm in (*ARMS, *(("uncapped",) if size == 262 else ())):
                    path = args.evidence / "final-grid" / city / f"L{size}-{arm}-{case}.json"
                    report = read(path)
                    key = f"{city}/{size}/{case}/{arm}"
                    if not report or not report.get("records"):
                        summary["missing"].append(key)
                        continue
                    record = report["records"][-1]
                    cells[(city, size, case, arm)] = (record, report)
                    summary["grid_records"].append({"city": city, "size": size, "case": case, "arm": arm,
                        "source_commit": SOURCE_COMMITS.get(report.get("method_signature")),
                        **{key: report.get(key) for key in ("report_sha256", "method_signature", "library_version", "inputs", "search_limits", "reference_contract", "merged_search_contract", "execution_environment", "measurement_protocol")},
                        "result": {key: record.get(key) for key in ("outcome", "paid", "semantic_sha256", "code", "stage", "audit_passed", "wall_seconds", "cpu_seconds", "rss_bytes", "process_peak_rss_bytes", "cgroup_peak_bytes", "cache_mode", "preparation_stats")},
                        "timings_ms": record.get("trace", {}).get("timings_ms", {}),
                        "counters": record.get("trace", {}).get("operation_counters", {})})
    for city in CITIES:
        observations = [r for r in summary["grid_records"] if r["city"] == city]
        summary["resource_observations"][city] = {
            "completed_cells": len(observations),
            "process_peak_rss_bytes": max((r["result"].get("process_peak_rss_bytes") or 0 for r in observations), default=None),
            "cgroup_peak_bytes": max((r["result"].get("cgroup_peak_bytes") or 0 for r in observations), default=None) if city == "malmo" else None,
            "memory_limit_bytes": 3 * 1024 ** 3 if city == "malmo" else None,
            "cpu_limit": 2 if city == "malmo" else None,
            "protocol": "one observation per arm/case; process peaks include previous cases; no load-capacity claim",
        }
        for case in CASES:
            reference = cells.get((city, 262, case, "uncapped"))
            for arm in ARMS:
                current = cells.get((city, 262, case, arm))
                row = {"city": city, "case": case, "arm": arm, "complete": bool(current and reference)}
                if row["complete"]:
                    record, report = current
                    prior, prior_report = reference
                    assert report["inputs"] == prior_report["inputs"]
                    assert report["method_signature"] == prior_report["method_signature"]
                    assert report["library_version"] == prior_report["library_version"]
                    row.update(reason=regression(record, prior), paid=record.get("paid"), reference_paid=prior.get("paid"),
                               reference_contract=prior_report["reference_contract"],
                               reference_report_sha256=prior_report["report_sha256"])
                summary["reference262_comparisons"].append(row)
    for arm in ARMS[1:]:
        errors, missing = [], []
        for city in CITIES:
            for case in CASES:
                baseline = cells.get((city, 262, case, "main"))
                previous = None
                for size in SIZES:
                    current = cells.get((city, size, case, arm))
                    key = f"{city}/{size}/{case}"
                    if current is None or baseline is None:
                        missing.append(key)
                        continue
                    for comparison, target in (("main262", baseline), ("previous_size", previous)):
                        if target is None:
                            continue
                        record, report = current
                        prior, prior_report = target
                        reason = None
                        if report["inputs"] != prior_report["inputs"] or report["method_signature"] != prior_report["method_signature"]:
                            reason = "incompatible data or method signature"
                        else:
                            reason = regression(record, prior)
                        if reason:
                            errors.append({"cell": key, "comparison": comparison, "reason": reason,
                                           "paid": record.get("paid"), "comparison_paid": prior.get("paid")})
                    previous = current
        summary["grid_gates"][arm] = {"complete": not missing, "missing": missing, "regressions": errors,
                                      "eligible_as_default": not missing and not errors}
    summary["server_matrix_complete"] = all(row["complete"] for row in summary["server_pairs"])
    summary["grid_complete"] = not summary["missing"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print(json.dumps({"server_pairs": sum(r["complete"] for r in summary["server_pairs"]),
                      "grid_cells": len(summary["grid_records"]), "missing": len(summary["missing"])}))


if __name__ == "__main__":
    main()
