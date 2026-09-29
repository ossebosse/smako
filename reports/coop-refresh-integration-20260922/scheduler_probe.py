"""Private scheduler bootstrap only: no cron daemon, host schedule or source calls."""
import json
import shlex
import subprocess
from pathlib import Path

program = '''import os,json,subprocess,sys
os.environ.update(DEMAND_REFRESH_ENABLED="true",COOP_MUNICIPAL_OFFERS_ENABLED="true",COOP_MUNICIPALITY_CODE="1281",COOP_XTRA_OFFERS_ENABLED="false",COOP_ALLOW_FULL_CRAWL="true",COOP_ONLINE_CONTEXT_IDS="730400")
from deploy.scripts import start_cron
exec_calls=[]
start_cron.os.execv=lambda *args:exec_calls.append(args)
start_cron.main()
from pathlib import Path
cron=Path("/etc/cron.d/grocery-beta").read_text()
assert "run_daily_refresh.py" in cron and exec_calls == [("/usr/sbin/cron",["cron","-f"])]
check="import sys,os,importlib.metadata,json; from grocery_data.app.services.coop_offer_job import source_plan; print(json.dumps({'python':sys.executable,'uid':os.getuid(),'playwright':importlib.metadata.version('playwright'),'municipality':os.getenv('COOP_MUNICIPALITY_CODE')}))"
r=json.loads(subprocess.check_output(["runuser","-u","app","--","python","-c",check]))
assert r["python"].startswith("/opt/ica-venv/") and r["uid"]==10001 and r["municipality"]=="1281"
print(json.dumps({"status":"PASS","runtime":r,"jobs":start_cron.scheduled_jobs(),"private_generated_cron":True,"daemon_started":False,"host_schedule_changed":False}))
'''
cmd=['docker','run','--rm','--network','none','--read-only','--user','root','--cpus','1','--memory','256m',
     '--tmpfs','/run:rw,size=16m,mode=0755','--tmpfs','/etc/cron.d:rw,size=1m,mode=0755',
     '--tmpfs','/tmp:rw,size=16m,mode=1777','--entrypoint','/opt/ica-venv/bin/python',
     'smako-coop-candidate:refresh-integration-20260922','-c',program]
code='import subprocess,sys; r=subprocess.run('+repr(cmd)+',capture_output=True);sys.stdout.buffer.write(r.stdout);sys.stderr.buffer.write(r.stderr);raise SystemExit(r.returncode)'
r=subprocess.run(['ssh','smako','python3 -c '+shlex.quote(code)],capture_output=True)
if r.returncode:print(r.stderr.decode(errors='replace')[-2000:]);raise SystemExit(r.returncode)
d=json.loads(r.stdout.decode().splitlines()[-1]);Path(__file__).with_name('scheduler-bootstrap.json').write_text(json.dumps(d,indent=2));print(json.dumps(d))
