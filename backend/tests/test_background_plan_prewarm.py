from __future__ import annotations

import asyncio
from dataclasses import replace
from types import SimpleNamespace

import pytest
from app.config import Settings
from app.services import plan_prewarm
from app.services.planner_admission import PlannerAdmissionBusy, PlannerAdmissionController


def prepared(city, postal, version='v1'):
    return SimpleNamespace(universe=SimpleNamespace(universe_id=version,
        key=SimpleNamespace(scope_id=f'city:{city}', city=city, postal_codes=(postal,))))


def setup(runner, *universes):
    active = {p.universe.key.scope_id:p for p in universes}
    manager = SimpleNamespace(get_active=active.get)
    app = SimpleNamespace(state=SimpleNamespace(planner_admission=PlannerAdmissionController()))
    queue = plan_prewarm.BackgroundPlanPrewarm(app, manager=manager, runner=runner, delay=.001)
    settings = Settings(price_universe_prewarm_enabled=True, price_universe_prewarm_modes=('balanced',),
                        price_universe_prewarm_max_stores=(3,), price_universe_prewarm_servings=2)
    return queue, settings, active, app


@pytest.mark.asyncio
async def test_municipal_queue_replaces_old_versions_and_uses_local_postal_codes():
    seen=[]
    async def runner(settings, **kwargs):
        seen.append((settings.price_universe_city, settings.price_universe_prewarm_postal_code))
        return SimpleNamespace(status='complete', profiles_succeeded=1)
    lund, malmo = prepared('lund','22350'), prepared('malmo','21120')
    queue, settings, active, _app = setup(runner,lund,malmo)
    assert queue.enqueue(settings,lund)=='scheduled'
    assert queue.enqueue(settings,malmo)=='scheduled'
    newer=prepared('lund','22350','v2');active['city:lund']=newer
    queue.enqueue(settings,newer)
    assert seen==[]  # Scheduling never blocks readiness or atomic activation.
    await asyncio.wait_for(queue.task,2)
    assert seen==[('lund','22350'),('malmo','21120')]
    assert queue.completed=={'city:lund':'v2','city:malmo':'v1'}
    assert queue.enqueue(settings,newer)=='already_active'
    assert queue.enqueue(replace(settings,price_universe_prewarm_enabled=False),newer)=='disabled'
    await queue.close()


@pytest.mark.asyncio
async def test_background_waits_for_consumers_and_joins_worker_on_shutdown(monkeypatch):
    consumer_started, consumer_release = asyncio.Event(),asyncio.Event()
    background_started, background_release = asyncio.Event(),asyncio.Event()
    async def consumer():
        consumer_started.set();await consumer_release.wait()
    class Service:
        async def create_plan(self,request):
            background_started.set();await background_release.wait();return 'plan'
    monkeypatch.setattr(plan_prewarm,'_default_service_factory',lambda *_:Service())
    async def runner(settings, *,manager,service_factory):
        assert await service_factory(settings,manager).create_plan(None)=='plan'
        return SimpleNamespace(status='complete',profiles_succeeded=1)
    universe=prepared('lund','22350')
    queue,settings,_,app=setup(runner,universe)
    admission=app.state.planner_admission
    user=asyncio.create_task(admission.run('user',consumer))
    await asyncio.wait_for(consumer_started.wait(),2)
    queue.enqueue(settings,universe)
    await asyncio.sleep(.02)
    assert not background_started.is_set()
    stats=await admission.stats()
    assert stats.active==1 and stats.queued==0 and stats.rejected==0
    consumer_release.set();await user
    await asyncio.wait_for(background_started.wait(),2)
    closing=asyncio.create_task(queue.close())
    await asyncio.sleep(.02)
    assert not closing.done()
    assert (await admission.stats()).active==1
    background_release.set();await asyncio.wait_for(closing,2)
    assert (await admission.stats()).active==0


@pytest.mark.asyncio
async def test_busy_probe_does_not_join_or_reject_consumer_job():
    admission=PlannerAdmissionController(max_queued=0)
    started,release=asyncio.Event(),asyncio.Event()
    async def work():
        started.set();await release.wait()
    task=asyncio.create_task(admission.run('same-key',work))
    await asyncio.wait_for(started.wait(),2)
    before=await admission.stats()
    with pytest.raises(PlannerAdmissionBusy):
        await admission.run('same-key',work,only_if_idle=True)
    assert await admission.stats()==before
    release.set();await task


@pytest.mark.asyncio
async def test_failed_municipality_does_not_stop_next_and_stale_queue_is_skipped(caplog):
    seen=[]
    async def runner(settings, **kwargs):
        seen.append(settings.price_universe_city)
        if settings.price_universe_city=='lund':raise ValueError('private detail')
        return SimpleNamespace(status='complete',profiles_succeeded=1)
    lund,malmo,old=prepared('lund','22350'),prepared('malmo','21120'),prepared('old','12345')
    queue,settings,active,_=setup(runner,lund,malmo,old)
    for p in (lund,malmo,old):queue.enqueue(settings,p)
    del active['city:old']
    await asyncio.wait_for(queue.task,2)
    assert seen==['lund','malmo']
    assert queue.completed=={'city:malmo':'v1'}
    assert 'private detail' not in caplog.text
    assert 'ValueError' in caplog.text
    await queue.close()


@pytest.mark.asyncio
async def test_pending_municipalities_are_bounded_and_latest_replacement_is_allowed():
    async def runner(*args,**kwargs):raise AssertionError('must not start')
    queue,settings,_,_=setup(runner)
    for n in range(64):assert queue.enqueue(settings,prepared(str(n),'12345'))=='scheduled'
    assert queue.enqueue(settings,prepared('overflow','12345'))=='capacity_deferred'
    assert queue.enqueue(settings,prepared('0','12345','v2'))=='scheduled'
    assert len(queue.pending)==64
    await queue.close()

@pytest.mark.asyncio
async def test_startup_schedules_every_loaded_municipality_without_waiting(monkeypatch):
    from app import main
    values=(prepared('lund','22350'),prepared('malmo','21120'))
    settings=Settings(price_universe_prewarm_enabled=True)
    app=SimpleNamespace(state=SimpleNamespace())
    seen=[]
    monkeypatch.setattr(main,'get_settings',lambda:settings)
    monkeypatch.setattr(main,'load_configured_price_universe',lambda _:values[0])
    monkeypatch.setattr(main,'precompute_pricing_semantics',lambda *_:None)
    monkeypatch.setattr(main,'GLOBAL_PREPARED_PRICE_UNIVERSES',SimpleNamespace(active_universes=lambda:values))
    monkeypatch.setattr(plan_prewarm,'schedule_plan_prewarm',lambda application,policy,value:seen.append(value))
    async with main.lifespan(app):
        assert seen==list(values)
        assert app.state.planner_admission is not None


@pytest.mark.asyncio
async def test_reload_schedules_only_after_atomic_activation(monkeypatch):
    from app.services.beta_observability import reload_active_price_universe
    old,new=prepared('malmo','21120','v1'),prepared('malmo','21120','v2')
    active={'city:malmo':old}
    def activate(value):
        previous=active['city:malmo'];active['city:malmo']=value;return previous
    manager=SimpleNamespace(get_active=active.get,activate=activate)
    app=SimpleNamespace(state=SimpleNamespace())
    def schedule(application,settings,value,**kwargs):
        assert active['city:malmo'] is new
        assert application is app and value is new and kwargs['manager'] is manager
        return 'scheduled'
    monkeypatch.setattr(plan_prewarm,'schedule_plan_prewarm',schedule)
    result=await reload_active_price_universe(app,Settings(price_universe_prewarm_enabled=True),
        artifact_store_factory=lambda _:SimpleNamespace(resolve_active_artifact=lambda _:'artifact'),
        staging_manager_factory=lambda:SimpleNamespace(load_file_and_activate=lambda _:new),
        projection_builder=lambda *_a,**_k:SimpleNamespace(status='miss_filled'),active_manager=manager)
    assert result['plan_prewarm']=='scheduled' and result['changed']
