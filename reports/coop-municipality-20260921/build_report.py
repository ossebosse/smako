"""Generate coverage from observed inventory and actual isolated pipeline results."""
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from grocery_data.app.connectors.coop.municipality_inventory import build_inventory
from grocery_data.app.domain import GeographicArea, RawFetch, SourceStore
from grocery_data.app.services.area_membership import assess_area
from grocery_data.app.services.municipality_geometry import SCB_URL

R=Path(__file__).parent
inv=json.loads((R/'acceptance/inventory/inventory.json').read_bytes())
run=json.loads((R/'verified-final/result.json').read_bytes())
pu=json.loads((R/'verified-final/price-universe.json').read_bytes())
by_id={s['store']:s for s in run['stores']}
doc=json.loads((R/'acceptance/xtra-3658/result.json').read_bytes())
summary=[];examples=[];quarantine=[]
headers=['Butik / ID / koncept','Kommunstatus','Officiell källa','Insamling','Grupper / varianter','Godkända / karantän','OWN / PU','Verifierade ingrediensköp','Beta']
lines=['| '+' | '.join(headers)+' |','|'+'---|'*len(headers)]
for row in inv['stores']:
 s=row['store'];sid=s['external_id'];status=row['geographic_evidence']['status']; source=s['source_fields']; data=by_id.get(sid)
 out={'id':sid,'ledger':source['ledger_account_number'],'name':s['name'],'concept':source['concept'],'address':s['address'],'postal_code':s['postal_code'],'city':s['city'],'municipality_status':status,'municipality_reason':row['geographic_evidence']['reason'],'municipality_evidence':row['geographic_evidence'],'official_url':source['official_store_url'],'offers_url':source['offers_url'],'aliases':source['aliases'],'selected_from_inventory':row['collection_selected'],'collection_reason':row['collection_reason'],'production_activation':False,'beta':'only_isolated_test; current_production_not_queried'}
 if data:
  out.update(collection='structured_success_partial_rows',observed_at=data['observed_at'],source_hash=data['source_hash'],groups=data['ads'],variants=data['extracted_variants'],accepted=data['accepted'],quarantined=data['rejected'],own=data['own_projected'],price_universe=data['price_universe'],full_snapshot_status=data['status'],full_quality=data['qualification']['full_parse'],recipe_checkout_verified=3,nutrition_restricted_planning='not_verified',blocking_reasons=data['reasons'])
  parsed=json.loads((R/'final-sources'/(sid+'-extracted.json')).read_bytes())
  acceptedids={d['source_id'] for d in data['qualification']['decisions'] if not d['blockers']}
  products=[p for p in parsed['products'] if p['external_product_id'] in acceptedids]
  names=['Kärnvetemjöl','Nötfärs 20%','Färsk Pasta Fettuccine'] if sid!='2696' else ['Kärnvetemjöl','Morötter','Tomater Plommon']
  for name in names:
   p=next(p for p in products if p['name']==name);o=p['offers'][0]
   examples.append({'store_id':sid,'store_name':s['name'],'official_url':out['official_url'],'product':p['name'],'brand':p['brand'],'package_quantity':p['package_quantity'],'package_unit':p['package_unit'],'source_product_id':p['external_product_id'],'source_offer_id':o['external_id'],'price':o['price'],'required_packages':o['quantity'] or 1,'member_only':o['member_only'],'max_quantity':o['max_quantity'],'conditions':o['description'],'valid_from':o['valid_from'],'valid_to':o['valid_to'],'deposit_text':o['source_payload']['deposit_text'],'observed_at':data['observed_at'],'own':True,'price_universe':True})
  quarantine.extend({'store_id':sid,**d} for d in data['qualification']['decisions'] if d['blockers'])
 elif sid==doc['store_id'] and status=='inside':
  out.update(collection=doc['status'],observed_at=doc['observed_at'],source_hash=doc['sha256'],document_pages=doc['document_pages'],pages_read=doc['pages_read'],groups=None,variants=None,accepted=0,quarantined=None,own=0,price_universe=0,recipe_checkout_verified=0,nutrition_restricted_planning='not_verified',blocker=doc['reason'])
 else:
  out.update(collection='not_selected',groups=None,variants=None,accepted=None,quarantined=None,own=None,price_universe=None,recipe_checkout_verified=None,nutrition_restricted_planning='not_verified')
 summary.append(out)
 values=[f"{s['name']} / {sid} / {source['concept']}",status+'; '+out['municipality_reason'],f"[butik]({out['official_url']})",out['collection'],f"{out['groups'] if out['groups'] is not None else '?'} / {out['variants'] if out['variants'] is not None else '?'}",f"{out['accepted'] if out['accepted'] is not None else '—'} / {out['quarantined'] if out['quarantined'] is not None else '?'}",f"{out['own'] if out['own'] is not None else '—'} / {out['price_universe'] if out['price_universe'] is not None else '—'}",str(out['recipe_checkout_verified']) if out['recipe_checkout_verified'] is not None else '—','ej aktiverad här']
 lines.append('| '+' | '.join(values)+' |')
inside=[s for s in summary if s['municipality_status']=='inside']
# Reuse same actual all-store registry and independently retained SCB geometry for second-area proof.
c=RawFetch.model_validate_json((R/'acceptance/inventory/coop-map.json').read_bytes());x=json.loads((R/'acceptance/inventory/xtra-registry.json').read_bytes())
b=json.loads((R/'acceptance/inventory/boundary.json').read_bytes());p=(R/'regso-1280.json').read_text(encoding='utf-8')
b.update(municipality_code='1280',payload=p,source_sha256=hashlib.sha256(p.encode()).hexdigest(),source_url=SCB_URL+"?service=WFS&version=1.1.0&request=GetFeature&typeName=stat:RegSO_2025&outputFormat=application/json&srsName=EPSG:4326&CQL_FILTER=kommunkod%3D%271280%27",observed_at=datetime.fromtimestamp((R/'regso-1280.json').stat().st_mtime,ZoneInfo('UTC')).isoformat())
malmo=build_inventory(GeographicArea(city='Malmö',mode='municipality',municipality_code='1280'),json.loads(c.payload)['stores'],x['stores'],b,inv['sources'])
malmo['verification']='offline use of separately fetched real SCB geometry and official registry; no Malmö price fetch';malmo['boundary_evidence']=b
(R/'malmo-reuse.json').write_text(json.dumps(malmo,ensure_ascii=False,indent=2),encoding='utf-8')
counts=Counter(s['geographic_evidence']['status'] for s in malmo['stores'])
final={'generated_at':datetime.now(ZoneInfo('Europe/Stockholm')).isoformat(),'branch':'areas/municipality-audit-20260920','area':inv['area'],'inventory_source_rows':inv['registry_rows'],'all_registry_stores':len(summary),'municipality_counts':dict(Counter(s['municipality_status'] for s in summary)),'independently_complete':False,'completeness_reason':inv['completeness_reason'],'structured_stores':len(run['stores']),'source_groups':sum(s['ads'] for s in run['stores']),'source_variants':sum(s['extracted_variants'] for s in run['stores']),'accepted':sum(s['accepted'] for s in run['stores']),'quarantined':sum(s['rejected'] for s in run['stores']),'own':sum(s['own_projected'] for s in run['stores']),'price_universe':run['price_universe_count'],'price_universe_id':run['price_universe_id'],'examples':examples,'stores':summary,'recipe_checkout_proofs':27,'nutrition_planning_verified':False,'malmo_reuse_counts':dict(counts),'max_test_stores':2,'production_activation':False}
(R/'coverage-final.json').write_text(json.dumps(final,ensure_ascii=False,indent=2),encoding='utf-8')
(R/'quarantine-final.json').write_text(json.dumps(quarantine,ensure_ascii=False,indent=2),encoding='utf-8')
(R/'ALL_STORES.md').write_text('# Alla publicerade registerposter\n\n778 butiksposter; inom/utanför/okänd behålls. Streck = inte insamlat; ? = okänt antal, inte noll.\n\n'+'\n'.join(lines)+'\n',encoding='utf-8')
short=[lines[0],lines[1]]+[line for line,s in zip(lines[2:],summary,strict=True) if s['municipality_status']=='inside']
text='''# Butikstäckning – Lunds kommun 1281

Färsk insamling 21 september 2026 kl. 19:55–19:58 Europe/Stockholm.
Nationell Coop-karta: 720 poster. X:-tra: 58 poster, kontrollerade mot samtliga
butikslänkar i samma officiella register. Alla 778 poster prövades: tio inom
Lunds kommun, 768 utanför, noll okända i detta källmaterial. En komplett publicerad
registerlista är inte oberoende bevis för att varje verklig butik finns med.
Inga misslyckade butiker har tagits bort. [Alla 778 rader](ALL_STORES.md).

Position från respektive officiellt register prövas mot SCB RegSO 2025, som
följer kommunindelningen 2025-01-01. Kommun-ID verifieras mot befintligt SCB-register.
Källversion, koordinater, hash och observation sparas. Inom tio meter från
någon delområdesgräns blir status okänd. Ingen ny radie/postnummerlikhet.
Genarp och Veberöd tillkommer jämfört med adressorten Lund: tio kommunbutiker
mot åtta adressortsbutiker, inklusive X:-tra i båda. Adressortsläget är oförändrat.
Registrets positionsnoggrannhet och gränsändringar efter 2025 är begränsningar;
Trollebergsvägens registerposition ligger misstänkt nära Flöjtvägen. Båda ligger
inom Lund, men positionerna är inte verifierade för avståndsberäkning/ruttning.

Varje Coop-butik har ett eget kontrollerat StorePageType-ID och konto samt ett
separat faktiskt strukturerat svar. De gemensamma priserna har inte kopierats.

'''+ '\n'.join(short)+'''

Godkända/karantän avser butik–produktvariant, inte oberoende kampanjer.
Totalt 372 butikskampanjer, 2 436 variantposter, 499 godkända och 1 937 i karantän.
Samtliga nio fulla snapshotkontrakt är fortsatt underkända; 95%-krav och hela
nämnaren är oförändrade. Endast det uttryckliga partiella radkontraktet publiceras
inom testdatabasen. Blockerare per variant och överlapp finns i
[quarantine-final.json](quarantine-final.json); fulla kvalitetsmått i
[coverage-final.json](coverage-final.json). Ingen karantän har tappats bort.

”Verifierade ingrediensköp” är tre konkreta produkter per Coop-butik som passerat
matcher, checkout och audit. Det är inte ett fullständigt antal planeringsbara
produkter. Näringsbegränsad planering har inte kvalificerats för dessa 499 poster;
inget nytt verifierat näringsunderlag har lagts till. Ingen vinnande meny eller
besparing påstås. Äldre Bulltofta-underlag hör till Malmö och är bevarat separat.

X:-tra Skansvägen 3658 / konto 216525 är upptäckt och dess butikslänk leder till
åtta PDF-sidor. Samtliga åtta har hämtats och text extraherats. Status är
`document_text_unintegrated`, inte ”saknar erbjudanden” och inte enbart bildberoende.
Ingen strukturerad produktpost exponerades i butikens publicerade data; PDF-texten
saknar ännu verifierad koppling annons–pris–variant–villkor för befintligt köpavtal.
Sista sidan gäller först torsdag 24–söndag 27 september; den får inte bli måndagspris.
Noll importer, okänt fullständigt annons-/karantänantal. Därför är prisinsamlingen
9 av 10 upptäckta kommunbutiker och täckningen uttryckligen partiell.

Första körningen stoppades av sträng/heltal vid jämförelse av samma butikskonto;
rättad med strikt ID-regression. Stora Coop hade nya uttryckliga åldersvillkor:
de sparas nu och 23 berörda varianter karantänsätts. Okända schemafält stoppar
fortfarande hela berörda källan. Stora hämtades på nytt efter rättningen.
Övriga färska källbatcher verifierades oförändrade med slutparsern; deras tider
har inte flyttats. Misslyckade förkörningar ligger kvar som separat evidens.

Kommuninsamlingen använder inventeringens `selected_store_ids`. Den gamla
OWN-postnummerhjälpen stöder fortfarande bara 20/21/22-prefix: den används inte
som kommungräns. Den isolerade verifieringen hämtar befintliga OWN-/stores-rader
per belagd adressort och exakt käll-ID och använder vanliga OWN get_offers.
En framtida betaexpansion måste koppla detta explicita kommunurval till användarens
butiksval; befintliga profiler har inte fått ett tyst utvidgat sökområde.
'''
text+=f"\nSamma kod på Malmö 1280 med sparade verkliga källor: {dict(counts)}; {len(malmo['selected_store_ids'])} Coop-butiker valda. Ingen Malmö-prisinsamling genomförd här.\n"
(R/'COVERAGE.md').write_text(text,encoding='utf-8')
lines=['# Aktuella konkreta erbjudanden','', 'Alla nedan finns i isolerat OWN och PriceUniverse; inte aktiverade i betan.','Tre separat butikskällbelagda exempel per Coop-butik. Käll-ID är opakt, inte påstått GTIN.','Saknat köpgränsbelopp är inte ett påstående om obegränsade köp. Ingen pantuppgift visas som ett uppfunnet nollbelopp.','']
for store in inside:
 lines.extend([f"## {store['name']} – {store['address']}, {store['city']} – ID {store['id']}",''])
 ex=[e for e in examples if e['store_id']==store['id']]
 if not ex:
  lines.append(f"[Officiell butik]({store['official_url']}) · [butikslänkat reklamblad]({doc['source_url']}). Åtta textsidor hämtade; prisimport blockerad av saknat verifierat dokumentavtal. Inga strukturerade prisposter att visa som importgodkända.\n")
  continue
 lines.extend(['| Produkt / förpackning | Köppris | Villkor | Gäller | Källpost |','|---|---|---|---|---|'])
 for e in ex:
  price=f"{e['required_packages']} för {e['price']} kr" if e['required_packages']>1 else f"{e['price']} kr/st"
  conditions=('Coop-medlem. ' if e['member_only'] else 'Publikt. ')+e['conditions']
  lines.append(f"| {e['product']}, {e['brand'] or 'varumärke saknas'}, {e['package_quantity']} {e['package_unit']}/st | {price} | {conditions}; pant: ingen angiven tillämplig pant | {e['valid_from']}–{e['valid_to']} | [butik]({e['official_url']}), `{e['source_offer_id']}` |")
 lines.extend(['',f"Observerat: {store['observed_at']}. Samma butiks-ID, prisgrupp, medlemskap och datum bevarade i OWN/PU. Recept-/checkoutprov: PASS; näringsstyrd meny: inte verifierad.",''])
(R/'EXAMPLES.md').write_text('\n'.join(lines),encoding='utf-8')
print(json.dumps({k:final[k] for k in ['municipality_counts','accepted','quarantined','source_groups','source_variants','malmo_reuse_counts']},ensure_ascii=False))
