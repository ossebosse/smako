# ICA: konkret bildtolkare via Responses

Ett separat [lokalt Qwen3-VL/Ollama-alternativ](ica_flyer_local.md) använder
samma processkontrakt. Det väljs uttryckligen och faller aldrig tillbaka till
detta API. OpenAI-adaptern och dess kostnadsgrindar är bevarade.

Implementation: `grocery_data.app.services.ica_flyer_openai`, körbar process
`python -m grocery_data.scripts.ica_flyer_openai`. Den implementerar befintligt
`smako-public-flyer-page-v1` på stdin/stdout. Detta är bildanalys, inte bildgenerering.
Ingen separat prisdatabas eller prissättare införs.

## Åtkomst och beroenden

Python 3.12, projektets befintliga httpx/Pydantic/pypdf och den separata
`grocery_data/requirements-flyer-vision.txt` (PyMuPDF 1.28.2). Installera i en
isolerad miljö, exempelvis:

```sh
python -m pip install -r grocery_data/requirements.txt -r grocery_data/requirements-flyer-vision.txt
```

Septemberprovet använder befintlig scheduler-image med skrivskyddade kodmounts,
UID 10001 och en isolerad Linux-wheel. Ingen installation i produktionscontainern.
OpenAI-SDK behövs inte; adaptern använder Responses HTTP API direkt.

API-åtkomst kräver ett finansierat OpenAI API-projekt och en projektnyckel med
behörighet för Responses och vald modell, samt HTTPS till `api.openai.com:443`.
Det faktiska modell-/kontotillträdet är inte verifierat utan en nyckel.
För den sparade serverkörningen ska nyckeln läggas i
`/srv/smako/secrets/ica-flyer-openai.key`, ägare UID 10001, läge 0400.
Runnern monterar den skrivskyddat till `/run/ica-flyer-openai.key` endast när
`--use-configured-key` anges. Lägg aldrig nyckeln i Git, kommandorad, rapport eller chatt.

## Konfiguration (inga hemliga värden)

| Namn | Betydelse |
|---|---|
| `ICA_FLYER_VISUAL_COMMAND_JSON` | Befintligt driftkontrakts JSON-array: `["python","-m","grocery_data.scripts.ica_flyer_openai"]`. Ändra inte produktion nu. |
| `--visual-command-json PATH` | Collector-CLI: fil med samma array. |
| `ICA_FLYER_SOURCE_ROOT` | Tillåten rot för hämtade offentliga original-PDF:er. |
| `ICA_FLYER_VISION_CACHE` | Isolerad katalog för innehållscache och `usage.json`. |
| `ICA_FLYER_VISION_MODEL` | `gpt-4.1-mini-2025-04-14` som standard; även dokumenterad alias `gpt-4.1-mini` stöds. |
| `ICA_FLYER_OPENAI_KEY_FILE` | Skyddad nyckelfil; annars kan processens `OPENAI_API_KEY` användas. |
| `ICA_FLYER_PAID_ENABLED` | Måste vara exakt `true` för nya betalda tolkningar. Standard av. |
| `ICA_FLYER_MAX_COST_USD` | Uttryckligen godkänd totalram för cachekatalogens körningar. Standard 0. |

Förhandskontroll utan betald generering:

```sh
python -m grocery_data.scripts.ica_flyer_openai --preflight --check-access
```

Modellbyte utanför den dokumenterade listan stoppas tills bildstöd och
kostnadsgräns har lagts till med test. Med GPT-4.1 mini räknas konservativt
0,40 USD/miljon input-token och 1,60 USD/miljon output-token. Varje sida
reserverar 0,1344 USD för två pass innan anrop. Uppmätt tokenanvändning ersätter
reservationen efter lyckat svar; det är en beräknad API-kostnad, inte en faktura.
Ingen rabatt för cachade input-token räknas av. Oklara timeout-/felanrop behåller
reservationen och återförs inte automatiskt; operatören måste stämma av dem innan
ett nytt försök får debiteras. Inga betalda automatiska retries.

## Bindning, granskning och import

Programmet kontrollerar dokumentrot, SHA-256, sida och tidszon. Butik, utgåva,
käll-URL och observationstid kommer från officiell inventory, inte modellen.
Original-PDF:en renderas på nytt: hel sida, fyra överlappande förstoringar samt
första/sista sidans gemensamma villkor. Ursprunglig dokumenttext och verifierad
utgåvetitel medföljer. Dokumentinstruktioner behandlas som data, inga modellverktyg
eller externa länkar exekveras och `store=false` används.

Ett extraktionspass följs av en separat bildkontroll av produkt/pris-koppling,
prisroller och små villkor. Strikta JSON-scheman, annons-/prisrektanglar,
literalbelopp och gemensamma fel valideras. Modellens tomma osäkerhetslista är
inte ensamt ett köpgodkännande. Det första verkliga provet ska också granskas
mot originalbilderna innan större batch tillåts.

Alla prisroller och råcitat sparas, även kilopriser, procent utan belagd bas,
grupper utan GTIN och icke-livsmedel. Sådana uppgifter kan vara extraherade men
sakna konkret köpavtal. Inget GTIN, paket, restpris eller pantbelopp fylls i från
modellens bakgrundskunskap. Blandningsvillkor och ytterligare gemensamma villkor
som inte kan representeras säkert spärrar köpimport och behålls för granskning.

Entydig exakt namn-, varumärkes-, förpacknings- och villkorsöverensstämmelse kan
länka annonsen till en befintlig strukturerad kampanj. Det ger inte automatisk
variant- eller köpkvalificering. Nya poster går genom befintlig
`ica_flyer_review → SourceOffer → collector → OWN → PriceUniverse`; matchning,
näring, checkout och audit avgör senare användbarhet. Fullsnapshotens 95-procentsgrind
och radgodkända offers_only-kontrakt är oförändrade.

Pant stöds nu för belagda, GTIN-bundna offers_only-köp: belopp per behållare,
antal per förpackning och inkluderad/tillkommande pant. Tillkommande pant räknas
på samtliga köpta behållare; inkluderad pant adderas inte igen. Ett ordinarie
restköp utan separat belagd pantomfattning stoppas. Okänd pant ligger kvar i
karantän. Stödet är inte belägg för ett specifikt verkligt pantbelopp.

## Återupptagning och isolerad körning

`python -m grocery_data.scripts.ica_flyer_vision_batch --help` visar körbara
argument. Den använder befintligt gemensamt refresh-lås, parallellitet 1,
90 sekunders API-timeout/pass och 240 sekunders processgräns. Källans sidantal,
även saknade sidor, samt misslyckade butiker finns kvar i rapporten.

Cachen binder PDF, sidinnehåll, villkorskontext, schema, prompt, modell och
tolkarversion. Samma tolkning kan återanvändas mellan redan belagda butikskopplingar,
men skapar aldrig en ny butiksgiltighet. Programmet binder om källbeviset för varje
koppling. Tolkning av gammalt material ändrar aldrig prisets observationstid.
Annons-ID:n namnges med utgåva och sida för att inte krocka mellan sidor.

Batchutdata är extraktionsbevis. Import körs genom ordinarie collector med
`--extract-flyers --row-approved-offers --visual-command-json ...` och samma cache;
den är inte en egen databasimport. En aktuell release kräver färsk insamling och
vanliga 36/48-timmarsgrindar. Ingen produktionsaktivering eller schemaläggning här.

Exakta isolerade serverkommandon och faktiskt utfall:
[2026-09-19](../reports/ica-flyer-vision-20260919/README.md).

## Officiellt underlag

Kontrollerat 2026-09-19: [bildinput](https://developers.openai.com/api/docs/guides/images-vision),
[GPT-4.1 mini: bildstöd, modellversioner och priser](https://developers.openai.com/api/docs/models/gpt-4.1-mini),
[strukturerade svar](https://developers.openai.com/api/docs/guides/structured-outputs).
