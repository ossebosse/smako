"""Synthetic transport failures: completeness is measured against source pages."""
import json
import sys
from types import SimpleNamespace

from grocery_data.scripts import ica_flyer_vision_batch as batch


def inputs(tmp_path,monkeypatch,extra=()):
    edition={'id':'fixture','sha256':'a'*64,'file':'fixture.pdf','fetched_pages':2,
             'source_pages':3,'pdf_url':'https://example.test/f.pdf',
             'fetched_at':'2026-09-19T12:00:00+00:00'}
    stores=[{'ica_account_id':str(i),'area_membership':'inside','collection_status':'success',
             'flyers':[{'editions':[edition]}]} for i in [1,2]]
    stores.append({'ica_account_id':'failed','area_membership':'unknown',
                   'collection_status':'failed','flyers':[]})
    (tmp_path/'db.sqlite').touch()
    (tmp_path/'universes').mkdir(exist_ok=True)
    coverage=tmp_path/'coverage.json'
    coverage.write_text(json.dumps({'stores':stores,'inventory':{'complete':False,'discovered':3}}))
    monkeypatch.setattr(sys,'argv',['worker','--coverage',str(coverage),'--source-root',str(tmp_path),
        '--output',str(tmp_path/'out'),'--operation-database',str(tmp_path/'db.sqlite'),
        '--price-universe-root',str(tmp_path/'universes'),*extra])


def test_failed_pages_and_stores_remain_in_denominator_and_resume(tmp_path,monkeypatch):
    inputs(tmp_path,monkeypatch);calls=[]
    def fail(*a,**kw):
        calls.append(json.loads(kw['input']))
        return SimpleNamespace(returncode=2,stdout='',stderr='{"status":"blocked","reason":"api_key_not_configured"}')
    monkeypatch.setattr(batch.subprocess,'run',fail)
    batch.main()
    result=json.loads((tmp_path/'out/batch.json').read_bytes())
    assert len(calls)==3 and len(result['pages'])==6 and len(result['stores'])==3
    assert {p['status'] for p in result['pages']}=={'blocked'}
    assert all(p['evidence']['observed_at']=='2026-09-19T12:00:00+00:00' for p in result['pages'])
    assert any(c['evidence']['page']==3 for c in calls)  # Missing source page cannot vanish.
    batch.main()
    assert len(calls)==6  # Access failure is resumable, never a cached success.


def test_inventory_only_never_calls_model_or_hides_remaining_pages(tmp_path,monkeypatch):
    inputs(tmp_path,monkeypatch,['--inventory-only'])
    monkeypatch.setattr(batch.subprocess,'run',lambda *a,**kw: (_ for _ in ()).throw(AssertionError('no calls')))
    batch.main()
    result=json.loads((tmp_path/'out/batch.json').read_bytes())
    assert result['selected_unique_pages']==3 and len(result['pages'])==6
    assert all(p['status']=='blocked_pending_verified_pilot_and_access' for p in result['pages'])


def test_explicit_local_command_timeout_and_changed_context_are_preserved(tmp_path,monkeypatch):
    inputs(tmp_path,monkeypatch)
    command=['python','-m','grocery_data.scripts.ica_flyer_ollama']
    monkeypatch.setenv('ICA_FLYER_VISUAL_COMMAND_JSON',json.dumps(command))
    monkeypatch.setenv('ICA_FLYER_VISUAL_TIMEOUT_SECONDS','1900')
    coverage=tmp_path/'coverage.json';value=json.loads(coverage.read_bytes())
    value['stores'][1]['flyers'][0]['editions'][0]['title']='Different narrow campaign conditions'
    coverage.write_text(json.dumps(value))
    calls=[]
    def worker(cmd,**kw):
        assert cmd==command and kw['timeout']==1900
        calls.append(json.loads(kw['input']))
        return SimpleNamespace(returncode=2,stdout='',stderr='{"status":"blocked","reason":"local_fixture_failure"}')
    monkeypatch.setattr(batch.subprocess,'run',worker)
    batch.main()
    assert len(calls)==6  # Identical PDF pixels cannot erase changed campaign context.
    result=json.loads((tmp_path/'out/batch.json').read_bytes())
    assert result['worker_command']==command and len(result['stores'])==3
