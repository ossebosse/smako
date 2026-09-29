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
    from grocery_data.local_relay import main
    raise SystemExit(main())
