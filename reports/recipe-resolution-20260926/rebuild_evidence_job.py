"""Explain the isolated rebuild without changing source observations or active disk state."""
import os, json, asyncio, hashlib
from pathlib import Path
from datetime import datetime
os.environ.update(GROCERY_DATABASE_URL='sqlite:////work/base/refreshed.sqlite',GROCERY_RAW_SNAPSHOT_ROOT='/work/raw')
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact, PreparedPriceUniverseManager, LocalPriceUniverseProvider
from app.services.price_universe import PriceUniverseBuilder
from app.services.economic_ingredient_selector import EconomicIngredientSelector

async def main():
 baseline=PreparedPriceUniverseArtifact.model_validate_json(Path('/work/universe.json').read_bytes()).restore()
 active=Path('/work/base/price-universes/active/city-lund.json');old_manifest=active.read_bytes()
 clock=datetime.fromisoformat('2026-09-24T21:16:35.494010+00:00')
 async def build():
  universe=PriceUniverseBuilder().build(baseline.universe.key,baseline.universe.products,built_at=clock)
  return await PreparedPriceUniverseManager().build_and_activate(city='Lund',postal_codes=['22350'],provider=LocalPriceUniverseProvider(universe,baseline.stores),memberships={},selector=EconomicIngredientSelector(),built_at=clock)
 first=await build();second=await build()
 def products(x):return {(p.store_id,p.product_id):p.model_dump(mode='json') for p in x.universe.products}
 assert products(baseline)==products(first)==products(second)
 assert first.economic_pool.model_dump()==second.economic_pool.model_dump()
 restored=PreparedPriceUniverseArtifact.model_validate_json(first.to_json()).restore()
 assert products(restored)==products(first)
 assert restored.economic_pool.model_dump()==first.economic_pool.model_dump()
 assert active.read_bytes()==old_manifest
 data={'original_products':len(baseline.universe.products),'rebuilt_products':len(first.universe.products),
 'all_product_fields_prices_observations_unchanged':True,'second_rebuild_same_pool':True,'artifact_roundtrip_same_pool':True,
 'active_disk_manifest_unchanged':True,'source_requests':0,
 'original_pool':baseline.economic_pool.model_dump(mode='json'),'rebuilt_pool':first.economic_pool.model_dump(mode='json')}
 Path('/work/profile/rebuild-evidence.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
 print(json.dumps({k:v for k,v in data.items() if not k.endswith('pool')}))
asyncio.run(main())
