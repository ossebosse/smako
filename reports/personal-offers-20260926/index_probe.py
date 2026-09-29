"""Before/after frozen real artifact; price candidate discovery without nutrition facts."""
import json,sys
from pathlib import Path
from datetime import datetime
from app.config import Settings
from app.models import PlanRequest
from app.models.personal import TasteProfile
from app.services.personal_planner import PersonalPlanner
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
root=Path(__file__).resolve().parents[2]
p=PreparedPriceUniverseArtifact.model_validate_json((root/'reports/purchase-planning-20260925/final/prepared-1281-second.json').read_bytes()).restore()
r=PlanRequest.model_validate({'recipes':0,'purchase_planning_mode':'estimated','personal':{'meals':[],'slots':[]}})
e=PersonalPlanner(r,Settings(price_provider='mock'),p,{'revision':0,'items':[],'reservations':{},'events':{}},facts={},now=datetime.fromisoformat('2026-09-24T21:16:35.494010+00:00'))
result=e.resolve('ost',100,'g',profile=TasteProfile())
rows=[{'product_id':c.product_id,'name':c.product_name,'store_id':c.store_id,'usage':c.purchase_terms.usage if c.purchase_terms else None} for _,c in result]
(root/'reports/personal-offers-20260926'/('index-'+sys.argv[1]+'.json')).write_text(json.dumps({'facts_loaded':False,'candidate_rows':rows},ensure_ascii=False,indent=2),encoding='utf8')
print(sys.argv[1],len(rows),sum(r['name']=='Hushållsost' for r in rows))
