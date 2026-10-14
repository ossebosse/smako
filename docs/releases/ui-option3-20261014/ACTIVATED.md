# Alternativ 3 aktiverat på betan

Aktiverat 2026-10-14 19:51:52 UTC (21:51:52 svensk tid), efter användarens
uttryckliga begäran att aktivera den färdiga implementationen på betan.
Öppna [Mina val](https://beta.smako.nu/personal#choices).

- Build: `ui-option3-ff241807809b`.
- Image: `sha256:28f2638f27ef31ef66402e5bfb9c178cff11d4648e6c1e6e27cb76a9bf98aacb`.
- UI-kod: `ff241807809b75e4c46dcdb4f204a91032e55a7e`.
- Faktisk föregående beta: `ica-purchase-estimates-20261014-ui`,
  image `sha256:6947734fc725d8b70fff52db1a682eeda9f68880a137438a001562e455d66f94`.

## Avgränsning och bevarad drift

Sju statiska frontendfiler byggdes ovanpå den verkliga aktiva bilden:
`personal.html`, `personal.js`, `personal.css`, `complete-recipes.js`,
`choices.css`, `choice-controls.js` och `service-worker.js`.
Ingrediensvalen från den redan lokalt införda `1518101` är ett beroende till
det godkända UI:t och ingår nu också på betan. Ingen annan lokal kod följde med.
Hela imagejämförelsen bekräftar att övriga 676 runtimefiler är identiska,
inklusive senare ICA-rättningar och deras `product-search.js`.

Första aktiveringsförsöket avstod eftersom ordinarie prisuppdatering höll
driftlåset. Efter att jobbet hade avslutats förvärvades samma lås. Appens
inaktivitet kontrollerades, PlanStore säkerhetskopierades med SQLite-backup
och endast appcontainern ersattes. Compose-diffen består av appens image
och BUILD_ID. Scheduler, proxy, miljö i övrigt, volymmounts och samtliga
aktiva prismanifest bevarades. Inga insamlingar startades av denna uppgift.

Samtliga 277 befintliga planrevisioner och 91 privata tillstånd verifierades
med radhashar före och efter bytet samt efter slutprovet. Provet tillförde en
egen plan och ett eget tillstånd: totalt 278/92. Noll nya OOM-händelser och
noll automatiska appomstarter observerades. Ingen Git-push har gjorts.

## Verifiering på publik beta

- Alla sju serverade frontendfiler matchar paketets SHA-256, inklusive
  routen `/personal` och `/service-worker.js`.
- Chromium och WebKit: frukost och mellanmål kan aktiveras, alla nio
  dialoger öppnas/stängs och fokus återgår. Inga JavaScript-sidfel.
- Ingen horisontell overflow vid 320, 390, 768 eller 1440 px.
- En befintlig separat testwebbläsare uppgraderades från shell-cache v15
  till v16 och visade det nya gränssnittet.
- Ett verkligt knapptryck i Lund skickade exakt ett POST med middag,
  frukost och mellanmål (ett tillfälle och en portion vardera).
  Resultat efter 119,0 sekunder: kassakontroll PASS, sju kontrollerade
  ingredienser, noll okända mängder, avstämd totalsumma 97,76 kr.
  Sparad GET gav identisk plan och sidan återställde planen efter omladdning.
- Paketets verkliga tremåltidsbegäran validerades dessutom mot datamodellen
  i den byggda bilden utan nätverk eller produktionsskrivning.

De tidigare lokala 59 UI-/statikfallen och 84 backendtesten gäller samma
hashstabila UI-kod; de kördes inte om utan kodändring. Se
[implementationsrapporten](../../../design/smako-ui-handoff/IMPLEMENTATION_REPORT.md).
Fysisk iOS Safari och full skärmläsargranskning återstår.

## Separat driftbegränsning i Malmö

Lund svarade 200 på `/ready`; Malmö svarade 503 med fyra föråldrade
obligatoriska Willys-kontexter. Den första efterkontrollen stoppade därför
innan menyprovet, och det kompletta menyprovet genomfördes i Lund.

Orsaken reproducerades med **föregående betaimage**, samma oförändrade
Malmö-artefakt och utvärderingstid 19:43:53 UTC, före UI-bytet. Samma fyra
kontexter var då redan 50,07–51,02 timmar gamla, över befintlig 48-timmarsgräns.
Detta är alltså ett belagt befintligt prisunderlagsproblem. UI-aktiveringen
ändrar inte insamling eller färskhetsregler och löser inte den begränsningen.
Ingen mockreserv eller försvagad spärr används.

## Evidens, bilder och återgång

[Sammanställd evidens](EVIDENCE.json) · [Dator](desktop-beta.png) ·
[Mobil Chromium](mobile-beta-chromium.png) · [Mobil WebKit](mobile-beta-webkit.png) ·
[Näringsdialog](nutrition-beta-webkit.png) · [Verklig plan](result-beta.png).

Privata arbetsunderlag och testwebbläsare finns i `.local/ui-option3/beta/`.
Serverns versionsbundna paket, imagekontroll, original-compose, aktiveringslogg
och backup finns i `/opt/smako/evidence/ui-option3-ff241807809b/`;
PlanStore-backup i `backup-20261014T195035Z/` därunder.

Aktiveringen hade automatisk återgång till föregående appimage om readiness
inte återkom. Den behövde inte användas. Vid senare återgång: kontrollera först
att compose fortfarande motsvarar denna release, ta befintligt driftlås och
invänta ledig app, återställ den sparade `compose-wrapper.before` atomiskt och
ersätt endast appen med `up -d --no-deps --no-build --pull never app` genom
den återställda wrappern. Behåll aktuella datavolymer och databaser; återställ
inte en äldre databas. Verifiera image, readiness, UI och bevarade rader igen.
