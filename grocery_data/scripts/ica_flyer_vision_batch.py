"""Serial, resumable public-PDF interpretation through the existing worker protocol.

No collection or observation refresh. No database mutation or activation. The
output is input to the existing review/import path after the real page pilot.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from grocery_data.app.services.durable_files import atomic_write_bytes
from grocery_data.app.services.ica_flyer_pipeline import visual_timeout_seconds
from grocery_data.app.services.ica_flyer_review import review_key
from grocery_data.app.services.manual_refresh_operations import (
    RefreshRunLock,
    production_refresh_lock_path,
)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--coverage',type=Path,required=True)
    p.add_argument('--source-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--previous-extraction',type=Path)
    p.add_argument('--inventory-only',action='store_true',help='Keep every remaining page visible without model calls')
    p.add_argument('--page',action='append',default=[],help='Exact issue:page, repeat for bounded pilot')
    p.add_argument('--operation-database',type=Path,required=True)
    p.add_argument('--price-universe-root',type=Path,required=True)
    p.add_argument('--visual-command-json',type=Path,help='JSON argv file; otherwise ICA_FLYER_VISUAL_COMMAND_JSON or existing OpenAI worker')
    p.add_argument('--worker-revision',default='existing-worker-v1',help='Separate checkpoints after changing model, weights, prompt or rendering')
    args=p.parse_args()
    command = json.loads(args.visual_command_json.read_bytes()) if args.visual_command_json else json.loads(
        os.getenv('ICA_FLYER_VISUAL_COMMAND_JSON', 'null'))
    if command is None:command=[sys.executable,'-m','grocery_data.scripts.ica_flyer_openai']
    if not isinstance(command,list) or not command or not all(isinstance(x,str) and x for x in command):
        p.error('visual command must be a nonempty JSON argv array')
    timeout=visual_timeout_seconds()
    coverage=json.loads(args.coverage.read_bytes())
    previous=json.loads(args.previous_extraction.read_bytes()) if args.previous_extraction else {'pages':[]}
    retained={(r['evidence'].get('pdf_sha256'),r['evidence']['page']) for r in previous['pages'] if r.get('complete')}
    jobs={};associations=[]
    for store in coverage['stores']:
        for flyer in store.get('flyers',[]):
            for edition in flyer.get('editions',[]):
                expected=max(edition['fetched_pages'],edition.get('source_pages',0)-len(edition.get('supplemental_pages',[])))
                for page in range(1,expected+1):
                    e={'issue_id':edition['id'],'pdf_sha256':edition['sha256'],'page':page,
                       'official_store_ids':[store['ica_account_id']],'observed_at':edition['fetched_at'],
                       'source_url':edition['pdf_url']}
                    selected=f"{edition['id']}:{page}" in args.page if args.page else (edition['sha256'],page) not in retained
                    association={'account':store['ica_account_id'],'evidence':e,'selected':selected,
                                 'status':'pending' if selected else 'retained_prior_status',
                                 'previous_complete':(edition['sha256'],page) in retained}
                    associations.append(association)
                    if selected:
                        context={'title':edition.get('title'),'definition_url':edition.get('definition_url')}
                        identity=review_key({'pdf_sha256':edition['sha256'],'page':page,'source_context':context})
                        jobs.setdefault(identity,{'document':str((args.source_root/edition['file']).resolve()),
                            'protocol':'smako-public-flyer-page-v1','evidence':e,
                            'source_context':context})
                        association['job']=identity
                for supplement in edition.get('supplemental_pages',[]):
                    associations.append({'account':store['ica_account_id'],'selected':False,
                        'status':'needs_review_supplemental_layout','evidence':{
                            'issue_id':edition['id'],'pdf_sha256':edition['sha256'],
                            'page':'reader-slot-'+str(supplement['reader_slot']),**supplement}})
    args.output.mkdir(parents=True,exist_ok=True)
    binding=review_key({'coverage':coverage,'selection':args.page,'retained':sorted(retained,key=str),
                       'worker_command':command,'worker_revision':args.worker_revision})
    checkpoint=args.output/'batch.json'
    if checkpoint.exists() and json.loads(checkpoint.read_bytes())['binding']!=binding:
        p.error('existing output belongs to different source versions or selection')
    result={'binding':binding,'protocol':'smako-public-flyer-page-v1','concurrency':1,
            'worker_command':command,'worker_revision':args.worker_revision,'worker_timeout_seconds':timeout,
            'price_observations_refreshed':False,'production_activation':False,'pages':associations,
            'jobs':{},'source_inventory':coverage['inventory'],
            'stores':[{'account':s['ica_account_id'],'area_membership':s['area_membership'],
                       'collection_status':s.get('collection_status'),'flyer_discovery_error':s.get('flyer_discovery_error')}
                      for s in coverage['stores']]}
    def save():atomic_write_bytes(checkpoint,json.dumps(result,ensure_ascii=False,indent=2).encode())
    if args.inventory_only:
        for row in associations:
            if row['selected']:row['status']='blocked_pending_verified_pilot_and_access'
        result['selected_unique_pages']=len(jobs)
        save();print(json.dumps({'unique_selected_pages':len(jobs),'associations':len(associations),'paid_requests':0}));return
    with RefreshRunLock(production_refresh_lock_path(args.operation_database,args.price_universe_root)):
        for identity,request in jobs.items():
            target=args.output/(identity+'.json')
            started=time.monotonic()
            if target.exists():
                outcome=json.loads(target.read_bytes())
                if outcome.get('request_sha256')!=review_key(request):raise ValueError('changed checkpoint evidence')
            else:
                env={**os.environ,'ICA_FLYER_SOURCE_ROOT':str(args.source_root.resolve())}
                try:
                    run=subprocess.run(command,
                        input=json.dumps(request),capture_output=True,text=True,encoding='utf8',env=env,timeout=timeout,check=False)
                    code=run.returncode
                    try:payload=json.loads(run.stdout if code==0 else run.stderr)
                    except ValueError:payload={'status':'blocked','reason':'worker_failed_without_safe_json'}
                except subprocess.TimeoutExpired:
                    code=124;payload={'status':'blocked','reason':'worker_timeout_review_backend_usage_before_retry'}
                outcome={'request_sha256':review_key(request),'result':payload,
                         'elapsed_seconds':round(time.monotonic()-started,3),'exit_code':code}
                # Failed access is resumable once configured; successful output immutable.
                if code==0:atomic_write_bytes(target,json.dumps(outcome,ensure_ascii=False,indent=2).encode())
            result['jobs'][identity]=outcome
            for row in associations:
                if row.get('job')==identity:
                    row['status']='extracted' if outcome['exit_code']==0 else 'blocked'
                    row['complete']=outcome['result'].get('complete',False)
                    row['reason']=outcome['result'].get('reason')
                    # Rebind evidence to this exact official association; never
                    # infer store eligibility from identical pixels alone.
                    row['result_evidence_sha256']=review_key(row['evidence'])
            save()
    print(json.dumps({'unique_selected_pages':len(jobs),'associations':len(associations),
                      'successful_jobs':sum(x['exit_code']==0 for x in result['jobs'].values()),
                      'production_activation':False}))


if __name__=='__main__':main()
