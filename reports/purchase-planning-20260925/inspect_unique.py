import json
from pathlib import Path
from collections import Counter
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
R=Path('reports/purchase-planning-20260925');O=R.parent/'offer-expansion-20260924'
def identity(p):
 o=p.offers[0]
 return (p.chain,p.name.casefold(),(p.brand or '').casefold(),p.package_quantity,p.package_unit,o.price,o.price_basis_unit,o.required_packages,str(o.eligibility),str(o.membership_program),str(o.valid_from),str(o.valid_to),o.max_quantity)
def products(root):
 d={}
 for code in ['1281','1280']:
  pu=PreparedPriceUniverseArtifact.model_validate_json((root/f'prepared-{code}-second.json').read_bytes()).restore()
  for p in pu.universe.products:d[identity(p)]=p
 return d
b,a=products(O),products(R/'final');bc={p.offers[0].price_contract_id for p in b.values()}
new=[p for k,p in a.items() if k not in b]
print('before',Counter(p.chain for p in b.values()),'after',Counter(p.chain for p in a.values()),'new',len(new))
for p in new:print(p.chain,p.name,p.package_quantity,p.offers[0].price,p.purchase_terms.usage if p.purchase_terms else None,'previous_campaign',p.offers[0].price_contract_id in bc)
print('removed',[(b[k].chain,b[k].name) for k in b if k not in a])
