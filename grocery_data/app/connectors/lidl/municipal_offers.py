"""Strict document-text bridge over the existing regional Lidl parser.

Exact compound identities qualified by closed text rules, or existing hash-bound
manual reviews, can acquire physical-store scope. Unknown cases remain blocked.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from grocery_data.app.connectors.lidl.connector import LidlConnector
from grocery_data.app.connectors.lidl.document_qualification import national_metadata, qualify
from grocery_data.app.connectors.lidl.parser import LidlParser
from grocery_data.app.domain import (
    ProductParseResult,
    PromotionType,
    RawBatch,
    RawFetch,
    SourceCollectionAudit,
    TransportMetrics,
)
from grocery_data.app.services.offer_rows import qualify_rows

POLICY = "lidl-national-qualified-document-text-v2"
POLICIES = {POLICY, "lidl-national-reviewed-document-text-v1"}
REVIEW = Path(__file__).parent / "fixtures/municipal_document_text_20260923.json"


def review_document(publication, pdf, *, review=None):
    import pymupdf

    review = review or json.loads(REVIEW.read_bytes())
    flyer = publication.json_payload()["flyer"]
    national = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m[1], 16)), flyer["subcategory"])
    if (publication.http_status != 200 or publication.url != "https://endpoints.leaflets.schwarz/v4/flyer"
            or flyer["id"] != review["publication_id"] or not flyer["isActive"]
            or flyer["countryCode"] != "SE" or flyer["status"] != "current"
            or national != "Reklamblad för samtliga butiker i Sverige"
            or flyer["pdfUrl"] != review["pdf_url"]
            or hashlib.sha256(pdf).hexdigest() != review["pdf_sha256"]):
        raise ValueError("current_national_document_review_required")
    with pymupdf.open(stream=pdf, filetype="pdf") as document:
        for row in review["products"]:
            text = document[row["page_number"] - 1].get_text(clip=pymupdf.Rect(row["bbox"]))
            if hashlib.sha256(text.encode()).hexdigest() != row["text_sha256"] or text != row["text"]:
                raise ValueError("reviewed_document_text_changed")
            if not (flyer["offerStartDate"] <= row["valid_from"] <= row["valid_to"] <= flyer["offerEndDate"]):
                raise ValueError("reviewed_period_outside_publication")
    return review


class MunicipalLidlOfferConnector(LidlConnector):
    """Retained evidence adapter; collection transport is shared, never per store."""

    def __init__(self, *, store, registry, catalog, publication, pdf):
        self.parser = LidlParser()
        self.review = national_metadata(publication, pdf)
        if REVIEW.exists():
            legacy = json.loads(REVIEW.read_bytes())
            if (legacy['pdf_sha256'] == self.review['pdf_sha256']
                    and legacy['publication_id'] == self.review['publication_id']):
                self.review['products'] = review_document(publication, pdf)['products']
        self.pdf = pdf
        self.publication = publication
        self.store = store.model_copy(update={"source_fields": {
            **store.source_fields, "offer_policy": POLICY}})
        self.locator = RawBatch(chain="lidl", documents=(RawFetch.model_validate(registry["sitemap"]),))
        self.catalog = catalog.model_copy(update={"transport": TransportMetrics(), "catalog_completion": None})
        self.regional = self.parser._regional_offer_context(reference="official-public-context", requested_city="Sverige")
        self.row_acceptance = None

    def collection_policy_audit(self):
        return SourceCollectionAudit(source_policy=self.source_policy, operator_opt_in=True,
                                     store_allowlist=(self.store.external_id,))

    async def fetch_stores(self, area):
        return self.locator

    def parse_stores(self, raw, references, area):
        return [self.store]

    def catalog_eligible(self, store):
        return store == self.store

    async def fetch_catalog(self, store):
        return self.catalog

    async def aclose(self):
        pass

    def parse_catalog(self, raw, references, store):
        extracted = self.parser.parse_catalog(raw, references, self.regional)
        source_rows = {}
        for document in raw.documents:
            for item in document.json_payload().get("items", []):
                row = item.get("gridbox", {}).get("data", {})
                source_rows.setdefault(str(row.get("productId")), []).append(row)
        reviewed = {r["product_id"]: r for r in self.review["products"]}
        automatic, self.document_decisions = qualify(self.publication, self.pdf, extracted.products, source_rows)
        for proof in automatic:
            old = reviewed.get(proof['product_id'])
            if old and (Decimal(str(old['price'])) != Decimal(str(proof['price'])) or any(
                    old[k] != proof[k] for k in ('member_only', 'package_text', 'valid_from', 'valid_to'))):
                reviewed.pop(proof['product_id'])
                continue
            reviewed[proof['product_id']] = proof
        candidates = []
        # Parser failures remain quarantined, never qualify for publication.
        # A page/envelope failure blocks the whole source; only records with an
        # explicit item reference may be handled independently.
        shared_failures = [f for f in extracted.failures if "#items[" not in f.raw_record_reference]
        for product in extracted.products:
            proof = reviewed.get(product.external_product_id)
            blockers = []
            rows = source_rows.get(product.external_product_id, [])
            if not proof:
                blockers.append("no_reviewed_product_to_national_campaign_binding")
            elif len(rows) != 1:
                blockers.append("ambiguous_source_product_identity")
            else:
                row = rows[0]
                description = html.unescape(re.sub("<[^>]+>", " ", row.get("keyfacts", {}).get("description", "")))
                if (product.gtin != proof["gtin"] or product.name.strip() != proof["source_name"].strip()
                        or product.brand != proof["brand"] or product.package_text != proof["package_text"]
                        or row.get("fullTitle") != proof["full_title"]
                        or description != proof["reviewed_source_description"]
                        or sum(p.brand == product.brand and p.name.strip() == product.name.strip()
                               and p.package_text == product.package_text for p in extracted.products) != 1
                        or any(t.casefold() not in description.casefold() for t in proof["required_source_text"])):
                    blockers.append("reviewed_exact_identity_changed")
                offer = product.offers[0] if len(product.offers) == 1 else None
                if (not offer or offer.price != Decimal(str(proof["price"]))
                        or offer.member_only != proof["member_only"]
                        or not product.source_fields.get("price_valid_at_observation")
                        or not product.source_fields.get("shared_price_universe_eligible")
                        or product.source_fields.get("geographic_restrictions")
                        or re.search(r"aktiver|kupong|personlig|just for you", description, re.IGNORECASE)):
                    blockers.append("current_price_or_eligibility_not_verified")
                for key, expected in (("price_window_start_at", "00:00:00"), ("price_window_end_at", "23:59:59")):
                    value = product.source_fields.get(key)
                    if not value or datetime.fromisoformat(value).astimezone(ZoneInfo("Europe/Stockholm")).strftime("%H:%M:%S") != expected:
                        blockers.append("intraday_contract_requires_review")
                limits = re.findall(r"Max\s+(\d+)\s+förp", description, re.IGNORECASE)
                if (limits and {int(n) for n in limits} != {proof["max_packages_per_household"]}):
                    blockers.append("purchase_limit_changed")
                if not blockers:
                    start = max(offer.valid_from or date.min, date.fromisoformat(proof["valid_from"]))
                    end = min(offer.valid_to or date.max, date.fromisoformat(proof["valid_to"]))
                    if not start <= product.fetched_at.date() <= end:
                        blockers.append("campaign_not_current_at_observation")
            fields = {**product.source_fields, "lidl_offer_policy": POLICY,
                "purchase_blockers": blockers, "variant_count": 1,
                "verified_store_scope": not blockers, "store_price_verified": not blockers,
                "source_channel": "offers", "source_variant_id": product.external_product_id,
                "national_publication_id": self.review["publication_id"],
                "publication_url": self.publication.json_payload()["flyer"]["flyerUrlAbsolute"],
                "publication_observed_at": self.publication.fetched_at.isoformat(),
                "document_sha256": self.review["pdf_sha256"], "document_product_binding": proof,
                "lidl_purchase_qualified": not blockers}
            offers = product.offers
            if not blockers:
                cap = proof["max_packages_per_household"]
                contract = f"lidl:household:{self.review['publication_id']}:{product.external_product_id}"
                offers = (offer.model_copy(update={"type": PromotionType.MEMBER_PRICE if proof["member_only"] else PromotionType.SALE_PRICE,
                    "external_id": product.external_product_id, "valid_from": start, "valid_to": end,
                    "max_quantity": cap, "description": proof["text"],
                    "source_payload": {**offer.source_payload, "policy": POLICY, "price_contract_id": contract,
                        "price_role": "member_price" if proof["member_only"] else "published_offer_price",
                        "document_text": proof["text"], "deposit_status": proof["deposit_status"],
                        'price_basis_unit': proof.get('price_basis_unit', 'package'),
                        **({'purchase_terms': proof['purchase_terms']} if proof.get('purchase_terms') else {}),
                        "ordinary_price_current_verified": False}}),)
                fields.update(deposit_status=proof["deposit_status"], purchase_limit_verified=True,
                              conditions_text=proof["text"], price_scope="verified_national_campaign_product")
            candidates.append(product.model_copy(update={"store_external_id": store.external_id,
                **({'package_quantity':Decimal(1),'package_unit':'st'}
                   if not blockers and proof.get('explicit_piece_purchase') else {}),
                "regular_price": None, "sale_price": None, "member_price": None,
                "drained_quantity": Decimal(proof['drained_quantity_g'])
                    if not blockers and proof.get('drained_quantity_g') is not None else product.drained_quantity,
                "source_fields": fields, "offers": offers}))
        parsed = ProductParseResult(products=candidates, failures=shared_failures)
        result, self.row_acceptance = qualify_rows(parsed, store=self.store,
            observed_at=max(d.fetched_at for d in raw.documents), original_parsed=extracted)
        local = [f for f in extracted.failures if f not in shared_failures]
        result = ProductParseResult(products=result.products, failures=[*result.failures, *local])
        self.row_acceptance["retained_parser_quarantine"] = [f.model_dump(mode="json") for f in local]
        self.row_acceptance.pop("evidence_sha256", None)
        self.row_acceptance["evidence_sha256"] = hashlib.sha256(json.dumps(self.row_acceptance, sort_keys=True).encode()).hexdigest()
        return result
