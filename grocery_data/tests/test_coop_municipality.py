"""Actual public registry/SCB snapshots, offline; never a fresh-price claim."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from grocery_data.app.connectors.coop.municipality_inventory import build_inventory, make_store
from grocery_data.app.domain import GeographicArea, RawFetch
from grocery_data.app.services.area_membership import assess_area, reuse_municipality_evidence
from grocery_data.app.services.municipality_geometry import (
    SCB_URL,
    bind_position,
    position_membership,
)
from grocery_data.scripts.collect_coop_physical_offers import same_official_identity

FIX = Path(__file__).parent / 'fixtures/coop-municipality-20260921'


def evidence(code):
    payload = (FIX/f'regso-{code}.json').read_text(encoding='utf-8')
    return {'source_url': SCB_URL+'?fixture=retained', 'version': 'RegSO_2025', 'municipality_code': code,
                'payload': payload, 'source_sha256': hashlib.sha256(payload.encode()).hexdigest(),
                'observed_at': '2026-09-21T17:39:00+00:00'}


def inputs():
    raw = RawFetch.model_validate_json((FIX/'coop-map.json').read_bytes())
    xtra = json.loads((FIX/'xtra-registry.json').read_bytes())
    return json.loads(raw.payload)['stores'], xtra['stores'], [
        {'url': raw.url, 'sha256': raw.payload_hash, 'observed_at': raw.fetched_at.isoformat()}, xtra['source']]


def inventory(code, name):
    coop, xtra, sources = inputs()
    return build_inventory(GeographicArea(city=name, mode='municipality', municipality_code=code),
                           coop, xtra, evidence(code), sources)


def test_real_lund_all_concepts_and_non_lund_localities():
    report = inventory('1281', 'Lund')
    inside = [r for r in report['stores'] if r['geographic_evidence']['status']=='inside']
    assert len(inside)==10  # observed fixture, not a runtime expected count
    assert {'3841','1158','3658','3839','3837','3659','3656','3813','3820','2696'} == {
        r['store']['external_id'] for r in inside}
    assert len(report['selected_store_ids'])==9 and '3658' not in report['selected_store_ids']
    assert len(report['stores'])==778 and not report['complete']
    assert {r['store']['source_fields']['concept'] for r in inside}=={'Coop','Stora Coop','X:-tra'}


def test_same_code_second_municipality_no_manual_list():
    report = inventory('1280', 'Malmö')
    assert '3815' in report['selected_store_ids']  # Bulltofta, independently positioned
    assert '3839' not in report['selected_store_ids']
    assert '3841' not in report['selected_store_ids']
    assert len(report['stores'])==778  # failed/unknown/outside never disappear


def test_exact_alias_binding_and_conflicts():
    coop, _, sources = inputs()
    one = next(r for r in coop if str(r['storeId'])=='3839')
    alias = {**one, 'name':'Legacy verified alias'}
    area = GeographicArea(city='Lund',mode='municipality',municipality_code='1281')
    r = build_inventory(area,[one,alias],[],evidence('1281'),sources)
    assert len(r['stores'])==1 and r['selected_store_ids']==['3839']
    assert 'Coop Flöjtvägen' in r['stores'][0]['store']['source_fields']['aliases']
    alias['storeId']=999
    r = build_inventory(area,[one,alias],[],evidence('1281'),sources)
    assert r['selected_store_ids']==[] and r['stores'][0]['collection_reason']=='identity_conflict'
    assert r['stores'][0]['store']['source_fields']['conflicting_record']['external_id']=='3839'


def test_bound_coordinates_unknown_missing_and_legacy_scope_unchanged():
    coop, _, sources = inputs()
    store = bind_position(make_store(next(r for r in coop if str(r['storeId'])=='3841'),sources[0]),evidence('1281'))
    area = GeographicArea(city='Lund',mode='municipality',municipality_code='1281',postal_codes=('99999',))
    assert assess_area(store,area)['status']=='inside'
    assert assess_area(store,GeographicArea(city='Lund'))['status']=='outside'
    assert assess_area(store.model_copy(update={'latitude':55}),area)['status']=='unknown'
    assert position_membership(None,None,evidence('1281'))[0]=='unknown'
    assert reuse_municipality_evidence(store,[store],area)==store


def test_partial_geometry_or_bad_hash_rejected():
    e=evidence('1281')
    with pytest.raises(ValueError,match='unbound'):position_membership(13,55,{**e,'source_sha256':'0'*64})
    data=json.loads(e['payload']); data['numberMatched']+=1
    e['payload']=json.dumps(data); e['source_sha256']=hashlib.sha256(e['payload'].encode()).hexdigest()
    with pytest.raises(ValueError,match='incomplete'):position_membership(13,55,e)


def test_hole_boundary_and_missing_position_are_not_guessed():
    e=evidence('1281');data=json.loads(e['payload']); f=copy.deepcopy(data['features'][0])
    f['geometry']={'type':'Polygon','coordinates':[
        [[13,55],[14,55],[14,56],[13,56],[13,55]],
        [[13.4,55.4],[13.6,55.4],[13.6,55.6],[13.4,55.6],[13.4,55.4]]]}
    data.update(features=[f],numberMatched=1,numberReturned=1)
    e['payload']=json.dumps(data);e['source_sha256']=hashlib.sha256(e['payload'].encode()).hexdigest()
    assert position_membership(13.2,55.2,e)[0]=='inside'
    assert position_membership(13.5,55.5,e)[0]=='outside'
    assert position_membership(13,55.5,e)[0]=='unknown'


def test_map_integer_string_account_fix_does_not_relax_identity():
    coop, _, sources=inputs();store=make_store(coop[0],sources[0])
    fresh=store.model_copy(update={'source_fields':{'ledger_account_number':int(store.source_fields['ledger_account_number'])}})
    assert same_official_identity(store,fresh)
    assert not same_official_identity(store,fresh.model_copy(update={'external_id':'WRONG'}))
    assert not same_official_identity(store,fresh.model_copy(update={'source_fields':{'ledger_account_number':999}}))


def test_real_stora_age_conditions_stay_in_quarantine_not_global_failure():
    from grocery_data.app.connectors.coop import CoopParser
    from grocery_data.app.domain import RawBatch, SourceStore
    from grocery_data.app.services.offer_rows import qualify_rows
    store=SourceStore.model_validate_json((FIX/'2696-store.json').read_bytes())
    batch=RawBatch.model_validate_json((FIX/'2696-batch.json').read_bytes())
    parsed=CoopParser().parse_catalog(batch,['real-stora-fixture'],store)
    assert not parsed.failures and len(parsed.products)==540
    accepted, evidence=qualify_rows(parsed,store=store,observed_at=batch.documents[0].fetched_at)
    assert len(accepted.products)==77
    blocked=[r for r in evidence['decisions'] if 'age_restriction_eligibility_unverified' in r['blockers']]
    assert len(blocked)==23
    assert evidence['full_parse']['denominator']==540
    assert evidence['full_parse']['threshold']==.95
