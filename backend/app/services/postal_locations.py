"""Local geographic lookup only. Never infer a position from a price build key."""
import json
import re
from functools import lru_cache
from pathlib import Path

from grocery_data.app.domain.municipality import municipality_name


@lru_cache(maxsize=1)
def postal_data():
    return json.loads((Path(__file__).parents[1] / "data/postal/se-gisco-2025.json").read_text(encoding="utf-8"))


def lookup_postcode(value):
    postal = re.sub(r"\s", "", value)
    if not re.fullmatch(r"[0-9]{5}", postal):
        raise ValueError("Ange ett svenskt postnummer med fem siffror.")
    rows = postal_data()["postcodes"].get(postal, [])
    if len(rows) != 1:
        return {"status": "ambiguous_postcode" if rows else "unknown_postcode", "postal_code": postal}
    latitude, longitude, code = rows[0]
    return {"status": "located", "postal_code": postal, "latitude": latitude,
            "longitude": longitude, "municipality_code": code,
            "municipality_name": municipality_name(code), "distance_basis": "postcode_reference_point",
            "attribution": postal_data()["attribution"]}
