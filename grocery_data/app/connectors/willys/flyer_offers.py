"""Willys flyer extension: complete reviewed text ledger, existing price contracts."""
import base64
import hashlib
import json
from datetime import date
from pathlib import Path

import pymupdf

from grocery_data.app.connectors.willys.connector import WillysConnector
from grocery_data.app.domain import (
    CoverageLevel,
    ParseFailure,
    ProductParseResult,
    RawBatch,
    SourceOffer,
    SourceProduct,
    TransportMetrics,
)
from grocery_data.app.services.offer_rows import qualify_rows

POLICY = 'willys-flyer-reviewed-text-v1'
PARSER = 'willys-flyer-text-v1'
REVIEW = Path(__file__).parent / 'fixtures/flyer_review_20260923.json'


def document_review(raw, store):
    if len(raw.documents) != 2:
        raise ValueError('one store listing and one document required')
    listing, document = raw.documents
    source = listing.json_payload()
    if (listing.http_status != 200 or document.http_status != 200
            or listing.store_external_id != store.external_id
            or listing.url.rstrip('/') != store.source_fields['flyer_url'].rstrip('/')
            or source['paperCompleteUrl'].rstrip('/') != listing.url.rstrip('/')):
        raise ValueError('official store to flyer binding unverified')
    pdf = base64.b64decode(document.json_payload()['pdf_base64'], validate=True)
    digest = hashlib.sha256(pdf).hexdigest()
    if digest != document.json_payload()['sha256']:
        raise ValueError('document digest mismatch')
    reviews = [r for r in json.loads(REVIEW.read_bytes()) if r['pdf_sha256'] == digest]
    if len(reviews) != 1:
        raise ValueError('new_flyer_document_requires_text_review')
    review = reviews[0]
    with pymupdf.open(stream=pdf, filetype='pdf') as doc:
        if len(doc) != len(source['pages']) or len(doc) != review['pages']:
            raise ValueError('publication page identity mismatch')
        # The current per-store viewer text must agree with the document. This
        # also prevents rebinding a retained PDF to a newly advertised edition.
        if (source['publication_url'] != review['publication_url'] or
                [hashlib.sha256(t.encode()).hexdigest() for t in source['pageTexts']] != review['viewer_text_sha256']):
            raise ValueError('current_viewer_document_text_mismatch')
        for ad in review['ads']:
            blocks = doc[ad['page']-1].get_text('blocks')
            if not any(list(b[:4]) == ad['bbox'] and b[4] == ad['text'] for b in blocks):
                raise ValueError('reviewed_ad_text_changed')
            if ad['status'] == 'qualified' and not any(
                    list(b[:4]) == ad['price_bbox'] and b[4] == ad['price_text'] for b in blocks):
                raise ValueError('reviewed_price_text_changed')
    observed = min(listing.fetched_at, document.fetched_at)
    if not date.fromisoformat(review['valid_from']) <= observed.date() <= date.fromisoformat(review['valid_to']):
        raise ValueError('document_not_current_at_observation')
    return review, observed


class WillysFlyerConnector(WillysConnector):
    coverage = CoverageLevel.OFFERS_ONLY
    connector_version = 'willys-flyer-v1'
    parser_version = PARSER
    offer_policy = POLICY

    def read_document(self, raw, store):
        return document_review(raw, store)

    def __init__(self, *, store, inventory, raw):
        self.store = store.model_copy(update={'source_fields': {**store.source_fields, 'offer_policy': self.offer_policy}})
        self.registry = RawBatch.model_validate(inventory['registry'])
        self.raw = raw.model_copy(update={'transport': TransportMetrics()})
        self.review, self.observed = self.read_document(raw, store)
        self.row_acceptance = None

    def collection_policy_audit(self):
        from grocery_data.app.domain import SourceCollectionAudit
        return SourceCollectionAudit(source_policy=self.source_policy, operator_opt_in=True,
                                     store_allowlist=(self.store.external_id,))

    async def fetch_stores(self, area):
        return self.registry.model_copy(update={'transport': TransportMetrics()})

    def parse_stores(self, raw, references, area):
        return [self.store]

    def catalog_eligible(self, store):
        return store == self.store

    async def fetch_catalog(self, store):
        return self.raw

    async def aclose(self):
        pass

    def parse_catalog(self, raw, references, store):
        products, failures = [], []
        for ad in self.review['ads']:
            ref = references[1] + f"#page={ad['page']}&advertisement={ad['index']}"
            if ad['status'] != 'qualified':
                failures.append(ParseFailure(raw_record_reference=ref, error_code='flyer_advertisement',
                    error_message=ad.get('reason', 'duplicate_advertisement'), parser_version=self.parser_version,
                    sample={'ad': ad['index'], 'title': ad['title']}))
                continue
            # Document/ad/variant identities are opaque source identities. They
            # are never represented as retailer SKUs or guessed GTINs.
            contract_key = json.dumps([ad['title'], ad['brand'], ad['package_quantity'], ad['package_unit'],
                                       ad['valid_from'], ad['valid_to']], ensure_ascii=False)
            contract = 'willys:household:' + hashlib.sha256(contract_key.encode()).hexdigest()[:24]
            if self.parser_version != PARSER:
                from grocery_data.app.connectors.willys.flyer_contract import household_contract
                contract = household_contract(ad)
            for vi, name in enumerate(ad['names']):
                identity = f"flyer:{self.review['pdf_sha256'][:16]}:{ad['index']}:{vi}"
                if self.parser_version != PARSER:
                    identity = f"flyer:{self.review['pdf_sha256'][:16]}:{ad['page']}:{hashlib.sha256(ad['text'].encode()).hexdigest()[:16]}:{vi}"
                if (ad.get('purchase_terms') or {}).get('identity_scope') == 'campaign_group':
                    identity += ':group'
                offer = SourceOffer(external_id=identity,
                    type='multibuy' if ad['required_packages'] > 1 else 'member_price' if ad['member_only'] else 'sale_price',
                    price=ad['price'], quantity=ad['required_packages'], member_only=ad['member_only'],
                    max_quantity=ad['max_quantity'], valid_from=ad['valid_from'], valid_to=ad['valid_to'],
                    description=ad['text'] + '\n' + ad['price_text'],
                    source_payload={'policy': self.offer_policy, 'price_contract_id': contract,
                        'document_sha256': self.review['pdf_sha256'], 'deposit_status': ad['deposit_status'],
                        'price_basis_unit': ad.get('price_basis_unit', 'package'),
                        **({'purchase_terms': ad['purchase_terms']} if ad.get('purchase_terms') else {}),
                        'ordinary_price_current_verified': False, 'advertisement': ad})
                products.append(SourceProduct(chain='willys', store_external_id=store.external_id,
                    external_product_id=identity, name=name, brand=ad['brand'] or None,
                    package_text=f"{ad['package_quantity']} {ad['package_unit']}" if ad['package_quantity'] else None,
                    package_quantity=ad['package_quantity'], package_unit=ad['package_unit'],
                    sale_unit='kg' if ad.get('price_basis_unit') == 'kg' else 'st',
                    raw_reference=ref, fetched_at=self.observed, offers=(offer,), source_fields={
                        'willys_flyer_policy': self.offer_policy, 'verified_store_scope': True, 'store_price_verified': True,
                        'source_channel': 'offers', 'variant_count': 1, 'source_variant_id': identity,
                        'document_product_binding': ad, 'document_sha256': self.review['pdf_sha256'],
                        'official_flyer_url': raw.documents[0].url, 'willys_flyer_purchase_qualified': True,
                        'purchase_blockers': [], 'deposit_status': ad['deposit_status'],
                        'purchase_limit_verified': True, 'conditions_text': offer.description}))
        parsed = ProductParseResult(products=products)
        accepted, evidence = qualify_rows(parsed, store=self.store, observed_at=self.observed,
            original_parsed=ProductParseResult(products=products, failures=failures))
        evidence.update(advertisements=len(self.review['ads']), advertisement_decisions=[
            {k: ad.get(k) for k in ('index', 'page', 'title', 'status', 'reason', 'duplicate_of')}
            for ad in self.review['ads']], retained_parser_quarantine=[f.model_dump(mode='json') for f in failures])
        evidence.pop('evidence_sha256', None)
        evidence['evidence_sha256'] = hashlib.sha256(json.dumps(evidence, sort_keys=True).encode()).hexdigest()
        self.row_acceptance = evidence
        if self.parser_version != PARSER:
            evidence.update(document_qualification=self.review.get('automation'),
                page_reports=self.review.get('page_reports'),
                unknown_image_content='not_interpreted')
            evidence.pop('evidence_sha256', None)
            evidence['evidence_sha256'] = hashlib.sha256(json.dumps(evidence, sort_keys=True).encode()).hexdigest()
        return ProductParseResult(products=accepted.products, failures=[*accepted.failures, *failures])


class AutomaticWillysFlyerConnector(WillysFlyerConnector):
    """Automatic supported text; optional previously approved legacy fallbacks.

    The legacy register is never required by the automatic rules. Removing it
    leaves automatic rows intact, and unknown hashes do not block an edition.
    """
    parser_version = 'willys-flyer-text-v2'
    offer_policy = 'willys-flyer-validated-text-v2'
    allow_legacy_review = True

    def read_document(self, raw, store):
        from grocery_data.app.connectors.willys.flyer_text import flat, qualify_document
        from grocery_data.app.services.campaign_refresh_policy import STOCKHOLM
        if len(raw.documents) != 2:
            raise ValueError('one store listing and document required')
        listing, document = raw.documents
        source = listing.json_payload()
        if (listing.http_status != 200 or document.http_status != 200
                or listing.store_external_id != store.external_id
                or listing.url.rstrip('/') != store.source_fields['flyer_url'].rstrip('/')
                or source['paperCompleteUrl'].rstrip('/') != listing.url.rstrip('/')):
            raise ValueError('official store to flyer binding unverified')
        pdf = base64.b64decode(document.json_payload()['pdf_base64'], validate=True)
        digest = hashlib.sha256(pdf).hexdigest()
        if digest != document.json_payload()['sha256']:
            raise ValueError('document digest mismatch')
        with pymupdf.open(stream=pdf, filetype='pdf') as doc:
            review = qualify_document(doc, source)
        review.update(pdf_sha256=digest, publication_url=source['publication_url'])
        review['automatic_decisions'] = [dict(a) for a in review['ads']]
        observed = min(listing.fetched_at, document.fetched_at)
        # A genuinely fetched future edition is retained with its future dates;
        # the ordinary OWN/PU campaign gate decides when it is purchasable.
        if observed.astimezone(STOCKHOLM).date() > date.fromisoformat(review['valid_to']):
            raise ValueError('document_expired_at_observation')
        automatic = [a for a in review['ads'] if a['status'] == 'qualified']
        fallback_count = 0
        if self.allow_legacy_review:
            try:
                legacy, _ = document_review(raw, store)
            except (ValueError, OSError):
                legacy = None
            if legacy:
                for old in legacy['ads']:
                    same = next((a for a in review['ads'] if a['page'] == old['page'] and a['bbox'] == old['bbox']
                                 and flat(a['text']) == flat(old['text'])), None)
                    open_same = bool(same and (same.get('purchase_terms') or {}).get('variant_selection') == 'required')
                    if same and same['status'] == 'qualified' and not open_same:
                        continue
                    if old['status'] not in {'qualified', 'duplicate'}:
                        continue
                    if old['status'] == 'duplicate' and same is None:
                        continue
                    if same and not open_same:
                        review['ads'].remove(same)
                    kept = {**old, 'qualification_method':'existing_manual_review_v1'}
                    review['ads'].append(kept)
                    fallback_count += old['status'] == 'qualified'
        # A legacy page and an automatically qualified repeated advertisement
        # must not become two offers. Prefer automatic evidence for the same
        # exact household/price/variant contract, without merging conflicts.
        from decimal import Decimal

        from grocery_data.app.connectors.willys.flyer_contract import household_contract
        seen = {}
        for ad in sorted(review['ads'], key=lambda a: a.get('qualification_method') == 'existing_manual_review_v1'):
            if ad['status'] != 'qualified':
                continue
            key = (household_contract(ad), Decimal(str(ad['price'])), ad['required_packages'],
                   ad['member_only'], ad['max_quantity'], tuple(sorted(flat(n).casefold() for n in ad['names'])))
            if key in seen:
                ad.update(status='duplicate', reason='duplicate_advertisement', duplicate_of=seen[key])
            else:
                seen[key] = ad['index']
        fallback_count = sum(a['status'] == 'qualified' and a.get('qualification_method') == 'existing_manual_review_v1'
                             for a in review['ads'])
        review['automation'] = {'automatic_advertisements':len(automatic),
            'existing_manual_advertisements':fallback_count,
            'automatic_decisions':review['automatic_decisions'],
            'manual_document_approval_required':False,
            'automatic_rules_use_legacy_register':False}
        for ad in review['ads']:
            if ad['status'] == 'qualified' and date.fromisoformat(ad['valid_to']) < observed.astimezone(STOCKHOLM).date():
                ad.update(status='expired', reason='expired_at_observation')
        return review, observed
