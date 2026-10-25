"""Resume this foreground evidence task after its SSH transport disconnected.

Completed frozen groups are verified and skipped. An unfinished nonempty
group is preserved and rejected. Disk logging outlives a closed SSH channel;
this installs no scheduler, queue, service or production configuration.
"""
from __future__ import annotations

import hashlib
import json
import os
import signal
import subprocess
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from run_current_pipeline import ARCHIVE_SHA, METHOD
from run_pilot import REVISION, ROOT, SOURCE, write
from run_pilot import main as pilot


def redirect_output(path):
    with path.open('x',encoding='utf8') as log:
        os.dup2(log.fileno(),1)
        os.dup2(log.fileno(),2)
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)


def main():
    stamp = datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')
    log = ROOT/f'resumed-pipeline-{REVISION}-{stamp}.log'
    redirect_output(log)
    if hasattr(signal,'SIGHUP'):
        signal.signal(signal.SIGHUP,signal.SIG_IGN)
    archive = Path('/tmp/candidate-catalogue-row-io.zip')
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == ARCHIVE_SHA
    with zipfile.ZipFile(archive) as bundle:
        for entry in bundle.infolist():
            if not entry.is_dir():
                assert hashlib.sha256(bundle.read(entry)).digest() == hashlib.sha256((ROOT/f'code-{REVISION}'/entry.filename).read_bytes()).digest()
    primary = json.loads((ROOT/f'candidate-{REVISION}-plain/L5000-verified-distribution.json').read_bytes())
    assert primary['method_signature'] == METHOD
    write(ROOT/f'resumed-pipeline-{REVISION}-{stamp}.json',{'source_commit':SOURCE,
        'entry_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'method_signature':METHOD,'archive_sha256':ARCHIVE_SHA,'pid':os.getpid(),'log':str(log),
        'scope':'Current foreground task; resume verified pilot groups, then HTTP/history, matched samples and full matrix'})
    print(json.dumps({'resume':'pilot','source_commit':SOURCE,'utc':datetime.now(UTC).isoformat()}),flush=True)
    pilot(resume=True)
    for script in ('run_http_history.py','run_matched.py','run_full_matrix.py'):
        print(json.dumps({'next_stage':script,'utc':datetime.now(UTC).isoformat()}),flush=True)
        subprocess.run(['python3','/tmp/'+script],check=True)


if __name__ == '__main__':
    main()
