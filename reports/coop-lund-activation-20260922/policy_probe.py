"""Private packaged runtime probes. No activation or installed schedule."""
import asyncio
import hashlib
import importlib.metadata
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from grocery_data.app.services.coop_municipal_refresh import update_selection
from grocery_data.app.services.manual_refresh_operations import RefreshRunLock, production_refresh_lock_path

ROOT = Path('/work')


def xtra_smoke():
    from grocery_data.scripts.collect_coop_municipality import collect_xtra
    inventory = json.loads(Path('/evaluation/inventory.json').read_bytes())
    rows = [r for r in inventory['stores'] if r['geographic_evidence']['status'] == 'inside'
            and r['store']['source_fields']['concept'] == 'X:-tra']
    assert rows
    with RefreshRunLock(production_refresh_lock_path(
            Path('/srv/app/var/grocery/grocery_data.sqlite'), Path('/srv/app/var/price_universes'))):
        result, products = asyncio.run(collect_xtra(rows[0], inventory, ROOT/'xtra-smoke'))
    print(json.dumps({'status': result['status'], 'own': result['own'], 'pu': len(products)}))


def run():
    inventory = json.loads(Path('/evaluation/inventory.json').read_bytes())
    collection = json.loads((ROOT/'coop-live/coverage.json').read_bytes())
    outcomes = {}
    for row in collection['stores']:
        parsed = json.loads((ROOT/'coop-live/sources'/(row['store_id']+'-extracted.json')).read_bytes())
        outcomes[row['store_id']] = {**row, 'windows': [
            {k: o.get(k) for k in ['valid_from', 'valid_to']}
            for p in parsed['products'] for o in p['offers']]}
    xtra = json.loads((ROOT/'xtra-smoke/result.json').read_bytes())
    outcomes[xtra['store_id']] = xtra
    now = datetime.now(UTC)
    state = update_selection(inventory, outcomes, now=now)
    restored = update_selection(inventory, previous=state, now=now+timedelta(minutes=1))
    assert not restored['due_store_ids']
    assert restored['next_inventory_check'] == state['next_inventory_check']
    one = collection['stores'][0]['store_id']
    failed = update_selection(inventory, {one: {'status': 'failed'}}, previous=state, now=now)
    f = next(s for s in failed['stores'] if s['store_id'] == one)
    assert f['last_success'] == outcomes[one]['observed_at']
    assert f['next_fetch_at'] == (now+timedelta(minutes=15)).isoformat()
    (ROOT/'update-selection.json').write_text(json.dumps(state, ensure_ascii=False, indent=2))
    result = {'checked_at': now.isoformat(), 'production_activation': False,
              'dependencies': {x: importlib.metadata.version(x) for x in ['playwright','beautifulsoup4','soupsieve','PyMuPDF']},
              'municipality_code': state['municipality_code'], 'all_store_rows': len(state['stores']),
              'selected_stores': [s for s in state['stores'] if s['selected']],
              'restart_preserves_schedule': True, 'failed_fetch_retains_last_success': True,
              'failed_retry_minutes': 15, 'external_calls_for_policy': 0,
              'scheduled_in_production': False,
              'cli_sha256': hashlib.sha256(Path('/srv/app/grocery_data/__main__.py').read_bytes()).hexdigest()}
    (ROOT/'policy-result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps({k: v for k,v in result.items() if k != 'selected_stores'}))
