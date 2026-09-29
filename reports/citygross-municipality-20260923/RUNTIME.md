# Isolerad City Gross-drift: verklig runner, publicering och reload

**PASS inom uttrycklig `OWN_SOURCES_ONLY=true` för Malmö.** Slutkodens två ordinarie rebuilds/publiceringar/reloads behåller exakt samma 13 523 City Gross-produktposter, prisvillkor och originalobservationer. Denna privata instans är inte ett fullständigt federerat Malmö-prov: aktuell komplett Malmö-Primatbas saknas, och ingen grannkommuns bas har lånats. Inget har aktiverats i produktion.

[Maskinellt slutresultat](runtime-final/ACCEPTANCE.json), [körbar verifierare](runtime_verify.py) och de sex `runtime-final/result-*.json` innehåller kvittenser, tillstånd, produkt-/kodhashar och nätmätning. Tio berörda kodfiler har identiska hashar i slutkodens faser och matchar filerna på disk vid sammanställningen.

## Vad som faktiskt kördes

Verifieringen använde Python 3.12 lokalt, separat SQLite/datamapp `runtime-final`, egen applikationsprocess på loopback-port 18763, eget operationslås samt separat persistent kommun- och uppdateringstillstånd. Varje fas startade en ny verklig serverprocess. `deploy/scripts/run_daily_refresh.py:main` körde den ordinarie låsta vägen, startade en verklig subprocess med `grocery_data.__main__.main(... daily-refresh ...)`, validerade/publicerade den riktiga artefakten och anropade den riktiga HTTP-routen `/api/admin/reload-price-universe`. `health` och `ready` gav 200 i samtliga faser.

Källtransporten var uttryckligt replayad eller injicerat fel. Harnessens subprocess-wrapper byter endast insamlingscallback till en hashkontrollerad kopia av den redan godkända, oförändrade OWN-databasen; builder, rad-/artefaktvalidering, lås, publicering, kvittenser och HTTP-reload är ordinarie komponenter. Separat slutlig parserreplay från originalråsvar finns i [final-v4-replay-1280/coverage.json](final-v4-replay-1280/coverage.json). Ingen källstrategi eller prissättare injicerades.

| Fas | Kodstatus | Verifierat resultat | Tid |
|---|---|---|---:|
| `first` | Mellanversion före slutlig provenancejustering | Första kommunstyrda source-job med replay, riktig rebuild/publicering/reload; 13 523 poster. | 437,266 s |
| `second` | Mellanversion före slutlig sökdelegation | Andra ordinarie rebuild via behovsrunner, med beständigt källunderlag; 13 523 poster. | 459,594 s |
| `restart` | Föregående sökversion; separat kodhash | Ny verklig app-/runnerprocess läste sparat kommunval och aktiv artefakt; full rebuild/publicering/reload, oförändrade priser och observationer. | 410,437 s |
| `not_due` | Slutkod | Riktig `main` efter processomstart returnerade `not_due`; ingen childprocess, insamling, rebuild eller reload startades. | 12,266 s |
| `fetch_fail` | Slutkod | Injektion av hämtfel för den valda butiken. Giltig LKG behölls och genomgick en full ordinarie rebuild/publicering/reload. | 71,328 s |
| `recovery` | Samma slutkod | Godkänt källunderlag återspelades utan ny observation. Full ordinarie rebuild/publicering/reload med exakt samma prispostsignatur. | 73,454 s |

Alla refreshfaser gav exit 0; alla publikationer fick separat `reloaded`-kvittens. Vid hämtfel betyder exit 0 att giltig LKG kunde byggas och serveras: källfelet finns kvar synligt i butikens `last_outcomes` och `selection` med `status=failed`, `failed_attempts=1` och nästa försök 23 september 08:55:14Z. Efter återhämtningen är butikens status `success`, felräknaren 0 och nästa ordinarie hämtning åter 23 september 21:00Z. Kommunvalet `1280`/Malmö lästes från disk efter första fasen; miljövariablerna för enabled/kommunkod togs bort inför följande processstarter.

`fetch_fail` och `recovery` är de två jämförda **slutkodsbyggena**. `first`, `second` och `restart` räknas inte som identiska slutkodskörningar. Ursprunglig orkestreringsprocess hade den gamla jämförelsen av alla sex faser laddad; den fick därför ett förväntat slutassert när första mellanversionens provenance skilde sig. Ingen driftfas misslyckades av detta. Den uppdaterade `summarize` kördes separat utan nya rebuilds och verifierade slutkodshashar, de två publicerade byggena, not-due-resultatet och observationernas identitet.

## Prisernas identitet och ålder

- Exakt butik: Hyllie, `storeNumber=3211`, fysiskt `siteId=169`, kommun `1280`; kontext `context:citygross:33b01007b20e8988`. Priskontexten är `online_store`; OWN:s provenance har `source_channel=catalog`, `source_role=basket` och `coverage=full_online_catalog`. Det är butikens onlinekatalog, inte fysisk hyllkant.
- Godkänd slutlig replay-snapshot: `0a15ea92d769401dab73d15b884749c8`.
- PriceUniverse-ID: `price-universe:b5b95975eb188cc8bb46ed1bf4f5a18749aeaa2a7dc585c8c27acb3157cbe8c7`.
- Slutkodens fulla produkt-/prispostsignatur: `aab2db7f01f4ef1e2423a2cedaa27167ac3ef6465295e8ccd781aad3f0eaec16`.
- 13 523 produkter finns i artefaktens fulla produktlista. Runtimens `product_count=464` avser urvalet efter pruning och `canonical_index_count=57`; dessa mått är olika och inget är antal godkända receptköp.
- Originalobservationerna är fortfarande **23 september 08:04:51.365362Z–08:07:07.369337Z**. `last_success` är fortfarande den äldsta originalobservationen även efter återhämtning. Inga insamlings-, pris- eller kampanjdatum har föryngrats.

HTTP-reload laddar och validerar diskens kandidat och byter runtime även när samma käll-/universe-ID används. `changed=false` i svaret är en jämförelse av ID, inte ett besked om att omladdning hoppats över. Ny process kräver dessutom den aktiva, hashverifierade artefakten vid uppstart efter första publiceringen.

## Nät, förfall och avgränsningar

Den ursprungliga Hyllie-insamlingen gjorde **136 verkliga kataloganrop**, separat från driftprovet. Slutlig parserreplay och samtliga driftfaser gjorde **0 externa pris-/kedjeanrop**. Nätspärren tillät endast loopback i harness, CLI-child och server. Parent och varje körd CLI-child registrerade 0 blockerade externa anslutningsförsök. Lokala HTTP-/ASGI-anrop är inte externa kedjeanrop. `not_due` startade ingen CLI-child alls; dess 12 sekunder inkluderar den nya privata appens uppstart och lokala kontroller.

Förfall verifierades med en **explicit framtida testklocka +49 timmar**, inte genom att skriva om källtider eller flytta maskinklockan. Både källplanen och den återlästa publicerade artefakten prövades: status blev `stale`, användbara kontexter 0 och Hyllie-kontexten blev utesluten. Källplanen markerade arbete förfallet och ändrade färskhetsfingeravtryck. Detta är ett runtime-/planeringsprov med injicerad tid, inte ett nytt livehämtförsök vid den framtida tidpunkten. Kampanj-, köptaks-, matcher-/checkout-/auditprov redovisas separat i [TESTS.md](TESTS.md) och [PURCHASES.md](PURCHASES.md).

Hämtfelet är också uttryckligt injicerat, inte ett påstått City Gross-driftfel. Återhämtningen använder bevarad aktuell källevidens, inte en ny livehämtning. Den verkliga nätinsamlingen, rådatareplayen, det injicerade felet och ordinarie rebuild/publicering/reload går därmed att särskilja i rapporterna.

Åtta fokuserade [refresh-wiringtester](../../backend/tests/test_citygross_refresh_wiring.py) passerade med Python 3.12. De täcker vidarebefordran genom ordinarie byggare, publicerings-/reloadgränsen vid fyra utfall, beständigt kommunval och 35/48-timmarsgränser, felaktig optional-konfiguration samt kommunbehov utan nätanrop. Ruff och compileall passerade för harness och tester.

Ingen aktiv produktionsdatabas, Windows-inställning, schemaläggning eller annan kedjas driftval ändrades. Malmö behöver fortfarande separat aktuell komplett federerad bas innan något fullständigt Malmö-releasebesked kan ges; se [Willys-avgränsningen](WILLYS-GAPS.md) och [City Gross-releaseunderlaget](RELEASE-CITYGROSS.md).
