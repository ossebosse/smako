"""Read-only, credential-free relay status; no collection or activation."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def local_status(workspace: Path):
    receipt_path = workspace / "last-success.json"
    receipt = json.loads(receipt_path.read_bytes()) if receipt_path.exists() else {}
    paths = sorted((workspace / "logs").glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    events = []
    if paths:
        for line in paths[-1].read_text(encoding="utf-8").splitlines():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # An interrupted final write is not a successful phase.
    by_event = {e["event"]: e for e in events if "event" in e}
    phases = {
        label: by_event.get(event, {}).get("at")
        for label, event in {
            "actual_start": "task_start",
            "collection_complete": "collection_complete",
            "local_validation": "validation_pass",
            "upload": "upload_pass",
            "server_import_started": "server_import_start",
            "server_activation_acknowledged": "server_activation_pass",
            "end": "task_end",
        }.items()
    }
    if "task_failed" in by_event:
        outcome = "FAILED"
    elif "task_success" in by_event or (
        "server_activation_pass" in by_event and "task_end" in by_event
    ):
        outcome = "SUCCESS"
    elif "already_delivered" in by_event:
        outcome = "ALREADY_DELIVERED"
    elif "already_running" in by_event:
        outcome = "SKIPPED_LOCK_HELD"
    else:
        outcome = "INCOMPLETE_OR_RUNNING" if events else "NO_RUN_LOG"
    activation = by_event.get("server_activation_pass", {}).get("activation")
    return {
        "expected_daily_schedule": "01:30 Europe/Stockholm",
        "trigger_kind": "not inferred from wall clock; manual starts are possible",
        "latest_log": str(paths[-1]) if paths else None,
        "phases": phases,
        "outcome": outcome,
        "vps_validation_activation_index": (
            "confirmed together by normal managed activation acknowledgement"
            if activation == "normal_managed_refresh"
            else "already active; no rebuild"
            if activation == "already_active"
            else "not confirmed for this run"
        ),
        "last_success_observed_from": receipt.get("observed_from"),
        "last_success_completed_at": receipt.get("completed_at"),
        "artifact_id": Path(receipt["artifact"]).stem if receipt.get("artifact") else None,
        "sha256_prefix": receipt.get("sha256", "")[:12] or None,
        "multi_day_reliability": "UNOBSERVED",
    }


REMOTE_STATUS = """
import json,os
from collections import Counter
from datetime import UTC,datetime
from pathlib import Path
from grocery_data.app.services.prepared_universe_activation import PreparedUniverseArtifactStore
p=PreparedUniverseArtifactStore(Path(os.environ['PRICE_UNIVERSE_CACHE_ROOT'])).resolve_active_artifact('Lund',verify_hash=True)
u=json.loads(p.read_bytes())['universe']
rows=[r for r in u['products'] if r['chain']=='willys']
now=datetime.now(UTC)
observations=[r['source_provenance']['source_observed_at'] for r in rows]
ages=[(now-datetime.fromisoformat(t.replace('Z','+00:00'))).total_seconds()/3600 for t in observations]
print(json.dumps({'status':'OK','universe_id':u['universe_id'],'artifact_hash_verified':True,'willys_rows':len(rows),'freshness':dict(Counter('STALE' if a>=48 else 'AGING' if a>=36 else 'FRESH' for a in ages)),'observed_from':min(observations) if observations else None,'observed_to':max(observations) if observations else None,'providers':dict(Counter(r['source_provenance']['source_provider'] for r in rows)),'transports':dict(Counter(r['source_provenance'].get('collection_location') for r in rows)),'provider_calls':0}))
"""


def vps_status():
    try:
        result = subprocess.run(
            [
                "ssh",
                "-oBatchMode=yes",
                "-oConnectTimeout=15",
                "smako",
                "/opt/smako/compose",
                "exec",
                "-T",
                "-u",
                "10001:10001",
                "scheduler",
                "python",
                "-",
            ],
            input=REMOTE_STATUS,
            text=True,
            capture_output=True,
            timeout=60,
            check=True,
        )
        return json.loads(result.stdout)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return {"status": "UNAVAILABLE", "error_type": type(exc).__name__}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--local-only", action="store_true")
    args = parser.parse_args()
    result = {"local": local_status(args.workspace)}
    if not args.local_only:
        result["vps"] = vps_status()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
