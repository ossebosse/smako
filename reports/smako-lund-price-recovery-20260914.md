# Lund/22350: återställning av prisunderlag 2026-09-14

## Verifierad utgångspunkt

Workspace `f5935e5`; fungerande appkod från `98381e5`, release
`personal-v2-fast-403020-20260913c`, image `9669be2e3b411588778b95e816adc5e3f3d12fd164a47ade81df2e6b425d6235`.
Scheduler körde fortfarande `0.1.0-smako-ica-quality-20260909`.
Detta är senare än den först angivna historiska releasen `8023488`.
AGENTS, HANDOFF och senaste [acceptansrapporten](smako-fast-combined-403020-20260913.md) lästes.

Feltexten kommer från `_assert_offline_ready` i `backend/app/api/plan.py`:
`prepared.status(...).status in {"stale", "broken"}` ger 503.
Betans faktiska värden före återställning var `stale`, 0 användbara och 6 uteslutna kontexter;
databas och planlagring var OK, `/health` 200 och `/ready` 503.
Gränserna var och är varning vid 36 h, oanvändbart vid 48 h.

Aktivt på disk och i processen var
`price-universe:11e58c7ce1ae5efaf8da60d87c3f67e29adc43bde8b1fb321f7351d450715a46`,
byggt 2026-09-12 02:07:35.882633 UTC, aktiverat 02:12:24.820500 UTC,
city:lund och postnummer 22350. Storlek och SHA-256 stämde. De ursprungliga
observationerna var Coop 12 september 01:17–01:45 UTC, Hemköp 12 september
01:55–02:06, ICA 11 september 02:07, Willys 11 september 06:37–07:04.
Sista användbara kontexten passerade 48 h den 14 september 01:55:30 UTC.

## Belagda orsaker och kvarstående utredning

Nattkörningen `refresh-report-20260914T020748.936967Z-d1326c97.json` och
Coop-återförsöket `refresh-report-20260914T044631.733526Z-f67b1b8d.json`
slutade med exit 1 och ingen rebuild. Primat rapporterade `ValueError`/
`failed_no_lkg`; återförsöket hade `active_cache_unavailable`.
Den gamla hanteringen sparade endast undantagsklass, inte meddelande eller stack,
och tog bort misslyckad kandidat. `provider_requests=0` i dessa gamla felrapporter
bevisar inte noll anrop: räknaren kopierades endast när insamlingen returnerade.
På 12 september kunde gammal cache behållas; 13–14 september var den för gammal,
och `required_external_cache_unavailable` stoppade hela rebuild-kedjan.
Färska Coop/Hemköp-snapshots fanns alltså utan att bli aktiva konsumentpriser.

**Primats exakta historiska ValueError-orsak är fortfarande inte belagd.**
Två isolerade, begränsade körningar av samma befintliga produktkedja passerade
49 anrop (1 store resolve + 48 produkter), samtliga HTTP 200, maximal samtidighet 1,
exakt butiksmatchning, produktparsning, stängd export, validering och context activation.
Båda hade 1 888 produkter från exakt de två ICA-kontexterna. Ingen butiksmatchning
försvagades. En mellanliggande diagnostikkörning fick ett separat nätverkstimeout/
PriceProviderError vid resolve; det är inte nattens ValueError.
Den första godkända exporten, observerad 12:23:06.684277 UTC, återanvändes utan
ny insamling. Den andra körningen använde isolerad SQLite- och cachekopia och
avbröts avsiktligt före rebuild. Dess exit 1 är diagnostikstoppet, inte Primat-fel.
Se [full isolerad diagnostik](recovery-22350/primat-diagnostic.json),
[context validation](recovery-22350/primat-context-validation.json) och
[managed replay](recovery-22350/managed-primat-diagnostic.json).
Det går därför inte att hävda att en specifik Primat-rotorsak har rättats eller
att ett regressionstest för just nattens okända fel finns.

**Willys-felorsaken är reproducerad och rättad.** Windows-tasken kördes enligt
schemat men slutade med resultat 1 den 12–14 september. Insamlingen var godkänd;
SSH-uppladdningen anropade `/opt/smako/compose`, som under SSH-användaren inte
kunde läsa `/opt/smako/production.env`: `permission denied`.
Samma problem fanns i import-, status- och preflight-anropen.
De använder nu den redan körande `smako-scheduler-1` via Docker med samma UID/GID
10001:10001. Inga ytterligare privilegier, ändrade filrättigheter eller
retailerinloggningar infördes. Hash-, symlink-, validerings- och aktiveringsskydden
är kvar. Fyra filer uppdaterades atomiskt efter hashkontroll i den verkliga
schemalagda taskens repository; schemat ändrades inte.

Nattens slutna Willys-fil hade SHA-256
`724f3b6c1448e1ac07b22b759d32be6bed85d510a50299d73f958c8ac2a41377` och
18 589 produkter. Den återanvändes inom gällande färskhet. Uppladdningen passerade.
Serverns självständiga replay/parsning tog 185,192 s, noll parserfel, healthy.
Räknaren 1 247 i denna replay avser fångade rådokument, inte nya nätverksanrop.
Importens skapandetid får inte förväxlas med prisernas nattliga observationstider.

## Skydd och driftsättning

Befintlig validate/promote → rebuild → kandidatvalidering → atomic activate →
runtime reload används med samma globala lås. Ingen ersättningsprismotor,
ändrad freshness-gräns, reducerad kandidat eller omskriven observationstid används.
Den godkända explicit-cache-vägen används för Primat och vanliga source-inbox-vägen
för Willys. `--chain citygross` är befintlig lokal rebuild-väg utan ny källinsamling.

`PRICE_UNIVERSE_REQUIRED_CONTEXT_IDS` kräver de sex exakta kontexterna i Lund.
Kandidatvalideringen avvisar saknade eller inaktuella obligatoriska kontexter.
Samma kontroll finns i konsumentens planeringsberedskap och `/ready`.
Driftstatus räknar aktiv prisålder på nytt vid läsning och ger `requires_attention`
från 36 h, även utan en ny refreshrapport. Rebuild-/aktiveringsfel exponeras separat.
Primat-felrapporteringen behåller steg, fråga, butikskontexter, verkligt anropsantal,
stack och orsakskedja. Meddelanden får bara återges om de är säkra kodkonstanter;
HTTP-body, interpolerade parserindata, lokala variabler och hemligheter kopieras inte.
Regressioner verifierar att fel inte tystas och att provider stängs.

Backup: `20260914T123547Z`. Staging verifierade 111 basfiler; VPS:ens befintliga
Caddy-konfiguration och frivilliga ACME_EMAIL-värde bevarades. Ursprungliga miljöfilens
ägare/rättigheter bevaras. Ingen migration eller databasrestore behövs för rollback.
App och scheduler kör samma nya release `price-recovery-lund-20260914a`.

## Separata källfel

- Coop Online Syd 730400 var färskt och godkänt: snapshot
  `7221700ddab04bfbb875b7387d00c514`, 11 406 produkter, från 04:17 UTC.
  Coops separata fysiska erbjudandeflöde har fortsatt ConnectorFetchError.
  Ett tidigare Online-fel den 11 september hade redan återhämtats samma dag.
- Hemköp Brunnshög 4224: snapshot `46e0819012be4eb0ab2034e26fbd50ac`,
  5 065 produkter, från 01:55 UTC. Hemköp Karhögstorg 4123 har separat
  ConnectorFetchError och gammal LKG; det är inte en av de sex obligatoriska kontexterna.
- Lidl-kandidaten den 14 september passerade inte schemakontroll: sex tillagda och
  fyra borttagna fält samt saknade sale/unit-price-fält. Föregående godkända snapshot
  behölls. Detta är separat från Primat/ICA och det sexkontexters Lund-underlaget.

## Tester

139 distinkta fokuserade tester PASS: relay 13, relaystatus 3, managed refresh 25,
Primat refresh 6, beta readiness/observability 33, runtime/aktivering 17, ytterligare
42 source-artifact/freshness/closed-cache-tester. Ruff och compileall PASS, Python 3.12.
25 managed-tester upprepades efter det sista stegtillägget.
[Verifieringsmanifest](recovery-22350/verification.json),
[releasefiler](recovery-22350/release-source-manifest.json),
[taskens faktiska filer](recovery-22350/task-runtime-files.json).

## Verifierat resultat på den körande betan

App och scheduler kör `price-recovery-lund-20260914a`, image
`54dde8382599ac30beee8bffd05d8cefff232e1ea5c81f1fd7f302db0d591c1f`.
Disk och HTTPS-process visar samma nya universum:
`price-universe:927c331cabf6d188472a6e8658f7e38eacc4b71553a4455ab5a2b85e0f34f9e2`.
Byggt 12:51:53.678870 UTC; exakt aktiveringstid finns i manifestet.
Runtime reload avslutades 12:55:25 UTC; nya appreleasen blev ready efter omstart.
Alla sex obligatoriska kontexter är användbara, 0 uteslutna, 2 094 produkter i
slutligt ekonomiskt index. Källornas kvalificerade rader redovisas nedan.

| Kontext | Exakt käll-ID | Prisobservationer UTC | Ålder vid kontroll | Rader |
|---|---|---|---|---|
| Coop Online Syd | own:coop:730400 | 14 sep 04:17:11–04:44:31 | 8,69 h | 11 406 |
| Hemköp Brunnshög | own:hemkop:4224 | 14 sep 01:55:51–02:06:52 | 11,05 h | 5 040 |
| ICA Maxi Gunnesbo | primat:ica:1088004 | 14 sep 12:23:06 | 0,59 h | 1 864 |
| ICA Clemenstorget | primat:ica:1004409 | 14 sep 12:23:06 | 0,59 h | 24 |
| Willys Lund | own:willys:2176 | 13 sep 23:31:11–23:42:09 | 13,46 h | 10 046 |
| Willys Nova | own:willys:2354 | 13 sep 23:49:32–23:59:20 | 13,15 h | 8 382 |

Coop behåller ONLINE_FULFILLMENT/online_price, Hemköp och Willys sina online_store-kontexter,
ICA sina exakt mappade physical_store/full_catalog-kontexter. ICA:s explicita
`price_semantics` är null i källartefakten; ingen hyllprisuppgift har hittats på.
Identiteter och komplett butiksunderlag kontrollerades mot de existerande sex ID:na.
Antalet kvalificerade rader kan vara lägre än insamlat antal: oförändrad produkt-/prisvalidering
användes, ingen mindre butikspool eller ändrad sökbredd infördes.

`/health` **200**, `/ready` **200**, `required_contexts_usable=true`,
`missing_required_context_ids=[]`, `status=fresh`, gränserna 36/48 h oförändrade.
[Runtime- och observationsbevis](recovery-22350/runtime-verification.json),
[aktivering/reload](recovery-22350/refresh-runner-status.json),
[full managed refresh](recovery-22350/managed-refresh.json),
[deployment och rättigheter](recovery-22350/deployment.json).

Verkligt HTTPS-formulär, 390×844 mobilvy: POST **201**, synligt fullständigt resultat
på **40,781 s**, svar **40,594 s**, första nya gäst efter omstart. Requesten är
**exakt lika** med den kvalificerade sanerade basrequesten. Samtliga 40/30/20-krav
per portion passerade: 15 tillfällen, 20 portioner, Balanserad/Blandad,
uppskattningar på, max två inköpsställen, inga extra krav.
Korgen kostar **560,33 kr**, använder **2** inköpsställen, är `VERIFIED`,
har inga ekonomivarningar och `total_reconciled=true`. Planen refererar det nya
aktiva universumet och gjorde noll externa källanrop. Historiska 574,92 kr används
inte som exakt jämförelse för de nya priserna. Detta enda mobilprov är inte en
ny treprovsacceptans av 30-sekundersmålet. Läsning av artefakten gjordes under provet;
tiden ska inte användas som en isolerad prestandabaslinje.

Receptbyte via samma UI: HTTP **200**, **7,092 s** till användbart resultat,
samtliga 40/30/20-krav och gemensamt butikstak kvar. Dubbelklick gav en POST;
avgång och timeout gav inga automatiska omstarter. Avbrottsproven stoppades före
tungt serverarbete. [Mobilacceptans](recovery-22350/mobile/acceptance.json).

Den verkliga Windows-tasken kördes manuellt med oförändrad S4U/Limited-konfiguration:
start 14:58:38 lokal tid, **LastTaskResult=0**. Validering passerade, uppladdning
26,078 s, serverbekräftelse 27,938 s (`already_active`, samma snapshot). Ingen ny
Willys-insamling startade. Total relay 102,641 s inklusive kontroll av befintlig fil.
Nästa ordinarie task kvar 15 september 01:30. Last-success-kvittot skrevs av den
verkliga framgångsrika tasken; det skapades inte manuellt.

Rebuild tog 148,725 s; kandidatbyggnad/validering/aktivering 206,835 s.
Hela wrappern inklusive Willys-import och runtime reload tog cirka 439 s.
Ingen färdig testplanscache värmdes; `plan_prewarm=disabled`.
Befintlig VPS: åtta vCPU och cirka 15,6 GiB RAM, oförändrad avsaknad av Docker
CPU-/RAM-kvot. Observerat bygg-RSS cirka 1,4 GB; efter UI-provet app cirka 910 MiB,
CPU under 1 %. Detta är stickprov, inte en peak-RSS-mätning. One-shot-containern
togs bort automatiskt och inga återställningsarbetare är kvar.

Planeringsberedskapen är frisk. Övergripande driftstatus flaggar fortfarande
separata ärenden: föregående Coop-retry-fel och Citygross `not_applicable` som
befintlig rapportlogik markerar för retry. Flaggorna har inte raderats för att
få en grön status; aktuell planeringsberedskap visas separat.

## Ändrade filer och återstående begränsning

- `grocery_data/source_cli.py`, `local_relay.py`, `relay_status.py`, `relay_preflight.py`: rättad VPS-transport med bevarade integritetskontroller.
- `backend/app/services/production_primat_refresh.py`, `grocery_data/__main__.py`, nya `grocery_data/app/services/refresh_diagnostics.py`: steg och undantagskedja bevaras utan känsliga indata.
- Båda `config.py`, `deploy/compose.yaml`, `prepared_universe_activation.py`, `backend/app/api/plan.py` och `beta_ops.py`: obligatoriska användbara kontexter vid publicering, planering och readiness.
- `backend/app/services/beta_observability.py`: aktuell ålder/36-timmarsvarning och rebuild-/aktiveringsstatus i befintlig driftstatus.
- Sex berörda testfiler och isolerade diagnostik-/release-/verifieringsskript; full lista finns i Git-diff och källmanifest.

**Planeringsfunktionen är verifierat återställd. Primats historiska ValueError-rotorsak
är fortfarande en öppen blockerare för att kalla hela felsökningsuppdraget färdigt.**
Ett nytt uppträdande behöver den nu bevarade steg-/undantagsdiagnostiken. Ingen
påhittad fix eller avslutad regression för just detta okända fel redovisas.
