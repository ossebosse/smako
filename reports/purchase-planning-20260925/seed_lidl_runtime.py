"""Normal persistent source job with explicit immutable transport replay."""
import asyncio
import hashlib
import json
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

from grocery_data.app.services import lidl_municipal_job as job
from grocery_data.scripts import collect_lidl_municipality as collector

R=Path(__file__).resolve().parent


async def main():
    runtime=R/'runtime-1280'; source=R/'final/lidl-1280'
    calls=[]
    async def replay(inventory, selected, output):
        rows=[]
        for old in json.loads((source/'coverage.json').read_bytes())['stores']:
            if old['store_id'] not in selected:continue
            target=output/old['database'];target.parent.mkdir(parents=True,exist_ok=True)
            original=source/old['database'];shutil.copyfile(original,target)
            assert hashlib.sha256(original.read_bytes()).digest()==hashlib.sha256(target.read_bytes()).digest()
            rows.append({**old,'resolved_database':str(target),'verification_fetch_mode':'immutable_qualified_OWN_replay'})
        calls.append(sorted(selected));return {'stores':rows,'external_price_requests':0}
    collector.collect=replay
    env={'GROCERY_DATABASE_URL':'sqlite:///'+(runtime/'grocery.sqlite').as_posix(),
         'LIDL_MUNICIPAL_ROOT':str(runtime/'lidl'),'LIDL_MUNICIPAL_ENABLED':'true',
         'LIDL_MUNICIPALITY_CODE':'1280','LIDL_MUNICIPAL_INVENTORY':str(source/'inventory.json')}
    now=datetime(2026,9,24,15,tzinfo=UTC)
    first=await job.run_source_job(environment=env,now=now)
    state=job.read(job.location(runtime/'lidl',job.configuration(env)[1]))
    first_approved=state['approved']
    restarted={'GROCERY_DATABASE_URL':env['GROCERY_DATABASE_URL'],'LIDL_MUNICIPAL_ROOT':env['LIDL_MUNICIPAL_ROOT']}
    assert job.configuration(restarted)[1]['municipality_code']=='1280'
    second=await job.run_source_job(environment=restarted,now=now)
    assert second['status']=='not_due' and len(calls)==1
    # Genuine failure/expiry policy exercised against copies, never by moving
    # source observations. Future clock is isolated; source replay stays old.
    state_copy=json.loads(json.dumps(state));config=job.configuration(env)[1]
    async def fail(*args,**kwargs):raise OSError('injected offline fetch failure')
    collector.collect=fail
    future=now+timedelta(hours=36)
    failed=await job.run_source_job(environment=restarted,now=future)
    failed_state=job.read(job.location(runtime/'lidl',config))
    assert failed_state['approved']==first_approved
    expired_inputs=job.source_inputs(city='Malmö',environment=restarted,now=now+timedelta(days=5))
    # Restore the real-clock successful state; no stale replay becomes fresh.
    job.write(job.location(runtime/'lidl',config),state_copy)
    collector.collect=replay
    recovery=await job.run_source_job(environment=restarted,now=now)
    assert recovery['status']=='not_due'
    (R/'lidl-job-verification.json').write_text(json.dumps({'first':first,'second':second,
        'failure':failed,'expired_inputs':expired_inputs,'restored_real_clock':recovery,
        'recovery_scope':'valid retained state resumes after injected future-clock failure; no fresh fetch claimed',
        'external_price_requests':0,'observations_rewritten':False,'calls':calls},ensure_ascii=False,indent=2,default=str),encoding='utf-8')


if __name__=='__main__':asyncio.run(main())
