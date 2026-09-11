"""Read-only, network-disabled verification of the deployed default fact adapter."""

import json
import resource
import time
from pathlib import Path

from app.services.personal_source_facts import load_retained_facts
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact

root = Path("/srv/app/var/price_universes")
manifest = json.loads((root / "active/city-lund.json").read_bytes())
prepared = PreparedPriceUniverseArtifact.model_validate_json(
    (root / manifest["artifact_file"]).read_bytes()
).restore()
start = time.perf_counter()
facts = load_retained_facts(prepared)
print(
    json.dumps(
        {
            "price_version": manifest["universe_id"],
            "facts_version": facts.version,
            "projected_products": len(facts),
            "load_seconds": round(time.perf_counter() - start, 3),
            "max_rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1),
            "live_requests": 0,
            "private_data_read": False,
        }
    )
)
