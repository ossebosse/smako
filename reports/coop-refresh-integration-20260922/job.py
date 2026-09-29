"""Bounded jobs inside disposable server test runtime."""
import asyncio
import hashlib
import json
import os
import sqlite3
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path

ROOT=Path('/work')
PROD=Path('/srv/app/var')

def freeze():
    from grocery_data.app.services.manual_refresh_operations import RefreshRunLock,production_refresh_lock_path
    database=PROD/'grocery/grocery_data.sqlite';pu=PROD/'price_universes'
    root=ROOT/'base-final';root.mkdir(exist_ok=False)
    target=root/'frozen-base.sqlite';assert not target.exists()
    with RefreshRunLock(production_refresh_lock_path(database,pu)):
        with sqlite3.connect('file:'+str(database)+'?mode=ro',uri=True) as source:
            with sqlite3.connect(target) as destination:source.backup(destination)
        cache=pu/'external-provider-cache';manifest=json.loads((cache/'active/city-lund.json').read_bytes())
        data=(cache/manifest['artifact_file']).read_bytes()
        assert hashlib.sha256(data).hexdigest()==manifest['artifact_sha256']
        (root/'frozen-primat.json').write_bytes(data)
        db=sqlite3.connect('file:'+str(target)+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
        columns=[r[1] for r in db.execute('pragma table_info(catalog_snapshots)')]
        snapshots=[dict(r) for r in db.execute("select * from catalog_snapshots where is_active=1")]
        safe=[{k:v for k,v in r.items() if k in ['id','chain','scope_key','state','coverage','observed_at','promoted_at','created_at','product_count','parser_version']} for r in snapshots]
        report={'frozen_at':datetime.now(UTC).isoformat(),'database_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
                'database_tables':[r[0] for r in db.execute("select name from sqlite_master where type='table'")],
                'source_snapshots':safe,'snapshot_columns':columns,'primat':manifest,
                'production_manifest':json.loads((pu/'active/city-lund.json').read_bytes()),
                'production_manifest_sha256':hashlib.sha256((pu/'active/city-lund.json').read_bytes()).hexdigest(),
                'production_activation':False}
        (root/'frozen-base-manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
        print(json.dumps(report,ensure_ascii=False))

async def collect():
    from grocery_data.scripts.collect_coop_physical_offers import collect as collect_coop
    inventory=json.loads(Path('/evaluation/inventory.json').read_bytes())
    selected=set(inventory['selected_store_ids'])
    # Inventory-approved Coop/Stora only. No X:-tra fetch or dependencies.
    assert selected and all(r['geographic_evidence']['status']=='inside'
       and r['store']['source_fields']['concept'] in ['Coop','Stora Coop']
       for r in inventory['stores'] if r['store']['external_id'] in selected)
    result=await collect_coop(inventory,selected,ROOT/'coop-live')
    print(json.dumps({'stores':[{k:r.get(k) for k in ['store_id','status','own','quarantined','error_type','observed_at']} for r in result['stores']],'seconds':result['runtime_seconds']}))

async def probe():
    from grocery_data.app.connectors.coop.connector import CoopConnector
    inventory=json.loads(Path('/evaluation/inventory.json').read_bytes())
    store=next(r['store'] for r in inventory['stores'] if r['store']['external_id'] in inventory['selected_store_ids'])
    connector=CoopConnector();evidence={'store':store['external_id'],'path':store['source_fields']['store_page_path']}
    try:
        from grocery_data.app.domain import SourceStore
        await connector.fetch_offers(SourceStore.model_validate(store))
        evidence['result']='success'
    except Exception as exc:
        evidence['errors']=[]
        while exc:
            batch=getattr(exc,'partial_batch',None)
            evidence['errors'].append({'type':type(exc).__name__,'message':str(exc)[:250],
                'statuses':[d.http_status for d in batch.documents] if batch else []})
            exc=exc.__cause__
    finally:await connector.aclose()
    (ROOT/'server-offers-transport-probe.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2))
    print(json.dumps(evidence,ensure_ascii=False))

if __name__=='__main__':
    try:
        os.environ.update(ICA_FLYER_PAID_ENABLED='false',ICA_FLYER_VISUAL_COMMAND_JSON='',ICA_STRUCTURED_OFFERS_ENABLED='false')
        mode=sys.argv[1]
        if mode=='freeze':freeze()
        elif mode in {'initialize','prepare-raw','cycle-a','cycle-b','cycle-base','cycle-c','cycle-xtra','plan',
                      'cycle-fetch-failure','cycle-recovery','cycle-reload-failure','cycle-reload-recovery','cycle-xtra-off','cycle-withdrawal','cycle-final-recovery','cycle-final-plan','cycle-expiry'}:
            import lifecycle
            lifecycle.run(mode)
        elif mode=='final-checks':
            import final_checks
            final_checks.run()
        elif mode in {'collect-package','collect-package-smoke'}:
            from grocery_data.scripts.collect_coop_release import main
            sys.argv=['collect_coop_release','--enabled','--inventory','/evaluation/inventory.json',
                '--output','/work/coop-live' if mode=='collect-package' else '/work/coop-final-smoke','--operation-database','/srv/app/var/grocery/grocery_data.sqlite',
                '--operation-universe-root','/srv/app/var/price_universes']
            if mode=='collect-package-smoke':sys.argv.extend(['--store-id','3659'])
            main()
        elif mode=='collect':asyncio.run(collect())
        elif mode=='collect-browser':
            ROOT=ROOT/'browser';ROOT.mkdir(exist_ok=False)
            asyncio.run(collect())
        elif mode=='probe':asyncio.run(probe())
        elif mode=='xtra-smoke':
            import policy_probe
            policy_probe.xtra_smoke()
        elif mode=='policy':
            import policy_probe
            policy_probe.run()
        elif mode in {'build-baseline','build-coop'}:
            from normal_source_build import build_original_sources
            out=ROOT/'profile';out.mkdir(exist_ok=True)
            artifact=out/(mode.split('-')[1]+'-acceptance-source-universe.json')
            from grocery_data.app.services.manual_refresh_operations import RefreshRunLock, production_refresh_lock_path
            with RefreshRunLock(production_refresh_lock_path(PROD/'grocery/grocery_data.sqlite',PROD/'price_universes')):
                result=build_original_sources(artifact,None,[],mode=='build-coop')
            print(json.dumps({k:result[k] for k in ['status','stores','raw_products','coop_optional_setup_error']},default=str))
        elif mode=='recipe-proofs':
            import recipe_proofs
            recipe_proofs.run()
        elif mode=='publication':
            import publication
            publication.run()
        elif mode in {'baseline','coop','baseline-final','coop-final','baseline-acceptance','coop-acceptance'}:
            arm=mode.split('-')[0]
            sys.argv=['evaluate_http.py','--artifact','/work/profile/'+arm+'-acceptance-source-universe.json','--candidate','/work/unused.json',
                '--request','/evaluation/request.json','--output','/work/profile','--label',mode,
                '--arm',arm,'--expected-base-facts-version','paired']
            import evaluate_http
            evaluate_http.main()
        else:raise ValueError('unknown bounded job')
    except Exception as exc:
        print(json.dumps({'error':type(exc).__name__,'message':str(exc)[:400],
            'frames':[{'file':f.filename,'line':f.lineno,'function':f.name} for f in traceback.extract_tb(exc.__traceback__)]}),flush=True)
        raise SystemExit(1) from None
