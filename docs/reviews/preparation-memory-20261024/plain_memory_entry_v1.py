"""Ordinary plan timings, with a final cgroup receipt after report serialization."""
from __future__ import annotations

import hashlib
import json
import runpy
import sys
from pathlib import Path

from app.services import reference_library

reference_library.PIN = Path('/review/backend/app/data/recipes/reference-library-262.json')
output = Path(sys.argv[sys.argv.index('--output')+1])
try:
    runpy.run_path('/review/docs/reviews/integration-scaling-20261023/run_matrix.py',run_name='__main__')
finally:
    memory = {key:int(Path('/sys/fs/cgroup/memory.'+key).read_text()) for key in ('current','peak')}
    memory['swap_current'] = int(Path('/sys/fs/cgroup/memory.swap.current').read_text())
    with Path(__file__).open('rb') as source:
        digest = hashlib.file_digest(source,'sha256').hexdigest()
    output.mkdir(parents=True,exist_ok=True)
    (output/'final-resource.json').write_text(json.dumps({
        'scope':'after all ordinary plan calls, report serialization and final GC; before tiny receipt write',
        'entry_sha256':digest,'memory':memory,'memory_target_passed':memory['peak'] <= 2684354560},indent=2)+'\n')
