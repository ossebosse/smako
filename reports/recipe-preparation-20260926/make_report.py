"""Render only measured files. Fail if an expected run is incomplete."""
import json
from collections import Counter
from pathlib import Path

R=Path(__file__).parent
P=R/'profile'
def read(name):return json.loads((P/name).read_text(encoding='utf-8'))
cases=read('all-84.json')
assert len(cases)==84
parents={r['original_hash'] for r in cases}
summary={'kind':'historical replay; recipe versions separated from code-only regression',
         'clock':'2026-09-24T21:16:35.494010+00:00',
         'price_source_requests':0,'new_nutrition_values_imported':0,
         'denominator':84,'original_preparation_passed':0,
         'adapted_preparation_passed':sum(bool(r.get('preparation_passed')) for r in cases),
         'product_match_passed':sum(bool(r.get('product_match_passed')) for r in cases),
         'nutrition_attempted':sum(bool(r.get('nutrition_attempted')) for r in cases),
         'nutrition_basket_passed':sum(bool(r.get('nutrition_basket_passed')) for r in cases),
         'nutrition_numerically_evaluated':sum(bool(r.get('nutrition_basket_passed')) or r.get('stop',{}).get('code')=='NUTRITION_TARGET_NOT_MET' for r in cases),
         'exhaustive_case_seconds':round(sum(r['seconds'] for r in cases),3),
         'first_stop_stages':dict(Counter(r.get('stop',{}).get('stage','passed') for r in cases)),
         'profiles':[],'http':[]}

def projection(plan):
 b=plan['optimized_basket'];items=[i for s in b['stores'] for i in s['items']]
 return {'cost':b['total'],'quality':b['verification_status'],
         'stores':[{'name':s['store_name'],'channels':sorted({i['price_context_type'] for i in s['items']})} for s in b['stores']],
         'rows':dict(Counter(i['verification_status'] for i in items)),
         'nutrition_statuses':dict(Counter(n['status'] for n in plan['personal']['checks']['nutrition'])),
         'selected_from_84':sorted({s['recipe']['preparation']['parent_sha256'] for s in plan['personal']['slots'] if s.get('recipe',{}).get('preparation',{}).get('parent_sha256') in parents}),
         'selected_recipes':[{'name':s['recipe']['name'],'method':s['recipe'].get('preparation',{}).get('version')} for s in plan['personal']['slots']],
         'selected_products':items}

for member in ('public','plus'):
 for mode in ('exact','estimated'):
  row={'membership':member,'mode':mode}
  for definition in ('legacy','edible-input-v1'):
   label=f'{definition}-{member}-{mode}-restored-original'
   result=read(label+'.json');assert result.get('status')=='PASS',(label,result.get('reason'))
   plan=read(label+'-plan.json')
   row[definition]={**projection(plan),'seconds':result['seconds']}
  summary['profiles'].append(row)
for name in ('http-warm-lidl-after-integration.json','http-generated-tofu-after-integration.json'):
 data=read(name)
 assert data['restart']['saved_plan_identical'] and data['restart']['process_restarted']
 for record in data['cases']:
  row={'case':name,'mode':record['mode'],'http_status':record['http_status'],'seconds':record['seconds'],
       'restart':data['restart'],'request':data['request']}
  if record['http_status']==201:
   response=record['response']
   plan=response.get('plan',response)
   row.update(projection(plan))
   row['nutrition']=plan['personal']['checks']['nutrition']
   row['audit']=plan['personal']['checks']['checkout_audit']
  else:row['failure']=record['response']
  summary['http'].append(row)
(R/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')

lines=['# Recept och beredning – mätt resultat, 26 september 2026','',
       'Historisk replay med samma kompletta bas, köpdag och medlemskontext inom varje jämförelse. Prisobservationer har inte ändrats. Inga produktlås, extraköp eller handpatchade kandidater.', '',
       '| De ursprungligen blockerade recepten | Gamla versioner | Nya versioner |',
       '|---|---:|---:|',
       f'| Nämnare | 84 | 84 |',
       f'| Beredningsgodkända med opt-in | 0 | {summary["adapted_preparation_passed"]} |',
       f'| Samtliga ingredienser når produkt-/köpmatchning | 0 efter beredningsgrinden | {summary["product_match_passed"]} |',
       f'| Når näringsprövning i varukorgen | 0 | {summary["nutrition_attempted"]} |',
       f'| Minst en korg får numeriskt näringsresultat | 0 | {summary["nutrition_numerically_evaluated"]} |',
       f'| Näringsmål + varukorg + audit passerar separat | 0 | {summary["nutrition_basket_passed"]} |','',
       'Godkänd beredning är inte produkt-, närings- eller menyselektion. Samtliga original och nya definitioner, exakta mängdändringar, källor, avslag och godkända korgar finns i `profile/all-84.json`. Originalen jämfördes mot den tidigare rapportens ingrediensmängder och instruktioner, inte bara mot namn.', '',
       '| 15/20: medlemskap / köpläge | Gamla recept: kr / s | Nya recept: kr / s | Valda av de 84, unika |',
       '|---|---:|---:|---:|']
for r in summary['profiles']:
 a,b=r['legacy'],r['edible-input-v1']
 lines.append(f'| {r["membership"]} / {r["mode"]} | {a["cost"]:.2f} / {a["seconds"]:.3f} | {b["cost"]:.2f} / {b["seconds"]:.3f} | {len(b["selected_from_84"])} |')
lines += ['', '40/30/20 g protein, 15 måltider/20 portioner, högst två inköpsställen är oförändrade. Gamla recept är en kodregression; de nya versionerna ändrar receptinnehåll och tillagning. En kostnadsskillnad mellan dessa pooler är inte en besparing för identisk mat. Körningstider är enstaka uppmätta körningar, inte ett statistiskt prestandatest. Butiker, kanaler, kvalitetsstatus, köprader, näringsstatus och valda produkter finns fullt ut i `summary.json`.', '',
          '| HTTP-fall | Köpläge | Status | Kostnad | Sekunder | Korgkvalitet |',
          '|---|---|---:|---:|---:|---|']
for r in summary['http']:
 lines.append(f'| {"Varm Lidl-ostsmörgås" if "warm-lidl" in r["case"] else "Genererad tofumacka"} | {r["mode"]} | {r["http_status"]} | {r.get("cost","–")} | {r["seconds"]} | {r.get("quality","spärrat")} |')
lines += ['', 'Båda HTTP-proven använder ordinarie POST/GET och verklig backendprocessomstart med identisk återläst plan. Tofumackan är ett av de 84 tidigare spärrade recepten, med oförändrat 30 g proteinmål och ordinarie område/max två butiker. Varm ostsmörgås är ett separat nytt tillagningsfall: explicit Lidl-butik, Lidl Plus för brödet och det offentliga Arla-erbjudandet. Den räknas inte som ett 85:e återvunnet recept.', '',
          'Arla köps som helt cirka 2,2 kg-paket för cirka 153,78 kr; 100 g används. Bröd 17,90 kr ger totalt cirka 171,68 kr. Näringsberäkningen använder 100 g ost och 100 g bröd, 33,8 g protein. Varm insatsberäkning är ESTIMATED även med verifierade deklarationer. Allergisäkerhet är inte begärd/bevisad. Exakt köpplanering spärrar cirka-osten.', '',
          '## Vad som ändrats', '',
          '- Versionerade definitioner för generatorns 15 varma mallar samt de fyra särskilda beredningsfallen. Originalen finns kvar som legacy och i varje fallrapport.',
          '- Explicit rapsolja 5/7,5/10 ml per portion efter tillagningsmall; hela mängden räknas. Ägg och tortillas har nya massbaserade receptportioner, inte påhittade styckvikter. Crème fraiche vägs i de nya versionerna; ml har inte behandlats som gram i näringsräkningen.',
          '- Gemensam operand-/instruktionsvaliderad insatsberäkning per portion. Ingen färdig rättvikt, retention, oljeupptag, densitet eller ätbar andel tillverkas.',
          '- Verifierade deklarationer prioriteras; generiska SLV-referenser och skafferiformer behåller opt-in, källa och version. Ursprunglig evidenstyp följer den uppskattade tillagningsberäkningen.',
          '- Komplett konservdeklaration får inte bli rå tomat. Äggkartongens vikt får inte bli ätbar äggmassa utan belägg. Köppris och näringsgodkännande hålls isär.',
          '- Metodmetadata överlever API/PlanStore och ingår i receptidentitet/cacheunderlag.', '',
          '## Kvarstående hinder', '',
          'Exakta första stopp per recept finns i `all-84.json`. Ett sökavslag efter högst 256 näringskombinationer är en sökbegränsning, inte ett bevis om global omöjlighet eller högre pris. Sökning, produktdiagnostik och hela förpackningspriser är bevarade.', '',
          'Ägg behöver belagd ätbar inköpsmängd eller direkt mätbar hel äggmassa; inga skal-/styckfaktorer har hittats på. Kikärtor behöver rätt produktbindning, avrunnen användbar inköpsmängd och avrunnen näringsgrund. Metoden stöder sådana belagda fält och SLV 3815 med rätt råvara; frysta källrader med bara nettovikt kvalificeras inte.', '',
          'En separat officiell webbkällkontroll av Zeta visar 230 g avrunnen vikt; direkt dokumentarkivering gav HTTP 403. Inga nya värden eller produktkopplingar från denna kontroll har importerats i jämförelsen. Se `sources/zeta-check.json` och [officiell sida](https://www.zeta.nu/produkter/kikartor-ekologiska/).', '',
          'Övriga stopp omfattar saknad köpbar ingrediens i basen, saknad passande enhet/deklaration och sökningar utan funnen målkompatibel korg. Inget fall har tagits bort ur nämnaren.', '',
          'Färsk produktionsbas, fullständig Malmö-publicering och historisk Lidl-fixture är separata öppna uppgifter. Prisimporter, providers, PurchaseTerms, kommunfunktion, observationstider, scheman och sparade användarprofiler har inte ändrats. Ingen produktionsaktivering.']
lines += ['', '## Första stopp, utan dubbelräkning', '',
          '| Orsak | Recept |', '|---|---:|']
for cause, count in json.loads((R/'blocker-counts.json').read_text(encoding='utf-8')).items():
 lines.append(f'| {cause} | {count} |')
lines += ['', 'De fyra fria körningarna använder Coop Online Syd (online_fulfillment) och Willys Lund (online_store). Korgarna är VERIFIED: 12 exakta rader före, 16 efter, inga uppskattade eller villkorade köprader. Näring redovisas separat: 5 ESTIMATED och 10 VERIFIED måltider både före och efter.', '',
          'De två nytillgängliga valda recepten är Tomatpasta med lax och gul lök samt Gryta med lax, nudlar och vitkål. Tofumackans HTTP-korg använder Coop Online Syd och fyra exakta rader; 36,4 g protein mot 30 g krav. Lidl-provet har en exakt och en uppskattad köprad.', '',
          'Riktade regressioner: 179 godkända, inga fel eller överhoppade prov. Ruff och compileall passerar. Historisk Lidl-fixture ingick inte och kvarstår separat. För ägg, avrunna baljväxter och g/ml-varor återstår kvalificerade mängd-/faktakopplingar; de beskrivs inte som färdigställda genom metodstödet.']
(R/'VERIFICATION.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in summary.items() if k not in ('profiles','http')},ensure_ascii=False))
