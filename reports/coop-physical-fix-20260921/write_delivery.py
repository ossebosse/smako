"""Build review evidence from completed runs; no network or production writes."""
import hashlib
import importlib.metadata
import importlib.util
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
result = json.loads((HERE / 'final-acceptance-v2/result.json').read_bytes())
live = json.loads((HERE / 'final-live-v2/coverage.json').read_bytes())


def write(name, value):
    (HERE / name).write_text(value, encoding='utf-8')


rows = []
quarantine = []
for s in sorted(result['stores'], key=lambda x: x['store'], reverse=True):
    observed = datetime.fromisoformat(s['observed_at']).astimezone(ZoneInfo('Europe/Stockholm')).isoformat()
    rows.append(f"| {s['name']} ({s['store']}) | {s['ads']} | {s['extracted_variants']} | {s['accepted']} | {s['rejected']} | {s['own_projected']} | {s['price_universe']} | {observed} |")
    products = json.loads((HERE / f"final-acceptance-v2/{s['store']}-extracted.json").read_bytes())['products']
    by_id = {p['external_product_id']: p for p in products}
    for d in s['qualification']['decisions']:
        if not d['blockers']:
            continue
        # Keep the whole decision to retain the contract's native ID spelling.
        quarantine.append({'store': s['store'], 'source_url': s['official_url'], 'observed_at': s['observed_at'],
                           'source_hash': s['source_hash'], 'decision': d})
write('quarantine.json', json.dumps(quarantine, ensure_ascii=False, indent=2))

coverage = '''# Slutlig täckning – Coop fysisk offers_only

Verklig insamling 21 september 2026 kl. 09:44 Europe/Stockholm. Två uttryckligt
valda butiker ur befintlig inventering; detta är inte en kommunfullständig körning.
Kommunernas okända butikstillhörigheter är oförändrade. Ingen produktionsaktivering.

| Butik | Annonsgrupper i källan | Extraherade varianter | Radgodkända | Karantän | Isolerad OWN | Isolerat PU | Observerat Stockholm |
|---|---:|---:|---:|---:|---:|---:|---|
''' + '\n'.join(rows) + f'''

Totalt 78 annonsgrupper / 491 källvarianter, 112 radgodkända och 379 i karantän.
Kategoridubbletter och gruppförälder räknas inte en gång till. Bulltoftas DOM
hade 55 penningpriskort men källan 56 grupper: den extra gruppen innehåller
74 varianter med 20% rabatt utan verifierad prisgrund. Dessa finns kvar som
extraherade prisuppgifter och i nämnaren, inte som köppris på 20 kr.

Full parserläsning: 135/135 respektive 356/356 utan parserfel. Efter köpvalidering
44/135 = 32,59% och 68/356 = 19,10%. Fullsnapshot är därför fortsatt `broken`,
inte godkänd mot 95%. Tröskel och nämnare är oförändrade. Endast det uttryckliga
partiella radkontraktet publicerades i isolerad OWN, med alla bortfall synliga.
Ingen aktiv beta-PriceUniverse har ändrats. Isolerat ID: `{result['price_universe_id']}`.

Tidigare audit 20 september hade 70 textkort och **0 verifierat nya köpklara
importer**. Den hade andra kampanjer; 70 får inte jämföras direkt med dagens
491 variantposter. `before-parser-comparison.json` kör i stället gamla parsern
offline mot exakt dagens råsvar: 22 respektive 55 kort, med tappade datum och
utan strukturerad variantidentitet. Det är inte ett mått på aktiva betapriser.

De 112 posterna är nya i denna tomma isolerade databas, inte bevisligen 112 nya
eller billigare marknadserbjudanden. Den sista lokala ombyggnaden återanvände
samma råsvar och förnyade inga observationer. Tidigare försökskataloger behålls
som historik; `final-live` misslyckades på Bulltoftas nya schemafält och är inte
slutacceptansen. Slutkodens underlag är `final-live-v2` och `final-acceptance-v2`.

## Kvarstående hinder

Antal per orsak överlappar; summera inte orsaker som om de vore olika poster.
Varje exakt berört käll-/variant-ID, råreferens och felorsak finns i
`quarantine.json` och fullständiga råfält i butikens `*-extracted.json`.

'''
for s in result['stores']:
    coverage += f"### {s['name']}\n\n"
    coverage += '\n'.join(f'- `{k}`: {v} varianter.' for k, v in s['reasons'].items()) + '\n\n'
coverage += f'''Okänd pant avser källtexten ”Pant tillkommer.” utan belopp; varken noll eller
standardpant antas. Osäkra gruppblandningar och ungefärliga/viktbaserade köp
behåller källpriset men går inte in i köpunderlaget. Fem enstaka styckvaror
saknar befintligt korrekt paketköpsstöd. Procentraderna kan dessutom ha samma
styckkontraktsproblem; därför överlappar antalen.

Den sena schemakontrollen hittade `isPercentageDiscount` och `isPil` i verklig
Bulltofta-data. Procentflaggan bevaras och hindrar penningprisförväxling.
`isPil` finns på 13 varianter i nio annonser; betydelsen är inte säkert verifierad.
Alla 13 köpblockeras, varav nio annars hade godkänts. Därför är slutantalet
68, inte tidigare preliminära 77. Källa och priser finns kvar för granskning.

## Checkout, audit och receptnytta

Sex verkliga köpfall kördes: pasta 300 g / 15 kr och nötfärs 500 g / 59,90 kr
(Coop-medlem, max 3 förpackningar/hushåll) klarar både checkout och audit i
båda butikerna. Mjöl: exakt två 2 kg-förpackningar för 26 kr, ingen tillåten
singelförpackning för 13 kr. Priset och mängden stämmer, men audit säger nej
på låg semantisk säkerhet för ingrediensklassificeringen. Hindret har inte
rundats. Se de sex `proof-*.json` i slutacceptansen.

Matcher→checkout→audit för pasta verifierades även i verkliga källfixturtester,
liksom medlemskap av/på, maxgräns över alias och ogiltiga kampanjdagar.
PriceUniverse har 31 varianter med hög taxonomisk säkerhet (9 + 22); detta är
**inte** 31 verifierat näringsgodkända receptprodukter. Ingen full näringsbegränsad
15/20-körning gjordes i denna avgränsade rättning och ingen besparing hävdas.

Färsk insamling: {live['runtime_seconds']} s. Slutkodens isolerade ombyggnad och
sex checkout/audit-fall: {result['runtime_seconds']} s. Python 3.12 på befintlig
Windowsmiljö, befintlig Playwright Chromium. Serverruntime är inte verifierad
av detta prov. Ingen bildanalys, modellkostnad, ny prenumeration eller driftändring.
'''
write('COVERAGE.md', coverage)

write('EXAMPLES.md', '''# Konkreta före/efterexempel

Kontrollerat 21 september 2026 cirka 09:44 Europe/Stockholm. Alla nedanstående
aktuella annonser har källdatum **21–27 september 2026**. Före = föregående
parser körd offline på samma sparade färska svar; efter = slutkodens isolerade
import. Detta är inte en jämförelse av två aktiva produktionsmanifest.

| Butik / annons | Före | Efter | Officiell källa |
|---|---|---|---|
| Flöjtvägen: Coop färsk pasta fettuccine, 300 g, 15 kr | Kortpris läst men datum null och ingen exakt strukturerad variantkoppling | Publikt kampanjköp, exakt 300 g-variant, ordinarie null, 21–27/9; 1 förpackning kostar 15 kr, audit PASS | [Flöjtvägen](https://www.coop.se/butiker-erbjudanden/coop/coop-flojtvagen/), annons `1297-42361-1140058`, variant `7340011392347` |
| Bulltofta: John’s Selection (Irland) nötfärs 20%, 500 g, 59,90 kr | Medlemspris och maxtext i kortet, men datum null och utan exakt strukturerad variant | Medlemsavtal med max 3 förpackningar/hushåll, 21–27/9, ordinarie null. Ett paket 59,90 kr; två 119,80 kr. Medlemskap av och fyra paket blockeras; audit PASS för tillåtet köp | [Bulltofta](https://www.coop.se/butiker-erbjudanden/coop/coop-bulltofta/), annons `1267-36480-1138433`, variant `7392055078800` |
| Flöjtvägen: Arla Bregott, 350–500 g, 39,90 kr | Gruppkort med förpackningsintervall; synlig extra villkorstext tappad | Sex uttryckliga varianter med respektive 350/500 g, medlemskap, datum och ”Gäller ej ekologiskt”; bevarat gemensamt köpavtal. I isolerat PU, inte påstått valt i meny | [Flöjtvägen](https://www.coop.se/butiker-erbjudanden/coop/coop-flojtvagen/), titel ”Bregott” |

Prisroller: Bulltoftas aktuella Glitterset 199 kr blev tidigare ordinarie
`regular_price=199`. Nu bevaras källans `Regular Price` och köppris 199 i ett
datumbegränsat SourceOffer, medan ordinarie pris är null. Köp blockeras av
styckkontrakt och oklara `isPil`, inte felaktigt globalt godkänt. Historiska Shot
33 kr från 20/9 har också en verklig regression: fel ordinarie roll rättad,
men ingen påhittad kampanjperiod och ingen aktuell import från gammalt kort.

Vetemjöl från båda butikerna: **2 för 26 kr, 2 kg/st**. Gruppvillkoret och
datumen går hela vägen till korrekt checkout, men audit stoppar receptköpet
på låg taxonomisk säkerhet. Ordinarie restpris förblir null.

Individuella publika annons-URL:er saknas i denna källa. Länkarna går till rätt
fysisk butik; titel och exakt käll-ID anges för återfinnande. Ovanstående
variantnummer behandlas som opaka Coop-ID:n, inte som verifierade GTIN.
''')

write('README.md', '''# Coop-rättning: slutleverans 21 september 2026

Kod och isolerad verifiering slutförda på `areas/municipality-audit-20260920`.
Ingen produktionsaktivering. [Täckning och exakta bortfall](COVERAGE.md),
[före/efterexempel](EXAMPLES.md), [separat releaseförslag](RELEASE.md).
Kontraktet finns i `docs/coop_physical_offers.md`.

112 kvalificerade varianter nådde isolerad OWN och PriceUniverse: Flöjtvägen
44, Bulltofta 68. 379 av 491 varianter är i karantän. Totalt 78 annonsgrupper.
Fyra av sex konkreta checkout/audit-fall PASS; mjölets två köp prissätts rätt
men har semantisk auditblockerare. Inget påstående om komplett täckning,
näringsgodkänd slutmeny eller besparing.

## Körkommandon (PowerShell, från den separata arbetskopian)

```powershell
$env:PYTHONPATH='backend;.'
$env:PYTHONIOENCODING='utf-8'
py -3.12 grocery_data/scripts/collect_coop_physical_offers.py --inventory reports/municipality-offers-20260920/coop-audit.json --store-id 3839 --store-id 3815 --output reports/coop-physical-next-live
py -3.12 reports/coop-physical-fix-20260921/verify_isolated.py --input reports/coop-physical-next-live/sources --output reports/coop-physical-next-acceptance
```

Output-katalogerna måste vara nya; befintligt underlag skrivs aldrig över.
Första kommandot gör begränsade verkliga publika anrop. Det andra använder
oförändrade råsvar, utan nät och utan föryngrade observationer. Vid senare
replay kan priser korrekt vara för gamla/utgångna; använd då testfixturerna med
explicit testklocka för historiska regressioner, inte som färsk acceptans.

Befintlig Playwright Chromium och Python 3.12 krävs. Inga nya beroenden.
`ICA_FLYER_VISUAL_COMMAND_JSON` används inte. Coop Online-allowlist och Primat
berörs inte. Inventeringsfilen och butik-ID:n är parametrar för den begränsade
kontrollen, inte en ny hårdkodad upptäcktslista. Inga kommuner gissas.

## Verifiering

184 tester PASS (26,46 s). Efter en beteendeoförändrad lintjustering kördes
berörda 22 tester igen (10,40 s), därefter isolerad slutacceptans mot exakt
samma färska källhashar (3,457 s). Ruff och compileall PASS på ändrade Pythonfiler.
Tester omfattar verkliga källfixturer, prisroller, procent/reference/ordinarie,
medlemskap, variantundantag, gruppköp/restmängd, köpgränser över alias, pant
okänd, tidsvillkor, fel butik, gemensamt schemafel, ICA och Coop Online.

```powershell
py -3.12 -m pytest grocery_data/tests/test_coop_physical_structured.py backend/tests/test_coop_physical_pipeline.py grocery_data/tests/test_coop_connector.py grocery_data/tests/test_coop_browser_integrity.py grocery_data/tests/test_coop_offers_acceptance.py grocery_data/tests/test_coop_online_catalog_parser.py grocery_data/tests/test_offer_rows.py grocery_data/tests/test_ica_area_offers.py grocery_data/tests/test_municipality_area.py backend/tests/test_own_provider.py backend/tests/test_own_provider_grocery_data_contract.py backend/tests/test_ica_area_offer_provider.py backend/tests/test_ica_conditional_checkout.py backend/tests/test_verified_offer_deposit.py -o addopts='' -q
```

Slutbevis: `final-live-v2/coverage.json`, dess oförändrade `sources/`,
`final-acceptance-v2/result.json`, `price-universe.json` och sex `proof-*.json`.
Föregående kods jämförelse: `before-parser-comparison.json`. Alla mellanresultat
ligger kvar för spårbarhet, inklusive Bulltoftas initiala schemastopp.
`baseline.json` och `prework.tar.gz` bevarar läget före denna rättning.
`incremental.patch` och `delivery-manifest.json` avgränsar leveransen från
ärvda ändringar; `preservation-check.json` redovisar originalets integritet.
''')

# Read-only preservation proof against the pending ICA worktree/release.
inherited = json.loads((ROOT / 'reports/municipality-offers-20260920/inherited-work.json').read_bytes())
original = Path(inherited['source'])
bad = [name for name, sha in inherited['files'].items()
       if hashlib.sha256((original / name).read_bytes()).hexdigest() != sha]
manifest = json.loads((original / 'reports/ica-structured-release-20260920/release-source-manifest.json').read_bytes())
vendor = {}
for package, dist in [('bs4', 'beautifulsoup4'), ('soupsieve', 'soupsieve')]:
    directory = Path(importlib.util.find_spec(package).origin).parent
    for p in directory.rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts:
            vendor['release-vendor/' + package + '/' + p.relative_to(directory).as_posix()] = p.read_bytes()
    meta = importlib.metadata.distribution(dist)
    for f in meta.files:
        if '.dist-info/' in str(f):
            vendor['release-vendor/' + str(f)] = meta.locate_file(f).read_bytes()
release_bad = []
for name, sha in manifest['files'].items():
    data = vendor[name] if name.startswith('release-vendor/') else (original / name).read_bytes().replace(b'\r\n', b'\n')
    if hashlib.sha256(data).hexdigest() != sha:
        release_bad.append(name)
proof = {'original_worktree': str(original), 'inherited_files_checked': len(inherited['files']),
         'inherited_mismatches': bad, 'pending_release_files_checked': len(manifest['files']),
         'pending_release_mismatches': release_bad, 'production_mutations': False,
         'hash_policy': 'inherited exact bytes; original release LF-normalized text and exact vendor bytes'}
write('preservation-check.json', json.dumps(proof, indent=2))
assert not bad and not release_bad, proof
print(json.dumps(proof))
