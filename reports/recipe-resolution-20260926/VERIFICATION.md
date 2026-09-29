# Recept- och mängdupplösning, 26 september 2026

Genererad från slutförda körningsfiler. Isolerad historisk prisreplay 24 september; nya officiella fakta hämtade 26 september. Ingen produktionsaktivering.
84-provet använder samma uppskattningsläge och Willys Plus/Lidl Plus som föregående 84-prov. Näringsuppskattningar är ett separat bevarat opt-in. De fria profilerna nedan prövar även exakt läge och ursprunglig medlemskontext.

| Samtliga ursprungliga 84 | Före (v1) | Efter (samma v1) |
|---|---:|---:|
| Beredningsgodkända | 84 | 84 |
| Vidare till näringsprövning | 48 | 84 |
| Numeriskt näringsresultat | 39 | 84 |
| Näringsmål + varukorg + audit | 19 | 33 |

Samtliga 19 tidigare godkända bevarade. 14 nytillkomna godkända recept. Ingen ingrediensmängd, portionsstorlek, instruktion eller v1-receptdefinition ändrad i denna etapp. Originalrecepten kontrolleras separat och finns kvar.

## Första stopp utan dubbelräkning

{'NUTRITION_TARGET_NOT_MET': 22, 'SEARCH_BUDGET': 29, 'PASS': 33}
Samtliga 84 rader, tidigare stopp och nuvarande stopp med konkret skäl: [recipe-first-stops.json](recipe-first-stops.json). Budgetavslag är inte bevis för omöjlighet eller högre pris.

## Fri 15/20-plan

40/30/20 g, max två inköpsställen. Samma frysta bas, inköpsdag och medlemskontext per par. Kalla planner-cachar i ny process; värdmaskinens OS-sidcache är inte tömd. `comparison-inputs.json` verifierar identiska anrop, prisartefakter, testklockor och sökinställningar.

| Körning | kr | sekunder | Kvalitet | Exakta/uppskattade/villkorade rader | Valda av de 84 |
|---|---:|---:|---|---|---|
| after-edible-input-v1-plus-estimated-restored-original | 484.73 | 170.830 | VERIFIED | 16/0/0 | Tomatpasta med lax och gul lök, Gryta med lax, nudlar och vitkål |
| after-edible-input-v1-plus-exact-restored-original | 484.73 | 145.039 | VERIFIED | 16/0/0 | Tomatpasta med lax och gul lök, Gryta med lax, nudlar och vitkål |
| after-edible-input-v1-public-estimated-restored-original | 484.73 | 166.500 | VERIFIED | 16/0/0 | Tomatpasta med lax och gul lök, Gryta med lax, nudlar och vitkål |
| after-edible-input-v1-public-exact-no-recipe-cache-restored-original | 484.73 | 150.441 | VERIFIED | 16/0/0 | Tomatpasta med lax och gul lök, Gryta med lax, nudlar och vitkål |
| after-edible-input-v1-public-exact-restored-original | 484.73 | 146.965 | VERIFIED | 16/0/0 | Tomatpasta med lax och gul lök, Gryta med lax, nudlar och vitkål |
| after-legacy-public-exact-restored-original | 535.25 | 66.180 | VERIFIED | 12/0/0 | inga |
| before-edible-input-v1-plus-estimated-restored-original | 484.73 | 126.433 | VERIFIED | 16/0/0 | Tomatpasta med lax och gul lök, Gryta med lax, nudlar och vitkål |
| before-edible-input-v1-plus-exact-restored-original | 484.73 | 115.123 | VERIFIED | 16/0/0 | Tomatpasta med lax och gul lök, Gryta med lax, nudlar och vitkål |
| before-edible-input-v1-public-estimated-restored-original | 484.73 | 125.231 | VERIFIED | 16/0/0 | Tomatpasta med lax och gul lök, Gryta med lax, nudlar och vitkål |
| before-edible-input-v1-public-exact-restored-original | 484.73 | 116.732 | VERIFIED | 16/0/0 | Tomatpasta med lax och gul lök, Gryta med lax, nudlar och vitkål |
| before-legacy-public-exact-restored-original | 535.25 | 62.161 | VERIFIED | 12/0/0 | inga |

Samtliga jämförbara v1-körningar väljer Coop Online Syd (online_fulfillment) och Willys Lund (online_store). Korgarna har 16 exakta rader; näring redovisas separat med 10 VERIFIED och 5 ESTIMATED. Ingen fysisk butiksprisgiltighet härleds från onlinepriser.
Butiker, kanaler, faktiskt valda recept, separat näringskvalitet och uppmätta delsteg finns i [summary.json](summary.json). Kostnaderna avser hela varukorgar; ingen framtvingad besparing.

## Gemensamma kodrättningar och verkliga källor

- Rödlök och bönor: grov låg källklassning får inte stoppa före den befintliga produktmatcharens identitets-/beredningsprövning. Picklad lök, chips och gul lök förblir egna identiteter. Produktvis före/efter med accepterade och avvisade kandidater: `profile/diagnose-before.json` och `profile/diagnose-after.json`.
- Beredningsform: gravad/gravlax/rimmad klassas i den gemensamma matcharen som beredd produkt, inte rå fisk. Detta fångades i mellankörningens jämförelse med tidigare meny; mellankörningen är arkiverad separat och ersätter inte slutresultaten.
- Blandfärs: bred navigationskategori Fläskfärs/Nötfärs får inte övertrumfa entydigt produktnamn. Produkt-, roll- och beredningsgrindarna kvarstår.
- Dabasimport via befintligt deklarationsregister: exakt kontrollsiffergranskad GTIN, varumärke och konsumentförpackning. Åtta leverantörsblad sparade med hash, faktisk hämtningstid och dokumentversion. Inga priser eller allergenbesked överförs.
- Skånemejerier crème fraiche 32 %, GTIN 7310867003803: källan anger 2 dl och 200 g nettovikt för just denna konsumentförpackning. Deklaration per 100 ml kan räknas på den belagda mängdrelationen. Arlas 2 dl utan belagd gramvikt får ingen sådan omräkning. Ingen generell ml=g-regel och ingen receptomskrivning.
- Bönor: inköpt nettovikt skiljs från explicit avrunnen vikt. Leverantörens tabell blir inte automatiskt en deklaration för avrunnen vara. SLV 3815/3816/3817/3761 används som märkta generiska referenser när identitet, sammansättning och form stämmer och opt-in är aktivt.
- GoGreen svarta bönor, GTIN 7310130009785: kvarstående källkonflikt 112 mot 100 kcal och 7,4 mot 5,6 g protein/100 g. Båda källorna bevaras; posten näringsgodkänns inte genom att välja gynnsammare värde.
- Skalägg: dokumenterad populationsuppskattning cirka 12 % skal (Svenska Ägg, Marknadsrapport 2019, PDF-sida 25). Endast källbelagd kartongvikt får projiceras till uppskattad ätbar mängd, med separat inköpsopt-in. 636 g blir uppskattat 559,68 g ätbart; hela kartonger köps. Styckantal blir inte gram. Kontrollvägning krävs; exakt läge behåller spärren. SLV 1225 är importerad reservreferens; verifierad produktdeklaration prioriteras när tillämplig.
- Begäranslokal cache för oförändrad receptkontroll. Nyckeln innehåller hela receptversionen och mängdenheter, måltids-/kostpolicy, medlemsidentitet och inköpsläge. Ingen global cache och ingen höjning av ordinarie 256-budget.

Se [sources/imported-declarations.json](sources/imported-declarations.json), sparade HTML/PDF/API-svar och `profile/all-84.json` (ingrediensvis faktiskt prövat näringsunderlag). Källa, ursprungliga värden och observationer bevaras.

## Sökning och tid

Referensprov för ursprungliga 20 avslag: {'256': {'cases': 20, 'passed': 0, 'budget_reached': ['Gryta med falukorv, nudlar och vitkål', 'Stekt ris med falukorv och vitkål', 'Tomatpasta med falukorv och gul lök', 'Falukorvpanna med couscous och gul lök', 'Stekt potatis med tofu och morot', 'Ugnsplåt med lax, potatis och gul lök', 'Stekt potatis med fisk och morot', 'Gryta med tofu, nudlar och vitkål', 'Stekt ris med tofu och vitkål', 'Tomatpasta med tofu och gul lök', 'Tofupanna med couscous och gul lök', 'Stekt tofu med potatis och vitkål'], 'seconds': 3.7367}, '4096': {'cases': 20, 'passed': 0, 'budget_reached': ['Stekt ris med tofu och vitkål'], 'seconds': 6.4628}}. Ny planner per budget; samma data och krav. Sökrymden gäller behållna näringsklasser, inte alla matematiskt tänkbara produkter.
Delstegen är uppmätta inklusiva tider och överlappar: kandidatgenerering omfattar närings-/varukorgsprov. De får inte summeras. Separat legacy-körning skiljer effekten av v1-recepten från kod/faktakomplettering. Kontrollen utan receptcache använder samma nya källor och recept.

## Ordinarie HTTP, audit och rollback

| Recept | Läge | HTTP | kr | sekunder | Korgkvalitet |
|---|---|---:|---:|---:|---|
| Mustig gryta på kyckling med potatis och rödlök | exact | 201 | 182.86 | 12.038 | VERIFIED |
| Mustig gryta på kyckling med potatis och rödlök | estimated | 201 | 314.53 | 6.558 | VERIFIED_WITH_ESTIMATES |
| Potatisgratäng med kyckling och gul lök | exact | 201 | 161.92 | 6.732 | VERIFIED |
| Potatisgratäng med kyckling och gul lök | estimated | 201 | 293.59 | 6.075 | VERIFIED_WITH_ESTIMATES |
| Äggsmörgås med tomat | exact | 422 | — | 5.118 | spärrad |
| Äggsmörgås med tomat | estimated | 201 | 120.1 | 6.403 | VERIFIED_WITH_ESTIMATES |
| Bowl med kyckling, nudlar och gul lök | exact | 201 | 101.7 | 11.875 | VERIFIED |
| Bowl med kyckling, nudlar och gul lök | estimated | 201 | 101.7 | 6.232 | VERIFIED |

Inga produktlås, extraköp eller handpatchade kandidater. Fyra oförändrade v1-recept med 40/30 g protein och vanlig butiksavgränsning. Positiva resultat sparas via ordinarie PlanStore, läses om och jämförs efter processomstart.
Rollback startar den frysta tidigare implementationen mot samma isolerade PlanStore. Samtliga nya sparade planer ska kunna läsas identiskt. Omräkning av de nyupplösta fallen ska säkert avslås av äldre kod och lämna sparad plan orörd. Exakta resultat i `profile/http-new-recipes-after-integration.json`.

## Kvarstående beroenden

Proteinmålen är oförändrade. Recept med beräknat för lågt protein är inte mängd-/källdatafel. Budgetbegränsade sökningar återstår att optimera; de klassas inte som omöjliga. En större fri receptpool kan ändra den begränsade menysökningens väg och slutkostnad utan att något alternativ bevisats dyrare.
Ingen färsk produktionsbas, Malmö-publicering eller reparation av den historiska Lidl-fixturen ingår. Ingen prisinsamling, schemändring eller ändring av sparad användarprofil. Aktiveringsvillkor och UI-kontroll dokumenteras separat i RELEASE.md.

## Tidigare stoppgrupper, oförändrad nämnare

| Grupp | Antal | Numeriskt efter | Mål + varukorg + audit efter |
|---|---:|---:|---:|
| Rödlök | 22 | 22 | 9 |
| Nio mängd-/näringsfall | 9 | 9 | 1 |
| Tidigare 20 sökavslag | 20 | 20 | 0 |
| Bönmatchning | 4 | 4 | 0 |
| Crème fraiche | 10 | 10 | 4 |
| Tidigare godkända | 19 | 19 | 19 |

De första stoppen är grupperade efter förekörningen. Alla 84 behålls; senare protein- eller budgetstopp döljs inte. Pris, avrunnen mängd och näringskonflikt är separata: GoGreens belagda 230 g får användas som mängd trots olöst deklarationskonflikt, men dess näring förblir spärrad.

## Uppmätta delsteg (inklusive underanrop)

| Körning | Kandidater | Näringsevidens | Numerisk näring | Varukorg | Audit | Receptkontroll |
|---|---:|---:|---:|---:|---:|---:|
| before-legacy-public-exact | 2.222 | 0.547 | 0.113 | 17.747 | 0.669 | 5.760 |
| before-edible-input-v1-public-exact | 7.015 | 1.743 | 3.408 | 37.162 | 1.434 | 8.410 |
| after-edible-input-v1-public-exact | 13.543 | 7.862 | 7.766 | 47.403 | 1.809 | 7.349 |
| after-edible-input-v1-public-exact-no-recipe-cache | 13.104 | 8.449 | 7.688 | 43.826 | 1.800 | 14.054 |

Sekunder. Inklusiva delsteg överlappar och får inte summeras. En mätning per konfiguration är ingen statistisk prestandagaranti. Den lokala cachen återanvänder lyckad receptkontroll, men hela körningen är långsammare när fler recept och produkter prövas. Ordinarie sökbudget har inte höjts.

## Separat ordinarie rebuild

535.35 kr, 99.592 s, VERIFIED. Samma 37031 produkter med oförändrade fält, priser och observationer; nyberäknad ekonomisk kandidatpool har 42 ingredienser mot den frysta artefaktens 41. Därmed ändras receptpool/sökväg. Detta är ett separat driftprov, inte besparing för identisk receptpool.
Två rebuilds ger identisk pool och artefaktens återläsning behåller den. Aktiv diskmanifest är oförändrad. Exakt pool före/efter: `profile/rebuild-evidence.json`.

## Slutlig identitetskontroll och bevisgräns

Blandningen Soppgrönsaker & potatis och färdigrätten Burek/Börek får inte bli rena råingredienser. Ytterligare granskning av källkategorierna fann ostkex som ost och Blötmat som fisk; ordningen i Ärtor Gula Eko missade även gul ärta-identiteten. Gemensamma produktklass-/ordkombinationsregler rättar detta utan märkes- eller butiksspecialfall. Samtliga 84, de fyra fria profilerna, referenssökningen, HTTP/omstart/rollback och rebuild kördes om efter dessa ändringar; `profile/composite-guard-verification.json` och `profile/identity-guard-verification.json` visar faktisk effekt. Mellanresultaten 428,98 och 448,10 kr är ersatta och räknas inte som verifierade slutresultat.
Kontrollen utan receptcache är en separat tidigare mätning före de sista identitetsspärrarna. Den jämförs med den arkiverade körningen på samma dåvarande kod (144,190 s med cache mot 150,441 s utan), inte som en identisk slutkodsjämförelse. Legacy-regressionen kördes däremot om på slutkoden efter reservvägsspärren.
Ett negativt cache-/universumprov fann också att textmatchning kunde kringgå en definierad semantisk spärr när ingrediensen saknades i det ekonomiska indexet. Detta är rättat i gemensam resolve-kod; explicit identitet eller en separat kvalificerad köpform förväxlas inte med en sådan identitetsspärr. Slutliga omkörningar efter reservvägsrättningen: `profile/fallback-guard-verification.json`.
Importerade referenser och leverantörsfakta som faktiskt användes i kandidatprövning respektive målgodkända recept särredovisas i `source-use.json`. SLV 1225 är importerad reserv; det visade äggköpet använder befintlig produktdeklaration och en separat dokumenterad mängduppskattning.
Slutliga riktade regressioner: `tests-final-complete.xml`. Tidigare prov räknas inte en gång till. Ruff, compileall och JavaScript-syntaxkontroll: `code-checks.json`.
