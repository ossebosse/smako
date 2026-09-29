import xml.etree.ElementTree as ET
import subprocess,sys
from pathlib import Path
root=Path('reports/purchase-planning-20260925')
files={t.get('classname').replace('.','/')+'.py' for t in ET.parse('reports/offer-expansion-20260924/tests-final.xml').findall('.//testcase')}
files.update('backend/tests/'+n+'.py' for n in ['test_purchase_planning_modes','test_purchase_quantity_resolver','test_product_search','test_personal_planning_v2','test_personal_booked_revisions','test_promotion_groups','test_shared_membership_pricing','test_citygross_purchase_limits','test_citygross_municipality_provider','test_coop_municipality_provider','test_ica_area_offer_provider','test_nutrition_store_search','test_personal_qualified_facts','test_variable_purchase_nutrition','test_source_promotion_groups'])
cmd=[sys.executable,'-m','pytest',*sorted(files),'-q','--tb=short','--junitxml='+str(root/'tests-release.xml')]
(root/'test-command.txt').write_text('\n'.join(cmd),encoding='utf-8')
with (root/'tests-release.log').open('w',encoding='utf-8') as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT)
print('exit',r.returncode);print((root/'tests-release.log').read_text(encoding='utf-8')[-16000:]);raise SystemExit(r.returncode)
