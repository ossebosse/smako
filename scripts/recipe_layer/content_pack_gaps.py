"""Read-only retained-source investigation, not a collection or patch job."""
import json
import re
from pathlib import Path

from app.services.personal_source_facts import load_retained_facts
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact

prepared = PreparedPriceUniverseArtifact.model_validate_json(Path('/inputs/universe.json').read_bytes()).restore()
facts = load_retained_facts(prepared)
rows = []
for product in prepared.universe.products:
    if not re.search(r'chili|risoni|krithar|orzo|pita|majs|tonfisk|ägg|äpple', product.name, re.IGNORECASE):
        continue
    fact = facts.get((product.store_id, product.product_id))
    rows.append({'name': product.name, 'product': product.model_dump(mode='json'),
                 'facts': str(fact)})
Path('/results/content-gaps.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2))
print(json.dumps({'products': len(rows), 'names': sorted({r['name'] for r in rows})}, ensure_ascii=False))
