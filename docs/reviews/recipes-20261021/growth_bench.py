import hashlib
import json
import socket
import sys
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

case=sys.argv[1]
D=__import__("os").environ["DATA"]
from app.config import Settings
from app.services.personal_planner import PersonalPlanner
from app.services.personal_policy import PolicyConflict, ProductFacts
from app.services.personal_source_facts import FactsCollection
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact

from backend.scripts.planner_acceptance_matrix import matrix_request

prepared=PreparedPriceUniverseArtifact.model_validate_json(Path(D,"prepared-universe.json").read_bytes()).restore()
raw=json.loads(Path(D,"product-facts.json").read_bytes())
facts=FactsCollection({(r["store_id"],r["product_id"]): ProductFacts(**r["facts"]) for r in raw["rows"]}); facts.version=raw["facts_version"]
base={'recipe_preferences': {'mode': 'complete'}, 'purchase_planning_mode': 'estimated','postal_code':'22350','max_stores':2,
      'allowed_store_ids':[s.store_id for s in prepared.stores]}
now=datetime.fromisoformat("2026-10-18T05:12:49.467392+00:00")
for run in sys.argv[2:] or ["kall"]:
    req=matrix_request(base, case)
    s=time.perf_counter()
    with patch.object(socket.socket,"connect",side_effect=AssertionError("net")):
        pl=PersonalPlanner(req,Settings(complete_recipes_enabled=True,price_provider="own"),prepared,{"revision":0,"items":[],"reservations":{},"events":{}},facts=facts,now=now)
        try:
            r=pl.create()
            v={"recipes":[x.model_dump(mode="json") for x in r.recipes],"basket":r.optimized_basket.model_dump(mode="json"),
               "nutrition":r.personal.checks.get("nutrition"),"audit":r.personal.checks["checkout_audit"],"alloc":[x.model_dump(mode="json") for x in r.personal.allocations]}
            out={"kr":r.optimized_basket.total,"digest":hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()[:16]}
        except PolicyConflict as e: out={"fel":e.code}
    out.update(case=case,run=run,s=round(time.perf_counter()-s,1),eco=round(pl.timings.get("ecological_search",0),1),nutr=round(pl.timings.get("nutrition",0),1),qual=round(pl.timings.get("candidate_generation_and_qualification",0),1),search=round(pl.timings.get("week_search",0),1))
    print(json.dumps(out),flush=True)
