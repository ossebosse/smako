"""Singleton qualification of authored recipes against the frozen Lund universe (exact mode)."""
import json, sys, time, socket, re
from datetime import datetime
from unittest.mock import patch
from collections import Counter
D="/home/claude/bundle/data/lund"
from app.config import Settings
from app.models import PlanRequest
from app.services.personal_planner import PersonalPlanner
from app.services.personal_policy import ProductFacts, PolicyConflict
from app.services.personal_source_facts import FactsCollection
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
from app.services.meal_library_content import validate_pack_bytes
prepared = PreparedPriceUniverseArtifact.model_validate_json(open(f"{D}/prepared-universe.json","rb").read()).restore()
raw=json.load(open(f"{D}/product-facts.json"))
facts=FactsCollection({(r["store_id"],r["product_id"]): ProductFacts(**r["facts"]) for r in raw["rows"]}); facts.version=raw["facts_version"]; del raw
settings=Settings(complete_recipes_enabled=True, price_provider="own")
now=datetime.fromisoformat("2026-10-16T18:12:49.613708+00:00")

def qualify(recipe, servings=None, max_stores=2, mode="exact"):
    mt=recipe.design.meal_types[0]; sv=servings or (4 if mt=="dinner" else 1)
    slot={"id":f"{mt}-1","day":1,"meal_type":mt,"recipe":recipe.model_dump(mode="json")}
    body={"postal_code":"22350","max_stores":max_stores,"recipes":1 if mt=="dinner" else 0,
          "recipe_preferences":{"mode":"complete"},"purchase_planning_mode":mode,
          "personal":{"allow_nutrition_estimates":True,"pantry_revision":0,
                      "meals":[{"meal_type":mt,"count":1,"servings":sv}],"slots":[slot]}}
    req=PlanRequest.model_validate(body)
    try:
        with patch.object(socket.socket,"connect",side_effect=AssertionError("net")):
            res=PersonalPlanner(req,settings,prepared,{"revision":0,"items":[],"reservations":{},"events":{}},facts=facts,now=now).create()
        return True, res.optimized_basket.total, None
    except PolicyConflict as e:
        return False, str(e)[:300], None

if __name__=="__main__":
    v=validate_pack_bytes(open(sys.argv[1],"rb").read(), label=sys.argv[1])
    if v["rejections"]:
        for r in v["rejections"]: print("AVVISAD", r)
    for r in v["recipes"]:
        t=time.perf_counter(); ok,info,st=qualify(r)
        print(("OK  " if ok else "NEJ ")+f"{r.design.meal_types[0]:9} {len(r.ingredients):2} ingr | {r.name} | {info} | {round(time.perf_counter()-t,1)}s", flush=True)
