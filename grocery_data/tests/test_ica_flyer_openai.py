"""Adapter/transport regressions with explicit synthetic responses, not live acceptance."""
import hashlib
import json
from decimal import Decimal

import httpx
import pymupdf
import pytest

from grocery_data.app.services.ica_flyer_openai import (
    Settings,
    VisionBlocked,
    analyze,
    bind_result,
    prepare_images,
)
from grocery_data.app.services.ica_flyer_review import review_key


def request(tmp_path):
    pdf=tmp_path/'fixture.pdf'
    with pymupdf.open() as doc:
        page=doc.new_page();page.insert_text((30,60),'Fixture product 2 for 30 SEK')
        doc.save(pdf)
    return {'protocol':'smako-public-flyer-page-v1','document':str(pdf),'evidence':{
        'issue_id':'fixture','pdf_sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),'page':1,
        'official_store_ids':['fixture-store'],'observed_at':'2026-09-19T16:30:00+00:00',
        'source_url':'https://example.test/public.pdf'}}


def ad():
    return {'box':'a1','bbox':[0,0,1,1],'name':'Fixture product','brand':None,'package':None,
        'gtin':None,'variant_evidence':None,'raw_text':'Fixture product 2 for 30 SEK',
        'prices':[{'role':'campaign','amount':30,'currency':'SEK','unit':'group','text':'2 for 30 SEK','bbox':[.1,.1,.5,.5]}],
        'quantity':2,'eligibility':'public','activation':'not_required','mixing':None,
        'limit_status':'unknown','max_purchases':None,'limit_evidence':None,
        'valid_from':None,'valid_to':None,'date_evidence':None,
        'deposit':{'status':'unknown','per_container':None,'containers_per_package':None,'inclusion':'unknown','evidence':None},
        'shared_conditions':None,'uncertainties':[],'not_price_ad':None}


def extracted():return {'complete':True,'page_issues':[],'ads':[ad()]}
def checked():return {'complete':True,'missing_price_ads':[],'shared_issues':[],'boxes':[{'box':'a1','issues':[]}]}


def settings(tmp_path):return Settings(tmp_path,tmp_path/'cache',budget_usd=Decimal(2),paid_enabled=True)


def test_real_image_payload_two_passes_cache_and_scope_are_program_bound(tmp_path,monkeypatch):
    req=request(tmp_path);calls=[];monkeypatch.setenv('OPENAI_API_KEY','test-not-a-real-key')
    def handle(r):
        body=json.loads(r.content);calls.append(body)
        assert body['store'] is False and 'tools' not in body
        images=[c for c in body['input'][0]['content'] if c['type']=='input_image']
        assert len(images)==5 and images[0]['image_url'].startswith('data:image/png;base64,')
        assert 'fixture-store' not in str(body) and req['evidence']['observed_at'] not in str(body)
        value=extracted() if len(calls)==1 else checked()
        return httpx.Response(200,json={'id':'fixture-response','status':'completed','usage':{'input_tokens':100,'output_tokens':100},
            'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(value)}]}]})
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        first=analyze(req,settings(tmp_path),client=client)
        req['evidence']['official_store_ids']=['other-official-association']
        req['evidence']['observed_at']='2026-09-18T16:00:00+00:00'
        cached=analyze(req,settings(tmp_path),client=client)
    assert len(calls)==2 and not first['cache_hit'] and cached['cache_hit']
    assert cached['evidence_sha256']==review_key(req['evidence'])!=first['evidence_sha256']
    assert cached['ads'][0]['extraction_status']=='extracted'  # GTIN absence never deletes an advertised price.
    assert 'unverified_gtin' in cached['ads'][0]['contract_blockers']
    assert not cached['price_import_approved']


@pytest.mark.parametrize('change,reason',[
    ('hash','document_hash_mismatch'),('outside','document_outside'),('page','page_out_of_range'),('time','timezone')])
def test_source_binding_rejects_before_network(tmp_path,change,reason):
    req=request(tmp_path);cfg=settings(tmp_path)
    if change=='hash':req['evidence']['pdf_sha256']='0'*64
    elif change=='outside':cfg=Settings(tmp_path/'cache',tmp_path/'cache');cfg.source_root.mkdir()
    elif change=='page':req['evidence']['page']=2
    else:req['evidence']['observed_at']='2026-09-19T16:30:00'
    with pytest.raises(VisionBlocked,match=reason):prepare_images(req,cfg)


@pytest.mark.parametrize('budget,enabled,reason',[('0',True,'not_authorized'),('2',False,'not_authorized'),('.001',True,'cost_limit')])
def test_cost_gate_precedes_any_paid_request(tmp_path,monkeypatch,budget,enabled,reason):
    monkeypatch.setenv('OPENAI_API_KEY','fixture');req=request(tmp_path)
    cfg=Settings(tmp_path,tmp_path/'cache',budget_usd=Decimal(budget),paid_enabled=enabled)
    with pytest.raises(VisionBlocked,match=reason):analyze(req,cfg,client=object())


def test_timeout_reserves_budget_and_does_not_repeat_ambiguous_bill(tmp_path,monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','fixture');req=request(tmp_path)
    def timeout(r):raise httpx.ReadTimeout('do not expose credential',request=r)
    with httpx.Client(transport=httpx.MockTransport(timeout)) as client:
        with pytest.raises(VisionBlocked,match='uncertain_charge'):analyze(req,settings(tmp_path),client=client)
        with pytest.raises(VisionBlocked,match='reconciliation'):analyze(req,settings(tmp_path),client=client)
    ledger=json.loads((tmp_path/'cache/usage.json').read_bytes())
    assert len(ledger['attempts'])==1 and 'estimated_usd_from_usage' not in ledger['attempts'][0]


def test_schema_success_or_empty_uncertainty_does_not_bless_wrong_price(tmp_path):
    req=request(tmp_path);value=extracted();value['ads'][0]['prices'][0]['amount']=99
    result=bind_result(req,value,checked(),cache_key='fixture',calls=[],cache_hit=False)
    assert result['ads'][0]['extraction_status']=='needs_review'
    assert 'numeric_amount_not_in_literal_price_text' in result['ads'][0]['extraction_issues']
    check=checked();check['boxes'][0]['issues']=['price belongs to adjacent product']
    result=bind_result(req,extracted(),check,cache_key='fixture',calls=[],cache_hit=False)
    assert 'price belongs to adjacent product' in result['ads'][0]['uncertainties']


def test_kg_reference_percentage_prices_are_preserved_without_invented_pack(tmp_path):
    value=extracted();value['ads'][0]['prices'][0].update(unit='kg')
    result=bind_result(request(tmp_path),value,checked(),cache_key='fixture',calls=[],cache_hit=False)
    assert result['ads'][0]['extracted_price_marks'][0]['amount']==30
    assert 'unit_rate_is_not_package_price' in result['ads'][0]['contract_blockers']


def test_incomplete_shared_context_blocks_every_purchase_but_retains_prices(tmp_path):
    value=extracted();check=checked();check['complete']=False
    result=bind_result(request(tmp_path),value,check,cache_key='fixture',calls=[],cache_hit=False)
    assert not result['complete']
    assert 'page_or_independent_verification_incomplete' in result['ads'][0]['uncertainties']
    assert result['ads'][0]['extracted_price_marks'][0]['amount']==30


def test_changed_source_context_invalidates_cache(tmp_path,monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','fixture');req=request(tmp_path);count=[]
    def handle(r):
        count.append(r)
        return httpx.Response(200,json={'status':'completed','usage':{'input_tokens':1,'output_tokens':1},
            'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(extracted() if len(count)%2 else checked())}]}]})
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        first=analyze(req,settings(tmp_path),client=client)
        req['source_context']={'title':'Changed campaign title 2026-39'}
        second=analyze(req,settings(tmp_path),client=client)
    assert len(count)==4 and first['model_cache_key']!=second['model_cache_key']
