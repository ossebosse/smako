"""Technical library load: synthetic metadata/amount variations, never food evidence.

Run inside a disposable image layer, with the ordinary benchmark inputs.
No synthetic content is imported into the real pilot or production registry.
"""
import runpy
import sys
import time
from pathlib import Path

from app.services.meal_library_content import encoded, import_pack, validate_pack
from app.services.meal_prepared_artifacts import prepare_content
from app.services.recipe_library import current_recipes

factor=int(sys.argv[1]);case=sys.argv[2]
assert factor in {1,2,5}
original=current_recipes();rows=[];started=time.perf_counter()
for n in range(len(original)*(factor-1)):
    source=original[n % len(original)]
    row=source.model_dump(mode='json');d=row['design']
    d.update(base_id=f'synthetic-load-{factor}-{n}',version='1.0.0',variant_id='base',
             active_minutes=d.get('active_minutes') or min(d['estimated_minutes'],20),
             total_minutes=d.get('total_minutes') or d['estimated_minutes'])
    d.pop('content_source',None)
    row['name']=f'SYNTHETISK BELASTNING {n}: '+row['name']
    # Different operands and identities exercise relevant candidates, not just
    # thousands of exact copies. These are not reviewed new culinary dishes.
    ratio=0.9+(n % 9)*0.025
    for ingredient in row['ingredients']:
        for field in ['quantity','quantity_min','quantity_max','quantity_step']:
            if ingredient.get(field) is not None:ingredient[field]*=ratio
    for component in d['components']:
        for amount in component['amounts']:amount['quantity']*=ratio
    d['provenance']['notes']='SYNTHETIC technical load only. Not recipe count, cooking or purchase evidence.'
    rows.append(row)
if rows:
    path=Path('/tmp/synthetic-pack.json')
    path.write_bytes(encoded({'schema_version':'smako-meal-pack-v1','pack_id':f'synthetic-load-{factor}','recipes':rows}))
    checked=validate_pack(path)
    Path(f'/results/scale-{factor}-{case}-validation.json').write_bytes(encoded({
        'rejections':checked['rejections'],'accepted':len(checked['recipes'])}))
    assert not checked['rejections'], 'Retain all synthetic validation errors'
    import_pack(path)
content=prepare_content(current_recipes())
Path(f'/results/scale-{factor}-{case}-preparation.json').write_bytes(encoded({
    'synthetic':True,'original_recipes':len(original),'library_recipes':len(current_recipes()),
    'added_synthetic_recipes':len(rows),'seconds':time.perf_counter()-started,'preparation':content}))
sys.argv=['benchmark',f'scale-{factor}-{case}',case,'warm']
runpy.run_path('/evaluation/benchmark.py',run_name='__main__')
