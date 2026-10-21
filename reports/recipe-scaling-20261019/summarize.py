"""Summarize acceptance-matrix reports: one row per process/iteration.

usage: summarize.py report.json [...] [--json out.json]
Spans are nested; never add them up. Times exclude artifact loading.
"""
import json
import statistics
import sys
from pathlib import Path

SPANS = ("personal_candidate_generation_and_qualification", "personal_week_search",
         "personal_package_calculation", "personal_nutrition")


def rows(path):
    report = json.loads(Path(path).read_bytes())
    for r in report["records"]:
        t = r["trace"]
        yield {
            "file": Path(path).name, "city": Path(path).resolve().parent.name, "case": report["case"], "label": report["label"],
            "limits": report["search_limits"], "iteration": r["iteration"], "mode": r["cache_mode"],
            "outcome": r["outcome"], "paid": r.get("paid"), "sha": (r.get("semantic_sha256") or "")[:12],
            "wall": round(r["wall_seconds"], 2), "cpu": round(r["cpu_seconds"], 2),
            **{s.removeprefix("personal_"): round(t["timings_ms"].get(s, 0) / 1000, 2) for s in SPANS},
            "baskets": t["operation_counters"].get("basket_calculations"),
            "peak_rss_mb": round((r.get("process_peak_rss_bytes") or 0) / 2**20),
            "load_s": round(report["load_seconds"], 1),
        }


def main():
    args = sys.argv[1:]
    out = None
    if "--json" in args:
        i = args.index("--json")
        out = args[i + 1]
        del args[i:i + 2]
    table = [row for path in args for row in rows(path)]
    keys = ["city", "label", "case", "mode", "outcome", "paid", "sha", "wall", "candidate_generation_and_qualification",
            "week_search", "baskets", "peak_rss_mb"]
    print(" | ".join(keys))
    for row in table:
        print(" | ".join(str(row[k]) for k in keys))
    warm = {}
    for row in table:
        if row["mode"] == "process-warm":
            warm.setdefault((row["city"], row["label"], row["case"]), []).append(row["wall"])
    for key, values in warm.items():
        print(key, "warm median", statistics.median(values), "n", len(values), "range", min(values), max(values))
    if out:
        Path(out).write_text(json.dumps(table, indent=1), encoding="utf8")


if __name__ == "__main__":
    main()
