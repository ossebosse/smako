# Production operations

For the public-beta Docker/Caddy deployment, durable volume layout, scheduled
refresh, backup and rollback procedures, see
[public-beta-deployment.md](public-beta-deployment.md) and
[production-backup-restore.md](production-backup-restore.md). The details below
remain the authoritative explanation of the underlying refresh/LKG semantics.

Den här körvägen använder endast promoterade lokala snapshots under själva
meal-plan-requesten. Connector- och licensierade provider-anrop tillhör den
separata dagliga insamlingsfasen.

## Daglig Lund-refresh

```powershell
python -m grocery_data daily-refresh `
  --city Lund `
  --external-cache .lund-frozen-external-v1-YYYYMMDD.json
```

Kommandot kör varje verifierad OWN-target med en egen felgräns. Ett fel för
Karhögstorg stoppar därför inte Brunnshög eller Willys. Den tidigare promoterade
snapshoten behålls som LKG och rapporteras separat som användbar eller för gammal.
Felrapporten innehåller endast allowlistade feltyper, aldrig exception-text,
cookies, headers eller tokens.

`--external-cache` måste vara en redan saniterad `lund-frozen-external-v1`-fil.
Envelopen, storleken, timestampen och förbjudna transport-/credentialfält
valideras lokalt. `daily-refresh` gör inget implicit Primat-anrop. Den befintliga
budgeterade 49-request-collectorn körs före detta steg när ett nytt licensierat
snapshot behövs; dess output får ett nytt filnamn och ersätter aldrig en tidigare
fil halvvägs.

Rekommenderad frekvens är en gång per dygn. Defaults är:

```dotenv
PRICE_AGE_WARNING_HOURS=36
MAX_PRICE_AGE_HOURS=48
MIN_SAMPLE_FOR_ACCURACY_SCORE=20
```

Freshness är exakt en av `FRESH`, `AGING`, `STALE` och `BROKEN`. Ett misslyckat
refreshförsök kan vara `BROKEN` samtidigt som dess explicit märkta LKG fortfarande
är yngre än 48 timmar.

## PriceUniverse-swap

`daily-refresh` har en explicit injektionspunkt för deploymentens lokala
PriceUniverse-builder. Hooken körs efter en lyckad basket-snapshot-promotion.
Ny key, promoterade/lokalt frysta produkter och den auktoritativa semantiska poolen
byggs och valideras före manager-låset; först därefter byts den aktiva pekaren. Ett
builder-/validatorfel verifieras lämna föregående universe objekt-identiskt. Om
composition hook saknas rapporterar CLI `rebuild_unavailable` i stället för att
låtsas att en rebuild skett.

En scheduler som delar build och aktivering över processer kan lämna över den
förbyggda, credential-fria `prepared-price-universe-v1`-artifacten explicit:

```powershell
python -m grocery_data activate-price-universe `
  --city Lund `
  --candidate .lund-price-universe-production-v1.json `
  --expected-snapshot-id <promoted-own-snapshot-id> `
  --expected-snapshot-id <frozen-primat-snapshot-id>
```

Kommandot gör noll connector-/provideranrop. Det validerar hela artifacten med
backendens auktoritativa Pydantic-modell, verifierar city/scope och varje angivet
snapshot-ID, avvisar transport-/credentialfält, skriver en content-addressed
immutabel kopia och byter därefter endast den lilla aktiva city-manifesten atomiskt.
Om schema, lineage, lagrad kopia eller validator fallerar förblir den föregående
manifestfilen byte-identisk. `PRICE_UNIVERSE_CACHE_ROOT` väljer den persistenta
artifact-/manifestkatalogen.

`daily-refresh` accepterar även `--price-universe-candidate` och
`--price-universe-cache-root` för samma validerade handoff direkt efter en promotion.
Kandidaten måste då redan innehålla exakt den nyss promoterade basket-lineagen;
annars blir status `rebuild_failed` och LKG-manifesten lämnas orörd. Den normala
långlivade deploymenten bör använda den injicerade builder-hooken så kandidaten
produceras efter insamlingen från samma promoterade/frozen provider som planflödet.

CLI-processen äger avsiktligt ingen implicit global manager och importerar inte den
privata benchmark-loadern. I en långlivad deployment injicerar composition root
samma manager och samma promoted/frozen product-loader som meal-plan-providern
använder. Det förhindrar att status och requestdata bygger två olika universum.
Den persistenta aktiva manifesten gör omstarts-handoff förklarbar; runtime laddar
artifactfilen som manifesten pekar på innan den aktiverar sitt processlokala objekt.
Composition root använder `PreparedUniverseArtifactStore.resolve_active_artifact()`;
den verifierar SHA-256 som standard och resultatet kan ges direkt till runtime-
managerns `load_file_and_activate()`.

Statusytor:

- `GET /price-universe/status?city=Lund&postal_code=22350`
- `GET /operations/daily-refresh/status?city=Lund`
- `GET /sources/status`

Ingen av dem bygger om data eller gör provideranrop.

## Fysisk validering

Fysiska stickprov är alltid frivilliga och skriver aldrig över digitala priser.
Under 20 observationer visas `insufficient_sample`/`LIMITED_SAMPLE`, inte ett
missvisande accuracy-procenttal. Från 20 observationer blir display-score
tillgänglig. Rapporter kan avgränsas till provider, kedja eller butik och delas upp
i regular, campaign, member, multibuy och weight-segment.

Karhögstorgs barcode-preview provar lagrade data i följande ordning:

1. direkt OWN-GTIN,
2. direkt extern/Primat-GTIN,
3. samma kedjas persistade detalj-GTIN kopplat via stabilt external product ID,
4. användarinitierad exakt namnsökning.

Prisfältet förifylls aldrig. Flödet gör inga bulk-detail- eller liveanrop.

## Kända, icke blockerande Lund-gap

- ICA: två verifierade fulla Primat-contexts; sju stale/offer-contexts.
- Coop: sju fysiska butiker; noll färska fulla basket-contexts.
- Lidl: regionala OWN-erbjudanden tillskrivs inte en fysisk butik.
- City Gross: inget Lund-context.

Coop visas därför med ett explicit diagnostic alert. Accepterade framtida vägar är
starkt matchningsbara fulla Primat-contexts, en officiell partner-API eller en
manuellt verifierad mapping med stark identitetsevidens. Inga spekulativa
workarounds ingår i denna milestone.
