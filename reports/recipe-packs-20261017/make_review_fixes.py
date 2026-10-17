"""Review follow-up: new versions that keep reviewed metadata, scale process water
and align names/labels with product requirements. Earlier versions stay issued."""
import json
import re
import sys

from app.services.meal_library_content import manifest_entries
from app.services.recipe_library import _registered_history, current_recipes

MINE = {"blocked-recipe-fixes-20261017", "basil-fixes-20261017"}
NEW = {"smako-new-recipes-20261017", "smako-cuisine-dinners-20261017"}
current = current_recipes(len(manifest_entries()["current"]))
history = _registered_history()
def ver(v): return tuple(map(int, v.split(".")))
def bump(v): a, b, _c = ver(v); return f"{a}.{b+1}.0"
out, log = [], []
for r in current:
    cs = r.design.content_source
    if not cs or cs.pack_id not in MINE | NEW:
        continue
    d = r.model_dump(mode="json", exclude={"preparation"})
    des = d["design"]; changes = []
    if cs.pack_id in MINE:
        # The version before the first fix carries the reviewed content source.
        older = [h for h in history if h.design.base_id == r.design.base_id
                 and h.design.variant_id == r.design.variant_id
                 and (not h.design.content_source or h.design.content_source.pack_id not in MINE)]
        original = max(older, key=lambda h: ver(h.design.version))
        ocs = original.design.content_source.model_dump(mode="json")
        # Carry the reviewed notes forward; validation binds the new version to
        # this pack (pack_id, proposal_id, source sha).
        des["content_source"] = {k: v for k, v in ocs.items() if k not in {"pack_id", "proposal_id", "sha256"}}
        changes.append(f"återställer granskad innehållskälla från {original.design.version} (säkerhetskällor, förvaring, metod- och skalningsnoter)")
        if original.design.active_minutes is None:
            des["active_minutes"] = ocs["active_minutes"]
            des["total_minutes"] = max(original.design.estimated_minutes, ocs["active_minutes"])
            des.pop("waiting_minutes", None)
            changes.append(f"aktiv tid {ocs['active_minutes']} min från innehållskällan i stället för den tidigare enda uppskattningen")
        notes = des["provenance"]["notes"]
        notes = re.sub(r" Aktiv och total tid sattes till den tidigare enda tidsuppskattningen \(aktiv tid är därmed en övre gräns\)\.", "", notes)
        des["provenance"]["notes"] = notes
    else:
        des.pop("content_source", None)
    for s in des["steps"]:
        m = list(re.finditer(r"(\d+(?:[,.]\d+)?) dl (vatten|dricksvatten)", s["text"]))
        for x in reversed(m):
            ml = round(float(x.group(1).replace(",", ".")) * 100)
            s["text"] = s["text"][:x.start()] + f"{ml} ml {x.group(2)}" + s["text"][x.end():]
        if m:
            amounts = [(t.group(0)[:-len(t.group(2))].rstrip(), float(t.group(1)))
                       for t in re.finditer(r"(\d+) ml (dricksvatten|vatten)", s["text"])]
            s["scalable_amounts"] = amounts
            changes.append("processvatten i ml som skalas med portionerna")
    if des["base_id"] == "smako-italian-weekday-meat-sauce":
        d["name"] = d["name"].replace("spaghetti", "kort pasta")
        for c in des["components"]:
            for a in c["amounts"]:
                if a["ingredient_key"] == "pasta|dry": a["name"] = "Kort pasta, torr (till exempel penne eller fusilli)"
        changes.append("namn och etikett: kort pasta, som pack:pasta tillåter (inte spaghetti)")
    if des["base_id"] == "smako-swedish-fish-gratin-mash":
        for c in des["components"]:
            for a in c["amounts"]:
                if a["ingredient_key"] == "fisk|raw_edible": a["name"] = "Torskfilé, rå"
        changes.append("etikett: torskfilé, som pack:cod tillåter (inte sej)")
    if not changes:
        continue
    d["instructions"] = [s["text"] for s in des["steps"]]
    des["content_sha256"] = "0" * 64
    des["version"] = bump(des["version"])
    des["provenance"]["reviewed_at"] = "2026-10-17"
    note = "Granskningsföljd 2026-10-17: " + "; ".join(dict.fromkeys(changes)) + "."
    des["provenance"]["notes"] = (des["provenance"]["notes"] + " " + note)[:4000]
    out.append(d); log.append((d["name"], des["version"], list(dict.fromkeys(changes))))
with open(sys.argv[1], "w", encoding="utf-8") as handle:
    json.dump({"schema_version": "smako-meal-pack-v1", "pack_id": "review-fixes-20261017", "recipes": out},
              handle, ensure_ascii=False, indent=1)
for row in log: print(row)
print(len(out), "recept")
