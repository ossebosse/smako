"""Simulated deadline across real owned transport, thread and revision store."""
import time

import pytest
from app.api import personal, plan
from app.models import PlanResponse
from app.models.personal import ExtraNeed
from app.services import plan_jobs
from app.services.personal_planner import PersonalPlanner as RealPlanner
from fastapi.testclient import TestClient

from backend.tests.test_personal_planning_v2 import NOW, prepared, product, request, run
from backend.tests.test_privacy_erasure import _application


@pytest.fixture
def scenario(tmp_path, monkeypatch):
    application, _, settings = _application(tmp_path, price_provider='mock',library_search_policy='smako-current-library-v2')
    for module in (plan, personal):monkeypatch.setattr(module,'get_settings',lambda:settings)
    application.include_router(plan.router);application.include_router(personal.router);personal.install_handlers(application)
    p=prepared(product('mjölk',1000,'ml',10))
    req=request(extras=[ExtraNeed(query='mjölk',quantity=100,unit='ml',confirmed=True)])
    initial=run(p,req)
    async def build(*args):return initial
    monkeypatch.setattr(plan,'_run_admitted_plan',build)
    monkeypatch.setattr(personal.GLOBAL_PREPARED_PRICE_UNIVERSES,'get_for_request',lambda *a,**kw:p)
    clock=[0.0];calls=[]
    monkeypatch.setattr(plan_jobs,'monotonic',lambda:clock[0])
    class Planner:
        def __init__(self,r,s,p,private,**kwargs):self.args=r,s,p,private,kwargs
        def create(self,**kwargs):
            calls.append(plan_jobs._planning_deadline.get())
            r,s,p,private,extra=self.args
            return RealPlanner(r,s,p,private,facts={},now=NOW,**extra).create(**kwargs)
    monkeypatch.setattr(personal,'PersonalPlanner',Planner)
    with TestClient(application) as client:
        saved=client.post('/api/plans',json=req.model_dump(mode='json'))
        assert saved.status_code==201,saved.text
        saved=saved.json();state=client.get('/api/personal/state').json()
        mutation={'action':'recalculate','revision':saved['revision'],'pantry_revision':state['revision']}
        yield client,application,saved,mutation,clock,calls,Planner,settings


def completed(client,response):
    if response.status_code!=202:return response
    for _ in range(100):
        result=client.get(response.json()['status_url'])
        if result.status_code!=202:return result
        time.sleep(.01)
    pytest.fail('small simulated job did not finish')


@pytest.mark.parametrize('as_job',[False,True])
def test_deadline_is_carried_to_thread_and_stops_inner_work(scenario,monkeypatch,as_job):
    client,app,saved,mutation,clock,calls,Planner,_=scenario
    def overrun(self,**kwargs):
        calls.append(plan_jobs._planning_deadline.get());clock[0]=61
        plan_jobs.check_cancelled()
    monkeypatch.setattr(Planner,'create',overrun)
    headers={'Prefer':'respond-async','X-Request-ID':'deadline-change-job'} if as_job else {}
    result=completed(client,client.post('/api/personal/plans/'+saved['plan_id']+'/change',json=mutation,headers=headers))
    assert result.status_code==422,result.text
    assert result.json()['code']=='SEARCH_INCOMPLETE'
    assert calls==[60.0]
    assert client.get('/api/plans/'+saved['plan_id']).json()['revision']==1
    with TestClient(app) as stranger:
        assert stranger.post('/api/personal/plans/'+saved['plan_id']+'/change',json=mutation).status_code==404


def test_expired_storage_rolls_back_revision_and_mutation_receipt(scenario,monkeypatch):
    client,_app,saved,mutation,clock,_calls,_Planner,_=scenario
    dump=PlanResponse.model_dump_json
    def expire_after_serialization(self,*args,**kwargs):
        result=dump(self,*args,**kwargs);clock[0]=61;return result
    with monkeypatch.context() as patch:
        patch.setattr(PlanResponse,'model_dump_json',expire_after_serialization)
        result=client.post('/api/personal/plans/'+saved['plan_id']+'/change',json=mutation)
    assert result.status_code==422 and result.json()['code']=='SEARCH_INCOMPLETE'
    assert client.get('/api/plans/'+saved['plan_id']).json()['revision']==1
    clock[0]=0
    retry=client.post('/api/personal/plans/'+saved['plan_id']+'/change',json=mutation)
    assert retry.status_code==200,retry.text
    assert retry.json()['saved']['revision']==2


@pytest.mark.parametrize('as_job',[False,True])
def test_completed_late_commit_is_recoverable_and_retry_does_not_duplicate(scenario,monkeypatch,as_job):
    client,app,saved,mutation,clock,calls,_Planner,_=scenario
    store=app.state.plan_store;append=store.append
    def late_commit(**kwargs):
        result=append(**kwargs);clock[0]=61;return result
    headers={'Prefer':'respond-async','X-Request-ID':'late-change-commit'} if as_job else {}
    with monkeypatch.context() as patch:
        patch.setattr(store,'append',late_commit)
        result=completed(client,client.post('/api/personal/plans/'+saved['plan_id']+'/change',json=mutation,headers=headers))
    assert result.status_code==422,result.text
    assert result.json()['planning_diagnostics']['committed_revision']==2
    assert client.get('/api/plans/'+saved['plan_id']).json()['revision']==2
    clock[0]=0
    retry=client.post('/api/personal/plans/'+saved['plan_id']+'/change',json=mutation)
    assert retry.status_code==200 and retry.json()['saved']['revision']==2
    assert len(calls)==1


def test_legacy_has_no_new_deadline(scenario,monkeypatch):
    client,_app,saved,mutation,clock,calls,Planner,settings=scenario
    legacy=__import__('dataclasses').replace(settings,library_search_policy='legacy')
    for module in (plan,personal):monkeypatch.setattr(module,'get_settings',lambda:legacy)
    create=Planner.create
    def late(self,**kwargs):
        clock[0]=61
        return create(self,**kwargs)
    monkeypatch.setattr(Planner,'create',late)
    result=client.post('/api/personal/plans/'+saved['plan_id']+'/change',json=mutation)
    assert result.status_code==200,result.text
    assert calls==[None]
