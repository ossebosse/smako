"""Ordinary plan timings, with a final cgroup receipt after report serialization."""
from __future__ import annotations

import hashlib
import json
import runpy
import sys
from pathlib import Path

from app.services import reference_library
from app.services.meal_prepared_artifacts import method_signature

reference_library.PIN = Path('/review/backend/app/data/recipes/reference-library-262.json')
output = Path(sys.argv[sys.argv.index('--output')+1])
completed = False
try:
    runpy.run_path('/review/docs/reviews/integration-scaling-20261023/run_matrix.py',run_name='__main__')
    completed = True
finally:
    memory = {key:int(Path('/sys/fs/cgroup/memory.'+key).read_text()) for key in ('current','peak')}
    memory['swap_current'] = int(Path('/sys/fs/cgroup/memory.swap.current').read_text())
    with Path(__file__).open('rb') as source:
        digest = hashlib.file_digest(source,'sha256').hexdigest()
    output.mkdir(parents=True,exist_ok=True)
    method = method_signature()
    current_runtime = method == '8a42f9b78e3addba9f9dc634b27895fd4c71ee36381f540624a4546bcb850dbb'
    (output/'final-resource.json').write_text(json.dumps({
        'scope':'after all ordinary plan calls, report serialization and final GC; before tiny receipt write',
        'entry_sha256':digest,'method_signature':method,'memory':memory,
        'memory_target_passed':memory['peak'] <= 2684354560,
        'target_enforced_for_current_runtime':current_runtime},indent=2)+'\n')
    if completed and current_runtime and memory['peak'] > 2684354560:
        raise RuntimeError('Final process peak exceeded the current 2.5 GiB gate; preserve reports and stop')
