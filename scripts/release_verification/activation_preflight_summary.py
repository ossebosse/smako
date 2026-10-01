"""Sanitize the stopped activation preflight; never perform a production action."""

import hashlib
import json
import zipfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree

root = Path(__file__).resolve().parents[2]
private = root / ".local/activation-20261001"


def read(name):
    return json.loads((private / name).read_text(encoding="utf-8-sig"))


image = read("image-identity.json")
relay = read("relay-identity.json")
production = read("production-readonly.json")
forecast = read("schedule-projection.json")
assert image["commit"] == "08c137475d9ca96a6ef7673245a639c8c5c9e922"
assert relay["commit"] == "bdc9f7df417084641d0a712e3dad188dad1ad7d4"
xml = (private / "windows-before.xml").read_bytes()
assert (
    hashlib.sha256(xml).hexdigest()
    == "c781d10ce504aa172d8006f365f7ad167ac2ca23688fcf629d1b0851c5ff6755"
)
task = ElementTree.fromstring(xml.decode("utf-8-sig"))
ns = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}
trigger = task.find("t:Triggers", ns)
assert len(trigger) == 1 and trigger[0].tag.endswith("CalendarTrigger")
assert trigger[0].find("t:Repetition", ns) is None
assert trigger[0].find("t:ScheduleByDay/t:DaysInterval", ns).text == "1"
package = root / ".local/transition/packages-readonly/smako-server-08c137475d9c.zip"
with zipfile.ZipFile(package) as z:
    policy_bytes = z.read("deploy/policies/lund-own-five-base-20260928-v1.json")
policy = json.loads(policy_bytes)
assert policy == json.loads(
    (root / "deploy/policies/lund-own-five-base-20260928-v1.json").read_bytes()
)
receipt_path = Path("D:/smako-local-relay/last-success.json")
receipt = json.loads(receipt_path.read_bytes())
old_artifacts = production["production"]["old_inbox_artifacts"]
report = {
    "checked_utc": datetime.now(UTC).isoformat(),
    "approval": {
        "policy": True,
        "server_with_read_only_recovery": True,
        "windows_arguments_and_working_directory_only": True,
        "schedule_change": False,
    },
    "result": "STOPPED_BEFORE_PAUSE_OR_CUTOVER: daily trigger cannot sustain 35h due / 48h stop with collection time",
    "working_branch": "release/lund-relay-20260929",
    "starting_documentation_commit": "6d84984e6e882becb9e49747c0b85d9016283855",
    "initial_worktree_clean": True,
    "server_identity": image,
    "relay_identity": relay,
    "target_image": "sha256:d8a166fa7ee162cd0570f9d8089ff800e00d9c949ac3c674e387c5fff1538dd7",
    "policy_id": policy["id"],
    "packaged_policy_sha256": hashlib.sha256(policy_bytes).hexdigest(),
    "required_context_ids": policy["required_context_ids"],
    "windows_task_xml_sha256": hashlib.sha256(xml).hexdigest(),
    "windows_task_state": "Ready",
    "next_windows_run_local": "2026-10-02T01:30:00+02:00",
    "last_windows_run_local": "2026-10-01T01:30:01+02:00",
    "last_windows_result": 1,
    "powershell_effective_policy": "RemoteSigned; registered PS7 executable, no override",
    "production_images": {c["name"]: c["image"] for c in production["containers"]},
    "production_checked_utc": production["checked_utc"],
    "production_ready": production["production"]["ready"],
    "production_serving": production["production"]["api/price-universe/status"],
    "production_manifest_sha256": production["production"]["manifest_sha256"],
    "production_plan_revisions": production["production"]["plan_revisions"],
    "old_inbox_paths": len(old_artifacts),
    "old_inbox_unique_artifacts": len(Counter(x["sha256"] for x in old_artifacts)),
    "old_windows_receipt": {
        "sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
        "artifact_sha256": receipt.get("sha256"),
        "observed_from": receipt.get("observed_from"),
        "collection_day": receipt.get("collection_day"),
    },
    "server_cron": production["cron"],
    "candidate_freshness_not_production": read("candidate-freshness.json"),
    "schedule_projection": forecast,
    "production_writes": 0,
    "retailer_requests": 0,
    "jobs_paused": False,
    "task_modified": False,
    "backup_status": "NOT STARTED; no consistent cutover backup claimed",
    "remaining_checks": "full current source/raw/campaign/optional-source validation, final private Compose/transport configuration, lock ownership, backups, deployment and all production acceptance tests not completed because schedule gate failed",
    "previous_queue_and_recovery_evidence": "still valid for the previously verified exact packages; not reopened",
    "next_phase_only": "campaign windows Sunday-Monday and Wednesday-Thursday Europe/Stockholm; measure base-price changes between authentic collections; no implementation or schedule change",
}
(root / "docs/releases/lund-20260929/ACTIVATION-PREFLIGHT-20261001.json").write_text(
    json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
)
print("Sanitized preflight saved; no activation was performed.")
