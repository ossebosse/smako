# Versionsbundna tester

Slutruntime **ce326c1d7fcf**, **173 PASS på 43,59 s**, Ruff och compileall PASS.
PriceUniverse, behovskontroll, incidenter, Hemköps parser/client/schema/full
acceptans, reläets D:-lagring, lokala köer, källartefakter och atomiska filer ingår.

Prov täcker false/saknat kontra null/true/fel typ, exakt butikskoppling,
legitima olika erbjudanden kontra verklig konflikt, nullable villkor och
ordnade prisvektorer, disk-/D:-fel, paketerings-/transportfel, idempotent import,
importerat men inte publicerat, ändrad incident/runtime, ofullständig federation,
upprepad åtgärd och upptaget operationslås. Kontextbegränsning bevarar andra
butiker och skiljer fysiska erbjudanden från onlinebasen. Produkt/villkor ger
kommersiell incidentidentitet; första v1-indexet bevaras vid v2-migrering.

Förekod: tio nya schema-/bindningsprov och fyra sorteringsprov FAIL.
Efterkod: PASS. En tidig integration hittade äldre store-wrapper; den
bevarades uttryckligt. Misslyckade försök ligger kvar i privat evidens.

## Packagerad kod

Pinnad source-bas verifierad före bygge; bara granskad delta ingår.
Ingen källkodsmount i paketprov. Alla levererade filhashar kontrollerade före
aktivering. Full nätverksfri replay: 6 304 produkter, healthy/promoted,
ursprungliga råhashar/tider; ofullständigt Brunnshög-underlag fortfarande stoppat.

Diagnosprov mot verklig DB på read-only-mount, med isolerad tillfällig indexrot:
båda autentiska fall återfunna, 86/49 filer hashverifierade. Därefter vanlig
slut-CLI status/reproduce och reparationsförkontroll i installerad image PASS.

Första diagnospaketet nådde testcontainerns 3 GiB-gräns; Linux MEMCG OOM
belagd. GROUP BY duplicerade stora snapshot-metrics per produkt. Paketet
aktiverades inte. Rättningen läser varje snapshot en gång och separata små
aggregat. PASS under samma 2 CPU/3 GiB. En kall statusläsning under annat
arbete tog 28,123 s, en varm 1,538 s; ingen p95 eller belastningsgaranti.
Första retestets hjälpare hade ett Path/str-fel efter lyckad status/index;
hjälparen rättad, misslyckandet sparat. Produktionsruntime ändrades inte för det.

## Webbläsare och äldre bevis

Live Chromium/public: ett FAIL (500), därefter PASS. WebKit/personlig: PASS.
Strikta fellyssnare kvar; inga injicerade nätfel i produktion.
Samma dd12-JS SHA-256
`17311d27a3a50ec9e75415316ca8cc90d10c94ac85380b36a75a3541d1b7114e`.
Kompakta resultat/evidenshashar i FINAL.json. Full DOM/transport/revisionsdata
ligger skyddat i `D:/Projects/Smako/.local/hemkop-operations-20261008`.

Ingen ny konsumentappomstart/fysisk iPhone-provning påstås. Tidigare 625 relä-
filhashar och S4U parent/child-tempbevis återanvänds för oförändrad kod.
En manuellt startad Scheduler-körning är inte flera dygns automatisk drift.
