"""Four bounded derived-file writes diagnose persistence cost, not plan latency."""
import argparse
import time
from pathlib import Path
from uuid import uuid4

from app.services import meal_prepared_artifacts as a
from app.services.meal_library_content import digest, encoded

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--output',type=Path,required=True)
args=p.parse_args()
directory=Path('.local/recipes/week-write-profile')/uuid4().hex
directory.mkdir(parents=True,exist_ok=False)
lease=a._SharedGeneration(directory.resolve(),'diagnostic',uuid4().hex,writable=True)
times={'fsync_seconds':0.0,'replace_seconds':0.0,'fsync_calls':0,'replace_calls':0}
fsync,replace=a.os.fsync,a.os.replace

def timed_fsync(fd):
    start=time.perf_counter()
    try:return fsync(fd)
    finally:times['fsync_seconds']+=time.perf_counter()-start;times['fsync_calls']+=1

def timed_replace(source,target):
    start=time.perf_counter()
    try:return replace(source,target)
    finally:times['replace_seconds']+=time.perf_counter()-start;times['replace_calls']+=1

a.os.fsync,a.os.replace=timed_fsync,timed_replace
start=time.perf_counter()
try:
    for n in range(4):
        key=digest(encoded(['diagnostic-derived-file',n]))
        data=a.payload_bytes({'schema':a.SCHEMA,'key':key,'payload':{'diagnostic':n},'encoding':'json-v1','sha256':digest(a.payload_bytes({'diagnostic':n}))})
        a._atomic_derived_write(directory/(key+'.json'),data,lease)
finally:a.os.fsync,a.os.replace=fsync,replace
result={**times,'total_write_seconds':time.perf_counter()-start,'scope':'four small own derived-file writes on the same workspace volume; no plan, source-version or p95 evidence'}
args.output.write_bytes(encoded(result))
print(result)
