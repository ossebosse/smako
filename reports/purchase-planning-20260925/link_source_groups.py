from pathlib import Path
for name,token in [('willys_flyers','context'),('lidl_municipality','context'),('citygross_municipality','context'),('coop_municipality_offers','context'),('ica_area_offers','context_id')]:
 p=Path('backend/app/providers')/(name+'.py');s=p.read_text();mark='from app.services.source_promotion_groups import groups_in_context\n'
 # Keep future imports first; attach alongside an existing app import.
 i=s.index('from app.');s=s[:i]+mark+s[i:]
 if name in ['willys_flyers','lidl_municipality','citygross_municipality']:
  a='accepted.append(product.model_copy(update={"store_id": context,';b=a+'\n                    "promotion_groups": groups_in_context(product, context),';assert a in s;s=s.replace(a,b)
 elif name=='coop_municipality_offers':
  a='                                "store_id": context,\n                                "price_context_type"';b='                                "store_id": context,\n                                "promotion_groups": groups_in_context(product, context),\n                                "price_context_type"';assert a in s;s=s.replace(a,b)
 else:
  a='"store_id": context_id, "price": None, "offers": offers,';b=a+'\n                            "promotion_groups": groups_in_context(product, context_id),';assert a in s;s=s.replace(a,b)
 p.write_text(s)
