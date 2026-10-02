"""Report real retained ingredient candidates and declarations, without patching."""
import json
from datetime import datetime
from pathlib import Path

from app.config import Settings
from app.models import PlanRequest
from app.models.personal import TasteProfile
from app.services.personal_planner import PersonalPlanner
from app.services.personal_source_facts import load_retained_facts
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
from app.services.product_search import ProductSearchRequest

prepared = PreparedPriceUniverseArtifact.model_validate_json(Path('/inputs/universe.json').read_bytes()).restore()
facts = load_retained_facts(prepared)
clock = datetime.fromisoformat(json.loads(Path('/inputs/freeze.json').read_text())['frozen_at_utc'])
request = PlanRequest(recipes=0, max_stores=2, personal={'meals': []})
planner = PersonalPlanner(request, Settings(price_provider='mock'), prepared,
                          {'revision': 0, 'items': [], 'reservations': {}, 'events': {}}, facts=facts, now=clock)
names = ['yoghurt naturell', 'yoghurt', 'fetaost', 'citronjuice', 'limejuice', 'gurka', 'zucchini', 'aubergine',
         'spenat', 'blomkål', 'champinjoner', 'haricots verts', 'senap', 'pepparrot', 'dill', 'persilja',
         'basilika', 'torkad oregano', 'oregano', 'paprikapulver', 'spiskummin', 'chilipulver', 'gurkmeja',
         'kanel', 'ingefära', 'jordnötssmör', 'sojasås', 'sesamfrön', 'ströbröd', 'havregryn', 'vetemjöl',
         'rapsolja', 'salt', 'potatis', 'kyckling', 'nötfärs', 'kikärtor', 'tofu', 'majs']
report = {}
for name in names:
    try:
        resolved = planner.resolve(name, 100, 'ml' if name == 'rapsolja' else 'g', profile=TasteProfile())
        resolution = {'count': len(resolved), 'first': [c.product_name for _, c in resolved[:8]]}
    except ValueError as exc:
        resolution = {'error': str(exc)}
    keys, _, _ = planner.index.retrieve(ProductSearchRequest(query=name))
    rows = []
    for i in dict.fromkeys(i for key in keys for i in planner.index.groups[key]):
        p = prepared.universe.products[i]
        f = planner.source_facts(p)
        rows.append({'id': p.product_id, 'store': p.store_id, 'name': p.name, 'brand': p.brand,
                     'quantity': p.usable_quantity, 'unit': p.usable_unit, 'category': p.category,
                     'confidence': str(p.semantic_confidence), 'price': p.price,
                     'facts': None if not f else {'nutrition': f.nutrition, 'unit': f.nutrition_unit,
                        'form': f.nutrition_preparation, 'ingredients': f.ingredients, 'conflicts': f.conflicts}})
    report[name] = {'resolution': resolution, 'products': rows[:60]}
out = Path('/results/ingredient-inventory.json')
out.write_text(json.dumps(report, ensure_ascii=False, indent=2))
print(json.dumps({k: v['resolution'] for k, v in report.items()}, ensure_ascii=False))
