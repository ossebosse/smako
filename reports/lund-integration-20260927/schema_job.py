import sqlite3,json
from job import configure,save
configure()
with sqlite3.connect('file:/work/grocery.sqlite?mode=ro',uri=True) as db:
 rows=[]
 for identity,chain,scope,version,raw in db.execute("select id,chain,scope_key,parser_version,metrics from catalog_snapshots where created_at>='2026-09-27' and state='rejected'"):
  data=json.loads(raw);rows.append({'snapshot':identity,'chain':chain,'scope':scope,'parser_version':version,'schema_diff':data.get('schema_diff'),'validation':data.get('validation'),'health':data.get('health')})
 save('schema-review',rows);print(json.dumps(rows,ensure_ascii=False,indent=2))
