"""Evidence-bound flyer review feeding the existing ICA parser/OWN pipeline.

No OCR result or fuzzy match is an approval. No scheduling or price activation.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime

from grocery_data.app.domain import RawBatch, RawFetch
from grocery_data.app.domain.identifiers import normalize_gtin


def review_key(evidence: dict) -> str:
    """Bind all relevant evidence, including scope, dates, OCR and observations."""
    return hashlib.sha256(json.dumps(evidence, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


def review_blockers(evidence: dict, review: dict, *, account_id: str) -> list[str]:
    blockers = []
    if review.get("evidence_sha256") != review_key(evidence):
        blockers.append("changed_or_unreviewed_evidence")
    if review.get("decision") != "approved":
        blockers.append("review_not_approved")
    if account_id not in evidence.get("official_store_ids", []):
        blockers.append("store_scope_unproven")
    for field in ("issue_id", "pdf_sha256", "page", "box", "bbox", "observed_at", "source_url"):
        if not evidence.get(field):
            blockers.append("missing_evidence_" + field)
    terms = review.get("terms", {})
    if review.get("terms_sha256") != review_key(terms):
        blockers.append("changed_reviewed_terms")
    for field in ("gtin", "name", "brand", "package", "price", "valid_from", "valid_to",
                  "date_evidence", "variant_evidence", "quantity", "limit_evidence", "deposit_evidence"):
        if not terms.get(field):
            blockers.append("unverified_" + field)
    if terms.get("eligibility") not in {"public", "general_member"}:
        blockers.append("eligibility_unverified_or_personal")
    if terms.get("limit_status") not in {"explicit_cap", "verified_no_published_cap"}:
        blockers.append("purchase_limit_unverified")
    if terms.get("limit_status") == "explicit_cap" and not terms.get("max_purchases"):
        blockers.append("purchase_limit_missing")
    if terms.get("deposit_status") == "known":
        from grocery_data.app.domain.promotion_pricing import DepositContract
        try:
            deposit = DepositContract.model_validate(terms.get('deposit_contract'))
            if deposit.gtin != terms.get('gtin'):
                blockers.append('deposit_variant_mismatch')
        except ValueError:
            blockers.append('deposit_amount_or_inclusion_unverified')
    elif terms.get("deposit_status") != "verified_not_applicable":
        blockers.append("deposit_checkout_contract_unverified")
    return blockers


def compare_advertisement(ad: dict, row: dict | None) -> dict:
    """Compare a manually linked campaign, never choose a GTIN or a price.

    The ad's coordinates and extracted values must be retained by the caller.
    Identical campaign-level display terms do not prove purchasable variants.
    """
    from grocery_data.app.connectors.ica.parser import _promotion

    if ad.get("not_relevant"):
        return {"status": "not_relevant", "reason": ad["not_relevant"]}
    if row is None:
        return {"status": "new_candidate", "reason": "no_structured_campaign_link",
                "price_import": False}
    try:
        offer = _promotion(row)
    except ValueError as exc:
        return {"status": "blocked", "reason": str(exc), "price_import": False}
    differences = {}
    for field, value in {"price": float(offer.price) if offer.price else None,
                         "quantity": offer.quantity or 1, "member": offer.member_only,
                         "max_purchases": offer.max_quantity}.items():
        if field in ad and ad[field] != value:
            differences[field] = {"flyer": ad[field], "structured": value}
    if ad.get("valid_to") != (offer.valid_to.isoformat() if offer.valid_to else None):
        differences["valid_to"] = {"flyer": ad.get("valid_to"), "structured": str(offer.valid_to)}
    if ad.get("valid_from") and offer.valid_from and ad["valid_from"] != offer.valid_from.isoformat():
        differences["valid_from"] = {"flyer": ad["valid_from"], "structured": str(offer.valid_from)}
    if ad.get("store_condition"):
        differences["store_condition"] = {"flyer": ad["store_condition"], "structured": "not_verified"}
    return {"status": "needs_review" if differences else "already_covered",
            "reason": "conflicting_or_unverified_terms" if differences else "same_campaign_display_terms",
            "differences": differences, "price_import": False,
            "coverage_level": "campaign_only_not_variant_or_checkout_qualification"}


def reviewed_flyer_batch(evidence: dict, review: dict, *, account_id: str) -> RawBatch:
    """Review -> sanitized ICA source row -> existing parser, preserving age.

    The caller must still run the normal collector, quality and OWN gates.
    This function grants neither snapshot promotion nor PriceUniverse entry.
    """
    blockers = review_blockers(evidence, review, account_id=account_id)
    if blockers:
        raise ValueError(", ".join(blockers))
    terms = review["terms"]
    normalize_gtin(terms["gtin"])
    # Observation is evidence age, not product/campaign identity. Re-observing
    # unchanged pixels/terms must not create a supposedly new price each run.
    identity = "flyer:" + review_key({
        **{k: v for k, v in evidence.items() if k != 'observed_at'},
        'terms_sha256': review['terms_sha256']})
    row = {
        "id": identity,
        "details": {"name": terms["name"], "brand": terms["brand"],
                    "packageInformation": terms["package"]},
        "validFrom": terms["valid_from"], "validTo": terms["valid_to"],
        "eans": [{"id": terms["gtin"]}],
        "stores": [{"accountNumber": account_id, "storeInd": True}],
        "traits": ["Stammis"] if terms["eligibility"] == "general_member" else [],
        "restriction": (f"Max {terms['max_purchases']} köp/hushåll"
                        if terms["limit_status"] == "explicit_cap" else ""),
        "parsedMechanics": {"benefitType": "FIXED", "quantity": terms["quantity"],
                            "value1": str(terms["price"]), "value2": "0"},
    }
    if terms.get('deposit_status') == 'known':
        row['reviewedDeposit'] = terms['deposit_contract']
    from grocery_data.app.connectors.ica.parser import IcaParser
    from grocery_data.app.domain import SourceStore

    batch = RawBatch(chain="ica", documents=(RawFetch(
        chain="ica", store_external_id=account_id, kind="offers_page", method="GET",
        url=evidence["source_url"], fetched_at=datetime.fromisoformat(evidence["observed_at"]),
        http_status=200, content_type="application/json", connector_version="ica-reviewed-flyer-v1",
        payload=json.dumps({"offers": {"weeklyOffers": [row]},
                            "review_evidence": evidence, "review": review}, ensure_ascii=False).encode()),))
    parsed = IcaParser().parse_catalog(batch, [identity], SourceStore(
        chain="ica", external_id=account_id, name="Verified official flyer scope",
        city="", raw_reference=identity, coverage="offers_only"))
    if parsed.failures or not parsed.products or not parsed.products[0].package_quantity:
        raise ValueError("reviewed flyer failed existing ICA exact-package parser")
    return batch
