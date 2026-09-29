"""SCB RegSO 2025 follows municipal boundaries; explicit optional evidence.

No geocoding or new radius. Coordinates come from the official store register.
Boundary-near points stay unknown. Legacy address/locality modes are unchanged.
"""
import hashlib
import json
import math
from datetime import UTC, datetime
from functools import lru_cache
from itertools import pairwise

import httpx

from grocery_data.app.domain.municipality import municipality_name

SCB_URL = "https://geodata.scb.se/geoserver/stat/wfs"
SCB_DOC = "https://www.scb.se/vara-tjanster/oppna-data/oppna-geodata/regso/"


async def fetch_boundary(code):
    municipality_name(code)
    params = {"service": "WFS", "version": "1.1.0", "request": "GetFeature",
              "typeName": "stat:RegSO_2025", "outputFormat": "application/json",
              "srsName": "EPSG:4326", "CQL_FILTER": f"kommunkod='{code}'"}
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(SCB_URL, params=params)
        response.raise_for_status()
    result = {"source_url": str(response.url), "documentation": SCB_DOC,
              "observed_at": datetime.now(UTC).isoformat(), "version": "RegSO_2025",
              "municipality_code": code, "source_sha256": hashlib.sha256(response.content).hexdigest(),
              "payload": response.text}
    validate_boundary(result)
    return result


def validate_boundary(evidence):
    if (not evidence["source_url"].startswith(SCB_URL + "?")
            or evidence["version"] != "RegSO_2025"
            or hashlib.sha256(evidence["payload"].encode()).hexdigest() != evidence["source_sha256"]):
        raise ValueError("unbound SCB geometry")
    data = json.loads(evidence["payload"])
    features = data["features"]
    if (not features or data["numberMatched"] != len(features)
            or data["numberReturned"] != len(features)
            or not data["crs"]["properties"]["name"].endswith("4326")):
        raise ValueError("incomplete or wrong-CRS SCB geometry")
    for f in features:
        if (f["properties"]["kommunkod"] != evidence["municipality_code"]
                or f["geometry"]["type"] not in {"Polygon", "MultiPolygon"}):
            raise ValueError("wrong municipality/geometry")
    return features


def _ring(x, y, ring):
    if len(ring) < 4 or ring[0] != ring[-1]:
        raise ValueError("unclosed boundary")
    inside, near = False, False
    scale = math.cos(math.radians(y))
    for a, b in pairwise(ring):
        # Conservative 10 m uncertainty around ANY RegSO edge (including
        # internal divisions). Do not silently round a border point inside.
        ax, ay = (a[0]-x)*scale*111320, (a[1]-y)*111320
        bx, by = (b[0]-x)*scale*111320, (b[1]-y)*111320
        dx, dy = bx-ax, by-ay
        t = max(0, min(1, -(ax*dx+ay*dy)/(dx*dx+dy*dy))) if dx or dy else 0
        near |= math.hypot(ax+t*dx, ay+t*dy) <= 10
        if (a[1] > y) != (b[1] > y) and x < (b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:
            inside = not inside
    return inside, near


def position_membership(longitude, latitude, evidence):
    if longitude is None or latitude is None:
        return "unknown", "official_position_missing"
    x, y = float(longitude), float(latitude)
    if not (math.isfinite(x) and math.isfinite(y) and -180 <= x <= 180 and -90 <= y <= 90):
        return "unknown", "invalid_position"
    features = validate_boundary(evidence)
    bounds = _bounds(evidence["payload"])
    if x < bounds[0]-.001 or x > bounds[2]+.001 or y < bounds[1]-.001 or y > bounds[3]+.001:
        return "outside", "official_position_outside_scb_municipality"
    hit, near = False, False
    for feature in features:
        geometry = feature["geometry"]
        polygons = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
        for rings in polygons:
            results = [_ring(x, y, ring) for ring in rings]
            hit |= results[0][0] and not any(v[0] for v in results[1:])
            near |= any(v[1] for v in results)
    if near:
        return "unknown", "position_within_10m_of_regso_boundary"
    return ("inside", "official_position_in_scb_municipality") if hit else ("outside", "official_position_outside_scb_municipality")


@lru_cache(maxsize=4)
def _bounds(payload):
    points = []
    for f in json.loads(payload)["features"]:
        g = f["geometry"]
        for poly in [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]:
            for ring in poly:
                points.extend(ring)
    return min(p[0] for p in points), min(p[1] for p in points), max(p[0] for p in points), max(p[1] for p in points)


def bind_position(store, boundary):
    status, reason = position_membership(store.longitude, store.latitude, boundary)
    evidence = {"basis": "official_position_scb_regso_2025", "store_id": store.external_id,
                "chain": store.chain.value, "latitude": str(store.latitude), "longitude": str(store.longitude),
                "coordinate_source": store.source_fields.get("coordinate_source"),
                "boundary_source": boundary["source_url"], "boundary_sha256": boundary["source_sha256"],
                "boundary_version": boundary["version"], "boundary_observed_at": boundary["observed_at"],
                "municipality_code": boundary["municipality_code"], "status": status, "reason": reason,
                "uncertainty": "SCB municipal boundary reference 2025-01-01; retailer position; 10m edge exclusion"}
    return store.model_copy(update={"source_fields": {**store.source_fields, "position_municipality_evidence": evidence}})
