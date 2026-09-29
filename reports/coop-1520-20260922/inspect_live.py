"""Read-only live health/version plus private test resource sample."""
import json, subprocess, shlex
from pathlib import Path
code = """import subprocess,json,datetime
r={'observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
r['images']={name:subprocess.check_output(['docker','inspect','--format','{{.Config.Image}}',name],text=True).strip() for name in ['smako-app-1','smako-scheduler-1']}
program="import urllib.request,json; print(json.dumps({p: {'status': urllib.request.urlopen('http://127.0.0.1:8000/'+p).status, 'body':json.load(urllib.request.urlopen('http://127.0.0.1:8000/'+p))} for p in ['health','ready']}))"
r['http']=json.loads(subprocess.check_output(['docker','exec','smako-app-1','python','-c',program],text=True))
r['resources']=subprocess.check_output(['docker','stats','--no-stream','--format','{{.Name}} {{.CPUPerc}} {{.MemUsage}}','smako-coop-1520-test','smako-app-1'],text=True)
print(json.dumps(r))
"""
r=subprocess.run(['ssh','smako','python3 -c '+shlex.quote(code)],capture_output=True,check=True)
d=json.loads(r.stdout);Path(__file__).with_name('live-health.json').write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'images':d['images'],'http':{k:v['status'] for k,v in d['http'].items()},'resources':d['resources']}))
