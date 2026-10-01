"""Publish a small evidence report only after all required local probes pass."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

root = Path(__file__).resolve().parents[2]
work = root / ".local/transition"


def read(name):
    return json.loads((work / name).read_text(encoding="utf-8-sig"))


release = read("packages-readonly/release.json")
assert release == read("reproduced-readonly/release.json")
image = read("image-08c1374.json")
assert image["commit"] == release["commit"] and not image["mismatch"]
final = read("state-final.json")
before = read("state-before-recovery.json")
assert final["plan_revisions"] == 40 and final["matching_live_imports"] == 1
assert final["plan_content_sha256"] == before["plan_content_sha256"]
assert final["old_inventory_sha256"] == before["old_inventory_sha256"]
assert final["source_rows_and_times"] == before["source_rows_and_times"]
assert read("old-inventory.json") == read("old-inventory-final.json")
audit = read("final-replay-audit.json")
assert audit["raw_hashes_times_contexts_equal_source"] and audit["served_source_times_preserved"]
assert audit["runner"]["runtime_reload"]["changed"] is True
assert audit["matching_import_snapshots"] == 1
raw = read("raw-final.json")
assert raw["raw_files"] > 0 and raw["bad_raw_files"] == 0
assert raw["manifest_sha256"] == final["active_manifest_sha256"]
plans = {
    name: read(name + ".json")
    for name in [
        "normal-before-recovery",
        "recovery-before-restart",
        "recovery-final-routes",
        "normal-final",
    ]
}
for probe in plans.values():
    assert len(probe["cases"]) == 6 and probe["all_previous_revisions_unchanged"]
    assert probe["after_revisions"] == 40 and all(c["plan_identical"] for c in probe["cases"])
replay = {
    name: read(name + ".json")
    for name in [
        "relay-first",
        "relay-redelivery",
        "relay-not-due",
        "relay-final-pair",
        "relay-final-not-due",
    ]
}
for probe in replay.values():
    assert probe["exit"] == 0 and probe["calls"]["retailer"] == 0
assert replay["relay-redelivery"]["receipt"]["server"]["activation"] == "already_active"
assert replay["relay-final-not-due"]["calls"] == {"retailer": 0, "push": 0, "activate": 0}
assert (work / "regression-08c1374-final.log").read_text().count(".") == 168
proofs = {
    p.name: hashlib.sha256(p.read_bytes()).hexdigest()
    for p in [
        work / "final-replay-audit.json",
        work / "state-final.json",
        work / "old-inventory-final.json",
        work / "regression-08c1374-final.log",
        work / "recovery-final-state.log",
        work / "production-task-after.xml",
        work / "final-stopped-state.txt",
    ]
}
assert (
    proofs["production-task-after.xml"]
    == "c781d10ce504aa172d8006f365f7ad167ac2ca23688fcf629d1b0851c5ff6755"
)
report = {
    "checked_utc": datetime.now(UTC).isoformat(),
    "branch": "release/lund-relay-20260929",
    "runtime_commit": release["commit"],
    "packages": release["packages"],
    "server_and_recovery_image": "sha256:d8a166fa7ee162cd0570f9d8089ff800e00d9c949ac3c674e387c5fff1538dd7",
    "recommended_relay_commit": "bdc9f7df417084641d0a712e3dad188dad1ad7d4",
    "recommended_relay_zip_sha256": "299ff34ecb7b5976e317afeef54719c9286d0ecd64c2807cee58533945de57d7",
    "status": {
        "original_s4u_live": "PASS for unchanged bdc9 package/configuration only",
        "queue_transition": "PASS",
        "recovery_saved_plan_reading": "PASS",
        "recovery_recalculation": "DISABLED: controlled 503, not supported",
        "production_activation": "NOT DONE; three decisions outstanding",
    },
    "new_retailer_requests": 0,
    "test_clock_used": False,
    "new_windows_package_installed_or_s4u_verified": False,
    "isolated_services_stopped_after_verification": True,
    "old_queue": {
        k: final[k]
        for k in [
            "old_inventory_sha256",
            "old_artifact_status_counts",
            "old_unique_artifacts",
            "old_receipt_files",
            "preserved_archive_hashes_valid",
        ]
    },
    "old_blocked_artifact_sha256": "05ab5b72790d7e270072945fd5090ca205dac0c4a174463233885ad10700c4b3",
    "old_policy_failure": "required_external_cache_unavailable; no successful old publication required",
    "old_policy_log_sha256": "a9ab11ddd3b469b2864a3f1f8e220a544cfc6f93fd1aa1829c1d64228e46d38f",
    "replays": replay,
    "live_artifact_audit": {
        k: audit[k]
        for k in [
            "artifact_sha256",
            "source_manifest",
            "matching_import_snapshots",
            "raw_payloads_verified",
            "raw_hashes_times_contexts_equal_source",
            "imported_source_rows",
            "active_manifest_sha256",
            "prepared_artifact_sha256",
            "serving",
            "served_rows_from_this_import",
            "served_source_times_preserved",
        ]
    },
    "final_actual_reload": audit["runner"]["runtime_reload"],
    "raw_files": raw,
    "freshness": read("freshness-final.json"),
    "plan_probes": plans,
    "recovery_restart_probe": json.loads(
        (work / "recovery-after-restart.log").read_text(encoding="utf-8-sig").splitlines()[0]
    ),
    "checkpoint": read("checkpoint.json"),
    "latest_plan_revisions": final["plan_revisions"],
    "plan_content_sha256": final["plan_content_sha256"],
    "final_image_verification": image,
    "compose_render": read("compose-final.json"),
    "regression_passed": 168,
    "proof_file_hashes": proofs,
    "historical_evidence_not_rerun": {
        "ordinary_windows_tests_bdc9": 3455,
        "restored_lidl_tests": 16,
        "five_previous_failures_focused_after": 40,
        "frontend_tests": 30,
        "browser_form_cases": 4,
    },
    "technical_decision": "REDO FÖR SEPARAT AKTIVERINGSBESLUT; rollback scope is authenticated saved-plan reading only",
}
target = root / "docs/releases/lund-20260929/TRANSITION-EVIDENCE.json"
target.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("Evidence checks passed; public report written without private cookies or keys.")
