"""Closed, read-only qualification of reviewed national-flyer matches.

This is diagnostic evidence for an isolated candidate, never a source strategy
or activation path. The review ledger links exact connector IDs/GTINs and pack
images to particular flyer pages; no fuzzy-name or price-only join is performed.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from decimal import Decimal
from html import unescape
from zoneinfo import ZoneInfo

from grocery_data.app.services.freshness import assess_freshness

STOCKHOLM = ZoneInfo("Europe/Stockholm")


def _plain(value: str) -> str:
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", value)).split())


def qualify_national_offers(
    *, live: dict, raw_rows: list[dict], flyer: dict, reviews: list[dict],
    store: dict, purchase_at: datetime, evaluated_at: datetime,
) -> dict:
    if purchase_at.tzinfo is None or evaluated_at.tzinfo is None:
        raise ValueError("explicit purchase/evaluation timezone required")
    if live["status"] != "healthy" or not live["snapshot_validation"]["passed"]:
        raise ValueError("source candidate did not pass existing validation")
    if not live["completion"] or any(not x["complete"] for x in live["completion"]):
        raise ValueError("incomplete collection")
    if (
        flyer["countryCode"] != "SE"
        or flyer["subcategory"] != "Reklamblad för samtliga butiker i Sverige"
        or "i alla butiker" not in flyer["name"]
    ):
        raise ValueError("flyer has no explicit national validity")
    if store.get("city") != "Lund" or not store.get("canonical_url", "").startswith(
        "https://www.lidl.se/s/sv-SE/butiker/lund/"
    ) or not store.get("address"):
        raise ValueError("verified physical Lund store required")
    by_id = {x["id"]: x for x in live["products"]}
    if len(by_id) != len(live["products"]):
        raise ValueError("duplicate source identity")
    review_ids = [x["product_id"] for x in reviews]
    if len(review_ids) != len(set(review_ids)):
        raise ValueError("duplicate review identity")
    raw_by_id = {str(x["raw"]["gridbox"]["data"]["productId"]): x for x in raw_rows}
    pages = {p["id"]: p for p in flyer["pages"]}
    accepted, rejected = [], []
    purchase_day = purchase_at.astimezone(STOCKHOLM).date().isoformat()
    for product_id, row in by_id.items():
        review = next((x for x in reviews if x["product_id"] == product_id), None)
        reasons = []
        if review is None:
            rejected.append({"id": product_id, "reason": "not_in_reviewed_flyer_set"})
            continue
        if review["flyer_id"] != flyer["id"] or review["page_id"] not in pages:
            reasons.append("flyer_page_identity_changed")
        if review["match_method"] != "reviewed_brand_variant_pack_front_and_source_identity":
            reasons.append("no_reviewed_identity_match")
        raw = raw_by_id.get(product_id)
        if raw is None:
            reasons.append("missing_raw_identity")
        else:
            data = raw["raw"]["gridbox"]["data"]
            meta = raw["raw"]["gridbox"].get("meta", {})
            if meta.get("ean") != review["gtin"] or meta.get("fullTitle") != review["source_name"]:
                reasons.append("raw_product_identity_changed")
            if datetime.fromisoformat(raw["observed_at"]) != datetime.fromisoformat(row["observed_at"]):
                reasons.append("raw_and_normalized_observation_differ")
            if data.get("image") != review["source_image_url"]:
                reasons.append("pack_image_identity_changed")
            if str(data["productId"]) != review["product_id"]:
                reasons.append("product_identity_changed")
            text = _plain(data.get("keyfacts", {}).get("description", ""))
            for required in review.get("source_required_text", []):
                if required not in text:
                    reasons.append("source_variant_or_condition_changed")
            # Product-level HTML is separate from price.discount and cannot be
            # discarded when it contains a purchase limit or a private benefit.
            if re.search(r"personlig|aktiver|kupong", text, re.IGNORECASE):
                reasons.append("unsupported_product_level_eligibility")
            limits = re.findall(r"\bMax\s+(\d+)\s+förp\./hushåll", text, re.IGNORECASE)
            if re.search(r"\bmax\b", text, re.IGNORECASE) and not limits:
                reasons.append("unresolved_product_level_limit")
            if limits and set(map(int, limits)) != {review["max_packages"]}:
                reasons.append("source_and_flyer_limits_disagree")
        for field, expected in (
            ("gtin", review["gtin"]), ("name", review["source_name"]),
            ("package_unit", review["unit"]), ("quantity_confidence", "exact"),
            ("sale_model", "fixed_package"), ("canonical_food", review["canonical_food"]),
        ):
            if row.get(field) != expected:
                reasons.append(f"{field}_mismatch")
        if Decimal(row.get("package_quantity") or "0") != Decimal(review["quantity"]):
            reasons.append("package_quantity_mismatch")
        price = Decimal(row.get("sale_price") or "0")
        if not price.is_finite() or price <= 0 or price != Decimal(review["price"]):
            reasons.append("purchase_price_mismatch")
        fields = row["source_fields"]
        if fields["member_offer_scope"] != "public" or fields["activation_required"]:
            reasons.append("eligibility_not_public")
        if fields["geographic_restrictions"]:
            reasons.append("unresolved_local_exception")
        if not flyer["offerStartDate"] <= purchase_day <= flyer["offerEndDate"]:
            reasons.append("outside_flyer_purchase_window")
        start = datetime.fromisoformat(fields["price_window_start_at"])
        end = datetime.fromisoformat(fields["price_window_end_at"])
        if not start <= purchase_at <= end:
            reasons.append("outside_product_purchase_window")
        if not assess_freshness(datetime.fromisoformat(row["observed_at"]), now=evaluated_at).usable:
            reasons.append("source_observation_stale")
        if review["deposit_status"] != "not_applicable_verified_non_beverage_package":
            reasons.append("deposit_not_resolved")
        if reasons:
            rejected.append({"id": product_id, "reason": ";".join(reasons)})
            continue
        accepted.append({
            **row, "review": review, "physical_store": store,
            "coverage": "offers_only", "geographic_basis": "explicit_national_flyer",
            "national_flyer_id": flyer["id"], "max_packages": review["max_packages"],
            "stock_verified": False, "ordinary_price_verified": False,
            "valid_from": max(flyer["offerStartDate"], start.astimezone(STOCKHOLM).date().isoformat()),
            "valid_to": min(flyer["offerEndDate"], end.astimezone(STOCKHOLM).date().isoformat()),
            "eligible_for_isolated_planning": True,
        })
    return {
        "schema": "lidl-national-offer-candidate-v1", "promoted": False,
        "built_at": evaluated_at.isoformat(), "purchase_at": purchase_at.isoformat(),
        "source_mode": live["mode"], "source_observations_preserved": True,
        "source_rows": live["counts"]["source_rows"], "source_parsed": len(by_id),
        "source_quarantined": live["counts"]["quarantined"],
        "accepted_count": len(accepted), "excluded_count": len(rejected),
        "exclusion_reasons": dict(Counter(x["reason"] for x in rejected)),
        "products": accepted, "excluded": rejected,
    }


def require_within_purchase_limits(candidate: dict, packages_by_product: dict[str, int]) -> None:
    """No fallback to a guessed regular price beyond a flyer purchase cap."""
    by_id = {x["id"]: x for x in candidate["products"]}
    for product_id, count in packages_by_product.items():
        if product_id not in by_id or type(count) is not int or count < 1:
            raise ValueError("invalid candidate purchase identity/count")
        limit = by_id[product_id]["max_packages"]
        if limit is not None and count > limit:
            raise ValueError("purchase exceeds verified flyer cap; no regular fallback exists")
