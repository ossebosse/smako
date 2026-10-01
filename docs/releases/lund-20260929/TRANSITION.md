# Lund: köövergång och begränsad återgång, 2026-10-01

**REDO FÖR SEPARAT AKTIVERINGSBESLUT**, med uttryckligen begränsad återgång
till autentiserad läsning av sparade planer. Ingen produktionsaktivering är gjord.

| Kontroll | Utfall |
| --- | --- |
| Obevakad livehämtning/leverans | PASS, bevarat bevis för exakt bdc9-konfiguration |
| Samordnat byte och bevarade köer | PASS; gammal blockerad kö hålls separat utan falsk publicering |
| Återgångsläsning och processomstart | PASS; sex planer identiska, 40 revisionsrader bevarade, fel ägare 403 |
| Omräkning/import i återgång | Säkert avstängt med 503/exit 3; inte omräkningsstöd |
| Liveartefaktens återleverans/not_due | PASS; en import, autentiska tider, inga nya prisanrop |
| Berörda regressioner | 168 PASS i ren klon; tidigare fem fel fortsatt PASS enligt tidigare bevis |
| Kvarstående teknisk spärr för detta begränsade alternativ | Ingen; aktuella aktiveringskontroller och tre produktionsbeslut återstår |

Arbetsgren `release/lund-relay-20260929`. Detta underlag ersätter de öppna
kö-/återgångspunkterna i den historiska OPERATIONS-rapporten. Slutstatus och
maskinläsbara prov finns i [TRANSITION-EVIDENCE.json](TRANSITION-EVIDENCE.json).
Inga produktionsbeslut, schemastarter, butikshämtningar eller remote-pushar
ingår i denna fortsättning. [ACTIVATION.md](ACTIVATION.md) är den enda aktuella
ordningen för ett senare godkänt byte.

## Implementerat och paketerat

- `07284b27c7640924a22745b9f3233648fc0c4140`: autentiserad återgångsläsare och
  köbevarande under befintliga lås, tester och driftmall.
- `a914043d9e6bf3ed5cec21232ea483d80c0ec91b`: bevara även oläsbara historiska
  artefaktbehållare utan att tillskriva dem kommun eller publiceringsstatus.
- `42478620aefd4e53699a6ce920f686c6e2986777`: korrekt produktionsfilnamn för
  planer, full privat releasekonfiguration och samma bild för samtliga jobb.
- **Slutlig runtime `08c137475d9ca96a6ef7673245a639c8c5c9e922`**: korrekt
  checkpointad SQLite-läsning på helt skrivskyddad volym. Icke-tom WAL ger
  kontrollerad vägran, så nya revisioner aldrig tyst hoppas över.

| Leverabel | SHA-256 |
| --- | --- |
| `.local/transition/packages-readonly/smako-server-08c137475d9c.zip` | `c20f8ad6ce316df121117c32cb44dc308a8d73011d097ec8799be095883b1e22` |
| `.local/transition/packages-readonly/smako-windows-relay-08c137475d9c.zip` | `399cd71f195538c08425afda938cb0b56c6046e150f67145a7a7285ad5bb61d2` |
| Slutlig server-/återgångsbild `smako-lund-transition:08c137475d9c` | `sha256:d8a166fa7ee162cd0570f9d8089ff800e00d9c949ac3c674e387c5fff1538dd7` |
| Rekommenderat liveprovat bdc9-relä-ZIP, oförändrat | `299ff34ecb7b5976e317afeef54719c9286d0ecd64c2807cee58533945de57d7` |

Slutpaketen har reproducerats från ren lokal klon med identiska bytehashar.
Slutbildens 621 runtimefiler matchar paketet; enda avsiktligt ej inkluderade
filen är env-exemplet. `pip check` och offline-Chromium passerar. Renderad
Compose binder app, migrate, scheduler, refresh-once och backup-once till samma
bild. App behåller read-only pris-/råvolymer; mottagaren har skrivbara volymer
och använder autentiserad reload över intern HTTP.

Det nya Windows-ZIP:et är **byggt, inte installerat eller S4U-liveprovat**.
Föreslaget driftpar är slutlig server plus oförändrat bdc9-relä, vars 624 filer
hashkontrolleras i varje replay. Ingen redan identifierad release har skrivits om.

## Sammanhängande isolerad sekvens

Testrot på servern: `/var/tmp/smako-repo-release-20260929/transition-verification`.
`old` är en kopia av det verkliga gamla parets data. `new` utgår från den
bevarade S4U-mottagaren. Inga produktionens volymer används. Livebevisets
ursprungliga lokala/serverdata är oförändrade. Containrar kör utan externt
nät; det sista paret använder ett separat internt Docker-nät. Reläets SSH
går till dessa testcontainrar. Ingen testklocka används.
De nya isolerade app-/receiver-/återgångstjänsterna stoppades efter proven;
data, köer, kvitton och samtliga tidigare paket finns kvar.

1. Faktisk gammal bild `54dde838…` återprovades med blockerad gammal artefakt:
   originalpolicyn gav `required_external_cache_unavailable`. Ingen falsk
   framgångskvittens skapades. Gamla paret stoppades före nästa skrivare.
2. `relay_transition` tog befintliga workflow/collection- och operationslås.
   Innehållsadresserad inventering bevarade **19 artefaktsökvägar, 17 unika
   artefakter och ett befintligt kvitto**. Samma inventeringshash efter omkörning
   och slutlig återgång: `6d283353f166870f1086fffcd4aacc4aa0ab82138cc3fd5d07a2ce5b1234f11b`.
   Original och kopior behålls; nya leveranser använder annan arbetsyta/inbox.
3. Ny kommunbunden liveartefakt återlevererades genom bdc9-reläets riktiga
   SSH-push och ordinarie mottagarimport. En uttrycklig felinjektion på kopian
   valde det tidigare autentiska 44 080-manifestet medan den validerade importen
   fanns kvar. Normal rebuild/publicering/reload återställde 44 066-underlaget.
   Det provade både återupptagning efter utebliven publicering och, i nästa
   steg, förlorat lokalt kvitto efter lyckad publicering.
4. Tre nya planer skapades via ordinarie HTTP: fri 15/20, uppskattad ICA-laxsida
   och öppet Hemköp-pizzaval. Samtliga gav 201. Planbasen förbereddes **innan**
   dessa skapades: alla 34 revisionsrader från livekopian verifierades byte-/
   fältidentiska i den senare kompletta 37-raders testdatabasen. Den tidigare
   34-radersfilen sparades separat. Därefter växte senaste databasen till 40;
   ingen äldre databas återställdes över nytillkomna planer.
5. Normal app stoppades. Senaste databas checkpointades med resultat `(0,0,0)`.
   Slutpaketets riktiga recovery-Compose kördes read-only utan prisrot på dess
   konfigurerade sökväg. Tre äldre och tre nya planer jämfördes med hela sparade
   request-/resultat-JSON, före och efter faktisk processomstart. Fel ägare
   gav 403. Nyplanering, ändring/omräkning och import/reload gav 503;
   source_cli och refresh gav exit 3. Ingen tyst omräkning görs.
6. Återgångstjänsten stoppades. Nya paret återstartades med samma senaste data.
   Alla sex planer lästes identiskt igen. Slutbilden provas även med separata
   app-/receiver-containrar, autentiserad intern reload och bdc9-SSH-leverans.

Det första verkliga read-only-provet avslöjade ett SQLite-WAL-problem som inte
syntes på skrivbar testdisk. Det rättades i slutcommiten och provades på nytt;
det misslyckade försöket räknas inte som PASS. Slutläsaren kräver stoppade
skrivare hela läsdriften och vägrar icke-tom WAL. Kontroll/byte av proxytrafik
är förberett, inte installerat eller utfört i produktion.

## Köer, kvitton och oförändrade observationer

| Tillstånd | Före → efter övergång/återgång |
| --- | --- |
| Gammalt bevarat kvitto | 1 → 1, oförändrat; ingen ny gammal framgång |
| Gamla artefaktsökvägar med kvittobevis | 1 → 1 |
| Mottagna gamla sökvägar utan aktuell belagd publicering/kvittens | 17 → 17, bevarade i gamla generationen |
| Oläsbar historisk behållare | 1 → 1, `unclassified_not_published`, originalhash bevarad |
| Ny autentisk artefakt | Samma hash, en import och bevarat lokalt kvitto |
| Sparade revisioner | 37 → 40 vid nyplanering; därefter 40 oförändrade |

Sökvägsantal inkluderar kopior: 19 sökvägar är 17 unika artefakter. Klassningen
`received_not_published` på historiska filer betyder att **aktuell** publicering
inte kan beläggas med manifest/kvittot; den påstår inte att filen aldrig har
publicerats historiskt. Den verkligt blockerade gamla artefakten är `05ab5b72…`,
med city-scope Lund och observation `2026-09-29T23:31:52.501849Z`. Den blir
inte en kommunartefakt och förblir synligt utan ny publiceringskvittens.

Ny liveartefakt: `5b1a2b6b01ba65338f224cdd6af432c8178f214b1612d5d54ec400ffe8f9362a`.
Import-ID: `293e153376ae45bbbf114c0cbb5790d3`, exakt **en** import. Alla 1 250
råfilshashar och deras observationer jämförs mot källmanifestet; 18 939
butiksproduktposter och autentiska tider behålls. Reläets schemaberäkning
utgår fortfarande från `2026-10-01T07:44:37.057437Z`, inte replaytid.
Återleverans efter förlorat kvitto gav `already_active`; efterföljande not_due
gav **0 prisanrop, 0 push, 0 aktiveringsanrop**. Detta är replay/idempotens,
inte en ny S4U-liveinsamling. Fullt ursprungligt [livebevis](S4U-LIVE-EVIDENCE.json)
och dess hashar lämnas oförändrade.

## Planläsning och begränsning

De fullständiga JSON-jämförelserna bevarar receptversion, mängder, köptermer,
kampanj- och källreferenser, pris-/näringsstatus, pant och öppna villkorade val.
Det öppna pizzavalet omvandlas inte till automatiskt godkänd receptingrediens.
Sex individuella resultathashar finns i bevisfilen. Databasens SHA före/efter
läsdrift och omstart är
`2bfcb7049620206561e2461236a9119923eec9622f4968edb9dd09089334a2d5`.

Återgången stöder **läsdrift med ägarkontroll**, inte nyplanering eller
omräkning. Kontrollerad 503/exit 3 är provad säker avstängning, inte fungerande
omräkningsstöd. Befintlig autentisering och hemligheter behålls. Full
planerings-UI är inte utlovad i detta läge; API-läsning är verifierad.
Den gamla produktionsbildens konstaterade fältförlust/500 försvinner inte och
bilden är därför borttagen som användbart återgångsmål. Primat-policy med
saknade baser är inte ett bevis för återställd full drift.

## Regressioner och beslutsgräns

Slutcommiten har **168 passerade fokustester i ren klon**: återgångsläsning,
WAL-vägran, köbevarande/lås, relä och konsumentplanering. Ruff/compileall,
reproducerade paket, bildhashar, offline-browserstart och verkliga Docker/HTTP-
prov redovisas separat. Inga nya frontendändringar gjordes.

Tidigare releasebevis återanvänds utan att räknas som nya körningar:
fem tidigare fel → 40/40 i riktat urval; 16 autentiska Lidl-prov PASS;
bdc9:s uppdelade rena Windows-svit 3 455 PASS; frontend 30 PASS, check/bygge
PASS; fyra browserflöden Chromium/WebKit PASS för formulär-JSON. Exakta
test-ID:n, tidigare infrastrukturfel och Linux-svitens begränsning står kvar i
[RESULTS.md](RESULTS.md). Ingen ny full svit eller full browser-E2E på
återgångs-UI påstås här.

Manifesten hålls isär: **42 491** för ursprungliga profilprov, **44 132** för
äldre drift-/återgångsprov, **44 080** historisk förkontroll/felinjektion,
**44 066** för liveartefaktens replay och de tre nya planerna här. Universe-ID
`19cd1da8…` är stabilt genom rebuild; aktiv manifestfil får nytt hash när
publiceringsmetadata uppdateras. Det föryngrar inte någon källobservation.

Slutlig separat mottagare publicerade/reloadade 10:59:14 UTC. Aktivt manifest
har SHA `52af66337280a939937bcc4f6df86cfaf1ef533a1079113906c9cba91471ba74`;
den förberedda artefakten `0894b8c9b2d63d47614d284f7db15e0435a89782f1c36845c30a9332848f513c`.
Alla **2 232** refererade råfiler kontrollerades, noll saknade/hashfel.
Vid 10:59:49 UTC var de fem obligatoriska kontexternas äldsta serverade
observationer 2,937–4,841 timmar gamla (FRESH). Manifestets separata,
konservativa `oldest_base_observed_at` är fortfarande
`2026-09-30T11:17:53.844785Z`, cirka 23,70 timmar gammalt. Det har inte
ersatts med rebuildtiden eller ignorerats för att få bättre färskhetsstatus.

Vid faktisk aktivering måste aktuella basobservationer, 36/48-timmarsgränser,
kampanjutgång, råfiler, kandidat/serving, bild-/pakethashar, lås, senaste köer,
planrevisioner, rättigheter/signering och slutlig privat transportkonfiguration
kontrolleras igen. En gammal friskhetsrapport eller ett gammalt startkvitto
är inte ett aktuellt godkännande. Produktionens bild och Windows-XML är
oförändrade; alla tre produktionsbeslut återstår.
