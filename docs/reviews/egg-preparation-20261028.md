# Gemensam äggberedning och recepttäckning 2026-10-28

**1 828 av 2 200 originalvarianter har nu verifierade hela korgar inklusive
uttryckligen tillåtna uppskattningar: +26, utan förluster.** Exakt läge har
fortsatt 1 064 insatslösta och 1 062 hela korgar. 372 varianter har kvarvarande
insatshinder. Alla 2 200 ursprungsreferenser, 2 462 aktiva varianter och gamla
receptversioner består. Detta är en kontrollpunkt; full täckning är inte klar.

[Verifiering](egg-preparation-20261028/verification.json),
[nya hela korgar](egg-preparation-20261028/newly-verified.json),
[kvittoindex](egg-preparation-20261028/basket-receipts.json) och
[restlista](egg-preparation-20261028/blockers.json) binder hela resultatet till
samma frysta Malmöunderlag: 89 458 produkter, 52 kontexter, klockan
2026-10-23T06:00:02.869273+00:00, högst två butiker, fyra middagsportioner,
en frukost-/mellanmålsportion och inget skafferi. Produktfakta är oförändrade
från PR #27, SHA `b56734ee54f2453c5e14bb1cbd38a1404ddd4a201259c51a15a88bfda09765e3`.
Inga priser, källtider, butiker eller personliga krav har bytts.

## Vad som gör äggvarianterna användbara

En explicit metodoperand i det befintliga, exakt granskade receptinnehållet
godkänner `hen_egg_separation_estimate_v1`. En egen hash eller klienttext
räcker inte: hela receptet måste finnas i det utgivna innehållsregistret.
Alla 26 varianter får separata efterföljare med oförändrade ingrediensmängder,
en föregående separerings-/vägningsinstruktion och tre ytterligare aktiva och
förflutna minuter. Tiden är en författaruppskattning, inte en källmätning.
Tidsfiltren använder de nya tiderna. [Versionsgranskning](egg-preparation-20261028/recipe-review.json).

[Kronäggs omvandlings- och näringsdata](https://www.kronagg.se/media/zkvbet4j/4-omvandlings-och-n%C3%A4ringsdata.pdf)
är den redan visuellt granskade populationskällan. För kvalificerad ätbar rå
heläggsmassa blir separeringsinsatsen `max(3 × gula, 1,5 × vita)`, plus separat
behov av helt ägg. Skalet hanteras redan av befintligt mängdunderlag och dras
inte av igen. Rå komponentnäring räknas för använda gram gula/vita, med
separat näringssamtycke. Tillagad vikt, retention och hållbarhet antas inte.

Samma `PersonalPlanner`, mängdresolver, inköpsoptimerare, checkout/audit och
privata transaktionsjournal används. Inköpet bokför hela ägg. Kvalificerade
hela ägg från skafferiet kan också reserveras som beredningsinsats. Uppmätt
beredning förbrukar verklig ätbar insats och skapar separata partier gula och
vita med ursprung och metod. Delarna får inte samma produktidentitet som om
de vore hela ägg. Upprepad åtgärd med samma ID bokförs en gång; ett ändrat
mätinnehåll med återanvänt ID avvisas. Andra planers reservationer skyddas.

För litet utbyte bokförs sanningsenligt och stoppar förbrukning tills behovet
är täckt. Delvis förbrukning bokförs mot ursprungliga komponentbehov.
Omplanering återanvänder ägarens köpta och beredda partier även när generiskt
skafferi är avstängt. Frigivning ändrar reservationer, inte verkligt lager
eller historik. Oanvända komponenter och hela ägg som blir kvar i paketet
visas separat. Uppskattat komponentöverskott ingår i befintlig jämförelse
vid samma inköpspris; inget framtida restvärde dras av från kassakostnaden.

Det riktade flödesprovet använder riktiga frysta produktkandidater men en
syntetisk ägare och syntetiska mätvärden. Två olika måltiders gula/vita samt
separat helt ägg delar köp. Efter beredning och halv förbrukning ger
omplaneringen 0 kr i nya köp; journalen består och slutlig frigivning lämnar
lagret oförändrat. Det är transaktionsverifiering, inte ett matlagningsprov.

## Pris och kontroll

| Prov | Hela korgen | API med sparning/återläsning | Separat förberedelse |
| --- | ---: | ---: | ---: |
| A, ny ägare | 281,31 kr, helt identisk | 51,83 s | 98,83 s |
| A, annan ny ägare | 281,31 kr, helt identisk | 53,75 s | 78,19 s |
| B2 | 731,20 kr, helt identisk | 32,71 s | 78,73 s |

Alla fullständiga sparade begäranden är oförändrade. Dessa prov visar inte
globalt lägsta pris eller en generell 60-sekundersgaranti. Kall förberedelse
och källa-/faktainläsning redovisas separat, inte som dold nolltid.

Samtliga 2 892 kvittofiler, deras beroenden, hela korgar och slut-audit är
kontrollerade. Ett recept hann inte klart inom den första ensekundsgränsen;
endast det ofullständiga provet fick tre sekunder vid omförsöket. Alla andra
hashstabila kvitton återanvändes. Inga ofullständiga sökningar räknas som
omöjliga eller godkända korgar.

Biblioteks-/privatregressioner, de 32 slutliga mängd-, lager-, tids- och
överskottsfallen samt dialogen i Chromium/WebKit passerar. Ruff och compileall
passerar på ändrade Pythonfiler. [CI-partitionerna](egg-preparation-20261028/ci-partitions.json)
innehåller alla 4 121 testnoder exakt en gång: 3 528 core, 133 planner och
460 integration. Inga tester eller kvalitetsgrindar har tagits bort.

PR #27:s genomförda CI tog 500 s (8:20) mot PR #26:s 701 s (11:41), med
4 103 tester, noll fel och 63 redovisade skips. [Körmetadata](egg-preparation-20261028/pr27-hosted-ci.json).
Denna ändrings hosted CI och integrationsstatus registreras vid leverans.
Legacy är fortsatt standard; ingen beta-/produktionsaktivering ingår.

Första hosted-körningen hade 14 fel med tre gemensamma orsaker: äldre tester
följde inte de nya efterföljarna, certifikatstester förutsatte en obruten kedja
trots en avsiktlig receptåterutgivning, och offline-skalets assetlista saknade
den nya klientversionen. Efterföljarkartor och kontroller av exakt utgivna
mellanversioner är rättade. Certifikatstesterna använder nu det verkliga
föregående, kompletta append-only-biblioteket; den oberoende spärren mot
återanvändning vid återutgivning är oförändrad. Offline-skalet har cache v19
och rätt klientfil, med API/POST fortsatt utanför cachen. De 55 berörda lokala
kontrollerna passerar. Runtime-modeller, tjänster, recept och fakta är
oförändrade, så de hashbundna korg-/prisproven ovan återanvänds.
[Reparation och testunderlag](egg-preparation-20261028/ci-repairs.json).

## Fortsättning

Tamarind, bladmynta, masa harina, citrongräs och pärlkorn är fortfarande stora
gemensamma hinder. För nya handlare finns ett separat
[avgränsat beslutsunderlag](coverage-source-pilot-20261028.md); inget sådant
utökningsbeslut eller någon driftaktivering ingår i den här kontrollpunkten.
Samma obegränsade totaljournal, en tung arbetare, två CPU:er, 3 GiB och
ordinarie käll-/operationslås består. Nästa nya fullkörning kan använda
tre sekunders receptgräns från början för att undvika ny källinläsning för
enstaka prov som precis överskrider en sekund; API-gränsen och alla
kvalitetskrav ska behållas.
