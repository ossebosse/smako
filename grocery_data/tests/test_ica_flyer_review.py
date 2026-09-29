"""Review gate protocol tests; synthetic values are not retailer price evidence."""
from copy import deepcopy

import pytest

from grocery_data.app.services.ica_flyer_review import review_key, reviewed_flyer_batch


def fixture():
    evidence = {'issue_id': 'fixture-issue', 'pdf_sha256': 'a' * 64, 'page': 1, 'box': 'top-left',
                'bbox': [0, 0, .5, .5], 'observed_at': '2026-09-16T05:00:00+00:00',
                'source_url': 'https://www.e-magin.se/paper/fixture/paper/1',
                'official_store_ids': ['fixture-store']}
    terms = {'gtin': '7318690494201', 'name': 'Fixture flour', 'brand': 'Fixture', 'package': '1 kg',
             'price': '30', 'quantity': 2, 'eligibility': 'general_member',
             'valid_from': '2026-09-17', 'valid_to': '2026-09-17',
             'date_evidence': 'ad explicitly Thursday only', 'variant_evidence': 'fixture exact code',
             'limit_status': 'explicit_cap', 'max_purchases': 1, 'limit_evidence': 'ad cap',
             'deposit_status': 'verified_not_applicable', 'deposit_evidence': 'paper flour bag'}
    return evidence, {'evidence_sha256': review_key(evidence), 'terms_sha256': review_key(terms),
                      'decision': 'approved', 'terms': terms}


def test_review_replays_existing_source_contract_without_freshening_observation():
    from grocery_data.app.connectors.ica.parser import IcaParser
    from grocery_data.app.domain import SourceStore
    evidence, review = fixture()
    batch = reviewed_flyer_batch(evidence, review, account_id='fixture-store')
    parsed = IcaParser().parse_catalog(batch, ['review-fixture'], SourceStore(
        chain='ica', external_id='fixture-store', name='Fixture', city='Fixture', raw_reference='fixture', coverage='offers_only'))
    p = parsed.products[0]
    assert p.fetched_at.isoformat() == evidence['observed_at']
    assert p.regular_price is None and p.sale_price is None
    assert p.offers[0].quantity == 2 and p.offers[0].max_quantity == 1
    assert p.offers[0].member_only
    assert str(p.offers[0].valid_from) == str(p.offers[0].valid_to) == '2026-09-17'


def test_new_actual_observation_of_same_reviewed_content_keeps_campaign_id():
    evidence, review = fixture()
    before = reviewed_flyer_batch(evidence,review,account_id='fixture-store')
    evidence['observed_at']='2026-09-17T05:00:00+00:00'
    review['evidence_sha256']=review_key(evidence)  # Fresh relevant review required.
    after = reviewed_flyer_batch(evidence,review,account_id='fixture-store')
    assert before.documents[0].json_payload()['offers']==after.documents[0].json_payload()['offers']
    assert before.documents[0].fetched_at != after.documents[0].fetched_at


@pytest.mark.parametrize('field,value', [('issue_id', 'next-week'), ('pdf_sha256', 'b' * 64),
    ('box', 'another-box'), ('official_store_ids', ['another-store']),
    ('observed_at', '2026-09-17T05:00:00+00:00')])
def test_changed_relevant_evidence_cannot_inherit_approval(field, value):
    evidence, review = fixture()
    evidence[field] = value
    with pytest.raises(ValueError, match='changed_or_unreviewed_evidence'):
        reviewed_flyer_batch(evidence, review, account_id='fixture-store')


@pytest.mark.parametrize('field,value', [('eligibility', 'personal'), ('deposit_status', 'unknown'),
    ('limit_status', 'unknown'), ('price', '1'), ('valid_from', '2026-09-14')])
def test_modified_terms_cannot_inherit_review(field, value):
    evidence, review = fixture()
    review = deepcopy(review)
    review['terms'][field] = value
    with pytest.raises(ValueError, match='changed_reviewed_terms'):
        reviewed_flyer_batch(evidence, review, account_id='fixture-store')
