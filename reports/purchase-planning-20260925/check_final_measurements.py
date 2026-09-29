import json,xml.etree.ElementTree as ET
from pathlib import Path
R=Path('reports/purchase-planning-20260925')
for f in ['tests-broad.xml','tests-final.xml','tests-checkout-final.xml','tests-cache-final.xml','tests-groups-final.xml']:
 x=ET.parse(R/f).getroot();print(f,len(x.findall('.//testcase')),len(x.findall('.//failure')),len(x.findall('.//error')))
d=json.loads((R/'comparison.json').read_bytes());print('newprices',d['new_campaign_prices'],d['new_food_campaign_prices'])
for x in json.loads((R/'final/verification-1280.json').read_bytes())['purchases']:
 if x['store'] in ['2352','0145'] and x['name'] in ['Gouda','Färsk pizza','Hushållsost','Persikor']:
  o=x['offer'];print(x['store'],x['name'], {k:o.get(k) for k in ['price','valid_from','valid_to','required_packages','max_quantity','member_program','description']})
print('profile', {k:v for k,v in json.loads((R/'profile/estimated-restored-original.json').read_bytes()).items() if k in ['status','cost','verification','portions','slots','store_count']})
