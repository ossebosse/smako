"""Reviewed public metadata must not change price or purchase qualification."""
import copy
import json
from pathlib import Path

import pytest

from grocery_data.app.connectors.coop import CoopParser
from grocery_data.app.connectors.coop.structured_offers import PARSER, sanitized_response
from grocery_data.tests.test_coop_physical_structured import parse, source


def test_observed_public_environmental_rows_are_retained():
    fixture = json.loads((Path(__file__).parent / 'fixtures/coop-environmental-code-20261029.json').read_bytes())
    assert {row['store_id'] for row in fixture['observations']} == {'3659', '3815'}
    for observation in fixture['observations']:
        row = observation['row']
        data = {'sortingGroups': [{'id': 'alla', 'offerAmount': 1, 'offers': [row]}]}
        assert sanitized_response(data) == data
        assert row['environmentalCode'] == 'A'
    assert CoopParser.parser_version == PARSER == 'coop-parser-v7'


@pytest.mark.parametrize('account', ['3839', '3815'])  # Lund and Malmö.
def test_metadata_on_parents_and_children_preserves_prices_and_all_blockers(account):
    baseline, accepted, evidence = parse(account)

    def annotate(envelope):
        def visit(row):
            row['environmentalCode'] = 'A'
            for child in row.get('clusterInteriorOffers', []):
                visit(child)
        data = envelope['structured_offers']['data']
        for group in data['sortingGroups']:
            for row in group['offers']:
                visit(row)
        envelope['structured_offers']['data'] = sanitized_response(data)

    changed, changed_accepted, changed_evidence = parse(account, mutate=annotate)
    assert not changed.failures and len(changed.products) == len(baseline.products)
    assert [p.external_product_id for p in changed_accepted.products] == [p.external_product_id for p in accepted.products]
    assert changed_evidence['shared_blockers'] == evidence['shared_blockers']
    assert changed_evidence['decisions'] == evidence['decisions']
    assert changed_accepted.failures and all(f.parser_version == PARSER for f in changed_accepted.failures)
    for before, after in zip(baseline.products, changed.products, strict=True):
        # Only the raw source record and its content hash may differ.
        old, new = before.model_dump(mode='json'), after.model_dump(mode='json')
        for product in (old, new):
            product['source_fields'].pop('source_sha256')
            for offer in product['offers']:
                payload = offer['source_payload']
                payload.pop('source_sha256')
                def remove_metadata(row):
                    row.pop('environmentalCode', None)
                    for child in row.get('clusterInteriorOffers', []):
                        remove_metadata(child)
                remove_metadata(payload['source_record'])
        assert old == new
        assert after.offers[0].source_payload['source_record']['environmentalCode'] == 'A'


@pytest.mark.parametrize('value', [None, '', 'B', 'a', True, 1, ['A'], {'code': 'A'}])
@pytest.mark.parametrize('child', [False, True])
def test_unreviewed_values_and_types_remain_blocked(value, child):
    _, batch = source()
    payload = json.loads(batch.documents[0].payload)['structured_offers']['data']
    row = payload['sortingGroups'][0]['offers'][0]
    if child:
        nested = copy.deepcopy(row)
        nested.pop('clusterInteriorOffers', None)
        row['clusterInteriorOffers'] = [nested]
        row = nested
    row['environmentalCode'] = value
    with pytest.raises(ValueError, match=r'row.environmentalCode.*schema review'):
        sanitized_response(payload)


def test_reviewed_metadata_does_not_allow_other_unknown_conditions():
    _, batch = source()
    payload = json.loads(batch.documents[0].payload)['structured_offers']['data']
    row = payload['sortingGroups'][0]['offers'][0]
    row.update(environmentalCode='A', activationRequired=True)
    with pytest.raises(ValueError, match=r'row.activationRequired'):
        sanitized_response(payload)
