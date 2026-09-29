import os,json
from pathlib import Path
os.environ.update(GROCERY_DATABASE_URL='sqlite:////work/base/refreshed.sqlite',GROCERY_RAW_SNAPSHOT_ROOT='/work/raw')
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
p=PreparedPriceUniverseArtifact.model_validate_json(Path('/work/universe.json').read_bytes()).restore()
selected=[x for x in p.universe.products if x.name in {'Tuc Ost','Ärtor Gula Eko','Poésie Torsk','Burek Nötfärs Fryst'}]
Path('/work/profile/rebuild-product-review.json').write_text(json.dumps([x.model_dump(mode='json') for x in selected],ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps([{'id':x.product_id,'store':x.store_id,'name':x.name,'category':x.category,'canonical':x.canonical_food,'role':x.product_role,'form':x.product_form} for x in selected],ensure_ascii=False))
