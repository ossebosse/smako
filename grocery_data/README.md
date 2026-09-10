# Grocery Data

`grocery_data` är ett separat, replaybart prisdatasystem för den befintliga
matkasseoptimeraren. Det samlar källdata, sparar råresponsen före tolkning,
normaliserar produkt- och köpsemantik, bygger prishistorik och publicerar endast
hälsokontrollerade snapshots.

## Nuvarande status

**Willys** är reference connector för full katalog. **City Gross Malmö Hyllie**,
**Hemköp Malmö Triangeln**, **Hemköp Lund Brunnshög** och **Hemköp Lund
Karhögstorg** är accepterade Own-basketkällor med verifierad och promoterad
`FULL_ONLINE_CATALOG`. **Coop Online Syd** (`730400`) är också accepterad OWN-
basketkälla med en promoterad `FULL_ONLINE_CATALOG`-snapshot. **ICA** är
fortsatt `OFFERS_ONLY` i OWN och använder Primat/licensierad data som bred
basketkälla. City Gross, Hemköp och Coops fullkatalog har source-policy `REVIEW`, så
full live collection kräver explicit operator-opt-in och exakt store-allowlist.
**Lidl** har en körbar, replaybar `OFFERS_ONLY`-connector för den nationella
publika standardregionens aktuella/kommande erbjudandeyta. Lidl-priserna
tillskrivs aldrig de fysiska Lund-/Malmö-butikerna utan verifierad regionkoppling;
Primat/licensierad data är därför fortsatt kedjans breda basketkälla.

| Kedja | Publik source potential | Körbar own connector | Viktig begränsning |
| --- | --- | --- | --- |
| Willys | `FULL_CATALOG` för aktiverbara onlinebutiker | `FULL_CATALOG` | Frontendinternt API; GTIN kräver extra detaljanrop och standardinsamlingen gör ingen full GTIN-enrichment. |
| ICA | Browserytan är bredare men inte säkert traverserbar | `OFFERS_ONLY` | Officiella butikserbjudanden; browserkatalogens continuation möter WAF och samlas inte in. |
| Coop | Resultat A: `FULL_ONLINE_CATALOG` för Coop Online Syd `730400` | `FULL_ONLINE_CATALOG`, accepterad | 748 terminalkategorier, 822 sidor och 11 175 unika produkter. Regionalt onlinepris-context, inte fysisk hyllprisidentitet; fysiska offers är en separat OWN-kanal. |
| Hemköp | `FULL_ONLINE_CATALOG` för Malmö Triangeln, Lund Brunnshög och Lund Karhögstorg | `FULL_ONLINE_CATALOG`, accepterad | Separata promoterade store-contexts. Karhögstorgs historiska pagination-overlap klassificerades och replayades säkert före en ny ren fullcrawl; policy `REVIEW`. |
| Lidl | `OFFERS_ONLY` | `OFFERS_ONLY`, accepterad | 421/421 aktuella/kommande publiceringsrader, 9/9 sidor och separat regional kontext; inte komplett lokalt sortiment eller basketkälla. |
| City Gross | `FULL_ONLINE_CATALOG` för Malmö Hyllie | `FULL_ONLINE_CATALOG`, accepterad | 13 642/13 642 produkter över 137/137 sidor; policy `REVIEW`, opt-in + allowlist krävs. Ingen verifierad Lund-butik/hemleveranskälla. |

Detaljer, verifierade fält, pagination, risker och canary-förslag finns i:

- [ICA](../docs/sources/ica.md)
- [Coop](../docs/sources/coop.md)
- [Willys](../docs/sources/willys.md)
- [Hemköp](../docs/sources/hemkop.md)
- [Lidl](../docs/sources/lidl.md)
- [City Gross](../docs/sources/citygross.md)
- [Federerat sexkedjorsuniversum](../docs/sources/federation.md)

Publik teknisk åtkomst är inte samma sak som tillstånd att återpublicera data.
Robots och publika villkor behandlas som source-policy-signaler: `ALLOW`,
`REVIEW` eller `BLOCK`. `REVIEW` kräver explicit operator-opt-in; `BLOCK`
stoppar. Connectors får aldrig kringgå login, CAPTCHA, åtkomstkontroller eller
anti-bot-skydd.

### Aktiv verifierad Willys Lund-körning 2026-08-23

Referensconnectorn kördes end-to-end mot Willys publika frontendkälla med en
request per sekund och två exakt allowlistade onlinebutiker. Resultatet är
butik-produktrader, inte unika nationella produkter:

| Butik | Produkter | Katalogsidor | Recipe coverage ≥1/≥3/≥5 |
| --- | ---: | ---: | ---: |
| Willys Lund `2176` | 10 069 | 653 | 48/48 / 47/48 / 39/48 |
| Willys Lund Nova `2354` | 8 365 | 585 | 48/48 / 45/48 / 39/48 |
| Totalt | 18 434 | 1 238 | — |

Source-snapshot `65a83015146d4c7d989ad6e58210b147` är aktiv och
`PROMOTED`. Replay-snapshot `9981f09460924fda8a138d3554467d28`
reproducerade alla 18 434 produkter helt offline med noll nätanrop. Samtliga
completion-, parser-, freshness- och quality-grindar passerade. Den tredje
fysiska Lund-butiken, Willys Hemma Stortorget `2863`, saknar verifierad full
onlinekatalog och är inte basketberättigad.

### Verifierad City Gross Malmö Hyllie-körning 2026-08-23

City Gross fullkatalog kördes staged bakom `SourcePolicy.REVIEW`, replayades
helt offline med parser v2/normalizer v3 och promotades först efter full
quality- och basketacceptance:

| Mätvärde | Resultat |
| --- | ---: |
| Kontext | Malmö Hyllie, `storeNumber=3211`, `siteId=169` |
| Deklarerade / råa / unika produkter | 13 642 / 13 642 / 13 642 |
| Pagination | 137 / 137 sidor, 0 dubbletter |
| Pris / ordinarie pris | 100,00 % / 100,00 % |
| Giltig GTIN | 99,11 % |
| Package quantity | 92,09 % |
| Löst purchase model | 95,35 % |
| Broad recipe-relevant purchase model | 97,35 % |
| Promotioner | 1 574 (1 239 multibuy, 62 member-only) |
| Live requests / HTTP-fel / 429 | 139 / 0 / 0 |
| Live runtime / raw | cirka 3 min 18 s / 139 filer, 74 036 248 byte |
| Recipe coverage ≥1 / ≥3 / ≥5 | 48/48 / 45/48 / 40/48 |
| Representative basket | 13/13, complete |
| Offline replay | 0 nätverksanrop, samma produkter/priser/promotioner |

Aktiv snapshot är `80b792e5029b4f348478550609ceff10`. Coverage betyder
komplett verifierad **onlinekatalog för Hyllie**, inte varje fysisk hyllprodukt
eller en Lund-butik. Availability publiceras ännu inte från `stockStatus`, vars
semantik inte har verifierats. Primat är endast en explicit fallback.

### Verifierad Hemköp Malmö Triangeln-körning 2026-08-23

Hemköps fullkatalog kördes staged bakom `SourcePolicy.REVIEW`, med exakt
aktiverad online-store-kontext `4247`. Live-snapshoten lämnades inaktiv och
replayades helt offline före separat atomisk promotion:

| Mätvärde | Resultat |
| --- | ---: |
| Kontext | Hemköp Malmö Triangeln, `storeId=4247` |
| Kategorier / pagination | 20/20 / 113/113 sidor |
| Deklarerade / råa / unika produkter | 10 016 / 10 016 / 9 002 |
| Dubblettklassificering | 0 within-category / 1 014 identiska cross-category |
| Pris | 9 002/9 002, 100 % |
| Package quantity | 8 793/9 002, 97,68 % |
| Okänd purchase model | 159/9 002, 1,77 % |
| GTIN i standardkatalog | 0 %; detaljroute krävs |
| Promotioner | 1 422 |
| Live requests / HTTP-fel / 429 | 118 / 0 / 0 |
| Live runtime / raw | cirka 10 min 39 s / 117 filer, 22 812 892 byte |
| Offline replay | 0 nätverksanrop/browser, samma 9 002 produkter |

Live source snapshot är `4d572317b00049268f8ee1d3b3060c87` och förblir
inaktiv `HEALTH_CHECKED` evidens. Den auktoritativa replay-snapshoten
`00db33803746408796d118c91270fccc` är `PROMOTED`, aktiv och `HEALTHY`.
Hemköps default registry-/canarytransport är fortfarande bounded och kan inte
ärva crawl-authority från miljön. Primat är endast explicit fallback.

### Verifierad Hemköp Lund Brunnshög-körning 2026-08-23

Lund körs med en separat snapshot per exakt aktiverad online-store-kontext.
Brunnshög `4224` fullföljde alla completion- och quality-grindar; source-
snapshot `a579353ef6844296a03d75b69fedbf53` är `PROMOTED`, aktiv och
`HEALTHY`:

| Mätvärde | Resultat |
| --- | ---: |
| Kontext | Hemköp Lund Brunnshög, `storeId=4224` |
| Kategorier / pagination | 20/20 / 67/67 sidor |
| Deklarerade / råa / unika produkter | 5 642 / 5 642 / 5 086 |
| Dubblettklassificering | 0 within-category / 556 identiska cross-category |
| Pris / availability | 5 086/5 086 / 100 % |
| Package quantity / löst purchase model | 98,49 % / 98,55 % |
| Promotioner | 995 (186 sale, 78 member, 731 multibuy) |
| Live requests / HTTP-fel / 429 | 72 / 0 / 0 |
| Live runtime / raw | cirka 12 min 54 s / 71 filer, 12 757 212 byte |
| Recipe coverage ≥1 / ≥3 / ≥5 | 48/48 / 43/48 / 30/48 |
| Representative basket | 13/13, complete |
| Offline replay | 0 nätverksanrop, samma 5 086 produkter |

Den separata fysiska butiken Hemköp Lund Karhögstorg `4123` finns i det
officiella registret och har verifierad onlineaktivering samt exakt contextlänk.
Det historiska kandidatförsöket `f0c46d421d514757912c1883cdecde0b`
underkändes korrekt fail-closed. Produkt `101882749_ST` låg byte-identiskt på
sida 5 och 6 i `godis-snacks-och-glass`: en `EXACT_ROW_DUPLICATE` orsakad av
`PAGINATION_OVERLAP`, inte en variant- eller ID-kollision. En strikt policy får
bara ta bort en sådan rad när produkt-ID, pris, ordinarie pris, paket,
promotion och availability är identiska; varje konflikt fortsätter att stoppa
kandidaten.

Den sparade traversalens rekonstruerade replay
`0ab1769e92c94243a379509b4517d3df` gjorde noll nätanrop och förklarade exakt en
sådan overlap, noll konflikter och 6 068 unika prissatta produkter. Därefter gav
en ny livecrawl en ren union: source-snapshot
`2d669d3dd375462fbb5fb8cf5a5ec934` täcker 20/20 kategorier, 78/78 sidor och
6 797 råa / 6 092 unika prissatta produkter, med noll within-category-
dubbletter, konflikter eller pagination-overlap. Den är `PROMOTED`, aktiv,
`HEALTHY` och basketberättigad; offline replay
`1398f77ad6654c668375122b9adae178` reproducerade 6 092 produkter med noll
nätanrop. Recipe coverage är 48/46/34 av 48 för ≥1/≥3/≥5 kandidater och den
representativa korgen är komplett 13/13.

### Verifierad Coop Online Syd-körning 2026-08-25

Coops accepterade fullkatalog är ett regionalt online-/fulfilment-context,
**Coop Online Syd** `730400`, inte en fysisk Coop-butik. Fysisk Stora Coop Lund
`2696` har en exakt separat pickuprelation via pickup point `257611`; Lund-
registret skapar ingen motsvarande länk för Mårtenstorget. Priserna märks därför
`online_price`/`Coop onlinepris` och får inte beskrivas som verifierade hyllpriser.

| Mätvärde | Resultat |
| --- | ---: |
| Accepterade terminalkategorier / sidor | 748 / 822 |
| Råa kategorirader / unika produkter | 12 380 / 11 175 |
| Säkra cross-category-overlaps / konflikter | 1 205 / 0 |
| Pris / ordinarie pris | 100,00 % / 100,00 % |
| Checksum-valid GTIN | 11 119 / 11 175 (99,50 %) |
| Package quantity | 11 086 / 11 175 (99,20 %) |
| Löst purchase model | 11 094 / 11 175 (99,28 %) |
| Recipe coverage >=1 / >=3 / >=5 | 48/48 / 45/48 / 39/48 |
| Representative basket | 13/13, complete |
| Offline replay | 11 175 produkter, 0 nätverksanrop |

Snapshot `851d317e88ce422b90d80d26ca1ebb2b` är atomiskt `PROMOTED`.
Katalogen innehåller 1 003 normaliserade promotioner över 979 produkter,
inklusive separata sale-, member-, multibuy- och percentage-rader.
`CUSTOMER_PRIVATE` tolkas som B2C, aldrig som medlemskap utan uttrycklig
`medMeraRequired`-evidens. Chain-strategin använder OWN som basket-primary och
behåller Primat/licensierad data som explicit fallback; fysiska OWN-offers är
fortsatt en separat channel.

## Arkitektur

```text
chain-specific HTTP client
        |
        v
immutable raw response + metadata
        |
        v
chain-specific parser -> SourceProduct / quarantine
        |
        v
shared ProductNormalizer -> CanonicalProduct
        |
        v
price observations + promotions + lineage
        |
        v
validation -> health/anomaly checks -> atomic promotion
        |
        v
FastAPI -> OwnGroceryPriceProvider -> meal optimizer
```

Ansvarsgränserna är avsiktliga:

- `app/connectors/<chain>/client.py` känner till transport, butikskontext,
  pagination, begränsade retries och rate limit.
- `app/connectors/<chain>/parser.py` tolkar sparad källdata till `SourceProduct`.
- Willys-parsern hämtar kataloghierarkin från sidnivåfälten
  `superCategories` + `categoryInfo` (med källstyrd breadcrumb-fallback), så
  varje produkt behåller en ordnad `category_path` även när resultatposten
  saknar egna kategorifält.
- `app/normalization/` härleder köpmodell och confidence utan att skapa data som
  källan inte gav. Jämförpris blir aldrig paketpris eller paketstorlek.
- `app/services/raw_storage.py` sparar immutabel rådata och maskerar
  credential-/sessionsformade JSON-fält.
- `app/storage/` lagrar lineage, historiska prisobservationer, snapshots,
  quarantine, körningar och connector-health.
- `app/monitoring/` gör schemafingerprinting, baselinejämförelse,
  pris-sanity och secret-safe alerts.
- `app/services/collector.py` koordinerar hela state machine-flödet.
- `app/services/replay.py` kör ny parser/normalizer mot redan sparad rådata med
  `network_requests = 0`.
- `app/api/` publicerar endast aktiva snapshots tillsammans med freshness och
  connectorstatus.

Willys är referensconnectorn. Ändras Willys schema ska reparationen normalt
stanna under `app/connectors/willys/`, dess fixtures och parser-test.

## Installation

Kör från repositoryroten med Python 3.12 eller senare:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r grocery_data/requirements.txt
```

Normal drift använder PostgreSQL, SQLAlchemy och Alembic. Skapa en tom databas
och en minst privilegierad databasroll utanför applikationen. Lägg DSN i `.env`;
lägg aldrig lösenord i repositoryt eller kommandologgar.

```powershell
Copy-Item .env.example .env
```

Relevanta miljövariabler:

| Variabel | Exempel/default | Användning |
| --- | --- | --- |
| `GROCERY_DATABASE_URL` | `postgresql+psycopg://<user>:<password>@localhost:5432/grocery_data` | CLI, collector och Alembic. |
| `GROCERY_RAW_SNAPSHOT_ROOT` | `raw_snapshots` | Rot för immutabla råpayloads. |
| `GROCERY_DATA_USER_AGENT` | `grocery-data-poc/0.1 (+source-transparency)` | Stabil identifierbar HTTP-identitet. |
| `WILLYS_REQUESTS_PER_SECOND` | `1` | Konservativ Willys-rate limit. |
| `OWN_GROCERY_BASE_URL` | `http://127.0.0.1:8010` | Måltidsappens URL till detta API. |
| `OWN_GROCERY_MAX_AGE_HOURS` | `48` | Max ålder som `OwnGroceryPriceProvider` accepterar. |
| `OWN_GROCERY_INCLUDE_OFFERS_ONLY` | `false` | Explicit opt-in för ICA-/Coop-offer-enrichment; opt-in gör aldrig en offers-only-butik till komplett basketbutik. |

CLI, Alembic och ASGI-applikationen läser samma `GROCERY_DATABASE_URL` från
repositoryts `.env` utan att skriva över en redan satt processvariabel. Om
variabeln saknas använder alla tre `./grocery_data.sqlite`. Det är endast en
credential-fri utvecklingsfallback; normal drift ska använda en explicit
PostgreSQL-URL.

## Databas och migrationer

Rekommenderat för normal drift:

```powershell
python -m alembic -c grocery_data/alembic.ini upgrade head
```

Kontrollera migrationshistoriken utan att ändra databasen:

```powershell
python -m alembic -c grocery_data/alembic.ini history
```

`init-db` skapar tabeller direkt från SQLAlchemy metadata och är endast en
bekvämlighet för lokal utveckling:

```powershell
python -m grocery_data init-db
```

Produktionsdatabasen ska migreras med Alembic, inte med `init-db`.

Tabellerna är:

- `stores`
- `collector_runs`
- `catalog_snapshots`
- `raw_snapshots`
- `source_products`
- `products`
- `price_observations`
- `promotions`
- `parser_failures`
- `connector_health`

Prisobservationer appendas per snapshot och kan frågas historiskt på stabil
källproduktnyckel + butik. Samma produkt/butik lagras idempotent inom en och
samma snapshot; en senare snapshot skapar en ny tidsstämplad observation.

## CLI

Visa det faktiska kontraktet med:

```powershell
python -m grocery_data --help
```

### Butiker

`stores` gör live store discovery och sparar råresponsen på filsystemet. Det
skriver inte en full katalogsnapshot till databasen.

```powershell
python -m grocery_data stores --chain willys --city Lund
python -m grocery_data stores --chain willys --city Malmö
python -m grocery_data stores --chain all --city Lund
```

Den sista körningen redovisar discovery-only-kedjor som `not_implemented` och
returnerar exitkod 2; ofullständig kedjetäckning blir alltså inte en tyst
lyckad automatiseringskörning.

### Collect

```powershell
python -m grocery_data collect --chain willys --city Lund
python -m grocery_data collect --chain willys --city Lund --city Malmö
```

City Gross full collection ligger bakom en separat `REVIEW`-grind. Store
discovery och canary är alltid bounded även om connectorn är registrerad:

```powershell
$env:CITYGROSS_ALLOW_FULL_CRAWL="true"
$env:CITYGROSS_STORE_EXTERNAL_IDS="3211"
$env:CITYGROSS_REQUESTS_PER_SECOND="1"
$env:CITYGROSS_MAX_CONCURRENCY="1"
python -m grocery_data collect --chain citygross --city Malmö --no-promote
```

Standardvärdet för `CITYGROSS_ALLOW_FULL_CRAWL` är `false`. En staged kandidat
ska granskas/replayas innan explicit `promote`. Full collection stoppar vid
401/403, access challenge, CAPTCHA, WAF eller 429 och gör inga bypassförsök.
CLI-utdata samt collector-run scope/metrics loggar ett sanerat auditspår med
`source_policy`, `operator_opt_in`, sorterad `store_allowlist`, request rate och
concurrency. Auditmodellen accepterar inga extra fält och kan därför inte bära
cookies, auth-headers, tokens eller sessionsvärden.

Hemköp använder samma operativa grind men en egen adapter och egna env-flaggor:

```powershell
$env:HEMKOP_ALLOW_FULL_CRAWL="true"
$env:HEMKOP_STORE_EXTERNAL_IDS="4247"
$env:HEMKOP_REQUESTS_PER_SECOND="0.1"
$env:HEMKOP_MAX_CONCURRENCY="1"
python -m grocery_data collect --chain hemkop --city Malmö --no-promote
```

Registry, `stores` och canary är alltid en kategori/en sida och saknar full-
crawl-authority. En full collect kräver både explicit opt-in och exakt allowlist.
Vid 401/403/405, CAPTCHA/WAF/challenge eller 429 stoppas körningen utan bypass,
sessionrotation eller challenge-retry.

En full collect gör i ordning:

1. store discovery;
2. raw capture;
3. parse och quarantine;
4. normalisering och prisobservationer;
5. schema- och baselinekontroller;
6. state transitions `FETCHED -> PARSED -> VALIDATED -> HEALTH_CHECKED`;
7. atomisk promotion endast vid `HEALTHY`.

Kommandot returnerar normalt exitkod 2 om kandidat-snapshoten inte promoterades
eller om en explicit begärd kedja ännu saknar connector. Det avsiktliga
undantaget är `--no-promote`: en `HEALTHY` kandidat som lämnas i
`HEALTH_CHECKED` för granskning är en lyckad staged collection och ger exitkod
0. En misslyckad kedja gör inte gammal fungerande data inaktiv.

### Health

```powershell
python -m grocery_data health
```

Utdata visar coverage, implementeringsstatus, senaste lyckade körning, aktiv
snapshot, metrics, varningar och discovery-begränsningar per kedja.

### Replay

Replay läser endast payloads från `GROCERY_RAW_SNAPSHOT_ROOT` och metadata från
databasen. Den gör inga requests mot Willys.

```powershell
python -m grocery_data replay `
  --chain willys `
  --snapshot-id <snapshot-id>
```

Replay skapar en ny kandidat-snapshot. Lägg endast till `--promote` efter att
resultat, diff och health är granskade:

```powershell
python -m grocery_data replay `
  --chain willys `
  --snapshot-id <snapshot-id> `
  --promote
```

Hemköps replay läser store-identiteter från snapshotens completion-evidence
och skapar en inert transport utan nät- eller crawl-authority:

```powershell
python -m grocery_data replay `
  --chain hemkop `
  --snapshot-id <snapshot-id>
```

`--accept-schema-change` stänger av schemaändringen som blockerande signal för
just replay-körningen. Flaggan betyder inte att schemat är korrekt och ska bara
användas efter fixture-, parser- och diffgranskning.

### Diff

```powershell
python -m grocery_data diff --old <old-snapshot-id> --new <new-snapshot-id>
```

Diffen matchar primärt via GTIN, därefter kedjans produkt-ID/stabila
källproduktnyckel. Den visar antal produkter, tillagda/borttagna produkter,
prisförändringar, parser-fel samt GTIN-, pris- och paketkvantitetscoverage före
och efter. Varningar markerar produktfall, ökade parser-fel och coverage-tapp på
mer än tio procentenheter. Verktyget påstår inte att det gör en raw-payload-diff;
strukturella raw-förändringar rapporteras separat via schemafingerprint i health.

### Validate och promote

```powershell
python -m grocery_data validate --snapshot-id <snapshot-id>
python -m grocery_data promote --snapshot-id <snapshot-id>
```

Normal `collect` gör dessa övergångar automatiskt. De fristående kommandona är
operatörsverktyg för redan parsade/replayade snapshots. `validate` avancerar
snapshotens state; den ersätter inte collectorens parser-, anomaly- eller
health-kontroller. `promote` är atomisk och kräver att snapshoten nått
`HEALTH_CHECKED`.

### Live canary (opt-in)

Normala tester är offline. Canary gör ett litet publikt nätverkstest och ska
köras uttryckligen:

```powershell
python -m grocery_data canary willys --city Lund
python -m grocery_data canary willys --city Malmö
python -m grocery_data canary ica --city Lund
python -m grocery_data canary ica --city Malmö
python -m grocery_data canary coop --city Lund
python -m grocery_data canary coop --city Malmö
python -m grocery_data canary citygross --city Malmö
python -m grocery_data canary citygross --city Lund
python -m grocery_data canary hemkop --city Lund
python -m grocery_data canary hemkop --city Malmö
```

Willys-canaryn begränsar sig till en kategori, en katalogsida och fem produkter.
ICA-canaryn hämtar en onlinefiltrerad butikssida och en publik offersida.
Coop-canaryn hämtar de 7 respektive 13 verifierade bootstrap-butikssidorna, väljer
första erbjudandeaktiverade butik och öppnar dess fysiska erbjudandesida i en färsk
vanlig Chromium-session. Den verifierar slutlig URL och rubrik, stoppar vid challenge
och accepterar endast ett explicit totalmatchat eller upprepat DOM-stabilt kortset.
Den gör ingen dynamisk store-locator-sökning, onlinekatalogtraversering eller snapshot-
promotion. City Gross-canaryn använder vanlig publik JSON, hämtar två butikskällor och
exakt en femprodukterssida. Den kräver korrekt store-context, pagination,
schemafingerprint och minst 95 % parse success, men är alltid begränsad och kan
aldrig ärva full-crawl-authority. Malmö Hyllie fungerar; Lund stoppar eftersom
ingen katalogberättigad Lund-butik finns. Canaryerna sparar den lilla sanerade råresponsen.
Hemköp-canaryn aktiverar en publik onlinebutik i en färsk anonym session,
verifierar readback/store-facet och hämtar exakt en kategori och en femprodukters-
sida. Den saknar alltid full-crawl-authority. Lidl-canaryn hämtar en enda sida
med fem rader ur den nationella publika offerytan; den tillskriver aldrig dessa
priser en fysisk butik och promotar ingen snapshot.

Avbryt och utred vid 403, 429, CAPTCHA/login, oväntad content type eller
schemaändring. Försök inte maskera klienten eller kringgå spärren.

## Daglig körning

En körning per dygn räcker. `collect-all` bygger sin plan från de centrala
source-rollerna och kör varje OWN connector/context isolerat. Ett kedjefel
stoppar inte övriga mål och rapporten visar vilken promoterad last-known-good
snapshot som ligger kvar. Kommandot kontaktar aldrig Primat och använder ingen
fallback:

```powershell
python -m grocery_data collect-all --city Lund --city Malmö
```

Lidls nationella offerkontext schemaläggs högst en gång även när två städer
begärs; den dagliga körningen traverserar hela den deklarerade publicerade
offerytan men klassar den fortsatt `OFFERS_ONLY`. City Gross Lund hoppas över
eftersom ingen OWN-kontext verifierats där. Coops fysiska offers-jobb förblir
stadsvisa, medan den regionala fullkatalogen `730400` dedupliceras till ett enda
review-gated basketjobb även om både Lund och Malmö begärs. Den körs endast med
`COOP_ALLOW_FULL_CRAWL=true` och exakt `COOP_ONLINE_CONTEXT_IDS=730400`.
Exempel för cron på en server där miljön laddas från en skyddad systemfil eller
tjänstekonfiguration:

```cron
15 02 * * * cd /srv/grocery-project && /srv/grocery-project/.venv/bin/python -m grocery_data collect-all --city Lund --city Malmö >> /var/log/grocery-data.log 2>&1
```

Lägg inte hemligheter eller crawl-opt-in direkt i crontab. City Gross och Hemköp
får endast köras brett när ansvarig operatör uttryckligen har aktiverat respektive
`REVIEW`-flagga och allowlistat exakt verifierad context.
Kedjespecifik concurrency och rate limit ska vara konservativa.

## Raw snapshots, replay och lineage

Råpayloaden sparas före parsern under ungefär:

```text
raw_snapshots/
  willys/
    <external-store-id-or-chain>/
      <snapshot-id>/
        <timestamp>_<index>_<kind>_<document-id>.json
```

Filer skapas exklusivt och skrivs inte över. Databasen sparar bland annat:

- kedja och extern butik;
- requesttyp, metod, sanerad URL/query och HTTP-status;
- hämtningstid, content type, payloadhash och sökväg;
- connectorversion, sidnummer och schemafingerprint;
- koppling till collector run och katalogsnapshot.

Headers, cookies, CSRF-token och authorization sparas inte. Secret-/
sessionsformade fält i JSON maskeras innan payloaden läggs på disk. Den
sessionbundna Willys-CSRF-tokenen används endast i klientminne.

Varje `SourceProduct`, normaliserad produkt, prisobservation, promotion och
parser failure pekar tillbaka till raw snapshot och katalogsnapshot. Parser-,
connector- och normalizer-version sparas så att en rad kan reproduceras.

## Quarantine och observability

Poster som saknar nödvändiga fält eller bryter schema försvinner inte. De skrivs
till `parser_failures` med stabil felkategori och raw reference. Pris-sanity
stoppar omöjliga värden; extrema men möjliga värden ger varning för granskning.

Health jämför med senaste aktiva baseline och mäter bland annat:

- produktantal och produktfall;
- parse success rate och quarantine;
- pris-, GTIN- och package coverage;
- andel okänd köpmodell;
- request-, HTTP- och 429-antal;
- runtime;
- schema paths, typer och strukturell diff.

Standardtrösklar degraderar vid mer än 30 % produkttapp, bryter vid mer än 70 %,
degraderar under 95 % parse success, bryter under 70 %, och degraderar vid över
20 % saknade priser. En material schemaändring är synlig även när HTTP svarar
200. `ConsoleAlertSink` skriver allow-listad, secret-redigerad JSON; stora
payloads loggas inte.

Collectorns körlivscykel skrivs dessutom som `collector_started`,
`collector_finished` och `collector_failed` i strukturerade JSON-rader. Schemat
är en strikt allow-list med kedja, scope, snapshot-id, produkt-/fel-/requestantal,
runtime och status. Source payloads, headers, undantagsmeddelanden, DSN:er och
godtycklig context kan inte läggas i eventet. `CollectorEventSink` kan injiceras
i tester och andra körmiljöer för att ersätta standardens
`ConsoleCollectorEventSink`.

## Last known good och atomisk promotion

Snapshots går genom:

```text
FETCHED -> PARSED -> VALIDATED -> HEALTH_CHECKED -> PROMOTED
                                         |
                                         +-> REJECTED
```

Promotion byter aktiv snapshot i en databastransaktion per kedja och scope.
Lund och Malmö kan därför ha separata aktiva snapshots, och core-arkitekturen behåller
senaste goda data när en ny kandidat underkänns. För Coop är både den fysiska
`OFFERS_ONLY`-kanalen och den separata regionala fullkatalogen raw-first och
replaybara. Fullkatalog `730400` reproducerade 11 175 produkter med noll
nätverksanrop; kritiskt schemafel, avvisad kandidat, bevarad LKG, lokal parserfix,
offline replay och efterföljande promotion är verifierade. API:t visar alltid
age/status; stale data blir aldrig en tyst fallback.

## API och statusgränssnitt

Starta API:t på en separat port från måltidsappen och peka det mot samma databas
som collectorn:

```powershell
python -m uvicorn grocery_data.app.main:app --env-file .env --host 127.0.0.1 --port 8010
```

Öppna:

- `http://127.0.0.1:8010/` — enkel connectorstatus;
- `http://127.0.0.1:8010/admin/connectors/willys` — runs, metrics,
  allow-listade felsamples, schemafingerprint och strukturell schema-diff;
- `http://127.0.0.1:8010/docs` — OpenAPI.

Konsument-API:

| Endpoint | Syfte |
| --- | --- |
| `GET /stores` | Filter på kedja, stad, Lund/Malmö-postnummer och onlinehandel. |
| `GET /stores/{id}` | En butik med freshness. |
| `GET /products/search` | Sök namn/brand/canonical food och filtrera på butik/kedja. |
| `GET /products/{id}` | Normaliserad produkt med source metadata/confidence. |
| `GET /prices` | Paginerade aktiva prisobservationer. |
| `POST /prices/query` | Bulkfråga för butik, produkt, canonical food eller kedja. |
| `GET /catalog/{store_id}` | Produkt-/offer-rader från aktiv snapshot, paginerade; response coverage avgör om underlaget är full katalog, partial eller offers-only. |
| `GET /offers` | Aktiva strukturerade promotioner. |
| `GET /health` | Samlad tjänstehealth. |
| `GET /health/connectors` | Samtliga connectorer. |
| `GET /health/connectors/{chain}` | Detaljstatus, senaste runs och felgrupper. |
| `GET /sources/status` | Basket-/offer-/fallbackstrategi, OWN-snapshot eligibility och explicit fallbackpolicy för alla kedjor. |

Katalog- och bulkendpoints stöder `limit`/`offset`. Response metadata innehåller
`snapshot_id`, `observed_at`, `data_age_hours`, `connector_status` och coverage.
API:t publicerar produkter från aktiva snapshots, inte en halvfärdig run.
Store-, produkt-, pris- och offerrader behåller de platta `source_*`-fälten och
har dessutom ett additivt `source`-objekt med provider, channel, snapshot,
observationstid, coverage, price context och `fallback_used`.
Varje produktpost från sök, produktdetalj och katalog innehåller dessutom ett
`lineage`-objekt med `source_snapshot_id`, opakt `raw_snapshot_id`,
`parser_version`, `normalizer_version` och `observed_at`. Rå-URL, query,
payloadplats, source fields och råpayload exponeras inte i konsument-API:t.

## Användning från måltidsoptimeraren

`backend/app/providers/own.py` implementerar `OwnGroceryPriceProvider` bakom
samma `GroceryPriceProvider`-interface som Primat. Starta grocery-data-API:t och
sätt följande för måltidsappens process:

```dotenv
PRICE_PROVIDER=federated
OWN_GROCERY_BASE_URL=http://127.0.0.1:8010
OWN_GROCERY_MAX_AGE_HOURS=48
OWN_GROCERY_INCLUDE_OFFERS_ONLY=false
PRIMAT_API_KEY=<server-secret>
MAX_PRICE_AGE_HOURS=48
ALLOW_PROVIDER_FALLBACK=false
OWN_SOURCES_ONLY=false
```

Som standard accepterar providern bara verifierat komplett
`full_catalog`/`full_online_catalog`, en aktiv
promoterad snapshot, `healthy` connectorstatus och data inom åldersgränsen. Explicit
`OWN_GROCERY_INCLUDE_OFFERS_ONLY=true` gör offer-rader synliga för enrichment men
klassar inte butiken som komplett för en matkasse. Providern avvisar stale, degraded,
broken och ofullständigt freshness-underlag; den faller inte tyst tillbaka till Primat
eller Mock.

`PRICE_PROVIDER=federated` skapar en enda `GroceryPriceProvider` över de
strategikonfigurerade OWN- och Primat-boundaries. Primat krävs fortfarande för
ICA/Lidl i normal sex-kedjedrift, men inte för Coops verifierade onlinecontext.
`OWN_SOURCES_ONLY=true` är ett explicit testläge som utesluter
externa providers och kräver `OWN_GROCERY_BASE_URL`; `ALLOW_PROVIDER_FALLBACK=true`
tillåter bara deklarerade
fallbacks och varje sådan observation märks `fallback_used=true`. Standard är
fail-closed utan fallback.

Kedjestrategin är separat och explicit:

| Kedja | Katalog-primary | Own-roll |
| --- | --- | --- |
| Willys | OWN | Full katalog; Primat är konfigurerad secondary men kräver explicit fallback. |
| ICA | Primat | Offers plus diagnostiskt registry-enrichment. |
| Coop | OWN | Coop Online Syd `730400`, `FULL_ONLINE_CATALOG`; fysiska OWN-offers separat; Primat kräver explicit fallback. |
| City Gross | OWN | Full onlinekatalog för Hyllie; Own-offers; Primat kräver explicit fallback. |
| Hemköp | OWN | Full onlinekatalog för separat aktiverade och promoterade store-contexts, inklusive Malmö Triangeln samt Lund Brunnshög och Karhögstorg; Primat kräver explicit fallback. |
| Lidl | Primat | Nationell OWN-offeryta (`OFFERS_ONLY`); aldrig basketkatalog. |

Coop Online Syd räknas som ett enda köpcontext även när flera fysiska pickup points
delar det. Ett fysiskt Coop-erbjudande behåller egen OWN-lineage och skapar inte en
andra basketbutik. Primat kompletterar eller ersätter aldrig OWN tyst; explicit
fallback behåller provider- och `fallback_used`-provenance.

## Jämförelse med Primat

Det offline-testbara jämförelseverktyget tar två explicita JSON-/JSONL-exporter:

```powershell
python -m grocery_data compare-primat `
  --store "Willys Lund Nova" `
  --own-export artifacts/willys-own.json `
  --primat-export artifacts/willys-primat.json `
  --sample-limit 10
```

`--store` är rapportens scope/etikett; verktyget filtrerar inte automatiskt två
olika källors interna butik-ID:n. Exporterna ska därför redan avse samma butik.
En export får vara en produktlista, JSONL eller ett objekt med `products`,
`items`, `results`, `data` eller `catalog`. Den egna exporten kan exempelvis
vara svaret från `GET /catalog/{store_id}`. Primat-exporten ska skapas separat
med den befintliga, auktoriserade Primat-integrationen och dess anropsbudget.

Matchning sker kollisionssäkert i följande ordning:

1. giltigt GTIN/EAN;
2. kedja + externt produkt-ID;
3. normaliserat varumärke + produktnamn + explicit förpackning.

Ambigua nycklar matchas inte. Rapporten innehåller antal produkter, matchmetod,
pris-, jämförpris-, paket-, försäljningsmodell- och kampanjavvikelser samt ett
begränsat sample. Jämförpris används aldrig för att skapa paketstorlek.
Kommandot gör inga nätanrop, initierar ingen provider och läser inte `.env`.

Detta är diagnostik, inte en atomisk hämtning: operatören ansvarar för att
exporterna avser samma butik och jämförbara observationstider. En Primat-
avvikelse är en utredningssignal, inte automatiskt bevis på att någon viss källa
är fel.

## Coops onlinekatalog och fysiska offers

Coop har två uttryckligen separata OWN-kanaler:

- online context `730400`: Resultat A, promoterad `FULL_ONLINE_CATALOG` och
  basket-primary;
- fysiska butikssidor: `OFFERS_ONLY`, aldrig full katalog i sig.

Fullkatalogen traverserar en verifierad category tree utan keyword brute-force.
Efter strikt sentinel-/leaf-hantering fullföljdes 748 terminalkategorier och 822
sidor. Unionen innehåller 12 380 råa kategorirader, 11 175 unika produkter och
1 205 säkra cross-category-overlaps, med noll konflikter. Priscoverage är
100,00 %, giltig GTIN 99,50 %, package quantity 99,20 % och resolved purchase
model 99,28 %. Recipe coverage är 48/45/39 av 48 för >=1/>=3/>=5 kandidater,
och den representativa korgen är komplett 13/13. Snapshot
`851d317e88ce422b90d80d26ca1ebb2b` replayades med noll nätverksanrop och är
atomiskt promoterad.

`730400` modelleras som **Coop Online Syd**, inte som Stora Coop Lund. Den
verifierade Lund-länken är physical `2696` -> pickup `257611` -> online context
`730400`; priserna presenteras som onlinepris. Flera pickup points som delar
samma context skapar aldrig fler köpcontexts, och Mårtenstorget saknar en sådan
verifierad länk.

OWN-offerconnectorn använder de verifierade, seedade bootstrap-pathsen för 7 Lund-
och 13 Malmö-butikssidor, gör vanliga GET-anrop mot dem och deduplicerar deras
`storeID`. Detta är avsiktligt separat från store-coverage-flödet: den bounded
officiella discovery-adaptern använder Coops publika locator som en vanlig besökare,
kräver dess deklarerade stadstotal, följer varje synlig detaljsida och bevarar både
`storeID` och `ledgerAccountNumber`. Locatorflödet kan därmed upptäcka att den
fysiska listan ändrats utan att hämta produktkatalog eller göra offerconnectorn
dynamisk.
Fysiska erbjudandesidor fångas med färsk Chromium, strikt store-contextkontroll,
challenge-stop och sanerad DOM-stability-evidence när sidan saknar source-declared
total. Cookies, browser storage och runtime-clientvärden sparas aldrig.

Offline verifiering omfattar parser/normalizer-replay av sparat erbjudande med noll
nätanrop, konservativ GTIN-identitet, quantity- och medlems/multibuy-semantik samt
schema-quarantine. Liveinsamling av den deklarerade `OFFERS_ONLY`-ytan är verifierad
för Lund (7/7 butiker, 322 offer-rader) och Malmö (11/13 butiker med verifierad
offerkontext, 494 offer-rader). Båda parser-v2-snapshotsen är atomiskt promoterade och
reproducerades exakt från raw data med noll nät- och browseranrop. En simulerad
Coop-parserbreak, avvisad kandidat, bevarad last-known-good och connector-local repair
är dessutom verifierade i databasacceptanstestet. Den fysiska offerytans counts får
fortfarande inte användas som katalogbevis; full-basket eligibility kommer enbart från
den separata healthy/fresh/promoterade `730400`-snapshoten.

## Lund store coverage och frivilliga hyllprissticksprov

Officiell butiksdiscovery är en separat, bounded operation och hämtar ingen
produktkatalog. Kör `python -m grocery_data audit-store-coverage --city Lund`
för att jämföra officiella fysiska butiker, exact-länkade pris-contexts och
basket-/offer-eligibility. `PhysicalStore` och `GroceryContext` är separata
many-to-many-identiteter: en fysisk butik kan sakna pris-context och ett regionalt
eller online fulfillment-context kan täcka mer än en fysisk butik.

Den strikt adress-/ortavgränsade Lund-discoveryn 2026-08-23 gav 23 fysiska
butiker:

| Kedja | Fysiska Lund-butiker |
| --- | ---: |
| Willys | 3 |
| Hemköp | 2 |
| ICA | 9 |
| Coop | 7 |
| Lidl | 2 |
| City Gross | 0 |

Staffanstorp och andra närliggande orter märks inte om som Lund. Lidls
nationella/regionala OWN-offercontext tillskrivs inte en viss fysisk Lidl-butik,
och Malmö Hyllie importeras inte som City Gross Lund.

### Historiskt Phase-C-resultat 2026-08-23 — bevarat

Phase-C-kandidatens dåvarande OWN-only benchmark passerade alla quality-,
provenance-, freshness-, no-network- och immutable-DB-grindar:

| Scenario | Resultat |
| --- | ---: |
| 13 varor, `max_stores=1` | 13/13, 331,30 kr |
| 13 varor, `max_stores=2` | 13/13, 323,76 kr |
| 13 varor, `max_stores=3` | 13/13, 323,76 kr |
| 5 recept × 4, BALANCED, `max_stores=2` | PASS, 251,58 kr |

Den dåvarande Primat v2-contextbootstrapen stoppade fail-closed på
`identity_no_exact_match_coop`. Offlineaudit hittade ingen säker bundle eller
exakt Primat Lund-länk att importera, så något nytt federerat numeriskt resultat
rapporterades i den körningen. Resultatet ovan är historik och har inte skrivits
om efter att Karhögstorg och två ICA-contexts blev basketberättigade. Det
historiska OLD-resultatet är ofullständigt på `yellow_onion` och har
`total=null`; ingen numerisk old/new-delta fabriceras.

### Historiskt price-context-slutläge 2026-08-24 före Coop Result A

`python -m grocery_data audit-price-contexts --city Lund` förklarar nu samtliga
23 fysiska butiker med exakt ett tillstånd: `physical=23`, `explained=23`,
`unknown=0`, `basket=6`, `offers=0`, `stale=14`, `mapping_unresolved=2` och
`no_price_context=1`. Auditen använder den konfigurerade 48-timmarsgränsen;
`STALE_CONTEXT` betyder att contextet finns men inte får användas i basketen.

| Kedja | Fysiska | Verifierat tillstånd | Basket |
| --- | ---: | --- | ---: |
| Willys | 3 | 2 × `OWN_FULL_CONTEXT`; Stortorget `2863` × `NO_PRICE_CONTEXT` | 2 |
| Hemköp | 2 | Brunnshög + Karhögstorg × `OWN_FULL_CONTEXT` | 2 |
| ICA | 9 | 2 × `EXTERNAL_FULL_CONTEXT`; 7 × `STALE_CONTEXT` | 2 |
| Coop | 7 | 7 × `STALE_CONTEXT` | 0 |
| Lidl | 2 | 2 × `MAPPING_UNRESOLVED` | 0 |
| City Gross | 0 | `NO_LUND_CONTEXT`; Malmö Hyllie importeras inte | 0 |
| **Totalt för de 23 butikerna** | **23** | 4 own full + 2 external full + 14 stale + 2 unresolved + 1 no context | **6** |

De två accepterade externa basket-contexten är
`physical:ica:1004409` → `primat:ica:1004409` (ICA Kvantum Malmborgs
Clemenstorget) och `physical:ica:1088004` → `primat:ica:1088004` (Maxi ICA
Stormarknad Gunnesbo). Båda har `EXACT_ID`, `VERIFIED`, `FULL_CATALOG` och en
färsk aktiv basketlänk; bounded smoke gav 4/4 respektive 90/90 prissatta rader
med full provenance.

Coops sju Primat-identiteter kunde verifieras med `EXACT_ID`, men deras
provider-contexts är endast `OFFERS_ONLY` och aldrig basketberättigade. Den
separata OWN-offerevidensen var dessutom för gammal i denna audit, vilket ger
det sanningsenliga aktuella tillståndet `STALE_CONTEXT`, inte full katalog.
Detta beskriver den frysta 2026-08-24-auditen. Från 2026-08-25 kommer Coops
basketcoverage i stället från det separat promoterade regionala OWN-onlinecontextet
`730400`; det ska inte räknas som sju butiksspecifika contexts eller som hyllpris.
Lidls Primat-kandidater fick ingen stark fysisk identity-länk: `0163` är
`NONE`, `0303` endast `PROBABLE`, och namnlikhet är suggestion-only. Regionala
OWN-erbjudanden tilldelas fortfarande inte som butiksspecifika priser; därför
är båda fysiska Lidl-butikerna ej basketberättigade och `MAPPING_UNRESOLVED` i
denna verifierade audit.

### Verifierad OWN-only och federerad benchmark 2026-08-24

Benchmarken läste enbart promoterade lokala snapshots och gjorde noll live-
anrop under optimeringen. Alla quality-, provenance-, nutrition-, diversity-
och basketgrindar passerade.

| Scenario | Valda contexts | Resultat |
| --- | --- | ---: |
| 13 varor, `max_stores=1` | Willys Lund | 13/13, 340,30 kr |
| 13 varor, `max_stores=2` | Hemköp Karhögstorg + Willys Lund | 13/13, 329,30 kr |
| 13 varor, `max_stores=3` | Hemköp Brunnshög + Karhögstorg + Willys Lund | 13/13, 326,36 kr |
| CHEAPEST 5 × 4, `max_stores=1` | Willys Lund | 225,74 kr / 11,29 kr per portion |
| CHEAPEST 5 × 4, `max_stores=2` | Karhögstorg + Willys Lund | 194,04 kr / 9,70 kr per portion |
| BALANCED 5 × 4, `max_stores=1` | Karhögstorg | 270,87 kr / 13,54 kr per portion |
| BALANCED 5 × 4, `max_stores=2` | Karhögstorg + Willys Lund | 236,68 kr / 11,83 kr per portion |
| VARIED 5 × 4, `max_stores=1` | Karhögstorg | 271,73 kr / 13,59 kr per portion |
| VARIED 5 × 4, `max_stores=2` | Karhögstorg + Willys Lund | 238,72 kr / 11,94 kr per portion |

Den efterföljande federerade frozen-replayen reproducerade **exakt samma valda
contexts, totals och recept** för samtliga nio scenarier i tabellen. OWN →
federerad delta är därmed 0,00 kr i varje 13-varukorg och menyplan. De två
ICA-contexten var eligible och övervägdes av optimeraren, men valdes i 0
shoppingrader; providerpreferens påverkade inte ekonomin.

Den credential-fria frozen-cachen samlades med exakt 49 godkända requests: 1
store resolve + 48 produktrequests, 49 × HTTP 200, 0 denied, 0 retry och 48/48
icke-tomma ingrediensfrågor. Den innehåller 1 863 produkter för exakt
`primat:ica:1004409` och `primat:ica:1088004` och har SHA-256
`399944820a33a875ad7b15a5bbf676c64400b1d223537602b92ccf9c0a51d508`.
Kandidatdatabasen var oförändrad efter collectorn.

Hela federerade acceptansmatrisen passerade med 0 nätförsök under benchmarken,
oförändrad immutable databas och runtime 1 063,0382 sekunder. Store-gaten
representerade Hemköp, ICA och Willys; Coop och Lidl var fullt förklarade men
ej basketberättigade och City Gross var `NO_LUND_CONTEXT`. BasketAuditor,
nutrition, diversity, full provenance och totalreconciliation passerade. Inga
member-only- eller fallbackrader användes.

Identity-flödet är store-för-store och replaybart i stället för att kräva
att alla kedjor matchar i en enda export. Efter den separat godkända, bounded
store-capture-körningen mappas filen offline:

```powershell
py -3.12 -m grocery_data map-primat-stores `
  --city Lund `
  --database .lund_phase_c_20260823.sqlite `
  --input <primat-store-discovery-bundle-v1.json>
```

Endast `exact_id`, `exact_address`, `exact_name_and_postal` och unik
`strong_geo` kan aktiveras. Fuzzy namn är suggestion-only; ambiguous och none
sparas som `unresolved`. Provider-ID-/adressdrift flaggas som `mapping_drift`
och behåller LKG-länken. Kommandot gör noll nätanrop.

En identity-länk är initialt inte basket-capable. Ett separat bounded
produkt-/prissmoke måste först skapa en sanerad
`primat-context-smoke-bundle-v1`, som sedan replayas offline:

```powershell
py -3.12 -m grocery_data verify-primat-context-smoke `
  --city Lund `
  --database .lund_phase_c_20260823.sqlite `
  --input <primat-context-smoke-bundle-v1.json>
```

Endast en fortfarande verifierad mapping med oförändrad identity, komplett
catalog coverage, minst en prissatt produktrad och korrekt Primat-provenance får
då `basket_eligible=true`. Inga manuella hyllprisobservationer krävs.

Manuella observationer via
`record-physical-price`, `physical-price-report` eller `/physical-check` är
endast extra valideringsevidens; de skriver aldrig över katalogpris och krävs
aldrig för normal användning. Phase-C-körningen hade 0 fysiska observationer
och benchmarkresultatet ovan blockerades inte. Det fulla kontraktet finns i
[store coverage and optional physical validation](../docs/store_coverage_and_physical_validation.md).

## Tester

### ICA:s inkrementella register

ICA:s säkra publika katalogcoverage är fortsatt `OFFERS_ONLY`. Plattformen har även ett
separat persistent produktregister som deduplicerar global ICA-produktidentitet, sparar
butiksspecifika prisobservationer och bevarar discovery-lineage från SSR, kategori,
sökning och erbjudanden. Registret är diagnostiskt och historiskt; det etiketteras aldrig
som en komplett katalog utan bevisad traversal.

Registry-API:

```text
GET  /registry/ica/stores/{store_id}/stats
GET  /registry/ica/products/{external_product_id}
POST /registry/ica/stores/{store_id}/basket-coverage
```

Pris- och metadataålder exponeras separat. Query-level basket coverage kräver att varje
efterfrågad canonical ingredient har en färsk, semantiskt och mängdmässigt godtagbar
prisobservation. Standardprovidern fortsätter att behandla ICA som offers-only; ingen
tyst opt-in till full butik sker.

Browserdiagnostiken använder vanlig Chromium, liten budget och stoppar omedelbart vid
WAF/CAPTCHA/Human Verification. Den sparar aldrig cookies eller browser storage och gör
inga bypassförsök.

Alla normala tester är offline och använder fixtures/SQLite:

```powershell
python -m pytest grocery_data/tests backend/tests/test_own_provider.py
```

Hela repositoryts suite:

```powershell
python -m pytest
```

Lint och compilation:

```powershell
python -m ruff check grocery_data backend/app/providers/own.py backend/tests/test_own_provider.py
python -m compileall -q grocery_data backend/app/providers/own.py
```

Willys-fixtures finns i `app/connectors/willys/fixtures/` och täcker fast paket,
lösvikt, styckvara, variabel vikt, medlemserbjudande, multipack, saknad GTIN och
schemaändring. Testerna verifierar även immutabel raw capture, redaction,
replay utan nät, quarantine, schema-diff, prishistorik, scope-isolering, atomisk
promotion och att en trasig run behåller last known good.

## HOW TO FIX A BROKEN CONNECTOR

1. Kör `python -m grocery_data health` och öppna
   `/health/connectors/<chain>`. Notera status, aktiv last-known-good snapshot,
   run metrics, schemafingerprint och de vanligaste felkategorierna.
2. Promotera inte den trasiga runnen. Kör `diff` mellan senaste fungerande och
   den nya kandidat-snapshoten för produktfall, prisförändringar och package-
   coverage.
3. Leta upp representativa raw records via `raw_snapshots`-metadata. Inspektera
   den sparade payloaden; gör inget nytt nätanrop för att reproducera felet.
4. Lägg ett litet, sanerat realutdrag som ny fixture under just
   `app/connectors/<chain>/fixtures/`. Ta bort cookies, tokens, session-ID:n och
   personlig data.
5. Uppdatera endast kedjans parser/client om källkontraktet ändrats. Behåll
   `SourceProduct`- och API-kontrakt om de fortfarande uttrycker samma fakta.
6. Lägg ett regressionstest för nya formen och kör connectorns parser-,
   normaliserings-, promotion- och quantity-test offline.
7. Kör `replay --chain <chain> --snapshot-id <id>` utan `--promote`. Bekräfta
   `network_requests: 0`, parse/quarantine, schema-diff, köpmodeller och priser.
8. Diffa replay-snapshoten mot last known good. Granska särskilt produktantal,
   saknade priser, package confidence och oväntade prisförskjutningar.
9. Promotera först en `HEALTHY`, `HEALTH_CHECKED` snapshot. Kör därefter en liten
   opt-in canary och låt nästa schemalagda collect bekräfta livekontraktet.

Använd `--accept-schema-change` först när steg 3–8 visar att ändringen är
förstådd. Flaggan är aldrig en genväg runt en okänd källändring.
