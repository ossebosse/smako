"""Bounded host-side samples of this task's running workers, outside their cgroups.

No docker exec observer allocates within the worker. Component samples are
not atomic with the historical memory.peak; they cannot identify exact peak
composition after the fact. No environment, credentials or user state is read.
"""
from __future__ import annotations

import json
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path('/opt/smako/evidence/preparation-memory-20261024')


def main():
    destination = ROOT/'host-memory-samples-b5c242d.jsonl'
    seen = {}
    deadline = time.monotonic()+18*60*60
    with destination.open('x') as output:
        while time.monotonic() < deadline:
            workers = subprocess.check_output(['docker','ps','--filter','name=smako-preparation-',
                                              '--format','{{.Names}}'],text=True).splitlines()
            for name in workers:
                try:
                    if name not in seen:
                        data = json.loads(subprocess.check_output(['docker','inspect',name]))[0]
                        if not data['State']['Running']:
                            continue
                        pid = data['State']['Pid']
                        relative = Path(f'/proc/{pid}/cgroup').read_text().splitlines()[0].split(':',2)[2].lstrip('/')
                        seen[name] = Path('/sys/fs/cgroup')/relative, -1
                    group, previous = seen[name]
                    peak = int((group/'memory.peak').read_text())
                    if peak == previous:
                        continue
                    stats = dict(line.split() for line in (group/'memory.stat').read_text().splitlines())
                    row = {'utc':datetime.now(UTC).isoformat(),'container':name,
                           'peak_bytes':peak,'current_bytes':int((group/'memory.current').read_text()),
                           'sampled_components':{key:int(stats[key]) for key in ('anon','file','kernel')},
                           'swap_current':int((group/'memory.swap.current').read_text()),
                           'scope':'host sample; components are not an atomic historical peak decomposition'}
                    output.write(json.dumps(row)+'\n');output.flush()
                    seen[name] = group,peak
                except FileNotFoundError:
                    continue  # Exited cgroups disappear; their Docker exit receipts remain.
            time.sleep(2)


if __name__ == '__main__':
    main()
