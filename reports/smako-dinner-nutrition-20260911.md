# Smako: spårbar näring för en begränsad middagsmeny

2026-09-11. Release `personal-v2-dinners-20260911c`, appkod `7b15c05`.
**PARTIAL: tre tillagade middagar fungerar; det begärda femmiddagsfallet gör det inte.**
R4/R5 är fortsatt partiella. Denna rapport ersätter inte tidigare V2-/OIDC-rapport.

## Faktisk utgångspunkt och produktval

Workspace började på dokumentationscommit `b20d7cd`, appkod `e1c0db1`.
Serverns current-länk och appimage pekade på `personal-v2-qualified-20260911b`.
Historiskt underlag och rapporter ändras inte retroaktivt.

I den föregående frukostacceptansen angav formuläret generiska **ost** och
**mjölk**; blåmögelost/getmjölk var inte uttryckligen valda. Befintlig matchare
gav båda hög identitetspoäng. Sammansatta svenska ord passerade identitetsmatchen,
medan specialproduktens avgränsning byggde på hela ord. Det var alltså en konkret
för bred produktmatchning, inte ett särskilt användarval. Se
[beslutsspår](personal-v2-dinners/matching-before.json).

`product_semantics.py` avvisar nu get-/fårmjölk för vanlig mjölk och blå-/mögelost,
brie, camembert och chèvre för vanlig ost. Explicit valda specialprodukter förlorar
inte sin identitet. Näringsmappningen avvisar dessutom oförenlig råvaruform,
marinad/tillsatt vatten, fel fiskstyckning, annat ris och andra nudlar än den
granskade referensens. Ingen ny stor ontologi har införts.

Det gamla 81,96-kronorsfallet ska därför inte längre räknas som korrekt acceptans.
Dess strikta mjölkbehov saknar nu ett kvalificerat vanligt alternativ med rätt
enhet. Separat strikt A2 visar att produktbaserad beräkning fortfarande fungerar.

## Riktad produktberikning och faktisk källa

Prioritering utgick från vanliga behov i receptpoolen och sparade godkända råsvar.
Tio distinkta Coop-produkter valdes: två gula lökar, en potatis, två morötter,
två tomater, två vitkålsprodukter och en färs. Olämpliga former/enheter filtrerades
bort före anrop. [Urval](personal-v2-dinners/detail-selection.json).

En avgränsad begäran gick genom befintlig godkänd
`CoopOnlineCatalogClient.fetch_products_by_id`, kontext **730400**, befintlig
åtkomstkonfiguration och gemensamt driftlås. Klientens schemavalidering stoppade
försöket med `CoopSchemaError`. Ingen fortsatt hämtning efter stoppet.
**10 distinkta produkter efterfrågade, 0 accepterade detaljdokument, 0 nya
produktfakta och 0 nya prisobservationer.** Feltypen, inte känsliga svar, sparades
i [resultatet](personal-v2-dinners/detail-result.json). Den exakta felorsaken
inom schemavalideringen är inte fastställd av detta resultat.

Alternativet som faktiskt fyllde näringsluckan är den nedan frysta generiska
referenskällan med uttryckligt användarval. Det är inte produktdeklarationer.
De fem tidigare verifierade Coop→ICA-faktakopplingarna kvarstår; inga nya sådana
kopplingar eller färska priser skapades. Willys-task/relay, ICA OWN och
kataloginsamlingens omfattning är oförändrade.

## Livsmedelsverket: åtkomst, licens och omfattning

[Officiell Swagger](https://dataportal.livsmedelsverket.se/livsmedel/swagger/v1/swagger.json)
var åtkomlig utan konto eller betalning. Den anger API v1.0.0 och
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.sv).
Källhänvisning: **Livsmedelsverkets Livsmedelsdatabas**, med respektive dataversion.
Swagger/API-info är sparade i evidenskatalogen. En senare hämtning av den mänskliga
webbsidan gav 403; ingen kringgång gjordes.

En metadataförteckning användes för manuell identifiering, inte en full hämtning
av näringskatalogen. Den ligger inte i den delade rapporten. Appens frysta fil
`backend/app/data/nutrition/slv-20260911.json` har **30 uttryckliga mappningar**,
31 råa livsmedelsdokument (en extra granskad färskandidat) och 13 dokument för
beredningsgranskning. Nio specifika beredningskopplingar används: åtta kokta och
en stekt lax. Dataversioner är 2026-06-29–2026-07-01; batchen hämtades
2026-09-11T16:32:34.727295Z. Originalvärden, enhet, 100 g-referens, beredningsstatus,
käll-ID/URL, version och transformationshistorik sparas. SLV-ID är aldrig GTIN.

## Användarval och beräkningskontrakt

På **Mina val → Tillåt spårbara näringsuppskattningar** gör användaren ett aktivt
val före generering. Gamla profiler får `false`; inget tyst reservvärde används
när läget är av. UI skiljer produktdeklaration, generisk referens,
dokumenterad beredningsuppskattning och ej kontrollerat krav. Varje relevant
ingrediens visas med källa och beräkningsgrund under detaljer.
Texten är **”Gränser uppfyllda enligt beräkningen”**, ingen garanti om den
faktiska färdiglagade matens exakta innehåll.

En granskad tillagad SLV-komponents makron per 100 g omräknas till den dokumenterade
råa ätbara insatsen: `tillagat värde × dokumenterad hel slutbatch / rå insats`.
För ris 2481→2515 används 85 g ris, 264,01 g tillagat ris och 1,4 g salt i
källans beräknade batch. Saltets fyra makron är källbelagt noll. Dess massa behövs
för att lösa upp källans per-100-g-nämnare; salt läggs inte till appens recept.
**WaterFactor 17,2 multipliceras aldrig med hela råvikten.** Bara en huvudråvara
och detta makroneutrala salt tillåts i den aktiva komponenttransformen.

För kvalificerad kompatibel produktdeklaration används den livsmedelsspecifika
förändringskvoten från samma råa/tillagade referenspar. Annars kan uttryckligt
tillåten generisk referens användas. Motsägelsefull deklaration, fel enhet eller
fel form ersätts inte av bekvämare generiska värden. En partiell deklaration
kan användas för dess kända efterfrågade värden; saknade efterfrågade värden
godkänns inte. Okänt blir aldrig noll. Redan tillagad/avrunnen referens får ingen
andra tillagningsjustering. Mjölk i ml omräknas inte godtyckligt till g.

Köpta hela förpackningar bestämmer kassakostnaden. Receptets använda ätbara mängd
bestämmer näringen, inklusive skafferibidrag. Kasserade delar måste vara borttagna
före den uppmätta receptmängden. Förpackningsöverskott räknas inte som uppäten mat.
Detta är fortfarande en uppskattning av motsvarande råvaruform/beredning;
produktens faktiska vattenhalt, styckning och tillagningsförlust kan avvika.

Generiskt skafferi kräver separat bekräftat livsmedel och rå/torr/avrunnen form
via befintligt skafferiformulär. Namn, vikt i gram, betydelsefull fetthalt och
referens måste stämma. Bekräftelsen ändrar inte lager eller historiska köp.

Tillagad portionsvikt har fortfarande otillräckligt underlag. Den beräknas inte
från en påhittad slutvikt och blockerar inte ett oberoende makrokrav. Generiska
referenser bevisar **varken eko eller allergenfrihet**. Eko räknas fortsatt över
matinköpets faktiska kostnad efter rabatt, utan skafferi/icke-mat/avgifter;
utan nya matinköp behandlas andelen uttryckligen som ej tillämplig.

## Fördeklarerade acceptansprofiler och begränsningar

[Profiler](personal-v2-dinners/profiles.json) sparades före respektive sökning.
A var den tidigare strikta frukosten. B: fem middagar, fyra portioner, Balanserad,
max två butiker, blandkost, inga medlemskap, inga smak-/allergifilter, explicit
uppskattningsläge, minst 20 g protein och högst 800 kcal per portion. Detta är
funktionstestparametrar, inte kostråd. C lade till 500 g bekräftat torrt ris i
skafferiet. D provade separat eko 25 %. E kombinerade B med eko 25 %.
Separata mindre fall A2/B4/B3/C4/C3/E4/E3 deklarerades; inga B-gränser ändrades
tyst eller i efterhand för att kalla B lyckat.

**B/C/E med fem middagar samt fyramiddagsförsöken: SEARCH_BLOCKED.** Alla nio
ingrediensrader i respektive lyckad tremiddagsmeny har beräkningsunderlag, men
en hel större varierad meny hittades inte. Åtta granskade varma receptmallar
har bara två kolhydratkällor (ris/äggnudlar) och två tillagningsmetoder
(kokning/stekt lax). Balanserads befintliga maxantal och likhetsregler behålls.
En genomgång av kombinationerna inom just dessa åtta mallar gav ingen giltig
fyr-/femkombination. Det är inte ett bevis att alla tänkbara menyer är omöjliga.

Många äldre middagar har ”lite matolja”, oklara avrunna mängder eller saknad
berednings-/förlustgrund och är därför inte kvalificerade. De åtta nya mallarna
är uttryckligen enkla, okryddade och utan tillsatt fett. Det är en begränsad
användbar delmängd, inte generell näringstäckning för vanliga middagar.

Ytterligare granskning av färs 10 %→SLV 2101 stoppades av en nödvändig
pepparpost 6661 som gav HTTP 404. Hasselbackspotatis 4128 innehåller potatis 230,
smör 29 och ströbröd 188; hela ingrediens-/faktor-/produktkedjan är inte
kvalificerad. Ingendera kopplingen aktiverades för att passera acceptansen.
Nästa konkreta arbete är att kvalificera en tredje kolhydrat och tillagningsmetod
med fullständiga mängder/komponentunderlag, samt lösa den godkända Coop-klientens
detaljschemastopp. Ingen ny full crawl eller privat åtkomst behövs för att
återuppta just dessa avgränsade luckor.

## Testning, versioner och drift

405 distinkta berörda regressionstestfall har passerat: 400 i samlad körning och
fem tillkommande. Efter sista kodändringen passerade 80 direkt berörda tester.
Oförändrad verifiering återanvändes; inga goldens ändrades. Ruff,
Python 3.12 compileall och JavaScript-syntaxkontroll passerade.
Evidens: `regression.xml`, `final-focused.xml`, `runtime.json`, `rollback.json`.

Tester täcker fel form/enhet, saknat värde, dubbel tillagningsjustering,
receptmängd kontra överskott/extras, aktivt val, bibehållna allergi-/ekokrav,
produktspecifikation, generiskt skafferi, köp/replay/förbrukning och historik,
fakta-/mappnings-/policycache och oförändrad ekonomi utan nya krav.
Frysta konsumentprov förbjuder socketanslutning; serverimage kördes dessutom
med `--network none`, riktiga monterade pris-/faktadata och normal planner.
Noll externa konsumentanrop; referenser hämtas aldrig vid generering/sökning.

Två relevanta regressionsfel hittades före aktivering: JSON-null i sparad
PlanRequest kunde tappa Balanserads implicita variationsregler; personlig
planering återställer nu presetens regler efter rundtur medan uttryckliga
numeriska överstyrningar består. LF/CRLF kunde ge olika referensversioner;
versionen använder nu kanoniskt JSON-innehåll. Båda har egna regressionstester.

Basfallet utan nya krav behöll exakt samma meny och **244,49 kr**.
Kall tid 16,102→14,477 s, varm 0,875→0,717 s. Enskilda mätningar med normal
miljövariation, inte en prestandaförbättringsgaranti; ingen prestandaomskrivning.

Aktivering skedde under gemensamt driftlås efter backup **20260911T171809Z**.
120 tidigare planrevisioner är hashbevarade; databasens integritet är OK.
Prismanifest och scheduler är oförändrade. Ingen användardata har raderats.
Rollbackimage `personal-v2-dinners-20260911c-rollback` kan läsa nya modeller och
blockerar ändring som den äldre motorn inte säkert kan utföra; offlineprov ger
503 på sådan ändring. Ingen databasrestore krävs för approllback.
Aktiveringsverktyget och evidensen sparar inte miljöhemligheter i denna rapport.

Appimage: `sha256:36d570521a5bcac20cdd307c059759e8e503d0a682d088b45de072a4341c6dfb`.
Prisversion: `price-universe:9ab6c58a4934c0a253e037c724d58fdcc8c84b484d26a87d2027be087e17b929`.
Faktaversion: `retained-catalog-facts-v2:a4283c8ba8ae5590d365808377efa00e2c6b2e2ae48d52f46d78fbddac756622`.
Referensversion: `slv-component-input-v1:af45feecd442a3217c11ca8550f486136368ebc68157d4506d7bb029b44da3ec`.
Personlig policy/resultat: `personal-policy-v2-3` / `personal-v2-3`.

Samma frysta **449 produkt-ID:n** före/efter: **83 ingrediensdeklarationer,
46 källstödda ekologiska produkter, 78 kompletta produktmakrodeklarationer**.
71 rader har en möjlig granskad tillagningsreferens före full recept-/kravkontroll.
Detta är inte 71 nya produktdeklarationer eller allergenkontroller.
[Jämförbar täckning](personal-v2-dinners/coverage.json).

R1 hårda allergier är fortsatt DATA_BLOCKED när komplett underlag saknas.
Animaliskt eko och sammansatta produkter har fortsatt begränsad källklassning.
OIDC-konfiguration/verklig kontoacceptans är separat och orörd. Fysisk iPhone
har inte testats. R6/R9 har inte byggts om.

## Verifierade referensidentiteter

| SLV-ID | Officiell beskrivning | Bekräftad form |
|---|---|---|
| slv:2481:dry | Ris långkornigt okokt | torr/okokt |
| slv:2475:dry | Ris basmati okokt | torr/okokt |
| slv:2477:dry | Ris jasmin okokt | torr/okokt |
| slv:845:dry | Pasta okokt | torr/okokt |
| slv:870:dry | Nudlar äggnudlar okokta | torr/okokt |
| slv:831:dry | Couscous | torr/okokt |
| slv:4457:raw | Potatis rå | rå |
| slv:289:raw | Morot | rå |
| slv:344:raw | Lök gul | rå |
| slv:4947:raw | Lök röd | rå |
| slv:370:raw | Vitkål | rå |
| slv:325:raw | Broccoli | rå |
| slv:364:raw | Tomat | rå |
| slv:422:canned_with_liquid | Tomat krossad konserv. m. lag | konserv med vätska |
| slv:905:ready | Tofu fast | som såld/ätfärdig |
| slv:1173:raw_skinless_breast | Kyckling bröstfilé rå u. skinn | rå bröstfilé utan skinn |
| slv:1255:raw_farmed | Lax odlad Norge fjordlax rå | rå odlad lax |
| slv:1246:raw_cod | Torsk rå | rå torsk |
| slv:951:raw | Nöt färs rå fett 10% | rå |
| slv:2499:raw | Blandfärs rå nöt 50% gris 50%  | rå |
| slv:881:dry | Kikärtor torkade | torr/okokt |
| slv:884:dry | Linser torkade | torr/okokt |
| slv:3815:drained | Kikärtor konserv. u. lag | kokt och avrunnen |
| slv:909:ready | Sojasås | som såld/ätfärdig |
| slv:2189:ready | Rapsolja | som såld/ätfärdig |
| slv:7266:ready | Kokosmjölk fett ca 18% | som såld/ätfärdig |
| slv:7139:ready | Crème fraiche lätt fett 13% | som såld/ätfärdig |
| slv:97:ready | Ost hårdost fett 31% | som såld/ätfärdig |
| slv:123:ready | Mjölk fett 3% berikad | som såld/ätfärdig |
| slv:1975:ready | Salt m. jod | som såld/ätfärdig |

## Fullständiga fungerande acceptansfall

Samtliga priser är frysta fulla förpackningsköp via normal optimering, inga produktlås eller hårdkodade produktval. Willys är online_store; Coop är Online Syd, onlinefulfillment, inte verifierat fysiskt hyllpris. Exakta ID:n, snapshots och fältvisa näringskällor finns i [fryst resultat](personal-v2-dinners/frozen.json).

### A2: 30.38 kr

Butiker: Coop Online Syd. Ekoandel: 0.00 %. Allergi: NOT_REQUESTED.

| Måltid | Portioner | Protein g/portion | kcal/portion | Beräkningsstatus |
|---|---|---|---|---|
| Ostsmörgås | 2 | 21.44 | 460.60 | VERIFIED |

Receptmängder, totalt före tillagning:

- Ostsmörgås: 160 g bröd, 120 g ost.

| Butik / produkt (ID) | Hela paket | Köpt | Radsumma kr | Paketöverskott |
|---|---|---|---|---|
| Coop Online Syd / Liba Bröd Grov (`dd144109147842e693defe7f0a57496a`) | 1 × 340 g | 340 g | 10.88 | 180 g |
| Coop Online Syd / Riven ost Cheddar (`ec402b9982f54404928326c81d6da22f`) | 1 × 150 g | 150 g | 19.50 | 30 g |

### D: 55.73 kr

Butiker: Coop Online Syd, Willys Lund. Ekoandel: 26.32 %. Allergi: NOT_REQUESTED.

| Måltid | Portioner | Protein g/portion | kcal/portion | Beräkningsstatus |
|---|---|---|---|---|
| Gryta med tofu, nudlar och morot | 2 | Ej kontrollerat | Ej kontrollerat | NOT_REQUESTED |

Receptmängder, totalt före tillagning:

- Gryta med tofu, nudlar och morot: 200 g tofu, 175 g nudlar, 250 g morot, 200 ml kokosmjölk, 150 g gul lök.

| Butik / produkt (ID) | Hela paket | Köpt | Radsumma kr | Paketöverskott |
|---|---|---|---|---|
| Coop Online Syd / Kokosmjölk Eko (`5f020932b6ed469c89854d9f8a72f6a0`) | 1 × 200 ml | 200 ml | 14.67 | 0 ml |
| Willys Lund / Lök Gul i Påse Klass 1 (`3456afb249914f9f828becbb6fb6c1b7`) | 1 × 1000 g | 1000 g | 9.90 | 850 g |
| Willys Lund / Morötter Klass 1 (`396b94bd623e425ca20aacbb4e773767`) | 1 × 500 g | 500 g | 9.90 | 250 g |
| Willys Lund / Äggnudlar (`532179034f824670b172c5a334a983e9`) | 1 × 250 g | 250 g | 9.36 | 75 g |
| Willys Lund / Naturell Tofu Fast Vegansk (`75ac3f3ac5de46b2bf0a8289f7aa038f`) | 1 × 200 g | 200 g | 11.90 | 0 g |

### B3: 426.52 kr

Butiker: Willys Lund. Ekoandel: 0.00 %. Allergi: NOT_REQUESTED.

| Måltid | Portioner | Protein g/portion | kcal/portion | Beräkningsstatus |
|---|---|---|---|---|
| Kokt kyckling med ris och morötter | 4 | 41.97 | 492.79 | ESTIMATED |
| Kycklingsoppa med äggnudlar och vitkål | 4 | 47.63 | 506.77 | ESTIMATED |
| Stekt lax med ris och morötter | 4 | 37.54 | 613.78 | ESTIMATED |

Receptmängder, totalt före tillagning:

- Kokt kyckling med ris och morötter: 600 g kyckling, 320 g ris, 600 g morot.
- Kycklingsoppa med äggnudlar och vitkål: 600 g kyckling, 320 g nudlar, 600 g vitkål.
- Stekt lax med ris och morötter: 600 g lax, 320 g ris, 600 g morot.

| Butik / produkt (ID) | Hela paket | Köpt | Radsumma kr | Paketöverskott |
|---|---|---|---|---|
| Willys Lund / Kycklingfilé 2-delad Frysta (`72a507fdf27d4c5cba6471cadbe618f3`) | 2 × 800 g | 1600 g | 151.22 | 400 g |
| Willys Lund / Laxfilé i Bit Refreshed (`b234bfd8c318416eacd0fb00b5b12fc7`) | 2 × 400 g | 800 g | 189.08 | 200 g |
| Willys Lund / Morötter Klass 1 (`65e5b718b02a43e59baba00b4752945d`) | 2 × 1000 g | 2000 g | 19.80 | 800 g |
| Willys Lund / Äggnudlar (`532179034f824670b172c5a334a983e9`) | 2 × 250 g | 500 g | 18.72 | 180 g |
| Willys Lund / Långkornigt Ris (`2585686a5060440bab52cfd9ad963f67`) | 1 × 1000 g | 1000 g | 19.90 | 360 g |
| Willys Lund / Vitkål Strimlad Klass 1 (`72ef4a1dd8e84ef6b7ff348c7201cdbf`) | 2 × 400 g | 800 g | 27.80 | 200 g |

### C3: 419.98 kr

Butiker: Willys Lund. Ekoandel: 0.00 %. Allergi: NOT_REQUESTED.

| Måltid | Portioner | Protein g/portion | kcal/portion | Beräkningsstatus |
|---|---|---|---|---|
| Kokt kyckling med ris och morötter | 4 | 41.97 | 492.79 | ESTIMATED |
| Kycklingsoppa med äggnudlar och vitkål | 4 | 47.63 | 506.77 | ESTIMATED |
| Nudelpanna med stekt lax och vitkål | 4 | 43.21 | 627.76 | ESTIMATED |

Receptmängder, totalt före tillagning:

- Kokt kyckling med ris och morötter: 600 g kyckling, 320 g ris, 600 g morot.
- Kycklingsoppa med äggnudlar och vitkål: 600 g kyckling, 320 g nudlar, 600 g vitkål.
- Nudelpanna med stekt lax och vitkål: 600 g lax, 320 g nudlar, 600 g vitkål.

| Butik / produkt (ID) | Hela paket | Köpt | Radsumma kr | Paketöverskott |
|---|---|---|---|---|
| Willys Lund / Kycklingfilé 2-delad Frysta (`72a507fdf27d4c5cba6471cadbe618f3`) | 2 × 800 g | 1600 g | 151.22 | 400 g |
| Willys Lund / Laxfilé i Bit Refreshed (`b234bfd8c318416eacd0fb00b5b12fc7`) | 2 × 400 g | 800 g | 189.08 | 200 g |
| Willys Lund / Morötter Klass 1 (`65e5b718b02a43e59baba00b4752945d`) | 1 × 1000 g | 1000 g | 9.90 | 400 g |
| Willys Lund / Äggnudlar (`532179034f824670b172c5a334a983e9`) | 3 × 250 g | 750 g | 28.08 | 110 g |
| Willys Lund / Vitkål Strimlad Klass 1 (`72ef4a1dd8e84ef6b7ff348c7201cdbf`) | 3 × 400 g | 1200 g | 41.70 | 0 g |

Faktiskt skafferilager före/efter generering: **500 g torrt ris**. Planen reserverar 320 g; disponibelt 180 g. Ingen inköpsbokföring sker. Menyn byter tredje rätt till nudelpanna; kostnadsskillnaden mot B3 är därför **inte** en samma-meny-besparing.

### E3: 480.05 kr

Butiker: Coop Online Syd, Willys Lund. Ekoandel: 50.54 %. Allergi: NOT_REQUESTED.

| Måltid | Portioner | Protein g/portion | kcal/portion | Beräkningsstatus |
|---|---|---|---|---|
| Kokt kyckling med ris och morötter | 4 | 41.97 | 492.79 | ESTIMATED |
| Kycklingsoppa med äggnudlar och vitkål | 4 | 47.63 | 506.77 | ESTIMATED |
| Stekt lax med ris och morötter | 4 | 41.73 | 648.11 | ESTIMATED |

Receptmängder, totalt före tillagning:

- Kokt kyckling med ris och morötter: 600 g kyckling, 320 g ris, 600 g morot.
- Kycklingsoppa med äggnudlar och vitkål: 600 g kyckling, 320 g nudlar, 600 g vitkål.
- Stekt lax med ris och morötter: 600 g lax, 320 g ris, 600 g morot.

| Butik / produkt (ID) | Hela paket | Köpt | Radsumma kr | Paketöverskott |
|---|---|---|---|---|
| Coop Online Syd / Laxfilé Eko (`f323565af92a45e7a06866da8445c999`) | 3 × 250 g | 750 g | 242.61 | 150 g |
| Willys Lund / Kycklingfilé 2-delad Frysta (`72a507fdf27d4c5cba6471cadbe618f3`) | 2 × 800 g | 1600 g | 151.22 | 400 g |
| Willys Lund / Morötter Klass 1 (`65e5b718b02a43e59baba00b4752945d`) | 2 × 1000 g | 2000 g | 19.80 | 800 g |
| Willys Lund / Äggnudlar (`532179034f824670b172c5a334a983e9`) | 2 × 250 g | 500 g | 18.72 | 180 g |
| Willys Lund / Långkornigt Ris (`2585686a5060440bab52cfd9ad963f67`) | 1 × 1000 g | 1000 g | 19.90 | 360 g |
| Willys Lund / Vitkål Strimlad Klass 1 (`72ef4a1dd8e84ef6b7ff348c7201cdbf`) | 2 × 400 g | 800 g | 27.80 | 200 g |

Verifierad ekologisk varukostnad 242,61 kr / matinköp 480,05 kr = **50,54 %**, mot fördeklarerat minimum 25 %. Samma meny som B3; den ekologiska laxprodukten har sin egen deklaration. Övriga generiska referenser skapar ingen ekostatus.

## Verklig HTTPS-acceptans efter aktivering

Chromium och WebKit passerade via verkliga formulär på https://beta.smako.nu/personal.
B5:s femmiddagsfel visades, följt av uttryckligt nytt val av tre middagar och
B3:s 426,52 kr. Skafferiformuläret krävde bekräftat torrt ris; C3:s 419,98 kr
och oförändrat faktiskt saldo kontrollerades. Sparat aktivt val, gästägarisolering,
A2/D/E3 via normal API, 24 px text och mobilbredd utan horisontellt överflöde
kontrollerades. Inga JavaScript-fel. Närings-/källvyn granskades visuellt.
[Resultat och skärmbilder](personal-v2-dinners/https/results.json).
Emulerad mobil är inte verklig iPhone-acceptans.

Efter proven finns 130 revisioner; alla 120 äldre är fortfarande hashbevarade.
[Driftverifiering](personal-v2-dinners/deployment.json).
Alla tio ändrade appfiler inklusive referensdata hashmatchar mellan workspace,
current-release och körande container. [Hashbevis](personal-v2-dinners/source-hashes.json).
Normal produktsökning anger noll leverantörsanrop; inga externa källor anropas
för näringsreferenser. Hypotetiska allergiprofiler används enbart i syntetiska
regressionsprov, aldrig i delade produktfakta eller PriceUniverse.
