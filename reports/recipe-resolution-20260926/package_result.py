"""Freeze completed results; preserves every earlier release evidence file."""
import json, hashlib, subprocess, xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, UTC
R=Path(__file__).parent;ROOT=R.parents[1]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_bytes())
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf8')
s=load(R/'summary.json');assert s['preserved_previous_passes']==19
proof=load(R/'profile/fallback-guard-verification.json');assert proof['all_84_repeated'] and proof['http_repeated']
comparisons=[]
for membership in ['public','plus']:
 for mode in ['exact','estimated']:
  label='edible-input-v1-'+membership+'-'+mode
  b=load(R/('profile/before-'+label+'-restored-original.json'));a=load(R/('profile/after-'+label+'-restored-original.json'))
  bi=load(R/('profile/before-'+label+'-inputs.json'));ai=load(R/('profile/after-'+label+'-inputs.json'))
  assert a['status']==b['status']=='PASS' and a['request']==b['request']
  assert bi['artifact_sha256']==ai['artifact_sha256'] and bi['frozen_test_clock']==ai['frozen_test_clock']
  assert bi['search']==ai['search'] and a['input_products']==b['input_products']
  comparisons.append({'case':label,'same_request':True,'same_price_artifact':bi['artifact_sha256'],'same_clock':bi['frozen_test_clock'],
   'same_search':bi['search'],'before_facts':b['facts_version'],'after_facts':a['facts_version'],
   'cache':'Fresh application process per case; cold planner caches. Host OS page cache not reset.'})
write(R/'comparison-inputs.json',comparisons)
freeze={}
for folder in ['backend/app','grocery_data/app','grocery_data/scripts']:
 for p in (ROOT/folder).rglob('*'):
  if not p.is_file() or '__pycache__' in p.parts:continue
  name=p.relative_to(ROOT).as_posix();old=R/'baseline-code'/name
  if not old.exists() or digest(old)!=digest(p):freeze[name]={'before':digest(old) if old.exists() else None,'after':digest(p)}
write(R/'final-code-freeze.json',freeze)
commands=[['py','-3.12','-m','ruff','check',*[p for p in freeze if p.endswith('.py')],'backend/tests/test_recipe_resolution.py'],
 ['py','-3.12','-m','compileall','-q','backend/app','grocery_data/app'],['node','--check','backend/app/static/personal.js'],
 ['git','diff','--check','--',*freeze]]
checks=[]
for command in commands:
 r=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf8');checks.append({'command':command,'exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
write(R/'code-checks.json',checks);assert all(x['exit']==0 for x in checks)
tests=ET.parse(R/'tests-final-complete.xml').getroot().find('testsuite').attrib
assert tests['errors']==tests['failures']==tests['skipped']=='0'
write(R/'tests-summary.json',{'final_regression':tests,'command_files':sorted({x.attrib['classname'].replace('.','/')+'.py' for x in ET.parse(R/'tests-final-complete.xml').findall('.//testcase')}),'note':'Earlier focused/intermediate runs retained, not summed as unique tests.'})
preserved={}
for name in ['recipe-preparation-20260926','personal-offers-20260926']:
 p=ROOT/'reports'/name/'PACKAGE.json';prior=load(p);rows=[]
 for path,sha in prior['evidence_hashes'].items():
  target=ROOT/path;row={'path':path,'exists':target.exists(),'unchanged':target.exists() and digest(target)==sha};rows.append(row)
 assert all(x['unchanged'] for x in rows),name
 preserved[name]={'package_sha256':digest(p),'results':rows}
write(R/'preservation-check.json',preserved)
before=s['baseline'];after=s['after'];profile=next(x for x in s['profiles'] if x['case']=='after-edible-input-v1-public-exact-restored-original')
header=f'''# Smako – 26 september 2026: mängd- och näringskoppling efter beredningsstödet

[Verifierade körresultat](../reports/recipe-resolution-20260926/VERIFICATION.md),
[alla 84 första stopp](../reports/recipe-resolution-20260926/recipe-first-stops.json),
[kandidater före/efter](../reports/recipe-resolution-20260926/candidate-review.json),
[separat aktiveringsunderlag](../reports/recipe-resolution-20260926/RELEASE.md).

Inaktiv kandidat. Oförändrade v1-recept: beredning {before['preparation']}→{after['preparation']},
näringsprövning {before['nutrition_attempted']}→{after['nutrition_attempted']}, numeriskt resultat
{before['numeric']}→{after['numeric']}, mål + varukorg + audit {before['passed']}→{after['passed']}.
Alla 19 tidigare godkända bevarade. Ingen ny receptversion eller ingrediensändring denna etapp.

Gemensam matchare prövar identitet före grov låg källklassning. Officiell Dabasimport
är bunden till kontrollsiffergranskad GTIN, varumärke och konsumentförpackning.
Crème fraiche har en produktspecifik belagd ml/g-relation, ingen generell densitet.
Avrunnen vikt skiljs från nettovikt och från näringstabellens beredningsgrund.
Fyra nya SLV-referenser importerade med råvärden och verkliga svarstider.
Ägg använder dokumenterad skalandel endast som separat opt-in-uppskattning;
verifierad produktnäring prioriteras. Pris, receptversion och näringskvalitet hålls isär.
Gravad fisk, burek, soppgrönsaksblandning och ostkex får inte bli rena råingredienser.
Gula ärtor är egen identitet och källkategorin Blötmat spärras som djurfoder.
En definierad identitets-/formspärr kan inte kringgås av textmatchning när en
ingrediens saknas i det ekonomiska kandidatindexet. Uttryckliga köpformer och
varor utanför taxonomin behåller sin separata, kontrollerade reservväg.

Fri 15/20, 40/30/20, max två butiker: {profile['cost']:.2f} kr,
{profile['seconds']:.3f} s, {profile['quality']}. Detaljer om fyra lägen, separata
legacy-/rebuildprov, valda recept och tidsprofil finns i verifieringen. Rebuildens
nya kandidatpool ändrar receptutbudet och är ingen jämförbar besparingsmätning.

Första stopp: {json.dumps(s['first_stops'],ensure_ascii=False)}.
Referenssökning 4096 för de gamla 20 avslagen ger inga nya godkända; se exakt
budgetstatus i rapporten, ingen global omöjlighets- eller dyrare-slutsats.

Ordinarie HTTP, checkout/audit, sparning, processomstart och explicit rollbackmål
är verifierade. Rollback till närmast föregående v1-beredningsleverans läser
nya sparade planer; omräkning avslås säkert och planen bevaras. Äldre versioner
utan preparation-kontrakt är inte verifierade rollbackmål. Visuell desktopkontroll
av uppskattningsmärkning och mängdinstruktioner dokumenterad separat.

Historisk prisreplay 24 september; nya mängd-/näringskällor 26 september.
Ingen prisobservation föryngrad. Ingen produktionsaktivering, användarprofil- eller
schemaändring. Färsk komplett bas, Malmö-publicering och historisk Lidl-fixture
kvarstår separat. GoGreen svarta bönors motstridiga näringsvärden kvarstår spärrade.

<!-- recipe-resolution-20260926:end -->

'''
handoff=ROOT/'docs/HANDOFF.md';current=handoff.read_bytes();baseline=(R/'baseline-HANDOFF.md').read_bytes()
marker='<!-- recipe-resolution-20260926:end -->'
if marker in current.decode('utf8'):current=current.decode('utf8').split(marker+'\n\n',1)[1].encode('utf8')
assert current==baseline,'HANDOFF changed outside this delivery; merge explicitly'
handoff.write_bytes(header.encode('utf8')+baseline)
(R/'README.md').write_text('''# Recept- och mängdupplösning

Läs **VERIFICATION.md** och **summary.json** för faktiska slutförda körningar.
**recipe-first-stops.json** innehåller alla 84 recept, utan dubbelräkning.
**candidate-review.json** innehåller produktvisa före/efterbeslut.
**RELEASE.md** är separat, inaktivt aktiverings- och rollbackunderlag.

`profile/` är körbevis; `sources/` är verkliga källsvar och importerade fakta.
Underkataloger med `intermediate` är ersatta mellankörningar, inte slutresultat.
`baseline-code/` fryser föregående implementation; ändra inte den.
`PACKAGE.json` binder slutkod, testkod, dokumentation och körbevis med SHA-256.

Slutproven kördes på Python 3.12 i privat native-behållare utan nät, separat
PlanStore, frysta prisartefakter och uttrycklig historisk testklocka. Rapporternas
HTTP-data har egna request-ID:n och tider; körningarna är inte aktuella priser.
Ingen produktion eller aktiv schemaläggning ingår. Kör inte remote.initialize
igen; den skapade isoleringen och tidigare releaser ska bevaras.
''',encoding='utf8')
test_files=sorted({x.attrib['classname'].replace('.','/')+'.py' for x in ET.parse(R/'tests-final-complete.xml').findall('.//testcase')})
package={'created_at':datetime.now(UTC).isoformat(),'status':'verified_inactive_recipe_resolution_candidate','production_activation':False,
 'changed_application_files':freeze,'tests':tests,'test_code_hashes':{p:digest(ROOT/p) for p in test_files},
 'handoff_previous_sha256':digest(R/'baseline-HANDOFF.md'),'handoff_sha256':digest(handoff),
 'previous_packages':{k:v['package_sha256'] for k,v in preserved.items()},
 'evidence_hashes':{p.relative_to(ROOT).as_posix():digest(p) for p in sorted(R.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.name!='PACKAGE.json'},
 'open':['nutrition search budgets','GoGreen conflicting nutrition','fresh full production base','Malmo complete publication','historical Lidl fixture','rollback before preparation v1 not verified']}
write(R/'PACKAGE.json',package)
print(json.dumps({'application_files':len(freeze),'tests':tests['tests'],'preserved_evidence':{k:len(v['results']) for k,v in preserved.items()},'package_sha256':digest(R/'PACKAGE.json')},ensure_ascii=False))
