"""Fail-closed storage for the local relay, independent of transport/source policy."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from grocery_data.app.services.durable_files import require_free_space

MIB = 1024 * 1024
RESERVE_BYTES = 512 * MIB


def configure_storage(workspace: Path) -> Path:
    """Do not create a missing workspace or accept a different mounted volume.

    The launcher sets these variables before Python starts. CLI callers receive
    the same protection before collector imports. An actual write probe avoids
    tempfile's otherwise silent fallback when the configured directory fails.
    """
    requested = workspace.absolute()
    root = requested.resolve(strict=True)
    if not root.is_dir() or root.anchor.casefold() != requested.anchor.casefold():
        raise OSError("relay workspace is unavailable or resolves to another volume")
    temporary = root / "tmp"
    temporary.mkdir(exist_ok=True)
    if temporary.resolve().parent != root:
        raise OSError("relay temporary directory escapes workspace")
    for key in ("TEMP", "TMP", "TMPDIR", "SQLITE_TMPDIR"):
        os.environ[key] = str(temporary)
    tempfile.tempdir = str(temporary)
    with tempfile.TemporaryFile() as handle:
        handle.write(b"relay storage probe")
        handle.flush()
        os.fsync(handle.fileno())
    return temporary


def storage_usage(workspace: Path) -> dict:
    root = workspace.resolve(strict=True)
    runs = []
    for run in (root / "runs").glob("*"):
        if run.is_dir() and not run.is_symlink():
            runs.append(sum(p.stat().st_size for p in run.rglob("*") if p.is_file()))
    return {"largest_run_bytes": max(runs, default=0), "retained_run_bytes": sum(runs),
            "queue_bytes": sum(p.stat().st_size for p in (root / "completed").glob("*.smako-source"))}


def collection_capacity(workspace: Path) -> dict:
    """Budget another run and uncompressed packaging, not just its ZIP size.

    Existing queue/raw/database bytes already reduce disk_usage.free; they are
    reported without charging them twice. Twice the largest retained run is a
    conservative growth allowance, with a 512 MiB floor and separate reserve.
    This is a preflight, never a promise that a later write cannot fail.
    """
    root = workspace.resolve(strict=True)
    usage = storage_usage(root)
    required = max(512 * MIB, 2 * usage["largest_run_bytes"])
    capacity = require_free_space(root, required_bytes=required, reserve_bytes=RESERVE_BYTES)
    return {"free_bytes": capacity.free_bytes, "required_bytes": required,
            "reserve_bytes": RESERVE_BYTES, **usage}


def storage_probe(workspace: Path) -> dict:
    """Create real temp files in parent and child; no network or collection."""
    temporary = configure_storage(workspace)
    with tempfile.NamedTemporaryFile() as handle:
        handle.write(b"parent storage probe")
        handle.flush()
        parent_path = str(Path(handle.name).resolve())
    source = """import json,os,tempfile
with tempfile.NamedTemporaryFile() as f:
 f.write(b'child storage probe');f.flush();os.fsync(f.fileno())
 print(json.dumps({'path':f.name,'temporary':tempfile.gettempdir()}))
"""
    child = json.loads(subprocess.check_output([sys.executable, "-I", "-B", "-c", source], text=True))
    if Path(child["path"]).resolve().parent != temporary:
        raise OSError("child temporary storage escaped workspace")
    result = {"status": "PASS", "parent_temp_file": parent_path,
              "child_temp_file": child["path"], "capacity": collection_capacity(workspace),
              "pid": os.getpid(), "external_price_requests": 0}
    if os.name == "nt":
        import ctypes
        session = ctypes.c_ulong()
        if not ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(), ctypes.byref(session)):
            raise OSError("unable to inspect task session")
        result["windows_session_id"] = session.value
    return result


# Executed with the existing authenticated receiver identity. No new server
# installation, paths, locks, collection or publication are introduced here.
RECEIVER_CAPACITY_SCRIPT = r'''
import json,os,shutil,sys
from pathlib import Path
from sqlalchemy.engine import make_url
args=json.loads(sys.argv[1])
raw=Path(os.environ['GROCERY_RAW_SNAPSHOT_ROOT'])
prices=Path(os.environ['PRICE_UNIVERSE_CACHE_ROOT'])
url=os.environ['GROCERY_DATABASE_URL']
if not url.startswith('sqlite'): raise ValueError('capacity probe requires known SQLite storage')
db=Path(make_url(url).database)
if not db.is_file(): raise ValueError('receiver database unavailable')
price_bytes=max((p.stat().st_size for p in prices.rglob('*.json') if p.is_file()),default=0)
db_bytes=sum(p.stat().st_size for p in db.parent.glob(db.name+'*') if p.is_file())
inbox=Path(args['inbox'])
if not inbox.is_dir(): raise ValueError('receiver inbox unavailable')
budgets=[(inbox,args['artifact_bytes']),(raw,args['run_bytes']),
         (db.parent,2*max(db_bytes,args['run_bytes'])),(prices,2*price_bytes)]
volumes={}
for path,required in budgets:
 device=str(path.stat().st_dev)
 row=volumes.setdefault(device,{'paths':[],'required_bytes':0,'reserve_bytes':512*1024**2,
                              'free_bytes':shutil.disk_usage(path).free})
 row['paths'].append(str(path));row['required_bytes']+=required
result={'status':'PASS','volumes':list(volumes.values()),'database_bytes':db_bytes,
        'largest_price_file_bytes':price_bytes,'uid':os.getuid()}
if any(v['free_bytes']<v['required_bytes']+v['reserve_bytes'] for v in volumes.values()):
 result['status']='FAIL';result['reason']='insufficient_receiver_storage'
print(json.dumps(result))
'''


def receiver_capacity(transport, workspace: Path) -> dict:
    """Conservative current receiver budget; failure never consumes local queue."""
    local = storage_usage(workspace)
    arguments = json.dumps({"inbox": transport.inbox,
                            "artifact_bytes": max(local["queue_bytes"], 64 * MIB),
                            "run_bytes": max(local["largest_run_bytes"], 256 * MIB)})
    # Supply data through stdin as part of a fixed script, not a remote shell arg.
    source = "import sys\nsys.argv=['capacity'," + repr(arguments) + "]\n" + RECEIVER_CAPACITY_SCRIPT
    response = subprocess.run([
        "ssh", "-oBatchMode=yes", "-oConnectTimeout=15", transport.ssh_host,
        "docker", "exec", "-i", "--user", "10001:10001", transport.container, "python", "-",
    ], input=source, capture_output=True, text=True, check=True, timeout=60)
    result = json.loads(response.stdout)
    if result.get("status") != "PASS":
        error = OSError("insufficient receiver storage; local delivery queue preserved")
        error.storage_status = result
        raise error
    return result
