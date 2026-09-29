"""Store-query physical campaigns on the existing Hemköp transport and OWN contract.

The public storefront's offline beam calls /search/campaigns/offline with q equal
to its route store ID. No online session, default store, image identity or catalog
price is reused. Explicit productCodes bind either a resolved package or an open
campaign choice. Supported count, membership and cap facts use PurchaseTerms;
all unsupported conditions remain review evidence.
"""
import re
from datetime import UTC, datetime
from decimal import Decimal

from grocery_data.app.connectors.hemkop.connector import HemkopConnector
from grocery_data.app.connectors.hemkop.models import validated_catalog_page
from grocery_data.app.connectors.willys.parser import parse_package_text
from grocery_data.app.domain import (
    Chain,
    CoverageLevel,
    ParseFailure,
    PriceContextType,
    ProductParseResult,
    RawBatch,
    SourceCollectionAudit,
    SourceOffer,
    SourceProduct,
)
from grocery_data.app.domain.purchase_terms import PurchaseTerms

POLICY = 'hemkop-physical-singleton-offers-v1'
PARSER = 'hemkop-physical-offers-v2'
URL = 'https://www.hemkop.se/search/campaigns/offline'
ROW_FIELDS = frozenset({'showGoodPriceIcon', 'manufacturer', 'googleAnalyticsCategory',
    'displayVolume', 'online', 'priceNoUnit', 'originalImage', 'priceUnit',
    'offlinePromotionLowestHistoricalPrice', 'title', 'price', 'thumbnail',
    'lowestHistoricalPrice', 'energyDeclaration', 'inactivePotentialPromotions',
    'ranking', 'productBasketType', 'potentialPromotions', 'image',
    'promotionProductOrdinaryComparePrice', 'solrSearchScore',
    'promotionProductOrdinaryComparePriceUnit', 'labels', 'name'})
PROMOTION_FIELDS = frozenset(['promotionPercentage', 'promotionRedeemLimit', 'productCodes', 'code', 'threshold', 'price', 'endDate', 'startDate', 'promotionType', 'textLabelGenerated', 'weightVolume', 'sorting', 'redeemLimit', 'campaignType', 'textLabelManual', 'offerStatus', 'promotionTheme', 'savePrice', 'realMixAndMatch', 'mainProductCode', 'discountPrice', 'splashTitleText', 'timesUsed', 'qualifyingCount', 'cartLabel', 'validUntil', 'conditionLabel', 'rewardLabel', 'textLabel', 'brands', 'comparePrice', 'redeemLimitLabel', 'name', 'priority', 'description'])


def page_rows(document, store_id):
    if (document.chain != Chain.HEMKOP or document.method != 'GET'
            or document.http_status != 200 or document.kind != 'physical_offers'
            or document.url != URL or document.store_external_id != store_id
            or document.query.get('q') != store_id
            or document.query.get('type') is not None):
        raise ValueError('Hemkop physical campaign source/store/query mismatch')
    payload = document.json_payload()
    page = validated_catalog_page(payload, requested_page=document.page_number,
                                  requested_size=int(document.query['size']), require_product_identity=False)
    for row in page.results:
        if set(row) - ROW_FIELDS:
            raise ValueError('Hemkop physical row schema changed: ' + ','.join(sorted(set(row) - ROW_FIELDS)))
        promotions = row.get('potentialPromotions')
        if not isinstance(promotions, list) or any(not isinstance(p, dict) or set(p) - PROMOTION_FIELDS for p in promotions):
            raise ValueError('Hemkop physical campaign promotion schema changed')
    return page


async def fetch(client, store):
    before = client._metrics_snapshot()
    documents = []
    total = None
    for index in range(20):
        document = await client._request('GET', '/search/campaigns/offline',
            kind='physical_offers', store_external_id=store.external_id,
            params={'q': store.external_id, 'page': index, 'size': 30, 'disableMimerSort': 'true'},
            page_number=index)
        documents.append(document)
        page = page_rows(document, store.external_id)
        if total is not None and total != page.total_results:
            raise ValueError('Hemkop campaign count changed during traversal')
        total = page.total_results
        if index + 1 >= page.number_of_pages:
            return RawBatch(chain=Chain.HEMKOP, documents=tuple(documents), transport=client._metrics_since(before))
    raise ValueError('Hemkop bounded campaign page budget exceeded')


def parse(raw, references, store):
    products, failures, seen = [], [], set()
    for doc, reference in zip(raw.documents, references, strict=True):
        page = page_rows(doc, store.external_id)
        for index, row in enumerate(page.results):
            ref = f'{reference}#result={index}'
            try:
                promotions = row['potentialPromotions']
                if len(promotions) != 1:
                    raise ValueError('multiple_or_missing_campaigns')
                p = promotions[0]
                if row.get('inactivePotentialPromotions'):
                    raise ValueError('inactive_personal_campaigns_require_review')
                identity = p.get('mainProductCode')
                ids = p.get('productCodes')
                if (not identity or not isinstance(ids, list) or not ids or identity not in ids
                        or any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids)):
                    raise ValueError('explicit_campaign_variant_membership_missing')
                count = p.get('qualifyingCount')
                if (type(count) is not int or not 1 <= count <= 100
                        or not isinstance(p.get('realMixAndMatch'), bool)
                        or (count == 1 and p['realMixAndMatch'])
                        or (count > 1 and len(ids) > 1 and not p['realMixAndMatch'])
                        or p.get('campaignType') not in {'GENERAL', 'LOYALTY'}
                        or p.get('promotionType') != 'MixMatchPricePromotion'
                        or row.get('priceUnit') != 'kr/st'
                        or any(p.get(k) not in (None, '', 0) for k in ['promotionPercentage',
                            'threshold', 'discountPrice', 'textLabelManual', 'offerStatus'])):
                    raise ValueError('purchase_conditions_require_review')
                if (p.get('conditionLabel', '') != (f'{count} för' if count > 1 else '')
                        or any(p.get(k) not in (None, '', 'Klubbpris' if p['campaignType']=='LOYALTY' else '',
                                               'Välj och blanda' if count > 1 else '')
                               for k in ['textLabel', 'textLabelGenerated'])):
                    raise ValueError('purchase_label_requires_review')
                description = p.get('description') or ''
                condition_text = re.sub(r'fetthalt\s+max\s+\d+(?:[,.]\d+)?\s*%', '', description, flags=re.IGNORECASE)
                if re.search(r'pant|gäller|endast|vid köp|handla|max\b|kupong|aktiver|personlig|\d{1,2}/\d{1,2}|måndag|tisdag|onsdag|torsdag|fredag|lördag|söndag', condition_text, re.IGNORECASE):
                    raise ValueError('additional_purchase_or_deposit_condition_requires_review')
                cap = p.get('redeemLimit')
                if cap is not None:
                    if (type(cap) is not int or cap < 1 or p.get('promotionRedeemLimit') != cap
                            or p.get('redeemLimitLabel') != f'Max {cap} köp'):
                        raise ValueError('purchase_limit_conflict')
                elif p.get('promotionRedeemLimit') or p.get('redeemLimitLabel'):
                    raise ValueError('purchase_limit_unproven')
                size = row.get('displayVolume')
                if p.get('weightVolume') not in (None, size):
                    raise ValueError('campaign_package_conflict')
                # A range belongs to the open campaign, never to its main image/product.
                open_group = len(ids) > 1
                if open_group:
                    quantity, unit = None, None
                elif isinstance(size, str) and re.fullmatch(r'\d+(?:[,.]\d+)?\s*(?:g|kg|ml|cl|dl|l|st)', size):
                    quantity, unit, _ = parse_package_text(size)
                elif isinstance(size, str) and (pieces := re.fullmatch(r'(\d+)\s*(?:p|pack|-pack)', size)):
                    quantity, unit = Decimal(pieces[1]), 'st'
                else:
                    raise ValueError('fixed_package_not_proven')
                start, end = (datetime.strptime(p[k], '%d/%m-%Y').replace(tzinfo=UTC).date() for k in ['startDate', 'endDate'])
                if (datetime.fromtimestamp(p['validUntil'] / 1000, tz=UTC).date() != end
                        or not p.get('code') or not isinstance(p.get('price'), (int, float))):
                    raise ValueError('campaign_price_or_dates_conflict')
                key = f"{p['code']}:group" if open_group else f"{p['code']}:{identity}"
                if key in seen:
                    raise RuntimeError('duplicate campaign/product identity')
                seen.add(key)
                terms = PurchaseTerms(source_reference=ref, purchase_form='fixed_package' if open_group else 'piece' if unit=='st' and quantity==1 else 'fixed_package',
                    identity_scope='campaign_group' if open_group else 'product',
                    variant_selection='required' if open_group else 'resolved',
                    eligible_variant_ids=tuple(ids), complete_group_size=count,
                    mixing_allowed=p['realMixAndMatch'],
                    campaign_group_id=f"hemkop:campaign:{p['code']}:{start}:{end}" if p['realMixAndMatch'] else None,
                    quantity_basis='unknown' if open_group else 'source_exact',
                    limit_scope='household_campaign' if cap else 'offer').model_dump(mode='json')
                offer = SourceOffer(external_id=str(p['code']), type='multibuy' if count>1 else 'member_price' if p['campaignType']=='LOYALTY' else 'sale_price',
                    valid_from=start, valid_to=end, price=Decimal(str(p['price'])), quantity=count, max_quantity=cap,
                    description=description or None, member_only=p['campaignType']=='LOYALTY',
                    source_payload={'hemkop_physical_campaign': p, 'purchase_terms': terms,
                        'price_contract_id': f"hemkop:campaign:{p['code']}:{start}:{end}",
                        'source_row': row})
                products.append(SourceProduct(chain=Chain.HEMKOP, store_external_id=store.external_id,
                    external_product_id=key, name=row['name'], brand=row.get('manufacturer'),
                    package_text=size, package_quantity=quantity, package_unit=unit,
                    sale_unit='st', basket_type='ST', offers=(offer,), raw_reference=ref, fetched_at=doc.fetched_at,
                    source_fields={'verified_store_scope': True, 'hemkop_physical_policy': POLICY,
                        'variant_count': len(ids), 'source_variant_id': identity if not open_group else None,
                        'purchase_terms': terms, 'source_sha256': doc.payload_hash,
                        'source_query': doc.query, 'purchase_blockers': []}))
            except (ValueError, KeyError, TypeError) as exc:
                failures.append(ParseFailure(raw_record_reference=ref, error_code='unsupported_physical_offer',
                    error_message='Hemkop physical row requires review:' + str(exc), parser_version=PARSER,
                    sample={'name': row.get('name')}))
    return ProductParseResult(products=products, failures=failures)


class RetainedPhysicalOffers(HemkopConnector):
    coverage = CoverageLevel.OFFERS_ONLY
    parser_version = PARSER

    def __init__(self, connector, store, locator, offers):
        self.client, self.parser = connector.client, connector.parser
        self.store = store.model_copy(update={'coverage': CoverageLevel.OFFERS_ONLY,
            'price_context_type': PriceContextType.PHYSICAL_STORE,
            'physical_store_external_id': store.external_id,
            'source_fields': {**store.source_fields, 'offer_policy': POLICY,
                'official_store_url': f'https://www.hemkop.se/butik/{store.external_id}'}})
        self.locator, self.offers = locator, offers

    def collection_policy_audit(self):
        return SourceCollectionAudit(source_policy=self.source_policy, operator_opt_in=True,
            store_allowlist=(self.store.external_id,), requests_per_second=self.client.requests_per_second,
            max_concurrency=1)

    async def fetch_stores(self, area):
        return self.locator

    def parse_stores(self, raw, references, area):
        return [self.store]

    def catalog_eligible(self, store):
        return store.external_id == self.store.external_id

    async def fetch_catalog(self, store):
        return self.offers

    def parse_catalog(self, raw, references, store):
        from grocery_data.app.services.offer_rows import qualify_rows
        parsed = parse(raw, references, store)
        result, self.row_acceptance = qualify_rows(parsed, store=store,
            observed_at=max(d.fetched_at for d in raw.documents))
        return result

    async def aclose(self):
        pass  # The municipal job owns the existing shared Hemkop client.
