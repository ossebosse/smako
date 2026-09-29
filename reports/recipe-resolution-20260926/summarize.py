"""Summarize completed files only; this script is not verification evidence."""
import json,hashlib,collections
from pathlib import Path
R=Path(__file__).parent;ROOT=R.parents[1];P=R/'profile'
def load(p):return json.loads(p.read_bytes())
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf8')
before=load(ROOT/'reports/recipe-preparation-20260926/profile/all-84.json')
after=load(P/'all-84.json')
assert len(before)==len(after)==84
assert all(a['adapted']==b['adapted'] for a,b in zip(before,after,strict=True))
def metrics(rows):
 return {'total':len(rows),'preparation':sum(bool(x.get('preparation_passed')) for x in rows),
 'nutrition_attempted':sum(bool(x.get('nutrition_attempted')) for x in rows),
 'numeric':sum(bool(x.get('nutrition_basket_passed')) or x.get('stop',{}).get('code')=='NUTRITION_TARGET_NOT_MET' for x in rows),
 'passed':sum(bool(x.get('nutrition_basket_passed')) for x in rows)}
oldpass={x['adapted']['name'] for x in before if x.get('nutrition_basket_passed')};newpass={x['adapted']['name'] for x in after if x.get('nutrition_basket_passed')};assert oldpass<=newpass
searches=load(P/'all-84-diagnostics.json')['nutrition_searches']
stops=[]
for old,new in zip(before,after,strict=True):
 name=new['adapted']['name'];matching=[s for s in searches if any(r['name']==name for r in s['recipes'])]
 last=matching[-1] if matching else None
 if not new.get('nutrition_basket_passed') and new.get('stop',{}).get('code')=='NUTRITION_TARGET_NOT_MET':
  assert last and last['numeric_passed']+last['nutrition_rejections']>0, (name,'no actual numeric evidence')
 status='PASS' if new.get('nutrition_basket_passed') else 'SEARCH_BUDGET' if last and last['budget_exhausted'] else new['stop']['code']
 stops.append({'recipe':name,'before':old.get('stop',{'code':'PASS'}),'after_first_stop':status,
 'after':new.get('stop'), 'search':last,'cost':new.get('basket',{}).get('total'),'seconds':new['seconds']})
write(R/'recipe-first-stops.json',stops)
source_usage={}
for row in after:
 for ingredient in row['ingredient_evidence']:
  for candidate in ingredient['qualified']:
   evidence=candidate['facts']['field_sources'].get('nutrition.protein_g',[])
   for source in evidence:
    identity=source.get('food_id') or source.get('gtin')
    if identity not in {1225,3815,3816,3817,3761,'7310867003803'}:continue
    use=source_usage.setdefault(str(identity),{'qualified_recipe_products':set(),'recipes':set(),'selected_in_passed_recipes':set()})
    use['qualified_recipe_products'].add((candidate['store_id'],candidate['product_id']))
    use['recipes'].add(row['adapted']['name'])
    if row.get('nutrition_basket_passed') and any(i['product_id']==candidate['product_id'] and i['store_id']==candidate['store_id'] for g in row['basket']['stores'] for i in g['items']):use['selected_in_passed_recipes'].add(row['adapted']['name'])
source_usage={k:{n:sorted(v) for n,v in values.items()} for k,values in source_usage.items()}
write(R/'source-use.json',source_usage)
cohorts={}
for old,new,stop in zip(before,after,stops,strict=True):
 reason=old.get('stop',{}).get('reason','')
 if old.get('nutrition_basket_passed'):group='Tidigare godkända'
 elif old['stop']['stage']=='nutrition':group='Tidigare 20 sökavslag'
 elif reason.startswith('Ingen verifierad köpbar vara för rödlök'):group='Rödlök'
 elif reason.startswith('Ingen verifierad köpbar vara för crème fraiche'):group='Crème fraiche'
 elif reason.startswith('Ingen verifierad köpbar vara'):group='Bönmatchning'
 else:group='Nio mängd-/näringsfall'
 cohort=cohorts.setdefault(group,{'total':0,'numeric':0,'passed':0,'first_stops':collections.Counter()})
 cohort['total']+=1;cohort['numeric']+=bool(new.get('nutrition_basket_passed')) or new.get('stop',{}).get('code')=='NUTRITION_TARGET_NOT_MET'
 cohort['passed']+=bool(new.get('nutrition_basket_passed'));cohort['first_stops'].update([stop['after_first_stop']])
profiles=[]
for p in sorted(P.glob('*-restored-original.json')):
 x=load(p)
 if x.get('status')!='PASS':raise ValueError(str(p)+' incomplete')
 plan=load(p.with_name(p.stem+'-plan.json'));basket=plan['optimized_basket'];items=[i for g in basket['stores'] for i in g['items']]
 names=[s['recipe']['name'] for s in plan['personal']['slots'] if s.get('recipe')]
 profiles.append({'case':p.stem,'cost':x['cost'],'seconds':x['seconds'],'quality':x['verification'],
 'stores':[{'name':g['store_name'],'id':g['store_id']} for g in basket['stores']],
 'channels':sorted({i.get('price_context_type','unknown') for i in items}),
 'purchase_rows':dict(collections.Counter('conditional' if i.get('conditional_variant_choice') else 'estimated' if i.get('quantity_confidence')=='estimated' else 'exact' for i in items)),
 'nutrition_rows':dict(collections.Counter(n['status'] for n in plan['personal']['checks']['nutrition'])),
 'original84_selected':[n for n in names if n in {r['adapted']['name'] for r in after}],
 'recipes':names,'stage_timings_inclusive':x['stage_timings_inclusive'],'cache_state':x['cache_state']})
search=load(P/'search-reference.json')
reference={str(b):{'cases':len([r for r in search if r['budget']==b]),'passed':sum(r['passed'] for r in search if r['budget']==b),
 'budget_reached':[r['recipe'] for r in search if r['budget']==b and r['searches'] and r['searches'][-1]['budget_exhausted']],
 'seconds':sum(r['seconds'] for r in search if r['budget']==b)} for b in sorted({r['budget'] for r in search})}
http=load(P/'http-new-recipes-after-integration.json');http_summary=[]
cream=load(P/'http-cream-after-integration.json')
http['cases']+=cream['cases'];http['rollback']+=cream['rollback'];http['restart']+=cream['restart']
for c in http['cases']:
 row={k:c[k] for k in ('recipe','mode','seconds','http_status')}
 if c['http_status']==201:
  plan=c['response']['plan'];basket=plan['optimized_basket'];items=[i for g in basket['stores'] for i in g['items']]
  row.update(cost=basket['total'],quality=basket['verification_status'],stores=[g['store_name'] for g in basket['stores']],
   rows=dict(collections.Counter('estimated' if i.get('quantity_confidence')=='estimated' else 'exact' for i in items)),
   nutrition=plan['personal']['checks']['nutrition'],roundtrip=c['roundtrip_identical'])
 else:row['reason']=c['response']
 http_summary.append(row)
summary={'baseline':metrics(before),'after':metrics(after),'preserved_previous_passes':len(oldpass),
 'new_passed':sorted(newpass-oldpass),'first_stops':dict(collections.Counter(s['after_first_stop'] for s in stops)),
 'recipe_content_changed':False,'cohorts':cohorts,'profiles':profiles,'reference_search':reference,'http':http_summary,'imported_source_use':source_usage,
 'rollback':[{'get_status':r['get_status'],'saved_plan_identical':r['saved_plan_identical'],'recalculate_status':r['recalculate_status'],'preserved_after_failed_recalculate':r['preserved_after_failed_recalculate']} for r in http['rollback']],
 'restart':http['restart'],'acquisition':'New official nutrition/quantity documents retrieved 2026-09-26; immutable price replay 2026-09-24T21:16:35.494010+00:00. No price requests or observation renewal.'}
write(R/'summary.json',summary)
lines=['# Recept- och mängdupplösning, 26 september 2026','',
 'Genererad från slutförda körningsfiler. Isolerad historisk prisreplay 24 september; nya officiella fakta hämtade 26 september. Ingen produktionsaktivering.',
 '84-provet använder samma uppskattningsläge och Willys Plus/Lidl Plus som föregående 84-prov. Näringsuppskattningar är ett separat bevarat opt-in. De fria profilerna nedan prövar även exakt läge och ursprunglig medlemskontext.',
 '', '| Samtliga ursprungliga 84 | Före (v1) | Efter (samma v1) |','|---|---:|---:|']
for k,label in [('preparation','Beredningsgodkända'),('nutrition_attempted','Vidare till näringsprövning'),('numeric','Numeriskt näringsresultat'),('passed','Näringsmål + varukorg + audit')]:lines.append(f"| {label} | {summary['baseline'][k]} | {summary['after'][k]} |")
lines+=['',f"Samtliga {len(oldpass)} tidigare godkända bevarade. {len(newpass-oldpass)} nytillkomna godkända recept. Ingen ingrediensmängd, portionsstorlek, instruktion eller v1-receptdefinition ändrad i denna etapp. Originalrecepten kontrolleras separat och finns kvar.",
 '', '## Första stopp utan dubbelräkning', '',str(summary['first_stops']),
 'Samtliga 84 rader, tidigare stopp och nuvarande stopp med konkret skäl: [recipe-first-stops.json](recipe-first-stops.json). Budgetavslag är inte bevis för omöjlighet eller högre pris.',
 '', '## Fri 15/20-plan', '', '40/30/20 g, max två inköpsställen. Samma frysta bas, inköpsdag och medlemskontext per par. Kalla planner-cachar i ny process; värdmaskinens OS-sidcache är inte tömd. `comparison-inputs.json` verifierar identiska anrop, prisartefakter, testklockor och sökinställningar.',
 '', '| Körning | kr | sekunder | Kvalitet | Exakta/uppskattade/villkorade rader | Valda av de 84 |','|---|---:|---:|---|---|---|']
for x in profiles:
 q=x['purchase_rows'];lines.append(f"| {x['case']} | {x['cost']:.2f} | {x['seconds']:.3f} | {x['quality']} | {q.get('exact',0)}/{q.get('estimated',0)}/{q.get('conditional',0)} | {', '.join(x['original84_selected']) or 'inga'} |")
lines+=['','Samtliga jämförbara v1-körningar väljer Coop Online Syd (online_fulfillment) och Willys Lund (online_store). Korgarna har 16 exakta rader; näring redovisas separat med 10 VERIFIED och 5 ESTIMATED. Ingen fysisk butiksprisgiltighet härleds från onlinepriser.',
 'Butiker, kanaler, faktiskt valda recept, separat näringskvalitet och uppmätta delsteg finns i [summary.json](summary.json). Kostnaderna avser hela varukorgar; ingen framtvingad besparing.',
 '', '## Gemensamma kodrättningar och verkliga källor','',
 '- Rödlök och bönor: grov låg källklassning får inte stoppa före den befintliga produktmatcharens identitets-/beredningsprövning. Picklad lök, chips och gul lök förblir egna identiteter. Produktvis före/efter med accepterade och avvisade kandidater: `profile/diagnose-before.json` och `profile/diagnose-after.json`.',
 '- Beredningsform: gravad/gravlax/rimmad klassas i den gemensamma matcharen som beredd produkt, inte rå fisk. Detta fångades i mellankörningens jämförelse med tidigare meny; mellankörningen är arkiverad separat och ersätter inte slutresultaten.',
 '- Blandfärs: bred navigationskategori Fläskfärs/Nötfärs får inte övertrumfa entydigt produktnamn. Produkt-, roll- och beredningsgrindarna kvarstår.',
 '- Dabasimport via befintligt deklarationsregister: exakt kontrollsiffergranskad GTIN, varumärke och konsumentförpackning. Åtta leverantörsblad sparade med hash, faktisk hämtningstid och dokumentversion. Inga priser eller allergenbesked överförs.',
 '- Skånemejerier crème fraiche 32 %, GTIN 7310867003803: källan anger 2 dl och 200 g nettovikt för just denna konsumentförpackning. Deklaration per 100 ml kan räknas på den belagda mängdrelationen. Arlas 2 dl utan belagd gramvikt får ingen sådan omräkning. Ingen generell ml=g-regel och ingen receptomskrivning.',
 '- Bönor: inköpt nettovikt skiljs från explicit avrunnen vikt. Leverantörens tabell blir inte automatiskt en deklaration för avrunnen vara. SLV 3815/3816/3817/3761 används som märkta generiska referenser när identitet, sammansättning och form stämmer och opt-in är aktivt.',
 '- GoGreen svarta bönor, GTIN 7310130009785: kvarstående källkonflikt 112 mot 100 kcal och 7,4 mot 5,6 g protein/100 g. Båda källorna bevaras; posten näringsgodkänns inte genom att välja gynnsammare värde.',
 '- Skalägg: dokumenterad populationsuppskattning cirka 12 % skal (Svenska Ägg, Marknadsrapport 2019, PDF-sida 25). Endast källbelagd kartongvikt får projiceras till uppskattad ätbar mängd, med separat inköpsopt-in. 636 g blir uppskattat 559,68 g ätbart; hela kartonger köps. Styckantal blir inte gram. Kontrollvägning krävs; exakt läge behåller spärren. SLV 1225 är importerad reservreferens; verifierad produktdeklaration prioriteras när tillämplig.',
 '- Begäranslokal cache för oförändrad receptkontroll. Nyckeln innehåller hela receptversionen och mängdenheter, måltids-/kostpolicy, medlemsidentitet och inköpsläge. Ingen global cache och ingen höjning av ordinarie 256-budget.',
 '', 'Se [sources/imported-declarations.json](sources/imported-declarations.json), sparade HTML/PDF/API-svar och `profile/all-84.json` (ingrediensvis faktiskt prövat näringsunderlag). Källa, ursprungliga värden och observationer bevaras.',
 '', '## Sökning och tid','',
 f"Referensprov för ursprungliga 20 avslag: {reference}. Ny planner per budget; samma data och krav. Sökrymden gäller behållna näringsklasser, inte alla matematiskt tänkbara produkter.",
 'Delstegen är uppmätta inklusiva tider och överlappar: kandidatgenerering omfattar närings-/varukorgsprov. De får inte summeras. Separat legacy-körning skiljer effekten av v1-recepten från kod/faktakomplettering. Kontrollen utan receptcache använder samma nya källor och recept.',
 '', '## Ordinarie HTTP, audit och rollback','',
 '| Recept | Läge | HTTP | kr | sekunder | Korgkvalitet |','|---|---|---:|---:|---:|---|']
for x in http_summary:lines.append(f"| {x['recipe']} | {x['mode']} | {x['http_status']} | {x.get('cost','—')} | {x['seconds']} | {x.get('quality','spärrad')} |")
lines+=['','Inga produktlås, extraköp eller handpatchade kandidater. Fyra oförändrade v1-recept med 40/30 g protein och vanlig butiksavgränsning. Positiva resultat sparas via ordinarie PlanStore, läses om och jämförs efter processomstart.',
 'Rollback startar den frysta tidigare implementationen mot samma isolerade PlanStore. Samtliga nya sparade planer ska kunna läsas identiskt. Omräkning av de nyupplösta fallen ska säkert avslås av äldre kod och lämna sparad plan orörd. Exakta resultat i `profile/http-new-recipes-after-integration.json`.',
 '', '## Kvarstående beroenden','',
 'Proteinmålen är oförändrade. Recept med beräknat för lågt protein är inte mängd-/källdatafel. Budgetbegränsade sökningar återstår att optimera; de klassas inte som omöjliga. En större fri receptpool kan ändra den begränsade menysökningens väg och slutkostnad utan att något alternativ bevisats dyrare.',
 'Ingen färsk produktionsbas, Malmö-publicering eller reparation av den historiska Lidl-fixturen ingår. Ingen prisinsamling, schemändring eller ändring av sparad användarprofil. Aktiveringsvillkor och UI-kontroll dokumenteras separat i RELEASE.md.']
(R/'VERIFICATION.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
extra=['','## Tidigare stoppgrupper, oförändrad nämnare','','| Grupp | Antal | Numeriskt efter | Mål + varukorg + audit efter |','|---|---:|---:|---:|']
for group,c in cohorts.items():extra.append(f"| {group} | {c['total']} | {c['numeric']} | {c['passed']} |")
extra+=['','De första stoppen är grupperade efter förekörningen. Alla 84 behålls; senare protein- eller budgetstopp döljs inte. Pris, avrunnen mängd och näringskonflikt är separata: GoGreens belagda 230 g får användas som mängd trots olöst deklarationskonflikt, men dess näring förblir spärrad.',
 '','## Uppmätta delsteg (inklusive underanrop)','','| Körning | Kandidater | Näringsevidens | Numerisk näring | Varukorg | Audit | Receptkontroll |','|---|---:|---:|---:|---:|---:|---:|']
for case in ['before-legacy-public-exact','before-edible-input-v1-public-exact','after-edible-input-v1-public-exact','after-edible-input-v1-public-exact-no-recipe-cache']:
 x=next(p for p in profiles if p['case']==case+'-restored-original');t=x['stage_timings_inclusive']
 extra.append('| '+case+' | '+' | '.join(f"{t[k]['seconds']:.3f}" for k in ['_candidates','_nutrition_evidence','_check_nutrition_uncached','basket_optimize','audit','clean_recipe'])+' |')
extra+=['','Sekunder. Inklusiva delsteg överlappar och får inte summeras. En mätning per konfiguration är ingen statistisk prestandagaranti. Den lokala cachen återanvänder lyckad receptkontroll, men hela körningen är långsammare när fler recept och produkter prövas. Ordinarie sökbudget har inte höjts.']
rebuild_path=P/'rebuild-evidence.json'
if rebuild_path.exists():
 rebuild=load(P/'after-edible-input-v1-public-exact-restored-rebuilt.json');proof=load(rebuild_path)
 summary['rebuild']={'cost':rebuild['cost'],'seconds':rebuild['seconds'],'quality':rebuild['verification'],
  'pool_before':len(proof['original_pool']['ingredients']),'pool_after':len(proof['rebuilt_pool']['ingredients']),**{k:v for k,v in proof.items() if k not in {'original_pool','rebuilt_pool'}}}
 extra+=['','## Separat ordinarie rebuild', '',f"{rebuild['cost']:.2f} kr, {rebuild['seconds']:.3f} s, {rebuild['verification']}. Samma {proof['original_products']} produkter med oförändrade fält, priser och observationer; nyberäknad ekonomisk kandidatpool har {summary['rebuild']['pool_after']} ingredienser mot den frysta artefaktens {summary['rebuild']['pool_before']}. Därmed ändras receptpool/sökväg. Detta är ett separat driftprov, inte besparing för identisk receptpool.",
 'Två rebuilds ger identisk pool och artefaktens återläsning behåller den. Aktiv diskmanifest är oförändrad. Exakt pool före/efter: `profile/rebuild-evidence.json`.']
extra+=['','## Slutlig identitetskontroll och bevisgräns','',
 'Blandningen Soppgrönsaker & potatis och färdigrätten Burek/Börek får inte bli rena råingredienser. Ytterligare granskning av källkategorierna fann ostkex som ost och Blötmat som fisk; ordningen i Ärtor Gula Eko missade även gul ärta-identiteten. Gemensamma produktklass-/ordkombinationsregler rättar detta utan märkes- eller butiksspecialfall. Samtliga 84, de fyra fria profilerna, referenssökningen, HTTP/omstart/rollback och rebuild kördes om efter dessa ändringar; `profile/composite-guard-verification.json` och `profile/identity-guard-verification.json` visar faktisk effekt. Mellanresultaten 428,98 och 448,10 kr är ersatta och räknas inte som verifierade slutresultat.',
 'Kontrollen utan receptcache är en separat tidigare mätning före de sista identitetsspärrarna. Den jämförs med den arkiverade körningen på samma dåvarande kod (144,190 s med cache mot 150,441 s utan), inte som en identisk slutkodsjämförelse. Legacy-regressionen kördes däremot om på slutkoden efter reservvägsspärren.',
 'Ett negativt cache-/universumprov fann också att textmatchning kunde kringgå en definierad semantisk spärr när ingrediensen saknades i det ekonomiska indexet. Detta är rättat i gemensam resolve-kod; explicit identitet eller en separat kvalificerad köpform förväxlas inte med en sådan identitetsspärr. Slutliga omkörningar efter reservvägsrättningen: `profile/fallback-guard-verification.json`.',
 'Importerade referenser och leverantörsfakta som faktiskt användes i kandidatprövning respektive målgodkända recept särredovisas i `source-use.json`. SLV 1225 är importerad reserv; det visade äggköpet använder befintlig produktdeklaration och en separat dokumenterad mängduppskattning.',
 'Slutliga riktade regressioner: `tests-final-complete.xml`. Tidigare prov räknas inte en gång till. Ruff, compileall och JavaScript-syntaxkontroll: `code-checks.json`.']
write(R/'summary.json',summary)
with (R/'VERIFICATION.md').open('a',encoding='utf8') as stream:stream.write('\n'.join(extra)+'\n')
print(json.dumps({'before':summary['baseline'],'after':summary['after'],'stops':summary['first_stops'],'profiles':len(profiles),'http':len(http_summary)},ensure_ascii=False))
