"""Final code over the separately fetched current revision, both municipalities."""
import asyncio
import json
import runpy
from pathlib import Path

from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
from app.services.production_price_universe_build import build_city_price_universe
from grocery_data.scripts.collect_lidl_municipality import collect, retained_bundle

R=Path(__file__).resolve().parent


async def main():
    helpers=runpy.run_path(str(R/'verify_coverage.py'))
    bundle=retained_bundle(R/'lidl-live-source')
    for code,city,postal in [('1281','Lund','22223'),('1280','Malmö','21120')]:
        inv=json.loads((R/f'lidl-{code}/inventory.json').read_bytes())
        root=R/f'lidl-current-{code}'
        result=await collect(inv,inv['selected_store_ids'],root,bundle=bundle)
        assert all(s['own']==14 for s in result['stores'])
        output=root/'prepared.json'
        build=await build_city_price_universe(database=R/'empty-base.sqlite',city=city,postal_code=postal,
            external_cache=None,output=output,max_price_age_hours=48,lidl_municipal_enabled=True,
            lidl_sources=helpers['sources'](root))
        prepared=PreparedPriceUniverseArtifact.model_validate_json(output.read_bytes()).restore()
        rows=helpers['purchases'](prepared)
        (root/'verification.json').write_text(json.dumps({'build':build,'products':len(rows),'purchases':rows,
            'network_requests_in_replay':0,'source_observations_rewritten':False,'manual_approvals_inherited':False},
            ensure_ascii=False,indent=2,default=str),encoding='utf-8')
        print(code,len(rows),'current PU',flush=True)


if __name__=='__main__':asyncio.run(main())
