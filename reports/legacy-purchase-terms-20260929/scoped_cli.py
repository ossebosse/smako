"""Bounded probe: ordinary CLI, unrelated optional fetches explicitly deferred."""
import os
import sys
from contextlib import ExitStack
from unittest.mock import patch
from grocery_data.__main__ import main

async def deferred(*args, **kwargs):
    return {'status':'not_collected_in_scoped_ica_hemkop_test','external_price_requests':0}

async def failed(*args, **kwargs):
    from pathlib import Path
    from datetime import datetime, UTC
    import json
    Path('/work/optional-failure-probe.json').write_text(json.dumps({'chain':'hemkop','invoked_at':datetime.now(UTC).isoformat(),'kind':'synthetic optional collection failure','external_price_requests':0}))
    raise ConnectionError('explicit isolated optional Hemkop failure probe')

with ExitStack() as stack:
    for target in ['citygross_municipal_job.run_source_job', 'lidl_municipal_job.run_source_job',
                   'willys_flyer_job.run_source_job','coop_offer_job.run_offer_job',
                   'ica_offer_job.run_structured_offer_job','hemkop_municipal_job.run_source_job']:
        stack.enter_context(patch('grocery_data.app.services.'+target, deferred))
    if os.getenv('HEMKOP_MUNICIPAL_PROBE') == 'fault':
        stack.enter_context(patch('grocery_data.app.services.hemkop_municipal_job.run_source_job', failed))
    raise SystemExit(main(sys.argv[1:]))
