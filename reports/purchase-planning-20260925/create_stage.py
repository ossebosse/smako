import subprocess,shlex
stage='/var/tmp/smako-purchase-planning-20260925'
code=f'''from pathlib import Path
import subprocess
p=Path({stage!r});p.mkdir(exist_ok=False);(p/'.owner').write_text('purchase-planning-20260925')
old=Path('/var/tmp/smako-offer-expansion-20260924');assert (old/'.owner').read_text()=='offer-expansion-20260924'
(p/'data').mkdir()
cmd=['docker','run','--rm','--network','none','--mount','type=bind,source='+str(old/'data')+',target=/old,readonly','--mount','type=bind,source='+str(p/'data')+',target=/new','alpine:3.20','sh','-c','cp -a /old/base /new/base && cp -a /old/raw /new/raw && chown -R 10001:10001 /new']
subprocess.run(cmd,check=True)
print('new private stage created; original retained read-only')'''
r=subprocess.run(['ssh','-oBatchMode=yes','smako','python3 -c '+shlex.quote(code)],capture_output=True);print(r.stdout.decode());print(r.stderr.decode()[-1200:]);raise SystemExit(r.returncode)
