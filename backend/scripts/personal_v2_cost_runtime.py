"""Offline image acceptance against mounted retained production artifacts."""

import json
import time
from copy import deepcopy
from pathlib import Path

from app.config import get_settings
from app.models import PlanRequest
from app.services.personal_planner import PersonalPlanner
from app.services.personal_policy import PolicyConflict
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact

root = Path('/srv/app/var/price_universes')
manifest = json.loads((root / 'active/city-lund.json').read_bytes())
prepared = PreparedPriceUniverseArtifact.model_validate_json((root / manifest['artifact_file']).read_bytes()).restore()
cases = json.loads(Path('/evidence/predeclared-inputs.json').read_bytes())
output = {'network': 'none', 'price_version': manifest['universe_id'],
          'pricing_time': str(prepared.universe.built_at), 'historical_test_time': True, 'cases': {}}
for key, case in cases.items():
    req = PlanRequest.model_validate(case['request'])
    inventory = {'revision': 0, 'items': deepcopy(case['stock']), 'reservations': {}, 'events': {}}
    before = deepcopy(inventory)
    planner = PersonalPlanner(req, get_settings(), prepared, inventory, now=prepared.universe.built_at)
    started = time.perf_counter()
    try:
        plan = planner.create()
        assert plan.data.live_chain_requests == 0
        assert key != 'no_fish'
        if key == 'same_menu':
            assert plan.optimized_basket.total == 677.43
        if key == 'strict':
            assert all(n['status'] == 'VERIFIED' for n in plan.personal.checks['nutrition'])
        output['cases'][key] = {'status': 'PASS', 'plan': plan.model_dump(mode='json')}
    except PolicyConflict as exc:
        assert key == 'no_fish' and exc.code == 'DATA_BLOCKED'
        output['cases'][key] = {'status': exc.code, 'message': str(exc), 'diagnostics': exc.diagnostics}
    assert inventory == before
    output['cases'][key].update(stock_unchanged=True, seconds=time.perf_counter()-started)
    Path('/evidence/runtime.json').write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(json.dumps({'case': key, 'status': output['cases'][key]['status'],
                      'cost': output['cases'][key].get('plan', {}).get('optimized_basket', {}).get('total')}), flush=True)
