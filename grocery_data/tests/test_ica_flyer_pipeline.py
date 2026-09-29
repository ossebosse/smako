import json
from pathlib import Path

import pytest

from grocery_data.app.domain import RawBatch
from grocery_data.app.services.ica_flyer_pipeline import classify_observations, link_ad, price_facts

ROOT = Path(__file__).parent/'fixtures/ica/area-20260916'


def test_real_89_boxes_have_concrete_source_ids_and_lineage_not_campaign_only():
    ads=json.loads((ROOT/'visual-boxes.json').read_bytes())
    sources={a:RawBatch.model_validate_json((ROOT/f'{a}.json').read_bytes()).documents[0].json_payload()['offers']['weeklyOffers'] for a in ['1004598','1004339']}
    results=[]
    for ad in ads:
        account=ad['evidence']['official_store_ids'][0]
        result=link_ad(ad,account=account,rows=sources[account],lineage={})
        if result['status']=='matched_structured_offer':
            assert result['source_id']==ad['source_offer_id']
            assert result['stages']['raw'] is True
            assert result['checkout_qualified'] is False  # No unverified downstream claim.
        results.append(result)
    assert sum(r['status']=='matched_structured_offer' for r in results)==89
    assert sum(r['status']=='blocked' for r in results)==5


def test_reference_and_comparison_and_percent_are_preserved_without_checkout_inference():
    row={'id':'fixture','parsedMechanics':{'benefitType':'PERCOFF','value1':20},
         'details':{'mechanicInfo':'20% rabatt','packageInformation':'500 g'},
         'comparisonPrice':'40 kr/kg','stores':[{'regularPrice':30,'accountNumber':'fixture'}]}
    facts=price_facts(row)
    assert facts['price_kind']=='percentage' and facts['percentage_basis'] is None
    assert facts['comparison_text']=='40 kr/kg'
    assert facts['reference_prices'][0]['current_checkout_proven'] is False
    assert 'checkout_price' not in facts


def test_observation_counts_distinguish_unchanged_changed_new_and_duplicate():
    old=[{'store_id':'a','source_id':'1','content_sha256':'old'}]
    new=[{'store_id':'a','source_id':'1','content_sha256':'old'},
         {'store_id':'a','source_id':'1','content_sha256':'old'},
         {'store_id':'a','source_id':'2','content_sha256':'new'},
         {'store_id':'b','source_id':'1','content_sha256':'old'}]
    assert classify_observations(new,old)=={'reobserved_unchanged':1,'duplicate':1,'new':2}
    assert classify_observations([{'store_id':'a','source_id':'1','content_sha256':'changed'}],old)=={'changed':1}


def test_missing_price_fields_cannot_become_matched_or_approved():
    result=link_ad({'source_offer_id':'a'},account='b',rows=[{'id':'a'}],lineage={})
    assert result['status']=='blocked' and result['reason']=='unextracted_price_terms'


def test_reviewed_flyer_duplicate_preserves_evidence_age_and_conflicts_quarantine_both():
    from datetime import timedelta

    from grocery_data.app.connectors.ica.parser import IcaParser
    from grocery_data.app.domain import ProductParseResult, SourceStore
    from grocery_data.app.services.ica_flyer_pipeline import reconcile_flyer_products
    raw = RawBatch.model_validate_json((ROOT/'1004598.json').read_bytes())
    parsed = IcaParser().parse_catalog(raw, ['real-source'], SourceStore(
        chain='ica', external_id='1004598', name='Linero', city='Lund', raw_reference='fixture',
        coverage='offers_only', source_fields={'store_id':'15172'}))
    original = next(p for p in parsed.products if p.gtin and p.offers[0].price)
    flyer = original.model_copy(update={'external_product_id':'flyer:fixture', 'raw_reference':'reviewed-box',
                                       'fetched_at': original.fetched_at-timedelta(hours=1)})
    result, decisions = reconcile_flyer_products(ProductParseResult(products=[original,flyer]))
    assert len(result.products)==1 and not result.failures and decisions[0]['status']=='duplicate'
    assert result.products[0].fetched_at==flyer.fetched_at
    assert 'reviewed-box' in result.products[0].source_fields['source_evidence']
    conflicting = flyer.model_copy(update={'offers':(flyer.offers[0].model_copy(update={'member_only':not flyer.offers[0].member_only}),)})
    result, decisions = reconcile_flyer_products(ProductParseResult(products=[original,conflicting]))
    assert not result.products and len(result.failures)==2
    other_store = conflicting.model_copy(update={'store_external_id':'1004339'})
    result, _ = reconcile_flyer_products(ProductParseResult(products=[original,other_store]))
    assert len(result.products)==2


async def test_configured_extraction_enters_existing_own_pipeline_and_unknown_deposit_does_not(tmp_path):
    from grocery_data.app.services.collector import GroceryCollector
    from grocery_data.app.services.ica_flyer_pipeline import (
        extraction_batch,
        import_area_extractions,
    )
    from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
    from grocery_data.app.storage import (
        create_database_engine,
        create_schema,
        create_session_factory,
    )
    from grocery_data.tests.test_ica_flyer_review import fixture
    evidence, review = fixture()
    ad = {'method':'configured_visual_extractor','uncertainties':[], 'box':evidence['box'],
        'evidence':evidence, 'terms':review['terms'], 'price_roles':{
            'advertised_purchase':30,'ordinary_label':None,'previous_reference':None,'comparison':None,
            'percent_discount':None,'percent_basis':None,'deposit':'verified_not_applicable'}}
    valid = extraction_batch(ad, account='fixture-store')
    uncertain = {**ad,'terms':{**ad['terms'],'deposit_status':'unknown'}}
    with pytest.raises(ValueError,match='deposit_checkout_contract_unverified'):
        extraction_batch(uncertain,account='fixture-store')
    with pytest.raises(ValueError,match='unverified_or_uncertain'):
        extraction_batch({**ad,'uncertainties':['layout']},account='fixture-store')
    # Synthetic empty structured page plus one independently verified flyer.
    doc=valid.documents[0]
    raw=valid.model_copy(update={'documents':(doc.model_copy(update={
        'payload':json.dumps({'offers':{'weeklyOffers':[]}}).encode()}),)})
    (tmp_path/'offers-fixture-store-batch.json').write_text(raw.model_dump_json())
    report={'area':{'city':'Fixture'},'inventory':{'complete':True},'stores':[{
        'ica_account_id':'fixture-store','ica_bms_id':None,'name':'Fixture','locality':'Fixture',
        'address':'Fixture 1','postal_code':'11111','discovery_sources':['fixture:official'],
        'official_store_url':'https://www.ica.se/butiker/fixture-store/',
        'offers_url':'https://www.ica.se/erbjudanden/fixture-store/', 'area_membership':'inside',
        'own_result':{'status':'healthy'},'flyers':[{'editions':[{'complete':True,
            'sha256':evidence['pdf_sha256'],'id':evidence['issue_id'],'pdf_url':evidence['source_url']}]}]}]}
    extraction={'pages':[{'account':'fixture-store','ads':[ad]}], 'ad_links':[]}
    database=tmp_path/'test.sqlite';engine=create_database_engine('sqlite:///'+str(database));create_schema(engine)
    collector=GroceryCollector(create_session_factory(engine),FilesystemRawSnapshotStore(tmp_path/'raw'))
    # Explicit historical regression data; timestamps are not current acceptance.
    result=await import_area_extractions(report,extraction,tmp_path,database=database,collector=collector)
    assert result['new_flyer_imports']==1
    assert result['extracted_imports'][0]['stages']['own_row_approved']
    assert report['stores'][0]['row_approved_own']==1
    engine.dispose()


def test_actual_local_and_central_egg_campaigns_share_one_purchase_cap():
    from datetime import datetime

    from grocery_data.app.connectors.ica.parser import IcaParser
    from grocery_data.app.domain import RawFetch, SourceStore
    from grocery_data.app.services.ica_flyer_pipeline import reconcile_flyer_products
    from grocery_data.app.services.offer_rows import qualify_rows
    payload=(Path(__file__).parent/'fixtures/ica/area-20260919/soderlivs-weekly.json').read_bytes()
    observed=datetime.fromisoformat('2026-09-19T16:00:22.608438+00:00')  # Historical regression clock, never live evidence.
    store=SourceStore(chain='ica',external_id='1004339',name='Söderlivs',city='Lund',address='Stora Södergatan 57',
        coverage='offers_only',raw_reference='fixture:locator',source_fields={
            'store_id':'2774','official_store_url':'https://www.ica.se/butiker/soderlivs-1004339/'})
    raw=RawBatch(chain='ica',documents=(RawFetch(chain='ica',kind='offers_page',method='GET',
        url='https://www.ica.se/erbjudanden/ica-nara-soderlivs-lund-1004339/',
        fetched_at=observed,http_status=200,connector_version='ica-v2',payload=payload),))
    parsed=IcaParser().parse_catalog(raw,['fixture:retained-sep19'],store)
    reconciled,decisions=reconcile_flyer_products(parsed)
    eggs=[p for p in reconciled.products if p.gtin=='7318690032977']
    assert len(eggs)==1 and eggs[0].offers[0].max_quantity==2 and eggs[0].offers[0].member_only
    assert eggs[0].source_fields['campaign_aliases']==['2005564335','5004125052']
    assert len(eggs[0].source_fields['source_evidence'])==2
    qualified,evidence=qualify_rows(reconciled,store=store,observed_at=observed,original_parsed=parsed)
    assert evidence['full_parse']['denominator']==57 and evidence['full_parse']['parsed']==52
    assert sum(p.gtin=='7318690032977' for p in qualified.products)==1
    assert sum(d['status']=='duplicate_campaign_alias' for d in decisions)==2
