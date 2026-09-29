"""Both arms use the same complete source DB/cache; no local search projection."""
import asyncio
import json
from pathlib import Path

from app.services.production_price_universe_build import build_city_price_universe

ROOT=Path('/work')

def build_original_sources(output, store, products, include_coop):
    options={'coop_offer_database':ROOT/'coop-live/own.sqlite',
             'coop_municipality_inventory':json.loads(Path('/evaluation/inventory.json').read_bytes())} if include_coop else {}
    result=asyncio.run(build_city_price_universe(database=ROOT/'base-final/frozen-base.sqlite',city='Lund',
        postal_code='22350',external_cache=ROOT/'base-final/frozen-primat.json',output=output,
        max_price_age_hours=48,**options))
    if include_coop:
        assert result['coop_optional_setup_error'] is None, 'Coop source setup failed'
        diagnostic = result['provider_metrics']['exact_identity_bridge']['coop_municipality_offers']
        assert len(diagnostic) == len(options['coop_municipality_inventory']['selected_store_ids'])
        assert all(r['status'] == 'success' and r['accepted'] > 0 for r in diagnostic.values())
    output.with_suffix('.build.json').write_text(json.dumps(result,default=str,ensure_ascii=False,indent=2))
    return json.loads(json.dumps(result,default=str))
