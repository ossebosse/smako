"""Synthetic transport regressions; actual CPU pilot is reported separately."""
import json
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

from grocery_data.app.services.ica_flyer_ollama import (
    Settings,
    analyze,
    flag_literal_nulls,
    model_identity,
)
from grocery_data.app.services.ica_flyer_openai import PageExtraction, VisionBlocked, bind_result
from grocery_data.app.services.ica_flyer_pipeline import visual_timeout_seconds
from grocery_data.app.services.ica_flyer_review import review_key
from grocery_data.tests.test_ica_flyer_openai import checked, extracted, request


@pytest.mark.parametrize('endpoint', ['https://127.0.0.1:11434', 'http://localhost:11434',
    'http://example.com:11434', 'http://192.168.1.2:11434', 'http://user:secret@127.0.0.1',
    'http://127.0.0.1/path', 'http://127.0.0.1?proxy=cloud'])
def test_no_remote_endpoint_or_credentials(tmp_path, endpoint):
    with pytest.raises(VisionBlocked, match='loopback'):
        Settings(tmp_path, tmp_path/'cache', endpoint=endpoint)


@pytest.mark.parametrize('model', ['qwen3-vl:4b-cloud', 'qwen3-vl:235b-cloud', 'other'])
def test_no_cloud_model_or_implicit_download(tmp_path, model):
    with pytest.raises(VisionBlocked, match='explicit_local'):
        Settings(tmp_path, tmp_path/'cache', model=model)


def transport(calls, *, incomplete=False, cloud=False, digest='fixture-digest', failure=None):
    def handle(r):
        assert r.url.host == '127.0.0.1' and 'authorization' not in r.headers
        if r.url.path == '/api/tags':
            return httpx.Response(200, json={'models':[{'name':'qwen3-vl:4b-instruct','digest':digest}]})
        if r.url.path == '/api/show':
            return httpx.Response(200, json={'capabilities':['vision','completion'],
                **({'remote_host':'cloud.example'} if cloud else {})})
        assert r.url.path == '/api/chat'  # No pull, paid fallback, or other HTTP operation.
        body=json.loads(r.content); calls.append(body)
        assert body['stream'] is False and body['think'] is False
        assert body['keep_alive']==0  # Do not accumulate an in-memory multi-page prompt cache on the beta host.
        assert body['options']['num_thread']==2
        assert body['format']['additionalProperties'] is False
        images=[v for v in body['messages'] if v.get('images')]
        assert images and all(v['images'][0].startswith('iVBOR') for v in images)
        value=checked() if 'Independently inspect' in body['messages'][0]['content'] else extracted()
        assert len(images[0]['images']) == (5 if 'boxes' in value else 1)
        if failure=='timeout':raise httpx.ReadTimeout('fixture timeout',request=r)
        if failure=='http':return httpx.Response(503,json={'error':'fixture local server unavailable'})
        return httpx.Response(200,json={'model':'qwen3-vl:4b-instruct','done':True,
            'done_reason':'length' if incomplete else 'stop','message':{'content':json.dumps(value)},
            'eval_count':123,'prompt_eval_count':456})
    return httpx.MockTransport(handle)


@pytest.mark.parametrize('failure,reason',[('timeout','local_inference_timeout_no_fallback'),
    ('http','local_inference_http_503')])
def test_failures_are_explicit_and_do_not_retry_or_call_external_model(tmp_path,failure,reason):
    calls=[]
    with (httpx.Client(transport=transport(calls,failure=failure)) as client,
          pytest.raises(VisionBlocked,match=reason)):
        analyze(request(tmp_path),Settings(tmp_path,tmp_path/'cache'),client=client)
    assert len(calls)==1 and not list((tmp_path/'cache').glob('*.json'))


def test_real_png_payload_and_cache_do_not_refresh_observation_or_leak_scope(tmp_path):
    req=request(tmp_path);calls=[];cfg=Settings(tmp_path,tmp_path/'cache')
    with httpx.Client(transport=transport(calls)) as client:
        first=analyze(req,cfg,client=client)
        req['evidence']['observed_at']='2026-09-17T00:00:00+00:00'
        req['evidence']['official_store_ids']=['different-proven-association']
        second=analyze(req,cfg,client=client)
        assert len(calls)==2
        req['source_context']={'title':'Different campaign conditions'}
        third=analyze(req,cfg,client=client)
    assert len(calls)==4 and not first['cache_hit'] and second['cache_hit']
    assert second['evidence_sha256']==review_key(req['evidence']) != first['evidence_sha256']
    assert third['model_cache_key'] != first['model_cache_key']
    assert 'fixture-store' not in json.dumps(calls)
    assert not first['price_import_approved'] and first['paid_api_cost_usd']==0
    assert not first['external_fallback']
    assert first['current_model_requests']==2 and second['current_model_requests']==0
    assert 'unverified_gtin' in first['ads'][0]['contract_blockers']


def test_extraction_only_pilot_keeps_prices_but_cannot_approve(tmp_path):
    calls=[];cfg=Settings(tmp_path,tmp_path/'cache',verify=False)
    with httpx.Client(transport=transport(calls)) as client:
        result=analyze(request(tmp_path),cfg,client=client)
    assert len(calls)==1 and not result['complete']
    assert result['ads'][0]['extracted_price_marks'][0]['amount']==30
    assert 'local_independent_image_check_not_run' in result['ads'][0]['uncertainties']
    assert result['ads'][0]['gtin'] is None


def test_generation_limit_retains_raw_response_without_cache_approval(tmp_path):
    cfg=Settings(tmp_path,tmp_path/'cache');calls=[]
    with (httpx.Client(transport=transport(calls,incomplete=True)) as client,
          pytest.raises(VisionBlocked,match='incomplete_raw_retained')):
        analyze(request(tmp_path),cfg,client=client)
    assert len(calls)==1
    paths=list(cfg.cache.glob('*.json'))
    assert len(paths)==1 and paths[0].name.endswith('-raw-extraction.json')
    assert json.loads(paths[0].read_bytes())['metrics']['eval_count']==123


def test_weights_must_be_local_even_with_allowed_name(tmp_path):
    cfg=Settings(tmp_path,tmp_path/'cache')
    with (httpx.Client(transport=transport([],cloud=True)) as client,
          pytest.raises(VisionBlocked,match='cloud_forbidden')):
        model_identity(client,cfg)
    with (httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'models':[]}))) as client,
          pytest.raises(VisionBlocked,match='no_automatic_download')):
        model_identity(client,cfg)


def test_changed_weights_invalidates_transcription_cache(tmp_path):
    req=request(tmp_path);cfg=Settings(tmp_path,tmp_path/'cache',verify=False);calls=[]
    with httpx.Client(transport=transport(calls)) as client:first=analyze(req,cfg,client=client)
    with httpx.Client(transport=transport(calls,digest='changed')) as client:second=analyze(req,cfg,client=client)
    assert len(calls)==2 and first['model_cache_key']!=second['model_cache_key']


def test_explicit_bounded_process_timeout_keeps_existing_default(monkeypatch):
    monkeypatch.delenv('ICA_FLYER_VISUAL_TIMEOUT_SECONDS',raising=False)
    assert visual_timeout_seconds()==240
    monkeypatch.setenv('ICA_FLYER_VISUAL_TIMEOUT_SECONDS','1900')
    assert visual_timeout_seconds()==1900
    monkeypatch.setenv('ICA_FLYER_VISUAL_TIMEOUT_SECONDS','100000')
    with pytest.raises(ValueError):visual_timeout_seconds()


def test_resource_limits_are_bounded(tmp_path):
    cfg=Settings(tmp_path,tmp_path/'cache')
    for change in ({'threads':12},{'context':32768},{'timeout':3600},{'output_tokens':0}):
        with pytest.raises(VisionBlocked):replace(cfg,**change)


def test_actual_local_failure_cannot_hide_prices_as_null_nonprice_or_fabricate_identity(tmp_path):
    saved=json.loads((Path(__file__).parent/'fixtures/ica/local-vision-20260920-initial.json').read_bytes())
    parsed=PageExtraction.model_validate_json(saved['response']['message']['content']).model_dump(mode='json')
    assert parsed['ads'][0]['not_price_ad']=='null'
    value=flag_literal_nulls(parsed)
    result=bind_result(request(tmp_path),value,{'complete':False,'boxes':[],
        'missing_price_ads':[],'shared_issues':['real_pilot_wrong_target_and_product_association']},
        cache_key='real-failure-fixture',calls=[],cache_hit=False)
    ad=result['ads'][0]
    assert ad['gtin'] is None and ad['not_price_ad'] is None
    assert ad['extraction_status']=='needs_review' and len(ad['extracted_price_marks'])==10
    assert ad['price'] is None and 'no_single_explicit_purchase_amount' in ad['contract_blockers']
    assert 'literal_null_in_optional_field:gtin' in ad['uncertainties']
    assert not result['price_import_approved']


def test_crop_is_original_evidence_bound_partial_and_boxes_map_to_page(tmp_path):
    req=request(tmp_path);req['focus_bbox']=[.1,.2,.6,.8]
    cfg=Settings(tmp_path,tmp_path/'cache',verify=False)
    with httpx.Client(transport=transport([])) as client:
        result=analyze(req,cfg,client=client)
    assert result['ads'][0]['bbox']==req['focus_bbox']
    assert result['ads'][0]['prices'][0]['bbox']==pytest.approx([.15,.26,.35,.5])
    assert not result['complete'] and 'partial_page_focus_only' in result['page_issues']
    assert result['evidence_sha256']==review_key(req['evidence'])


def test_unknown_nonprice_classification_is_quarantine_not_a_reason_to_drop_ad():
    value=extracted();value['ads'][0]['not_price_ad']='unknown'
    result=flag_literal_nulls(value)
    assert result['ads'][0]['not_price_ad'] is None
    assert 'nonprice_classification_unproven' in result['ads'][0]['uncertainties']


def test_real_target_response_keeps_all_prices_and_does_not_repair_wrong_amount(tmp_path):
    saved=json.loads((Path(__file__).parent/'fixtures/ica/local-vision-20260920-target.json').read_bytes())
    value=flag_literal_nulls(PageExtraction.model_validate_json(
        saved['response']['message']['content']).model_dump(mode='json'))
    assert len(value['ads'])==4
    assert all(a['not_price_ad'] is None for a in value['ads'])
    assert value['ads'][0]['prices'][0]['amount']==12  # Actual model error: visually verified source says 19.
    assert value['ads'][0]['prices'][0]['unit']=='st'
    assert value['ads'][1]['prices'][0]['unit']=='group' and value['ads'][1]['quantity']==2
    assert value['ads'][3]['prices'][0]['amount']==14 and value['ads'][3]['quantity']==2
    assert all('purchase_currency_unverified' in a['uncertainties'] for a in value['ads'])
    result=bind_result(request(tmp_path),value,{'complete':False,'boxes':[],
        'missing_price_ads':[],'shared_issues':['held_out_pilot_not_approved']},
        cache_key='actual-target-fixture',calls=[],cache_hit=False)
    assert {a['extraction_status'] for a in result['ads']}=={'needs_review'}
    assert all(a['gtin'] is None and a['deposit']['status']=='unknown' for a in result['ads'])


def test_actual_comparison_prices_cannot_become_purchase_even_with_piece_unit():
    saved=json.loads((Path(__file__).parent/'fixtures/ica/local-vision-20260920-comparison-failure.json').read_bytes())
    original=PageExtraction.model_validate_json(saved['response']['message']['content']).model_dump(mode='json')
    assert len(original['ads'])==3 and all(a['prices'][0]['role']=='purchase' for a in original['ads'])
    result=flag_literal_nulls(original)
    assert [a['prices'][0]['amount'] for a in result['ads']]==[25,60,83.33]
    assert all('comparison_label_misclassified_as_purchase' in a['uncertainties'] for a in result['ads'])
    # Unit-based rejection must not be the only barrier for a printed Jfr/st price.
    row=extracted();row['ads'][0]['prices'][0].update(unit='st',text='Jfr pris 30:00/st')
    assert 'comparison_label_misclassified_as_purchase' in flag_literal_nulls(row)['ads'][0]['uncertainties']
