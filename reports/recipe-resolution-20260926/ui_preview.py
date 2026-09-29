"""Read-only UI presentation replay of actual isolated HTTP responses; no planning substitute."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import json,mimetypes
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parents[2]
R=Path(__file__).parent
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  report=json.loads((R/'profile/http-new-recipes-after-integration.json').read_bytes())
  report['cases']+=json.loads((R/'profile/http-cream-after-integration.json').read_bytes())['cases']
  path=urlsplit(self.path).path
  if path=='/api/personal/state':body=json.dumps(report['ui_state']).encode();kind='application/json'
  elif path=='/api/account/status':body=b'{"status":"GUEST"}';kind='application/json'
  elif path.startswith('/api/plans/'):
   plan=next(c['response'] for c in report['cases'] if c['http_status']==201 and c['response']['plan_id']==path.rsplit('/',1)[-1])
   body=json.dumps(plan).encode();kind='application/json'
  else:
   if path=='/personal':target=ROOT/'backend/app/static/personal.html'
   elif path.startswith('/static/'):target=ROOT/'backend/app/static'/path.removeprefix('/static/')
   elif path=='/scanner-assets/physical-barcode-scanner.js':target=ROOT/'grocery_data/app/static/physical-barcode-scanner.js'
   else:self.send_error(404);return
   if not target.resolve().is_relative_to(ROOT.resolve()) or not target.is_file():self.send_error(404);return
   body=target.read_bytes();kind=mimetypes.guess_type(target)[0] or 'application/octet-stream'
  self.send_response(200);self.send_header('Content-Type',kind+'; charset=utf-8');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(body)
 def do_POST(self):self.send_error(405,'Read-only verification replay')
 def log_message(self,*args):pass
print('Read-only UI replay on http://127.0.0.1:8794',flush=True)
ThreadingHTTPServer(('127.0.0.1',8794),Handler).serve_forever()
