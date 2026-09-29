import json
from pathlib import Path
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
from app.services.official_product_facts import declared_facts
from app.services.nutrition_reference import reference_evidence
pu=PreparedPriceUniverseArtifact.model_validate_json(Path('reports/purchase-planning-20260925/final/prepared-1281-second.json').read_bytes()).restore()
p=next(p for p in pu.universe.products if p.name=='Hushållsost')
print(p.model_dump(include={'name','brand','package_quantity','package_unit','usable_quantity','usable_unit','purchase_terms','offers'}))
print(declared_facts([p]));print(reference_evidence(580))
