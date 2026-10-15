# Baspriser behålls, kampanjer följer slutdatum

Status: **aktiverad på betan 2026-10-15 efter användarens uttryckliga beslut**.
Se [aktiveringsrapporten](../releases/base-price-retention-20261015/ACTIVATED.md)
för driftsatta versioner, efterkontroller och återgång.
Gren: `fix/base-price-retention`, integrationsbas `bdf0a3a`.
Implementationscommit: `0f54e51`.
Användarens instruktion 2026-10-15 ersätter åldersspärren för baspriser,
för samtliga butiker. Inga nya insamlingsscheman har införts.

## Aktuell drift och orsak

Läsande kontroll 2026-10-15 06:45 UTC: Lund `/ready` ger 503 i app
`ui-option3-ff241807809b`. Publicerat och laddat manifest är identiska.
Willys 2176 och 2354 finns kvar i underlaget, men åldersgränsen 48 timmar
utesluter deras kontexter. Det blockerar områdets obligatoriska baskällor.
Databasen har alltså inte behövt återställas för att återfå dessa baspriser.
Windowsreläet observerades som Ready med väntande leverans/kvittens.

Ett separat insamlingsfel finns: `source-28f02640d493c57dc843b0e5`,
signatur `28f02640d493c57dc843b0e5adac77c8f91776a31680f33d6dd267aa2948ff7f`.
Snapshot `6e5ed8fd7b8e414c8f0a244a4ad418e9` stoppas av nya schemafält
`hasPickingBaseStore` i butikslistan och butikskontexten. Reproduktionen
verifierade 1 267 råfiler och deras ursprungliga hashar, utan hämtning/replay
till databasen. De granskade svaren visar explicit false för 2176/2354 i
butikslistan och för 2176 i kontextsvar. Parser v5 är oförändrad i denna
ändring. Felet är fortfarande öppet och nya Willys-kampanjer kräver att
insamlingen återhämtas; gamla rabatter förlängs inte för att dölja detta.

## Ändring

- Kvalificerade, promoterade baspriser behålls tills en validerad ersättning
  kommer. Det gäller OWN och federerade baskällor, underlagsbygge,
  aktivering, butikssökning, beräkning, dashboard och återanvändning vid fel.
- FRESH/AGING/STALE och verklig observationsålder bevaras. Åldersvarningar
  och ordinarie återförsök fortsätter. Driftstatus redovisar separat
  `base_prices_usable` och `retained_older_base_context_ids`.
- Erbjudanden utan eget baspris är datumstyrda för alla sex kedjor.
  Utgång vid svensk midnatt utesluter erbjudandet; en vara med baspris
  återgår till detta. Daterade medlemspriser följer samma regel.
- Rabatter utan slutdatum får inte bli obegränsat giltiga när basen behålls.
  Den tidigare 48-timmarsgränsen tillämpas konservativt på svensk inköpsdag,
  utan att fabricera eller skriva om något slutdatum.
- Cacheidentiteten innehåller inköpsdag även för katalogvaror med kampanjer.
  Utgångna medlemsprisskalärer kan inte återskapa en rabatt vid omprojektion.
- Saknad/felaktig proveniens, framtida observationer, identitet, källtillstånd,
  fullständighet och representativ korgvalidering behåller sina spärrar.
  Ingen ändring av sparade planer, användarprofiler eller source-allowlists.

## Verifiering

376 unika riktade testfall godkända genom huvudkörning och avgränsade
omkörningar. Urvalet täcker runtime/readiness, datumgränser, medlemspriser,
butikssökning, federering, cache, byggen/aktivering, LKG, dashboard,
kampanjåterförsök och UI-texter. Ruff och compileall för ändrad Python-kod
samt Node-syntaxkontroll av båda ändrade JavaScript-filerna passerar.
Detta lokala testurval ger ingen fullsvitsgaranti. Efterföljande browserprov
och produktionskontroller redovisas separat i aktiveringsrapporten.

Läsande hämtade, hashverifierade aktiva artefakter återspelades lokalt med
klockan 2026-10-15 06:32 UTC:

| Kommun | Produkter i artefakten | Åter tillgängliga äldre baskontexter | Användbara kontexter | Utgångna daterade erbjudanden avvisade |
| --- | ---: | ---: | ---: | ---: |
| Lund | 43 750 | 2 Willys | 29 | 2 |
| Malmö | 87 900 | 4 Willys | 59 | 35 |

Källornas tidsstämplar och artefaktidentiteter är oförändrade. Resultaten är
lokal verifiering på verklig data, inte ett påstående om aktiverad drift.
Detaljer, urval, testloggar, incidentbevis och artefakter ligger i den
ignorerade katalogen `.local/base-price-retention/`.

## Granskade aktiveringspaket

Separata patchpaket är jämförda med **verkliga** aktiva containerfiler:
25 appfiler och 26 schedulerfiler, inga olösta patchkonflikter.
Skillnader mellan app och scheduler bevaras, inklusive den senare appens UI
och medlems-/butiksval. Befintliga CRLF-filer i scheduler normaliserades
enbart vid patchning; ursprungliga bytehashar finns i manifestet.
Python-filer i paketen kompilerar lokalt. Efter aktiveringsbeslutet byggdes
separata Dockerbilder från dessa paket och de pinnade aktiva baserna.
Hela runtimejämförelsen bekräftade exakt 25 respektive 26 ändrade filer;
658 appfiler och 604 schedulerfiler förblev byteidentiska.

- Appbas: `sha256:28f2638f27ef…` (full identitet i `app-patch-review.json`).
- Schedulerbas: `sha256:a5a55f723eaf3b6b9a81470e8cab64174bf892cb02f6176454b9339baf79a587`.
- `app-candidate.zip`: SHA-256 `939e16b82616720a998797097c16bdded7eef1ee8da7d7d737688ccd372614b0`.
- `scheduler-candidate.zip`: SHA-256 `bb5f3f0393ce1a2e038b971460f612f1d3791566538f8caada789f90ccce3924`.

Användaren gav aktiveringsbeslutet "Aktivera och commita". Basernas fulla
image- och filhashar kontrollerades igen. App och scheduler aktiverades
selektivt under befintligt driftlås efter databasbackup. Hela lokala HEAD
har inte driftsatts. Willys schemafel ska hanteras som en separat granskad
parserreparation med negativa prov och versionsbunden replay/insamling.
