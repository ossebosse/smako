"""Read-only inventory of the independently published artifact, no price fetching."""
import json
from datetime import datetime, UTC
from pathlib import Path
from collections import Counter
from grocery_data.app.services.prepared_universe_activation import PreparedUniverseArtifactStore
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
root = Path('/work/physical-probe')
path = PreparedUniverseArtifactStore(root/'price-universes').resolve_active_artifact('Lund', verify_hash=True)
artifact = PreparedPriceUniverseArtifact.model_validate_json(path.read_bytes())
today = datetime.now(UTC).date()
offers = []
for p in artifact.universe.products:
    if not p.offers or not p.source_provenance or p.source_provenance.source_channel != 'offers':
        continue
    offers.append(p.model_dump(mode='json'))
result = {'scope':'Actual separately published OWN-only artifact, not complete Lund', 'observed_inventory_at':datetime.now(UTC).isoformat(), 'source_artifact':path.name, 'offer_products':offers, 'counts_by_chain':dict(Counter(p['chain'] for p in offers))}
(root/'served-offer-inventory.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
for p in artifact.universe.products:
    active = [o for o in p.offers if o.is_active(today) and o.required_packages > 1]
    if active and p.source_provenance and p.source_provenance.source_channel == 'offers':
        print(json.dumps({'id':p.product_id,'name':p.name,'store':p.store_id,'chain':p.chain,'package_quantity':p.package_quantity,'package_unit':p.package_unit,'usage':p.purchase_terms.usage if p.purchase_terms else None,'groups':[(o.price,o.required_packages) for o in active]},ensure_ascii=False))
