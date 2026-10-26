# Receptintegration av 800-leveransen, 2026-10-25

**Uppföljning 26 oktober: [hela samlingen är nu integrerad](recipe-integration-all-20261026.md).**
Alla 2 200 källvarianter finns i utvecklingsbiblioteket, totalt 2 462 aktiva
varianter på 934 registrerade baser. [Konkreta kvarvarande köphinder](recipe-integration-all-20261026/HINDER.md)
redovisas separat. Samma budgetjournal fortsätter gälla. Nedanstående
45-variantersrapport bevaras som historiskt etappkvitto.

Första granskade leveransen är **45 aktiva varianter av 18 nya grundrätter
och två befintliga grundrätter**. Utvecklingsbiblioteket växer från 262
varianter/165 baser till **307 varianter/183 baser**. Alla tre måltidstyper
och sex kök ingår. Detta färdigställer en granskad delmängd; hela samlingen
med 2 200 varianter är inte publicerad eller produktkvalificerad.

Leverans: [PR #13](https://github.com/ossebosse/smako/pull/13). Slutligt
recept-/appträd för den frysta kontrollen är commit `81466b1`. Ingen beta,
produktion, scheduler, profiländring eller insamling har aktiverats.
`library_search_policy=legacy` och `library_merge_generations=False` består.
Recepten är AI-författade och inte provlagade.

## Antal och spårbarhet

| Steg | Utfall |
| --- | --- |
| Mottaget original | 800 baskandidater, 2 200 varianter, 160 författarpaket |
| Originalets bytekontroll | Samtliga 166 manifestbundna filer oförändrade |
| Native kontroll med slutkod | 572 kompatibla, 1 626 ingrediensblockerade, två ursprungliga innehållsavslag |
| Innehållsgranskad och aktiv delmängd | 45 varianter från 20 källkandidater |
| Grundrätter efter jämförelse med gamla biblioteket | 18 nya och två befintliga med nya varianter |
| Måltider | 29 middag, tio frukost, sex mellanmål |
| Kök | Grekiskt tio, indiskt sex, italienskt åtta, mexikanskt fem, svenskt åtta, thailändskt åtta |
| Kvar utan import | 2 155: 529 native-kompatibla men inte färdiggranskade, 1 626 ingrediensblockerade |

[summary.json](recipe-integration-800-20261025/summary.json) innehåller exakt
aktiva ID:n, käll-ID → runtime-ID, statisk valbarhet per variant, paketstorlekar
och redaktionella beslut. [all-source-variants.json](recipe-integration-800-20261025/all-source-variants.json)
redovisar alla 2 200 originalvarianter med källfil/rad och ingrediensantal.
[original-after.json](recipe-integration-800-20261025/original-after.json)
är den omkörda ursprungliga intakekontrollen; dess blockerade exit är väntad.
Den granskar avsiktligt originalen och är inte author/validate-rapporten
för de rättade filerna.

Granskat författarunderlag ligger i
`backend/app/data/recipes/reviewed-800-20261025`. Varje `REVIEW.json` binder
beslut till originalfilens SHA-256, radindex, originalradens hash och rättad
rad. Originalens manifest och bytes är bevarade. Tidigare 262 aktiva varianter
kan återställas som separat fryst testläge med det sparade 13-paketsmanifestet;
rå inläsning av alla paket utan versionsurval motsvarar inte denna baslinje.

## Ingredienser och verkligt produktunderlag

Författarvägen kan nu läsa ett uttryckligt granskat vokabulär i
`backend/app/data/ingredients/authoring-20261025.json`. Bootstrap kräver
korrekt namn/form/enhet, implementerade produktkrav, granskningsgrund och
källreferenser. Det skapas inga låtsasrecept och befintliga krav skrivs inte
över. Standardisering får inte ta bort de nya obligatoriska `pack:intake_*`-kraven.

Tolv nya identiteter har registrerats: smör, torr timjan, torr rosmarin,
majsstärkelse, kikärtsmjöl, bakpulver, kokosflingor, valnötter, mandel,
pumpakärnor, solroskärnor och rismjöl. De binds till **23 exakta referenser**
i redan behörigt, bevarat produktunderlag, inklusive snapshot och artefakthash.
Sammansatta varor och namnträffar i en ingrediensförteckning är inte
automatiskt hela inköpsprodukten.

Smör använder befintlig huvudproduktklassificering och avvisar bland annat
Milda/Bregott som smöridentitet. Torra örter får inte bli färska krukörter;
den första referensgenomgången rättades till verkliga torra hyllförpackningar.
Oliver som uttryckligen kräver urkärnad ätlig mängd behöver positivt belägg
för urkärning; negationer såsom ”ej urkärnade” godkänns inte.

Normaliseraren skiljer nu exempelvis gröna/svarta linser, gula ärtor,
klibbigt ris, rimmat fläsk, rökt/varmrökt lax, äggula, kokta ägg,
kondenserad mjölk och puffat ris från bredare delsträngsalias. Entydiga
färsk-koriander- och rädisealias är dokumenterade. Rå koriander i gram är
fortfarande blockerad där en verifierad sådan inköpsgrund saknas.
Äggnudlar får sitt befintliga särskilda produktkrav vid författarimport;
det gamla globala nudelaliaset bevaras för legacy.

Ingen omräkning från hel frukt till ätligt gram, från styck till gram eller
från färsk till torr vara har antagits. Pumpafrön/kärnor, solrosfrön/kärnor,
polenta/majsgryn, korngryn/pärlkorn och matbanan/grön matbanan är inte
automatiska alias. Form, skal, mognad och beredning behöver eget belägg.

Det finns **183 kvarstående kanoniska namn/form-identiteter**. De tidigare
189 jämförs som mängder efter normalisering; tolv nya registreringar betyder
inte att tolv av just dessa gamla identiteter försvinner.
[ingredient-blockers.json](recipe-integration-800-20261025/ingredient-blockers.json)
ger exakt recept-ID, källfil/rad och nästa komplettering per identitet.

| Prioritet | Berörda originalvarianter | Nästa underlag |
| --- | ---: | --- |
| Salladslök, rå ätlig | 139 | Exakt hel vara och verifierad användbar gramvikt/ansning |
| Mynta, rå ätlig | 131 | Färsk form och verifierad blad-/ätlig mängd |
| Koriander, rå ätlig | 111 | Färsk form och användbar gramgrund; torr krydda räcker inte |
| Purjolök, rå ätlig | 111 | Hel förpackning kontra receptets ansade ätliga gram |
| Tamarindpasta | 93 | Exakt pasta, sammansättning och as-sold-mängd |
| Pumpa | 65 | Art/form samt köpt kontra skalad/kärnad ätlig massa |

Effekterna överlappar och summeras inte. Smör berörde 111 originalvarianter
och är nu registrerat; det innebär inte att samtliga 111 kan publiceras.
Övriga ingredienser, innehåll och användarens produktkrav kan fortfarande stoppa dem.

## Innehåll, tider och gemensamma grundrätter

De sex ursprungliga standardiseringsfelen gällde lång förberedelse, och de
två ursprungliga innehållsavslagen gällde kalla sluträtter med rå animalisk
insats. Den granskade delmängden behåller blötläggning, jäsning, avrinning och
kylning i tids-/stegkedjan. `estimated_minutes` kan nu uttrycka total tid upp
till 2 880 minuter, i linje med befintliga total-/väntetidsfält i API/UI.
Aktiv tid, väntetid och användarens filter behåller sina egna gränser.
Recept över 180 minuter passerar inte ett uttryckligt 180-minutersfilter.

Kall kyckling- respektive laxsallad har korrekt upphettningsmetod och
komponentkedja; rå kyckling/lax är inte omdöpt till färdiglagad inköpsvara.
Rå-animaliegrinden omfattar också bland annat lamm, skaldjur och äggula.
Dietklassificeringen täcker det utökade sortimentet. Skaldjur har en egen
intern kategori och räknas inte som fisk i fördelningskrav; de publika
fyra fördelningsvalen ändras inte.

Övriga dokumenterade rättningar omfattar entydiga mängdenheter från redan
angivna g/ml, kycklingbröstkrav för roulader, vitböns-/urkärningskrav,
broccoli-/vitlökssteg, verklig väntan för deg och fyllning samt separata
uppkoknings-, ugns- och ångförberedelser. En utlovad men saknad tomatsås
tas bort från titeln på ostfyllda paprikor. Ingen fyllnadsingrediens läggs
till för att nå ett filter.

Portionsskalningen bevarar den utfärdade källportionens exakta innehåll.
Ökad tillagning utgår från författat portionsantal, och blötläggning får inte
misstas för skalbar upphettning. Alla 45 aktiva varianter valideras och
serialiseras/återläses vid 1, 2, 4 och 12 portioner.

Författarens sex namngivna likhetspar har jämförts med instruktioner och
mängder; deras skilda huvudsakliga processer dokumenteras i maskinrapporten.
Jämförelse mot det gamla biblioteket avvisar tre ytterligare ny-basanspråk:

- Grekiska avlånga färsbiffar med tomat är tre varianter av befintliga
  `smako-greek-keftedes`, med samma diversitetsfamilj.
- Thailändsk kall lax-/jordnötssallad är en variant av
  `smako-thai-sour-noodle-salad`, med samma diversitetsfamilj.
- Bulgur-/linsfrukost behöver behandlas som två framtida varianter av
  `smako-breakfast-lentil-carrot-porridge`; dessa har inte importerats.

Originalet har fortsatt 800 mottagna baskandidater. Efter dessa tre avvisade
anspråk återstår högst **797 nya baskandidater**, inte ett bevis på 797 unika
nya rätter. Tretton bredare likhetsgrupper återstår för kulinarisk granskning.
Redan granskade laxbiffar är skilda från gammal ugnsbakad hel laxfilé genom
hackning, bindning och stekning av biffar, inte endast namn eller tillbehör.

För alla original återbekräftar Smakos räknare **294 avvikelser** från
variantintervallen och **sju middagsbaser utan någon variant inom 10–15**.
Exakta bas-ID:n och avvikelser finns i `summary.json`. `variant_id` är inte
`dinner_level`. Nuvarande standardfilter ändras inte. I denna leverans
passerar 14 av 29 middagsvarianter standardens statiska ingrediensfilter;
alla 16 frukost-/mellanmålsvarianter passerar sina motsvarande statiska val.
Detta ger 30 statiska träffar, inte 30 färdigkvalificerade inköpslistor.

## Vanlig import och historik

`author -> validate -> diff -> import -> prepare` har körts genom den
befintliga CLI:n. Första paketet innehåller 37 varianter och andra åtta.
Tredje/fjärde paketet bevarar samgrupperingens mellanversion och rättar dess
familjer i version 1.0.1. Fyra separata tidigare bas-ID:n och fyra
mellanversioner har återkallats med vanlig `revoke`, utan ändring av gamla
hashade filer. Totalt 53 nytillkomna historiska poster, 45 aktiva och åtta
återkallade. Det finns **17 aktuella + sju historiska generationer = 24**.

| Paket | Standardiserade bytes | Publicerade bytes |
| --- | ---: | ---: |
| Första | 514 397 | 659 199 |
| Andra | 78 545 | 104 300 |
| Samgruppering 1.0.0, återkallad | 64 453 | 81 615 |
| Samgruppering 1.0.1 | 64 477 | 81 575 |

Alla ligger under 16 MiB. Återimport av samtliga fyra paket lämnar manifestet
byteidentiskt och återupplivar inte återkallade ID:n. Nytt gränsprov visar
att generation 129 avvisas före paket-/manifestskrivning, medan idempotent
återimport vid gränsen fortfarande fungerar. Inga historiska referenser
tas bort och 128-gränsen höjs inte.

Author-/validate-/diff-/import- och återkallelsekvitton ligger bredvid
maskinrapporten. Gemensam förberedelse inkluderar historiska recept för
sparade referenser; antalet sådana objekt är inte aktiva sökkandidater.
Slutlig förberedelse redovisas i `prepare-current.json`.

## Produktinventering och selektiva användarprov

Samma frysta, tidigare behöriga partiella Malmöunderlag används: 89 458
produkter och 71 138 faktarader, prisklocka
`2026-10-23T06:00:02.869273+00:00`. Detta är historisk återspelning, inte ett
påstående om färska priser den 25:e. Prisartefaktens SHA-256 är
`06cbf0b12e619f09dd3709b808916d1c74676859d246ad72f74d52d0e6d91857`;
faktabytesens SHA-256 är
`914327f31e06b4c81840c3c8f79959babf8da67e1041255714514ee5a3c13516`.
Källscopet är oförändrat, utan ny insamling eller fabricerade fakta.

[product-inputs-current.json](recipe-integration-800-20261025/product-inputs-current.json)
inventerar gemensamt 201 mängd-/kravscope för 70 namn/form-nycklar över
alla 45 varianter med vanliga resolverns källa-, datum-, form-, mängd- och
produktgrindar. 23 varianter har individuellt lösbara inköpsinsatser, 22 har
minst en produktblockerare. Fulla gemensamma korgar och näring/eko/allergier
följer inte automatiskt av enskilda produktträffar. Varje scope har exakta
kandidat-/butiks-/snapshotreferenser eller explicit avslag.

Faktastatus redovisas per verklig produkt: näringsenhet/beredning,
fullständig ingrediensförteckning, kontrollerade allergener, animalie- och
ekostatus samt konflikter. Saknat är fortsatt saknat. Selektiva prov nedan
ställer inga närings-/eko-/allergikrav; näring har status `NOT_REQUESTED`.

Fyra uttryckligt låsta enmåltidsfall använder vanlig planerare, exakt
gemensam checkout/audit, riktig privat `PlanStore.create` och ägarbunden
återläsning av hela svaret. Varje oberoende fall har en ny ägare och revision
0; gamla revisions- och ägargrindar har inte försvagats. Dessa är funktionella
replayprov efter gemensam inläsning, inte veckosökning eller HTTP-/UI-latens.

| Låst fall | Pris, kr | Plan + audit/save/återläsning, s |
| --- | ---: | ---: |
| Kycklingroulader, utökad, fyra portioner | 270.36 | 22.11 |
| Kikärtsmjölsfrukost, enkel | 109.15 | 9.52 |
| Grekisk vitlöks-/potatisemulsion, enkel | 103.46 | 8.88 |
| Linscrepes, enkel, lång blötläggning | 125.83 | 8.95 |

Samtliga fyra har godkänd audit och identiskt fullständigt svar efter
återläsning. De tre tidigare provade priserna är exakt oförändrade. Nytt
linsfall saknar tidigare prisjämförelse. Gemensam källinläsning tar
45.92 s; inklusive initiering 50.18 s. Hela inventeringen och fyra
prov tar 117.30 s, en observation. Tabellens provtider är efter denna gemensamma
inläsning och får inte presenteras som första användarvalets sluttid.

Kall gemensam receptförberedelse tar 25.62 s, en observation, med
649 innehållsfiler/425,687 bytes och 671 historiskt inkluderande
receptobjekt per portionsnivå 1/2/4/12. Detta är 307 aktiva varianter, inte
671 aktiva sökkandidater. Den kompakta rapporten binder hela rårapportens
hash och beroendekarta; råkopian finns lokalt under `.local/recipes/intake-evidence`.


## Tester, resursgräns och gemensam budget

122 riktade offlineprov passerar för intake, import, privata artefakter och
referenssökning, plus tre budgetprov för tidigare V2-förbrukning, avbruten
journal och misslyckat prov utan nollställning av förbrukningen. Nya regressioner omfattar namn-/formseparation, smör/färska
örter/urkärning, diet/skaldjur, kall rå animalie, lång total-/väntetid,
portionsskalning, manifestgräns och delad upprepningsgräns både mellan
simple/extended och mellan nytillkommen variant/befintlig grundrätt.
Ruff och compileall körs på ändrade Pythonfiler och berörda paket.

Ordinarie full CI inklusive Chromium/WebKit passerar på runtime `81466b1`
i [körning 40241622213](https://github.com/ossebosse/smako/actions/runs/40241622213).
Slutleveransens checkar finns på [PR #13](https://github.com/ossebosse/smako/pull/13/checks).
De första CI-körningarna hittade verkliga regressioner i smörklassificering
och det globala nudelaliaset samt felaktiga testantaganden om en enda
publicering/att hela biblioteket fortfarande var 262. Dessa har rättats med
bevarad legacy-fixtur och separat fryst referens. En senare tillagd
urkärningstestfixtur saknade obligatorisk källidentitet; fixturen rättades.
Samgrupperingens diversitetsfamilj rättades efter befintligt regressionsprov.
Inga produkt-, checkout- eller ägargrindar har sänkts för gröna prov.

Mätningarna körs seriellt i Windows med faktisk Pythonprocess bunden till
två CPU och Windows-jobbets hårda 3 GiB commitgräns. Detta skiljer sig från
tidigare Linux cgroup/RSS; inga Linux/Windows-tidskvoter eller p95 beräknas.
De första tre wrapperförsöken följde fel process när Store-Python delegerade.
Deras minnesvärden är markerade ogiltiga och används inte som belägg;
alla tider belastar ändå budgeten. Rättad körning ansluter den verkliga
interpretern till jobbet och har stoppgräns. Även misslyckade hjälpverktygs-
och ägarrevisionsförsök, förberedelse och omtag är debiterade.

[budget.json](recipe-integration-800-20261025/budget.json) debiterar totalt
**1073.9377 s = 17.90 minuter av gemensamma 120 minuter**.
**6126.0623 s = 102.10 minuter återstår för samma fortsatta etapp/V2**.
Tidigare V2-förbrukning vid start var noll; den äldre avslutade V1-etappens
117,13 minuter var en annan avslutad etapp. Ingen journal har återställts.
Alla reservationer är stängda och inga mätarbetare fortsätter. Största
verifierade privata commitpeak är 1.102 GiB, working-set-peak
1.120 GiB; båda redovisas som Windowsmått.
Målet 2,5 GiB klaras i dessa små prov; versionsöverlappning och större
sökningar är inte därmed minneskvalificerade.


## Kvarvarande arbete och V2

Detta är recept-/ingrediensleveransen före stora V2-skalprov. Någon
`smako-prepared-personal-v2`-sökväg har inte införts. De verkliga granskade
recepten är förberedda genom befintliga gemensamma artefakter och den gamla
262-baslinjen är separat verifierbar. Inga 1 000-/5 000-prov eller 2 200
individuella veckoplaneringar har startats.

V2-uppdragets vertikala API-/jobbväg, aktuell-bibliotekssökning utan historisk
återspelning, deadline genom inre korg-/näringsloopar och audit/save, 1..N/alla
butiker utan full delmängdsmaterialisering, uppskjutna kompletteringar och
prisversionslivscykel återstår. De ändras inte indirekt av denna import.
Gamla A–E-resultat är historisk evidens och inte nya mätningar på denna kod.
Särskilt E:s 46 produktavslag behöver fortsatt exakt produkt-/faktadiagnos;
det gamla blockerade E får inte räknas som en snabb färdig meny.

Nästa avgränsade steg är att granska de 529 strukturellt kompatibla men
ointegrerade varianterna i sammanhängande paket, prioritera de högsta exakta
ingrediensluckorna i det befintliga tillåtna underlaget och slutföra de 13
öppna likhetsgrupperna. Använd sedan dessa verkliga recept i V2:s små
checkout-/butiksorakel och få villkorade användarprov. Fortsätt samma
budgetjournal; varken nästa rapport eller nästa uppdrag skapar ytterligare
120 minuter. HTTP GET/browser, nya personliga val, verkligt prisversionsbyte
och 30–60-sekundersmålet är fortfarande omätta för en ny V2-väg.
