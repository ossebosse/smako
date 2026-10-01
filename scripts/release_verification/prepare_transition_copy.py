"""Explicit fault injection in a disposable COPY: import exists, publication absent."""

import json
import shutil
import sys
from pathlib import Path

from grocery_data.app.services.manual_refresh_operations import (
    RefreshRunLock,
    production_refresh_lock_path,
)
from grocery_data.app.services.prepared_universe_activation import (
    PreparedUniverseArtifactStore,
    validate_backend_prepared_universe_artifact,
)

root = Path("/work")
assert (root / "ops-copy.json").exists()
digest = "5b1a2b6b01ba65338f224cdd6af432c8178f214b1612d5d54ec400ffe8f9362a"
inbox = root / "raw/source-inbox/municipality-1281"
inbox.mkdir(exist_ok=True)
shutil.copy2(root / "raw/source-inbox/willys" / (digest + ".smako-source"), inbox)
cache = root / "price-universes"
with RefreshRunLock(production_refresh_lock_path(root / "grocery.sqlite", cache)):
    active = cache / "active/city-lund.json"
    backup = root / (sys.argv[1] if len(sys.argv) > 1 else "before-publication-fault.json")
    assert backup.parent == root and not backup.exists()
    shutil.copy2(active, backup)
    # Real, previously verified 44,080-row artifact; no fabricated rows/times.
    candidate = (
        cache / "artifacts/b0bb2fd6f191b2362a7912d617a073f94ea3a265eabb679a509b756591d3ddd3.json"
    )
    policy = json.loads((root / "policy.json").read_bytes())
    result = PreparedUniverseArtifactStore(cache).activate(
        candidate,
        city="Lund",
        validator=lambda payload, city: validate_backend_prepared_universe_artifact(
            payload, city, required_context_ids=tuple(policy["required_context_ids"])
        ),
    )
    assert result.status == "active_from_prebuilt_artifact", result
print(
    "COPY ONLY: older real publication selected; latest import retained; no source observations changed."
)
