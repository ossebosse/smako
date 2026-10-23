import json
import re
from collections import Counter
from pathlib import Path

from app.services.complete_recipes import _requirements_compatible, _whole_food_identity
from app.services.meal_prepared_artifacts import ingredient_search_positions
from app.services.official_product_facts import project_usable_quantity
from app.services.personal_policy import ProductFacts
from app.services.personal_source_facts import FactsCollection
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
from app.services.product_semantics import evaluate_product_semantics

out={}
for city in ("malmo","lund"):
    D=Path(f".local/fixes-review-20261018/data/{city}")
    prepared=PreparedPriceUniverseArtifact.model_validate_json((D/"combined-prices.json").read_bytes()).restore()
    raw=json.loads((D/"product-facts.json").read_bytes())
    facts=FactsCollection({(r["store_id"],r["product_id"]): ProductFacts(**r["facts"]) for r in raw["rows"]})
    stores={s.store_id:s for s in prepared.stores}
    cov=Counter((s.chain, s.coverage) for s in prepared.stores)
    rows=Counter(stores[p.store_id].coverage for p in prepared.universe.products if p.store_id in stores)
    print("==",city,"produkter",len(prepared.universe.products),"fakta",len(facts),"| butiker per täckning",dict(Counter(s.coverage for s in prepared.stores)),"| rader per täckning",dict(rows))
    print("   fullkatalog:",sorted({(s.chain,s.name) for s in prepared.stores if s.coverage!="offers_only"}))
    for can,req,pat in (("kvarg",("plain",),"kvarg"),("jordnötssmör",(),"jordnöts"),("ägg",("pack:egg",),"^ägg|^brunchägg")):
        pos=set(ingredient_search_positions(prepared,can,complete=True))
        c=Counter(); ex={}
        for i,p in enumerate(prepared.universe.products):
            if not re.search(pat,p.name.lower()): continue
            s=stores.get(p.store_id); f=facts.get((p.store_id,p.product_id))
            pp=project_usable_quantity(p,f,required_unit="g")
            k=(s.coverage if s else "?", i in pos, evaluate_product_semantics(can,p).compatible, _whole_food_identity(can,"as_sold" if can!="ägg" else "raw_edible",pp,f,req), _requirements_compatible(can,req,pp,f), bool(f), bool(f and f.ingredients))
            c[k]+=1; ex.setdefault(k,(p.name,s.name if s else ""))
        print("  ",can,": (täckning, i index, semantik, identitet, krav, fakta, ingredienslista)")
        for k,v in c.most_common(8): print("     ",v,k,ex[k])
    del prepared, facts, raw
