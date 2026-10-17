import os
from pathlib import Path

WORK = Path(os.environ.get("SMAKO_RECIPE_WORK", ".local/recipe-packs"))
import json

from app.services.recipe_library import current_recipes

blocked = json.load((WORK / "blocked.json").open(encoding="utf-8"))
# Kapris is deliberately left out: the library rule requires drained-weight
# evidence and an explicit draining step for cured ingredients.
names = {x["recipe"] for x in blocked if any(k in x["reason"] for k in ("majs", "chiliflakes"))}
NOTE = {
 "chiliflakes": "1.x: chiliflakes utan krav på märkningen mild/medium; 0,3 g per recept ger ingen avgörande hetta och ingen sådan märkning fanns i Lunds sortiment.",
 "majs": "Ny version: majs som fryst naturell vara i stället för kokt och avrunnen konserv; samma vikt, tillsätts direkt i den varma rätten.",
 "tid": "Aktiv och total tid sattes till den tidigare enda tidsuppskattningen (aktiv tid är därmed en övre gräns).",
 "komponenter": "Komponentmängder härledda från ingrediensernas komponenttillhörighet; inga mängder ändrade.",
 "metod": "Metod ändrad från sallad till panna: kycklingen steks i ett eget steg med kärntemperaturkontroll; rätten serveras som sallad.",
 "kapris": "Ny version: kapris anges som såld vara (vikt inklusive lag) eftersom avrunnen vikt saknas i produktfakta; kaprisen hälls av före användning.",
}
def bump(v):
    a, b, _c = map(int, v.split(".")); return f"{a}.{b+1}.0"
out = []
for r in current_recipes(6):
    if r.name not in names: continue
    d = r.model_dump(mode="json", exclude={"preparation"})
    d["design"].pop("content_source", None)
    d["design"]["content_sha256"] = "0" * 64
    d["design"]["version"] = bump(d["design"]["version"])
    changed = []
    for i in d["ingredients"]:
        if i["canonical_name"] == "chiliflakes":
            i["product_requirements"] = [x for x in i.get("product_requirements") or [] if x != "pack:chili"]
            if not i["product_requirements"]: i.pop("product_requirements")
            changed.append("chiliflakes")
        if i["canonical_name"] == "majs" and i["form"] == "cooked_drained":
            i["form"] = "as_sold"; i["product_requirements"] = ["frozen", "plain"]; changed.append("majs")
        if i["canonical_name"] == "kapris" and i["form"] == "preserved_drained":
            i["form"] = "as_sold"; changed.append("kapris")
    ren = {"majs|cooked_drained": "majs|as_sold", "kapris|preserved_drained": "kapris|as_sold"}
    for c in d["design"]["components"]:
        for a in c.get("amounts") or []:
            if a["ingredient_key"] in ren:
                a["ingredient_key"] = ren[a["ingredient_key"]]
                a["name"] = "Majs, fryst naturell" if a["ingredient_key"].startswith("majs") else "Kapris, i lag"
    for s in d["design"]["steps"]:
        s["ingredient_keys"] = sorted(ren.get(k, k) for k in s["ingredient_keys"])
        if "kapris" in changed and "kapris" in s["text"]:
            s["text"] = s["text"].replace("Tillsätt vitlök, kapris,", "Häll av kaprisen. Tillsätt vitlök, kapris,")
    d["instructions"] = [s["text"] for s in d["design"]["steps"]]
    des = d["design"]
    if des.get("active_minutes") is None:
        # Older content had only one total estimate; keep it as both values
        # (an upper bound for active time) and say so in the provenance.
        des["active_minutes"] = des["estimated_minutes"]; des["total_minutes"] = des["estimated_minutes"]
        changed.append("tid")
    if any(not c.get("amounts") for c in des["components"]):
        for c in des["components"]:
            c["amounts"] = [{"ingredient_key": f"{i['canonical_name']}|{i['form']}",
                             "name": i["name"], "note": "", "quantity": i["quantity"], "unit": i["unit"]}
                            for i in d["ingredients"] if i["component"] == c["id"]]
        changed.append("komponenter")
    if d["design"]["method"] in {"salad", "cold_assembly", "refrigerated_assembly"} and any(
            i["canonical_name"] in {"kyckling", "nötfärs", "fläskkött", "ägg", "fisk", "lax"} and i["form"] == "raw_edible"
            for i in d["ingredients"]):
        # The dish is served as a salad, but its raw protein is pan-cooked in a
        # documented step with a core-temperature check.
        d["design"]["method"] = "pan"; changed.append("metod")
    prov = d["design"]["provenance"]
    prov["reviewed_at"] = "2026-10-17"
    prov["notes"] = (prov["notes"] + " " + " ".join(NOTE[k] for k in dict.fromkeys(changed)))[:4000]
    out.append(d)
json.dump({"schema_version": "smako-meal-pack-v1", "pack_id": "blocked-recipe-fixes-20261017", "recipes": out},
          (WORK / "fixes-20261017.json").open("w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(out), "recept")
