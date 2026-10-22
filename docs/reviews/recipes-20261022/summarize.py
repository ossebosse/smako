"""Summarise planner_acceptance_matrix outputs: one row per city/version/case/iteration."""
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
print("| Stad | Ver | Profil | It | Utfall | kr | Vägg s | Kval s | Veckosök s | Korgberäkn. | Recept |")
print("| --- | --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |")
for f in sorted(root.glob("*/*.json")):
    if "-prepared" in f.parts[-1]:
        continue
    d = json.loads(f.read_bytes())
    if "records" not in d:
        continue
    city = f.parent.name
    for r in d["records"]:
        t = r["trace"]["timings_ms"]
        c = r["trace"].get("operation_counters", {})
        paid = f"{r['paid']:.2f}" if r.get("paid") is not None else r.get("code", "")
        print(f"| {city} | {d['label']} | {d['case']} | {r['iteration']} | {r['outcome']} | {paid} | "
              f"{r['wall_seconds']:.1f} | {t.get('personal_candidate_generation_and_qualification', 0)/1000:.1f} | "
              f"{t.get('personal_week_search', 0)/1000:.1f} | {c.get('basket_calculations', '')} | "
              f"{r.get('distinct_recipes', '')} |")
