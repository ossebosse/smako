"""Retained real visual transcription vs the two real public source replies."""
import json
from collections import Counter
from pathlib import Path

from grocery_data.app.domain import RawBatch
from grocery_data.app.services.ica_flyer_review import compare_advertisement, review_blockers


def test_all_94_priority_ad_boxes_keep_exact_source_ids_and_blockers():
    root = Path(__file__).parent / 'fixtures/ica/area-20260916'
    ads = json.loads((root / 'visual-boxes.json').read_bytes())
    source = {}
    for account in ('1004598', '1004339'):
        batch = RawBatch.model_validate_json((root / f'{account}.json').read_bytes())
        source[account] = {r['id']: r for r in batch.documents[0].json_payload()['offers']['weeklyOffers']}
    counts = Counter()
    for ad in ads:
        account = ad['evidence']['official_store_ids'][0]
        row = source[account].get(ad['source_offer_id'])
        result = compare_advertisement(ad, row)
        assert result == ad['comparison']
        assert result['price_import'] is False
        assert review_blockers(ad['evidence'], {}, account_id=account)
        counts[result['status']] += 1
    assert len(ads) == 94
    assert counts == {'already_covered': 89, 'blocked': 4, 'needs_review': 1}


def test_same_campaign_id_cannot_hide_different_terms():
    root = Path(__file__).parent / 'fixtures/ica/area-20260916'
    ad = next(a for a in json.loads((root / 'visual-boxes.json').read_bytes())
              if a['name'] == 'Fond')
    row = next(r for r in RawBatch.model_validate_json((root / '1004339.json').read_bytes()).documents[0].json_payload()['offers']['weeklyOffers']
               if r['id'] == ad['source_offer_id'])
    # Deliberately corrupted review, not a retailer-price assertion.
    result = compare_advertisement({**ad, 'price': 38, 'member': False}, row)
    assert result['status'] == 'needs_review'
    assert set(result['differences']) == {'price', 'member'}
