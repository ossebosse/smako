# Fem valda matkök: prestanda och receptvisning, 2026-10-04

Testad app-only-kandidat: `b89fadb96c4edc4576cb4daae6c5d80e553ad8ca`.
Produktionsaktivering ingår inte. Betasidan kör fortsatt
`complete-recipes-17a9c1330dcc`, med receptflaggan på.

## Reproduktion och oförändrat resultat

En unik sparad revision matchade observationen: fem middagar för fyra,
butikstak tre och 768,04 kr. Den behöriga läsningen ändrade inte planen.
Valen var grekiskt, italienskt, mexikanskt, indiskt och thailändskt;
Balanserad, 10–15 ingredienser, inget tidstak, 30 g protein per portion,
godkända variationer, fisk tillåten, uppskattade köp och separat medgivande
till uppskattad näring, samtliga fem medlemskap. Inga skafferiallokeringar.
[Sanerad faktisk begäran](REQUEST.json) bevarar resterande inställningar.

Fem **valda** matkök är det tillåtna urvalet, inte ett krav på en rätt från
varje kök. Den oförändrade menyn innehåller indiska och mexikanska rätter.
[Reproducerad meny](REPRODUCED-MENU.json) redovisar recept/versioner,
mängder, näring, 27 samordnade inköpsrader och audit. 768,04 kr är ett
historiskt resultat, aldrig en hårdkodad gräns eller aktuell prisutfästelse.

Originalets hela PriceUniverse återfanns: `price-universe:b8a677e3e46828048a1946edbeaeb75649cd35f208da826536561fcd4cc90b6c`,
SHA-256 `f82d66103e830b82b7d919fe847fd5b3ef85c5e323e0a2133c338f064dfb8768`.
Alla 2 233 frysta råfiler hashverifierades. Endast publicerade källtabeller
kopierades, inga ägar-/konto-/plan-/skafferitabeller. Faktaversionen är
identisk med originalets. Replay använder revisionens sparade tid
2026-10-04 07:19:16 UTC; den exakta klicktiden finns inte lagrad.
Recept, korg, ingredienser, slots, behov, rester, näringsresultat och audit
är identiska med den autentiska sparade planen.

Samtliga tolv fulla före-/efterresultat är semantiskt identiska.
Jämförelsen undantar endast uppmätta tidsfält och ordningen i mängden
`membership_programs_used` (processberoende set-ordning, även före ändringen).
Produktval, kampanjvillkor, mängder, förpackningar, näring, audit och
beslutsunderlag jämfördes, inte bara totalsumman. Fulla resultat och profiler
ligger utanför Git i `.local/five-cuisine-20261004` och det markerade
serverområdet `/var/tmp/smako-five-cuisine-20261004`.

## Mätningar utan tung profilering

Samma Linuxserver, identisk Python/installerade beroenden, underlag, sökbudget och gräns **2 CPU/3 GiB**
användes före och efter. Aktiv produktion saknar containergränser på en
värd med 8 CPU och cirka 15,6 GiB; proven använder alltså en uttrycklig,
snävare resursgräns, inte fler resurser. Varje varm körning skapar en ny
PersonalPlanner och gör en ny beräkning; inget färdigt menyresultat hämtas.
Kall avser en ny process, inte tömd operativsystems- eller diskcache.

| Mått (sekunder) | Före, alla tre prov | Efter, alla tre prov | Median före → efter |
| --- | --- | --- | --- |
| Kall ny process, inklusive import och underlagsberedning till serialiserat resultat | 204,251 / 206,202 / 204,818 | 87,278 / 83,602 / 82,033 | 204,818 → 83,602 |
| Första beräkning efter underlagsinläsning | 188,914 / 190,395 / 188,952 | 70,880 / 67,057 / 66,007 | 188,952 → 67,057 |
| Varm process, **ny beräkning** | 180,505 / 179,061 / 179,210 | 60,650 / 58,874 / 58,154 | 179,210 → 58,874 |

Kall process minskar cirka 59 %, varm nyberäkning cirka 67 %. Spridningen
min–max för varm nyberäkning är 179,061–180,505 före och 58,154–60,650 efter.
Ingen statistisk p95 sluts ut från tre prov. CPU-tider följer väggtiderna
(cirka en CPU). Högsta observerade RSS: 1 951 436 KiB före och 1 940 132 KiB
efter. [Alla tider, CPU, minne och hashar](PERFORMANCE-FINAL.json).

**60-sekundersmålet är inte nått från klick till komplett visad meny.**
Slutimagen gav 72,313 s i Chromium och 75,000 s i WebKit, utan kö,
med ny beräkning och omladdning under väntan. Två av tre rena varma
backendprov låg under 60 s, ett över. Kall process ligger tydligt över.
Ingen färdig resultathämtning räknas som nygenerering.

Slutproven ovan kördes på paketimagen utan monterad utvecklingskod.
[Utvecklingsmätningarna](PERFORMANCE.json) bevaras separat; rapporten väljer
inte deras något bättre tider. [Beroendejämförelse](DEPENDENCIES.json).
CPU, min/max och spridning för varje fas finns i slutmätningens JSON.

## Tre samtidiga användare

En aktiv tung beräkning, samma kögräns och 2 CPU/3 GiB före/efter.
[Alla kö-, CPU-, minnes-, sparnings- och HTTP-mått](HTTP-PERFORMANCE.json).
Raderna nedan följer slutförandeordning, inte någon beständig användaridentitet.

| Prov | Kö före → efter | Beräkning före → efter | Hela väntan före → efter |
| --- | --- | --- | --- |
| 1 | 0,000 → 0,000 s | 200,755 → 70,515 s | 202,884 → 74,280 s |
| 2 | 200,870 → 70,658 s | 189,161 → 59,904 s | 393,812 → 133,708 s |
| 3 | 390,221 → 131,506 s | 189,517 → 60,204 s | 582,739 → 194,101 s |

Separat hämtning av redan klart resultat tog 1,15–1,42 s före och 2,20–2,85 s
på slutimagen under detta belastningsprov. Längsta väntande statusanrop var
1,78 respektive 2,37 s; kortare polling har inte använts som förbättring.
Högsta process-RSS var 2 017 592 respektive 2 011 720 KiB. Sparning tog
cirka 0,09 s. Dubbelstart gav samma jobb, främmande jobb gav 404 och främmande
plan gav 403 för samtliga tre ägare. Alla fick oförändrad korg på 768,04 kr.

## Uppmätta flaskhalsar och ändringar

Föreprofilen hade cirka 500 miljoner funktionsanrop. Veckosökningen gjorde
2 075 korgberäkningar och miljontals upprepade val mellan samma produkter.
Det personliga flödet skickade nya listor och missade motorns befintliga
cache för oförändrade kandidatuppsättningar. Näringscachen tömdes helt när
den nådde sitt tak, vilket orsakade återkommande kvalificering av samma data.

- Exakt ordnade, begäranslokala kandidattupler återanvänds i samma korgmotor.
- Näringsbevis får begränsad LRU-lagring; identiska kvalificerade kandidatlistor
  och normaliserade receptbehov återanvänds inom samma planner.
- Butiker utan ett enda kvalificerat produktalternativ för just korgen tas
  bort före kombinationsuppräkning. Inga produkter eller köpbara alternativ
  försvinner; bara identiska eller ofullständiga butikskombinationer undviks.
- Butikskombinationer återanvänds, och tomma trace-anrop undviks för produkter
  som den befintliga avgränsade spårningen inte lagrar.

Nygenereringens sökordning för möjliga lösningar, veckobudget, antal maträttsalternativ och
samtliga slutkontroller är bevarade. Efterprofilen har cirka 120 miljoner
funktionsanrop. Båda profilerna gör lika många korgberäkningar och audits.
Profileringens överlappande spann summeras inte som oberoende tider.
Nästa större kostnader är paketberäkning (cirka 19–21 s), audit (11–12 s),
faktaberedning (14–17 s kall/6 s varm) och initial underlagsinläsning (14–15 s).

Nya cacher ägs av en planner och försvinner med begäran. De delar inte
skafferi, planer, ägare eller användarval. Receptnycklar omfattar exakta
mängder, innehåll, version och metod. Kandidater är kvalificerade mot samma
begärans prisunderlag, köpdatum, medlemskap, butiker och köp-/näringsval.
Inga observationstider, färskhetsgränser eller externa fakta ändras.

## Bytesfel funnet i slutprovet

Första knapp-provet genererade och visade exakt den ursprungliga menyn på
62,703 s men stoppade vid byte av första rätten. Samma stopp reproducerades
i aktiva 17a9c1330dcc-imagen på identiskt underlag: åtta billiga prefix tog
hela sökbredden och alla föll senare mot redan låsta rätter. Detta bevisar
inte att ett byte är omöjligt.

Slutcommiten prövar en ersättare mot den redan kända, oföränderliga resten av
menyn innan prefixet kan ta plats i sökningen. Bara bevisat oförenliga
slutföranden avvisas tidigare. Sökbredden är fortfarande åtta; prisberäkning,
skafferiallokering och slutkontroller sker i ursprunglig slotordning.
Nygenerering är orörd. Denna integrationsrättning skiljs från de rena
prestandaändringarna och ändrar avsiktligt utfallet för det tidigare stoppade bytet.

## Bredare verkliga HTTP-prov

[Samtliga regressioner](REGRESSIONS.json) använder vanliga jobb-/planvägar och
samma autentiska frysta underlag. Tolv positiva fall gav komplett plan och
återläsning med ägarskydd; tre negativa stoppade med oförändrade krav.
Det breda Varierad-fallet gick från 345,153 till 100,929 s, med identisk
**hel plan** förutom build-ID och uppmätta tider; 587,96 kr historiskt.
Det är ett före-/efterpar, ingen statistisk säkerhetsuppskattning.

Befintliga 15/20-profiler (15 tillfällen, 20 portioner) passerade både exakt
och uppskattat, med oförändrade 40/30/20-krav. Samma profil med nya kompletta
middagar passerade. Äldre publikt flöde passerade på 157,426 s. Separata
prover täcker ett, flera och alla tillåtna kök, Billigast/Balanserad/Varierad,
vegetariskt, ingrediensintervall, medlemskap och faktiskt angivet skafferi.
Allergenkravet stoppade på saknad fullständig källinformation; det försvagades
inte. För kort tid och butik utanför underlaget stoppade också uttryckligen.

Slutimagen passerade det tidigare stoppade bytet i båda webbläsarna:
första rätten blev spenat- och kesofylld pastagratäng, övriga fyra behölls
exakt. Ny korg 831,09 kr, tre butiker inom valt tak, audit godkänd och
alla proteinmål uppfyllda. Detta är ett uttryckligen valt receptbyte,
inte ett dyrare resultat för samma nygenerering.

## Receptvisning

Näring visas med svensk talformatering och högst en decimal. Uppskattningen
31.588999999999995 visas som **ca 31,6 g protein per portion**. Originalvärdet
och gränsjämförelsen är orörda. ”Om näringsberäkningen” ersätter den råa
decimalförklaringen. Vegetariska rätter märks ”Vegetarisk” och får faktisk
huvudråvara från strukturerat receptinnehåll när den finns.

En snävt kvalificerad visningsprojektion av den befintliga metodtexten gör
serveringssteget naturligare och behåller förutsättningarna om angivna
mängder, olja/sås/sky och dricksvatten intill ingredienserna och under
näringsinformationen. Okänd metod/version eller ändrad struktur behåller
originaltexten. Stegtider visas och faktiska parallella beroenden förklaras
samlat. Inga sparade recept, innehållshashar eller revisioner skrivs om.

[Mobilbild](recipe-mobile.png) · [Desktopbild](recipe-desktop.png).
Alla 104 aktuella varianter kontrollerades i Chromium och WebKit, 390/1280 px.
Ingen fysisk iPhone eller fysisk provlagning har utförts.

## Verifieringsstatus

- 2 226 backendtester passerade på slutcommiten, inklusive nya cache-, likvärdighets- och bytesprov.
- 1 664 grocery_data-tester passerade; dess kod är hashoförändrad sedan provet.
- Åtta befintliga frontendkontrakts-/layoutfall passerade i Chromium/WebKit,
  mobil/desktop, publikt/personligt. Dessa använder märkta syntetiska API-svar.
- Fyra innehållsvisningsprov × 104 verkliga registrerade varianter passerade.
- Ruff och compileall för ändrade filer passerade.
- Riktiga Chromium/publikt och WebKit/personligt, mobil 390×844: PASS.
  Menyknapp, omladdning under >1 minuts generering, fulla recept/inköp,
  korrigerad text, receptbyte, explicit omräkning, revision 1–3 och omstart.
  [DOM, layout, transport och revisionshashar](BROWSER.json).
- 19 tidigare testrevisioner bevarades byte för byte och lästes med slutappens
  PlanStore efter omstart; 29 revisioner fanns vid slutkontroll, SQLite ok.
  Den autentiska ursprungliga användarrevisionens båda hashar är oförändrade.
  [Bevarandekontroll och faktisk produktionsversion](RETENTION.json).
- Alla 645 runtimefiler matchar paketmanifestet; pip check och offline-
  Chromiumstart PASS. [Imagekontroll](IMAGE-VERIFICATION.json).

[Testöversikt](TESTS.json). Det första bytesstoppet och ett för tidigt
webbläsarstartförsök före readiness är bevarade, tillsammans med godkända
slutprov. Ingen fysisk iPhone eller provlagning påstås.

## Versionsbunden leverans

Runtime **b89fadb96c4edc4576cb4daae6c5d80e553ad8ca**, BUILD_ID
`five-cuisine-b89fadb96c4e`. Lokalt paket:
`.local/releases/five-cuisine-final-20261004/smako-server-b89fadb96c4e.zip`,
2 741 764 byte. Paket-SHA-256:
`eafba3aa7b4ab59d8fb92e258c995792caff9b9a3eb41838c3481b47142f982b`.
Verifierad image:
`sha256:80dd265779182eb750453e3b12a2249e71a9ed845f62c6e9c3c5f1a3a86ee4d1`.
[Manifestuppgifter](RELEASE.json), [app-only-aktivering och återgång](ACTIVATION.md).

Kvarstående mål: 60 s från klick är inte nått. Nästa uppmätta flaskhalsar
är förpackningsberäkning/audit samt kall fakta-/indexberedning. Alla tester
ovan passerar inom oförändrade krav; ingen större resursbudget, mindre
sökning, försvagad kvalificering eller dyrare ursprungsmeny användes.

## Driftgräns

Den egna isolerade testappen är stoppad efter slutförda prov; alla dess data
och revisioner är bevarade.

Ingen Git-push, produktionsaktivering, insamling eller ändring av relä,
scheduler, backup, proxy, kommunurval, femkällorspolicy eller 36/48-timmarsgränser.
Tidigare godkännande för 17a9c13 gäller inte denna kandidat. Ett nytt explicit
beslut krävs före ett framtida appbyte. Befintlig app-only-ordning används;
testklocka och frysta data får aldrig följa med till produktion.
