"""Export only non-secret operational results; never export plans or cookies."""

import hashlib
import json
from pathlib import Path

root = Path("/work")
report = {
    "runtime_commit": "bdc9f7df417084641d0a712e3dad188dad1ad7d4",
    "production_image": "sha256:54dde8382599ac30beee8bffd05d8cefff232e1ea5c81f1fd7f302db0d591c1f",
    "candidate_image": "sha256:2f81344208e05cbc57d16fa74a73c97b26bc729859936ca5d96ab150579fe221",
    "network": "none for all Docker replay/HTTP probes; no new live retailer requests",
    "evidence": {},
}
for name in (
    "ops-copy",
    "ops-preflight",
    "new-created",
    "new-open-current",
    "old-read-original",
    "old-read-diagnostic",
    "old-read-restored",
    "old-recalculate-restored",
    "new-read-recovery",
):
    path = root / (name + ".json")
    data = json.loads(path.read_bytes())
    keep = {
        key: value
        for key, value in data.items()
        if key not in {"current_campaign", "serving_status"}
    }
    if "serving_status" in data:
        keep["serving"] = {
            key: data["serving_status"].get(key)
            for key in (
                "active",
                "universe_id",
                "raw_product_count",
                "freshness",
                "usable_context_count",
                "oldest_usable_price_age_hours",
            )
        }
    keep["evidence_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    report["evidence"][name] = keep
for name in ("ops-production-copy", "old-drain"):
    path = Path("/oldpair") / (name + ".json")
    report["evidence"][name] = {
        **json.loads(path.read_bytes()),
        "evidence_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
(root / "ops-summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
print("Sanitized operational evidence written.")
