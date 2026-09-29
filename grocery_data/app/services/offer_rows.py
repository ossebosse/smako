"""Explicit, opt-in row-approved offers contract; never full-snapshot health.

The original fetch and its 95% assessment are retained separately. A dedicated
scope can publish independently verified rows, with every other row quarantined.
Unknown parser/schema failures stop the entire candidate rather than being
reclassified as harmless row failures.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date
from decimal import Decimal
from zoneinfo import ZoneInfo

from grocery_data.app.domain import ParseFailure, ProductParseResult
from grocery_data.app.domain.campaign_validity import CampaignEvidence
from grocery_data.app.domain.identifiers import normalize_gtin

CONTRACT = "partial-row-approved-offers-v1"
COOP_POLICIES = {"coop-physical-structured-v1", "coop-xtra-pdf-text-v1"}
LIDL_POLICY = "lidl-national-reviewed-document-text-v1"
LIDL_POLICIES = {LIDL_POLICY, "lidl-national-qualified-document-text-v2"}
WILLYS_FLYER_POLICY = "willys-flyer-reviewed-text-v1"
WILLYS_FLYER_POLICIES = {WILLYS_FLYER_POLICY, "willys-flyer-validated-text-v2"}
CITYGROSS_POLICY = "citygross-store-online-offers-v1"
HEMKOP_POLICY = "hemkop-physical-singleton-offers-v1"
LOCAL_FAILURES = (
    "deposit_amount_unverified:",
    "ICA offer requires review of date, audience or deposit condition",
    "ICA unrecognized purchase restriction",
    "ICA additional eligibility condition requires review",
    "ICA conflicting campaign evidence",
)


def row_blockers(product) -> list[str]:
    reasons = []
    fields = product.source_fields
    from grocery_data.app.services.source_purchase_terms import bound_purchase_terms
    bound = bound_purchase_terms(product) if product.chain.value in {'ica', 'coop', 'hemkop'} else None
    if product.chain.value in {'ica', 'coop', 'hemkop'} and (fields.get('purchase_terms')
            or any(o.source_payload.get('purchase_terms') for o in product.offers)) and not bound:
        reasons.append('purchase_terms_source_mismatch')
    if product.chain.value == 'ica':
        reasons.extend(fields.get('purchase_blockers', []))
    open_group = bound and bound.usage == 'variant_selection_required'
    rate_ad = fields.get('document_product_binding') or {}
    verified_rate = (product.chain.value == 'willys'
                     and fields.get('willys_flyer_policy') == 'willys-flyer-validated-text-v2'
                     and rate_ad.get('price_basis_unit') == 'kg'
                     and rate_ad.get('exact_checkout_supported') is False
                     and product.sale_unit == 'kg' and product.package_quantity is None
                     and product.package_unit is None
                   and len(product.offers) == 1
                   and rate_ad.get('comparison_unit') == 'kg'
                   and Decimal(str(rate_ad.get('comparison_price', 0))) == product.offers[0].price
                   and product.offers[0].source_payload.get('price_basis_unit') == 'kg')
    from grocery_data.app.domain.purchase_terms import PurchaseTerms
    for offer in product.offers:
        if offer.source_payload.get('purchase_terms'):
            terms = PurchaseTerms.model_validate(offer.source_payload['purchase_terms'])
            ad_terms = rate_ad.get('purchase_terms')
            if product.chain.value == 'willys' and terms.model_dump(mode='json') != ad_terms:
                reasons.append('purchase_terms_source_mismatch')
    if not fields.get("verified_store_scope"):
        reasons.append("store_scope_unverified")
    if product.chain.value == "citygross":
        reasons.extend(fields.get("purchase_blockers", []))
        if (fields.get("citygross_offer_policy") != CITYGROSS_POLICY
                or fields.get("variant_count") != 1
                or fields.get("source_variant_id") != product.external_product_id
                or fields.get("source_channel") != "online_price"
                or not product.external_product_id):
            reasons.append("exact_source_variant_unverified")
        if not product.gtin:
            reasons.append("exact_single_variant_unverified")
        else:
            try:
                normalize_gtin(product.gtin)
            except ValueError:
                reasons.append("invalid_gtin")
    elif product.chain.value == "lidl":
        reasons.extend(fields.get("purchase_blockers", []))
        if (fields.get("lidl_offer_policy") not in LIDL_POLICIES or not fields.get("document_product_binding")
                or fields.get("variant_count") != 1
                or (not product.gtin and not (rate_ad.get("identity_method")
                    and rate_ad.get("product_id") == product.external_product_id
                    and rate_ad.get("source_name") == product.name
                    and rate_ad.get("brand") == product.brand))):
            reasons.append("reviewed_national_product_unverified")
    elif product.chain.value == "willys":
        reasons.extend(fields.get("purchase_blockers", []))
        if (fields.get("willys_flyer_policy") == WILLYS_FLYER_POLICY
                and product.package_unit == "st" and product.package_quantity == 1):
            reasons.append("piece_purchase_contract_not_supported")
        ad = fields.get("document_product_binding") or {}
        if (fields.get("willys_flyer_policy") not in WILLYS_FLYER_POLICIES
                or not fields.get("document_sha256") or fields.get("variant_count") != 1
                or product.name not in ad.get("names", []) or product.gtin is not None
                or product.package_quantity != ad.get("package_quantity")
                or product.package_unit != ad.get("package_unit")
                or product.brand != (ad.get("brand") or None)
                or len(product.offers) != 1 or str(product.offers[0].price) != ad.get("price")
                or product.offers[0].member_only != ad.get("member_only")
                or product.offers[0].max_quantity != ad.get("max_quantity")
                or product.offers[0].quantity != ad.get("required_packages")
                or not product.offers[0].valid_to or product.offers[0].valid_to.isoformat() != ad.get("valid_to")
                or not product.offers[0].valid_from or product.offers[0].valid_from.isoformat() != ad.get("valid_from")):
            reasons.append("reviewed_flyer_advertisement_unverified")
    elif product.chain.value == "hemkop":
        reasons.extend(fields.get('purchase_blockers', []))
        if (fields.get('hemkop_physical_policy') != HEMKOP_POLICY
                or (not open_group and (fields.get('variant_count') != 1 or not fields.get('source_variant_id')))
                or fields.get('source_query', {}).get('q') != product.store_external_id):
            reasons.append('exact_physical_campaign_variant_unverified')
    elif product.chain.value == "coop":
        reasons.extend(fields.get("purchase_blockers", []))
        if not bound and product.package_unit == "st" and product.package_quantity == 1:
            reasons.append("piece_purchase_contract_not_supported")
        if (fields.get("coop_physical_policy") not in COOP_POLICIES
                or (not open_group and fields.get("variant_count") != 1) or not fields.get("source_variant_id")
                or not product.external_product_id):
            reasons.append("exact_source_variant_unverified")
    elif open_group:
        pass  # Priceable only as an explicitly confirmed campaign choice, never a recipe variant.
    elif fields.get("variant_count") != 1 or not product.gtin:
        reasons.append("exact_single_variant_unverified")
    else:
        try:
            normalize_gtin(product.gtin)
        except ValueError:
            reasons.append("invalid_gtin")
    if product.chain.value == 'lidl' and rate_ad.get('price_basis_unit') == 'kg':
        terms = rate_ad.get('purchase_terms')
        verified_rate = bool(terms and product.sale_unit == 'kg' and product.package_quantity is None
            and product.package_unit is None and len(product.offers) == 1
            and product.offers[0].source_payload.get('purchase_terms') == terms
            and product.offers[0].source_payload.get('price_basis_unit') == 'kg'
            and str(product.offers[0].price) == rate_ad.get('price'))
    group_terms = rate_ad.get('purchase_terms') or {}
    verified_group = (product.chain.value == 'willys' and group_terms.get('identity_scope') == 'campaign_group'
        and group_terms.get('variant_selection') == 'required' and rate_ad.get('status') == 'qualified'
        and len(product.offers) == 1 and product.offers[0].source_payload.get('purchase_terms') == group_terms)
    if not (bound or verified_rate or verified_group) and (not product.package_quantity or not product.package_unit or product.sale_unit != "st"):
        reasons.append("fixed_purchase_package_unverified")
    if len(product.offers) != 1 or not product.offers[0].price or not product.offers[0].valid_to:
        reasons.append("bounded_checkout_contract_unverified")
    if product.regular_price is not None:
        reasons.append("unverified_ordinary_checkout_price")
    return reasons


def qualify_rows(parsed: ProductParseResult, *, store, observed_at, original_parsed=None) -> tuple[ProductParseResult, dict]:
    original_parsed = original_parsed or parsed
    shared = []
    coop = store.chain.value == "coop"
    citygross = store.chain.value == "citygross"
    lidl = store.chain.value == "lidl"
    willys = store.chain.value == "willys"
    hemkop = store.chain.value == "hemkop"
    chain_policy = store.source_fields.get("offer_policy", "coop-physical-structured-v1")
    pdf = coop and chain_policy == "coop-xtra-pdf-text-v1"
    parser_version = (("willys-flyer-text-v2" if chain_policy == "willys-flyer-validated-text-v2" else "willys-flyer-text-v1") if willys else "lidl-parser-v4" if lidl else "citygross-parser-v4" if citygross else "xtra-pdf-text-v2" if pdf
                      else "coop-parser-v5" if coop else "hemkop-physical-offers-v2" if hemkop else "ica-parser-v8")
    physical_proven = (bool(store.source_fields.get("store_page_path"))
                       and bool(store.source_fields.get("ledger_account_number"))
                       and not store.source_fields.get("online_fulfilment_store_id")) if coop else bool(store.source_fields.get("official_store_url"))
    if pdf:
        physical_proven = (store.source_fields.get("concept") == "X:-tra"
                           and bool(store.source_fields.get("pdf_sha256"))
                           and bool(store.source_fields.get("ledger_account_number"))
                           and str(store.source_fields.get("official_store_url", "")).startswith("https://x-tra.se/butiker/")
                           and not store.source_fields.get("online_fulfilment_store_id"))
    if citygross:
        physical_proven = (
            store.source_fields.get("offer_policy") == CITYGROSS_POLICY
            and store.source_fields.get("price_context_verified") is True
            and str(store.source_fields.get("store_number")) == store.external_id
            and bool(store.source_fields.get("site_id"))
            and bool(store.source_fields.get("store_page_url"))
            and store.price_context_type is not None
            and store.price_context_type.value == "online_store"
        )
    if not store.address or not store.city or not physical_proven:
        shared.append("official_physical_store_unverified")
    for failure in parsed.failures:
        # Known unsupported Coop rows retain their facts and purchase_blockers.
        # A parsing exception is not a safe local condition failure.
        local_failures = ('Hemkop physical row requires review:',) if hemkop else () if coop or citygross else LOCAL_FAILURES
        if not failure.error_message.startswith(local_failures):
            shared.append("unclassified_parser_or_shared_source_failure:" + failure.error_message)
    failures = list(parsed.failures)
    accepted = []
    decisions = []
    for product in parsed.products:
        reasons = row_blockers(product)
        if coop and product.source_fields.get("coop_physical_policy") != chain_policy:
            reasons.append("source_policy_store_mismatch")
        if pdf and not reasons:
            from grocery_data.app.connectors.coop.xtra_pdf import row_evidence_matches

            if not row_evidence_matches(product, store):
                reasons.append("pdf_advertisement_binding_mismatch")
        if product.chain != store.chain or product.store_external_id != store.external_id:
            reasons.append("source_product_store_mismatch")
        if shared:
            reasons = [*reasons, "shared_source_failure"]
        decisions.append({"source_id": product.external_product_id, "blockers": reasons})
        if reasons:
            failures.append(ParseFailure(raw_record_reference=product.raw_reference,
                error_code="row_qualification", error_message=";".join(reasons),
                parser_version=parser_version,
                sample={"id": product.external_product_id, "name": product.name}))
        else:
            offer = product.offers[0]
            # No retrospective start inference. A published current offer is
            # observed from this local date, preserving an explicit future start.
            start = offer.valid_from or product.fetched_at.astimezone(ZoneInfo("Europe/Stockholm")).date()
            if start > offer.valid_to:
                failures.append(ParseFailure(raw_record_reference=product.raw_reference,
                    error_code="row_qualification", error_message="expired_at_observation",
                    parser_version=parser_version, sample={"id": product.external_product_id}))
                decisions[-1]["blockers"] = ["expired_at_observation"]
                continue
            # Preserve null valid_from. Applicability from observation is a
            # separate, source-bound fact, not a fabricated campaign date.
            campaign = CampaignEvidence(store_external_id=store.external_id,
                offer_id=product.external_product_id, source_reference=product.raw_reference,
                observed_current_at=product.fetched_at, checked_at=product.fetched_at)
            accepted.append(product.model_copy(update={
                "source_fields": {**product.source_fields, **({"coop_purchase_qualified": True} if coop else {})},
                "offers": (offer.model_copy(update={
                "source_payload": {**offer.source_payload,
                    "campaign_evidence": campaign.model_dump(mode="json")}}),)}))
    evidence = {
        "contract": CONTRACT, "complete": False, "store_id": store.external_id,
        "observed_at": observed_at.isoformat(), "shared_blockers": shared,
        "full_parse": {"parsed": len(original_parsed.products), "quarantined": len(original_parsed.failures),
                       "denominator": len(original_parsed.products) + len(original_parsed.failures), "threshold": .95},
        "accepted_ids": sorted(p.external_product_id for p in accepted), "decisions": decisions,
        "local_failures": [f.model_dump(mode="json") for f in parsed.failures],
    }
    if coop or citygross or lidl or willys or hemkop:
        evidence["chain_policy"] = chain_policy
    evidence["evidence_sha256"] = hashlib.sha256(json.dumps(evidence, sort_keys=True).encode()).hexdigest()
    return ProductParseResult(products=accepted, failures=failures), evidence


def contract_allows_publication(evidence: dict, *, metrics, scope_key: str, chain: str, coverage: str) -> bool:
    original = {k: v for k, v in evidence.items() if k != "evidence_sha256"}
    if evidence.get("evidence_sha256") != hashlib.sha256(json.dumps(original, sort_keys=True).encode()).hexdigest():
        return False
    if (evidence.get("contract") != CONTRACT or evidence.get("complete") is not False
            or evidence.get("shared_blockers") or not scope_key.endswith(":offer-rows")
            or chain not in {"ica", "coop", "citygross", "lidl", "willys", "hemkop"} or coverage != "offers_only"
            or chain == "hemkop" and evidence.get("chain_policy") != HEMKOP_POLICY
            or chain == "coop" and evidence.get("chain_policy") not in COOP_POLICIES
            or chain == "citygross" and evidence.get("chain_policy") != CITYGROSS_POLICY
            or chain == "lidl" and evidence.get("chain_policy") not in LIDL_POLICIES
            or chain == "willys" and evidence.get("chain_policy") not in WILLYS_FLYER_POLICIES
            or chain == "ica" and evidence.get("chain_policy") is not None):
        return False
    ids = evidence.get("accepted_ids", [])
    return bool(ids) and len(set(ids)) == len(ids) == metrics.products_parsed and not metrics.stores_failed and not metrics.http_error_count


def period_status(valid_from: date | None, valid_to: date | None, purchase_date: date) -> str:
    if valid_to is None:
        return "unknown"
    if valid_from and valid_from > purchase_date:
        return "future"
    return "expired" if valid_to < purchase_date else "current"
