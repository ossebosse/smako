"""Offline same-observation ICA normalization audit; no provider calls."""

import argparse
import asyncio
import json
from collections import Counter
from pathlib import Path

from app.providers.primat import PrimatPriceProvider
from app.services.primat_phase_c_export import FrozenExternalCacheBundle, write_closed_json

from grocery_data.app.services.durable_files import atomic_write_bytes


def summarize(raw, products):
    result = {}
    for sid in sorted({r["store_id"] for r in raw}):
        rows = [r for r in raw if r["store_id"] == sid]
        normalized = [p for p in products if p.store_id == "ica:" + sid]
        identities = {p.product_id for p in normalized}
        classes = {}
        for r in rows:
            reasons = []
            promotion = PrimatPriceProvider._promotion_rejection(r)
            if promotion:
                reasons.append(promotion)
            p = next((p for p in normalized if p.product_id == r["product_id"]), None)
            if r["product_id"] not in identities:
                reasons.append("no_safe_ordinary_or_standalone_price")
            elif not p.package_quantity:
                reasons.append("package_semantics_unproven")
            elif str(p.quantity_confidence) in {"unknown", "estimated"}:
                reasons.append("quantity_not_verified")
            if not r.get("gtin"):
                reasons.append("missing_gtin_separate_identity")
            for reason in reasons:
                group = classes.setdefault(reason, {"count": 0, "samples": []})
                group["count"] += 1
                if len(group["samples"]) < 3:
                    group["samples"].append(
                        {
                            k: r.get(k)
                            for k in ("product_id", "name", "brand", "amount", "unit", "package")
                        }
                    )
        fixed = [p for p in normalized if str(p.sale_model) in {"fixed_package", "sold_by_piece"}]
        unit = [
            p
            for p in fixed
            if p.package_quantity
            and p.package_unit
            and str(p.quantity_confidence) in {"exact", "derived"}
        ]
        result[sid] = {
            "raw_unique_rows": len(rows),
            "normalized_retained_rows": len(normalized),
            "rows_with_gtin": sum(bool(p.gtin) for p in normalized),
            "rows_without_gtin": sum(not p.gtin for p in normalized),
            "package_quantity_rows": sum(bool(p.package_quantity) for p in normalized),
            "package_dimension_rows": sum(bool(p.package_unit) for p in normalized),
            "valid_search_unit_price_rows": len(unit),
            "fixed_checkout_price_rows": len(fixed),
            "raw_ordinary_rows": sum(bool(r["prices"].get("regular")) for r in rows),
            "raw_campaign_rows": sum(bool(r["prices"].get("offer")) for r in rows),
            "raw_member_rows": sum(bool(r["prices"].get("member")) for r in rows),
            "retained_campaign_rows": sum(
                any(str(o.kind) == "campaign" for o in p.active_offers()) for p in normalized
            ),
            "retained_member_rows": sum(
                any(str(o.eligibility).casefold() == "member" for o in p.active_offers())
                for p in normalized
            ),
            "retained_multibuy_rows": sum(
                any(o.required_packages > 1 for o in p.active_offers()) for p in normalized
            ),
            "sale_models": dict(Counter(str(p.sale_model) for p in normalized)),
            "source_observed_at": sorted(
                {p.source_provenance.source_observed_at.isoformat() for p in normalized}
            ),
            "provider_confirmed_at": sorted({r.get("confirmed_at") for r in rows}),
            "rejections_or_limitations": classes,
        }
    grouped = {}
    for p in products:
        if p.gtin and p.package_quantity:
            key = (p.gtin, p.package_quantity, p.package_unit, p.sale_model)
            grouped.setdefault(key, set()).add(p.store_id)
    result["exact_identity"] = {
        "cross_context_groups": sum(len(v) > 1 for v in grouped.values()),
        "rows_in_cross_context_groups": sum(len(v) for v in grouped.values() if len(v) > 1),
    }
    return result


async def audit(root):
    raw_doc = json.loads((root / "raw-private.json").read_text(encoding="utf-8-sig"))
    raw = raw_doc["rows"]
    before = FrozenExternalCacheBundle.model_validate_json(
        (root / "candidate-before.json").read_text(encoding="utf-8-sig")
    )
    provider = PrimatPriceProvider("offline-audit-no-live-credential")
    provider._stores = {s.store_id: s for s in before.stores}
    provider._observed_at = before.captured_at
    provider._observation_id = before.stores[0].source_provenance.source_snapshot_id
    try:
        products = tuple(p for r in raw if (p := provider._parse_product(r)) is not None)
    finally:
        await provider.aclose()
    after = FrozenExternalCacheBundle(
        postal_code=before.postal_code,
        captured_at=before.captured_at,
        stores=before.stores,
        products=products,
    )
    write_closed_json(root / "candidate-after.json", after)
    report = {
        "observation_preserved": after.captured_at == before.captured_at,
        "provider_calls": 0,
        "raw_occurrences": raw_doc["occurrences"],
        "before": summarize(raw, before.products),
        "after": summarize(raw, after.products),
    }
    atomic_write_bytes(
        root / "quality-audit.json", json.dumps(report, ensure_ascii=False, indent=2).encode()
    )
    print(
        json.dumps(
            {
                k: {
                    s: {
                        x: v
                        for x, v in d.items()
                        if x not in {"rejections_or_limitations", "provider_confirmed_at"}
                    }
                    for s, d in report[k].items()
                }
                for k in ("before", "after")
            }
        )
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--evidence-root", type=Path, required=True)
    asyncio.run(audit(p.parse_args().evidence_root))
