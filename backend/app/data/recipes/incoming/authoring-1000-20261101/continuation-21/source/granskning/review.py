import json,re,unicodedata,collections,hashlib
from pathlib import Path
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
W=Path('/mnt/data/smako_work_022')
load=lambda p:json.loads((W/p).read_text())
write=lambda p,o:(W/p).write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n')
C=load('candidate_seed.json'); B=load('reference_bases.json')+load('previous_bases.json'); V=load('reference_variants.json')+load('previous_variants.json')
alias={'feta':'fetaost','socker':'strösocker','tortillabröd':'tortillas','sesamfrö':'sesamfrön','vaniljsocker':'vaniljpulver'}
for c in C:c['planned_ingredients']=[alias.get(n,n) for n in c['planned_ingredients']]
def norm(t):return ''.join(x for x in unicodedata.normalize('NFKD',t.lower()) if not unicodedata.combining(x))
vs=collections.defaultdict(list)
for v in V:vs[v['base_id']].append(v)
def ingredients(v):return v.get('ingredients',[i for co in v.get('components',[]) for i in co['ingredients']])
def text(v):return ' '.join(v.get('instructions',[s['text'] for s in v.get('steps',[])]))
Btxt=[]; Bname=[]; Bis=[]
for b in B:
 rs=vs[b['base_id']]; ns=b['names'];bs=' '.join(ns)+' '+' '.join(b.get('families',[]))+' '+b['base_id']
 Bname.append(norm(bs));Btxt.append(norm(bs+' '+' '.join(text(r) for r in rs)))
 Bis.append(set(i['name'] for r in rs for i in ingredients(r)) - {'salt','svartpeppar','vatten'})
Cname=[norm(c['name']+' '+c['traditional_name']+' '+c['base_id']) for c in C]
Ctxt=[norm(c['name']+' '+c['identity']+' '+' '.join(c['planned_ingredients'])) for c in C]
vector=TfidfVectorizer(analyzer='char_wb',ngram_range=(3,5),sublinear_tf=True,min_df=1,max_features=180000)
M=vector.fit_transform(Bname+Cname)
name=(M[len(B):]@M[:len(B)].T).toarray()
v2=TfidfVectorizer(analyzer='word',ngram_range=(1,2),sublinear_tf=True,max_features=180000)
M2=v2.fit_transform(Btxt+Ctxt);txt=(M2[len(B):]@M2[:len(B)].T).toarray()
ing=np.zeros(name.shape)
for i,c in enumerate(C):
 a=set(c['planned_ingredients'])
 for j,s in enumerate(Bis):ing[i,j]=len(a&s)/len(a|s) if a|s else 0
score=.40*name+.35*ing+.25*txt
newname=(M[len(B):]@M[len(B):].T).toarray();newtxt=(M2[len(B):]@M2[len(B):].T).toarray()
newscore=.45*newname+.25*newtxt
for i,c in enumerate(C):
 a=set(c['planned_ingredients'])
 for j,d in enumerate(C):
  b=set(d['planned_ingredients']);newscore[i,j]+=.30*len(a&b)/len(a|b)
 np.fill_diagonal(newscore,-1)

def hit(i,j):
 b=B[j];return dict(base_id=b['base_id'],names=b['names'],origin='original' if j<934 else 'previous_delivery',score=round(float(score[i,j]),4),name_similarity=round(float(name[i,j]),4),ingredient_jaccard=round(float(ing[i,j]),4),full_instruction_similarity=round(float(txt[i,j]),4))
rows=[]
for i,c in enumerate(C):
 top=np.argsort(-score[i])[:7];nidx=np.argsort(-newscore[i])[:3]
 rows.append(dict(candidate=c,nearest_library=[hit(i,j) for j in top],nearest_new=[{'base_id':C[j]['base_id'],'name':C[j]['name'],'score':round(float(newscore[i,j]),4)}for j in nidx]))
write('pre_review_machine.json',dict(stage='before_full_recipe_authoring',reference_bases=934,previous_bases=len(B)-934,reference_variants=2462,previous_variant_occurrences=len(V)-2462,library_pair_count=len(B)*len(C),new_unique_pair_count=len(C)*(len(C)-1)//2,method='Full character name TF-IDF (40%), canonical ingredient Jaccard (35%), word TF-IDF across all variant instruction texts per base (25%). All cuisines and unlabelled included. Ranking supports, does not replace, culinary judgement.',rows=rows))
with (W/'pre_review_hits.txt').open('w') as f:
 for row in rows:
  f.write('\n'+row['candidate']['name']+'\n'+row['candidate']['identity']+'\n')
  for h in row['nearest_library']:f.write(f" {h['score']:.3f} {h['base_id']} :: {' / '.join(h['names'])[:150]}\n")
  f.write(' NEW '+str(row['nearest_new'][0])+'\n')
print((W/'pre_review_hits.txt').read_text())
