# Fresh Production Data, Cold Search och Physical Ground Truth

Slutrapport för milestonen, 2026-08-26.

## Beslut

Milestonen är genomförd. Lund har en ny aktiv och verifierad PriceUniverse, den stabila kandidatsökningen är production-aktiverad, warm-pathen ligger under en sekund och fysisk stickprovsvalidering är redo för en riktig 20-varorssession på Hemköp Karhögstorg.

Det kvarstår ett tydligt prestandabacklog: en helt kall 5×4-sökning med `max_stores=2` tar cirka 31,9–32,0 sekunder i själva requesten, eller cirka 35,9 sekunder inklusive process-start och artifact-load. Målet under 20 sekunder nåddes för `max_stores=1`, men inte för `max_stores=2`. Correctness och provenance har inte försvagats för att pressa tiden.

ICA-spåret öppnades inte. Klassificeringen är fortsatt per verifierad strategi:

- ICA OWN: `PARTIAL_CATALOG`/offers, inte full basketkälla.
- ICA basket: Primat/licensierad källa där ett färskt, verifierat context finns.
- Ingen tyst fallback.

## 1. Fresh production refresh

Den kontrollerade Lund-refreshen kördes per godkänd källa med isolerade failures, atomic snapshot promotion och efterföljande atomic PriceUniverse-aktivering. Den aktiva PriceUniverse använder inga LKG-snapshots: alla fem snapshot-ID:n i manifestet är aktuella/promoted. Äldre LKG-data finns kvar som historik för contexts som inte är basket-eligible.

| Källa/context | Provider | Coverage | Snapshot | Produkter | Health | LKG i aktiv universe |
|---|---|---:|---|---:|---|---|
| Willys Lund + Lund Nova | OWN | FULL_CATALOG | `51a535d739284e4e856acd2d179950bc` | 18 485 | HEALTHY | Nej |
| Hemköp Karhögstorg 4123 | OWN | FULL_ONLINE_CATALOG | `fcd77d9857c94245bb9f184b2ee533b0` | 6 100 | HEALTHY | Nej |
| Hemköp Brunnshög 4224 | OWN | FULL_ONLINE_CATALOG | `89c6d7cd01754107804163b200ff8a99` | 5 018 | HEALTHY | Nej |
| Coop Online Syd 730400 | OWN | FULL_ONLINE_CATALOG | `39759740759845aaad0aea59503937e7` | 11 168 | HEALTHY | Nej |
| ICA Clemenstorget + Gunnesbo | Primat | FULL_CATALOG | `primat-request-37589bfc022e4256b31c50f625e54376` | 1 932 | HEALTHY/FRESH | Nej |
| ICA egna erbjudanden | OWN | OFFERS_ONLY | `de25e281fe66411a9a413cdb635791aa` | 430 råa, 412 prissatta | HEALTHY | Ej basketkälla |
| Lidl publik region | OWN | OFFERS_ONLY | `3d25be457569435096c683b7547d72c9` | 397 | HEALTHY | Ej basketkälla |
| City Gross | OWN | FULL_ONLINE_CATALOG där verifierad | – | – | `NO_LUND_CONTEXT` | Ej Lund |

Refreshen gjorde också en ny offline price-context-audit:

- Fysiska Lund-butiker: 23
- Förklarade states: 23
- Okända: 0
- Basket-capable contexts: 7
- OWN full contexts: 5
- External full contexts: 2
- Regional offers-only: 2
- Stale/non-eligible contexts: 13
- No price context: 1, Willys Hemma Stortorget
- Live provider requests i audit: 0

ICA:s sju övriga fysiska Lund-butiker är explicit `STALE_CONTEXT`, inte dolda som färska basketkällor. Lidl har två sanningsenliga regionala offers-only states. City Gross har fortsatt inget Lund-context.

### Aktiv PriceUniverse

| Fält | Värde |
|---|---:|
| Universe ID | `price-universe:9c3dd313ffa8922aa00141525f38d6a7a2b7011109af54f3b496d968b501df14` |
| Built at | 2026-08-26 18:52:40Z |
| Activated at | 2026-08-26 18:56:49Z |
| Oldest observation | 2026-08-26 12:19:18Z |
| Freshness vid slutkontroll | FRESH, 9,76 timmar |
| Fresh warning/stale policy | 36 h / 48 h |
| Raw products | 42 042 |
| Eligible products | 7 306 |
| Post-pruning products | 2 287 |
| Canonical index keys | 56 |
| Materialiserade ekonomiska/exakta kandidatrader | 824 |
| Contexts | 7 |
| Artifact size | 77 328 396 byte, 73,75 MiB |
| Build time | cirka 212,7 s |
| Load + schema validation + activation | 3,666 s |
| Provider calls vid build/request | 0 |

Manifestets SHA-256 och artifactens faktiska SHA-256 är identiska:
`4851f72f80be5f492257ea79c5ad38a8d6d4984281a9871d97bfcc4302214044`.

En äldre Coop-snapshot under legacy-scope `lund:coop:730400` ligger fortfarande som `promoted + is_active` parallellt med det kanoniska scopet `coop:online:730400`. Den aktiva context-länken och PriceUniverse använder endast den färska snapshoten `397597…`; ingen prisblandning sker. Detta är därför ett registry-metadata-backlog, inte ett aktivt pris- eller request-pathfel.

## 2. Search correctness

### Stabil kandidatsuperset

Sökningen använder nu:

1. en deterministisk stabil baskandidatpool på 120 recept,
2. pris-aware kandidater som får läggas till,
3. en quality-safe, stratifierad sökpool på 160 av 172 giltiga kandidater.

Detta gör att en ny produktkälla kan lägga till ekonomiska möjligheter utan att tidigare giltiga basrecept försvinner enbart på grund av ändrad prisrankning. Pruning bevarar familj, dish form, protein, kolhydrat och tillagningssätt.

Production-gränsen 160 valdes genom mätning:

- 120 kandidater, CHEAPEST max2: 207,46 kr
- 160 kandidater: 195,75 kr
- alla 172 giltiga kandidater: 195,75 kr
- 160 mot 172: exakt gap 0,00 kr
- recept, contexts och samtliga åtta valda produktköprader är identiska mellan 160 och 172

120-kandidatsläget avvisades alltså som production-standard eftersom det hade ett känt gap på 11,71 kr.

160-vs-172-kontrollen använder samma production-beam och mäter därför shortlist-stabilitet, inte ett matematiskt globaloptimum över alla möjliga menyer. Global exact-vs-beam verifieras separat på små, exhaustivt lösbara fixtures.

Den aktiva arbetsmiljön och `.env.example` har explicit `STABLE_CANDIDATE_SEARCH_ENABLED=true`, baskandidatantal 120 och sökgräns 160. Kodens kompatibilitetsdefault är fortsatt rollout-gated; en ny deployment måste därför behålla den explicita production-konfigurationen.

### Monotonicitet och exakta kontroller

Regressionerna verifierar nu att:

- ett fast receptset inte kan få ett dyrare CHEAPEST-resultat när endast giltiga produkter läggs till,
- en fast shopping basket inte kan bli dyrare när endast giltiga produkter läggs till,
- kandidater genereras deterministiskt och baskandidater behålls,
- basket-cache-nyckeln är kanonisk och oberoende av receptordning,
- lower bound är admissible mot exact search på små fixtures,
- store-subset pruning och multibuy-resultat matchar authoritative BasketOptimizer,
- slutlig komplett basket räknas och auditeras av den auktoritativa optimeraren.

Monotoniciteten är också testad direkt genom production `MenuOptimizer` med beam width 3, två butiker och en verklig `2 för 12`-promotion: BEFORE 19,00 kr, samma gamla lösning reprissatt i det större universumet 19,00 kr och AFTER 17,00 kr.

## 3. Vad tog tid före och efter?

Profilen före den sista optimeringen visade tre dominerande lokala hotspots:

1. miljontals återberäkningar av candidate checkout floors/lower bounds,
2. upprepade fulla basket- och store-subsetberäkningar för ekonomiskt identiska partial states,
3. package/quote-urval och hot-path-mätning per enskild operation.

Åtgärderna blev därför begränsade och resultatsäkra:

- checkout floors delas och förberäknas en gång,
- kanoniska requirement-nycklar återanvänds oberoende av receptordning,
- parent + recipe delta återanvänds för partial states,
- store subsets och ingredient/store-availability återanvänds,
- exact per-store winner vectors undviker upprepade quote scans,
- package/quote/select-cacher aggregerar counters efter cache-scope,
- O(recept²)-relationer byggs endast vid en verklig menu-cache miss,
- slutlig basket och alla quality gates är oförändrat auktoritativa.

### Cold och warm 5×4

Tiderna nedan är request-tid med samma frysta PriceUniverse, seed, beam width, constraints och memberships. `AFTER` använder 160-kandidatsupersetet; `BEFORE` använde den äldre 67/73-kandidatsökningen.

De sex BEFORE-filerna är låsta med SHA-256 i `reports/production-readiness-20260826/before-baseline.sha256`, inklusive universe-ID och benchmarkkonfiguration.

| Scenario | Före total | Efter total | Delta | Före cold | Efter cold | Efter warm |
|---|---:|---:|---:|---:|---:|---:|
| CHEAPEST max1 | 232,85 kr | 216,36 kr | −16,49 | 38,292 s | 13,795 s | 0,892 s |
| CHEAPEST max2 | 204,15 kr | 195,75 kr | −8,40 | 59,326 s | 31,874 s | prewarm PASS; separat trace ej sparad |
| BALANCED max1 | 288,45 kr | 278,01 kr | −10,44 | 38,210 s | 13,719 s | 0,934 s |
| BALANCED max2 | 259,37 kr | 253,01 kr | −6,36 | 59,557 s | 31,948 s | 0,953 s |
| VARIED max1 | 288,45 kr | 278,01 kr | −10,44 | 39,182 s | 13,846 s | 0,943 s |
| VARIED max2 | 259,37 kr | 253,01 kr | −6,36 | 58,852 s | 32,023 s | 0,948 s |

Efter-tider inklusive ny process, artifact-load och request:

- max1: cirka 17,6–17,7 s
- max2: cirka 35,8–35,9 s

Cold max1 är 64–65 % snabbare. Cold max2 är cirka 46 % snabbare. Warm target under en sekund är uppnått i de persistenta profilerna; en separat full sexprofilers prewarm gav 6/6 lyckade profiler, 0 provider calls och en efterföljande BALANCED max2-request på 0,836 s.

### Kandidater, states och cache

| Scenario | Före kandidater/states/baskets | Efter kandidater/states/baskets | Efter basket-cache |
|---|---:|---:|---:|
| CHEAPEST max1 | 67 / 7 173 / 7 101 | 160 / 332 / 285 | 14,16 % |
| CHEAPEST max2 | 73 / 7 907 / 7 829 | 160 / 332 / 288 | 13,25 % |
| BALANCED max1 | 67 / 4 383 / 2 343 | 160 / 334 / 82 | 75,45 % |
| BALANCED max2 | 73 / 5 125 / 2 863 | 160 / 333 / 29 | 91,29 % |
| VARIED max1 | 67 / 4 314 / 0 delad cache | 160 / 333 / 30 | 90,99 % |
| VARIED max2 | 73 / 5 038 / 0 delad cache | 160 / 333 / 29 | 91,29 % |

CHEAPEST har lägre basket-hit rate eftersom fler unika ekonomiska requirement-set faktiskt måste prissättas, men antalet authoritative basketberäkningar sjönk ändå från cirka 7 000–7 800 till under 300. Incremental-requirement-cachen ligger mellan cirka 97,5 och 99,7 % hits i de slutliga profilerna.

## 4. Ekonomiskt resultat

Ingen AFTER-plan blev dyrare än sin kompatibla BEFORE-plan. Förbättringarna kommer från det stabila/additiva kandidatsetet på exakt samma färska PriceUniverse, inte från en senare source-refresh.

Valda contexts efter ändringen:

- CHEAPEST max1: Willys Lund Nova
- CHEAPEST max2: Hemköp Brunnshög + Willys Lund Nova
- BALANCED/VARIED max1: Willys Lund
- BALANCED/VARIED max2: Hemköp Brunnshög + Willys Lund

### Färsk 13-item basket

Den separata representativa varukorgen kördes helt offline och passerade 13/13 samt provenance/audit i samtliga lägen:

| Max stores | Total | Contexts | Runtime |
|---:|---:|---|---:|
| 1 | 336,52 kr | Coop Online Syd | 0,080 s |
| 2 | 308,55 kr | Coop Online Syd + Hemköp Brunnshög | 0,093 s |
| 3 | 300,80 kr | Coop Online Syd + Hemköp Brunnshög + Willys Lund | 0,131 s |

Mot den äldre historiska Lund-golden 340,30 / 329,30 / 326,36 kr är skillnaden −3,78 / −20,75 / −25,56 kr. Detta är en färsk-datajämförelse, inte en ren kod-A/B, och redovisas därför separat från den kompatibla BEFORE/AFTER-menymatrisen.

## 5. Prewarm och normal request-path

Prewarm är konfigurerbar och operator-opt-in. Standardprofilerna är CHEAPEST, BALANCED och VARIED för max1/max2, fem recept och fyra portioner.

- Körs efter lyckad PriceUniverse-aktivering.
- Ett prewarm-fel får inte avaktivera ett giltigt universe.
- Aktiv universe kontrolleras före och efter varje profil.
- OpenAI och live provider boundary är blockerade i prewarm-flödet.
- Meal requests läser endast aktiv PriceUniverse och gör 0 chain/provider calls.

Den verifierade sexprofilskörningen tog cirka 46,4 s efter load och fyllde processcachen. För vanlig veckovis användning är rekommendationen därför daily refresh + atomic universe swap + standard-prewarm.

## 6. Physical price ground truth

Systemet är redo för en riktig, frivillig stickprovsvisit på Hemköp Karhögstorg. Inga testobservationer eller testsessioner har skrivits till production-DB:

- `physical_price_observations = 0`
- `physical_validation_sessions = 0`
- session items/candidates = 0

### Karhögstorg field readiness

- Fysisk butik och exact online-context är aktiva.
- Promoted FULL_ONLINE_CATALOG-snapshot: `fcd77d9857c94245bb9f184b2ee533b0`.
- 6 100 digitala produktrader finns som jämförelseunderlag.
- `/physical-check` kan starta en 20-varorssession.
- Blind capture är på som standard.
- Digitalt pris visas först efter commit.
- Prisfältet för hyllpris förifylls aldrig.
- BarcodeDetector och manuell GTIN finns, med explicit produktsökning som säker fallback.
- Osäker identitet kan sparas som `NO_MATCH`; fuzzy match autoaccepteras inte.
- Sessionen visar progression, exempelvis `7 av 20`, och kan avslutas tidigt.
- JSON- och CSV-export är sanerad.

En read-only suggestionskörning valde 20 produkter ur 759 möjliga digitala kandidater: 1 regular, 1 member, 13 multibuy och 5 weight, spridda över 7 kategorier och 8 varumärken. Mixen är stratifierad men speglar också den aktuella snapshotens kampanjdata; den är ett rekommenderat stickprov, inte ett krav.

Varje observation fryser exakt digital evidens:

- provider och context ID,
- snapshot ID,
- source product ID/GTIN där säkert,
- digital observed_at,
- digitalt pris och prissemantik,
- separat inmatat hyllpris och fysisk observationstid.

Fysisk observation skriver aldrig över digital catalog price.

### Accuracy efter första riktiga besöket

Före 20 matchbara observationer visas `INSUFFICIENT_SAMPLE`, inte en missvisande procentsats. Vid minst 20 produceras:

- sample size och `sampled_only=true`,
- exact matches och inom 0,50 kr,
- mean och median absolute error,
- signed mean error/bias,
- digitalt lägre/högre än hylla,
- NO_MATCH-count,
- separata breakdowns för REGULAR, SALE, MEMBER och WEIGHT där underlaget räcker.

MULTIBUY jämför villkor och kvantitet, MEMBER jämförs medlem-mot-medlem och viktvaror jämförs i SEK/kg. Ett resultat formuleras exempelvis som ”20 av 20 stickprovsvaror matchade”, aldrig som att hela butiken är verifierad.

## 7. Verifiering

Efter omstarten kördes kvalitetsgrindarna på nytt:

```text
py -3.12 -m pytest backend/tests grocery_data/tests -q     PASS, 100 %, exit 0
py -3.12 -m ruff check backend grocery_data               PASS
py -3.12 -m compileall -q backend grocery_data            PASS
```

Regressionerna omfattar bland annat stable candidate retention, monotonicitet, exact/reference search, basket-cache-kanonisering, incremental reuse, store-subset pruning, admissible lower bound, prewarm failure isolation, blind capture, NO_MATCH, promotion/member/multibuy/weight, minsta sample, historical snapshot linkage och att fysisk evidens inte modifierar digital source-data.

En separat textsökning över senaste refresh-raw, aktiv PriceUniverse-artifact och milestone-rapporter hittade inga förbjudna Cookie-, Authorization-, CSRF-, Page-View-, tracking-, browser-storage- eller bearer/sessionvärden. ICA-transporttesterna i testsuiten var fixture/offline; inga nya live ICA- eller WAF-experiment kördes.

## 8. Slutbedömning

Systemet är redo för vanlig veckovis användning under följande production-liknande drift:

1. kontrollerad daily refresh,
2. atomic PriceUniverse validation/activation,
3. standard-prewarm,
4. meal requests mot aktiv lokal artifact,
5. frivilliga fysiska stickprov som separat evidenslager.

Freshness, correctness, ekonomisk monotonicitet, provenance och warm latency är production-mässiga för den nuvarande Lund-konfigurationen. Det återstående större teknikbackloget är cold max2-sökningen på cirka 32 s request-tid. Den påverkar första o-prewarmade requesten, inte normal warm veckomenyanvändning.
