import json

from grocery_data.app.services.ica_offer_job import run_optional_candidate_job


async def test_disabled_job_does_nothing_and_failure_recovers_without_changing_base(tmp_path):
    root=tmp_path/'candidates'
    assert (await run_optional_candidate_job(enabled=False,city='Malmö',root=root))['status']=='disabled'
    assert not root.exists()
    fail=False

    async def collect(area, output, **kwargs):
        output.mkdir()
        if fail:
            raise OSError('fixture transport failure')
        assert area.city=='Malmö' and kwargs['row_approved_offers'] is True
        return {'inventory':{'complete':True},'stores':[{
            'ica_account_id':'fixture-official','area_membership':'inside',
            'area_reason':'official_address_locality_matches_existing_area',
            'row_approved_result':{'published':True}}]}

    def extract(*args, **kwargs):
        return {'observations':[],'complete':False}

    first=await run_optional_candidate_job(enabled=True,city='Malmö',root=root,collect=collect,extract=extract)
    assert first['candidate_pointer_updated'] and not first['production_activation']
    pointer=root/'malmö/latest-candidate.json';previous=pointer.read_bytes()
    fail=True
    failed=await run_optional_candidate_job(enabled=True,city='Malmö',root=root,collect=collect,extract=extract)
    assert failed['status']=='failed_candidate_lkg_retained' and pointer.read_bytes()==previous
    fail=False
    recovered=await run_optional_candidate_job(enabled=True,city='Malmö',root=root,collect=collect,extract=extract)
    assert recovered['candidate_pointer_updated'] and pointer.read_bytes()!=previous
    assert json.loads(pointer.read_bytes())['proposal']['ica_offer_store_ids']==['fixture-official']


async def test_optional_startup_filesystem_failure_is_reported_not_raised(tmp_path):
    root=tmp_path/'existing-file';root.write_text('preserve')
    result=await run_optional_candidate_job(enabled=True,city='Lund',root=root)
    assert result['status']=='failed_candidate_lkg_retained' and result['phase']=='startup'
    assert root.read_text()=='preserve'


async def test_structured_job_restarts_without_calls_until_due_and_preserves_other_sources(tmp_path):
    from datetime import UTC, datetime, timedelta
    from grocery_data.app.services.ica_offer_job import run_structured_offer_job, structured_source_inputs
    calls=[]
    now=datetime(2026,9,20,8,tzinfo=UTC)
    async def collect(area, output, **kwargs):
        calls.append(kwargs)
        assert not kwargs['collect_flyers'] and not kwargs['discover_flyers']
        return {'inventory':{'complete':True},'stores':[{
            'ica_account_id':'official-1','area_membership':'inside','collection_status':'success',
            'area_reason':'official_address_locality_matches_existing_area',
            'last_success_at':now.isoformat(), 'campaign_windows':[{'valid_from':None,'valid_to':'2026-09-20'}],
            'row_approved_result':{'published':True, 'acceptance':{'shared_blockers':[]}}}]}
    first=await run_structured_offer_job(city='Lund',root=tmp_path,now=now,collect=collect)
    assert first['ica_offer_store_ids']==['official-1']
    assert structured_source_inputs(city='Lund',root=tmp_path)['ica_offer_store_ids']==frozenset(['official-1'])
    # Another invocation reads durable due times; no in-memory scheduler needed.
    second=await run_structured_offer_job(city='Lund',root=tmp_path,now=now+timedelta(hours=1),collect=collect)
    assert second['status']=='not_due' and len(calls)==1 and second['network_requests']==0
    assert second['database']==first['database']
    assert second['observed_at']==first['observed_at']


async def test_structured_store_failure_is_retained_and_schedules_retry_after_restart(tmp_path):
    from datetime import UTC, datetime, timedelta
    from grocery_data.app.services.ica_offer_job import run_structured_offer_job
    now=datetime(2026,9,20,8,tzinfo=UTC)
    fail=False
    async def collect(area,output,**kwargs):
        return {'inventory':{'complete':True},'stores':[{
            'ica_account_id':'official','area_membership':'inside','area_reason':'official_address_locality_matches_existing_area',
            'collection_status':'error' if fail else 'success',
            'last_success_at':None if fail else now.isoformat(), 'campaign_windows':[] if fail else [{'valid_to':'2026-09-20'}],
            'row_approved_result':None if fail else {'published':True}}]}
    first=await run_structured_offer_job(city='Lund',root=tmp_path,now=now,collect=collect)
    fail=True
    failed=await run_structured_offer_job(city='Lund',root=tmp_path,now=now+timedelta(hours=1),force=True,collect=collect)
    assert failed['ica_offer_store_ids']==['official'] and failed['excluded_store_ids']==[]
    schedule=failed['store_schedule']['official']
    assert schedule['last_success_at']==first['store_schedule']['official']['last_success_at']
    assert schedule['failed_attempts']==1 and schedule['reason']=='bounded_failure_retry'
    assert datetime.fromisoformat(schedule['next_fetch_at'])==now+timedelta(hours=1,minutes=15)
    assert (await run_structured_offer_job(city='Lund',root=tmp_path,now=now+timedelta(hours=1,minutes=5),collect=collect))['status']=='not_due'
