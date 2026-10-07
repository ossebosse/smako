"""Run only code inside this installed release, independent of caller/PYTHONPATH."""
import hashlib
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / "RELEASE.json").read_bytes())
if manifest["kind"] != "windows-relay":
    raise SystemExit("Not a Windows relay release")
for name, expected in manifest["files"].items():
    path = (root / name).resolve()
    if not path.is_relative_to(root) or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise SystemExit("Release file integrity failure: " + name)
sys.path[:0] = [str(root / "backend"), str(root)]
if "--check-install" in sys.argv:
    from grocery_data import local_relay, relay_preflight, relay_status, source_cli  # noqa: F401
    print(json.dumps({"status": "PASS", "commit": manifest["commit"], "files": len(manifest["files"]),
                      "python": sys.version, "relay_module": local_relay.__file__, "network_calls": 0}))
else:
    # Validate actual writable temporary storage before importing collection code.
    from grocery_data.relay_storage import configure_storage, storage_probe
    workspace = Path(sys.argv[sys.argv.index('--workspace') + 1])
    configure_storage(workspace)
    probe_request = workspace / 'storage-preflight.request'
    if probe_request.exists():
        import os
        from datetime import UTC, datetime

        from grocery_data.app.services.durable_files import atomic_write_bytes
        from grocery_data.app.services.manual_refresh_operations import RefreshRunLock
        with RefreshRunLock(workspace / 'local-workflow.lock'):
            os.replace(probe_request, workspace / 'storage-preflight.consumed')
            result = storage_probe(workspace)
            result.update(commit=manifest['commit'], checked_at=datetime.now(UTC).isoformat())
            atomic_write_bytes(workspace / 'storage-preflight.json', json.dumps(result).encode())
            print(json.dumps(result))
        raise SystemExit(0)
    from grocery_data.local_relay import main
    raise SystemExit(main())
