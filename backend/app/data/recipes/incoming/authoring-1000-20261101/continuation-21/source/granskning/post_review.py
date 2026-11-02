import json,collections,re,unicodedata
from pathlib import Path
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
W=Path('/mnt/data/smako_work_022');load=lambda p:json.loads((W/p).read_text());R=load('authored_working.json');V=load('reference_variants.json')+load('previous_variants.json')
def ing(r):return r.get('ingredients',[i for c in r.get('components',[])for i in c['ingredients']])
def txt(r):return ' '.join(r.get('instructions',[s['text']for s in r.get('steps',[])]))
def norm(s):return ''.join(c for c in unicodedata.normalize('NFKD',s.lower())if not unicodedata.combining(c))
def words(r):return norm(r['name']+' '+r.get('family','')+' '+txt(r))
def key(r):return r['base_id']+':'+r['version']+':'+r['variant_id']
vec=TfidfVectorizer(analyzer='word',ngram_range=(1,2),max_features=180000,sublinear_tf=True)
M=vec.fit_transform([words(r)for r in V+R]);sim=(M[len(V):]@M[:len(V)].T).toarray()
namevec=TfidfVectorizer(analyzer='char_wb',ngram_range=(3,5),sublinear_tf=True,max_features=150000)
N=namevec.fit_transform([norm(r['name']+' '+r['base_id'])for r in V+R]);nsim=(N[len(V):]@N[:len(V)].T).toarray()
sets=[{i['name']+'|'+i['form']for i in ing(r)if i['name']not in ['salt','svartpeppar','peppar','vatten']}for r in V+R]
jac=np.array([[len(a&b)/len(a|b) for b in sets[:len(V)]]for a in sets[len(V):]])
score=.4*sim+.3*nsim+.3*jac
out=[]
for i,r in enumerate(R):
 hits=[];seen=set()
 for j in np.argsort(-score[i]):
  old=V[j]
  if old['base_id']in seen:continue
  seen.add(old['base_id']);hits.append(dict(base_id=old['base_id'],variant_id=old['variant_id'],name=old['name'],origin='original'if j<2462 else'previous_delivery',score=round(float(score[i,j]),4),ingredient_jaccard=round(float(jac[i,j]),4),instruction_similarity=round(float(sim[i,j]),4)))
  if len(hits)==3:break
 out.append(dict(base_id=r['base_id'],variant_id=r['variant_id'],nearest_library=hits))
newtext=(M[len(V):]@M[len(V):].T).toarray();newname=(N[len(V):]@N[len(V):].T).toarray()
pairs=[]
for i,r in enumerate(R):
 for j in range(i+1,len(R)):
  d=R[j]
  if r['base_id']==d['base_id']:continue
  a,b=sets[len(V)+i],sets[len(V)+j];js=len(a&b)/len(a|b)
  pairs.append(dict(left=key(r),right=key(d),score=round(float(.4*newtext[i,j]+.3*newname[i,j]+.3*js),4),ingredient_jaccard=round(js,4),instruction_similarity=round(float(newtext[i,j]),4)))
pairs.sort(key=lambda p:-p['score'])
report=dict(stage='after_full_recipe_authoring',reference_variants=2462,previous_variant_occurrences=len(V)-2462,new_variants=len(R),variant_to_library_pair_count=len(R)*len(V),new_cross_family_variant_pair_count=len(pairs),method='All actual variant texts (word TF-IDF 40%), names/IDs (character TF-IDF 30%) and canonical name|form Jaccard (30%). Shared status notes are excluded. Original and previous archive occurrences are retained for collision visibility. Scores are candidates for review, not novelty probabilities.',rows=out,new_cross_family_pairs=pairs,editorial_completion='pending')
(W/'post_review_machine.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
for b in dict.fromkeys(r['base_id']for r in R):
 rr=[x for x in out if x['base_id']==b];top=sorted([h for x in rr for h in x['nearest_library']],key=lambda h:-h['score'])[:2]
 print(b,'=>',[(h['base_id'],h['score'])for h in top])
print('Highest new pairs',pairs[:6])
