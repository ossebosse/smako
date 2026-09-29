"""Bounded probe: ordinary CLI, unrelated optional fetches explicitly deferred."""
import os
import sys
from contextlib import ExitStack
from unittest.mock import patch
from grocery_data.__main__ import main

async def deferred(*args, **kwargs):
    return {'status':'not_collected_in_scoped_coop_test','external_price_requests':0}

async def failed(*args, **kwargs):
    raise ConnectionError('explicit isolated Coop failure probe')

with ExitStack() as stack:
    for target in ['citygross_municipal_job.run_source_job', 'lidl_municipal_job.run_source_job',
                   'willys_flyer_job.run_source_job', 'ica_offer_job.run_structured_offer_job']:
        stack.enter_context(patch('grocery_data.app.services.'+target, deferred))
    if os.getenv('COOP_BINDING_PROBE') == 'fault':
        stack.enter_context(patch('grocery_data.app.services.coop_offer_job.run_offer_job', failed))
    raise SystemExit(main(sys.argv[1:]))
