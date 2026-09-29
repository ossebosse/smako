"""Separate current estimated meal test using a normal recipe and a permitted store."""
import time

def run_representative(client,prepared,physical):
 cheese=[p for p in prepared.universe.products if p.chain=='lidl' and p.name=='Hushållsost' and p.purchase_terms and p.purchase_terms.usage=='estimated' and p.store_id in physical]
 if not cheese:return [{'case':'representative-current-cheese','status':'not_available','reason':'No current qualified Hushållsost approximate package in served physical scope. No historical price substituted.'}]
 from app.models.recipe import Recipe
 from app.services.recipe_preparation import adapt
 recipe=adapt(Recipe.model_validate({'name':'Varm ostsmörgås','servings':1,'ingredients':[{'name':'bröd','quantity':100,'unit':'g'},{'name':'ost','quantity':100,'unit':'g'}],'instructions':['Värm smörgåsen.']}),'cheese_toast',origin='explicit_adaptation').model_dump(mode='json')
 value={'postal_code':'22350','recipes':0,'max_stores':1,'allowed_store_ids':[cheese[0].store_id],'purchase_planning_mode':'estimated','memberships':{'willys':True,'lidl':True},'personal':{'allow_nutrition_estimates':True,'meals':[{'meal_type':'breakfast','count':1,'servings':1,'limits':{'min_protein_g':30}}],'slots':[{'id':'breakfast-1','day':1,'meal_type':'breakfast','recipe':recipe}],'pantry_revision':client.get('/api/personal/state').json()['revision']}}
 began=time.monotonic();response=client.post('/api/plans',json=value)
 row={'case':'representative-current-cheese','scope':'separate one-store warm cheese sandwich; no product lock, extras or patched candidates','seconds':time.monotonic()-began,'http_status':response.status_code,'request':value,'response':response.json()}
 if response.status_code==201:
  row['plan_id']=response.json().get('id',response.json().get('plan_id'));row['roundtrip_identical']=client.get('/api/plans/'+row['plan_id']).json()==response.json()
 return [row]

def run_multibuy(client,prepared,physical):
 """Normal eight-portion breakfast, permitted current Coop store; no product ID lock."""
 from app.models.recipe import Recipe
 from app.services.recipe_preparation import adapt
 stores=sorted({p.store_id for p in prepared.universe.products if p.chain=='coop' and p.name=='Hönökaka' and p.store_id in physical and any(o.required_packages>1 for o in p.offers)})
 if not stores:return [{'case':'representative-current-multibuy','status':'not_available','reason':'No qualified current physical bread multibuy source'}]
 recipe=adapt(Recipe.model_validate({'name':'Varma ostsmörgåsar till åtta portioner','servings':8,'ingredients':[{'name':'bröd','quantity':800,'unit':'g'},{'name':'ost','quantity':800,'unit':'g'}],'instructions':['Värm smörgåsarna.']}),'cheese_toast',origin='explicit_adaptation').model_dump(mode='json')
 value={'postal_code':'22350','recipes':0,'max_stores':1,'allowed_store_ids':[stores[0]],'purchase_planning_mode':'estimated','memberships':{'willys':True,'lidl':True},'personal':{'allow_nutrition_estimates':True,'meals':[{'meal_type':'breakfast','count':1,'servings':8,'limits':{'min_protein_g':30}}],'slots':[{'id':'breakfast-1','day':1,'meal_type':'breakfast','recipe':recipe}],'pantry_revision':client.get('/api/personal/state').json()['revision']}}
 began=time.monotonic();response=client.post('/api/plans',json=value)
 row={'case':'representative-current-multibuy','scope':'Separate eight-portion warm breakfast, unchanged 100 g bread and 100 g cheese per serving, ordinary allowed store; no product locks/extras/candidate patches. Not the 15/20 profile.','seconds':time.monotonic()-began,'http_status':response.status_code,'request':value,'response':response.json()}
 if response.status_code==201:
  row['plan_id']=response.json()['plan_id'];row['roundtrip_identical']=client.get('/api/plans/'+row['plan_id']).json()==response.json()
 return [row]
