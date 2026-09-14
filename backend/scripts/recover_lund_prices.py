"""One recovery through the existing locked source-inbox/managed refresh runner."""

import json
import os
from datetime import UTC, datetime
from pathlib import Path

from deploy.scripts.run_daily_refresh import _operations_lock, _run_locked, build_refresh_command

REQUIRED = (
    "context:coop:23eaae11c9661e68",
    "context:hemkop:3288e04edd97e349",
    "context:ica:46850f1523580803",
    "context:ica:979e70ce1f577bc4",
    "context:willys:383650ec6ff5a636",
    "context:willys:4a671428fc484e43",
)

assert os.geteuid() == 10001
assert set(os.environ["PRICE_UNIVERSE_REQUIRED_CONTEXT_IDS"].split(",")) == set(REQUIRED)
candidate = Path("/srv/app/var/reports/recovery-22350-20260914/primat-candidate.json")
assert candidate.is_file()
# Explicit cache goes through the normal freshness, identity and closed-schema
# checks. No observation is rewritten and there is no provider request here.
command = build_refresh_command() + [
    "--chain", "citygross", "--external-cache", str(candidate),
]
with _operations_lock() as lock:
    code = _run_locked(lock, started_at=datetime.now(UTC), command=command)
print(json.dumps({"recovery_exit_code": code, "required_context_count": len(REQUIRED)}))
raise SystemExit(code)
