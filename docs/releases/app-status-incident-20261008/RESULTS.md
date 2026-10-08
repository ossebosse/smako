# Avgränsad appfix klar – inte aktiverad

## Historisk händelse: fortfarande FAIL, grundorsak okänd

Första publika Chromium-försöket gav **GET /api/plan-jobs/3218c89521084fc7a1c6b53b622c7276 → 500**,
text/plain. Klientens transportlogg binder det till startbegäran
`9a92c76a-4162-444c-9b3b-b202c8536c53` och statusrequest
`9e96c548-6414-467b-ab7e-3d5e4fe6d779`. Två dokumentgenerationer använde samma
jobb; tre statusläsningar gav 202 efter omladdning innan den fjärde gav 500.

- Klientens svarshändelse observerades **2026-10-08 14:51:20.452506 UTC**.
- Serverns asynkront skrivna metrik: **14:51:24.173961 UTC**, `internal_error`,
  servermätt 0,779 ms. Detta är inte samma klocka/loggningspunkt som klientens
  nätmätning 90,083 ms. Skillnaden bevisar ingen ordning eller orsak.
- App: `status-reconnect-dd12cc80e98c`; image `c8362751…`.
- Manifest: `price-universe:bc39552cbb018b402f1d05fc0518728aa8d635d8e19a047e919b6e70642e1364`.
- Första belagda felsteget är **appens statusläsning**. Metrikens exakta request-ID
  matchar klientens `reference`; det är inte enbart en tidskorrelation.
- Ingen planrevision finns i kontrollerat fönster 14:50:50–14:54:00 UTC. Det
  saknas dock beständig jobb→plan-koppling för originaljobbet. Dess slutliga
  beräknings-/sparutfall, exceptionkedja och felande kodrad kan inte beläggas.
- Bevarad och på nytt avgränsat läst Dockerlogg är tom (exit 0). En utebliven
  logg är inte bevis för frånvaro av fel. Inget proxyfel har belagts; appens
  egen metrik bekräftar 500. Chromium/WebKit tillskrivs ingen grundorsak.

Full POST-body saknas för första försöket. Senare sparad publik POST stämmer
med den misslyckade sidans formulärval. Den lyckade omkörningen ändrar inte FAIL.
Exakta händelser, hashvärden och testbindning finns i [EVIDENCE.json](EVIDENCE.json).

## Vad diagnostiken hittade och vad som kompletterats

Den ursprungliga `smako_ops.py status` hittade återställda priser och
källincidenter, men **ingen appincident**. Den gemensamma ingången läser nu
också appens befintliga 5xx-metrik utan installation, insamling eller beräkning:

```powershell
.venv\Scripts\python.exe -X utf8 scripts\smako_ops.py app-incident --request-id 9e96c548-6414-467b-ab7e-3d5e4fe6d779
```

Det kommandot har faktiskt återfunnit originalmetriken i dd12 och anger uttryckligen
att exceptionbevis saknas. Kandidaten kompletterar endast denna lucka: ett privat,
atomiskt index på högst 64 incidenter/512 kB, med request-/jobbreferens, steg,
utfall, requestens pris-ID och exceptionkedjans typ/kodställen. Inga meddelanden,
lokala variabler, headers, cookies, ägaridentiteter eller planinnehåll sparas.
Misslyckad diagnostikskrivning maskerar inte originalfelet. Se [OPERATIONS](../../OPERATIONS.md).
Indexet fångar HTTP 5xx, inte alla oavlästa bakgrundsjobb. Produktion får inte
denna nya insamling förrän ett separat appbyte har godkänts och genomförts.

Webbläsarverktyget behåller nu klientens requestreferens även när 500-svaret
saknar `X-Request-ID`, tid för observerat svar och testets POST innan resultatet
är färdigt. Strikta felkontroller är kvar.

## Reproduktion och avgränsad rättning

1. En första isolerad dd12-körning med prisartefakten men utan katalogfakta gav
   `PolicyConflict` som felaktigt blev 500 i `poll_plan_job`, dd12 rad 694.
   **Detta var inte likvärdigt historiskt underlag** och räknas inte som
   reproduktion av originalorsaken. Råfel och körning finns kvar.
2. Därefter användes samma hashverifierade prisartefakt, bevarad deklarations-
   projektion med verifierad faktaversion, samma rekonstruerade request och
   prisklocka 14:51:13 UTC. dd12 gav **201**, 58,968 s. Detta återgav inte 500.
   Faktaprojektionen lästes separat med befintlig dd12-kod; provet återskapar
   inte den ursprungliga processens cachebefolkning eller samtidighet.
3. `_offer_structure` anropades **noll gånger** i båda prov. Det tidigare
   sorteringsfelet är inte belagd orsak här och ingår inte i appfixen.
4. En konkret gemensam statusdefekt är däremot bevisad: dd12 lindar även
   `PolicyConflict` och `PersonalConflict` i RuntimeError. Två riktade prov
   ger felaktigt 500 före och korrekt 422/409 efter. Rättningen fanns redan
   i senare commit **ab2718a** och återanvänds selektivt; ingen ny planerare.

## Slutprov

- 58 riktade tester PASS på arbetsgren; samma 58 PASS mot det selektivt
  paketerade dd12-trädet. Det är inte 116 olika tester.
- Två domänregressioner FAIL på original-dd12, PASS i kandidaten.
- Slutimagen: 422, 409 och injicerat oväntat 500 med kedja PASS, även separat
  som verklig app-UID/GID **10001:10001**, indexmode 0600. En arbetskörning
  vid dubbelstart, annan ägare får 404. Injektionen bevisar insamlingen,
  aldrig den historiska orsaken. Diskfel, begränsning och läsande reader testade.
- Chromium mobil, riktiga knappar/planerare/PlanStore, 2 CPU/3 GiB: **PASS**.
  Dubbelstart, omladdning, tio sekunders injicerat nätavbrott, samma återanslutna
  jobb, receptöppning, inköpslista, audit, byte, omräkning, revision 1/2/3 och
  annan ägare 403/404. Ett jobb/en dyr POST för varje avsiktlig operation.
  Inga pageerrors; råa förväntade navigations-/offlinefel finns kvar i rapporten.
- Generering till mottaget resultat 54,656 s, inte en ny prestandajämförelse.
  Minnestopp 2 135 207 936 byte, ingen OOM. Den separata baseline-körningen
  var lokal Windows; dess tid får inte jämföras som prestandavinst.
- Full request och full plan matchar före/efter, undantaget app/build-version
  och `personal.checks.timings_seconds`. Recept, mängder, produkter, kanaler,
  näring, variation och audit lika. 649,95 kr/454,08 kr är historisk replay,
  inte ett dagens acceptanspris eller en ny prisoffert.
- Tre browser-recorderregressioner PASS; riktad Ruff och compileall PASS.
  Ingen fysisk telefon eller signerad kontosession påstås testad.

## Leverans och oförändrad drift

Kandidatcommit **293fc6c49400f6f508eebb6772774d4fdfd995c9** beskriver denna
etapps delta. Leveransimagen består av dd12 + de två API-filerna från den
avgränsade ab2718a-rättningen + incidentkoden, **inte hela arbetsgrenens runtime**.
652 förväntade filer i imagen hashverifierade; frontend är oförändrad dd12.
Paket, image och framtida app-only-väg: [ACTIVATION.md](ACTIVATION.md).

Slutkontroll 16:22 UTC: `/ready` 200, samma manifest, dd12-container/image/starttid
oförändrade. Ingen produktionsomstart, menyprov, insamling, källrelease,
schema-/reläändring eller Git-push i detta ärende. Den egna isolerade
provcontainern är stoppad; dess testlagring och felunderlag bevaras på D: och
i avgränsad serverkatalog. Inga produktionsdata kopierades in i testets PlanStore.

**Redo för separat aktiveringsbeslut för statusrättningen och incidentinsamlingen.**
Originalfelets grundorsak är fortfarande okänd; påstå inte att det historiska
intermittenta felet därmed är bevisat löst. Inga fler fulla menyomkörningar behövs
utan nytt belägg. Stora privata provunderlag finns i `.local/app-status-20261008/`.
