"""Actual Oct 10 Coop responses and retained Oct 9 quantity evidence."""
import gzip
import hashlib
import json
from decimal import Decimal
from pathlib import Path

import pytest

from grocery_data.app.connectors.coop import CoopParser
from grocery_data.app.connectors.coop.online_catalog_parser import _package
from grocery_data.app.connectors.coop.structured_offers import sanitized_response
from grocery_data.app.domain import RawBatch, RawFetch, SourceStore
from grocery_data.app.services.offer_rows import qualify_rows

ROOT=Path(__file__).parent/'fixtures/comparability-20261010'

def capture(sid):
    data=gzip.decompress((ROOT/f'coop-{sid}.json.gz').read_bytes())
    proof=json.loads((ROOT/f'coop-{sid}-proof.json').read_bytes())
    assert hashlib.sha256(data).hexdigest()==proof['sha256'] and len(data)==proof['bytes']
    raw=RawFetch.model_validate_json(gzip.decompress((ROOT/f'coop-{sid}-fetch.json.gz').read_bytes()))
    env=json.loads(raw.payload)
    env['structured_offers'].pop('error',None);env['structured_offers'].pop('schema_review_reason',None)
    env['structured_offers']['data']=sanitized_response(json.loads(data))
    physical=next(r for r in json.loads((ROOT/'official-physical-stores.json').read_bytes()) if r['external_store_id']==sid)
    store=SourceStore(chain='coop',external_id=sid,name=physical['name'],address=physical['address'],city=physical['city'],postal_code=physical['postal_code'],coverage='offers_only',price_context_type='physical_store',physical_store_external_id=sid,raw_reference=physical['official_source'],source_fields={'store_page_path':env['store_page_path'],'ledger_account_number':env['structured_offers']['ledger_account_number']})
    return store,raw.model_copy(update={'payload':json.dumps(env).encode()}),env

@pytest.mark.parametrize('sid,total',[('3659',249),('3820',250)])
def test_actual_scan_both_stores_preserve_blocked_buy_pay_and_scope(sid,total):
    store,raw,_=capture(sid)
    parsed=CoopParser().parse_catalog(RawBatch(chain='coop',store_external_id=sid,documents=(raw,)),['raw:retained-oct10'],store)
    approved,_evidence=qualify_rows(parsed,store=store,observed_at=raw.fetched_at)
    assert not parsed.failures and len(parsed.products)==total
    scan=next(p for p in approved.products if 'ytterfil' in p.name.lower())
    assert scan.offers[0].price==65 and scan.offers[0].member_only
    assert scan.offers[0].max_quantity==2 and scan.sale_unit=='kg'
    assert scan.store_external_id==sid and scan.fetched_at==raw.fetched_at and scan.gtin is None
    blocked=[p for p in parsed.products if 'buy_x_pay_y_variant_prices_unverified' in p.source_fields.get('purchase_blockers',[])]
    assert len(blocked)==40 and all(p.offers[0].price is None for p in blocked)
    assert not any(p in approved.products for p in blocked)
    assert len(approved.products)==160
    # Different physical shop or ledger never inherits this price.
    other=store.model_copy(update={'external_id':'other'})
    bad=CoopParser().parse_catalog(RawBatch(chain='coop',store_external_id='other',documents=(raw,)),['raw:retained-oct10'],other)
    assert bad.failures and not bad.products

@pytest.mark.parametrize('field,value',[('weeklyTip',None),('weeklyTip','true'),('unreviewedField',False)])
def test_schema_still_rejects_unreviewed_or_wrong_types(field,value):
    with pytest.raises(ValueError): sanitized_response({'sortingGroups':[{'id':'alla','offerAmount':1,'offers':[{'id':'1','priceInformation':{},'content':{},field:value}]}]})

@pytest.mark.parametrize('field,value',[('buyAmount',True),('payAmount','2'),('claim',False)])
def test_buy_pay_schema_types(field,value):
    with pytest.raises(ValueError): sanitized_response({'sortingGroups':[{'id':'alla','offerAmount':1,'offers':[{'id':'1','priceInformation':{field:value},'content':{}}]}]})

def test_actual_garlic_printed_quantity_without_price_division():
    r=json.loads((ROOT/'product-036a35871545499789de7cf99ddd0451.json').read_bytes())['record']
    assert _package(r)==(Decimal(57),'g')
    assert _package({**r,'packageSizeInformation':'57'})==(None,None)
    assert _package({**r,'packageSizeInformation':'ca 57 g'})==(None,None)
    assert _package({**r,'packageSize':10000,'packageSizeUnit':'Millimeter'})==(None,None)
