"""Explicit isolated optional job failure; ordinary CLI remains authoritative."""
import sys
from unittest.mock import patch
from grocery_data.__main__ import main
async def fail(*args, **kwargs):
    raise ConnectionError('explicit isolated optional-source injection')
with patch('grocery_data.app.services.willys_flyer_job.run_source_job', fail):
    raise SystemExit(main(sys.argv[1:]))
