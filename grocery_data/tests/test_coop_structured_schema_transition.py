"""Public campaign schema changes must not masquerade as store conflicts."""
import gzip
import json
from pathlib import Path

import pytest

from grocery_data.app.connectors.coop import CoopParser
from grocery_data.app.connectors.coop.structured_offers import (
    capture_public_response,
    sanitized_response,
)
from grocery_data.app.domain import RawBatch, SourceStore
from grocery_data.app.services.offer_rows import qualify_rows
from grocery_data.tests.test_coop_physical_structured import one_ad_mutation, parse, source


@pytest.mark.parametrize('field,value,blocker', [
    ('rules', 'Handla andra varor för 200:- så får du köpa:', 'additional_purchase_rules_requires_review'),
    ('steps', [{'discountValue':25, 'quantity':3, 'unit':'st', 'dealType':'pris'}],
     'tiered_price_steps_requires_review'),
])
def test_new_public_conditions_retained_and_quarantined_per_row(field, value, blocker):
    def change(row):
        if field == 'rules':
            row['content']['dealOfferRulesText'] = value
        else:
            row['priceInformation']['steps'] = value
    original, approved, evidence = parse(mutate=one_ad_mutation(change))
    assert len(original.products) == 1 and not original.failures
    assert not approved.products and not evidence['shared_blockers']
    assert blocker in evidence['decisions'][0]['blockers']
    record = original.products[0].offers[0].source_payload['source_record']
    data = {'sortingGroups':[{'id':'alla', 'offerAmount':1, 'offers':[record]}]}
    assert sanitized_response(data) == data


def test_parent_only_rules_and_steps_cannot_disappear_on_child():
    def change(e):
        data = e['structured_offers']['data']
        for group in data['sortingGroups']:
            for row in group['offers']:
                if row.get('clusterInteriorOffers'):
                    row['content']['dealOfferRulesText'] = 'Handla andra varor för 200:-'
                    row['priceInformation']['steps'] = [{'discountValue':25,'quantity':3,'unit':'st'}]
    original, approved, evidence = parse(mutate=change)
    assert not original.failures and not evidence['shared_blockers']
    children = [p for p in original.products if p.source_fields['group_variant_count'] > 1]
    assert children and approved.products  # Independent simple rows remain qualified.
    assert not {p.external_product_id for p in children} & {p.external_product_id for p in approved.products}
    for p in children:
        payload = p.offers[0].source_payload
        assert payload['purchase_rules_text'] and payload['parent_price_steps']
        assert 'additional_purchase_rules_requires_review' in p.source_fields['purchase_blockers']
        assert 'tiered_price_steps_requires_review' in p.source_fields['purchase_blockers']


@pytest.mark.parametrize('field,value', [('source_url','https://external.api.coop.se/dke/offers/sorting-groups/106595'),
    ('store_external_id','1158'), ('ledger_account_number','106595')])
def test_wrong_source_still_blocks_whole_document(field,value):
    parsed, approved, evidence = parse(mutate=lambda e:e['structured_offers'].update({field:value}))
    assert not parsed.products and not approved.products and evidence['shared_blockers']
    assert 'store/source evidence mismatch' in parsed.failures[0].error_message


def test_schema_rejection_is_not_reported_as_identity_mismatch():
    def change(e):
        e['structured_offers'].pop('data')
        e['structured_offers']['error'] = 'public_structured_schema_unrecognized'
        e['structured_offers']['schema_review_reason'] = 'new public offer fields require schema review: content.futureRule'
    parsed, approved, evidence = parse(mutate=change)
    assert not approved.products and evidence['shared_blockers']
    assert 'response rejected: public_structured_schema_unrecognized' in parsed.failures[0].error_message
    assert 'content.futureRule' in parsed.failures[0].error_message
    assert 'identity' not in parsed.failures[0].error_message


@pytest.mark.asyncio
async def test_unknown_condition_keeps_closed_gate_and_specific_schema_diagnostic():
    store,batch = source()
    payload = json.loads(batch.documents[0].payload)['structured_offers']['data']
    payload['sortingGroups'][0]['offers'][0]['content']['futureRule'] = 'unreviewed condition'
    class Response:
        url = 'https://external.api.coop.se/dke/offers/sorting-groups/' + str(store.source_fields['ledger_account_number'])
        status = 200
        async def json(self):
            return payload
    captures = []
    await capture_public_response(Response(),store,captures)
    assert 'data' not in captures[0]
    assert captures[0]['error'] == 'public_structured_schema_unrecognized'
    assert 'content.futureRule' in captures[0]['schema_review_reason']
    assert 'unreviewed condition' not in str(captures)


def test_unknown_nested_step_condition_is_not_silently_dropped():
    _,batch = source()
    payload = json.loads(batch.documents[0].payload)['structured_offers']['data']
    payload['sortingGroups'][0]['offers'][0]['priceInformation']['steps'] = [{'minimumSpend':200}]
    with pytest.raises(ValueError,match='steps requires schema review'):
        sanitized_response(payload)


def test_real_campaign_transition_new_hash_dates_and_independent_row_approval():
    fixture = json.loads(gzip.decompress((Path(__file__).parent/'fixtures/coop-physical-transition-20260928.json.gz').read_bytes()))
    store = SourceStore.model_validate(fixture['store'])
    editions = {}
    for label, value in fixture['editions'].items():
        batch = RawBatch.model_validate(value)
        document = batch.documents[0]
        parsed = CoopParser().parse_catalog(batch,['raw:retained-'+label],store)
        approved,evidence = qualify_rows(parsed,store=store,observed_at=document.fetched_at)
        assert not parsed.failures and not evidence['shared_blockers'] and approved.products
        data = json.loads(document.payload)['structured_offers']['data']
        assert sanitized_response(data) == data
        for product in approved.products:
            payload = product.offers[0].source_payload
            assert payload['source_sha256'] == document.payload_hash
            assert payload['campaign_evidence']['observed_current_at'] == document.fetched_at.isoformat().replace('+00:00','Z')
        editions[label] = (document, parsed, approved, evidence)
    old, new = editions['2026-09-27'], editions['2026-09-28']
    assert old[0].payload_hash != new[0].payload_hash
    assert old[3]['evidence_sha256'] != new[3]['evidence_sha256']
    assert old[0].fetched_at < new[0].fetched_at
    day = new[0].fetched_at.date()
    expired = [p for p in old[2].products if p.offers[0].valid_to < day]
    assert expired
    assert not {p.external_product_id for p in expired} & {p.external_product_id for p in new[2].products}
    assert all(p.offers[0].valid_from <= day <= p.offers[0].valid_to for p in new[2].products)
    tiers = [p for p in new[1].products if p.offers[0].source_payload['source_record']['priceInformation'].get('steps')]
    assert tiers
    for p in tiers:
        assert p.offers[0].price is None and p.offers[0].quantity is None and p.offers[0].type.value == 'other'
        assert 'tiered_price_steps_requires_review' in p.source_fields['purchase_blockers']
    assert not {p.external_product_id for p in tiers} & {p.external_product_id for p in new[2].products}
