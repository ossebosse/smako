# Annonserade medlemspriser och Scan-utredning

Runtime `f00f5304e5449bd8417f3dab4fcb547e27135de7`, gren
`feature/member-prices-scan-20261010`. **Inte aktiverad, ingen push.**

## Genomfört

Nya publika och personliga beräkningar samt produktsökning tar med alla sex
stödda kedjors generella annonserade medlemsprogram. Samma kandidat-,
köpterms-, korg-, närings- och auditväg används; inget medlemspris tvingas in
om ett annat giltigt köp är bättre. Kampanjperioder, köpgrupper, köpgränser,
medgivande för uppskattad vikt, butik och kanal behålls.

`membership_price_policy=all_advertised` är ett prisantagande i den sparade
begäran och dess cacheidentitet. Användarens `memberships` och
`membership_programs` ändras inte till påhittade innehav. Personliga kuponger
aktiveras inte. Äldre requests/revisioner utan fältet behåller `selected` vid
läsning; fältet utelämnas då ur JSON så befintlig serialisering bevaras.
Publika nyberäkningsendpoints tillämpar den nya policyn även för äldre klienter.

Resultatet anger **Medlemskapsbaserat pris. Totalsumman kräver …** vid summan,
med namn på de medlemsprogram som faktiskt används av rader eller köpgrupper.
Enskilda rader har kvar medlemsvillkor. Formulären förklarar detta före start;
de gamla medlemsrutorna är dolda. Gemensam presentationsfunktion används av
publik och personlig vy. Versionsändrade JS-adresser undviker gammal klientkod.

Viktvaruändringen från 0e7 ingår. I hashbundet historiskt replay av 9 oktober-
underlaget, med 10 oktober 12:00 UTC som prisklocka, ger Satsumas 1 000 g behov
8 × cirka 140 g och **22,40 kr**, med Coop-medlemskravet synligt, trots tomt
medlemsval. Exakt inköpsläge stoppas fortfarande; användaren väljer uppskattad
vikt. Detta är inte en ny liveprisoffert eller en ny matematisk prismotor.

## Scan: orsaken är funnen, källrättningen återstår

65 kr/kg finns i vårt sparade råsvar från **Coop Värpinge Lund**, fysisk butik
3659, 9 oktober 13:30:40 UTC: Sverige/Scan, ca 1 kg, medlemspris, max 2 st.
Tre nya strukturerade fält (`buyAmount`, `claim`, `payAmount`, alla under
`priceInformation`) avvisades av schemakontrollen. Den strukturerade vägen
stoppade därefter publicering; sidtexten används inte som reservpris.

Detta preciserar den tidigare utredningen. Online Syds separata råsvar anger
105 kr/kg utan kampanj. Det är inte korrekt att flytta butikens 65-pris till
onlineprodukten. Exakt råfil, hash, tid, kodväg, reproduktion och kvarstående
fältvärdeslucka finns i [SCAN.md](SCAN.md). Medlemsändringen löser inte denna
källspärr och paketet ändrar ingen källprocess.

## Verifiering

- 145 berörda tester PASS mot 882-imagen, återanvända för oförändrad backend i slutimagen: 143 i huvudkörningen, två
  asynkrona jobbtester efter att saknad pytest-plugin lagts till testmiljön.
  Första körningens två miljöfel finns kvar i `.local/member-scan-20261010/`.
- Tester omfattar alla sex medlemsprogram, cacheisolering, äldre JSON,
  personliga kupongspärrar, gemensamma recept-/extrabehov, heltalsflerköp,
  viktpris, datum, oberoende audit och befintliga medlemsregressioner.
- Strikta mobila Chromium/WebKit-knappflöden PASS mot imagen utan kodmount:
  tomt medlemsval, jämförelse 20 kr/kg, korg 22,40 kr, synlig medlemsmärkning,
  dubbelklick med ett start-POST, audit, GET, omladdning, omräkning till revision
  2, oförändrad revision 1, ägare 403 och bevarad revision vid misslyckat byte
  till exakt inköp. Inga oväntade sid-/nät-/serverfel i dessa två slutprov.
- Första Chromium-försöket väntade inte på att initialiseringen aktiverade
  sökknappen; testet tryckte Enter medan den var inaktiverad. Det kvarstår
  som FAIL. Testverktygets väntan rättades; appkoden ändrades inte för omprovet.
- 14 runtimefiler och sex serverade HTML/JS-filer SHA-verifierade. Ruff,
  compileall och fyra JS-syntaxkontroller passerade.
- Endast automatiserade lokala webbläsare, ingen fysisk iPhone eller liveplan.
  Två CPU, 3 GiB, en tung planner åt gången, isolerad lagring på D:.

### Publikt menyprov och avgränsad återhämtningsrättning

De två första publika försöken använde testmiljöns tomma källdatabas: det
första nådde tidsgränsen 240 s, det andra stoppades med 422 i produktkvalificering.
Det var inte tillräckligt underlag för att kvalificera recept. Därefter exporterades
endast de redan sparade offentliga källtabellerna och råfilerna för prisartefakten,
läsande och hashkontrollerat. Ingen ny prisinsamling, inga privata produktionsplaner.
2 232 råfiler, 116 294 377 byte; komprimerat 21 743 690 byte. Samma prisklocka.

Ett startförsök före tillgänglig app gav ERR_EMPTY_RESPONSE och en bevarad
`crypto.randomUUID`-pageerror. Följande försök väntade på faktisk readiness.
Två fullständiga försök med rätt fakta skapade och sparade riktiga menyer
(198,203 respektive 165,109 s), men är fortfarande FAIL: efter omladdning
under jobbet tog `/ready` längre än klientens 15 s och lämnade startknappen
spärrad även efter levererat resultat. GET-felet är separat från jobbets framgång.
Ingen orsak till serverns långa readiness-svar påstås vara bevisad här.

Runtime f00f530 gör en ny begränsad, auktoritativ readiness-GET när ett resultat
har lästs och den tidigare kontrollen misslyckats. Det startar aldrig om jobbet.
Generation och AbortController hindrar ett gammalt svar/fel från att skriva över
nyare status. Ett verkligt aktuellt 503 blockerar fortfarande ny planering.
Regressionen kör de faktiska JS-funktionerna: FAIL före, PASS efter för återhämtning,
sent svar, sent avvisande, ingen extra generering och fortsatt 503-spärr.
Det är kontrollerad transportinjektion, inte ett nytt fullständigt menyprov.

### Slutligt publikt prov – PASS med bevarade transporthändelser

Faktisk paketerad f00-image, Chromium mobil, tre middagar × två portioner,
Billigast, indiskt/italienskt/mexikanskt tillåtna, minst 18 g protein, tomt
medlemsval, uppskattat köp och separat näringsmedgivande. En tung start och ett
jobb, omladdning under jobbet, tre fullständiga recept, inköpslista, audit,
identisk sparad återläsning och främmande ägare nekad. Inga pageerrors.
190,594 s till slutfört jobb, 190,813 s klick till renderat resultat i detta
enskilda replayprov. Detta är ingen prestandakvalificering eller förbättringsclaim.

Slutkorgen är 355,34 kr, använd mängd 140,29 kr, två butiker. Denna valda meny
använder ingen medlemsrabatt; medlemskorgen prövades separat med Satsumas.
Fulla recept, mängder, produkter, korg, näring, variation, köp-/allergenstatus
och audit matchar före den rena readiness-rättningen, inte bara totalsumman.

Två `/ready`-GET fick `net::ERR_ABORTED` och finns kvar i rårapporten. Det första
inträffade vid kontrollen efter omladdning under jobbet; efter resultatleverans
fick klienten ett nytt godkänt readiness-svar och knappen fungerade. Ytterligare
ett avbrott registrerades efter leverans. Den andra händelsens exakta abortorsak
är inte bevisad genom dessa browserloggar. Provets PASS betyder fungerande
återhämtning och strikta sidfelskontroller, **inte att inga nätfel inträffade**.
Inga fellyssnare eller breda felundantag ändrades. De två föregående UI-spärrarna
är fortfarande FAIL. Personliga Chromium/WebKit-bevis från 882 återanvänds
för hashidentiska personliga/shared filer och backend; de räknas inte som nykörda.

## Paket och drift

Paket, image, filhashar och provutfall finns i [EVIDENCE.json](EVIDENCE.json).
[ACTIVATION.md](ACTIVATION.md) gäller bara denna appkandidat och kräver ett
separat aktiveringsbeslut med aktuella förkontroller. Beta var vid läsande
kontroll kvar på `return-session-205cd8ca0f31`; källor, relä, scheman,
prispublicering och produktionsdata har inte ändrats.
