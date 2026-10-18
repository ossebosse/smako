# Aktiverat: uppstart, recept och snabbare exakt planering

Betan aktiverades **2026-10-18 19:39:52 UTC** efter användarens uttryckliga
beställning. Releasekod `bac0fc15ca9a5dffe2cde80d8c977d238fa40028`,
BUILD_ID `app-bac0fc15ca9a-512ef3ea`, image
`sha256:574025c92df8ffc6dec47d0200c20750eb863fe6b69e214710bd56abdfffb79d`.

[Granskning, omfattning och det bevarade admin-undantaget](REVIEW.md).
26 runtimefiler ändrades, 673 övriga filer bevarades. 222 recept ingår;
de 20 experimentrecepten är inte aktiverade. Uppstarts-/faktarättningarna och
de granskade sök-/receptändringarna sedan `e041451` ingår tillsammans med den
senaste exakta återanvändningen av butiksjämförelser.

## Aktivering och databevarande

Aktiveringen väntade på ordinarie prisuppdatering och tillräckligt diskutrymme.
21 kapacitets-/låsväntesteg föregick den lyckade körningen; upptaget driftlås
kringgicks inte. Befintligt kernel-lås hölls under lugn-trafik-kontroll,
SQLite-backup, integritetskontroll, appbyte och efterkontroller.

Endast appens image och BUILD_ID ändrades. Miljö, volymer, scheduler, proxy
och prismanifest bevarades vid bytet. **295 tidigare planrevisioner och 106
privata tillstånd** är hashbevarade både vid bytet och efter HTTP-proven.
Proven skapade fyra nya syntetiska gästplaner och fyra privata gästtillstånd.
Ingen produktionsdatabas återställdes. Backuperna klarade quick_check;
PlanStore klarade även integritets- och främmande-nyckelkontroller.

Lund och Malmö svarar ready med kandidatens BUILD_ID.
`PRICE_UNIVERSE_PREWARM_ENABLED=false` är bevarat. Efterkontrollen 19:45 UTC
visar app, scheduler och proxy running, noll omstarter och inga nya OOM-händelser.
Admin utan autentisering svarar 401. Kandidatens syntetiska positiva/negativa
autentiseringsprov passerade före bytet; inga verkliga lösenord ändrades.

## Publika menyprov

Alla fyra anrop gav HTTP 201, fem recept, högst två valda butiker, godkänd
checkout-audit, avstämda summor och noll okända mängder. Varje sparad plan
lästes tillbaka två gånger med identiskt innehåll. Varje prov har egen
syntetisk gästsessionsidentitet. Butiker väljs via ordinarie geografiska API
inom 3 km; Lund utgår från 22225 och dess API-normaliserade prisområde 22350,
Malmö från 21120.

| Prisområde | Första publika provet efter bytet | Nästa prov | Inköpssumma |
| --- | ---: | ---: | ---: |
| Lund | 52,11 s | 38,77 s | 545,25 kr |
| Malmö | 55,23 s | 52,23 s | 545,25 kr |

Tiderna inkluderar HTTP och asynkron pollning, som sker var tredje sekund.
Första provet är inte ett separat kontrollerat tom-cache-prov; appens normala
uppstart/faktaförberedelse kan redan ha gjort arbete. Dessa enstaka liveprov
bevisar funktion, inte en jämförande tidsvinst, p95 eller samtidighetskapacitet.
Frysta kalla/varma kandidatprov med identiska resultathashar finns i REVIEW.md.

Kommunerna använder olika prismanifest och olika valda butiks-ID:n, verifierat
i EVIDENCE.json. Testharnessens fria `location`-text var standardvärdet Lund
även i Malmöanropen; de använde korrekt postnummer 21120, Malmömanifest och
Malmöbutiker. Detta är API-prov, inte verifiering av gränssnittets ortetikett.
Harnessens textfält har rättats för framtida körningar utan att de uppmätta
anropens bevis skrivs om.

## Kvarstående begränsningar och underlag

Käll-/åldersvarningar finns kvar. Qualified äldre baspriser behålls enligt
befintlig policy; denna release gör ingen ny insamling eller åldersförnyelse.
Efterkontrollen visar samma publicerade och laddade Lund-manifest. Båda
kommunernas laddade manifest och butiksscope är dessutom verifierade via
readiness och de publika planerna.

Full konsolidering av äldre serverändringar till main är inte gjord. Den
befintliga admin-inställningen är ett explicit granskat och dokumenterat
undantag; de övriga ändrade appfilerna matchar vald Git-kod exakt.
Globalt optimalt menypris och prestandamålet under 30 sekunder är fortfarande
inte bevisade. [Uppgiften till Claude](../../CLAUDE-RECIPE-SCALING.md) beskriver
nästa skalningsarbete.

[Sanerat maskinunderlag](EVIDENCE.json). Privata HTTP-svar, backupinnehåll och
sessionsdata checkas inte in. Fulla underlag finns i releasekatalogen på servern
och lokalt under `.local/beta-planner-20261018`.

## Lagring efter releasen

Den nya, avslutade releasebackupen komprimerades under befintligt driftlås
efter att de publika proven och kontrollen av tidigare rader passerat.
6 788 206 863 byte blev ett arkiv på 1 651 167 540 byte. Alla fyra arkivposter
(katalogen och dess tre filer) verifierades med filhashar, ägare och rättigheter;
ursprunget kontrollerades igen som oförändrat och oanvänt före borttagning.
Inga levande databaser, ordinarie dagsbackuper eller images raderades.

Arkiv: `backup-20261018T193114Z.tar.gz` i releasekatalogen.
SHA-256: `faf8794971ca2cf339dd4acb7c192765e213722648c9e85a667b72080fe50d3a`.
Intill finns `backup-20261018T193114Z.ARCHIVED.txt` med återställningskommando
och ett skyddat inventarium. Återställ endast under driftlåset till frånvarande
originalsökväg, aldrig över aktuell produktionsdata.

Slutkontroll **19:49 UTC**: ready/200 med rätt BUILD_ID, samma publicerade och
laddade Lund-manifest, senaste driftkörning complete. **16,69 GB ledigt** mot
beräknat behov **13,99 GB**. Arkiveringen frigjorde 5,14 GB netto.
