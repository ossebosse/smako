# 2026-10-08: Hemköp återställt och gemensam driftstatus aktiverad

**Prisdriften är återställd; en första publik HTTP 500-händelse kvarstår som
separat, oförklarad appanmärkning.** Läs först [OPERATIONS.md](OPERATIONS.md),
kör `.venv\Scripts\python.exe -X utf8 scripts\smako_ops.py status` i D:\Projects\Smako.
Fortsätt med `incidents`/`reproduce`; börja inte om med hela historikarkivet.

Slutlig source-runtime **ce326c1d7fcf5235e77ea4fcf2139d4fb25be849**, endast scheduler,
image **sha256:8fce7b9c72fbadc615aba9b46d2a2fec32a81dfb87231b33aae20ebca6547e3b**.
Betan är oförändrad dd12; fe795-reläet och Windows-XML oförändrade. Ingen
mål-/prestandakandidat aktiverad. Releasepaket/aktivering, 173 tester och resultat:
[RESULTS](releases/hemkop-operations-20261008/RESULTS.md),
[FINAL.json](releases/hemkop-operations-20261008/FINAL.json),
[ACTIVATION](releases/hemkop-operations-20261008/ACTIVATION.md).

Karhögstorgs exakta booleska tillägg rättat, ordinary replay med ursprungliga
observationer passerade. Brunnshögs gamla medlems/offentlig-källmotsägelse
bevarad; ett nytt komplett försök passerade utan att konfliktspärren ändrades.
Ytterligare TypeError i nullable erbjudandesortering rättad i källbyggaren.
Alla fem baser FRESH/laddade, /ready200 vid 15:17 UTC. Manifest bc39552c…;
2 232 råhashar verifierade. Samma Willys d53486fb… exakt en import, återleverans
gav already_active och beständigt kvitto 14:53:39 UTC. Ingen fullhämtning igen.

WebKit/personlig PASS; Chromium/publik först FAIL 500, sedan PASS utan appbyte.
Båda PASS-flödena omfattar omladdning, dubbelstart, receptbyte, omräkning,
tre revisions-GET och ägarisolering. Första felet: jobb
3218c89521084fc7a1c6b53b622c7276, app-request 9e96c548-6414-467b-ab7e-3d5e4fe6d779,
14:51:24 UTC internal_error. Exakt grundorsak okänd; påstå inte rättat av omkörningen.
En separat dd12-hjälparprob visar nullable-sorteringsfel för 26 produkter men
ingen bevisad koppling till detta HTTP 500. Eventuell konsumentapprelease kräver
separat omfattning; byt inte mat/prisdata eller aktivera 54cb för att maskera felet.
Råfel/testunderlag: skyddat D:\Projects\Smako\.local\hemkop-operations-20261008.

Alla gamla 216 revisioner/61 privata rader hashbevarade; nu 222/63 efter prov.
Server 13,32 GB, C:5,51 GB, D:664,22 GB ledigt. Ingen ny rensning i denna etapp.
Scheman inte pausade. Omedelbar demandkontroll not_due/0 anrop; äldre global
backoff 18:37:43 UTC kvar (första efterföljande tick18:45 UTC). Windows nästa
17:30 svensk tid vid kontrollen; manuell tidigare start är inte fler dygns driftbevis.
V2-index 13 incidenter, aktuella Hemköpsfall återhämtade. Äldre separata
Coop-fysiska schema-/Lidl-kvalificeringsincidenter öppna; de blockerar inte femkällorsbasen.
Ingen extern notifieringstjänst tillagd och inga skickade larm påstådda.

# Tidigare kontroll 2026-10-08: Driftåterställning – konkreta Hemköp-blockerare

**Windows och serverutrymme är åtgärdade; prispublicering är inte återställd.**
Se [slutstatus](releases/drift-restoration-20261008/STATUS.md),
[FINAL.json](releases/drift-restoration-20261008/FINAL.json) och
[separata källstopp](releases/drift-restoration-20261008/BLOCKERS.md).

Uppgiften använder fe795e5b04f5, 625 filer matchar, övrig XML bevarad.
Verkligt S4U/session 0 parent/child-temp på D: PASS. Återleverans av nattens
bdc9-artifact gav exakt en promoverad import 72c524df46c34fe69af362158af38692.
Publiceringen misslyckades; paket kvar på D:, inget nytt last-success/kvitto.

Användarens förnyade säker-rensningsgodkännande användes för fem exakt
arkiverade testkataloger och 61 exakta reproducerbara byggcacheposter.
Fyra testdatabaser och alla aktiva data/images bevarade. Server 0→14,0 GB
som mest; 13,49 GB efter återhämtning. C: cirka 5,53 GB, D: 664,30 GB.
Ingen bred prune eller aktiv tempfilradering.

Ordinarie serveråterhämtning **avslutad** 12:37:43 UTC med exit 1; exec87815
är inte längre aktiv. Coops fullcrawl promoverad. Karhögstorg komplett men
rejected på två booleska hasPickingBaseStore-fält. Brunnshög ofullständig
på olika potentialPromotions för 101293703_ST. Råbevis och separata
stopporsaker bevarade; inga spärrar kringgångna. Separat förberedelse av
avgränsad schemafix efterfrågad, inget användarsvar vid denna notering.
Ingen källkod ändrad eller driftsatt.

Samma dd12-app/JS/flagga; /health200, /ready503, grocery/plan_store ok.
216 revisioner och 61 privata tillståndsrader exakt bevarade. Gammalt
manifest är fortsatt laddat med alla fem baser STALE. Menyproven blockerade.

Scheman inte pausade: Windows nästa 17:30 lokal tid; server var15min.
12:45 UTC demandkontroll not_due på **backoff**, inga prisanrop.
Global retry_at 18:37:43 UTC; möjlig cronåterhämtning20:45 lokal tid.
Ingen framtida automatisk framgång påstådd. Kontrollera verkliga jobb/lås
innan nya åtgärder. Ingen måltids-/sökaktivering eller Git-push.

# 2026-10-07 kväll: Endast driftåterställning – operatörsåtgärder återstår

Gren `ops/restore-price-flow-20261007`, ovanpå `72a936b`. Ingen ny apprelease
eller fortsatt prestandaetapp. Betan behåller dd12, kompletta recept på.
Ny faktisk kontroll 20:40 UTC: `/ready` 503, PlanStore
`SQLITE_IOERR_SHMSIZE`, serverns faktiska filsystem fortfarande 0 byte
tillgängligt. C: hade cirka 6,6 GB och D: cirka 688 GB vid etappens start.
Alla fem baser är STALE; aktiv prisartefakt och 2 236 råreferenser är
hashverifierade och ligger kvar i produktionens ordinarie rårot.

17:30-reläkörningen är avslutad men saknar slutkvitto och task_success.
Schemaläggarens slutkod 0 bevisar inte lyckad leverans. Uppgiften är
Ready/Enabled och använder fortsatt bdc9. Ingen paus eller insamling
har startats av oss i denna etapp. Nästa Windows-start 8 oktober 01:30;
serverns behovskontroll var 15:e minut och backup 02:47 svensk tid.

Operatören har tidigt fått exakt administratörskommando för
`scripts/activate_willys_storage_fix.ps1 -Apply`, commit `43a712a`.
Verktyget verifierar förväntad hel uppgifts-XML, paketmanifest och 625 filer,
bevarar konto/S4U/Limited/schema och respekterar båda lokala låsen. Endast
Actions Arguments/WorkingDirectory ändras; det startar ingen insamling.
Läsande förkontroll passerade. Ingen automatisk elevation eller ACL-ändring.

Nio inaktiva testdataobjekt under gamla `ops-verification` är arkiverade
direkt till skyddad D:-lagring. Arkivets 89 550 filer matchar originalens
SHA-256; full återställning med rätt filantal/storlek genomförd. Ytterligare
hashkontroll av återställda filer passerade för 39 532 filer inklusive alla
fyra databaser; resterande extra efterkontroll stoppades uttryckligen och
påstås inte genomförd. Inga hashfel observerade. Arkiv SHA-256
`21946e544ae4b8605c0d5f52aa32fad3ae21869052716c7c00207441a5f5e3f4`.
Ingen serverkopia är godkänd för ny radering. Exakt nioobjektslista har
lämnats till användaren för beslut; ingen radering före svar.
Exakt lista, arkiv-/återställningsbevis och nästa operatörssteg finns i
[aktuell driftstatus](releases/drift-restoration-20261007/STATUS.md) och
[arkivförslaget](releases/drift-restoration-20261007/ARCHIVE-PROPOSAL.md).
Målen saknar container-/öppna filreferenser; planer, konfigurationer,
produktionsrådata, köer och paket är undantagna. Kontrollera referenser och
innehåll igen efter ett eventuellt raderingsgodkännande. Gamla tillstånd,
paket och större råbevis finns utanför Git på D:. Ingen Git-push.

# 2026-10-07: Slutleverans – A blockerad, B kvalificerad i isolering

Arbetsgren `feature/willys-storage-search-20261007`. Ingen Git-push eller
aktivering av måltids-/prestandakandidaten. [Slutrapport](releases/willys-storage-search-20261007/RESULTS.md).

**A är inte återställd.** Full driftkontroll 15:05 UTC visade rätt dd12,
kompletta recept på, serverns faktiska datavolymer med 0 byte tillgängligt,
`/ready` 503 och `SQLITE_IOERR_SHMSIZE`. Alla fem obligatoriska baser var
över 48 timmar. Den separata reläkandidaten `fe795e5b04f5` är installerad,
men Windows nekade `Set-ScheduledTask`; uppgiften använder fortsatt bdc9.
Schema, konto, S4U/Limited och övriga inställningar är bevarade. Ordinarie
17:30-start observerades; det är ingen manuellt kontrollerad start.
Serverutrymme och administratörskörning av det redan avgränsade
`update_relay_task.ps1` behövs före fortsatt S4U-/driftverifiering.
Ingen kö eller tidigare data har raderats. Se tidsstämplad
[A-status](releases/willys-storage-search-20261007/A-STATUS.md).

**B är färdig och isolerat kvalificerad, inte aktiverad.** Runtime
`54cb2e8159a126de26fa11cb1d393dc275238fd3`, image
`sha256:8a537fc4d333d9fc17fd06916061ed481ba433951126688df51b6b4da19766f3`.
ZIP SHA-256 `98446fac69395c8f7eded6c15f23f8194b5e26dffde1810e83cb5a9007338667`.
Verifierad imageexport SHA-256
`ec82580cc0a7c6d001bfda93dd0f2b8fc48938cda5d0ea5f57f7d93d9879ff19`.
Båda finns i `.local/willys-storage-search-20261007/package-54cb2e8159a1/`.
Senare commits gäller dokumentation/testverktyg; bygg inte om slutpaketet.

Tre kalla 5×-processer per sida: median 892,01→534,79 s (−40 %).
Tre varma nya 5×-beräkningar: 775,67→419,03 s (−46 %). Samma relevanta
620 recept och 12 781 veckoutvärderingar; samma begränsade sökbudget.
Huvudklick varmt 54,234 s Chromium/53,234 s WebKit; kallt 87,078 s når
fortfarande inte 60-sekundersmålet. Ingen global optimalitet hävdas.

37 fullständiga resultatpar matchar efter redovisad metadatanormalisering;
60 planresultat, 206 backendtester, 14 strikta webbläsarprov, fyra äldre
15/20-profiler och alla 24+6 receptkvalificeringar passerar. Individuell
receptkvalificering hade inget proteinmål. Import, invalidering, gemensamt
inköp, privat skafferi, ägarisolering, revisioner, omstart och flagga av
verifierade. Ursprungliga samtidighetsfel och telemetrivarningar bevaras;
SQLite-väntetiden rättades i testmiljön, inte i appimagen.
Alla tunga testsekvenser är avslutade. Se
[slutkontroll](releases/willys-storage-search-20261007/QUALIFICATION.json),
[mätgränser](releases/willys-storage-search-20261007/PERFORMANCE.md) och
[framtida app-only-anvisning](releases/willys-storage-search-20261007/ACTIVATION.md).

## Historiska delstatusar 7 oktober – ersatta av slutläget ovan

Uppdatering 14:35 UTC: basens tre varma 5×-nyberäkningar är klara,
775,67/775,73/771,76 s (median 775,67). Efterversionens motsvarande serie
pågår i `smako-search-after-scale5-warm-1`. Därefter kör den redan startade
sekvensen de fem profilparen och `container_followups.py` inklusive 30
kvalificeringar, invalidering, äldre lagring och imageexport. Kör inte en
andra tung sekvens parallellt. Slutkontroller finns förberedda som
`collect_followups.py`, `compare_all.py`, `validate_results.py`,
`final_gate.py` och `index_evidence.py` under samma lokala evidensrot.
14:11 UTC var servern fortsatt full och uppgiften fortsatt bdc9.

Uppdatering 13:32 UTC: tre kalla 5×-par klara. Hela processens median
892,01→534,79 s (cirka −40 %); varma 5×-nyberäkningar pågår därefter i
samma sekventiella matris. Runtime/image är fortfarande 54cb/8a537fc4d333.
Serverns faktiska appdatavolymer hade 0 byte ledigt 13:08 UTC; uppgiften
pekade fortsatt på bdc9. Se REPRODUCE.md för bevarade körkommandon.

Uppdatering 12:00 UTC: servern har fortfarande 0 byte tillgängligt och
Windows-uppgiften pekar fortsatt på bdc9. A är inte återställd. B:s
paketerade huvud-/webbläsar-/profilprov är utförda; längre sekventiell
1×/2×/5×-matris pågår via `.local/willys-storage-search-20261007/remaining_sequence.py`.
Den stoppar vid fel och kör aldrig parallella tunga prov. Slutlig runtime är
fortfarande `54cb2e8159a1`; senare commits gäller dokumentation och striktare
testverktyg. Se [testläget](releases/willys-storage-search-20261007/TESTS.md)
för bevarade SQLite-/testfel, korrigerad isolerad SQLite-väntetid och omkörningar.

Arbetsgren `feature/willys-storage-search-20261007`. Betan kör fortsatt rätt
dd12-image; ingen måltids-/prestandakod har aktiverats. Vid ny kontroll
7 oktober var serverns rotvolym åter full (0 byte tillgängligt), `/ready`
503 och planlagringen gav `SQLITE_IOERR_SHMSIZE`. Äldre 172 MB är historiskt.
[Aktuell A-rapport](releases/willys-storage-search-20261007/A-STATUS.md).

Lagringsfix `813eadda8e26`, separat ren reläkandidat ovanpå bdc9
`fe795e5b04f5a5ff973b71bb9bcdd28ca8668ce2`, installerad men ännu inte vald
av uppgiften. Den binder även temporärfiler till befintlig kommunarbetsyta
på D: och stoppar vid otillräcklig lokal/serverkapacitet. Windows nekade
`Set-ScheduledTask`; definitionen är verifierat oförändrad och fortsatt aktiv.
Användaren har fått ett avgränsat administratörsskript. S4U-prov och verklig
prisåterhämtning väntar på behörighet respektive serverutrymme. Köer, state,
rådata och tidigare paket bevaras. Inga nya prisanrop eller raderingar gjorda.

B utgår från fd2 och bevarar samtliga recept/fakta/import-/statusfiler.
Delprofil av exakt tidigare 176→880-korpus visade upprepad näringsprövning:
1,4 miljoner `input_evidence`-anrop i ett avbrutet 657-s-prov (inte ett
slutfört prestandaprov). Optimeringscommits `ada436763c8a` och
`54cb2e8159a126de26fa11cb1d393dc275238fd3` strömmar samma faktahash,
behåller ofta använda cacheposter inom samma gränser och delar
ingrediensunderlag efter separat validering av varje exakt recept.
Portionsberäkning, veckosökbudget och oberoende slutlig audit är oförändrade.

Paket `smako-server-54cb2e8159a1.zip`, SHA-256
`98446fac69395c8f7eded6c15f23f8194b5e26dffde1810e83cb5a9007338667`,
lokal image `sha256:8a537fc4d333d9fc17fd06916061ed481ba433951126688df51b6b4da19766f3`.
664 imagefiler hashkontrollerade. **Slutkvalificering pågår; ännu inte redo
för aktiveringsbeslut.** Första parade kalla huvudfallet: 98,94→90,07 s,
741,15 kr, full resultatekvivalens utom explicita mät-/byggmetadata och
ordning i medlemsmängden. Det är inte median eller klicktid. Råunderlag,
testloggar, isolerade profiler och pågående matris finns på D: under
`.local/willys-storage-search-20261007/`. Docker-data-VHDX ligger på D:.

# 2026-10-06: Statuskandidaten aktiverad; måltidsbibliotek färdig kandidat

Etapp A är genomförd med användarens uttryckliga app-only-godkännande:
beta.smako.nu kör dd12-image `c8362751b13a`, BUILD_ID
`status-reconnect-dd12cc80e98c`, kompletta recept på. Inga testdata eller
historisk klocka installerades. Samma mounts och aktuella data; alla tidigare
209 revisionsrader och 58 privata tillståndsrader har bevarade fingerprint.
Privat, integritetskontrollerad backup togs före bytet. Endast appen ersattes.
[Separat aktiveringsrapport](releases/status-activation-20261006/RESULTS.md).

Riktiga publika Chromium- och personliga WebKit-knappflöden passerade,
inklusive dubbelstart, omladdning/offline, byte, omräkning och revisions-GET.
Första WebKit-provet är bevarat som FAIL för statuslatens 16,12 s mot
testets 10 s-gräns, trots färdig meny utan sidfel. Servermetriken för samma
anrop är 159,367 ms; exakt fördröjningsorsak är fortsatt obelagd. Omkörning
är inte en appfix. Kontoinloggning är avstängd i faktisk drift; proven gäller gäster.

Etapp B är lokalt färdig på `feature/meal-library-20261006`, ovanpå eaf9dfd och dd12.
Låst implementation P2 `e2e5d248ee44`, slutlig runtime P3
`fd2cfda5490ac93295e6a2cef6b6b8408497f89e`, image
`sha256:b8541e165a2075c4c5657e1296c83e276f3aa8f59607292e32b653b60a7655fb`.
Senare lokala dokumentationscommits ändrar inte runtime. Den koden är inte
aktiverad. Receptformat, importerare, tre måltidstyper, gemensam veckokorg
och beständiga förberedelseartefakter är implementerade. 24 pilotrecept och
ett separat sexreceptspaket; ny data-only-import efter kodlåsning med
oförändrade runtimefiler. Två felaktiga versioner från det första
sexreceptsförsöket är återkallade, historiska GET bevaras.

Slutimagen har passerat strikta Chromium/WebKit-mobilflöden, gamla 15/20-
profiler, privat skafferi, ägarisolering, omstart och flagga av. 267 isolerade
historiska revisioner läses oförändrat. Hela P0–P3-matrisen med tre kalla
och tre varma nyberäkningar är färdig. Main 741,15 kr oförändrat;
nya fria enkla middagar 328,16→262,28 kr, kombinerat 495,44→418,17 kr.
De senare är olika receptval, inte billigare samma mat. Inga nya produktfakta.
Huvudklick utan omladdning 63,81/72,30 s: 60-sekundersmålet återstår; kall start är långsammare
än dd12, minnestoppen lägre. [Slutrapport](releases/meal-library-20261006/RESULTS.md).
Alla 30 slutkvalificeringar och 1×/2×/5×-skal-/invalideringsprov passerade.
5× huvudfall tog 919,89 s, topp 1,62 GiB: snabb storbibliotekssökning återstår.
Data-only-målet och återanvändning är verifierade; kandidaten är färdig för
separat aktiveringsbedömning, inte installerad. Fjorton strikta mobilprov; enkla
fem middagar för två tog 38,53 s via ordinarie knapp. Inga nya fakta/priser.

Beta är separat degraderad: planlagringen fungerar efter uttryckligt godkänd
arkivering av endast etappens nya byggmappar; `/health` 200 men `/ready` 503
för två för gamla Willys-underlag. Rätt dd12-image/JS och flagga på har
återverifierats. Senaste driftkontroll 20:36:31 UTC: bara 172 MB ledigt på rotvolymen.
Ingen ny insamling, ytterligare städning eller gränsändring har gjorts.
Ingen push, relä-, scheduler-, collector-, proxy- eller säkerhetsändring.

# 2026-10-06: Statusflöde och återanslutning – färdig lokal appkandidat

Gren `feature/status-reconnect-20261006`, slutlig paketerad runtime
**dd12cc80e98c79aa32c159223c8bc1ceeaaa7580**, ovanpå f5deaef/82de.
Senare commits för testverktyg och dokumentation ändrar inte runtime.
**REDO FÖR SEPARAT APP-AKTIVERINGSBESLUT.** Betan är oförändrad;
ingen aktivering, push, insamling, relä-, schema-, proxy- eller säkerhetsändring.
[Resultat och beslutsmatris](releases/status-reconnect-20261006/RESULTS.md),
[testbevis](releases/status-reconnect-20261006/TESTS.md),
[bevarade fel och osäkerheter](releases/status-reconnect-20261006/HISTORY.json),
[senaste app-only-anvisning](releases/status-reconnect-20261006/ACTIVATION.md).

Publikt och personligt flöde delar en sekventiell livscykelbunden statusläsare.
Egna avbrott stoppar klienten, aldrig serverjobbet. Sena svar spärras även
efter JSON-läsning. Begränsad återhämtning och manuell statusåterupptagning
behåller samma jobb; förlorat accepterat startsvar återfinns genom ägarbunden
GET med samma begäransreferens. Inget nytt beständigt bakgrundsjobbsystem.
Ofärdiga processminnesjobb överlever inte backendomstart; sparade revisioner gör det.

Slutimagen passerade 11 riktiga Chromium/WebKit-mobilresor, två separata
treägarkörningar (ostörd och kontrollerat statusavbrott), verklig gästcookieutgång,
cookieborttagning och omstart under ofärdigt jobb. En instrumenterad tung
beräkning per ursprungligt återhämtningsförsök, samma jobb och ägarisolering.
10 transport-, 41 backend- och 8 syntetiska frontendprov passerade.
Fullt resultat matchar 82de i 15 jämförelser, inklusive byte/omräkning;
741,15 / 787,56 / 910,39 kr är oförändrad historisk replay.
11 äldre HTTP-revisioner och 22 revisioner i separat lagringskopia läses
oförändrat. Flagga-av på samma image och äldre menyflöde fungerar.
Äldre binäråtergång och signerad kontosessionsexpiry är inte kvalificerade.

Ett nytt strikt WebKit-fel gav en reproducerad lucka före pagehide; beforeunload
stoppar nu pollningen tidigare. Exakt historisk WebKit-orsak och det separata
historiska socketfelet är fortfarande obelagda. Råa FAIL har bevarats.
Ostört huvudklick 67,81 s: 60-sekundersmålet återstår. Två CPU, 3 GiB och
en tung admissionplats är oförändrade. Recept, fakta, sökbudget, pris,
näring, variation och audit ändrades inte i denna etapp.

Paket `smako-server-dd12cc80e98c.zip`, SHA-256
`bc1ec3f2b03c228348bb63bcf3bba0f84f300b56aa375cdbe877f0dc8838484c`.
Verifierad image
`sha256:c8362751b13a6e649beadad2a3c27b9b5df8bfd1e2fa177ff68e01e1d7b8b2c7`.
Använd just den nya app-only-anvisningen vid ett separat framtida beslut;
återställ aldrig äldre databas över senare användararbete.

# 2026-10-06: Hela förpackningsköp och uttrycklig veckovariation – lokal kandidat

Gren `feature/package-variation-20261005`, slutlig runtime
**82de80e1ae898e2ab005c16c8d95e6670898be93**. Källbasen är den senaste
sammanhängande receptkandidaten inklusive senare relevanta ändringar. Ingen
produktionsaktivering, push, relay-, insamlings-, kommun- eller policyändring.
[Resultat och kvarstående begränsningar](releases/package-variation-20261005/RESULTS.md),
[fulla menyer och inköp](releases/package-variation-20261005/MENU.md),
[käll- och kandidatspår](releases/package-variation-20261005/RESEARCH.md),
[testbevis](releases/package-variation-20261005/TESTS.md),
[separat app-only-anvisning](releases/package-variation-20261005/ACTIVATION.md).

Fryst historisk replay: samma fem recept och mängder **747,77 → 741,15 kr** i
hela betalningen efter exakt identifierad 1 kg-ärtförpackning; ny kod utan nya
fakta gav ingen sänkning. Använd mängd 494,93 → 495,13 kr. Paprikapulver 37 g
finns till 25,50 kr i samma snapshot men saknar belagd variantbunden mildhet
och har inte valts. Fritt R2: fyra indiska/en mexikansk. Uttryckligt minst tre
kök och proteintak: 787,56 kr; ett av vart och ett av fem kök: 910,39 kr.
Olika rätter jämförs inte som besparing för samma mat.

Tre kalla R2-processer median 80,92 s, tre varma nyberäkningar 54,49 s.
Chromium/WebKit huvudklick 70,72/61,56 s: 60-sekundersmålet återstår.
WebKit rapporterade åter ett status-`fetch`-fel precis vid avsiktlig omladdning;
rått underkänt prov bevaras. Tre samtidiga klienter klarade kö, dubbelstart,
ägarisolering och 3 GiB-gräns efter ett separat avbrutet första klientförsök.
Elva äldre planrevisioner lästes med identiska hashvärden av nya imagen från en
kopia av tidigare testlagring. Blandning av olika förpackningsstorlekar i samma
ingrediensköp är ännu inte implementerad. Den förberedda appimagen är **inte**
installerad; se aktiveringsanvisningen före något separat framtida beslut.

# 2026-10-05: Receptens användbarhet och beräkningskostnad – verifierad kandidat

Gren `feature/recipe-usability-20261005`, runtime
**2816d50e4a14dd118015a4c047f2346435b981ef**. Efterföljande b58e2c1 förbättrar
endast testloggning. Ingen produktionsaktivering eller push.
[Slutrapport](releases/recipe-usability-20261005/RESULTS.md),
[kvarstående källunderlag](releases/recipe-usability-20261005/RESEARCH.md),
[separat aktivering och återgång](releases/recipe-usability-20261005/ACTIVATION.md).

Alla 48 paketversioner prövade i båda köplägena på samma frysta underlag:
**11 → 27 uppskattat, 7 → 19 exakt; överlapp 19, union 27 efter ändringen**.
Paketets användbara grundrätter ökar 6 → 14 respektive 4 → 10. Över hela
biblioteket är ökningen 52 → 57 respektive 26 → 32. Alla äldre godkännanden
består: 96/104 uppskattat och 44/104 exakt, identiska versionsmängder.
Källbunden mildhet för Santa Maria 200 g, Garant Risoni 500 g och SLV 588 för
äpple införs i befintliga faktavägar. Mängder och receptversioner är oförändrade.
C är berikad historisk replay; källornas nya hämtningstider har inte backdaterats.

Samtliga 16 nytillkomna versioner har faktiskt prissatts i fri veckosökning.
Huvudkorgen minskar **768,04 → 747,77 kr**, använd mängd 566,87 → 494,93 kr.
IN03-base och IN04-kikartor väljs fritt. Bred Varierad minskar 591,65 → 590,08 kr;
nio andra lyckade profiler behåller inköpstotalen. Indisk vegetarisk femmiddagsprofil
stannar fortfarande i begränsad variationssökning. Ingen global omöjlighet påstås.

Tre kalla och tre varma nya beräkningar per A/B/C, samma 2 CPU/3 GiB:
median kall **92,17 → 79,25 s**, varm **66,68 → 54,80 s**. Med enbart ny kod
och gamla fakta (B) är medianerna 74,55/47,00 s. Parat färskprocessprov på mobil:
Chromium 82,14 → 70,20 s, WebKit 80,88 → 68,94 s klick till renderat resultat.
**60-sekundersmålet är inte uppnått.** Samtliga råtider och sidoprofilernas
regressioner redovisas, inklusive bred Varierad 117,89 → 120,47 s i HTTP-provet.

Begränsad återanvändning av exakta prisvektorer, rangordningsmönster, ren text och
negativa uppslag minskar dubbelarbete utan lägre budget eller mindre receptpool.
Mutable kandidater använder exakt skalär prövning; 40 g-regressionen i 522 är rättad.
Mellanversion 0da nådde 3 GiB efter åtta HTTP-profiler. 2816 frigör avslutade
felramars lokala variabler och oåtkomliga sökcykler inför nästa antagna jobb.
Slutmatrisens alla tolv profiler klarade samma process utan OOM. Slutaudit kvarstår.

**1 076 regressionstester PASS**, Ruff och riktad compileall PASS. Chromium och
WebKit mobil/desktop genomförde ordinarie knappflöden, omladdning, byte, explicit
omräkning och återläsning efter faktisk omstart. 28 explicita versions-/köplägesprov
(16 uppskattat/12 exakt) täcker alla nykvalificerade versioner, 58 revisioner
bevarade efter omstart. Tre samtidiga klienter, ägarisolering och dubbelstart PASS.
51 tidigare testrevisioner bevarade med flagga på/av. Isolerad slutbackup:
75 planer/141 revisioner, SQLite-integritet PASS. Inga produktionsdata återställda.

**Testanmärkning:** första WebKit-mobilförsöket fick ett statusanropsfel med
"access control checks" efter passerade funktioner. Full omkörning och parat
färskprocessprov passerade. Orsaken är inte fastställd eller påstått rättad;
underkänd rapport bevaras och ska beaktas vid framtida aktiveringskontroll.

Paket `.local/releases/recipe-usability-memory-20261005/smako-server-2816d50e4a14.zip`
(2 832 452 byte), SHA-256
`c74ad647643e949085f048644492432f6226c3d01a2bb90d6ae088b798f013b4`.
Image `sha256:362e0eabf703d515b96ffad1412bd80d0c97a42927738fa75e1a033db240415d`.
650 installerade runtimefiler manifestverifierade; pip check och offline browser PASS.
Föreskrivet framtida BUILD_ID `recipe-usability-2816d50e4a14`.
Aktivering kräver nytt beslut. Återgång: flagga av i samma nya image, bevara alla
revisioner; återställ aldrig äldre databas eller äldre binär över nyare planer.

Beta är fortsatt ready på **complete-recipes-17a9c1330dcc**, flagga true;
app, scheduler, Linux-relä och proxy har oförändrade container-/image-ID:n och
starttider. Windows-relä, insamling och scheman är orörda. Egna testcontainrar är
avslutade; isolerad backup och bevis bevaras i `.local/recipe-usability-20261005`
och `/var/tmp/smako-recipe-usability-20261005`. Manifestet binder rapporternas
råbevis till hashvärden. Privata sessionsuppgifter/databaser ligger utanför Git.

# 2026-10-05: Innehållspaket 24 + 24 integrerat, ej aktiverat

Gren `feature/recipe-content-pack-20261005`, runtime
**dbd89abbed0a0e3b9d8955badabb17615d6c8d09**, BUILD_ID `content-dbd89abbed0a`.
[Slutresultat, kvalificering och mätningar](releases/recipe-content-20261005/RESULTS.md),
[separat app-only-aktivering och funktionsåtergång](releases/recipe-content-20261005/ACTIVATION.md).
Ingen produktionsaktivering, Git-push, insamling eller driftpolicyändring.

Paketets färdiga innehåll infördes prioritet 1 före 2 utan ny receptgenerering.
24 familjeförslag jämfördes mot alla 104 aktuella versioner: 14 nya grundrätter,
10 befintliga familjer med motiverade variationer. 48 nya 2.0.0-versioner;
totalt 62 grundrätter/152 versioner. Alla äldre recept bevarade och hashoförändrade.
Komponentmängder, former, varianternas egna steg och processvatten bevaras.
Ny metod `smako-authored-input-v2` redovisar uppskattad näring och okända
beredningsförluster utan att kräva att källans avhällda kokvatten serveras.

På samma autentiska frysta pris-/faktaunderlag kvalificeras 11/48 nya versioner
med uppskattade köp och 7/48 med exakta köp. Uppskattad full näringsprofil:
96 → 107 kvalificerade versioner, 47 → 52 distinkta familjer. De 37 datastoppen
beror bland annat på milt paprikapulvers näring, chiliflakes, avrunnen majs,
pita/småpasta och ätbar mängd för ägg/tonfisk. Inga fakta eller mängder uppfanns.
Tidigare preliminära 23 kvalificerade/698,77 kr är underkända som slutacceptans
efter striktare kontroll mot innehållspaketets angivna ingredienser.

Huvudfallet bevarar exakt recept, produkter, mängder, näring, audit och rester:
768,04 kr inköp/566,87 kr använd mängd. Billigast 534,40 kr och Varierad 808,76 kr
är också oförändrade före/efter. Utbyggnaden ger längre söktid, ingen dold besparing:
huvudfall kall process 82,49 → 93,11 s, varm nyberäkning 58,00 → 64,93 s;
Billigast kall process 66,59 → 109,77 s (inklusive tidigare pools omvalidering),
Varierad 135,02 → 149,84 s. Samma 2 CPU/3 GiB, oförändrad sökbudget, en observation
per sidofall. 60-sekundersmålet är inte uppnått. Ingen färdigplancache används i måtten.

2 258 backendtester, deterministisk import, Ruff och compileall PASS.
48 versioner renderade i båda webbläsarna på mobil/desktop. Riktigt publikt
Chromium-flöde väljer nya IT04-base vid byte, omräknar och läser revisionerna
1–3 efter faktisk omstart; personlig WebKit-mobil gör motsvarande femköksflöde.
Ägarisolering/dubbelstart passerar. Angivet 500 g potatisskafferi används med
300 g utan automatisk restbokföring. Inga fysiska iPhone- eller provlagningspåståenden.

Serverpaket `.local/releases/recipe-content-final-20261005/smako-server-dbd89abbed0a.zip`,
SHA-256 `e6fe6c4698af816d1b1c8f8f36e23a7be770008237672927557ec38a27ebef4c`,
image `sha256:a7b0440c6efb19cc2f4b25ae12689656f19f881a2446d7e4f2249d00d0950727`.
Alla 649 installerade runtimefiler verifierade mot paketet. Produktion är fortsatt
ready på `complete-recipes-17a9c1330dcc`, flagga true, oförändrad image/starttid.
**Efter sparade 2.0.0-planer: funktionsåtergång med flagga av i samma nya image,
inte äldre binär eller återställd databas.**

Fulla lokala bevis `.local/recipe-content-20261005`, serverns isolerade bevis
`/var/tmp/smako-content-20261005`. Testcontainer `smako-content-isolated` stoppad,
eget tillstånd och alla revisioner bevarade med konsistent slutbackup. Frysta
indata från tidigare prestandaarbete har inte ändrats eller kopierats till produktion.

# 2026-10-04: Femköksplanering – testad prestandakandidat, ej aktiverad

På `perf/five-cuisine-planning`. Runtime **b89fadb96c4edc4576cb4daae6c5d80e553ad8ca**,
BUILD_ID `five-cuisine-b89fadb96c4e`. [Resultat och samtliga prov](releases/five-cuisine-performance-20261004/RESULTS.md),
[app-only-aktivering/återgång](releases/five-cuisine-performance-20261004/ACTIVATION.md).
Ingen Git-push eller produktionsaktivering. Det äldre godkännandet för 17a9c13
är inte ett beslut för denna kandidat. Produktion är fortsatt ready på 17a9c13,
flagga true, samma container/image; autentisk ursprungsrevision hashoförändrad.

Exakt sparad femköksbegäran återfanns: fem middagar × fyra, Balanserad,
10–15 ingredienser, 30 g protein, inget tidstak, fem tillåtna kök, butikstak tre,
uppskattade köp och separat näringsmedgivande. Fullt autentiskt pris-/faktaunderlag
frystes isolerat. Reproducerad meny, mängder, produkter, näring, audit och
768,04 kr är oförändrade. Historiska belopp är inga nya produktionspriser.

På samma 2 CPU/3 GiB och identiska beroenden: median kall ny process
**204,8 → 83,6 s**, varm **ny beräkning 179,2 → 58,9 s**, tre prov vardera.
Tre samtidiga användares sista resultat **582,7 → 194,1 s**, kö separat.
Brett Varierad **345,2 → 100,9 s**, identisk hel plan. **60-sekundersmålet
från klick är inte nått**: slutliga Chromium/WebKit-knappar gav 72,3/75,0 s.
Nästa kostnader är förpackningsberäkning, audit och kall fakta/indexberedning.

Begäranslokal begränsad återanvändning av kvalificerade kandidater, normaliserade
recept och näring; befintlig korgmotor undviker butiker som saknar varje kvalificerad
vara. Inga mindre sökbudgetar, receptmängder, alternativa prismotorer eller ändrade
insamlingsinställningar. Svenska näringsdecimaler och naturligare metodvisning
ändrar inte sparat receptinnehåll. Ett befintligt bytesfel reproducerades i 17a
och rättades genom tidigare kontroll mot de redan låsta rätterna.

2 226 backendtester och 1 664 tester för oförändrad grocery_data-kod PASS.
Alla 104 varianter renderade i Chromium/WebKit mobil/desktop. Riktiga publika
Chromium- och personliga WebKit-mobilflöden PASS: generation, omladdning, byte,
omräkning och revision 1–3 efter omstart. 19 tidigare testrevisioner oförändrade,
29 vid slutkontroll. Ingen fysisk iPhone eller fysisk provlagning påstås.

Paket `.local/releases/five-cuisine-final-20261004/smako-server-b89fadb96c4e.zip`,
SHA-256 `eafba3aa7b4ab59d8fb92e258c995792caff9b9a3eb41838c3481b47142f982b`.
Image `sha256:80dd265779182eb750453e3b12a2249e71a9ed845f62c6e9c3c5f1a3a86ee4d1`;
645 runtimefiler, pip check och offline-Chromium PASS.
Fulla privata bevis och testdata ligger i `.local/five-cuisine-20261004` och
`/var/tmp/smako-five-cuisine-20261004`. Testcontainer `smako-five-cuisine-isolated`
är stoppad efter slutförda prov; data och revisioner är bevarade. Den använder
enbart dessa isolerade data. Kopiera aldrig replayklockan/databaserna
till produktion. Tidigare UI-arbetskopia i `D:/Projects/Smako-worktrees/five-cuisine-presentation`
är bevarad; dess integrerade ändringar finns redan i root-branchens commits.

# 2026-10-03: Nya receptlagret aktiverat på beta.smako.nu

Uttryckligen godkänd app-only-aktivering är genomförd. Slutkontroll
**2026-10-03 15:38:23 UTC (17:38 svensk tid)**: beta.smako.nu är ready,
BUILD_ID **`complete-recipes-17a9c1330dcc`**, featureflagga **true**.
Aktiv runtime `17a9c1330dcc72ff9750a3fa680fa6982f7ed99b`, image
`sha256:99bf3bfcb4f395ec1a06df23649e0241903d52bb5bba40ca4336abbd2bbecc35`.
Ingen Git-push. Ingen funktionsutveckling under aktiveringen.

[Full driftrapport](releases/complete-recipes-production-20261003/RESULTS.md),
[sanerade aktiveringsbevis](releases/complete-recipes-production-20261003/ACTIVATION-RESULT.json),
[faktisk produktionsmeny och inköp](releases/complete-recipes-production-20261003/LIVE-MENU.json).

På vanliga betasidan och `/personal`: **Receptstil → Välj receptläge →
Genomarbetade middagar**. Där finns matkök, ingrediensintervall, tid och
proteinmål. Befintliga vardagsrecept är kvar. Uppskattade köp och medgivande
till uppskattad näring är fortsatt separata val; formulärberoendet verifierat.

Före bytet körde produktion fortfarande 74c9077; alla 419 runtimefiler matchade
dess manifest. Kandidatpaketets fulla SHA och 651 filer verifierades lokalt
samt på servern. Installerad kandidatimage och 644 runtimefiler kontrollerades.
Befintlig Compose-wrapper `/opt/smako/compose` har fått beständig override sist:
`/opt/smako/overrides/complete-recipes-17a9c1330dcc.yaml`.
Exakt konfigjämförelse tillåter endast appens image, BUILD_ID och flagga.
`current`-länk, basfiler, scheduler, proxy, collector, migrate, backup-tjänst,
Windows-relä, insamling, scheman, policy och kommunurval är oförändrade.

Gemensamt driftlås, vilande app före omstart samt konsekventa online-backuper
före båda stegen. Privata backup-/konfig-/tillståndsbevis finns under
`/opt/smako/evidence/complete-recipes-20261003`:
`backups-off/20261003T150917Z` och `backups-on/20261003T152044Z`.
Alla **195 ursprungliga planrevisioner** och **52 ursprungliga personliga
tillstånd** är bevarade. Slutkontroll: **207 revisioner**, alla läsbara med
PlanStore och SQLite quick_check ok. Inga äldre databaser återställdes.

Flagga-av-prov: äldre publikt 101,781 s, personlig 15/20-profil 283,296 s,
401,35 kr och oförändrade 40/30/20-proteinkrav. Därefter beständig aktivering.
På faktisk HTTPS-beta passerade Chromium mobil/publikt (101,797 s), WebKit
mobil/publikt (92,610 s), WebKit desktop/personligt (92,797 s) samt ett nytt
äldre publikt desktopprov (102,688 s). De nya proven gav fem middagar för två,
grekiskt/mexikanskt, 10–15 ingredienser, högst två butiker, 40 min och 40 g,
beräknat inköp cirka 738,17 kr. Omladdning under generering, byte till annan
grundrätt, omräkning, revision 1–3, inköpslista, kvalitetsmärkning, DOM/layout
och ägarisolering kontrollerades. Äldre testägda planer/val återlästes efter
flaggbytet. Ingen fysisk iPhone och ingen syntetisk smakfeedback.

WebKit/personligt fick först en automatisk klick-timeout efter lyckat byte.
Samma ägares revision 2 öppnades igen via Min plan; den vanliga synliga och
aktiverade knappen räknade om på 13,281 s utan force-klick eller appändring.
Alla tre revisioner stämde efteråt. Både första verktygsutfall och fortsättning
är bevarade. Inget kvarstående konkret app-/datakompatibilitetsfel konstaterat.

Riktig klocka och aktuellt publicerat underlag användes: universe
`price-universe:a2eb6ab5ffec325392ad98c69e6483a3b901312359c5c659673ea7da5fadd0c6`,
byggt 2026-10-03 11:31:32 UTC. Inga replaypriser/testdatabaser kopierades till
produktion. Köp- och näringsuppskattningar är märkta; färskhetsgränser 36/48 h.
Kandidatens källluckor kvarstår enligt rapporterna nedan.

Återgång vid framtida fel: samma nya image, endast flagga av i den beständiga
overriden, exakt konfigjämförelse och enbart appåterskapning efter jobbslut.
Bevara senaste data och revisioner. Följ [nya receptlagrets aktiveringsordning](releases/complete-recipes-20261002/ACTIVATION.md),
inte den historiska Lund-/reläreleasens byte av current eller globala versioner.

# 2026-10-03: Nästa receptlager – testad kandidat levererad lokalt

Arbetet är slutfört på `feature/complete-recipe-layer`, från faktiska `402a5c9`
ovanpå publika `74c9077`. Ingen produktionsaktivering eller Git-push.
Runtime är låst till **`17a9c1330dcc72ff9750a3fa680fa6982f7ed99b`**.
Efterföljande commits ändrar dokumentation och acceptansskript, inte runtime.

[Slutredovisning](releases/complete-recipes-20261002/RESULTS.md),
[alla sju menyer, produkter och inköp](releases/complete-recipes-20261002/MENUS.md),
[kontrollerad aktivering och beständig flaggåtergång](releases/complete-recipes-20261002/ACTIVATION.md).

Paket `.local/releases/complete-recipes-20261002/smako-server-17a9c1330dcc.zip`,
2 739 005 byte, SHA-256
`d3327b9137d4310707118b5272bc826ed0403ebd6d0c0ab935bb1196efee060a`.
Image `sha256:99bf3bfcb4f395ec1a06df23649e0241903d52bb5bba40ca4336abbd2bbecc35`:
645 runtimefiler matchar; pip check och offline-Chromium som appanvändare PASS.
Featureflaggan är av som standard. Planrevisioner ska bevaras även vid återgång.

Både publikt och personligt flöde har matkök, ingrediensantal, tid, kost,
valfritt proteinmål och tillåtna variationer. Valen följer jobb, generering,
ordinarie pris-/korgmotor, sparning, receptbyte och uttrycklig omräkning.
Bibliotek 1.4.0 har **48 distinkta grundrätter och 56 variationer**.
Samtliga 104 är prövade på slutimagen: **94 kvalificerade versioner, 47/48
fungerande grundrätter, 43/48 original**. Alla sju fria femmiddagsmenyer PASS.
De tio verkliga källstoppen gäller kapris, kidneybönors mängdbasis och mjölkens
näringsbasis. Piccata saknar fungerande variant i detta underlag. Två produkter
med motstridiga energipar spärras; normal produktkvalificering hittar annan
färs och källstyrkt färdigt matbröd i 16 versioner utan ändrade receptmängder.
Ingen fysisk provlagning eller fysisk iPhone-testning har utförts.

Full offline-regression på oförändrad slutruntime: **3 887 PASS**, 0 fel eller
överhoppade, 2 042,099 s, inga spärrade nät-/äldre källåtkomster. 252 riktade
integrationsprov plus 6 slutliga HTTP-runner-kontrakt PASS. Ruff för samtliga
ändrade Python-filer, compileall och pip check PASS.
[TESTS.json](releases/complete-recipes-20261002/TESTS.json) bevarar även äldre körningar.

Ren slutmätning med identiska frysta underlag/beroenden och 2 CPU/3 GiB:

- Äldre publikt flöde 161,047 s kallt mot baseline 328,424 s (**−50,96 %**),
  2,264 s varmt. Recept, ingredienser och hela korgen identiska: 168,55 kr.
- Komplett grekisk/mexikansk 5×2, 10–15, 40 min/40 g, Billigast: 105,721 s
  kallt / 95,976 s varmt, samma korg 738,17 kr.
- Brett Varierad HTTP-prov: 359,675 s. Sex minuters väntan kvarstår som
  prestandabegränsning; ingen global optimalitet påstås.

Alla fem slutliga HTTP-fall PASS: gamla publika anrop, komplett 15/20-profil,
Varierad, exakt2→uppskattat2→uppskattat3 (796,15→682,23→665,62 kr) och tre
samtidiga användare. Tre klienter fick separata planer efter 24,66/48,29/70,82 s,
högst samplat 2,073 GiB. Befintlig kö med en aktiv beräkning användes.
Dubbelstart, ägarisolering och återläsning verifierades.
[HTTP-bevis](releases/complete-recipes-20261002/HTTP-ACCEPTANCE.json).

Slutliga Chromium mobil/personligt och WebKit desktop/publikt PASS:
generering 95,328 respektive 86,593 s, omladdning under jobb, receptbyte,
omräkning, versioner/redskap, DOM/layout och sparade revisioner. Kontrollerad
omstart bevarade alla 34 testrevisioner exakt, inklusive alla 28 äldre.
Två feedbackrader matchar sina sparade receptversioner vid skrivskyddad
DB-verifiering. Tidigare fyra browserfall täcker båda motorerna på mobil och
desktop, tillfälligt nätavbrott och flagga-av-omstart, med egna versionsbindningar.
[UI-bevis](releases/complete-recipes-20261002/UI-ACCEPTANCE.json),
[omstart](releases/complete-recipes-20261002/FINAL-PERSISTENCE.json).

Isolerat test kör på **http://127.0.0.1:18122** via befintlig SSH-tunnel,
BUILD_ID `recipe-candidate-17a9c133-0476bf36`, featureflagga på. Det använder
frysta historiska priser från 2026-10-02, inte löften om dagens inköp.
Inga acceptansjobb återstår på resursen. Fjärrrot
`/var/tmp/smako-complete-recipes-20261002`, endast syntetisk privat teststate.
Replayklocka/state/testlauncher får aldrig användas som produktionskonfiguration.

Produktion kontrollerad skrivskyddat 2026-10-03 10:12:15 UTC: HTTP200/ready,
fortfarande build `74c9077001b3084317f36630fd38ce48e4663473`. Relä, scheduler,
insamling, femkällorspolicy, kommunomfattning och 36/48-timmarsgränser orörda.
[Oberoende paket- och driftgränskontroll](releases/complete-recipes-20261002/PACKAGE-BOUNDARIES.md).
Råfiler och privata/syntetiska testplaner ligger utanför Git i `.local` och
befintliga agentworktrees. Återstående begränsningar är dokumenterade källluckor,
uppskattad näring/tillagningstid, utebliven fysisk provlagning och söktiderna.

# 2026-10-02: Uppföljning – korrekta fältfel och fungerande lång generering

Appen kör nu Git `74c9077001b3084317f36630fd38ce48e4663473`, image
`sha256:80e8ba59c9b04c8bff668062da2bf1937eae236881472449e2a0180f42387180`.
Det ersätter appversionen i följande historiknotering. Scheduler/källjobb
är fortfarande `08c1374`. [Full rapport och bevis](releases/public-menu-followup-20261002/RESULTS.md).

Två fel är reproducerade och rättade: postnummer utanför artefaktens
aktiverade täckning gav missvisande 503/prisuppdatering och avstängd knapp;
WebKit bröt lång generering efter cirka en minut. Postnummerfel ger nu
422 på rätt fält, dataproblem har egna koder och vanlig 503 beskrivs som
tjänstefel. Publika knappen använder sessionsbundna, begränsade planjobb
med korta statusanrop runt samma planner och samma sparning. Ingen
policy, optimeringsgräns eller medgivande ändrat. Oavslutade transportjobb
löper ut vid appomstart; färdiga planer ligger kvar i PlanStore.

Fem publika knapp-prov PASS: WebKit mobil Balanserad (kall 338,359 s)
och Billigast; Chromium ren session samt båda mobilvalen. Fem middagar × två,
max tre inköpsställen, exact/mixed, verkliga medlems-ID:n, fullständiga recept,
inköpslista, kostnad, kvalitet och identisk återläsning verifierade.
Balanserad 168,55 kr, Billigast 125,10 kr. 308 HTTP-anrop korrelerade med
backend; frontendhashar matchar. Fyra separata 15/20-regressioner i samma
isolerade image PASS, 440,72 kr. Ingen fysisk iPhone har provats.

App-only-byte under driftlås cirka 11:15 CEST. Alla 188 tidigare revisioner
oförändrade, 193 efter proven. Prismanifest, proxy, scheduler och miljö
(utom appens BUILD_ID) bevarade. Skyddad backup/återgång under
`/opt/smako/evidence/public-menu-followup-20261002`. Testtjänster stoppade,
bevis bevarade. Ingen Git-push, städning eller Malmö-aktivering.

Användarens Fel-ID från 10:19 är matchat till 503/1,658 ms i gamla builden,
men den historiska body:n och det aktuella postnumret är inte bekräftade.
Det enskilda försöket tillskrivs därför inte säkert postnummerfelet.
Kalla menyberäkningar tar fortfarande cirka fem–sex minuter.

# 2026-10-02: Publik veckomeny – app-hotfix efter aktiveringen

Se [felsökning, request-ID:n och offentlig knappacceptans](releases/public-menu-20261002/RESULTS.md).
Webbappen kör nu Git `14cc716ae54e2bb09ceaed5c4e3c2159e3a9c97d`, image
`sha256:7dcc2c5c9b35a0f0ab68e1e1b180eada790c3f0a045d8f6a63c883ee7461ebef`.
Scheduler/källjobb ligger avsiktligt kvar på nedanstående 08c1374-release.
Detta var ett app-only-byte under befintligt driftlås, inte en ny Lund-aktivering.
Relä, scheman, femkällorspolicy, autentisering, prismanifest och alla 179 tidigare
planrevisioner bevarades. Återgångsunderlag och plandatabackup ligger skyddade under
`/opt/smako/evidence/public-menu-20261002`; återgång återställer enbart appkod.

Grundfelet var att publika femmiddagsformulärets MealPlanService skapade en
liveprovider innan den förberedda lokala PriceUniverse-vägen valdes. Därmed gav
normal drift utan OWN_GROCERY_BASE_URL ett missvisande 422. PersonalPlanner-provet
15/20 använde en annan kodväg. Följdfel i exakt medlemsprojektion, frivillig
obegränsad butiksjämförelse och kampanjsökningens cache/nested-gränser rättades
med reproducerande regressioner. Felpresentationen skiljer nu fältfel,
dataspärr, timeout och serverfel och visar Fel-ID med bibehållna val.

Publika mobilprov för Balanserad och Billigast med 22350, 5 × 2, tre inköpsställen,
exact, mixed och sex faktiskt tillgängliga medlemsprogram har passerat via knappen:
168,55 respektive 125,10 kr, verifierad korg, fullständiga recept och identisk
sparning/GET. Ren desktopsession utan medlemskap passerar också: 168,55 kr,
313,984 s, identisk sparning/GET. Fyra separata 15/20-profiler passerar med
440,72 kr; alla sju anrop matchas mot backendlogg och nya build-ID:t.
Kall femmiddagsberäkning tar
fortfarande flera minuter. Ingen fysisk iPhone har provats. Ingen Git-push.

# 2026-10-02: Lund 1281 aktiverat i normal drift

**Aktiveringen är genomförd och båda schemana är återupptagna.** Läs
[aktuellt aktiveringsprotokoll](releases/lund-20260929/ACTIVATION-LIVE-20261001.md),
[dess sanerade bevis](releases/lund-20260929/ACTIVATION-LIVE-EVIDENCE.json) och
[drift-/återgångsordningen](releases/lund-20260929/ACTIVATION.md).
Äldre statusnoteringar nedanför är bevarad historik, inte aktuella blockerare.

Fem godkännanden är givna och tillämpade: femkällorspolicy, slutlig server,
bdc9-reläbyte, Windows 01:30/09:30/17:30 och serverns behovskontroll var 15:e
minut. Inhämta inte dessa igen för samma omfattning. Backup är fortsatt 02:47;
35h behov, 36h varning och 48h stopp är oförändrade. Ingen säkerhetspolicy ändrad.

Serverruntime `08c137475d9ca96a6ef7673245a639c8c5c9e922`, bild `sha256:d8a166fa7ee162cd0570f9d8089ff800e00d9c949ac3c674e387c5fff1538dd7`.
Alla fem Compose-jobb använder bilden. Windows använder oförändrat
`D:\smako-local-relay\releases\bdc9f7df4170`, separat kommunarbetsyta och
scheduler/receiver som transportmål. Återläst befintlig uppgift: Ready,
ossia/S4U/Limited, tre lokala tider, nästa 2 oktober 01:30. Övriga XML-fält/ACL
är bevarade. Servern kör faktisk `cron -f`, nästa kontroll vid återupptagandet
00:15. Framtida schemakörningar är ännu inte verifierade.

En autentisk Willys-leverans, en import, atomisk publicering, faktisk reload
och beständigt kvitto passerar. Återleverans `already_active`; både relä och
server `not_due` med noll prisanrop och oförändrade observationer. Serving
`57ca714e…`, 44 077 råproduktposter, samtliga 2 232 råfiler hashverifierade.
Fyra 15/20-profiler: 440,72 kr, två butiker, checkout PASS, 40/30/20 uppfyllt.
Näring är separat VERIFIED/ESTIMATED. Cirka-vikt/lösvikt/flerköp/villkorat
kampanjval och spärrar passerar. **Uttrycklig omräkning PASS**, revision 1→2;
nio verifieringsrevisioner identiska efter faktisk appomstart, fel ägare 403.
Alla 170 ursprungliga planrevisioner är oförändrade; totalt 179 vid kontrollen.

Backuper och gamla köer är bevarade. Inga gamla Primat-artefakter fick falskt
publiceringskvitto. Serverns skyddade backup ligger under
`/srv/smako/backups/lund-activation-20261001T2110Z`; lokala bevis/backup under
`.local/activation-live-20261001`. `/opt/smako/current` och `/opt/smako/compose`
använder nu slutpaketet och skyddad `activation-private.env`; äldre env/policy
är separat bevarade. Använd inte gamla bilden som återgångsmål.

Godkänd reservdrift är slutbildens `app.recovery`, senaste checkpointade
planbas read-only och befintlig autentisering; ingen nyplanering/omräkning/import.
Den är **inte aktiverad**. Full normal drift är aktiv. Begränsad fysisk
utbudstäckning, karantän och schema-/datorbortfallsrisker finns i protokollet.
Konservativ manifestgräns är 2 oktober 13:17:53 CEST; förfallna frivilliga
källkontroller beräknas omkring 00:30. Bekräfta verkliga kommande körningar,
använd aldrig rebuildtid som observationstid.

Ingen applikationskod eller identifierat paket ändrades under aktiveringen.
Verifieringsverktyg/driftunderlag har ändrats lokalt; ingen push, städning eller
Malmö-aktivering. Nästa separat etapp: kampanjfönstren söndag–måndag och
onsdag–torsdag samt mätning av basprisförändringar, inte implementerat här.

## Bevarad historik före genomförandet

# Aktivering 2026-10-01: schema godkänt, stopp vid Windows-behörighet

Alla fyra beslut är givna: femkällorspolicy, server med begränsad läsåtergång,
bdc9-reläbyte och lokala 01:30/09:30/17:30. Begär inte dessa igen.
Faktisk uppdatering/paus av befintlig uppgift nekades 19:50:00 UTC med
`0x80070005 E_ACCESSDENIED` för ossia utan förhöjning. Uppgiften är byteidentisk,
fortfarande Ready med enbart 01:30. Ingen paus/serverändring/insamling utförd.
Läs [aktuellt operatörssteg och bevis](releases/lund-20260929/ACTIVATION-OPERATOR-20261001.md).
Slutligt granskat skript `scripts/release_verification/set_lund_task_paused.ps1`
stagerar godkända Arguments/WorkingDirectory och tre lokala tider, lämnar
befintlig uppgift DISABLED och bevarar principal/övriga inställningar. Det ska
köras förhöjt som samma ossia, utan policyöverstyrning. Därefter läs tillbaka
och fortsätt serverförkontroller/paus/backup/samordnat byte enligt ACTIVATION.
Återuppta inte scheman före faktisk produktionsacceptans.
Nytt bdc9-not_due-prov på kopierat autentiskt tillstånd: 0 externa anrop,
byteidentiskt kvitto/källtid. Normal drift/nyplanering/uttrycklig omräkning/GET
är ännu inte provade i ny produktion. Inga gamla blockerare återinförs.

## Föregående stopp före det nu givna schemagodkännandet

**Tre produktionsbeslut är nu uttryckligen godkända, villkorat av förkontroller.**
Godkännandena ska inte begäras igen. Ingen aktivering har gjorts: bdc9-reläets
35-timmarsregel ihop med enbart daglig 01:30-start ger ett återkommande glapp
vid 48-timmarsstoppet. Användarens uttryckliga stoppvillkor i B gäller.
Läs [aktiveringsprotokollet](releases/lund-20260929/ACTIVATION-PREFLIGHT-20261001.md)
och [aktuella driftordningen](releases/lund-20260929/ACTIVATION.md).
Förslag till separat schemabeslut: behåll 01:30, lägg till 09:30/17:30-kontroller
med oförändrade behovsregler, konto och PT3H. Inget schema har ändrats.
Produktion kör fortsatt gammal bild; läsande kontroll visade stale och /ready 503,
170 planrevisioner. Inga planer, köer, policyer eller drifttillstånd ändrades.
Releaseidentitet/filer verifierade. Återstående aktuella aktiveringskontroller
är inte generellt PASS. Tidigare kö-/återgångs-/S4U-bevis gäller fortfarande.

## Bevarad releasebedömning före villkorat aktiveringsgodkännande

**REDO FÖR SEPARAT AKTIVERINGSBESLUT**, med begränsad återgång till sparad
planläsning. Köövergång och kompatibilitetsåtergång är implementerade och provade.
Läs [TRANSITION.md](releases/lund-20260929/TRANSITION.md), dess maskinläsbara
bevis och [ACTIVATION.md](releases/lund-20260929/ACTIVATION.md) före driftarbete.
Slutlig runtime är `08c137475d9ca96a6ef7673245a639c8c5c9e922`; server-/
återgångsbild `sha256:d8a166fa7ee162cd0570f9d8089ff800e00d9c949ac3c674e387c5fff1538dd7`.
Föreslaget Windows-relä förblir det oförändrade liveprovade bdc9-paketet.
Nytt Windows-ZIP är byggt men inte installerat/S4U-liveprovat.

Gamla kön arkiveras återupptagbart under befintliga lås och hålls separat;
blockerad gammal Primat-publicering behöver **inte** lyckas före bytet.
Återgångsmålet är slutbildens `app.recovery`, senaste checkpointade planbas,
read-only, befintlig autentisering och full sparad JSON. Det stöder läsdrift,
inte nyplanering/omräkning/import; de funktionerna vägras kontrollerat.
Ingen äldre databas eller kö återställs över nytillkommet tillstånd.
168 fokustester passerade i ren klon; paket reproducerade, Docker/HTTP-prov
och verklig omstart redovisade i det nya underlaget. Produktionsbild, aktiv
Windows-uppgift och säkerhetspolicy/scheman är oförändrade; ingen push.
Femkällorspolicy, serveraktivering (inklusive begränsad återgång) och byte av
Windows-uppgiften är fortfarande tre separata, ej fattade beslut.

## Bevarat S4U-livebevis och tidigare driftstatus

**Senaste granskning 2026-10-01: obevakad livehämtning och leverans PASS.**
Operatören körde den isolerade uppgiften 09:44:23–10:33:32 svensk tid.
`ossia`, S4U/Limited, session 0, icke-interaktivt; giltigt startkvitto.
1 255 verkliga Willys-anrop (två återhämtade HTTP 500), 18 939 produktposter,
ny artefakt `5b1a2b6b…`, exakt en mottagarimport `293e1533…`.
Faktisk reload och senare HTTP-läsning visar manifest `19cd1da8…`, **44 066**
råproduktposter; samma ID/hash i beständigt framgångskvitto. Mottagare,
relä, observatör och Task Scheduler rapporterar 0 för denna körning.
Se [S4U-LIVE.md](releases/lund-20260929/S4U-LIVE.md) och dess hashade bevis.
Granskningen startade inget nytt jobb, samlade inte in och ändrade inte drift.
Starta inte igen med stöd av gamla instruktioner eller gammalt startkvitto.

[Förkontrollen](releases/lund-20260929/S4U-PREFLIGHT.md) är historik:
dess 44 080-manifest har ersatts av denna liveleverans. Profilproven på
42 491 och de tidigare driftproven på 44 132 är fortfarande separata bevis.
Inga säkerhetspolicyer, uppgiftsargument eller produktionsbeslut ändrades.

**Historiska driftspärrar från 2026-09-30, ersatta av TRANSITION ovan.** Läs även
[OPERATIONS.md](releases/lund-20260929/OPERATIONS.md) och uppdaterad
[ACTIVATION.md](releases/lund-20260929/ACTIVATION.md). Runtime/paket är kvar
på bdc9f7d i det historiska underlaget; dess fortsättning ändrade endast provverktyg och underlag.
Faktisk produktionsbild `54dde838…` tappar 64/12 planfält och ger 500 för
`kind=campaign`, även efter omstart med gammalt manifest. Ny bild återläser
alla tre nya planer identiskt på 44 132-manifestet; samtliga 37 revisionsrader
bevarade. Originalpolicyn stoppar publicering av den gamla kön genom saknad
Primat-bas. Det nya Windows-paketets SSH-replay/kvittot/not_due passerar;
det är separat från det nu granskade obevakade liveprovet. Registrerings-
och S4U-livehindren är stängda för provad konfiguration. Versionsövergång
och säker återgång är fortsatt blockerade och har inte omprövats här.
Aktiva Windows-uppgiftens XML är byteidentisk före/efter. Produktionens
bild, policy och scheman är oförändrade; ingen push. De tre
produktionsbesluten är fortfarande separata och ej fattade.

### Ursprungligt releaseunderlag före driftkompletteringen

Arbeta i **D:\Projects\Smako** på `release/lund-relay-20260929`.
Runtime-källcommit för separat server- och Windows-reläpaket är
`bdc9f7df417084641d0a712e3dad188dad1ad7d4`; se
[resultat, källfärskhet, hashvärden och blockerare](releases/lund-20260929/RESULTS.md)
och [förberedd aktivering/återgång](releases/lund-20260929/ACTIVATION.md).
Konsolideringstaggen och originalmapparna är bevarade. Fem tidigare basfel är
utredda/rättade; de 16 autentiska Lidl-proven passerar. Kandidaten är byggd,
installerad som **inaktiv** relärelease och isolerat provad; den är inte
installerad eller aktiverad på produktionsservern och den aktiva Windows-uppgiften
har inte ändrats. Senaste isolerade faktiska serving hade 44 132 produkter i 33
kontexter efter behovsstyrd frivillig insamling, med fem giltiga obligatoriska
onlinebaser. Äldre mottagare kan inte ta ny kommunartefakt och ny mottagare
avvisar gammal city-scope-artefakt. Tillfälligt S4U-testjobb kunde inte
registreras (`Åtkomst nekad`); obevakad kandidatkörning är därför fortfarande
öppen. Statusen ovan ersätter tidigare oprövade återgångsantaganden.

---

## Bevarad konsolideringshandoff 2026-09-29

# Aktuell arbetsrot: lokal konsolidering 2026-09-29

Permanent rot: **D:\Projects\Smako**. Huvudgren: `master`.
Integrationsgren: `chore/consolidate-smako`. Lokal tagg:
`consolidation-20260929-local` (ingen produktionsrelease).

Konsolideringsverifiering: **672 godkända, fem befintliga fel, inga nya fel**
bland 677 unika testfall; samma resultat i ren klon. Planner/audit/sparning/
återläsning matchar basen. Frontend 30/30, Ruff, compileall och pip check PASS.
Dockerbygge och browser-E2E är inte körda. Alla 16 historiska Lidl-prov passerar.

Den samlade koden är arbetskopians smako-legacy-purchase-terms:20260929-v5,
inklusive dess tidigare ocommittade kommunflöden, PurchaseTerms, exakta/uppskattade/
villkorade köp, närings-/beredningskontroller, sökoptimering och planlagring.
Äldre autentiska Lidl-fixturer samt streckkodsläsarens byggkällor är återställda.
Historiska appalternativ bevaras, men ersätter inte rättad kod.

Ingen produktion har aktiverats eller undersökts på servern. Kandidatens tidigare
handoff redovisar isolerad verifiering, inte produktionsaktivering. Windows-jobb,
scheman och användarprofiler är oförändrade. Priserna behåller observationstiderna.

Start, test, bygg och återställning: [DEVELOPMENT.md](DEVELOPMENT.md).
Ursprung, backup och externa gamla sökvägar: [CONSOLIDATION.md](CONSOLIDATION.md).
Aktuella testresultat och basfel: [verifiering](consolidation/VERIFICATION.md).
Backup: D:\Smako-backups\consolidation-20260929. Stora testdata återställs med
hashmanifest; hemligheter och privata drift-/användardata tillförs separat vid
ett uttryckligt behov. Använd mockmiljön för lokal start.

Kvarvarande produktfrågor från tidigare handoff gäller bland annat okända
kampanjvillkor/källfakta, Malmös fullständiga publicering, originalpolicy/Primat,
ICA:s okända kommunträffar och Lidl/Willys-täckning. Den tidigare saknade
historiska Lidl-fixturen är nu återfunnen; testutfallet redovisas i verifieringen.

---

## Historiska handoff-anteckningar, bevarade nedan

# Smako – 29 september 2026: äldre importer anslutna till PurchaseTerms

[Resultat och före/efter](../reports/legacy-purchase-terms-20260929/RESULTS.md), [acceptans](../reports/legacy-purchase-terms-20260929/ACCEPTANCE.json), [hela nämnaren](../reports/legacy-purchase-terms-20260929/comparison.json).

PASS i isolering: ICA/Coop/Hemköp/X:-tra för vidare belagda fasta/styck-, cirka-/lösvikts-, flerköps- och villkorade variantköp till befintlig motor. Inga uppdiktade restpriser, vikter eller variantidentiteter. Oklart viktköp utan uttrycklig form spärras. Samma sparade underlag/köpdag: godkända källrader 277→824, 254→1 614, 42→333 respektive 7→11; exakt/uppskattat/villkorat och butikskopior särredovisas i rapporten. Noll nya återförsäljarhämtningar.

Lund serving 42 085→44 119; 33 kontexter och fem obligatoriska onlinebaser (41 512 produkter) bevarade. Andra ordinarie rebuilden med frivilligt Hemköp-fel, reload och faktisk omstart ger identiska produkter/köptermer. Sju verkliga API-köp, två negativa kontroller, sparning/återläsning och befintligt närings-/beredningsprov PASS. Alla fyra oförändrade 15/20-profiler: 201/445,29 kr; audit och sparning/omstart PASS. Tidigare planrevisioner, skafferi och privata tillstånd är bevarade.

457 berörda regressioner verifierade, ytterligare 31 UI/runtime-prov, Ruff/compileall PASS. Isolerad image `smako-legacy-purchase-terms:20260929-v5` (`eee77ff22794…`), femkällorskandidaten fortsatt alternativ; ingen produktion, Windows-/schema- eller originalpolicyändring. Observationer är oföryngrade och status AGING/degraded redovisas ärligt. Coop-v4, kommunstödet, Primat och tidigare femmiddagsmilstolpe kvarstår.

Kvar separat: saknade källuppgifter/pant och ännu ej modellerade kampanjvillkor, Malmös baspolicy/fullständiga publicering, ICA:s okända kommunträffar, Bunkeflostrands källväg, Lidl/Willys-täckning och historisk Lidl-fixture. Prisgodkännande ger inte närings-/allergigodkännande.

---

# Smako – 28 september 2026: ICA/Hemköp kopplade till gemensamt kommunläge

[Samlat resultat](../reports/ica-hemkop-municipality-20260928/RESULTS.md),
[butiksrader och nästa uppdatering](../reports/ica-hemkop-municipality-20260928/STORES.md),
[köp och audit](../reports/ica-hemkop-municipality-20260928/OFFERS.md),
[acceptans](../reports/ica-hemkop-municipality-20260928/acceptance.json).

Lund PASS i isolering: samma kommunval genom inventering, källurval, OWN, PriceUniverse och beständig uppdateringsstatus. ICA 12 butiker/277 godkända OWN/275 serverade; Hemköp 3/18/18, inklusive Dalby utan onlinekatalog. Total serving 42 003 → 42 085. Södra Sandby, Genarp och Veberöd inkluderas på verifierad kommuntillhörighet. Fem obligatoriska baser, Coop-v4 och X:-tra bevaras.

Ordinarie publicering/reload, nästa rebuild med synligt frivilligt Hemköp-fel och omstart ger identisk produkthash. Fyra HTTP-profiler 201/445,29 kr, audit och identisk sparning/GET efter omstart. Förfallen ICA-inventering behöll alla prisobservationer och godkännanden utan prisanrop. 217 tester, Ruff/compileall och 592 runtimefilhashar PASS. Isolerad image `smako-ica-hemkop-municipality:20260928-v8` (`0790b31f3d7a…`); ingen produktionsaktivering, Windows- eller schemaändring.

Malmö: ICA 24 verifierat innanför, 23 insamlade/560 OWN; Hemköp 4/24 OWN. Två identiska PU-kandidater med 580 produkter, men **0 aktiverad serving**: ordinarie kontrollkorg är ofullständig, ingen Lund-baspolicy används. Bunkeflostrand saknar verifierad strukturerad erbjudandelänk; 45 ICA-träffar har okänd kommunstatus. Full Malmö-publicering, äldre PurchaseTerms, komplexa kampanjvillkor, Lidl/Willys-täckning och historisk Lidl-fixture kvarstår separat. Tidigare femmiddagsmilstolpe, originalpolicy/Primat och sparade användarval bevaras.

---

# Smako – 28 september 2026: Coops aktuella butikskälla återställd i isolering

[Resultat och butiksrader](../reports/coop-source-binding-20260928/RESULTS.md),
[exakt källkonflikt och rättning](../reports/coop-source-binding-20260928/ANALYSIS.md),
[maskinellt avstämd acceptans](../reports/coop-source-binding-20260928/acceptance.json).

PASS: den missvisande butik-/källkonflikten var två nya villkorsfält i det strukturerade svaret. Parser v4 bevarar köpkrav/prissteg och spärrar berörda rader; providern medger granskade v3/v4, inte okända versioner. Ny faktisk insamling 28/9 11:01 UTC: nio Coop/Stora Coop, 254 godkända av 2 179 rader, 1 925 i karantän. Faktisk serving 41 755 → 42 003 poster. Fem onlinebaser oförändrade; X:-tra separat med sex oförändrade poster.

Ordinarie rebuild/reload, nästa rebuild med injicerat Coop-fel, faktisk omstart och kampanjreplay PASS. Fyra profilprov gav 201/445,29 kr, verifierad audit och identisk sparning/GET efter omstart. 152 tester, Ruff och compileall PASS. Isolerad image `smako-coop-source-binding:20260928-v4` (`fdaf9c4a61e9…`); ingen produktionsaktivering eller schema-/Windowsändring.

`lund-own-five-base-20260928-v1` bevaras som verifierad alternativ kandidat. Tidigare kandidat och 337 bevisfiler är oförändrade. Originalpolicy/Primat och övriga uttryckligen separata uppgifter kvarstår; tidigare femmiddagsmilstolpe påverkas inte. Ingen extern uppgift blockerar denna källfix; kvarstående villkorsrader ska fortsatt spärras.

---

# Smako – 28 september 2026: Lunds alternativa basstrategi verifierad i isolering

[Samlad rapport](../reports/lund-base-strategy-20260928/VERIFICATION.md),
[Primats faktiska kontrakt](../reports/lund-base-strategy-20260928/PRIMAT-CONTRACT.md),
[butikstäckning](../reports/lund-base-strategy-20260928/STORE-RESULTS.md),
[valda köp](../reports/lund-base-strategy-20260928/SELECTED-PURCHASES.md),
[profilresultat](../reports/lund-base-strategy-20260928/profile-summary.json),
[separat policy-/aktiveringsunderlag](../reports/lund-base-strategy-20260928/ACTIVATION.md).

**Originalpolicyn är fortfarande blockerad; ingen aktivering.** Primat 1004409
anger offers_only, oförändrad identitet. Coverage är lokal normalisering av
källans tier; selected är källurval och inte orsaken till full_catalog-avslaget.
Augustiexporter visar tier=full, men fullständigt historiskt HTTP-råsvar saknas;
dåtidens fullklassning var källdeklarerad med begränsade produktprov.

Separat testpolicy `lund-own-five-base-20260928-v1`: fem obligatoriska OWN-baser
(Coop Online Syd, Hemköp Karhögstorg/Brunnshög, Willys Lund/Nova) plus giltiga
frivilliga erbjudanden. 41 512 tillgängliga basposter + 243 erbjudandebutiksposter
= 41 755 serverade poster / 19 kontexter. Onlinebas och fysiska offers_only hålls
isär. Clemenstorget bidrar med 34 erbjudanden, ingen full katalog.

Fyra ordinarie HTTP 15/20-profiler (original/Plus × exact/estimated): alla 201,
445,29 kr, 15 exakta/0 uppskattade/0 villkorade köprader, Coop Online Syd och
Willys Lund. 159,07 / 180,31 / 154,05 / 182,97 s. 40/30/20-målen uppfyllda;
10 näringsresultat VERIFIED och 5 ESTIMATED. Audit PASS; fyra planer oförändrade
vid GET och faktisk omstart. Plus är aktiverat men inget valt medlemsprisköp.

Den första isolerade kopian saknade katalogernas råfiler. Felet är rättat i
initialize_job.py och genom 2 232 hashverifierade råfiler; HTTP har nu förkontroll.
De första DATA_BLOCKED-proven är sparade separat och är inte basstrategins resultat.
Inga observationer föryngrades. Appkoden är oförändrad: 589 filhashar matchar den
pinnade bilden 32e838155b0e…; pip check utan fel; 238 tidigare rapportbevis bevarade.
37 riktade regressioner godkända. Ordinarie andra rebuild/reload, omstart/not_due,
obligatorisk basavvisning utan LKG, frivilligt fel, kampanjutgång och replay-
återhämtning är verifierade och särredovisade. Sista basålder 15,72–16,54 h.

Alternativet kan nu bedömas separat för fortsatt release. Det är inte godkänt enligt
originalpolicyn och ändrar inga produktionskrav eller användarval. ICA-/Hemköps
kommunlucka, äldre köptermer, Malmö-publicering och historisk Lidl-fixture kvarstår.
Dagens nya fysiska Coop-hämtning är avvisad på butik-/källbeviskonflikt; endast
fortfarande giltiga godkända LKG-erbjudanden används. Före eventuell aktivering
måste aktuell basfärskhet, kampanjer, råfiler och policy kontrolleras igen.

---

# Smako – 27 september 2026: aktuellt Lund-prov, ingen aktivering

[Samlad verifiering](../reports/lund-integration-20260927/VERIFICATION.md),
[butik för butik](../reports/lund-integration-20260927/STORE-RESULTS.md),
[faktiska HTTP-resultat](../reports/lund-integration-20260927/profile-summary.json),
[separat aktiveringsunderlag](../reports/lund-integration-20260927/ACTIVATION.md).

**Lund är inte redo för aktiveringsbeslut.** Aktuell Primat-resolve anger
ICA Clemenstorget 1004409 som offers_only, medan obligatoriskt kontrakt kräver
full_catalog. Ingen färsk komplett LKG. Full federation/publicering och de fyra
fria kompletta 15/20-proven är därför spärrade, inte godkända eller omräknade
med historiska 484,73 kr. Gunnesbos fullständiga identitet kan fortfarande
återvalideras; den obligatoriska bunten publiceras inte partiellt.

Verklig insamling 27 september: 41 704 OWN-baskatalograder; 192 uttryckligen
slut i lager. Smala schemaöversyner för redan stödda Coop-procent-/beskrivningsfält
och Hemköps EPREL-lampmetadata återställer normal import från samma råsvar.
Primat avbryter nu tidigt och rapporterar exakt täcknings-/identitetsstopp utan
onödiga produktanrop när giltig LKG saknas. Inga pris-/näringsskydd sänkta.

Separat OWN-only publicering: 42 319 poster, 27 kontexter, samma posthash efter
andra byggning och faktiskt reload. Det är inte den kompletta Lund-kandidaten.
Fysisk 15/20 exact/estimated: 422; 96 middagskandidater stoppas vid produkt/fakta,
inte sökbudget eller styrkt ekonomiskt bortval. Aktuell varm ostsmörgås via HTTP:
171,68 kr (hela Lingongrova 500 g + Hushållsost cirka 2,2 kg), 1 exakt/1 uppskattad,
33,8 g protein mot 30 g, VERIFIED_WITH_ESTIMATES, beredningsnäring ESTIMATED,
audit PASS. Flerköpsmåltidsprovet saknar brödets näringsunderlag och är inte grönt.
Sparning, omstart, faktisk klienttext samt läskompatibilitet i separat äldre
rollbackkod verifierade. Äldre nyomräkning inte bevisad.

Willys-källans not_due/felinjektion/replayåterhämtning verifierad med oförändrade
observationer. Framtidsklocka visar noll utgångna kampanjer till köp; baskatalog
spärras efter 48 timmar. Hela federerade driftkedjan måste omprövas när basen finns.
597 unika regressioner godkända (676 körningar inklusive riktade omkörningar).
Slutbild sha256:32e838155b0ef2b4b4eb9944cb7d1b31324b37e7ea56eb6d840fc70fc9e1ff87.
589 paketfiler kontrollerade; tidigare sökleverans 9 kod-/546 bevishashar bevarade.
ICA:s aktuella driftkoppling är fortfarande ortsurval, Hemköp godkända kontexter;
full kommuninventering för dessa är inte visad. Malmö-publicering och historisk
Lidl-fixture är separata olösta kontroller. Ingen produktion, Windows-uppgift,
schemaläggning eller sparad användarprofil har ändrats.

---

# Smako – 27 september 2026: gemensam receptsökning och korrekta råvaruformer

[Verifierade resultat](../reports/recipe-search-20260927/VERIFICATION.md),
[alla 84 recept med ID och första stopp](../reports/recipe-search-20260927/RECIPE-RESULTS.md),
[kandidat- och källspårning](../reports/recipe-search-20260927/recipe-first-stops.json),
[inaktiv release/rollback](../reports/recipe-search-20260927/RELEASE.md).

Historisk replay 24 september, oförändrade recept/mängder/40–30–20-mål/tvåbutikstak.
33/84 före och efter: 32 godkännanden bevarade, nytt Tacos med tofu och gul lök
(40,2125 g protein/portion, hel varukorg 117,05 kr). Stekt ris med lax och vitkål
hade ett felaktigt tidigare godkännande med torkad kryddvitlök som rå vitlök.
Det återkallas: korrekt råvaruform ger högst 39,58 g mot 40 g. Målet om fler netto
samt alla 33 bevarade är alltså inte uppnått; detta får inte döljas.

51 återstående första stopp är nu styrkta proteinövre gränser inom det aktuella
kvalificerade underlaget, inte budgetstopp eller påstådd global omöjlighet.
Alla 29 tidigare budgetfall har nytt referensprov (4096 lokalt tak, 30 s/case).
28 avbryts av giltig näringsgräns; tacoreceptets 832 klasser uttöms med samma
117,05 kr som ordinarie 256-sökning. Ingen global budgethöjning.

Fri 15/20: 484,73 kr i alla fyra fall. Original exakt 146,965→102,989 s,
original uppskattat 166,500→117,835 s, Plus exakt 145,039→104,718 s,
Plus uppskattat 170,830→119,052 s. Coop Online Syd online_fulfillment + Willys Lund
online_store. 16 exakta köp, 0 uppskattade/villkorade; näring 10 VERIFIED/5 ESTIMATED.
Samma 37031 produkter och pool 41; inga nya priser eller föryngrade observationer.

Gemensamma ändringar: konservativa näringsgränser och förberäknade näringsklasser,
återanvända fakta, begäransbunden cache för förpackningskostnader, exakt GTIN-bunden
Dabasimport med uttryckliga 200 ml/200 g för Skånemejerier 13 %, rå-formkontroll
för potatis/vitlök och befintliga SLV-referenser 4457/371. Deklarationsprioritet,
opt-in, allergispärrar, GoGreen-konflikt och butik/kanal/prisroll bevaras.
Ingen ny receptversion. Slutlig kod med gamla deklarationer ger 32/84; med
nya belagda mängdfakta 33/84. Den laktosfria varianten får inte låna massuppgiften.

700 regressioner plus 32 riktade slutprov; Ruff/compileall godkända. Nytt tacorecept
verifierat via ordinarie HTTP i båda lägena, audit, lagring, omstart och säker
rollback (läsning identisk, omräkning 422 bevarar plan). Alla 720 tidigare
releasebevis bevarade. Produktion, användarprofiler och scheman är oförändrade.
Färsk komplett produktionsbas, Malmö-publicering och historisk Lidl-fixture
kvarstår separat. Se PACKAGE.json för exakta filer, hashar och testbevis.

---

# Smako – 26 september 2026: mängd- och näringskoppling efter beredningsstödet

[Verifierade körresultat](../reports/recipe-resolution-20260926/VERIFICATION.md),
[alla 84 första stopp](../reports/recipe-resolution-20260926/recipe-first-stops.json),
[kandidater före/efter](../reports/recipe-resolution-20260926/candidate-review.json),
[separat aktiveringsunderlag](../reports/recipe-resolution-20260926/RELEASE.md).

Inaktiv kandidat. Oförändrade v1-recept: beredning 84→84,
näringsprövning 48→84, numeriskt resultat
39→84, mål + varukorg + audit 19→33.
Alla 19 tidigare godkända bevarade. Ingen ny receptversion eller ingrediensändring denna etapp.

Gemensam matchare prövar identitet före grov låg källklassning. Officiell Dabasimport
är bunden till kontrollsiffergranskad GTIN, varumärke och konsumentförpackning.
Crème fraiche har en produktspecifik belagd ml/g-relation, ingen generell densitet.
Avrunnen vikt skiljs från nettovikt och från näringstabellens beredningsgrund.
Fyra nya SLV-referenser importerade med råvärden och verkliga svarstider.
Ägg använder dokumenterad skalandel endast som separat opt-in-uppskattning;
verifierad produktnäring prioriteras. Pris, receptversion och näringskvalitet hålls isär.
Gravad fisk, burek, soppgrönsaksblandning och ostkex får inte bli rena råingredienser.
Gula ärtor är egen identitet och källkategorin Blötmat spärras som djurfoder.
En definierad identitets-/formspärr kan inte kringgås av textmatchning när en
ingrediens saknas i det ekonomiska kandidatindexet. Uttryckliga köpformer och
varor utanför taxonomin behåller sin separata, kontrollerade reservväg.

Fri 15/20, 40/30/20, max två butiker: 484.73 kr,
146.965 s, VERIFIED. Detaljer om fyra lägen, separata
legacy-/rebuildprov, valda recept och tidsprofil finns i verifieringen. Rebuildens
nya kandidatpool ändrar receptutbudet och är ingen jämförbar besparingsmätning.

Första stopp: {"NUTRITION_TARGET_NOT_MET": 22, "SEARCH_BUDGET": 29, "PASS": 33}.
Referenssökning 4096 för de gamla 20 avslagen ger inga nya godkända; se exakt
budgetstatus i rapporten, ingen global omöjlighets- eller dyrare-slutsats.

Ordinarie HTTP, checkout/audit, sparning, processomstart och explicit rollbackmål
är verifierade. Rollback till närmast föregående v1-beredningsleverans läser
nya sparade planer; omräkning avslås säkert och planen bevaras. Äldre versioner
utan preparation-kontrakt är inte verifierade rollbackmål. Visuell desktopkontroll
av uppskattningsmärkning och mängdinstruktioner dokumenterad separat.

Historisk prisreplay 24 september; nya mängd-/näringskällor 26 september.
Ingen prisobservation föryngrad. Ingen produktionsaktivering, användarprofil- eller
schemaändring. Färsk komplett bas, Malmö-publicering och historisk Lidl-fixture
kvarstår separat. GoGreen svarta bönors motstridiga näringsvärden kvarstår spärrade.

<!-- recipe-resolution-20260926:end -->

# Smako – 26 september 2026: implementerat recept- och beredningsstöd, inaktiv kandidat

[Uppmätt verifiering](../reports/recipe-preparation-20260926/VERIFICATION.md),
[rå sammanställning](../reports/recipe-preparation-20260926/summary.json),
[exakta receptändringar](../reports/recipe-preparation-20260926/recipe-changes.json),
[beräkningsmetod](recipe-preparation.md),
[aktiveringsunderlag](../reports/recipe-preparation-20260926/RELEASE.md).

Generatorns 80 varma recept och fyra särskilda beredningsfall har separata
versionerade definitioner, mängder och validerade instruktioner. Legacy och
sparade recept bevaras. Oljan 5/7,5/10 ml per portion är receptutformning,
inte mätt upptag. Gemensam metod beräknar insatsbaserade makron per portion
med opt-in och ESTIMATED; den hittar inte på färdigvikt, retention eller
ätbara andelar. Pris-/korgkvalitet är separat. Metoden följer API/PlanStore.

84/84 passerar nu beredning, 48 når näringsprövning, 39 får numeriskt
näringsresultat, 19 klarar mål + varukorg + audit. Två väljs i fri 15/20.
Första kvarstående stopp: 36 köp-/matchningsfall (22 rödlök, 10 crème fraiche
med g/ml-lucka, 3 svarta bönor, 1 bönor); 9 mängd-/näringsfall (5 ägg,
1 kidneybönor, 2 kikärtor, 1 blandfärs); 20 utan funnen målgodkänd kombination
i begränsad sökning. Det sistnämnda bevisar inte global omöjlighet/dyrare.

15/20, 40/30/20, max två butiker: gamla recept 535,25 kr, nya 484,73 kr
för public/Plus och exact/estimated. Samma kompletta historiska bas/köpdag.
Coop Online Syd + Willys Lund, 12→16 exakta köprader, VERIFIED korg,
5 ESTIMATED +10 VERIFIED näringsresultat. Olika receptinnehåll: inte en
besparing för identisk mat. Gamla definitioner är kodregression.

Ordinarie HTTP + sparning/GET + verklig backendomstart: tidigare spärrad
tofumacka 107,64 kr, 36,4 g protein mot 30; separat varm Lidl-/Arla-smörgås
171,68 kr, 33,8 g protein mot 30. Arla hela cirka 2,2 kg kostar cirka
153,78 kr, 100 g används. Exakt läge stoppar cirka-osten, uppskattat passerar
VERIFIED_WITH_ESTIMATES. Inga produktlås, extraköp eller kandidatpatchar.

179 riktade regressioner, Ruff och compileall passerar. Privata replayjobb
använder fryst klocka 2026-09-24T21:16:35.494010Z; inga prisobservationer
föryngras. Separat officiell Zeta-kontroll gav ingen ny importerad faktarad;
direkt arkivering 403. Ätbar äggmängd, avrunna mängd-/faktakopplingar och
saknade enhets-/produktkopplingar kvarstår. Ingen produktion, profil eller
schemauppgift ändrad. Färsk bas, Malmö-release och historisk Lidl-fixture
är separata öppna kontroller. Tidigare underlag följer oförändrat nedan.

---

# Smako – 26 september 2026: verkliga erbjudanden i PersonalPlanner, inaktiv kandidat

[Genererad verifiering](../reports/personal-offers-20260926/VERIFICATION.md),
[före/efter](../reports/personal-offers-20260926/profile-summary.json),
[produktbeslut](../reports/personal-offers-20260926/product-decisions.json),
[84 beredningsfall](../reports/personal-offers-20260926/preparation-review.json),
[aktiveringsunderlag](../reports/personal-offers-20260926/RELEASE.md),
[paket](../reports/personal-offers-20260926/PACKAGE.json).

Rättat: uppskattade priskandidater får tillgång till breda index även utan
inlästa näringsfakta. Verkligt fryst prov ger 4→6 ostkandidater: ett Arla-erbjudande
i två Lidl-butiker, inte två nya unika priser. För profilen med näringsfakta nådde
Arla redan matched-indexet; ingen sådan överföringsförlust har påvisats där.
Verifierad leverantörsklassificering Matbröd kopplas nu via gemensam deklarations-
projektion till receptmatchning; det löser Lingongrovas tidigare kortnamnslucka.
Ingen ny produkt-/kampanjlista och inga nya priser eller näringsvärden importerades.

PlanRequest har frivilligt planbundet allowed_store_ids för PersonalPlanning;
standardläge/användarprofil/kommunval ändras inte. Diagnostik binder produkt,
källsnapshot, butik, recept, första stopp, faktiska sökhändelser och avgränsade
alternativa hela korgar. Checkout/audit följer sparat personligt resultat.

Oförändrad 15/20 med 40/30/20 och max två butiker: 535,25 kr före/efter för
public/Plus × exact/estimated. Coop Online Syd + Willys Lund, 12 exakta rader,
20 förpackningar. Måltidsnäring separat: 10 VERIFIED +5 tillåtna ESTIMATED.
Arla-alternativen prövades i fulla korgar men den befintliga 256-kombinations-
näringssökningen hittade ingen godkänd lösning under butikstaket. Detta bevisar
inte ”dyrare” eller global omöjlighet. Gouda behöver deklaration/tillämplig
referens (Vardagsfavoriter, tillfälligt parti; GTIN/fetthalt saknas). Fläskreceptet
stoppas före produktprövning av beredningsgrund. Frukterna efterfrågas inte i poolen.

Verklig HTTP PersonalPlanner-måltid PASS: vanlig ostsmörgås, Lidl Plus för
Lingongrova, uttryckligt Lidl Åkerlund och Rausings väg 1. Ingen produktlåsning
eller extravara. 100 g bröd +100 g Arla-ost ger 33,8 g protein mot minst 30 g.
Helt bröd 17,90 kr +cirka 2,2 kg ost för 153,78 kr =cirka 171,68 kr;
1 exakt +1 uppskattad köprad, VERIFIED_WITH_ESTIMATES, checkout/audit passerar.
POST/GET och ny backendprocess/GET bevarar planen. Exakt läge spärrar cirka-osten.
Föreversionens HTTP ignorerar det då okända butiksväljarfältet och väljer Coop
för 30,28 kr: detta är inte en jämförbar Lidl-kostnad eller besparing.

252 regressioner PASS; Ruff/compileall PASS. Två äggberedningar, stekt tofu,
avrunna kikärtor och 80 genererade varma recept har kvar legitima beredningsspärrar;
alla 84 har konkret ingrediens-/instruktionsredovisning. Tidigare kommun-, andra-
rebuild- och refreshbevis behålls; berörd runtime/persistens prövas igen här.

Alla priser är historisk replay vid 2026-09-24T21:16:35.494010Z, samma kompletta
2139-produktbas/9 kontexter och alla 6 obligatoriska. Arlas redan sparade deklaration
observerades 25 september. Inga observationer föryngras. Ingen produktion,
Windows-/schemaändring, användarprofiländring, bildanalys eller betalt modell-API.
ÖPPET: färsk komplett bas/komplett Malmö-publicering; historisk Lidl-fixturelucka;
ny oberoende verklig kampanjutgåva; återstående käll-/beredningsunderlag.

---

# Smako – 25 september 2026: gemensam köpplanering, inaktiv kandidat

Senaste underlag: [resultat](../reports/purchase-planning-20260925/README.md),
[verifiering](../reports/purchase-planning-20260925/VERIFICATION.md),
[aktiveringsunderlag](../reports/purchase-planning-20260925/RELEASE.md),
[paketmanifest](../reports/purchase-planning-20260925/PACKAGE.json),
[kontrakt](purchase-planning.md) och
[alla blockerartyper](../reports/purchase-planning-20260925/BLOCKERS.md).

Den befintliga arbetskopian är bevarad; tidigare kedjereleaser och Primat kvarstår.
Gemensamt PurchaseTerms-kontrakt går genom SourceOffer/collector/OWN/PriceUniverse
samt matchning, optimering, checkout/audit och personligt API/UI/sparning.
Exakt är standard; uttryckligt uppskattningsläge stödjer lösvikt och hela
cirka-förpackningar med synliga reservationer. Styckpris behöver inte gramvikt.
Öppna källbelagda variantgrupper kan väljas som villkorat extra inköp men är
inte specifika recept-/närings-/allergigodkännanden. Riktig uppmätt användbar
mängd krävs för lagerbokning av ungefärliga köp.

Identifierade blandgrupper använder befintlig PromotionGroup-motor med
explicit käll-ID/grupp-ID, samma butik/snapshot, verifierad delmängd,
hela flerköp utan fabricerat restpris och belagda gemensamma hushållstak.
SourceOffer→collector→OWN→PU→gruppköp/audit provas med syntetisk källa;
detta är inte bevis för identifierade varianter i alla verkliga öppna grupper.
Gamla serialiserade defaults/digests bevaras och beräkningscachen har ny version.

Fryst jämförelse 24 september, samma prisunderlag och medlemskontext:
Willys 87→108 deduplicerade prisposter; 21 nya grupposter överlappar en gammal
kampanj, alltså 20 nya kampanjpriser varav 18 livsmedel. 74 exakta livsmedelsköp
kvar, 8 tidigare kg-priser nu användbara uppskattat, 19 villkorade livsmedelsval.
Lidl 26→28 (26 exakta +2 uppskattade). Willys annonser 20→23 av 34 och 57→75
av 112; manuella aktuella poster 2/7 bevarade separat. Lidl hela 380-ID-nämnaren
kvar: 28 kvalificerade, 350 saknar tillräcklig bindning, 2 parserkarantäner.
Gram-kompatibel näring Willys 10→10 / Lidl 2→3. Arla Hushållsost 26 %, ca 2,2 kg har officiell
variantbunden deklaration; 200 g behov köper helt paket för cirka 153,78 kr. SLV 580
Persika är märkt referens för uppmätta ätbara gram, ingen gissad kärnandel.
5 verkliga officiella närings-/produkthämtningar, 0 nya prisnätanrop i etappen.

768 unika riktade regressioner passerar; Ruff/compileall/JS-syntax passerar.
Riktig oförändrad 15/20, 40/30/20, högst 2 inköpsställen: 535,25 kr och VERIFIED
före/efter i både exakt och uppskattat läge (alla faktiskt valda rader exakta).
Slutprovet har samma kompletta bas och 9 kontexter inklusive alla 6 obligatoriska.
Ett mellanprov saknade fryst federerad klocka och föll till 8 kontexter; det
räknas inte som komplett bas. Ingen produktionsfärskhetsregel ändrades.

Ordinarie isolerad runner/publicering/reload, andra rebuild, processomstart,
not_due utan prisanrop, hämtfel/LKG och återhämtning PASS med samma slutkod.
Willys 243 / Lidl 224 / City Gross 13 523 poster i Malmö-driftprovet; källobservationer
bevaras. Separat Lidl-jobb återkvalificerar råsvar efter injicerat fel och
återstartar not_due. Framtida testklocka spärrar för gammalt underlag.

ÖPPET: verklig bas är nu för gammal för aktuell komplett publicering;
fullständigt Malmö-publiceringsprov med aktuell komplett bas; historisk
Lidl-fixture test_reviewed_lidl_nutrition.py (lidl_offer_adapter.py saknas);
ny oberoende tidigare ogranskad verklig kampanjutgåva; källblockerarna i
BLOCKERS.md. Hundra procent är inte uppnått och dessa punkter är inte stängda.
Ingen produktion, Windows-/schemaändring, bildanalys eller betalt modell-API.

---

# Smako – 20 september 2026, lokal Qwen3-VL faktiskt prövad; ingen prisaktivering

[Resultat och råbevis](../reports/ica-flyer-local-20260920/README.md), [körbok](../reports/ica-flyer-local-20260920/RUNBOOK.md), [lokalt kontrakt](ica_flyer_local.md), [före/efter](../reports/ica-flyer-local-20260920/BEFORE-AFTER.md), [releaseförslag](../reports/ica-flyer-local-20260920/RELEASE.md).

- Samma branch/worktree `sources/lidl-ica-evaluation-20260914`. Tidigare ocommittat arbete och OpenAI-adapter bevarade. Inga betalda API-anrop är godkända eller utförda i denna etapp; tidigare API-nyckelfråga är inte nästa steg här.
- Konkret lokal adapter `grocery_data.scripts.ica_flyer_ollama`, samma `smako-public-flyer-page-v1`, Qwen3-VL 4B Instruct Q4_K_M via Ollama 0.34.2. Modellvikter lokala, ingen cloud/fallback, innehålls-/kontext-/viktcache, original-PDF-bindning och diagnostiska utsnitt med koordinattransform. Befintlig batch använder samma kommandoinställning och begränsad timeout.
- Verkligt fyrsidorsprov på befintlig CPU-server: Söderlivs 6 gav 4 annonser, 3 rätt huvudbelopp men Milda 12 i stället för 19; Linero 1 timeout efter 900 s; Linero 3 HTTP 500/OOM i testmodellen; Söderlivs 1 läste sju tal under en enda felaktig produktidentitet. 28,86 min totalt. Fryst visuellt facit 25 annonser: 4 rätt produkt–priskopplingar, 7 fel, 14 ej bedömbara p.g.a. sidfel. Assistentens separata visuella granskning, inte påstådd extern mänsklig attest.
- Två verkliga 240-dpi-utsnitt: Milda fick rätt 19/st och Jfr 38/liter, men fel geometri/okända villkor/identitet; Linero ris + Dusch/Deo + Donuts fick jämförpriser felaktigt som köppriser. 235,389/396,118 s. Explicit jämförprisgrind tillagd med verkligt modellsvar som regression. Ingen helsida blir komplett av ett utsnitt; Milda fortsatt isolerad.
- Resurser: laptop otillräckligt ledigt RAM/gammal GPU-driver; serverprov 2 CPU/6 GiB hårt modellminne, låg prioritet, offline nätverk utan publicerade portar. Vikter flyttade från tmpfs till vanlig disk med samma SHA-256. Ett minnesskyddsstopp och en OOM i testmodellen, inga OOM/omstarter i beta/scheduler. Slutkod släpper modellminne efter anrop (`keep_alive=0`); två utsnittsprov utan ny OOM. Ingen flerdagars- eller latensgaranti. Modellcontainern är nu stoppad, inga scheman/aktiveringar.
- 7 lokala chat-anrop (5 svar, 2 fel), 10 539 kända input-/5 915 output-token för avslutade svar; ofullständig tokenmätning för felanrop, inte noll. 0 USD API. Fyra cacheåterbindningar utan modellgenerering eller ändrad källobservation. 325 riktade regressioner samt Ruff/compileall PASS.
- 0 nya kvalificerade bildimporter. Tidigare Linero 14/Söderlivs 16/totalt 155 ICA-produkter bevarade. Pris-/planeringskoden är oförändrad; tidigare 15/20 = 560,33 kr i båda armarna är historisk verifiering, inget nytt menykörningsresultat. Primat kvar, blockerad ICA-baspriskatalog pausad. 54 återstående unika PDF-sidor/112 butik–sidkopplingar kvar i kön; storbatch och 8B inte godkända av pilotutfallet.

Det lokala backendet fungerar som verklig modelltransport men den prövade konfigurationen är **inte tillräcklig för automatisk prisimport**. Nästa tekniska arbete måste förbättra produkt–pris-/prisrollstolkning, annonsgeometri och små villkor samt verifiera resurser/återhämtning innan större batch. Behåll karantän, 95-procentsgrind, datum/färskhet och prisavtal. Ingen skarp aktivering utan separat beslut.

---

# Smako – 19 september 2026, konkret bildadapter; API-provet blockerat

[Leverans och exakta körkommandon](../reports/ica-flyer-vision-20260919/README.md), [kontrakt/konfiguration](ica_flyer_vision.md), [före/efter](../reports/ica-flyer-vision-20260919/BEFORE-AFTER.md), [15/20](../reports/ica-flyer-vision-20260919/PROFILE.md), [releaseförslag](../reports/ica-flyer-vision-20260919/RELEASE.md).

- Concrete Responses-bildadapter `grocery_data.scripts.ica_flyer_openai`, modell `gpt-4.1-mini-2025-04-14`, befintligt processkontrakt. Original-PDF/hash/sida kontrolleras av programmet, två bildpass med småtrycksförstoringar, separata prisroller, innehålls-/kontextcache, kostnadsbokföring, serialiserad återupptagning. Ingen parallell prissättare.
- Serverberoendet PyMuPDF 1.28.2 provat via isolerad Linux-wheel; produktionen inte ändrad. Verkliga original: Linero `btnvspch:3`, Söderlivs `pjv63t92:6`, sju renderade bilder vardera. HTTPS till OpenAI fungerar (401 utan autentisering). **Ingen modelltolkning har utförts:** API-nyckel saknas och betald ram är inte godkänd. 0 anrop, 0 USD, 0 bildimporter. Nyckeln ska konfigureras skyddat på servern, aldrig i chatt. Frågan lyftes tidigt och är obesvarad. 54 unika PDF-sidor kvarstår; kalla inte detta färdig bildinsamling.
- Belagd GTIN-bunden pant går via befintlig review/SourceOffer/OWN/prisavtal till checkout/audit: belopp per behållare × antal × köpta paket, inkluderad pant inte dubbelt. Okänd pant, fel variant och obelagda ordinarie restköp stoppas. Verifierat med uttryckliga fixtures, inte verklig ny bildprisimport.
- Slutkodens nya offentliga insamling 20:58–20:59 UTC: 655 oförändrade återobservationer mot förra leveransen, 0 nya. Linero 14, Söderlivs 16, totalt 155 ICA-produkter kvar. Linero 56/59 och Söderlivs 52/57 underkänner fortfarande fullsnapshotens 95-procentsgrind; partiella radavtal bevarade.
- Verkligt nytt 15/20-par, samma frysta originalbas/Primat/krav: 560,33 kr i båda armarna, två ställen, HTTP 201/PASS; 37,432/38,718 s HTTP, 212,382/213,912 s totalt. 36 657 basprodukter och 35 078 basfakta identiska. 155 ICA-produkter tillagda, inga valda i menyn. Linero 2 paket ris/50 kr och Söderlivs tomater 1 paket/30 kr passerar diagnostisk audit; de är befintliga strukturerade priser, inte nya bildpriser.
- 300 riktade tester PASS; Ruff/compileall PASS. Samma arbetsgren/worktree, äldre rapporter och ocommittat arbete bevarade. Ingen aktivering, källväxling eller schemaändring; Primat kvar, blockerad ICA-baspriskatalog pausad, Milda fortsatt isolerad. Nästa steg är nyckel/ram, verkligt modellprov och granskning före batch – inte ännu en inventering.

---

# Smako – 19 september 2026, radgodkänd ICA-import och färskt slutkodstest

[Leverans och kvarstående hinder](../reports/ica-flyer-import-20260919/README.md), [kvalitet](../reports/ica-flyer-import-20260919/QUALITY.md), [reklamblad](../reports/ica-flyer-import-20260919/FLYERS.md), [15/20-resultat](../reports/ica-flyer-import-20260919/PROFILE.md), [separat releaseförslag](../reports/ica-flyer-import-20260919/RELEASE.md). Samma branch/worktree, tidigare ocommittat arbete bevarat. Ingen produktion, källväxling eller schemaaktivering. Primat kvar; ICA:s blockerade direkta baspriskatalog fortsatt pausad.

- Explicit `partial-row-approved-offers-v1`, separat offers_only-scope och `complete=false`; ursprunglig fullsnapshotbedömning/nämnare/95-procentsgrind oförändrade. Okända parser-/schema-/gemensamma butiksfel stoppar berörda kandidater. Osäkra rader ligger kvar i karantän, LKG och baskontrakt påverkas inte.
- Färsk begränsad serverinsamling 19 september 16:30:12–16:30:57 UTC, befintligt operationslås och isolerad SQLite/rådata. Lund 12 upptäckta/9 inom verifierad adressort, Malmö 69/21 inventerat utan handlista. 655 råannonser, 633 parsade, 22 parseravslag. Linero 56/59 och Söderlivs 52/57 underkänner fortsatt fullgrinden men bidrar nu med 14 respektive 16 radgodkända OWN/PriceUniverse-produkter. Totalt 156 OWN/155 PriceUniverse; Gunnesbos gaständare stannar i OWN på explicit fixed_package-gräns.
- Parser v7 bevarar tryckt ordinarie kampanjreferens separat; inget fabricerat ordinarie köppris. Offentliga och berättigade allmänna medlemsavtal använder befintlig prissättning. Verifierad identisk lokal/central Söderlivs-äggkampanj deduplicerad med båda beläggen och ett gemensamt köptak. Tidigare sju identitetsrättningar kvar, Milda-kopplingen fortsatt karantän.
- Alla upptäckta nio unika utgåvor: 94 unika PDF-sidor plus fyra digitala läsarsidor hämtade. 40 PDF-sidor innehållsverifierat transkriberade; 54 unika PDF-sidor fortfarande ofullständigt extraherade. 179 av 687 butik–annonskopplingar har konkret strukturerad post, 508 blockerade/preliminära. Extra läsarbilder manuellt verifierade som instruktioner/navigation utan priser. Automatisk bildtolkning saknar konfigurerad tjänst i körmiljön. Generisk worker → review → SourceOffer → OWN-import är fixturetestad, men verkliga nya bildextraherade importer är **0**. Hela reklambladsuppdraget är inte färdigt.
- Riktig oförändrad 15/20, 40/30/20 g, max två ställen: båda HTTP 201, **560,33 kr före/efter**. HTTP 37,831/39,875 s, totalt 214,582/219,680 s. Samma färska frysta originalbas (inte sökprojektion), alla 36 657 basprodukter och 35 078 fakta exakt oförändrade. 155 ICA-prisprodukter/28 härledda fakta tillkommer. Inga tillskott valda; 15 individuellt näringsstödda, inga tillskott i profilens registrerade auditerade receptkorgar. Separata verkliga diagnostiska korgar klarar matcher/checkout/audit: Linero jasminris 2×1 kg/50 kr, Söderlivs tomater 500 g/30 kr. Näringsuppskattningar enligt oförändrad ursprungsprofil särredovisas.
- Nya källrader 43, ändrade 27, återobserverade oförändrade 585; en logisk äggdubblett. 155 produkter kallas inte 155 nya priser. 242 fokuserade tester samt Ruff/compileall PASS. Efter prisparet ändrades bara valfria kandidatjobbets uppstartsfelisolering/CLI-hook; berörda tester och hela fokuserade sviten kördes om. Pris-/parser-/matcher-/checkoutkod matchar paret. Inaktiv driftflagga och testad LKG-återhämtning finns, ingen observerad flerdagarsstabilitet.

Nästa kvarstående arbete: verklig bildtolkarintegration/acceptans, resterande annons-/text-/digital-layout-extraktion, pant- och variantbevis, samt styckvarans offers_only-projektion. Nya kampanjer måste ha aktuell relevant evidens. Läs README/FLYERS/QUALITY före fortsättning; gamla kampanjer och historisk replay är inte framtida releaseacceptans.

---

# Smako – 19 september 2026, ICA-täckningsluckor och återupptaget arbete

[Leverans och kvarstående hinder](../reports/ica-area-gaps-20260916/README.md), [butiksvis före/efter](../reports/ica-area-gaps-20260916/BEFORE-AFTER.md), [separat releaseförslag](../reports/ica-area-gaps-20260916/RELEASE.md). Samma branch/worktree från 14 september; befintliga ändringar bevarade. Ingen commit, produktionsaktivering eller schemainstallation. Primat kvar och ICA-baspriskatalog fortsatt pausad.

- Ny begränsad publik insamling 16 september 12:36 UTC: Linero 56/59 (94,915254 %), Söderlivs 45/49 (91,836735 %). Samma 95-procentsgrind/nämnare; sju pantposter saknar belagda variantspecifika belopp. Tydligare parserdiagnostik, verkliga råsvarsregressioner. Båda snapshots avvisade, 0 aktiva OWN/PriceUniverse. Jasminris/Pizzakit spårade till exakt snapshotblockerare; inga köpriser har fabricerats.
- Åtta identitetskonflikter utredda: sju fallbacknamn/skiftlägesskillnader rättade, Milda/Milda Culinesse-kopplingen kvar i karantän. Oberoende basfakta förblir orörda; priser/medlemsvillkor överförs inte. 35 207 gemensamma basfakta oförändrade, 20 tillagda faktaposter.
- Alla Lund 12/Malmö 69 butiker redovisas, 9/21 inom befintlig adressort. Granskningsbara konfigurationsförslag genereras från full inventering, även när butikens prisinsamling underkänns. Malmöinsamlingsstatus är omätt, inte tom.
- Reklamblad: 9 utgåvor/94 sidor/605 preliminärt inventerade rutor. 40 sidor avlästa kampanjvillkor, 54 kvar i granskning. Linero/Söderlivs 94 rutor: 89 kampanjmässigt täckta, fyra pantblockerade, en Ciabatta-butiksgiltighet att granska. Evidensbunden granskningsadapter till befintlig SourceOffer; ingen ny flyer-prisimport/liveacceptans. Datum/ruta/butik/villkor/hash och ursprunglig observation bevaras.
- Flerköpsfel rättat: gruppköp utan ordinarie pris kräver inte ett påhittat enstyckspris. Befintlig checkout kräver full grupp, giltighet, medlemsbehörighet och tak. Av 121 historiska produkter kan 104 publika pris-/mängdavstämmas, 36 får diagnostisk audit PASS, 68 har låg semantisk säkerhet; 17 medlemserbjudanden spärras utan medlemskap. Detta är inte receptkvalificering.
- Komplett verkligt 15/20-par före sista flerköpsfixen: 563,17 kr i båda armarna, två ställen, ingen ICA-selektion/besparing. 42 namnmatchade/22 semantiska/8 individuellt näringsstödda/1 auditerad enskild receptkorg. Efter sista fixen hann bara före-ledet slutföras. Återstart 19 september stoppas korrekt av det frysta Primat-underlagets ålder. Ingen bakdatering/föryngring. Nytt komplett par med färska jämförbara källor återstår före release; kalla inte gamla paret slutkodsacceptans.
- 189 fokuserade tester, Ruff och compileall PASS. Aktiva universummanifestet är oförändrat; befintlig drift har själv förnyat Primat-cachemanifestet den 19:e. Historiska ICA-observationer är nu STALE och är inget aktiveringsunderlag. Fulla rådata, ID:n, osäkerheter och nästa blockerare finns i leveransen.

---

# Smako – 16 september 2026, ICA-inventering per område och inaktiv erbjudandepilot

[Leverans och kvarstående luckor](../reports/ica-area-20260916/README.md), [butiksvis täckning](../reports/ica-area-20260916/COVERAGE.md), [separat releaseförslag](../reports/ica-area-20260916/RELEASE.md). Befintlig branch/worktree `sources/lidl-ica-evaluation-20260914` användes; tidigare ej committat arbete är bevarat. Ingen produktionsaktivering, ny cron, deploy eller baspriskataloginsamling. Primat och befintligt publikt ICA-flöde kvar.

- Automatisk officiell inventering: Lund 12/12 resultat, 9 verifierade adressorter inom området. Linero 1004598, Söderlivs 1004339, Clemenstorget 1004409 och Tuna 1003391 finns med. Södra Sandby, Genarp och Veberöd ligger utanför den befintliga adressortsgränsen. Samma CLI med Malmö: 69/69, 21 inom adressort Malmö. Full offentlig kartprojektion kompletterar paginerad SSR-lista; ingen Lund-lista eller ny radie/postnummergräns.
- Färska offentliga Lund-svar 16 september 05:39–05:40 UTC, därefter offline v6-replay med oförändrade observationer: 631 poster, 609 parsade, 22 avvisade, 508 aktiva i sju isolerade OWN-snapshots. Söderlivs/Linero understiger oförändrad 95 %-gräns och är blockerade, inte tomma. Nio PDF-utgåvor/94 sidor hämtade; alla bildbaserade, kampanjextraktionen ofullständig. Torsdag 17/9 i Malmborgs/Brunnshög särredovisas från veckogiltighet.
- Frivillig ICA-provider återanvänder OWN, ProductMatcher, PriceUniverse, personligt medlems-/datumval, A/C:s `price=None`, korgberäkning och audit. 121 exakta produkt-/förpackningskandidater (104 offentliga, 17 medlem) införda; bara sju har individuellt näringsstöd i faktiskt prövade recept. Trasigt valfritt underlag blockerar inte basbygget. Default drift är oförändrad.
- Riktig identisk 15/20-profil före/efter: båda HTTP 201/VERIFIED, 783,03 kr, inga ICA-tillskott valda. HTTP 70,883/71,579 s. Brunnshögs verkliga tomater 500 g/30 kr följer separat hela kedjan till 300 g behov → ett paket/30 kr, godkänd audit. Ingen menybesparing påstås. 156 riktade offline-tester, Ruff och compileall passerar.
- Faktakontroll: alla 34 980 basposter och deras sakvärden finns kvar, nio identitetsfaktaposter tillkommer. Åtta basposter får dock ordinarie härledd `identity_variant`-flagga vid tillskottet. Faktamängderna är inte helt identiska; exakt differens finns i rapporten och är granskningskrav före release. Aktiva manifest och Primat-cache är hashstabila.

---

# Smako – 15 september 2026, ICA-pausen avgränsad till baspriskatalogen

[Kontroll av befintligt erbjudandeflöde](../reports/ica-offer-flow-check-20260915/README.md). **Pausen gäller blockerad direkt baspriskatalog/browserinsamling, inte befintliga publika ICA-erbjudanden.** Befintlig OWN-erbjudandeinsamling ska behållas. Sparad dygnskörning har 206 parsade/promoted offers_only-poster: Gunnesbo 138 och Södra Sandby 68. Aktivt PriceUniverse innehåller ett exakt matchat Stämmis-kontrakt (Falukorv, 2 för 65 kr), men det saknas i de tre förberedda ingredienskandidatindexen och produktens paketstorlek saknas. Kopplingen läser bara medlemspriser; publika icke-medlemspriser stannar i OWN. Clemenstorgets 73 erbjudanden finns endast i separat utvärdering och saknar aktiv OWN-butikssnapshot. Nästa steg är befintlig erbjudandeintegration/produktkvalificering, inte retry av blockerad baspriskatalog. Kontrollen var skrivskyddad mot produktion: inga ICA-/Primatanrop, browserförsök, refresh eller aktivering.

---

# Smako – 15 september 2026, Lidls två näringsluckor lösta och 15/20 verifierad

[Leverans, källor, körkommandon och pilotunderlag](../reports/lidl-nutrition-20260915/README.md), [jämförbara resultat](../reports/lidl-nutrition-20260915/comparison.json), [precisa meny-/korgavslag](../reports/lidl-nutrition-20260915/choice-quotes.json).

- ICA:s direkta baspriskatalog är pausad; befintlig publik ICA-erbjudandeinsamling berörs inte. Inga ICA-/Primatanrop, ingen aktivering, croninstallation eller ändrad användarprofil/butikskrav/färskhetsgräns i denna etapp. Arbetsgrenen används. Aktiva prisartefakter, Primat-cache, manifest, image och cron oförändrade.
- Exakt Allerum Grevé 28 %, 12 mån, 670 g (GTIN 7393720092442): tillverkare + Dabas styrker 27 g protein/100 g, med explicit 0 g kolhydrat. Kronfågel naturell lårfilé 900 g: tillverkarartikel 8028 och dokumenterad identisk förpackningsbild kopplas till Lidl GTIN 7300328028001. Tillverkar-GTIN inte oberoende belagt. Rå deklaration 20 g protein/100 g; kolhydrat <0,5 g bevarad som gräns, inte noll.
- Opt-in `reviewed_product_nutrition` binder två befintliga `ProductFacts` till exakt granskad produkt/förpackning/snapshot. Ingen ny generell databas. Befintlig varm insatsuppskattning får separat lårfilérecept: 200 g rå filé/person, all mat/sky serveras. Ingen bröstfiléreferens eller obelagd tillagningsfaktor. Gamla bröstfilérecept avvisar lårfilén. Näringsregistret laddas inte i produktion.
- Tre HTTP-körningar, faktisk schedulerimage/miljö UID 10001, nätverk avstängt: normal bas, kontrollerat Lidl-tillskott, normal byggning med Lidl före ingrediensurval. Original-SQLite/råunderlag + fryst Primat-cache, ingen återbyggnad via begränsad lokal sökprojektion. Identiska basprodukter/observationer, kod, request, fakta och inköpsdag 2026-09-15 verifierade. **Alla: 15 tillfällen/20 portioner, 40/30/20 g, två ställen, 793,03 kr, inga Lidl-köp.** Coop Online Syd 506,91 kr + Willys Lund 286,12 kr. HTTP 68,348/76,550/73,657 s; originalbyggningar 150,177/148,324 s. Sparade observationer fortsatt färska, ingen ny prisinsamling.
- Alla tre erbjudanden når pris-/ingredienskandidatstegen. Osten näringskvalificerad i fem recept. Lårfiléreceptet blir en elfte godkänd middagskandidat; en verklig enskild måltid väljer en 900 g-påse för 99 kr, 400 g rå användning, total tvåbutikskorg 131,57 kr och godkänd audit. Normalgenereringens 106 recept är annars identiska mellan armarna. Detta är inget helt-menysparande.
- Fast Lidl-ost kostar 79,90 kr för behovet 80 g, mot vald Coop-förpackning 43,50 kr. Den fasta hela menyn kräver Coop + Lidl + tredje ställe för köpbar vitkål. Prövade lårfilébyten stoppas av variation eller kombinationer där kvalificerat ris kräver tredje ställe. Noll tillåtna tvåbutikskombinationer för de loggade köpberäkningarna; ingen global omöjlighet eller optimalitet påstås. Sökgränserna är oförändrade.
- 105 fokuserade regressioner (16 nya), Ruff/compileall PASS. Kampanj/snapshotgranskningen gäller endast blad 01a0664a-ccb7-7278-a66f-8af0278032c3, 14–20 september. Ordinarie Lidl-priser förblir okända, offers_only, maxantal och datum intakta. Nästa separata beslut kan avse frivillig funktionspilot för exakt granskat tillskott; underlaget visar ingen besparing för 15/20. Nästa blad kräver ny tillämplig granskning. Ingen aktivering är utförd.

---

# Smako – 15 september 2026, Gunnesbos serverdiagnostik avslutad

[Slutlig dokumentkontroll](../reports/gunnesbo-document-check-20260915/README.md), [oskickade frågor till ICA och Primat](../reports/gunnesbo-document-check-20260915/kontaktunderlag.md). En verklig lucka fanns: tidigare full Chromium prövade startsida + produkt-API, medan 50-prisbeviset gällde SSR-sökdokumentet. Exakt en vanlig navigation till den observerade `/stores/1088004/search?q=mj%C3%B6lk` genomfördes i samma fungerande full Chromium/schedulerkonfiguration. **Huvudrespons 403, text/html, 919 byte, “Request blocked”, 2026-09-15 15:00:09 UTC**. Ingen initial-state-/produktprojektion i det nya svaret; inga efterföljande produkt-API-svar observerades. Inget gammalt sidtillstånd användes. Körning 1,121 s, UID/GID 10001, operationslås. Serverdiagnostiken stoppas nu; ingen ytterligare retry utan medgiven fungerande dataväg från ICA/driftansvarig. Ingen specifik policy, inloggningsplikt eller permanent omöjlighet är bevisad. Inga app-/connector-/A/C-ändringar, ingen aktivering/cron; Primat och aktiva prisartefakter oförändrade.

---

# Smako – 15 september 2026, avgränsad Gunnesbo-åtkomstdiagnos

[Rapport, kommandon och evidens](../reports/gunnesbo-access-20260915/README.md). Arbetsgrenen används; ingen aktivering, croninstallation eller ändring av A/C, butikskrav, färskhet eller användarprofil. Primat och aktiva manifest/artefakter är oförändrade.

- Tidigare 50-prisbevis kom från `mcp__cua_repl`, **Codex In-app Browser (iab)**. Browserversion, binär, fysisk körplats och ny kontext är inte belagda. Ny flik bevisar inte tom sessionshistorik; anta inte användarens lokala dator. Produkt-XHR:s body/status sparades inte då; prisbeviset var SSR-projektionen.
- Samma schedulerimage/cronmiljö rekonstruerar standardstarten som **Chrome Headless Shell 145.0.7632.6**, verifierat via den startade processen. Full Chromium av samma version får ett separat Crashpad-startfel i read-only-miljön; egen temporär XDG-konfiguration löser detta offline. Befintlig insamlare har opt-in `--browser-channel chromium`, inga cookieimporter eller skyddsbypasser.
- Slutkodens nya helt obemannade nätkontroll **12:46:33–12:46:38 UTC, 5,100 s**, UID/GID 10001, faktisk cronmiljö: butiksdokument GET 200, normal sökning, produkt-GET **403, text/html, 919 byte, “Request blocked”**. Bounded diagnostics läser granskade felmarkörer utan råbody/headers/sessiondata. Transporthash `5aff1f84…ce1b7e`, diagnostik `de3ffd47…d6f74` matchar slutkod. Stopp utan fler ICA-anrop. 0 produkter; aktuellt totalantal/täckning okända. Ingen traversal/queryutökning eller automatisk cronstart.
- Miljörättningen löser browserstart, inte produktåtkomst. Full Chromium ensam räcker inte. Exakt bakomliggande åtkomstpolicy/session-/nätorsak är okänd. Fortsättning kräver en av ICA/driftpartner medgiven fungerande produktprisväg för 1088004 online från servermiljön; ingen ny blind retry.
- Bevarad Primat-råprojektion: 1 848 Gunnesbo-/71 Clemenstorgetsposter saknar bevarat kanalbelägg; exportvitlistan utelämnade flera kanalfält. Gamla normaliserade `physical_store` är därför fortsatt **okänd kanalproveniens** för båda butikerna. Framtida parser/discovery/cache har frivillig `price_context_evidence` som skiljer explicit källvärde, saknat/okänt fält och tilldelning från default/butik/persistent kontext. Legacy-fält utelämnas; gamla kanaler/tider skrivs inte om. Inte aktiverat.
- 173 fokuserade tester, Ruff och compileall passerar. Offline browserprov med syntetiska svar körda i rätt cronmiljö; 0 retaileranrop. Aktiva prisartefakter/manifester, cron och schedulerimage jämförda oförändrade; operationslåset taget/släppt efter körningen. Inga ändringar utanför tillåten Primat-proveniens bland 300 jämförda befintliga arbetsytefiler. Ingen flerdagarsstabilitet påstås.

---

# Smako – 15 september 2026, kod och obemannad källtransport

Arbetsgren `sources/lidl-ica-evaluation-20260914`, bas `02ad73b`. Ingen kod-/källaktivering: live är fortsatt `price-recovery-lund-20260914a`, Primat och sex pris-/butikskontexter kvar. [Samlad kodleverans](../reports/smako-source-implementation-20260915.md), [A: 15/20](../reports/source-implementation-20260915/A-1520-reproduction.md), [B: Gunnesbo](../reports/source-implementation-20260915/B-gunnesbo-unattended.md), [C: erbjudandemodell](../reports/source-implementation-20260915/C-offer-only-model.md).

- A: historisk riktig request/artefakt reproducerad till 560,33 kr med fryst testklocka/orörda observationer. De 25 mallarna användes bara i täckningsanalys; planeringen hade 105 råa kandidater. Felaktig återbyggnad genom LocalPriceUniverseProvider tappade kvalificerade middagar, 10→6. Korrekta faktorkontroller skiljer detta från sökningen.
- A: septemberrequesten är möjlig. Begränsad beam tappade fungerande prefix. Slutkod deduplicerar likvärdiga genererade dagpermutationer och gör högst ett explicit 8→64-försök efter uttömning och prunade olika prefix, endast utan skafferi/produktlås. Näringsstartpunkter inom tillåtna butiksdelmängder tillkommer; näringsbudget 256 och alla användarkrav kvar.
- Slutkodens riktiga 15/20 genom isolerad HTTP, sparning och återläsning: 201/VERIFIED, 805,23 kr, alla 40/30/20, Coop Online Syd + Willys Lund. Bas 109,197 s och Lidl 121,335 s HTTP. Ingen ny 30-sekunders-prestandaacceptans. Detta är arbetsgrensverifiering, inte ändrad livefunktion.
- C: price=None stöds utan fabricerat ordinarie pris genom normering, prisavtal, optimering, audit, redigering och UI. Datum/inköpsdag och hela korgens köpgräns följer med. Inaktivt erbjudande hoppas över utan att stoppa giltig basprodukt; syntetiska regressioner täcker före/under/efter, paketkostnad, gemensamt tak, vald kampanj och ingen förbättring.
- C: samma tre exakt granskade Lidl-priser/vecka 38/14–20 sep, offers_only, fysisk destination Åkerlund och Rausings väg 1 Lund. Observationer 05:56 UTC oförändrade, inga nya Lidl-anrop. Alla 3 passerar matchning/semantik/shortlist; ost/kyckling når personlig resolve men saknar kvalificerad näring. Ostdeklaration saknas, lårfilé får inte låna bröstfiléns referens. Inga Lidl-köp: fullprofil 805,23 med/utan; middag 67,16 med/utan. Kycklingpaket 99 mot 43,90 är dessutom dyrare; prisjämförelsen ensam förklarar inte näringsavslaget.
- B: körbar separat Playwrighttransport/CLI och browserimage från exakt schedulerbas. Riktig obemannad nätkörning UID/GID 10001/faktisk cronmiljö: dokumentGET 200, verkligt sökfält, observerat produktGET 403 efter 5,045 s. 0 prisposter/0 batcher, aktuellt totalantal okänt. Ingen retry/bypass/cookieimport. Slutliga saneringshärdningar testade offline, live- och slutkodhashar redovisade separat.
- B: full pagination >50 testad med 83 tydligt syntetiska UI-produkter, inte nätbelagd. Aktuell riktig plan ger 12 behov/32 förekomster; frivillig lista med 13 sökord sparad, belagd obemannad täckning 0/12 på grund av 403, faktisk källtillgång okänd. online_price hålls separat. Primat physical_store kan komma från default och är metadataosäkerhet, ingen tyst omklassning. Clemenstorget kvar på Primat.
- Verifiering: 70 ICA-tester,283 tidigare erbjudande/kompatibilitet, efter slutlig resolvefix 49 riktade och 55 slutlig A/C-samkörning PASS (överlappar, summera inte). Ruff/compileall/node syntax/diffcheck PASS. Slutliga HTTP-kodhashar matchar arbetsgrenen. Aktiva manifest/cache/snapshotpekare/cron/36–48 h/sex krav oförändrade, health/ready 200; delade låset återtaget och släppt efter prov.
- Inget schema installerat; helt kommenterat frivilligt ICA-shadowförslag finns. 0 lyckade automatiska flerdagarskörningar observerade. Nästa separata beslut: kodrelease med explicit prestandabedömning; Lidl fortsatt inaktivt tills aktuellt granskat blad/näringsstöd/pilotbeslut; Gunnesbo tillåten produktåtkomst före skuggschema/källbyte. Null-artefakter kräver kompatibel läsare; framtida rollback måste först välja giltig basartefakt före äldre appbild.

---

# Smako – 15 september 2026, Lidl/ICA-datablockerare

Live och Primat är oförändrade. [Samlad leverans](../reports/smako-source-unblock-20260915.md), [Lidl-kandidat och planering](../reports/lidl-lund-candidate-20260915.md), [Gunnesbo/Clemenstorget](../reports/ica-gunnesbo-clemenstorget-20260915.md).

- Lidl: samma parser v4 och schemafixar. Ny riktig liveinsamling i faktisk cronmiljö/UID 10001, manuellt startad: 391/389/2 hämtade/parsade/karantän, 12,872 s, snapshot PASS. Slutkodens LF-normaliserade hash stämmer med körningen. Ingen promotion.
- Nationellt reklamblad vecka 38 belägger tre specifikt granskade förpackningar via råprodukt-ID/GTIN, variant/packbilder, sid-ID och villkor: Stjärnägg 15 st 41,90, Allerum Grevé 670 g 79,90, Kronfågel lårfilé 900 g 99. Ägg/kyckling max 3 förp./hushåll. Kvalificerat för 15 september kl. 12, offers_only. Alla övriga region-1-poster saknar denna nya bevisning. Ingen lagersaldogaranti.
- Verklig Lidl-destination Åkerlund och Rausings väg 1, Lund, kontext context:lidl:05f1cb3d9fc89bc3. Isolerad middag 2 portioner/minst 40 g protein, 22350/max 2 ställen: VERIFIED 67,16 kr med och utan Lidl; bara Willys Lund, inga Lidl-köp, ingen besparing. Större 15/20-profilens basarm fick befintligt PolicyConflict; middagstestet är inte återacceptans av hela betaprofilen.
- Lidl-kandidatens slutliga offlinekvalificering i cronmiljön ger exakt samma testade kandidat. Hårda köpgränser och datum spärrar gissat ordinarie restpris. Ingen direkt produktionsimport: äldre obligatoriskt Product.price används bara som scoped verifierat köppris i experimentet; produktion behöver säker befintlig erbjudandeprojektion utan självständigt ordinarie pris.
- Gunnesbo 1088004: normal anonym browser via officiell butikssida → e-handel → mjölksökning fungerar. 50 publika faktiska köppriser i SSR-productEntities, 232 sök-ID:n; endast 50 prisposter, inte komplett katalog. Befintlig ICA-parser/normalizer återanvänds av isolerad adapter. 50/50/0 prisposter; ingen godkänd global kandidat.
- Gunnesbo vs färsk Primat-cache: 36 retailerProductId-par, 35 belagda lika förpackningar, 36 numeriskt lika priser. Direkt onlinepris vs Primat physical_store: 0 fullt likvärdiga jämförelser. Tidsavstånd 3 h 42 min 48 s; ingen överföring av Primat-GTIN. Räkost 1023643 saknar mängd i Primat.
- Normala browserpriser belagda, men en vanlig httpx-GET av observerad söksida ger 403 vid dokumentsteget. Rå XHR-metod/body/status och fullständig pagination saknas i browserverktyget; exakt sanerat underlag beskrivs i ICA-rapporten. Ingen cookieöverföring eller challenge-bypass. Offlineadapterreplay i scheduler 0,012 s/0 nätanrop är inte liveinsamling. Noll automatiska flerdagarskörningar.
- Clemenstorget 1004409: officiell näthandel pekar på Caroli/Mobilia, egen direkt baspriskatalog inte belagd. Inga nya gissade mappningsanrop, inga främmande butikspriser; Primat kvar. Blockerar inte Gunnesbo.
- 168 distinkta fokuserade tester PASS, Ruff/compileall PASS. Sex butikskrav, 36/48 h, cron, aktiva manifest/cache och Lidl-snapshots exakt bevarade före/efter; health/ready 200. Ordinarie nattkörning före arbetet hade förnyat aktivt universum till 495742a1…1e7a. Inga experimentella aktiveringar, kodreleaser, scheman eller obligatoriska beroenden.
- Nästa separata beslut: frivillig Lidl-pilot efter datum-/antalssäker integration; Gunnesbo parallell transport-/täckningsverifiering före eventuell flerdagarsacceptans; Clemenstorget behåll Primat. Återställning enligt befintligt atomiskt manifest/LKG/lås, aldrig via för gamla priser.

---

# Smako – 14 september 2026, Lidl/ICA-källutvärdering

Live är oförändrad: `price-recovery-lund-20260914a` (app och scheduler).
[Samlad leverans och beslutspunkt](../reports/smako-source-evaluation-20260914.md),
[Lidl](../reports/lidl-repair-evaluation-20260914.md),
[ICA](../reports/ica-direct-evaluation-20260914.md).

- Arbetsgren `sources/lidl-ica-evaluation-20260914`, bas `02ad73b`. Ingen experimentell kandidat aktiverad, Primat kvar, inga nya obligatoriska beroenden eller ändrade butikskrav.
- Lidl: ursprunglig schemaorsak avgränsad, prisparser v4 rättar bland annat felaktigt styckpris från `4 för 22`. Sparade källsvar/regressioner. Slutlig liveinsamling 386/384/2 hämtade/parsade/karantän; slutåterspelning i faktisk scheduleranvändare/miljö healthy och snapshotvaliderad, 0 nätverksanrop, 3,490 s. Observationerna 14:23 UTC bevarade.
- Lidl är fortsatt `offers_only`, standardregion 1. Fysisk Lund-giltighet och breda ordinarie priser obelagda. 159 pågående, 224 framtida och 1 utgånget fönster; 8 kuponger med okänd målgrupp exkluderas. Preliminärt 4/35 publika och 1/35 medlemsvillkorliga ingredienskrav; 0 fullt belagda globala Lund-priser för aktivering.
- ICA: officiella butikskort verifierar konto 1088004/BMS 17883 och konto 1004409/BMS 2771. 138+73 publika erbjudandegrupper parsade; Gunnesbos verifierade online-rout 403, Clemenstorget saknar verifierad online-URL. Isolerad diagnostik v2 kräver denna mappning och kan aldrig aktivera. Fäladstorget ersätter ingen butik; tidigare `collect` oklassificerat eftersom request/svarsbody saknas.
- 14 exakta ICA/Primat-GTIN-identitetspar, 0 fullt jämförbara prispar; två avvikelser förklarade med officiellt kampanj-/referenspris. Receptpotential 8/35 respektive 9/35 krav. Primat är jämförelsekälla. Ingen bred baspriskatalog och 0 lyckade automatiska flerdagarskörningar; inget ICA-byte rekommenderas.
- Diagnostiken kördes manuellt i verklig cronmiljö/UID 10001 med delat operationslås, inte som automatiska cron-event. 422 distinkta tester PASS, Ruff/compileall PASS. Slutkontroll 14:30:57 UTC: samma manifest/universum `927c331c…f34f9e2`, samma 6 färska kontexter, health/ready 200, gränser 36/48 h och cron oförändrade. Ingen kodrelease, prisaktivering eller användardataändring.
- Föreslagen senare aktivering och återställningsplan finns i samlad rapport. Aktivera inget utifrån teknisk `healthy` ensam; gamla observationer föryngras inte av replay/bygg.

---

# Smako – 14 september 2026

Live: `price-recovery-lund-20260914a` (app och scheduler).
[Återställningsrapport](../reports/smako-lund-price-recovery-20260914.md).

- Planering 22350 återställd: alla sex Lund-kontexter färska, samma universum på disk/i process `927c331c…f34f9e2`, health/ready 200. Gränser 36/48 h oförändrade.
- Exakt kvalificerad basrequest: 15 tillfällen/20 portioner, 40/30/20, max två butiker. HTTPS mobilvy 201/40,781 s efter omstart, 560,33 kr VERIFIED; byte 200/7,092 s. Noll externa källanrop. Ingen ny treprovs-prestandaacceptans.
- Willys-transportens fel rättat via befintlig driftcontainer/UID. Båda kontexter importerade med äkta observationer. Verkliga Windows-tasken återtestad: resultat 0; schema 01:30 oförändrat.
- Primats historiska ValueError är fortfarande oförklarat. Två isolerade kompletta 49-anropskörningar passerade även parsning/export/validering/context activation. Godkänd färsk export användes. Ny steg-/stack-/orsaksdiagnostik bevarar nästa fel; ingen specifik historisk Primat-fix hävdas.
- Obligatoriska kontexter kontrolleras vid aktivering, planering och ready. Driftstatus varnar vid 36 h och visar rebuild-/aktiveringsfel. Separata Coop-erbjudanden, Karhögstorg och Lidl-fel kvar enligt rapport.
- 139 tester PASS, Ruff/compileall PASS. Backup `20260914T123547Z`; samma VPS, Caddy och miljöfilens rättigheter bevarade. Föregående app är läskompatibel rollback; föregående schedulerbild sparad.

---

# Smako – 13 september 2026

Live: https://beta.smako.nu/personal · `personal-v2-fast-403020-20260913c` · appkod `98381e5`.
[Prestandaacceptans och reproduktion](../reports/smako-fast-combined-403020-20260913.md).
[Föregående kombinerade funktionsacceptans](../reports/smako-combined-403020-20260913.md).

- **30-sekundersmålet PASS.** Fryst request-kall beräkning 357,670 s (före n=1) → median 26,480 s (efter n=3). Slutrelease genom HTTP: 27,047 / 27,462 / 28,007 s, median 27,462 s, tre nya gäster och ingen färdig resultatcache.
- Middag 5×2 ≥40 g, frukost 5×1 ≥30 g, mellanmål 5×1 ≥20 g per portion. Totalt 15 tillfällen, 20 portioner, Blandad/Balanserad, max två inköpsställen gemensamt. Spårbara uppskattningar uttryckligen på enligt denna milstolpe. Inga extra kcal-, fisk-, eko- eller skafferikrav.
- Samma frysta priser/fakta ger exakt samma meny, kostnad 574,92 kr, variation och kravkontroller. Kandidatpooler 95/5/5 råa och 10/2/2 kvalificerade, sökbredd/policy/prismotor oförändrade. Request-lokal exakt näringsmemoization, ren textcache och hashverifierad offentlig faktacache ersätter upprepade beräkningar. Admission omfattar faktisk arbetstråd även vid avbrott.
- Processkall ASGI till resultat 48,537 s; varm HTTP 27,124 s. Mobilformulär via HTTPS 28,760 s med laddad katalog; första efter omstart 33,224 s. Byte dag fyra 4,562 s, hel korg 584,92 kr och alla 40/30/20-krav kvar. Browserprov 390×844; fysisk telefon/mobilnät inte mätt.
- Två samtidiga isolerade planer 27,301/55,544 s; en aktiv/en i kö, sök/health <0,16 s, korrekt ägarisolering, inga kvarvarande arbetare. Dubbelklick gav en POST; navigation/timeout gav inga automatiska retries. Befintliga 600/540 s timeoutgränser oförändrade.
- 477 distinkta fokuserade regressioner passerade; 79 berörda upprepades efter sista adapterändringen. Ruff/compileall PASS. Separata A/B/C, uppskattningar på/av, ändrat protein/portioner/skafferi, paket/kampanj, färskhet, köp/revisioner och isolering kontrollerade. Strikt A/D fortsatt datablockerat; B/C fungerar utan uppskattningar.
- Backup `20260913T194832Z`; 164 äldre revisioner hashbevarade, nu 168. Health/ready 200; scheduler och prismanifest oförändrade. Läskompatibel rollback till `personal-v2-fast-403020-20260913a` verifierad utan databasrestore. Mellanbild b aktiverades aldrig.
- Kvar: gemensam näringsalternativ-/paketsökning (7 335 korgoptimeringar), första råfaktaladdning, befintligt begränsad sökning, strikt middagsunderlag och okänd slutvikt. Inga nya källanrop, observationstider, recept, OIDC-, Willys-task/relay-, server- eller tjänsteändringar.
- Tidigare [fiskfria acceptansen](../reports/smako-fishfree-five-dinners-20260913.md) är historik och får inte ersätta 40/30/20-profilen.


## 2026-09-20 structured ICA release — blocked before activation

User authorized production release of structured ICA offers and campaign-driven refresh, no images/paid models. Continued on sources/lidl-ica-evaluation-20260914, HEAD 02ad73b with all previous dirty work retained; pre-edit archive in reports/ica-structured-release-20260920/prework.tar.gz.

Read reports/ica-structured-release-20260920/README.md, RELEASE.md, COVERAGE.md, CONTROL.md, PROFILE.md and release-gate.json before resuming. Concrete code/image ica-structured-lund-20260920a prepared, not deployed. Fresh final collection 2026-09-20 10:37–10:38 UTC: 12 discovered/9 inside strict official-address Lund locality; 654 offers, 155 row-approved OWN, 154 isolated PU, remaining quarantine preserved. Gaständare is the one extra OWN→PU rejection: normalized sold_by_piece conflicts with existing strict offers_only fixed-package contract; see exact retained error, not a generic nonfood exclusion.

Normal publication previously failed IneligibleMemberPriceError for two public Willys products whose independent public/member amount happened to coincide. Reused the existing dirty-tree fix and real source regression. Also fixed optional offer combinatorial overflow: unchanged 200000 exact limit, precomputed search size, same optimizer can return independently verified baseline with explicit warning instead of optional additions blocking it. New campaign evidence preserves null start, original observation and explicit end; bounded campaign policy distinct from unchanged base 36/48h. Durable 15-minute due checker reuses managed refresh/locks. Source promotion fingerprints, campaign transitions, row-only OWN inputs and 35h base deadlines covered. Willys local timer is independently owned and not falsely advertised as campaign-coalesced.

Final same-input real 15/20 HTTP tests PASS: without additions 560.33 SEK / 38.422s; with additions 560.33 SEK / 39.253s. 15/20, 40/30/20g, max2, membership off unchanged. 15 individual nutrition-supported products, none of the new ICA products selected. Actual separate matcher→checkout→audit proofs PASS for Linero mushrooms 250g/15 SEK, Söderlivs pizzakit 600g/19 SEK and mushrooms/20 SEK, Gunnesbo oats TWO 1500g packages/30 SEK; ordinary price null. Full isolated managed publication and restart/no-due/no-network PASS. 150 regression tests, last affected optimizer 28 rerun, last affected scheduler/relay 20 rerun, Ruff/compileall PASS.

CRITICAL EXTERNAL GATE: Set-ScheduledTask updating existing Smako Willys Local Relay action/trigger returned Access denied. Original daily task was re-enabled and verified unchanged. No server env/current link, price manifest, or cron changed. Existing beta remains version price-recovery-lund-20260914a, active PU 4832eaa0... built Sep16, health200/ready503. Production backup succeeded 20260920T104654Z; private env backup /opt/smako/rollback/ica-structured-lund-20260920a/. Inactive local relay export D:/smako-local-relay/releases/ica-structured-lund-20260920a. User was asked early to run configure-relay-admin.ps1 as Windows administrator; it configures the SAME task disabled pending coordinated release. No secrets requested. Waiting for this external permission/configuration; do not silently treat old daily relay as satisfying the new demand-policy gate.

production_ops.py activate checks actual task configuration before contacting deployment, and artifact/code/current campaign-day gates before stopping scheduler. Activation/switch/live_verify.py remain UNEXECUTED. User data untouched. Never reactivate stale Sep16 manifest as rollback: use newly validated compatible fresh baseline instead. If campaign day, code or source freshness changed, repeat affected fresh collection/acceptance before activation. Do not reuse today's PASS after midnight as current campaign evidence. No multiday stability claim.


# 2026-09-20 — separate municipality/source-audit branch

New work ONLY in C:/Users/ossia/Documents/Codex/2026-09-16/municipality-coverage-20260920, branch areas/municipality-audit-20260920. Inherited dirty baseline preserved; pending ICA release in original directory untouched. See reports/municipality-offers-20260920/README.md, SOURCES.md, NEXT.md, RELEASE.md and incremental.patch.

Opt-in municipality mode uses official SCB 2026 codes plus evidence-bound explicit retailer administrative addresses. Legacy locality remains default. Live ICA Lund 12 included vs 9 locality; Malmö 24 included, 10 outside, 35 unknown among 69 discovered. Four missing Malmö-locality addresses enriched via original transport; exact cross-query address evidence reused without renewing source time. Lantmäteriet metadata200 but geometry401: no coordinate membership fallback. All other-chain 50 physical candidates retained with unknown municipal membership.

Fresh bounded Windows source checks reused Willys/Hemköp/Coop/City Gross/Lidl connectors; public/group/member prices exist without images. 24 sample prices reported with raw IDs/time/terms and read-only OWN/active-PU comparison. Coop text loses periods, variant identities and full conditions (Yoggi not lactose-free), plus eight public prices acquire unproven ordinary role: recommended one next connector-local fix, NOT implemented or activated here. Hemköp applied=true vs offerStatus=Vilande flagged. Active beta PU remains Sep16; no fresh planning acceptance claimed, no prices/config/schedules/tasks changed. Municipality completeness explicitly partial; no new production activation proposal approved.


## 2026-09-21 — Coop physical offers correction, isolated only

Continued in areas/municipality-audit-20260920, same separate worktree. See reports/coop-physical-fix-20260921/README.md, COVERAGE.md, EXAMPLES.md and RELEASE.md. Existing browser now retains public DKE response with exact physical store/ledger, source hash/time and opaque variant IDs (not fabricated GTIN). Coop parser v3 preserves campaign/member/group roles, dates, packs and exclusions; ordinary price stays null. Existing SourceOffer → row-approved collector/OWN → PriceUniverse reused; explicit partial contract, full 95% gate and 36/48h unchanged. Online 730400 remains separate.

Final actual Windows collection Sept21 09:44 Stockholm: Flöjtvägen 22 groups/135 variants, 44 approved/91 quarantine; Bulltofta 56 groups/356 variants, 68 approved/288 quarantine. 112 isolated PU products, no active-beta change. Proportion/full snapshot remains broken; row candidate explicitly partial. Percentage lamps (74 variants) preserved without monetary purchase price. Newly observed isPil flag remains unresolved: 13 variants quarantined, 9 would otherwise qualify; do not reuse preliminary 77/121 totals as final.

Final acceptance uses final-live-v2 sources unchanged and final-acceptance-v2. Pasta 300g/15 SEK and member mince 500g/59.90 (max3) pass checkout/audit in both stores. Flour 2x2kg/26 SEK charges correctly but recipe audit fails LOW semantic confidence; not forced through. 184 regression tests pass, affected 22 rerun after lint-only refactor; Ruff/compileall pass. No full 15/20 or savings claim. Source times never renewed by replay. No server-runtime acceptance claimed.

Original pending ICA worktree 139 inherited file hashes and 415 release hashes verified unchanged. No production, Windows task, scheduler, server configuration, Primat or ICA-base-pause changes. No images/paid calls. Release proposal is separate and requires future fresh runtime/compatibility acceptance and explicit activation decision. Baseline archive plus incremental.patch separate these changes from inherited uncommitted work.


## 2026-09-21 — bounded Coop closeout, no activation

See reports/coop-closeout-20260921/README.md, QUARANTINE.md and RELEASE.md. Previous 112-price release artifacts retained unchanged. Classified all 379 quarantine variants: Flöjtvägen 78 food/10 groups +13 other/1; Bulltofta 185 food/31 +103 other/9; no unknown titles in this reviewed sample. Primary causes are disjoint per variant; overlap tables deduplicate repeated error codes. Prior package-error counts 14/18 were occurrences, actually 7/9 unique variants. isPil 13 variants spans 8 groups, correcting previous prose.

Small source-proven alias fix: Kärnvetemjöl parent Vetemjöl now matches recipe vetemjöl. Narrow visible-name gate rejects other flours/mixes even with incorrect structured identity. No nutrition, GTIN, ordinary prices or pantry assumptions added. Original flour audit bypassed matcher; old exact Kärnvetemjöl query already matched, ordinary vetemjöl rejected. before-matcher.json reproduces that with archived old modules. New actual same-source collector→OWN→PU→matcher→checkout→audit passes all six proofs; flour 2x2kg/26, no one-pack13 rest price. Approved totals remain44/68, quarantine379 unchanged; no new import claims. Nutrition-backed 15/20 still unverified.

324 focused/regression tests PASS18.46s; 18 affected tests rerun5.14s after import ordering; Ruff/compileall pass. No external fetch this closeout: original Sept21 09:44 source times retained, isolated verification at17:17 Stockholm3.385s. No production/Windows/schedule/config changes, no other chains, images or paid calls. Keep this additive closeout patch separate from both prior Coop patch and waiting ICA release.

## 2026-09-21 — Coop municipal store coverage, isolated only

Same separate worktree/branch. See reports/coop-municipality-20260921/README.md,
COVERAGE.md, EXAMPLES.md, RELEASE.md and coverage-final.json. National official
Coop map720 + X:-tra58 =778 store rows; SCB RegSO2025 position test yields Lund10
inside (9 Coop/Stora,1 X:-tra),768outside,0unknown. This follows municipality
boundaries2025-01-01, not address locality; Genarp/Veberöd included. No independent
business-list completeness claim. Same code offline Malmö18inside/759outside/
1unknown, preserved. Legacy area modes and user store selection unchanged.

Fresh individual physical feeds Sep21 19:55–19:58 Stockholm:499 OWN/isolatedPU
variants from2436, quarantine1937,372 store-campaign groups. Every full snapshot
still below95%; explicit row-approved contracts only. Previous112-artifact preserved;
Bulltofta outside Lund. 44 Flöjtvägen overlap;455 additional store-variant posts.
Map/StorePage account string/int comparison fixed without relaxing exact identity.
Stora source ageRestriction/simplifiedAgeRestriction retained and23 rows blocked;
unknown shared schema fields still fail closed. Existing isPil/deposit/group guards
unchanged. Same source campaign family+period conservatively shares household cap
across stores, never shares prices or grants store applicability.

Source→OWN→PU→matcher→checkout/audit:27 real ingredient proofs. Actual optimizer
max2 stores Genarp flour26 + Veberöd pasta15 =41 SEK, auditPASS. Cross-store2+2
mince packages rejected against sharedmax3;2+1 allowed. 356 testsPASS33.36s;
Ruff/compileallPASS. No nutrition-backed menu/savings/server-runtime claim.
OWN legacy postcode helper rejects247xx; isolated verification uses existing
/stores by known source locality + exact source ID and normal provider.get_offers,
not fabricated postcodes. Future beta area selection must consume explicit inventory.

X:-tra3658/account216525 official link -> eight PDF text pages all fetched.
Status document_text_unintegrated,0imports,advertisementcountunknown, not empty
and not image-only. Page8 validThu24–Sun27, notMonday. No image/paid API.
Primat, Online730400, ICA-basepause, pendingICApackage, production, userprofiles,
Windows task/schedules/serverconfig unchanged. Separate release proposal only.

## 2026-09-22 – X:-tra retained PDF text import, separate partial candidate

Same municipality worktree/branch; reports/xtra-text-20260922/README.md and
RELEASE-COOP.md / RELEASE-XTRA.md are the latest bounded delivery. No deployment.
New opt-in coop-xtra-pdf-text-v1 uses existing PyMuPDF text spans/grid and original
source binding, no OCR/model/API. SourceOffer → collector → partial OWN → normal
provider/PU → matcher/checkout/audit. No GTIN or ordinary price fabrication.
Source PDF Skansvägen3658/account216525 SHA065efd248050a6761a45adad7695186048484f76e9d6d1aebe05f18458c4aa18,
observed2026-09-21T17:56:02.943342Z, week39 Sep21–27; page8 Sep24–27 only.
Final actual local-time verification Sep22 07:46:32, age11.842h, runtime1.892s.
8 pages,57 detected textual ads,10 approved OWN,9 current PU,1 future,47 blocked.
Unknown additional image ads remain unknown; not complete flyer coverage.
Fullsnapshot10/57 remainsbroken;95%unchanged. Couscous15, tomato2x200g30,
onion3kg19.90 matcher/checkout/auditPASS. Honey30 priceimported, ingredientmatch
blocked. No nutrition-backed menu. Future cappedmemberads blocked pending
verified cross-store campaign identity; PDF hash is not shared household evidence.
125testsPASS49.55s; finalaffected20PASS16.58s includes1newtest; Ruff/compileallPASS.
Coop499approved/1937quarantine preserved, replay25auditPASS21.077s. CurrentPU493:
six Stora meal variants expiredSep21 (exact IDs in expired-difference.json), not lost.
Previous27proofs preserved;2additionalStora proofs reused hashstable, not newnetwork.
Separate Coop release remains independent of Xtra; real unchanged15/20 with fresh
frozen base arms/nutrition/max2 is still pending. No external calls/production writes.
Primat, pendingICA, users, Windows/schedules/serverconfig unchanged.


## 2026-09-22 – municipal Coop controlled 15/20, no activation

Same isolated municipality worktree/branch. Latest decision:
reports/coop-1520-20260922/RELEASE-COOP.md, PROFILE.md, COVERAGE.md.
New optional CoopMunicipalityOfferProvider and two explicit builder arguments
coop_offer_database / coop_municipality_inventory reuse collector/OWN/full-source
builder; official municipal IDs include Genarp/Veberod without changing profiles.
Exact physical contexts, Online730400 separate, household cap IDs retained.
Missing/corrupt optional source retains baseline with diagnostic. No drift wiring.

Fresh actual server browser collection Sep22 06:39:02-06:39:38 UTC:
9 stores,493approved/1937quarantine. Six Stora day-only Sep21 rows remain excluded.
Uses pre-existing smako-ica-shadow:20260915 Python3.12/Playwright runtime; prepared
ordinary scheduler image lacks playwright. No installation/production changes.
Full live source DB+validated Primat frozen08:32:48 Stockholm under shared lock;
latest ordinary live collection, not an extra full-base crawl or search projection.
Oldest usable base CoopOnlineSep21T01:17:55Z (<36h); same exact fullsources botharms.

Final real HTTP A/B, identical request hash0bac8f0da2dfdaa922dfacc9a57527ff4c083d2d987ceba3ea242d11619b7d6c,
identical application code/baseproduct hash/nutrition facts and106 frozen recipes.
15slots20portions40/30/20,max2,membershipsOFF,existingallow_nutrition_estimates unchanged.
A536.27 SEK,HTTP40.440s,total215.421s; B536.27 SEK,HTTP43.731s,total234.415s.
Same CoopOnlineSyd+WillysLund, zero municipalCoop selected.493retainedprices,
22actualproductnutritionlookups,0supported: verified product facts/identity missing.
No guessed GTIN/nutrition.332Bbasket auditsPASS;both201+identical savedreadback,
health/ready200,privateidentity/planDB,networkdisabled.141regressionsPASS14.578s.
No demonstrated saving; not ready as a verified15/20 improvement. Separate
browser-enabled Coop deployment integration still required; do not deploy dirty
worktree/pendingICA package wholesale. Xtra is independent and not a blocker.
Production already refreshed overnight toSep22 before this task; originalimage
price-recovery-lund-20260914a remains, same active manifest, users/schedules unchanged.
Rollback and publication fault evidence: server-results/publication-result.json.
No production activation, Windows/schedule/server configuration/image/model changes.


## 2026-09-22: Coop-näring och separat browserpaket (ingen aktivering)

Fortsatt i `areas/municipality-audit-20260920`, bevarat ärvt/ocommittat arbete.
Se `reports/coop-nutrition-20260922/README.md`, `22-POSTER.md`, `PACKAGE.md` och
`RELEASE-COOP.md`. 22 tidigare näringsprövade rader = 7 källvariant-ID:n.
Strikt faktaöverföring via befintlig Coop-katalogidentitet/variant/förpackning
(ingen prisöverföring eller ny GTIN), bibehållna näringsgränser och smala
plommontomatalias: 14/22 nu näringskvalificerade, åtta färska pastor spärrade.
Samma fullständiga frysta baskällor/faktaversion i slutlig 15/20 A/B: 536,27 kr
båda, samma 12 produkter/2 kontexter, noll valda fysiska Coop-rader. Separata
Cheddar/Gouda-receptprov klarar näringskrav och checkout/audit; högre paketkostnad.
Nio färska flöden: 493 godkända/1937 karantän. Slutlig separat serverimage
`smako-coop-candidate:nutrition-20260922` (hash i PACKAGE), UID 10001, befintlig
Playwright/Chromium, operationslås, inga kodoverlay, verklig begränsad hämtning.
125 fokuserade tester + Ruff/compileall PASS. Privat publicering/rollback PASS.
Redo för separat tidsbunden aktiveringsprövning; ingenting aktiverat. Giltig
rollbackbas stoppar 2026-09-23 03:17:55 Europe/Stockholm, varning 22/9 15:17:55.
Ny kontroll/insamling krävs efter tidsgräns. Primat, produktion, väntande ICA,
Windows/scheman och X:-tra är oförändrade. Inkrementell patch utgår från denna
etapps säkerhetskopierade smutsiga arbetsläge, inte från ren HEAD.


## 2026-09-22 – bestående kommunacceptans Coop/Stora Coop/X:-tra

Separat arbetskopia/gren oförändrad. Se `reports/coop-municipal-contract-20260922/README.md`, COVERAGE.md och RELEASE.md. Samma kod har körts med officiella kommunkoder 1281/1280, färsk inventering av 778 upptäckta butiker per prövning. Lund 10 inne/0 okända; Malmö 18 inne/1 okänd (X:-tra Kirseberg 3548, gränsnära). Alla rader finns i STORES-1281/1280.md.

`approved_municipal_stores` binder om kommunbevis i urval/provider/X:-tra-import; sparat inside räcker inte. `collect_coop_municipality` kopplar befintlig strukturerad insamling och befintlig PDF-textimport till isolerat OWN/PriceUniverse. X:-tra-länkar upptäcks ur varje aktuell officiell butikssida; inga fasta Skansvägen-/Lundutgåvor. `coop_municipal_refresh.update_selection` återanvänder kampanjpolicy, sparar omstarts-/retrytider och behåller alla butiker. Inget förfallet arbete ger noll prisanrop och ingen tom ersättningskandidat.

Färsk 22 september: Lund 493 strukturerade + 9 aktuella X:-tra-poster; Malmö 532 + 9. Separata X:-tra-PDF:er Skansvägen/Söderkulla, vardera 8 sidor/57 identifierade textannonser/10 OWN (1 framtida)/47 karantän. Texttäckning är partiell, okänd layout/bildannonser är inte noll. X:-tra Nydala saknar weeklyOffersLink. Malmö har dessutom tre ConnectorFetchError samt två gemensamma invalid offer quantity-fel (Stadion/Jägersro). Spärrar bevarade. Slutkod återspelad offline med exakt samma observationer/antal; checkout/audit för tre X:-tra-ingredienser per butik PASS. 105 unika berörda tester, Ruff/compileall PASS.

Ingen produktion, användarprofil, server, Windows eller scheduler ändrad. Tidigare Coop-näringspaket och väntande ICA-release bevaras separat. Ny kommunorkestrering har verifierats lokalt, inte byggts in i serverimagen; se RELEASE för återstående server-/aktiveringskontroller. Tidigare 15/20=536,27 kr per arm är oförändrat historiskt bevis, inte en ny körning för Malmö/X:-tra.


## 2026-09-22 – samlat Lundsunderlag och faktisk driftlucka

Senaste underlag: `reports/coop-lund-activation-20260922/RELEASE-LUND.md`, decision.json och UPDATES.md. Ingen ny inventering/aktivering/schema-/Windows-/serverkonfigurationsändring. Ny separat slutimage `smako-coop-candidate:lund-activation-20260922`, SHA00fd55cc75d824dfcfb1aa2c6abbee882c0af95a574ad190c2a6932db0064622. Paketet innehåller senaste kommun-/pris-/näringskod, CLI, BeautifulSoup/soupsieve/PyMuPDF-pins samt befintlig browser. Inga runtimeinstallationer i produktion.

Färsk serverinsamling nio Lunds-Coop:493 OWN/PU,1937 karantän, inga gemensamma kritiska blockerare. Skansvägens aktuella PDF upptäckt/hämtad i slutpaketet:10 OWN/9 aktuella PU/47 karantän, separat valfritt tillägg. Befintlig full builder tar fortfarande bara Coop/Stora; Xtra exkluderat ur fullkandidaten.

Fullständiga baskällor nyfrysta under operationslås, byteidentiska med tidigare underlag/cache. Full Coop-kandidat b893fb0448ca2e70d6a7e5a980dbf740fb3b8727ed8fb1b6b9d8b63eccdd2888 passerar befintlig privat publicering, lineage-/invalid-/stale-rollback-felprov och återstart. Produktionsmanifest oförändrat. Slutbildens riktiga15/20:536,27kr,HTTP201,43,949s HTTP/91,272s totalt,332 audits,sparning/återläsningPASS,inga fysiskaCoopval. 78 unika berörda tester+Ruff/compileallPASS.

Rättad releasepolicy: Coop/Xtra saknar ICA:s kampanjundantag från48h. Begränsa därför lyckad källas nästa hämtning till35h, behåll36hvarning/48hstopp, tidigare kampanjbyte och retry. Serverpolicyprovet verifierar omstart/15min-felretry. Beräknad nästaCoop23/9cirka22:28, Xtra22:34; inget installerat. Bas35h22/9 14:17:55, varning15:17:55, stopp/rollback23/9 03:17:55 Stockholm. Faktiskt oförändrat cron03:17nästa dag ger bara55sek marginal tillstopp och är inte tillräcklig säker insamlingsmarginal.

INTE REDO FÖR ÅTERKOMMANDE AKTIVERING: grocery_data.__main__._build_production_price_universe skickar ännu inte coop_offer_database/coop_municipality_inventory till byggaren; run_daily_refresh läser inte kommun-Coop:s beständiga källpekare/uppdateringsurval. Engångsartefakt fungerar, nästa normala rebuild riskerar tappa tillskottet. Nästa avgränsade kodsteg: explicit avstängd koppling av godkända källor+kommuninventering+durabelLKG/version till befintlig rebuild/publicering/reload, andra-rebuild/fel/omstartstester. Xtra kan fortsatt lämnas avstängt; Malmöfel är källbundna och ska inte blockera nio Lundsbutiker. Ingen aktivering före nytt beslut.

Testutrymmet i /tmp(tmpfs) blev fullt vid första backupen. Endast denna körnings data flyttades intakta till /var/tmp/smako-coop-lund-activation-20260922; ofullständig backup är bevarad i failed-base-disk-full. Ingen rensning av äldre data. Där lyckades full backup; datadisken har gott om plats. Primat, betan, användarnas val och väntande ICA-release bevarade.


## 2026-09-22: Coop/X:-tra i ordinarie refresh/rebuild (ingen aktivering)

Separat arbetskopia `municipality-coverage-20260920`, gren
`areas/municipality-audit-20260920`; tidigare ocommittat arbete är bevarat.
Underlag: `reports/coop-refresh-integration-20260922/RELEASE-COOP-REFRESH.md`.
Inkrementell patch jämför mot denna körnings säkerhetskopior, inte mot HEAD.

Ordinarie `run_daily_refresh.py`/`grocery_data daily-refresh` tar nu kommunens
förfallna källor genom befintlig collector/OWN och läser beständiga godkända
källreferenser vid varje efterföljande PriceUniverse-build. Kommunval, valfri
X:-tra-flagga, samtliga butiksstatusar, relativa snapshotreferenser med hash,
uppdateringstider och separata publicerings-/reloadkvitton sparas atomiskt under
`COOP_MUNICIPAL_OFFERS_ROOT` (standard bredvid grocery-databasen).
`docs/coop_refresh_integration.md` beskriver kontrakt och konfiguration.

Slutimage: `smako-coop-candidate:refresh-integration-20260922`,
`sha256:73371776b99a8b240435e2d575473d746bda5f694d1b3a6a485273be2ff12924`.
285 moduler hashverifierade. Appkod var inte monterad från utvecklarkatalog.
Privata beständiga serverdata: `/var/tmp/smako-coop-refresh-integration-20260922/data`.
Detta testunderlag innehåller även märkta felinjektioner och får inte kopieras
som produktionsstate.

493 fysiska Coop-poster behölls över basrebuild och omstart. Verklig Primat-
uppdatering, kontrollerat hämtfel, verklig återhämtning och X:-tra av/på
(493/502) verifierades. Slutkoden verifierade normal parser/collector för ett
uttryckligt muterat nollsvar: bara Värpinges 55 poster återkallades. Testad
framtida köpdag i Coop-provider gav noll Coop-avtal med giltig bas kvar;
observationer ändrades aldrig. Verklig återhämtning gav åter 493 poster.
Reloadfel gav separat väntestatus; efterföljande riktig reload lyckades.
Privat publicering/rollback, avvisad ogiltig artefakt och avvisad för gammal
rollback passerade.

Slutkodens efterföljande rebuild + riktiga 15/20-anrop: 536,27 kr,
50,288 s, HTTP 201, 332 passerande audits, identisk sparning/återläsning.
Max två inköpsställen, oförändrade 40/30/20-krav och samma receptpool.
Näringsreferensversion och valda näringskontroller är identiska med B2;
katalogens samlade facts_version skiljer sig mellan de nya insamlingarna.
Detta är ingen ny parad besparingsjämförelse. 202 unika regressioner,
Ruff och compileall passerade.

Redo för separat aktiveringsbeslut, inte aktiverat. Förberedd
`deploy/coop-runtime.override.yaml` har endast konfigurationskontrollerats.
Ny färskhetskontroll, förfallen basinsamling och kodkompatibelt giltigt
rollbackunderlag krävs vid faktisk aktivering. Kontrollens äldsta basobservation
är 2026-09-21 01:17:55Z; hårt stopp 2026-09-23 01:17:55Z. Rapportens byggtid
föryngrar inte detta. Se aktuella per-källa-tider i `decision-state.json`.
Ingen Windows-, aktiv scheduler- eller produktionsändring; väntande ICA-release,
Primat och användarval är bevarade. Malmö-/X:-tra-formatluckor hålls separata.

## Willys kommunstöd 2026-09-22, slutkontroll 2026-09-23

Fortsatt separat arbetskopia `municipality-coverage-20260920`, gren
`areas/municipality-audit-20260920`. Befintligt ocommittat ICA/Coop/X:-tra-arbete
bevarat. Ingen produktions-, Windows- eller aktiv schemaändring.

Willys har explicit kommunurval från hela officiella registret och SCB RegSO 2025,
samma kod för Lund 1281 och Malmö 1280. Alla 258 registerrader kvarstår: 257
namngivna butiker och okänd rad 2002. Lund 3 kommunbutiker varav 2 online,
Malmö 10 varav 4 online. Priserna är butiksknuten online_price, inte belagda
fysiska hyllpriser. Sju butiker saknar verifierad transport i denna väg.

Ny persistent relay `source-scope.json` och serverinställning
`WILLYS_MUNICIPAL_CONFIG` styr ordinarie import/byggare; ingen fast butikslista.
Självständig kommun-/sidvalidering i source artifact. OWN-matchning behåller
exakt butik, fysisk identitet och kanal även över adressorter; ett faktiskt
postnummerformatfel är rättat. Saknad godkänd butik stoppar nu publicering.
Oförändrad prisparser, medlemskap, 35h behovsstyrning och 36/48h-gränser.

Lund: 18 824 käll-/OWN-poster, 18 642 i PriceUniverse. Ordinarie privata
refresh/rebuild/publicering/reload, andra rebuild och omstart ger identisk
prispostsignatur; 493 Coop-poster bevaras, health/ready 200. Riktiga ursprungliga
Willys-observationer 21/9 23:31–23:59Z återanvända utan föryngring.
Malmö: ny faktisk insamling 22/9 16:18–17:11Z, 39 274 OWN-poster och 38 950
i OWN-only PriceUniverse. Samma import och produktionsbyggare efter omstart
ger identisk prispostsignatur. Ett fullständigt federerat Malmö-publicerings-
och reloadprov med aktuell komplett Primat-bas återstår; det har inte ersatts
med Lunds bas eller sökprojektion.

180 regressioner passerar, Ruff/compileall passerar. 276 paketerade Python-filer
hashjämförda utan avvikelse även efter återupptagandet. Två verkliga relästarter
utan förfallet arbete gör noll externa anrop. Explicit +49h-test spärrar gamla
Willys-kontexter. Ingen ny 15/20-jämförelse eller besparing påstås.

VIKTIGT vid fortsatt releasebeslut: 23/9 cirka 08:08 Stockholm är Willys-källorna
fortfarande under 36h, men en annan baskälla i gårdagens privata Lund-testbas
är nu över 48h och spärras (`degraded`, en utesluten kontext). Den gamla basen
är inte giltigt aktiverings-/rollbackunderlag utan förfallen uppdatering.
Nästa beräknade Willys-hämtning: Lund 23/9 12:31, Malmö 24/9 05:18 Stockholm;
ingen ny skarp körning installerad. Skarpt manifest ändrades över natten utanför
denna uppgifts privata tester; endast läskontroll utförd.

City Gross: befintlig full onlinekatalog/OWN/PriceUniverse finns redan;
kommunbevis och genererat storeNumber/siteId-urval återstår. Lidl: befintligt
offers_only-flöde och nationell bevisväg finns, men kommun-/regiongiltighet
måste knytas till faktiskt omfattade butiker och aktuella kampanjer.
Ingen ny bred kedjeinsamling eller parserombyggnad gjord.

Se `reports/willys-municipality-20260922/{README,COVERAGE,CHAIN-STATUS,VALIDATION,RELEASE}.md`,
`decision-current.json`, samtliga registerrader i `ALL-STORES.md`,
före-läget i `initial-state.json`/`backups` samt avgränsad patch och filhashar.
`deploy/willys-municipality.override.yaml` är förberedd, inte applicerad.
Väntande ICA-release och dess operatörssteg är fortsatt separata.

## 2026-09-23 – City Gross kommunstöd, separat kandidat utan aktivering

Ovanstående City Gross-lucka är nu implementerad i samma kommunfunktion:
officiella PageData/sites → SCB RegSO → exakt storeNumber/siteId → befintlig
onlineconnector → OWN → PriceUniverse. Lund 1281 ger verifierat noll; Malmö 1280
endast Hyllie 3211/site 169; positiv kontroll Staffanstorp 1230 ger 3229/site 11.
Stora Bernstorp lånas inte till Malmö. Samtliga 38 nationella registerrader
per kommun och okända/felorsaker sparas.

Verklig kataloginsamling gav 13 523 respektive 13 780 godkända OWN-rader,
0 produktkarantän. Slutparser v4 återspelar källorna utan föryngring eller nät.
Kampanjfält som tappades för ItemsTotal×1 bevaras; villkor som minsta köpbelopp
spärrar rabattavtalet. Separat källbelagt varukorgstak följer provenance till
checkout/audit. Offers-only kan kvalificeras ur faktiska partiella svar och
ersätter inte fortfarande giltig full LKG.

Kommunval/status är beständigt och ansluter till ordinarie daily-refresh,
behovsplan, builder, publicering och reload. Avstängt som standard.
Explicit befintligt OWN_SOURCES_ONLY respekteras även i daily-refresh;
standardens kompletta externa bas och färskhetsgrindar består.
Isolerade drift- och köpbevis, slutkodhashar samt nät-/replayavgränsning finns
i reports/citygross-municipality-20260923. Full federerad Malmö-publicering
med aktuell komplett Malmö-/Primat-bas återstår och ersätts inte av Lund.

Willys sju onlinebortval har konkret onlineStore=false: Lund Stortorget 2863;
Malmö Lindängen 2843, Lugnet 2851, Möllevången 2870, Söderkulla 2865,
Oxie Centrum 2879 och Rosengård 2352. Varje butik har separat verifierad
officiell reklambladslänk, men befintlig connector importerar inte bladen.
Avsaknad av katalog betyder inte avsaknad av erbjudanden. Willys kod, tester och tidigare
releaseunderlag behålls och hashkontrolleras i separat release-manifest.

Köpprovets explicita färska tomat passerar matcher/checkout/audit. Generellt
tomaturval kan även acceptera passata; detta kvarstående matcharfel är
redovisat, inte ombyggt här. Lidls nästa steg: samma officiella kommunurval
och belagd butiksgiltighet för aktuella erbjudanden i befintlig offers-only-väg.
Ingen produktion, Windows-/schemakonfiguration, bildanalys eller modell-API
aktiverad. Se separat RELEASE-CITYGROSS.md och docs/citygross_municipality.md.


## 2026-09-24: Willys/Lidl automatisk kvalificering och näring

Senaste verifierade delresultat: reports/offer-nutrition-20260924/README.md,
RELEASE.md och PACKAGE.json. Samma dokument: Willys automatiska varianter
16→22 och 46→56, total unik import fortfarande 24/64. Lidl senaste
29-sidorsrevision 14→23, nio nya livsmedelspriser. SLV-spårad g-näring
0→3/5/2 i jämförda dokument; ingen automatisk tillagad receptgaranti.
427 tester passerar. Isolerad drift, två rebuilds/omstart, not_due,
fel/återhämtning och samtliga 438 prisraders datumspärr verifierade.
Ingen produktion eller schemaändring. Hela målet är inte färdigt:
fler produkt-/kampanj- och deklarationsbindningar återstår, inklusive
tillgängliga tillverkarkällor. Historisk Lidl-fixture och full komplett
Malmö-publicering är fortsatt öppna. Bevara föregående releaser.

## 2026-09-24: större Willys/Lidl-hinder och officiella produktfakta

Senaste delresultat: `reports/offer-expansion-20260924/README.md`,
`RELEASE.md`, `PACKAGE.json`, `profile-summary.json` och `runtime-summary.json`.
Föregående offer-nutrition-underlag och alla kedjereleaser kvarstår.

Garant Majskorvar/Gyros har återanvändbar officiell deklarationsimport med
entydig full identitet och förpackning. Bevarad officiell katalog kan ge
fakta genom kontrollerad råpost/GTIN-bindning; inga priser flyttas mellan
butiker. Pågenlimpan/Pizzamjöl får användbar gramdeklaration, kokosmjölk
saknar fortfarande belagd ml→g-konvertering. Mango har SLV 574 per 100 g
ätbar del, opt-in, ingen antagen fruktvikt.

Fryst före/efter: Willys 77→87 unika priser (två nya exakta livsmedelsköp,
åtta kg-priser utan exakt paketplanering), Lidl 23→26 exakta livsmedelsköp.
Willys automatiska annonser 17→20 av 34 och 51→57 av 112; manuella varianter
2→2 respektive 8→7 efter deduplicering. Gyros automatisk bindning/namnbyte
är inget nytt pris. Unik gram-kompatibel näring Willys 6→10, Lidl 2→2.
Pågenlimpan har separat nytt receptprov. Kycklingvingar får exakt paketköp
men kan inte bli generella gram kycklingkött i recept.

453 riktade unika testfall passerar, Ruff/compileall passerar. Riktig
oförändrad 15/20 på samma kompletta bas och frysta klocka: VERIFIED,
535,25 kr före/efter, två butiker; slutkod verifierad. Privat faktisk
Coop 730400-hämtning: 11 309 produkter/825 anrop; inga produktionsskrivningar.
Basen var AGING, ingen STALE-kontext; får inte beskrivas som nyhämtad i sin helhet.

Driftprovet har publicering/reload, andra rebuild, omstart, fel/LKG och
återhämtning. Hela not_due-provet är PARTIAL: bevarad City Gross-bas var
förfallen enligt ordinarie 35h-gräns, Willys/Lidl hade inget förfallet arbete.
Full komplett Malmö-publicering, oberoende ogranskad utgåva och historisk
Lidl-fixturelucka är fortsatt öppna. Hela ursprungliga nämnaren kvarstår:
38 Willys variant-/intervallfall och 81 regionalt aktuella Lidl-livsmedel
har kvarstående hinder, utöver övriga dokumenterade grupper. Detta är
inte full täckning. Ingen produktion, Windows-/schemaändring eller modell-API.
