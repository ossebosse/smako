import json
from app.services.recipe_library import current_recipes
from app.services.meal_library_content import manifest_entries
TARGET=("smako-thai-basil-tofu","smako-thai-sour-noodle-salad","smako-thai-chicken-coconut-curry")
NOTE=("x.2.0: basilika utan krav på färsk vara (pack:basil); fryst finhackad basilika med exakt vikt får användas. "
      "Krukbasilika har bara uppskattad vikt och den färska skurna basilikan i Lund har en faktakonflikt, så ingen basilika kunde köpas i exakt läge.")
out=[]
for r in current_recipes(len(manifest_entries()["current"])):
    if r.design.base_id not in TARGET or r.design.version.split(".")[0] != "2": continue
    d=r.model_dump(mode="json", exclude={"preparation"})
    d["design"].pop("content_source",None); d["design"]["content_sha256"]="0"*64
    a,b,c=map(int,d["design"]["version"].split(".")); d["design"]["version"]=f"{a}.{b+1}.0"
    for i in d["ingredients"]:
        if i["canonical_name"]=="basilika":
            i["product_requirements"]=[x for x in i.get("product_requirements") or [] if x!="pack:basil"]
            if not i["product_requirements"]: i.pop("product_requirements")
    for comp in d["design"]["components"]:
        for am in comp.get("amounts") or []:
            if am["ingredient_key"]=="basilika|raw_edible": am["name"]="Basilika, färsk eller fryst finhackad"
    for s in d["design"]["steps"]:
        if "basilika|raw_edible" in s["ingredient_keys"] and "basilika" in s["text"] and "fryst" not in s["text"]:
            s["text"]=s["text"].rstrip()+" Fryst finhackad basilika kan användas direkt."
            break
    d["instructions"]=[s["text"] for s in d["design"]["steps"]]
    d["design"]["provenance"]["reviewed_at"]="2026-10-17"
    d["design"]["provenance"]["notes"]=(d["design"]["provenance"]["notes"]+" "+NOTE)[:4000]
    out.append(d)
json.dump({"schema_version":"smako-meal-pack-v1","pack_id":"basil-fixes-20261017","recipes":out},open("/home/claude/recipes/basil-fixes-20261017.json","w"),ensure_ascii=False,indent=1)
print(len(out),[ (x["name"],x["design"]["version"]) for x in out])
