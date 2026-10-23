import json
import sys
from pathlib import Path

print("| set | label | it | paid | hash | wall | qual | week | baskets | pkgcalc | peakMB |")
for f in sorted(Path(sys.argv[1]).glob("*/*.json")):
    d = json.loads(f.read_bytes())
    if "records" not in d:
        continue
    for r in d["records"]:
        t = r["trace"]["timings_ms"]
        c = r["trace"].get("operation_counters", {})
        peak = r.get("process_peak_rss_bytes") or 0
        print(f"| {f.parent.name} | {d['label']} | {r['iteration']} | {r.get('paid')} | {(r.get('semantic_sha256') or '')[:10]} | "
              f"{r['wall_seconds']:.1f} | {t.get('personal_candidate_generation_and_qualification', 0)/1000:.1f} | "
              f"{t.get('personal_week_search', 0)/1000:.1f} | {c.get('basket_calculations')} | {c.get('package_calculations')} | {peak/1e6:.0f} |")
