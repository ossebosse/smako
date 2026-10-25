"""Finite foreground retry of a failed HTTP diagnostic; preserve every attempt."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import subprocess
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from resume_current_pipeline import redirect_output
from run_current_pipeline import ARCHIVE_SHA, METHOD
from run_http_history import main as http_history
from run_pilot import REVISION, ROOT, SOURCE, write
from run_pilot import main as pilot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt',type=int,choices=range(2,10),required=True)
    args = parser.parse_args()
    destination = ROOT/f'http-history-{REVISION}-attempt{args.attempt}'
    assert not destination.exists(), 'Never overwrite an earlier diagnostic'
    stamp = datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')
    log = ROOT/f'continued-http-{REVISION}-attempt{args.attempt}-{stamp}.log'
    redirect_output(log)
    if hasattr(signal,'SIGHUP'):
        signal.signal(signal.SIGHUP,signal.SIG_IGN)
    archive = Path('/tmp/candidate-catalogue-row-io.zip')
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == ARCHIVE_SHA
    with zipfile.ZipFile(archive) as bundle:
        for entry in bundle.infolist():
            if not entry.is_dir():
                assert bundle.read(entry) == (ROOT/f'code-{REVISION}'/entry.filename).read_bytes()
    primary = json.loads((ROOT/f'candidate-{REVISION}-plain/L5000-verified-distribution.json').read_bytes())
    assert primary['method_signature'] == METHOD
    write(log.with_suffix('.json'),{'source_commit':SOURCE,'method_signature':METHOD,
        'archive_sha256':ARCHIVE_SHA,'entry_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'pid':os.getpid(),'log':str(log),'http_destination':str(destination),
        'scope':'Current foreground task; verify completed pilot, retry HTTP/history in a new folder, then matched samples and full matrix'})
    pilot(resume=True)
    print(json.dumps({'next_stage':'http-history','attempt':args.attempt,'utc':datetime.now(UTC).isoformat()}),flush=True)
    http_history(destination=destination)
    for script in ('run_matched.py','run_full_matrix.py'):
        print(json.dumps({'next_stage':script,'utc':datetime.now(UTC).isoformat()}),flush=True)
        subprocess.run(['python3','/tmp/'+script],check=True)


if __name__ == '__main__':
    main()
