"""Separate 15-meal/20-portion API regression; never public-button acceptance."""
import argparse
import hashlib
import json
import ssl
import time
from pathlib import Path

import httpx

parser=argparse.ArgumentParser()
parser.add_argument('--base',default='https://beta.smako.nu')
parser.add_argument('--inputs',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--ca-file',type=Path,help='Trust the isolated candidate TLS CA without disabling verification')
parser.add_argument('--origin',help='Configured application origin for an isolated transport alias')
args=parser.parse_args()
inputs=json.loads(args.inputs.read_bytes())['cases']
assert len(inputs)==4
report={'path':'separate PersonalPlanner API regression','cases':[]}
verify = ssl.create_default_context(cafile=str(args.ca_file)) if args.ca_file else True
with httpx.Client(base_url=args.base,timeout=540,headers={'Origin':args.origin or args.base},verify=verify) as client:
    for case in inputs:
        request=case['request']
        personal=request['personal']
        assert sum(m['count'] for m in personal['meals'])==15
        assert sum(m['count']*m['servings'] for m in personal['meals'])==20
        assert request['max_stores']==2
        state=client.get('/api/personal/state')
        state.raise_for_status()
        personal['pantry_revision']=state.json()['revision']
        started=time.monotonic()
        response=client.post('/api/plans',json=request)
        saved=response.json()
        record={'case':case['case'],'status':response.status_code,'seconds':round(time.monotonic()-started,3),
                'request_id':response.headers.get('x-request-id'),'request':request}
        if response.status_code==201:
            plan=saved['plan']
            audit=plan['personal']['checks']['checkout_audit']
            record.update(total=plan['optimized_basket']['total'],stores=plan['optimized_basket']['store_count'],
                          checks=plan['personal']['checks'],build_id=plan['build_id'],
                          plan_sha256=hashlib.sha256(json.dumps(plan,sort_keys=True).encode()).hexdigest())
            loaded=client.get('/api/plans/'+saved['plan_id'])
            record['identical_reload']=loaded.status_code==200 and loaded.json()['plan']==plan
            assert audit['passed'] and audit['totals_reconciled'] and not audit['deficits']
            assert record['stores']<=2 and record['identical_reload']
            assert plan['personal']['checks']['purchase_planning_mode']==request['purchase_planning_mode']
            limits={m['meal_type']:m['limits'].get('min_protein_g') for m in personal['meals']}
            for row in plan['personal']['checks']['nutrition']:
                minimum=limits[row['slot_id'].rsplit('-',1)[0]]
                assert minimum is None or row['values']['protein_g']>=minimum
        else:
            record['body']=saved
        report['cases'].append(record)
        args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({k:record[k] for k in ['case','status','seconds','request_id']}),flush=True)
        assert response.status_code==201
