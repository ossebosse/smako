"""Preserve raw public probe evidence locally; publish bounded diagnostics."""
import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path


def main(args):
    data = args.input.read_bytes()
    report = json.loads(data)
    if "full_report_sha256" in report:
        return
    args.archive.mkdir(parents=True, exist_ok=True)
    raw = args.archive / args.input.name
    if raw.exists():
        assert raw.read_bytes() == data
    else:
        raw.write_bytes(data)
    result = {k: v for k, v in report.items() if k not in {"diagnostics", "error", "checks", "profile"}}
    result.update(full_report_sha256=hashlib.sha256(data).hexdigest(), full_report_bytes=len(data),
                  full_report_local_copy=raw.as_posix())
    checks = report.get("checks", {})
    error = report.get("error", {})
    diagnostic = checks.get("planning_diagnostics") or error.get("planning_diagnostics") or report.get("diagnostics", {})
    result["diagnostics"] = {k: v for k, v in diagnostic.items() if k not in {"candidate_details", "product_decisions", "missing_needs"}}
    reasons = Counter((r.get("stage"), r.get("reason")) for r in diagnostic.get("candidate_details", []))
    result["diagnostics"]["first_rejection_reasons"] = [
        {"stage": stage, "reason": reason, "count": count} for (stage, reason), count in reasons.most_common()]
    if checks:
        result["checks"] = {k: v for k, v in checks.items() if k not in {"planning_diagnostics", "ingredient_product_details"}}
    if error:
        result["error"] = {k: v for k, v in error.items() if k != "planning_diagnostics"}
    if "profile" in report:
        result["profile"] = {k: v for k, v in report["profile"].items() if k != "stacks"}
    budget = json.loads(args.budget.read_bytes())
    when = datetime.fromisoformat(report["started_at"])
    entry = max((e for e in budget["entries"] if e.get("started_at") and datetime.fromisoformat(e["started_at"]) <= when),
                key=lambda e: e["started_at"])
    result["budget_receipt"] = entry
    if report["status"] == "running" and entry["status"] == "deadline_exceeded":
        result.update(status="deadline_exceeded", valid_menu_delivered=False, user_deadline_seconds=75,
            completion_latency_seconds=None, observation="No completed response at the 75-second request stop. Progress diagnostics are partial.")
    elif report["status"] == "running" and entry["status"] != "running":
        result.update(status="probe_failed_before_delivery", valid_menu_delivered=False, completion_latency_seconds=None)
    args.input.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print({"file": args.input.name, "before_bytes": len(data), "after_bytes": args.input.stat().st_size, "status": result["status"]})


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--budget", type=Path, required=True)
    main(p.parse_args())
