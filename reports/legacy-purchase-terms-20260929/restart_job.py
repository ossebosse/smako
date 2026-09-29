"""Actual process restart after second publication, with the same terms and saved quote."""
import json,os,subprocess,sys,time
from pathlib import Path
import httpx
from job import configure,save
configure();os.environ['PLAN_PREWARM_ENABLED']='false'
P=Path('/work')
prior=json.loads((P/'purchases-results.json').read_bytes())
def start():
    process=subprocess.Popen([sys.executable,'/evaluation/http_job.py','--serve'],stdout=(P/'restart-app.log').open('a'),stderr=subprocess.STDOUT)
    for _ in range(1800):
        if process.poll() is not None:raise RuntimeError('restart failed')
        try:
            if httpx.get('http://127.0.0.1:8000/ready',timeout=1).status_code==200:return process
        except httpx.TransportError:pass
        time.sleep(.1)
    raise RuntimeError('restart timeout')
def stop(server):server.terminate();server.wait(30)
server=start();report={'searches':[]}
try:
 with httpx.Client(base_url='http://127.0.0.1:8000',timeout=90) as client:
    for row in prior['cases']:
        if row['http_status']!=201:continue
        extra=row['request']['personal']['extras'][0]
        programs={'ica':'ICA_STAMMIS','coop':'COOP_MEMBER','hemkop':'HEMKOP_MEMBER'}
        response=client.post('/api/product-search',json={'query':extra['query'],'product_key':extra['product_key'],
            'memberships':[programs[c] for c,v in row['request']['memberships'].items() if v]})
        assert response.status_code==200 and response.json()['live_provider_calls']==0
        assert response.json()['results']==row['search']['results'],row['case']
        report['searches'].append({'case':row['case'],'identical_terms_price_and_source':True,'live_provider_calls':0})
    request=json.loads(json.dumps(prior['cases'][0]['request']))
    request['personal']['pantry_revision']=client.get('/api/personal/state').json()['revision']
    response=client.post('/api/plans',json=request)
    assert response.status_code==201,response.text[:300]
    saved=response.json();assert saved['plan']['optimized_basket']['total']==166.8
    stop(server);server=start()
    report['saved_quote_identical_after_restart']=client.get('/api/plans/'+saved['plan_id']).json()==saved
    assert report['saved_quote_identical_after_restart']
    report['build_id']=saved['build_id'];report['price_universe_id']=saved['price_universe_id']
    report['quote_total']=166.8
    save('restart-final-result',report)
finally:stop(server)
print('seven searches and a saved estimated purchase identical after second rebuild and actual restart')
