"""Freeze existing public price/fact artifacts only, without collecting sources."""

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from app.services.personal_source_facts import load_retained_facts
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact

root = Path("/srv/app/var/price_universes")
manifest = json.loads((root / "active/city-lund.json").read_bytes())
artifact = (root / manifest["artifact_file"]).read_bytes()
prepared = PreparedPriceUniverseArtifact.model_validate_json(artifact).restore()
facts = load_retained_facts(prepared)
Path("/tmp/combined-prices.json").write_bytes(artifact)
Path("/tmp/combined-facts.json").write_text(
    json.dumps(
        {
            "now": datetime.now(UTC).isoformat(),
            "facts_version": facts.version,
            "facts": [[list(k), asdict(v)] for k, v in sorted(facts.items())],
        },
        ensure_ascii=False,
    )
)
print(
    json.dumps(
        {
            "price_version": manifest["universe_id"],
            "facts_version": facts.version,
            "products": len(prepared.universe.products),
            "external_calls": 0,
        }
    )
)
