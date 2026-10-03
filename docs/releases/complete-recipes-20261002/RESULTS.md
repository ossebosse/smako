# Nästa receptlager – verifieringsunderlag

Detta underlag uppdateras under slutproven. Kandidaten är inte
produktionsaktiverad och ingen Git-push ingår.

## Leveransens användarflöde

Det publika menyflödet och den personliga planeringen har ett valbart läge
för genomarbetade middagar. Valen omfattar Matkök och inspiration, eget
ingrediensintervall eller förval, uppskattad högsta tillagningstid, kost,
uteslutningar, fisk, valfritt proteinmål och tillåtna anpassningar. De
befintliga optimeringsmålen Billigast, Balanserad och Varierad är kvar.
Portioner, medlemskap, butiks-/kanalval, butikstak, skafferi och exakt eller
uppskattat köp följer samma ordinarie planeringskedja.

Receptkort visar komponenter, mängder, numrerade beroendeordnade steg,
utrustning, uppskattad tid och separata kvalitetsstatusar. Desktop använder
två kolumner för ingredienser och metod; mobil använder en kolumn. Inköpslistan
skiljer veckans hela förpackningar från receptets använda mängder. Ett
automatiskt byte väljer en annan grundrätt. Byte och uttrycklig omräkning
skapar nya revisioner. Återkoppling kopplas till den exakta receptversionen.

Ingen betald modellgenerering krävs vid menyknappen. Innehållet är strukturerat
och versionsbundet. Flaggan `COMPLETE_RECIPES_ENABLED` är av som standard;
både server och gränssnitt kontrollerar den. Äldre anrop utan de nya fälten
behåller sitt tidigare läge.

## Pris- och näringsunderlag

Autentiskt publicerat PriceUniverse fryst **2026-10-02 15:09:36 UTC**:

- Universe: `price-universe:8ecd0659a7e69b8eb007e383ae4f9686a3d1a4f24570b0dd9b72c9c875653bad`.
- Artefakt SHA-256: `1335cbb6680237f5826912f19a1d5c348476089ec3091126cb073c4cc5a643e0`.
- 44 185 produkter, fyra katalogsnapshots och 2 232 hashverifierade råunderlag.
- Kopian innehåller offentligt pris-/produktunderlag; testmiljön har egen
  ny sessions- och planlagring. Privat produktionsdata kopierades inte.

Replaypriserna är historiska och får inte användas som nya prisutfästelser.
Vanliga produkt-, mängd-, närings-, inköps- och auditvägar används utan
produktpatchar eller tvingade kampanjval. Produktionsdriftkontrollen hålls
separat från replayklockan. Inga insamlingar, scheman, reläer eller
färskhetsgränser ändras.

Kompletterande referenser hämtades från Livsmedelsverkets officiella API och
exakta tillverkar-/leverantörsdeklarationer. Importvägen sparar källa, version,
hämtningstid och matchningsunderlag. Generiska referenser och varm beredning
kräver det befintliga uttryckliga opt-in-valet och märks som uppskattningar.
Uppskattat köp aktiverar inte automatiskt generisk näring. Okänd mängdbasis,
motstridiga deklarationer och saknad allergendokumentation förblir egna stopp.

## Bibliotek och verklig kvalificering

48 distinkta grundrätter och 56 godkända variationer ger 104 konkreta
receptkandidater. 23 grundrätter är vegetariska och sex innehåller fisk.
Samtliga har 12–14 räknade ingredienser och uppskattad tid 35–50 minuter
för två personer. Salt, peppar och vatten särredovisas; skafferiet ändrar
inköpsbehovet men inte receptets ingrediensantal.

Slutkörningen på `28bca2d` gav följande resultat genom normal produkt-,
mängd-, närings-, korg- och auditkontroll, med uttryckligt medgivande till
uppskattad näring och uppskattade köp:

| Matkök | Grundrätter | Godkända variationer | Kvalificerade konkreta kandidater | Grundrätter med fungerande variant | Fungerande originalvariant |
|---|---:|---:|---:|---:|---:|
| Grekiskt | 8 | 8 | 16/16 | 8/8 | 8/8 |
| Italienskt | 8 | 8 | 14/16 | 7/8 | 7/8 |
| Mexikanskt | 8 | 12 | 16/20 | 8/8 | 6/8 |
| Indiskt | 8 | 8 | 16/16 | 8/8 | 8/8 |
| Thailändskt | 8 | 8 | 16/16 | 8/8 | 8/8 |
| Svenskt | 8 | 12 | 16/20 | 8/8 | 6/8 |
| Totalt | 48 | 56 | 94/104 | 47/48 | 43/48 |

Piccatans två varianter stoppas först av kaprisens käll-/mängdunderlag.
Mexikansk linschilis original använder kidneybönor med otillräckligt underlag;
dess uttryckligt godkända vita bönvariation fungerar. Majssoppans, pannbiffens
och ärtsoppans original saknar näring på rätt mängdbasis för mjölk. Deras
granskade crème-fraîche- respektive vattenpanadvariationer fungerar. Dessa
stopp rapporteras som datahinder, inte som bevis för för lågt protein.

Olivrätterna kvalificerar med en faktiskt prissatt, snävt matchad Zeta-produkt
och tillämplig generisk SLV-referens 402. Motstridig Fontana-deklaration är
fortsatt spärrad. Referensen gäller inte godtyckliga gröna, fyllda eller
smaksatta oliver och ersätter inte allergendokumentation.

Aktuell biblioteksutgåva är 1.4.0, innehållshash
`1c623aa7e4a8e8f9cde292807198c59d6f191f0dd3030462a254893995e7e90c`.
De konkreta objekten har 82 versioner 1.4.0, 12 versioner 1.3.0 och tio
versioner 1.1.0; oförändrat innehåll får inte en falsk ny receptversion.
Tidigare utgåvor ligger kvar för sparade planer. Innehållsgranskning,
maskinell validering och faktisk provlagning är separata: **ingen fysisk
provlagning har utförts**. Smak och verklig tillagningstid är därför inte
uppmätta. Se de versionsbundna granskningsfilerna för utgåva 1.3.0 och 1.4.0.

## Jämförbar prestanda för det befintliga publika flödet

Samma frysta underlag, två CPU, 3 GiB minnesgräns, fem middagar för två,
Balanserad, exakt köp och högst tre inköpsställen. Samma fem recept och
**168,55 kr** i båda versionerna. Inget annat acceptansprov kördes samtidigt
med den slutliga mätningen.

| Mått | Baseline | Kandidat | Förändring |
|---|---:|---:|---:|
| Kall generering | 328,424 s | 163,313 s | −50,27 % |
| Varm generering | 2,166 s | 2,179 s | i praktiken oförändrad |
| CPU, kall | 328,147 s | 163,171 s | −50,27 % |
| Högsta RSS | 1 281 328 KiB | 1 195 204 KiB | −6,72 % |
| Inläsning av fryst artefakt, separat | 14,584 s | 14,321 s | redovisas utanför generering |

Optimeringen återanvänder ekvivalenta delmängders prisberäkningar och vinnande
butiksofferter i den befintliga korgmotorn. Semantik, hela paket, kampanjvillkor
och audit sänktes inte. Veckosökningen minskade från 319,634 till 154,453 s.
Spann överlappar och får inte summeras som oberoende delsteg.

## Det nya lägets uppmätta svarstid

Samma frysta underlag och 2 CPU/3 GiB, fem middagar för två personer,
grekiskt/mexikanskt, 10–15 ingredienser, högst 40 minuter, minst 40 g protein,
Billigast, uppskattade köp och uttryckliga näringsuppskattningar:

| Mått | Kall | Varm |
|---|---:|---:|
| Ny fullständig beräkning | 160,708 s | 152,447 s |
| CPU | 160,569 s | 152,312 s |
| Processens högsta RSS hittills | 1 355 232 KiB | 1 557 644 KiB |
| Inköp | 738,17 kr | 738,17 kr |

Varmt betyder här en ny beräkning i samma process, inte återanvändning av ett
redan färdigt jobb. Faktaberedningen återanvänds men veckosökningen kostar
fortfarande tid. Återanslutning eller dubbelklick återanvänder samma ägarspecifika
jobb och ska inte räknas som en snabb ny sökning. Denna mätning avser
`cfcc3bb` med innehåll 1.3.0; efterföljande presentation-, integritets- och
replaystartändringar redovisas separat.

Den uppmätta menyn innehöll majs-/bönsoppa med ostquesadilla, vit bön- och
linschili, kycklingbowl, citronkyckling med spenatris och spenatris med
kikärtor/feta. Protein per portion var 40,172 / 43,5325 / 52,4545 / 55,489 /
41,515 g; jämförelsen gjordes före avrundning. Näringsstatus är **ESTIMATED**,
inte en verifierad märkesdeklaration för hela den färdiglagade portionen.

Inköpsbeloppet var 738,17 kr och den beräknade kostnadsandelen för använda
mängder 444,93 kr. Ett faktiskt samordnat exempel är 100 + 130 + 130 + 110 =
470 g ris i fyra rätter: motorn köpte **en 1 kg Långkornigt Ris för 21,95 kr
på Hemköp Lund Brunnshög**, med 530 g planerad rest. Den köpte inte en ny
kiloförpackning per recept. Citronjuice 36 + 30 = 66 ml delade en 200 ml
förpackning för 8,99 kr från Coop Online Syd. Detta är faktiska valda
förpackningar och mängder; ingen hypotetisk optimal jämförelseplan används
för att tillskriva ytterligare besparing.

## Sju kompletta slutmenyer

[MENUS.md](MENUS.md) visar samtliga rätter, näringsvärden och varje vald
inköpsrad. [evidence.json](evidence.json) binder dem till källor, faktiska
mängder och receptversioner. Alla sju använder fem middagar för två personer,
10–15 ingredienser, högst två inköpsställen och målet Balanserad. Det blandade
provet kräver dessutom högst 40 minuter och minst 40 g protein; de sex fria
köksproven har inget protein- eller tidskrav utöver receptens angivna tider.

| Matkök | Inköpsbelopp | Beräknad kostnad för använd mängd |
|---|---:|---:|
| Grekiskt | 682,23 kr | 418,77 kr |
| Italienskt | 647,98 kr | 359,83 kr |
| Mexikanskt | 673,87 kr | 390,82 kr |
| Indiskt | 628,95 kr | 333,50 kr |
| Thailändskt | 638,99 kr | 371,48 kr |
| Svenskt | 730,09 kr | 355,12 kr |
| Grekiskt/mexikanskt, 40 g/40 min | 738,17 kr | 444,93 kr |

Den grekiska menyn valde faktiskt Coop Online Syds kycklinglårfilé för
46,90 kr, kampanj 27 september–4 oktober. Den mexikanska valde två fasta
tofu för 9,90 kr styck på Willys Lund, kampanj till 11 oktober. Ingen
kampanjprodukt tvingades in. Det svenska veckoinköpet köpte tre 200 g tofu:
två för 22 kr plus en till känt ordinarie pris 13,20 kr, totalt 35,20 kr.
Det visar ett faktiskt flerköp med korrekt prissatt överskjutande paket.

Det blandade provets gröna paprika på Hemköp Lund Brunnshög är ett
**uppskattat köp**: 200 g vid 58,95 kr/kg, uppskattat belopp 11,79 kr.
Den osäkerheten ligger kvar i korgens `VERIFIED_WITH_ESTIMATES`; den är
inte en separat extravara och inte en exakt viktgaranti. Näringsstatus
redovisas oberoende av köpstatus. Planerade rester dras inte av från
inköpsbeloppet och bokförs inte automatiskt i skafferiet.

## Verkliga browserflöden

[UI-ACCEPTANCE.json](UI-ACCEPTANCE.json) innehåller sanerad bevisning för
Chromium desktop/publikt, WebKit mobil/personligt, Chromium mobil/publikt
och WebKit desktop/personligt. Alla fyra genererade riktiga planer med
serverbuild `recipe-candidate-26ecd5d3-fe953617`, bytte till en annan grundrätt,
räknade uttryckligen om inköpen och skapade revision 1–3. Inga tidigare
revisioner skrevs över. Annan sessionsägare nekades åtkomst till jobb och
planer. Omladdning och ett avsiktligt nätavbrott återanslöt till samma jobb.

Generering tog 151,016 / 142,079 / 99,344 / 142,500 sekunder. Längsta
statusanropet var 1,767 sekunder; inget långt blockerande genereringsanrop
återinfördes. Efter kontrollerad omstart med flaggan av kunde samtliga tre
revisioner i sista fallet läsas med identiska innehållshashar. Nya receptval
var dolda. DOM och faktisk layout kontrollerades; fysisk iPhone har inte
provats.

Återkopplingens fyra fält sparades och kontrollerades mot rätt revision,
receptindex, version och innehållshash i testlagringen. Värdena var syntetisk
acceptansinmatning och utgör **inte provlagning eller verkligt smakbetyg**.
Senare redskapsmetadata 1.4.0 och budgetpresentation verifierades separat
med innehållsprov, 49 riktade tester och åtta browserkontrakt mot integrerad
frontend. De fyra autentiska fullflödena påstås inte vara omkörda på 1.4.0.

## Separat aktuell driftkontroll

2026-10-03 06:08:37 UTC, skrivskyddad kontroll: produktionens appbild var
`sha256:80e8ba59c9b04c8bff668062da2bf1937eae236881472449e2a0180f42387180`,
build `74c9077001b3084317f36630fd38ce48e4663473`. Readiness, databas och
planlagring rapporterade `ready`/`ok`. Den nya funktionen har inte aktiverats
där. Ingen insamling startades av kontrollen.

## Genomförd bred regression

Den nätspärrade ordinarie sviten på runtime `38ee1aa` passerade
**3 694 tester, 0 fel, 0 överhoppade**, på 2 059,201 sekunder. Inga externa
nätförsök eller läsningar av spärrade äldre källkopior registrerades.
[TESTS.json](TESTS.json) binder resultatet till rårapportens hash.
Ett upptäckt bakåtkompatibilitetsfel är rättat: okända nya smakkomponenter
utelämnas ur äldre numeriska kvalitetsrapporter, medan faktiskt nollvärde
behålls. Okänt konverteras alltså inte till noll. Efterföljande begränsade
ändringar provas separat med berörda regressions- och acceptansprov.
Ruff på samtliga ändrade Python-filer, compileall och pip check är godkända.

Slutresultaten för innehåll, fria menyer, fyra browserkombinationer, privata
revisioner, omstart, skafferi och samtidiga användare läggs till efter att de
faktiska körningarna är avslutade. Fysisk provlagning och fysisk iPhone-testning
har inte utförts.

Aktiverings- och återgångsvägen finns i [ACTIVATION.md](ACTIVATION.md).

## Versionsbunden kandidat

Runtime-commit: **`38ee1aa5ecbc64045801a4f40f9c0302ed0e4a09`**.
Dokumentations- och acceptansskriptcommits efter den ändrar inte paketets
runtimefiler. Serverpaket: `smako-server-38ee1aa5ecbc.zip`, 2 732 614 byte,
SHA-256 `6764c69429f132360431df436de9ce7338e162a4496d1db090091fda1d2a2143`.
Det finns lokalt under `.local/releases/complete-recipes-20261002/`.
Paketmanifest och verifiering finns i [release.json](release.json) och
[image-verification-38ee1aa5ecbc.json](image-verification-38ee1aa5ecbc.json).

Byggd Linux/amd64-image:
`sha256:65670569e3d142e9a58e823a237869a845f3f544b2292880f119e231f0df25e4`,
tagg `smako-complete-recipes-candidate:38ee1aa5ecbc`. 644 runtimefiler
matchar paketmanifestet, inga avvikelser. `pip check` och Chromium-start
som bildens ordinarie appanvändare passerade utan nätverk. Det enda
avsiktligt uteblivna exemplet är `deploy/.env.production.example`.
Paketbyggaren producerar också ett reläarkiv; det ska inte installeras i
denna app-only-leverans. Befintligt Windows-relä och scheduler är orörda.
