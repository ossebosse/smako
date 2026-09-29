"""Ordinary source-job recovery with immutable actual captures, no fake age."""
import asyncio
import json
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

from grocery_data.app.services import lidl_municipal_job as job
from grocery_data.scripts import collect_lidl_municipality as collector

R=Path(__file__).resolve().parent


async def main():
    root=R/'lidl-recovery-final';root.mkdir(exist_ok=False)
    before=R/'final/lidl-1281'; actual_collect=collector.collect;calls=[]
    env={'GROCERY_DATABASE_URL':'sqlite:///'+(R/'empty-base.sqlite').as_posix(),
         'LIDL_MUNICIPAL_ROOT':str(root),'LIDL_MUNICIPAL_ENABLED':'true','LIDL_MUNICIPALITY_CODE':'1281',
         'LIDL_MUNICIPAL_INVENTORY':str(before/'inventory.json')}
    async def first(inventory,selected,output):
        result=json.loads((before/'coverage.json').read_bytes())
        for row in result['stores']:
            p=output/row['database'];p.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(before/row['database'],p);row['resolved_database']=str(p)
        calls.append('immutable_qualified_OWN_replay');return result
    collector.collect=first
    now=datetime(2026,9,24,15,tzinfo=UTC);await job.run_source_job(environment=env,now=now)
    config=job.configuration(env)[1];path=job.location(root,config);state=job.read(path)
    old=state['approved']
    for row in state['selection']['stores']:
        if row['selected']:row['next_fetch_at']=(now-timedelta(seconds=1)).isoformat()
    job.write(path,state)
    async def failure(*args,**kwargs):
        calls.append('injected_fetch_failure');raise OSError('injected fetch failure')
    collector.collect=failure
    failed=await job.run_source_job(environment=env,now=now)
    assert job.read(path)['approved']==old
    bundle=collector.retained_bundle(R.parent/'offer-coverage-20260924/lidl-live-source')
    async def recovery(inventory,selected,output):
        calls.append('immutable_capture_requalified_by_final_collector');return await actual_collect(inventory,selected,output,bundle=bundle)
    collector.collect=recovery
    clock=now+timedelta(minutes=20)
    recovered=await job.run_source_job(environment=env,now=clock)
    final=job.read(path)
    assert all(row['own']==28 for row in final['last_outcomes'].values())
    expected={datetime.fromisoformat(row['observed_at']) for row in json.loads((before/'coverage.json').read_bytes())['stores']}
    assert {datetime.fromisoformat(ref['observed_at']) for refs in final['approved'].values() for ref in refs} == expected
    restarted={'GROCERY_DATABASE_URL':env['GROCERY_DATABASE_URL'],'LIDL_MUNICIPAL_ROOT':str(root)}
    idle=await job.run_source_job(environment=restarted,now=clock)
    assert idle['status']=='not_due' and len(calls)==3
    expired=job.source_inputs(city='Lund',environment=restarted,now=now+timedelta(days=5))
    (R/'lidl-recovery-verification.json').write_text(json.dumps({'failed':failed,'recovered':recovered,
        'idle_after_restart':idle,'expired_inputs':expired,'calls':calls,'external_price_requests':0,
        'clock':'retry advanced 20 minutes and expiry advanced 5 days; source observations unchanged',
        'new_revision_manual_approvals_inherited':False},ensure_ascii=False,indent=2,default=str),encoding='utf-8')


if __name__=='__main__':asyncio.run(main())
