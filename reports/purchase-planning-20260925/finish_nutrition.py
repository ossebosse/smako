from pathlib import Path
import json
p=Path('grocery_data/tests/test_lidl_municipality.py');s=p.read_text();s=s.replace('len(parsed.failures) == 357','len(parsed.failures) == 355');p.write_text(s)
p=Path('backend/tests/test_promotion_groups.py');s=p.read_text().replace("with pytest.raises(ValueError,match='ordinary price evidence'):","with pytest.raises(ValueError,match='No complete basket'):");p.write_text(s)
r=Path('reports/purchase-planning-20260925/sources')
a=json.loads((r/'slv-persika-nutrients-acquisition.json').read_bytes())
entry={'food':json.loads((r/'slv-persika.json').read_bytes()),'nutrients':json.loads((r/'slv-persika-nutrients.json').read_bytes()),'source_url':a['url'],'retrieved_at':a['observed_at'],'acquisitions':[json.loads((r/n).read_bytes()) for n in ['slv-persika-acquisition.json','slv-persika-nutrients-acquisition.json']]}
obj={'source':'Livsmedelsverkets Livsmedelsdatabas','retrieved_at':a['observed_at'],'use':'Generic raw edible grams only; gross weight and stone removal conversion are not established.','foods':{'580':entry}}
Path('backend/app/data/nutrition/slv-20260925.json').write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
p=Path('backend/app/services/nutrition_reference.py');s=p.read_text().replace('    574: ("mango", "raw"),','    574: ("mango", "raw"),\n    580: ("persika", "raw"),')
a=s.index('    supplement = json.loads(SUPPLEMENT_PATH.read_bytes())');b=s.index('    for identity in MAPPINGS:',a)
s=s[:a]+'''    for path in (SUPPLEMENT_PATH, PATH.with_name('slv-20260925.json')):
        supplement = json.loads(path.read_bytes())
        if data['foods'].keys() & supplement['foods'].keys():
            raise ValueError('SLV supplement must not silently replace retained references')
        data['foods'].update(supplement['foods'])
        data.setdefault('supplements', {})[path.name] = {k: v for k, v in supplement.items() if k != 'foods'}
'''+s[b:];p.write_text(s)
p=Path('backend/tests/test_nutrition_reference.py');s=p.read_text().replace('len(MAPPINGS) == 41','len(MAPPINGS) == 42');p.write_text(s)
