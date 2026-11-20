"""Qualify a candidate library's recipes against live prices, one recipe per week.

Owner decision 2026-11-20: every ingredient of a new recipe must have a buyable
product in Lund and Malmö before import. Run inside a throwaway container from
the app image with the app's environment and read-only data mounts, the
candidate library files copied into backend/app/data/recipes:

    python qualify_candidate_library.py UNIVERSE.json OUT.json VARIANT [PACK_ID]

Prints how many recipes qualified; OUT.json has the stop reason per recipe.
"""
import json, sys, types, time
from pathlib import Path
from app.services.meal_library_cli import _qualify_issued
from app.services.meal_library_content import manifest_entries
from app.services.recipe_library import current_recipes
issued = [r for r in current_recipes(len(manifest_entries()["current"])) if r.design.content_source and r.design.content_source.pack_id == (sys.argv[4] if len(sys.argv) > 4 else "smako-cheap-bases-20261119")]
variant = sys.argv[3]
recipes = [r for r in issued if r.design.variant_id == variant]
t=time.time()
from datetime import datetime, timezone
args = types.SimpleNamespace(clock=datetime.now(timezone.utc).isoformat(), universe=Path(sys.argv[1]), facts=None, purchase_mode="estimated", max_stores=2)
out = _qualify_issued(args, recipes)
Path(sys.argv[2]).write_text(json.dumps(out, ensure_ascii=False, indent=0))
print(sum(r["status"] == "qualified" for r in out["recipes"]), "/", len(out["recipes"]), round(time.time()-t), "s")
