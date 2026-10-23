import argparse
import hashlib
import json
from pathlib import Path

parser=argparse.ArgumentParser(description="Validate pinned review reports without network access.")
parser.add_argument('--evidence',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
root=args.evidence
cases=('standard','protein40','all-macros','vegan','distribution','organic-share','breakfast-snack-weight')
rows=[]
for city in ('lund','malmo'):
    for case in cases:
        old_path=root/'server-matrix'/f'{city}-main-{case}.json'
        new_path=root/'final-grid'/city/f'L262-main-{case}.json'
        row={'city':city,'case':case,'complete':new_path.exists()}
        if row['complete']:
            old=json.loads(old_path.read_bytes());new=json.loads(new_path.read_bytes())
            assert old['inputs']==new['inputs'] and old['search_limits']==new['search_limits']
            keys=('outcome','paid','semantic_sha256','code','stage')
            same=all(all(a.get(k)==new['records'][0].get(k) for k in keys) for a in old['records'])
            row.update(same_results=same,inputs=new['inputs'],method_signature=new['method_signature'],
                       old_source_commit='2efb62f',new_source_commit='c9390dd' if city=='lund' else 'b139cd4',
                       old_report_sha256=hashlib.sha256(old_path.read_bytes()).hexdigest(),
                       new_report_sha256=hashlib.sha256(new_path.read_bytes()).hexdigest(),
                       result={k:new['records'][0].get(k) for k in keys})
            assert same,(city,case)
        rows.append(row)
target=args.output
target.write_text(json.dumps({'schema':'default-result-regression-v1','complete':all(r['complete'] for r in rows),'rows':rows},indent=2)+'\n',encoding='utf8')
print(json.dumps({'completed':sum(r['complete'] for r in rows),'total':len(rows),'all_completed_results_identical':True}))
