# Verifiering – avslutad isolerad slutmatris

Appens testade runtime är `54cb2e8159a126de26fa11cb1d393dc275238fd3`,
image `8a537fc4d333`. Senare dokumentations-/testverktygscommits ändrar inte
den paketerade appkoden. A:s rena reläpaket är separat `fe795e5b04f5`.

## Genomfört

- 206 riktade backendtester passerade: beräkningsekvivalens, sökgränser,
  personlig planering, näringsunderlag, förberedelser, receptcache,
  måltidsbibliotek, faktahash och köpavtal. Arbetskällans 550 relevanta filer
  är jämförda med paketet; endast bevisade radslutsskillnader normaliseras.
- 664 faktiskt levererade imagefiler matchar RELEASE.json. Sex dokumenterade
  paketeringsfiler ingår i ZIP men kopieras inte av ordinarie Dockerfile.
- Tre före- och elva efterprov i Chromium/WebKit, mobil layout, passerade
  verklig planering, DOM, sparad GET och ägarisolering. Navigations-/nätprov
  och mutations-/omstartsprov anges individuellt i BROWSER-EVIDENCE.json.
  Varje ursprunglig begärans-ID motsvarar exakt en tung beräkning i serverloggen.
  Proven använder gästsessioner i publikt och personligt flöde; de är inte
  verifiering av samtliga signerade kontosessionsformer.
- Fyra äldre 15/20-profiler, exakt/uppskattat och original/plus, passerade
  15 måltider, 20 portioner, 40/30/20 g, korg/audit och sparade revisioner efter
  faktisk appomstart. Hela resultaten jämfördes med fd2:s bevarade prov.
- Recept/fakta (38 filer), frontend (15), jobb/session/lagring (4) och
  innehållsimport/förberedelse (3) är oförändrade enligt INVARIANTS.json.
  Tidigare data-only- och opåverkade statusbevis återanvänds som äldre bevis,
  inte nykörda tester.
- Privat 300 g ost fördelades över middag, frukost och mellanmål utan
  dubbelanvändning. Frukost-/mellanmålsbyte, oföränderliga revisioner och
  separat ägares nekade GET passerade. Äldre menyflöde med flaggan av
  fungerade i samma nya image; det kvalificerar inte äldre binäråtergång.

## Samtidighet och bevarade fel

Första ostörda treägarprovet levererade tre korrekta planer, men serverloggen
visade analytics HTTP 500 (`database is locked`) 11:33:44 UTC. Slutbedömningen
är därför FAIL. Nästa avbrottsprov fick samma typ av serverfel och `/ready`
503 under formulärförberedelsen. Endast två jobb accepterades; båda slutfördes.
Den tredje klientens dubbelklick väntade på en spärrad knapp. Det är inte
bevisat att navigation var den historiska orsaken till just detta klickfel.
CONCURRENCY.json använder den strikta bedömningen som samlat `outcome`;
klientens ursprungliga PASS ligger separat i `client_reported_outcome`.
Den ursprungliga rårapporten är orörd.

Testverktyget hade också en konkret osäker ordning: statuscallbacken kunde
navigera innan Playwrights klick hade avslutats. `f3dc1ac` ordnar dessa
händelser och bevarar partiell evidens. `6b59b04` stoppar även vid alla
observerade HTTP 5xx, inklusive analytics. Detta är testverktygsändringar,
inte appfixar. Ingen sidfelslyssnare eller säkerhetskontroll togs bort.

Den isolerade HTTP-startfilen använde SQLite-standardväntetiden 5 s.
Faktisk produktion har `timeout=30` och journal_mode `delete`. Teststarten
är nu korrigerad till 30 s; produktionen och runtimeimagen ändrades inte.
Både ostört och injicerat treägarprov passerade därefter. Avbrottsprovet
gav cirka 65/120/173 s till resultat och det ostörda 61/115/168 s, inklusive
kö. Exakt låshållare/tidsförlopp i de äldre felen är fortfarande okänt.
Omkörningarna bevisar testad funktion under denna konfiguration, inte att
SQLite-lås aldrig kan återkomma.

De fyra äldre profilernas avsiktligt upprepade start-ID:n och skafferiprovets
dubbelstart gav fem `telemetry_persist_failed`-varningar. Samtliga ID:n
matchar exakt de upprepade starterna. Samma varning reproducerades med
oförändrad telemetrikod i en separat minnesdatabas: den andra raden bryter
den befintliga unika `request_id`-nyckeln (`SQLITE_CONSTRAINT_UNIQUE`).
Varningarna bevaras i TELEMETRY-WARNINGS.json; den ursprungliga fångade
exceptiontypen loggas inte av appen. Detta är separat från de belagda
HTTP 500/503-låsfelen. Ingen generell varnings-/felundantagsregel infördes.

Samtliga fyra äldre planresultat matchar också det bevarade fd2-underlaget.
För senare profiler skiljer `personal.cache_identity` eftersom hela det
privata tillståndet innehåller nya state-/plan-ID:n. Identiska requests,
tomma skafferiallokeringar och alla övriga resultatfält jämförs uttryckligen;
denna begränsade normalisering gäller endast separata historiska HTTP-sessioner.

## Begränsningar och återstående arbete

Slutlig 1×/2×/5×-matris och individuella innehålls-/invalideringsprov har
passerat. QUALIFICATION.json binder 36 planerarprocesser, 60 validerade
fulla resultat, 37 matchande före/efter-par och 30 receptkvalificeringar till
den slutliga imagen. Nio bevarade isolerade revisionsrader läses oförändrade,
inklusive två rader med senare återkallat innehåll. Gamla och nya revisioner
överlever de separata HTTP-/webbläsarprovens faktiska appomstarter och
flagga av; tidigare 267-radersbevis återanvänds för oförändrad kod.

Lokal replay använder frysta historiska priser/fakta,
två CPU, 3 GiB och en tung planerare. Inga produktionspriser eller privata
produktionsplaner ingår. Mobil WebKit är inte fysisk iPhone-testning.
Kallt huvudklick överstiger fortfarande 60 sekunder. Stora relevanta bibliotek
har lägre kostnad per sökning men flera minuters väntan. Befintliga
sökbudgetgränser är oförändrade och redovisas; global optimalitet är inte
bevisad. A:s produktionsåterställning är separat blockerad.

Råbevis finns på D: under `.local/willys-storage-search-20261007/`.
Avbrutna profiler, ursprungliga testfel och omkörningar bevaras var för sig.
