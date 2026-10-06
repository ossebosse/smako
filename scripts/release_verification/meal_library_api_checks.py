"""Owned real HTTP jobs, cross-meal pantry allocation and explicit replacements.

Cookies remain only in client memory. Never print/write request headers or tokens.
Run against the disposable meal app, never production.
"""
import argparse
import hashlib
import json
import time
import uuid
from pathlib import Path

import httpx

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--base',required=True);parser.add_argument('--request',type=Path,required=True)
parser.add_argument('--pack',type=Path,required=True,help='Exact content pack, never a product override')
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args();assert args.base.startswith('http://127.0.0.1:18128')
args.output.mkdir(parents=True,exist_ok=True)
def dump(name,value):(args.output/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
def fingerprint(saved):return hashlib.sha256(json.dumps({'plan':saved['plan'],'request':saved['request']},sort_keys=True).encode()).hexdigest()
def resolve(client,response):
    response.raise_for_status();url=response.json().get('status_url');reference=response.json().get('request_id')
    if not url:return response.json()
    deadline=time.monotonic()+900
    while time.monotonic()<deadline:
        status=client.get(url);assert status.status_code in {201,202},status.text
        if status.status_code==201:
            assert status.headers.get('x-plan-request-id')==reference
            return status.json()
        time.sleep(2)
    raise TimeoutError('Retain original job, no new generation')
with httpx.Client(base_url=args.base,headers={'Origin':args.base},timeout=60) as actor, httpx.Client(base_url=args.base,headers={'Origin':args.base},timeout=60) as other:
    actor.get('/').raise_for_status();other.get('/').raise_for_status()
    state=actor.get('/api/personal/state').json()
    pantry_id=str(uuid.uuid4())
    write=actor.put('/api/personal/pantry',json={'revision':state['revision'],'items':[
        {'id':pantry_id,'name':'ost','quantity':100,'unit':'g','form':'as_sold','food':True,'unusable':False}]})
    write.raise_for_status();state=write.json()
    assert not other.get('/api/personal/state').json()['items']
    request=json.loads(args.request.read_text(encoding='utf8'))
    request['personal'].update(use_pantry=True,pantry_revision=state['revision'])
    reference=str(uuid.uuid4());headers={'Prefer':'respond-async','X-Request-ID':reference}
    start=actor.post('/api/plans',json=request,headers=headers);start.raise_for_status()
    same=actor.post('/api/plans',json=request,headers=headers);same.raise_for_status()
    assert same.json().get('status_url')==start.json().get('status_url')
    saved=resolve(actor,start);plan_id=saved['plan_id']
    dump('pantry-generated.json',saved)
    allocations=[r for r in saved['plan']['personal']['allocations'] if r.get('item_id')==pantry_id or r.get('pantry_id')==pantry_id]
    if not allocations:allocations=saved['plan']['personal']['allocations']
    assert abs(sum(r['quantity'] for r in allocations)-100)<1e-6,allocations
    assert len({r['source'] for r in allocations})>1,allocations
    assert other.get('/api/plans/'+plan_id).status_code==404
    if start.json().get('status_url'):assert other.get(start.json()['status_url']).status_code==404
    assert not other.get('/api/personal/state').json()['items']
    # Replace real breakfast and snack by exact suggestions and read revisions.
    revisions=[saved]
    for category in ['breakfast','snack']:
        slot=next(s for s in saved['plan']['personal']['slots'] if s['meal_type']==category)
        options=json.loads(args.pack.read_text(encoding='utf8'))['recipes']
        selected=next(r['design'] for r in options if category in r['design']['meal_types']
            and r['design']['base_id']!=slot['recipe']['design']['base_id'])
        selected_id=f"{selected['base_id']}:{selected['version']}:{selected['variant_id']}"
        state=actor.get('/api/personal/state').json()
        response=actor.post(f'/api/personal/plans/{plan_id}/change',json={'revision':saved['revision'],
            'pantry_revision':state['revision'],'action':'replace','slot_id':slot['id'],'recipe_id':selected_id},
            headers={'Prefer':'respond-async','X-Request-ID':str(uuid.uuid4())})
        body=resolve(actor,response);saved=body.get('saved',body);revisions.append(saved)
        assert next(s for s in saved['plan']['personal']['slots'] if s['id']==slot['id'])['recipe']['design']['base_id']!=slot['recipe']['design']['base_id']
    for revision in revisions:
        read=actor.get(f'/api/plans/{plan_id}',params={'revision':revision['revision']});read.raise_for_status()
        assert fingerprint(read.json())==fingerprint(revision)
    dump('explicit-replacements.json',{'revisions':revisions,'original_request_id':reference,
        'status_url':start.json().get('status_url'),'same_job_double_start':True,
        'allocated_grams':sum(r['quantity'] for r in allocations),'allocation_slots':[r['source'] for r in allocations],
        'separate_owner_denied':True,'cookies_recorded':False})
