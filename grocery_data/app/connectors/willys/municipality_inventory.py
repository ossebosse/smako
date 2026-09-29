"""Municipal selection from the whole official register, independent of prices."""
from grocery_data.app.connectors.willys.parser import WillysParser
from grocery_data.app.services.area_membership import assess_area
from grocery_data.app.services.municipality_geometry import bind_position, validate_boundary


def build_inventory(area, raw, references, boundary, *, parser=None):
    if area.mode != "municipality" or boundary["municipality_code"] != area.municipality_code:
        raise ValueError("municipality/boundary mismatch")
    validate_boundary(boundary)
    documents = [d for d in raw.documents if d.kind == "stores"]
    if len(documents) != 1 or documents[0].http_status != 200:
        raise ValueError("one successful national register required")
    rows = documents[0].json_payload()
    if not isinstance(rows, list) or not rows:
        raise ValueError("missing national register rows")
    ids = [str(r.get("storeId") or "") for r in rows if isinstance(r, dict)]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate register identity; no arbitrary selection")
    stores = (parser or WillysParser()).parse_stores(raw, references, area, filter_locality=False)
    records = []
    for original in stores:
        store = bind_position(original, boundary)
        evidence = assess_area(store, area)
        selected = evidence["status"] == "inside" and store.online_shopping is True
        records.append({"store": store.model_dump(mode="json"),
                        "geographic_evidence": evidence,
                        "collection_selected": selected,
                        "collection_reason": "verified_municipal_online_context" if selected else
                            "no_verified_online_catalog" if evidence["status"] == "inside" else evidence["reason"],
                        "collection_status": "not_collected", "beta_status": "not_activated"})
    represented = {s.external_id for s in stores}
    rejected = [{"row_index": i, "source_store_id": r.get("storeId") if isinstance(r, dict) else None,
                 "status": "unknown", "reason": "missing_store_identity_or_name"}
                for i, r in enumerate(rows) if not isinstance(r, dict)
                or str(r.get("storeId") or "") not in represented]
    return {"area": area.model_dump(mode="json"), "stores": records,
            "registry_rows": len(rows), "unresolved_registry_rows": rejected,
            "selected_store_ids": sorted(r["store"]["external_id"] for r in records if r["collection_selected"]),
            "complete": False,
            "completeness_reason": "all_published_registry_rows_processed; unresolved_rows_retained; no_independent_municipal_total",
            "price_channel": "online_store; not_verified_physical_shelf_prices"}
