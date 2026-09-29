"""Optional candidate runner: actual operation lock and scope guards."""
import json
import sys
from pathlib import Path

import pytest

from grocery_data.app.services.manual_refresh_operations import (
    RefreshRunLock,
    production_refresh_lock_path,
)
from grocery_data.scripts import collect_coop_release as runner

INVENTORY=Path(__file__).resolve().parents[2]/'reports/coop-municipality-20260921/acceptance/inventory/inventory.json'


def arguments(tmp_path):
    prod=tmp_path/'prod';prod.mkdir();database=prod/'grocery.sqlite';database.touch()
    universe=prod/'price-universes';universe.mkdir()
    return ['coop-release','--enabled','--inventory',str(INVENTORY),'--output',str(tmp_path/'candidate'),
            '--operation-database',str(database),'--operation-universe-root',str(universe)],database,universe


@pytest.mark.parametrize('fault',['disabled','unknown_store','production_output','existing_output'])
def test_scope_fails_before_any_source_request(tmp_path,monkeypatch,fault):
    args,db,_universe=arguments(tmp_path)
    if fault=='disabled':args.remove('--enabled')
    if fault=='unknown_store':args.extend(['--store-id','3658'])  # Xtra is separate.
    if fault=='production_output':args[args.index('--output')+1]=str(db.parent/'new')
    if fault=='existing_output':(tmp_path/'candidate').mkdir()
    async def no_fetch(*a):raise AssertionError('source request before scope validation')
    monkeypatch.setattr(runner,'collect',no_fetch);monkeypatch.setattr(sys,'argv',args)
    with pytest.raises(SystemExit):runner.main()


def test_existing_operation_lock_blocks_candidate_collection(tmp_path,monkeypatch):
    args,db,universe=arguments(tmp_path)
    async def no_fetch(*a):raise AssertionError('request while production operation locked')
    monkeypatch.setattr(runner,'collect',no_fetch);monkeypatch.setattr(sys,'argv',args)
    with RefreshRunLock(production_refresh_lock_path(db,universe)), pytest.raises(RuntimeError):
        runner.main()


def test_inventory_supplies_selection_and_release_guard_remains_off(tmp_path,monkeypatch):
    args,_db,universe=arguments(tmp_path);observed=[]
    async def collect(inventory,selected,output):
        observed.append(selected)
        return {'stores':[],'runtime_seconds':0}
    monkeypatch.setattr(runner,'collect',collect);monkeypatch.setattr(sys,'argv',args)
    runner.main()
    assert observed==[set(json.loads(INVENTORY.read_bytes())['selected_store_ids'])]
    assert not (universe/'active').exists()


def test_failed_source_returns_failure_without_activation(tmp_path,monkeypatch):
    args,_db,_universe=arguments(tmp_path)
    async def partial(*args):
        return {'stores':[{'status':'partial_candidate'},{'status':'failed'}], 'runtime_seconds':1}
    monkeypatch.setattr(runner,'collect',partial)
    monkeypatch.setattr(sys,'argv',args)
    with pytest.raises(SystemExit) as error:
        runner.main()
    assert error.value.code==1
