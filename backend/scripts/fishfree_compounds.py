"""Verify positive fish detection against five retained real declarations."""

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from app.models.personal import TasteProfile
from app.services.personal_policy import PolicyConflict, check_product
from app.services.personal_source_facts import project_raw_facts

retained = json.loads(Path("reports/private/qualified-facts.json").read_bytes())
original = {key[1]: value for key, value in retained["facts"]}
rows = []
for key in (
    "0d21d980f0b54196a7adee1ccfa5fe05",
    "a1eb0aaf3199447b95c9702e633731f9",
    "c104c3535ce84f9aabf07e9e85b99448",
    "12d9da3926b64608bcd0dc8bd2e2e889",
    "2f0fa6da7a8b40708b68b5a0537e336c",
):
    raw = retained["raw"][key]
    prior = original[key]
    fact = project_raw_facts(
        raw,
        chain="coop",
        product_id=key,
        snapshot_id=prior["source_snapshot_id"],
        source_reference=prior["source"],
    )
    try:
        check_product(
            SimpleNamespace(name=raw["name"], canonical_name=raw["name"]),
            TasteProfile(exclusions=["fisk"]),
            fact,
        )
    except PolicyConflict as error:
        assert error.code == "CONFLICT" and "produktdeklarationen" in str(error)
        rows.append(
            {
                "name": raw["name"],
                "product_id": key,
                "retailer_product_id": str(raw["id"]),
                "source": prior["source"],
                "field": "listOfIngredients",
                "declaration": raw["listOfIngredients"],
                "projection_sha256": hashlib.sha256(
                    json.dumps(raw, sort_keys=True, ensure_ascii=False).encode()
                ).hexdigest(),
                "status": "FISH_IDENTIFIED",
                "reason": str(error),
            }
        )
    else:
        raise AssertionError("Known fish ingredient passed")
Path("reports/fishfree-20260913/compound-fish.json").write_text(
    json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf8"
)
print("Five retained compound declarations: FISH_IDENTIFIED")
