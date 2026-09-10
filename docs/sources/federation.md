# Federerat grocery price universe

Senast verifierat: **2026-08-25**

## Accepterad source-strategi

| Kedja | OWN coverage | Basket-primary | OWN-roller | Policy |
| --- | --- | --- | --- | --- |
| Willys | `FULL_CATALOG` | OWN | katalog + offers | `ALLOW` |
| ICA | `OFFERS_ONLY` | Primat/licensierad | offers + registry-enrichment | `ALLOW` |
| Coop | `FULL_ONLINE_CATALOG` | OWN | regional onlinekatalog + fysiska offers | `REVIEW` för full crawl |
| City Gross | `FULL_ONLINE_CATALOG` | OWN | onlinekatalog + offers | `REVIEW` |
| Hemköp | `FULL_ONLINE_CATALOG` | OWN | onlinekatalog + offers | `REVIEW` |
| Lidl | `OFFERS_ONLY` | Primat/licensierad | nationell/regional offers-feed | `ALLOW` |

Fyra kedjor är därmed oberoende av Primat för full basket i sina verifierade
contexts: Willys, City Gross, Hemköp och Coop. ICA och Lidl kräver fortsatt en
bred extern källa. Primat finns kvar som explicit fallback för Coop men används
inte tyst när en healthy/fresh OWN-snapshot är aktiv.

`SourcePolicy` verkställs centralt före run, snapshot och source request:
`BLOCK` nekas alltid och `REVIEW` kräver explicit operator-opt-in. City Gross
och Hemköp kräver dessutom en exakt store-allowlist. Coops fullkatalog kräver
`COOP_ALLOW_FULL_CRAWL=true` och exakt context-allowlist `730400`; den separata
fysiska offerinsamlingen förblir lågvolym. Den dagliga collectorn
schemalägger inte City Gross för Lund, eftersom ingen fysisk butik eller
verifierad fulfillment-context finns där. Hemköp Lund planeras däremot som
separata exakta store-contexts: Brunnshög `4224` och Karhögstorg `4123` har
promoterade fulla OWN-snapshots.

## Coop-slutklassning

**COOP OWN = `FULL_ONLINE_CATALOG`; basket-primary = OWN.**

Den accepterade entityn är regionala/online fulfilment-contextet **Coop Online
Syd** (`730400`), inte en fysisk butik. Den aktiva Lund-relationen är Stora Coop
Lund physical `2696` -> pickup `257611` -> context `730400`. Mårtenstorget har
ingen verifierad pickup-länk, och `730400` räknas som ett enda köpcontext oavsett
hur många pickup points som kan betjäna det. Alla priser presenteras som
**onlinepriser**, aldrig som verifierade hyllpriser.

| Mätetal | Resultat |
| --- | ---: |
| Terminal categories / pages | 748 / 822 |
| Raw category rows / unika produkter | 12 380 / 11 175 |
| Giltig GTIN | 99,50 % |
| Priscoverage | 100,00 % |
| Package quantity | 99,20 % |
| Resolved purchase model | 99,28 % |
| Recipe coverage >=1 / >=3 / >=5 | 48/48 / 45/48 / 39/48 |
| Representative basket | 13/13 complete |
| Offline replay | 11 175 produkter, 0 nätverksanrop |

Snapshot `851d317e88ce422b90d80d26ca1ebb2b` är promoterad. Fysiska
Coop-erbjudanden behåller sin separata OWN/OFFERS-lineage. Primat/licensierad
data är endast strategideklarerad fallback och måste aktiveras explicit med
`fallback_used=true` i resultatets provenance.

## Lidl-slutklassning

**LIDL = `OFFERS_ONLY`; full basket capable = nej.**

Den publika, oautentiserade produkt-/erbjudandeytan gav exakt 421 deklarerade,
råa och unika rader över 9/9 sidor, med noll dubbletter. Detta är ett aktuellt
eller kommande publiceringsset, inte ett bevis på Lidls permanenta lokala
sortiment.

Den accepterade OWN-identiteten är därför en enda sanningsenlig regional
kontext, `public-default-region` / Sverige. Priserna tillskrivs inte de två
upptäckta Lund-butikerna eller de sju Malmö-butikerna. Fysiska butiker behåller
adress och koordinater som separata contexts.

| Mätetal | Resultat |
| --- | ---: |
| Produkter/prisobservationer | 421 / 421 |
| Sidor / requests | 9 / 10 (inklusive context-probe) |
| HTTP-fel / 429 / challenge | 0 / 0 / 0 |
| Runtime | 13,235 s |
| Raw payloads / bytes | 10 / 3 044 486 |
| Parser / quarantine | 421 / 0 |
| Explicit raw EAN / checksum-valid GTIN | 277 / 260 (61,76 % av alla rader) |
| Source package quantity | 233 / 421 (55,34 %) |
| Canonical package quantity | 237 / 421 (56,29 %) |
| Resolved purchase model | 266 / 421 (63,18 %) |
| Member / multibuy / percent | 37 / 16 / 51 |

Replay av samma raw data gav 421 produkter och samma pris-/promotionprojektion
med noll nätverksanrop och noll browserstarter. Parser-v2 lade endast till
checksum-validerad GTIN från det uttryckliga `gridbox.meta.ean`-fältet. Schema-
break, BROKEN candidate, last-known-good och connector-lokal replay-reparation
är regressionstestade.

Se även [Lidl source discovery](lidl.md), [Lidls robots.txt](https://www.lidl.se/robots.txt)
och [Lidls officiella Lund-butiker](https://www.lidl.se/s/sv-SE/butiker/lund/).

## Federationskontrakt

`FederatedGroceryPriceProvider` implementerar samma `GroceryPriceProvider`-
interface som måltidsoptimeraren redan använder. Chain/source-logik ligger i
den centrala strategin och resolver-boundaryn, inte i optimeraren.

En basketkälla är eligible endast när den har:

- komplett basketcoverage (`FULL_CATALOG` eller `FULL_ONLINE_CATALOG`);
- promoterad och HEALTHY snapshot;
- rad- och snapshot-freshness inom gemensam `MAX_PRICE_AGE_HOURS`;
- kundvänd, geografiskt verifierad store/context;
- komplett provenance och giltig produkt-/kvantitetssemantik.

Fallback är av som standard. `ALLOW_PROVIDER_FALLBACK=true` tillåter endast en
strategideklarerad fallback och märker varje sådan observation
`fallback_used=true`. `OWN_SOURCES_ONLY=true` stänger ute externa providers.
OFFERS_ONLY kan aldrig bli basketkatalog.

Alla verifierade publika och generiska medlemskontrakt lagras i ett gemensamt
PriceUniverse. `UserPricingContext` filtrerar behörighet vid request-time; ett
medlemsbyte kräver endast ny optimering, inte refresh, provideranrop eller en
medlemsprofilerad artefakt. Stabilt medlemsprogram följer kontraktets provenance,
så en kedjas medlemskap kan inte aktivera en annan kedjas medlemspris.

`USER_SPECIFIC`-erbjudanden, aktiverade kuponger och bonuscheckar hör i stället
till en framtida användarspecifik overlay. De får aldrig komma in i den delade
PriceUniverse-artefakten. Capped kampanj-/member-priser får inte driva
obegränsad checkout för vikt-, styck- eller variabelviktvaror när source-capens
enhet inte kan modelleras säkert; då används ordinarie pris fail-closed medan
promotionmetadata och `max_quantity` bevaras.

## Malmö: kandidatyta och representativ basket

En bounded customer-context-run för postnummer 21120 gav fem användbara
contexts: City Gross Hyllie, Hemköp Triangeln och Willys Emporia via OWN samt
ICA Caroli och Lidl Caroli via Primat. Primats enda resolve-resultat för Coop
var en intern/personal-context och exkluderades fail-closed.

48-ingrediensbenchmarken gav:

| Mått | Resultat |
| --- | ---: |
| Ingredienser med minst 1 / 3 / 5 kandidater | 48 / 48 / 46 |
| Usable kandidatrader | 2 639 |
| OWN-rader | 2 399 (90,91 %) |
| Externa rader | 240 (9,09 %) |
| Kedjefördelning | City Gross 902, Hemköp 806, Willys 691, ICA 223, Lidl 17 |
| Saknad provenance / fallback / member leakage / staff-context | 0 / 0 / 0 / 0 |

Det bevarade radunderlaget från samma bounded live-run var följande. Tabellen
är mätdata från den körningen, inte ett löfte om stabil count mellan snapshots.
Den efterföljande exakta linsvariantgrinden och legacy-aliasfixen verifierades
offline utan att göra om den licensierade 48-query-runnen.

| Canonical ingredient | Usable | OWN | Primat |
| --- | ---: | ---: | ---: |
| milk | 110 | 107 | 3 |
| cream | 100 | 100 | 0 |
| creme_fraiche | 51 | 51 | 0 |
| butter | 19 | 15 | 4 |
| cheese | 271 | 267 | 4 |
| eggs | 53 | 53 | 0 |
| potato | 45 | 43 | 2 |
| ris | 160 | 119 | 41 |
| pasta | 294 | 238 | 56 |
| nudlar | 105 | 62 | 43 |
| tortillas | 16 | 16 | 0 |
| bröd | 380 | 380 | 0 |
| couscous | 16 | 15 | 1 |
| chicken_meat | 19 | 16 | 3 |
| minced_beef | 7 | 6 | 1 |
| meat_mince | 5 | 4 | 1 |
| pork_meat | 6 | 6 | 0 |
| korv | 263 | 250 | 13 |
| falukorv | 22 | 22 | 0 |
| salmon | 25 | 24 | 1 |
| fish_meat | 27 | 27 | 0 |
| tofu | 16 | 16 | 0 |
| lentil | 3 | 3 | 0 |
| red_lentils | 3 | 3 | 0 |
| kidney_bean | 29 | 23 | 6 |
| chickpeas | 29 | 23 | 6 |
| yellow_onion | 12 | 10 | 2 |
| garlic | 26 | 19 | 7 |
| carrot | 21 | 19 | 2 |
| pepper | 49 | 48 | 1 |
| white_cabbage | 9 | 9 | 0 |
| broccoli | 20 | 16 | 4 |
| cauliflower | 11 | 10 | 1 |
| tomato | 119 | 119 | 0 |
| cucumber | 18 | 18 | 0 |
| zucchini | 6 | 6 | 0 |
| leek | 6 | 5 | 1 |
| mushroom | 32 | 32 | 0 |
| krossade_tomater | 34 | 28 | 6 |
| tomato_puree | 39 | 30 | 9 |
| coconut_milk | 24 | 14 | 10 |
| broth | 7 | 6 | 1 |
| soy_sauce | 19 | 14 | 5 |
| corn | 25 | 22 | 3 |
| peas | 21 | 20 | 1 |
| spinach | 37 | 36 | 1 |
| celery | 6 | 6 | 0 |
| cooking_oil | 24 | 23 | 1 |
| **TOTAL** | **2 639** | **2 399** | **240** |

Efter den sista konservativa recall-/variantgrinden hade den fasta
13-ingredienskorgen kandidater i samtliga tre OWN-contexts. Bara synligt eller
strukturerat röda, torra linser accepterades för `red_lentils`.

| Scenario | Resultat |
| --- | ---: |
| City Gross ensam | 13/13, 276,37 kr |
| Willys ensam | 13/13, 294,29 kr |
| Hemköp ensam | 13/13, 331,26 kr |
| OWN max_stores=1 | 276,37 kr |
| OWN max_stores=2 | 262,15 kr |
| OWN max_stores=3 | 258,65 kr |

Alla körningar var VERIFIED, BasketAuditor PASS, med full OWN/catalog-
provenance och noll fallback-/memberrader.

## Fem recept × fyra portioner

En sista federerad körning använde den deterministiska receptgeneratorn,
kundfilter, membership=false och fallback=false. Primat och OWN utvärderades;
alla vinnande shoppingrader kom ekonomiskt från OWN.

| Butikstak / läge | Total | Valda contexts |
| --- | ---: | --- |
| 1 / CHEAPEST | 199,26 kr | Willys Emporia |
| 1 / BALANCED | 237,52 kr | Willys Emporia |
| 1 / VARIED | 237,52 kr | Willys Emporia |
| 2 / CHEAPEST | 184,15 kr | City Gross 54,59 + Willys 129,56 |
| 2 / BALANCED | 226,71 kr | City Gross 64,57 + Willys 162,14 |
| 2 / VARIED | 226,71 kr | City Gross 64,57 + Willys 162,14 |

Samtliga sex planer passerade BasketAuditor, nutrition och diversity, hade
VERIFIED checkout, noll deficits, noll okända kvantiteter och avstämda del-/
totalsummor. Provenance var komplett; fallback/member usage var noll.

Den sanerade benchmark-outputen bevarade inte `sale_model`, `applied_offer`
och `max_quantity` per vald rad. Den senare capped-non-fixed-härdningen ska
därför inte anses återbevisad av just denna live-output; den verifieras i stället
av separata public/member-regressioner för weight, piece och variable-weight i
den slutliga 1 172-testerssviten.

Körningen gjorde 44 seriella Primat-anrop (42 products + 2 store resolve), alla
HTTP 200 och utan auth-/403-/429-/challenge-svar. Andra planen återanvände hela
produktcachen och gjorde bara ett nytt store-resolve. OWN-API:t kördes
in-process mot en immutable SQLite-snapshot; hash och sidecar-count var exakt
oförändrade före/efter.

## Historisk Lund-diagnostik före Coop Result A

Den äldre Lund-snapshoten gav två fulla Willys-contexts via OWN samt ICA, Coop
och Lidl via Primat. City Gross/Hemköp var korrekt otillgängliga. Den live-
diagnostiska 48-ytan gav 37/28/26 ingredienser med minst 1/3/5 kandidater och
318/691 OWN-rader (46,02 %). Den lägre recallen spårades till äldre rader utan
dagens strukturerade taxonomyfält; den nya providern har därför en liten,
auktoritativ exact-alias-kompatibilitetsväg och matcher som slutlig grind. Ingen
fuzzy search eller source-fabricering infördes.

Den slutliga Phase-C-kandidaten 2026-08-23 är en separat och nyare observation.
Willys snapshot `65a83015146d4c7d989ad6e58210b147` innehåller 18 434
butik-produktrader för Lund-contexten `2176` och `2354`; offline replay
`9981f09460924fda8a138d3554467d28` reproducerade dem med noll nätanrop.
OWN-only-korgen blev 331,30 kr med `max_stores=1` och 323,76 kr med
`max_stores=2/3`; 5 × 4 BALANCED med `max_stores=2` blev 251,58 kr och samtliga
quality-/provenancegrindar passerade.

Det bounded Primat v2-bootstrap som skulle etablera dagens exakta Lund-länkar
stoppade däremot fail-closed på `identity_no_exact_match_coop`. Offlineaudit
hittade ingen säker bundle eller Primat-länk att importera. Därför finns inget
nytt federerat numeriskt Lund-resultat: Coop behåller fysisk discovery och OWN
offers, men dess Primat-basketroll är `NO_PRICE_CONTEXT`; inga ICA-/Lidl-länkar
accepterades heller från den misslyckade bundlen. Den äldre diagnostiken ovan
får inte återetiketteras som den nya federerade acceptance-körningen.

Detta historiska Primat-contextresultat avgör inte längre Coops basketcoverage.
Från 2026-08-25 använder Lund det separat verifierade OWN-onlinecontextet
`730400` när dess promoterade fullsnapshot är healthy och fresh.

## API, drift och observability

- `GET /sources/status` visar strategi, channel, coverage, health, age och
  fallback-policy utan att fabricera extern provider-health.
- Generiska store-, catalog-, search-, price- och offer-endpoints behåller ett
  additivt `source`-objekt samt snapshot/raw lineage.
- `collect-all --city Lund --city Malmö` planerar endast explicita OWN-roller,
  isolerar connectorfel, behåller LKG och kontaktar aldrig Primat.
- Hemköp Lund planeras från aktiva officiella `PhysicalStore`-rader med exakta
  OWN online-context-länkar. Varje operator-allowlistat context får eget
  `lund:hemkop:<store-id>`-scope; utan `HEMKOP_ALLOW_FULL_CRAWL=true` och exakt
  ID blir resultatet en synlig skip med noll nätanrop.
- `SourceDisagreementService` jämför OWN/Primat deterministiskt via GTIN eller
  säker source identity; pris snittas aldrig.
- Måltidsgenerering använder endast promoterade snapshots/lokal providerdata;
  den startar ingen kedjecrawl.

## Säkerhet och slutverifiering

ICA:s äldre full-HTML-capture ersattes med en strikt allowlistad replay-envelope.
Exakt 29 historiska ICA-filer och 43 databaserade raw-referenser sanerades
atomiskt utan osanitiserade backuper; parserparitet var 29/29. En efterföljande
scan över raw-rötterna hittade noll credential-/sessionnycklar, Bearer-värden,
auth-/cookieheaders eller privata nycklar. Willys, ICA och City Gross lagrar
endast inert diagnostisk JSON vid access challenge/terminal HTTP-fel.

Slutverifiering: **1 172/1 172 tester PASS**, Ruff check PASS och compileall
PASS. Full live/benchmarkdata öppnades read-only/immutable; inga SQLite-
sidecars lämnades kvar.
