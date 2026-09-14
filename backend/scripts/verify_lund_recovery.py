"""Read-only verification of active bytes, HTTPS readiness and source ages."""

import hashlib
import json
import os
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path("/srv/app/var/price_universes")
OUT = Path("/srv/app/var/reports/recovery-22350-20260914")
expected_sources = {
    "context:coop:23eaae11c9661e68": "own:coop:730400",
    "context:hemkop:3288e04edd97e349": "own:hemkop:4224",
    "context:ica:46850f1523580803": "primat:ica:1088004",
    "context:ica:979e70ce1f577bc4": "primat:ica:1004409",
    "context:willys:383650ec6ff5a636": "own:willys:2176",
    "context:willys:4a671428fc484e43": "own:willys:2354",
}
required = set(os.environ["PRICE_UNIVERSE_REQUIRED_CONTEXT_IDS"].split(","))
manifest = json.loads((ROOT / "active/city-lund.json").read_bytes())
raw = (ROOT / manifest["artifact_file"]).read_bytes()
assert len(raw) == manifest["artifact_bytes"]
assert hashlib.sha256(raw).hexdigest() == manifest["artifact_sha256"]
artifact = json.loads(raw)
now = datetime.now(UTC)
stores = []
for store in artifact["stores"]:
    provenance = store["source_provenance"]
    source_context = ":".join((provenance["source_provider"], store["chain"], provenance["provider_store_id"]))
    assert source_context == expected_sources[store["store_id"]]
    rows = [r for r in artifact["universe"]["products"] if r["store_id"] == store["store_id"]]
    observed = sorted(datetime.fromisoformat(r["source_provenance"]["source_observed_at"]) for r in rows)
    age = (now - observed[0]).total_seconds() / 3600
    stores.append({"context_id": store["store_id"], "name": store["name"],
                   "price_context_type": store.get("price_context_type"), "coverage": store.get("coverage"),
                   "source_context_id": source_context, "price_semantics": store.get("price_semantics"),
                   "source_snapshot_ids": sorted({r["source_provenance"]["source_snapshot_id"] for r in rows}),
                   "observed_from": observed[0].isoformat(), "observed_to": observed[-1].isoformat(),
                   "age_hours": age, "products": len(rows), "usable": age < 48})
assert required <= {row["context_id"] for row in stores if row["usable"]}
responses = {}
for route in ("/health", "/ready", "/api/admin/status"):
    headers = {"Authorization": "Bearer " + os.environ["BETA_ADMIN_TOKEN"]} if "admin" in route else {}
    request = urllib.request.Request("https://beta.smako.nu" + route, headers=headers)
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.load(response)
        if "admin" in route:
            payload = {key: payload.get(key) for key in ("refresh", "price_universe", "build_id")}
        responses[route] = {"status": response.status, "body": payload}
ready = responses["/ready"]["body"]["price_universe"]
assert ready["price_universe_id"] == manifest["universe_id"]
assert ready["required_contexts_usable"] and ready["usable_context_count"] >= 6
result = {"verified_at": now.isoformat(), "disk_manifest": manifest, "contexts": stores,
          "https": responses, "all_six_usable": True, "artifact_hash_verified": True}
(OUT / "runtime-verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
print(json.dumps({"universe_id": manifest["universe_id"], "all_six_usable": True,
                  "contexts": stores, "health": responses["/health"]["status"],
                  "ready": responses["/ready"]["status"]}, ensure_ascii=False))
