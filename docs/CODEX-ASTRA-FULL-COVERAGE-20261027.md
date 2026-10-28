# Full recepttäckning: uppdrag och kontrollpunkt 2026-10-27

Ägaren gav Astra ansvar för hela restlistan efter PR #20, main `9992d34`.
Arbetskopia är `D:\Projects\Smako`; den historiska Codex-katalogen används inte.
Målet är fortfarande alla 2 200 importerade varianter, av 2 462 aktiva,
med bevarade original och versionskedjor. Legacy är standard och V2 opt-in.

Uppdraget omfattar samtliga 76 då kvarvarande grupper/595 varianter, exakta
produkt- och källrelationer, dokumenterade beredningar och det generella
prisgapet i A. Originalreferensen är Malmöfilen med 89 458 produkter,
52 kontexter, klockan `2026-10-23T06:00:02.869273+00:00`, fyra portioner
middag, en frukost/mellanmål, högst två butiker och inget skafferi.
Nytt sortiment ska få eget scope; priser och källtider får inte blandas in.

Separat tilldelning för denna etapp: högst 3 600 sekunder tungt arbete,
en tung arbetare, två CPU och hårt 3 GiB via befintlig `budgeted_check`.
Minst 600 sekunder reserverades för slutkontroll. Tidigare budgetjournaler
är hashkontrollerade och orörda. Första granskningsbara kontrollpunkt ska
levereras senast tre timmar efter start `2026-10-27T12:54:20Z`.
Ingen automatisk fortsättning, deployment eller schedulerändring ingår.

## Levererat i denna kontrollpunkt

Se [resultatrapport](reviews/recipe-coverage-full-20261027.md),
[alla ursprungliga grupper](reviews/recipe-coverage-full-20261027/work-matrix.md)
och [verifieringsdata](reviews/recipe-coverage-full-20261027/verification.json).
41 nya hela uppskattningskorgar, 11 nya exakta korgar och A:s prisrättning
är verifierade. Detta är inte en slutleverans av målet om full täckning.

## Fortsättning efter PR #21

Ägarens ”Fortsätt” återupptar samma etapp och samma budget. Den andra
[kontrollpunkten](reviews/recipe-weight-coverage-20261027.md) löser det ordinarie
viktpriset för hel oxfilé: tre ytterligare fullkorgar, totalt 1 649 i estimated.
Rabatten med obelagd gränsenhet tillämpas inte. Inga nya fakta eller priser
har lagts in i den frysta referensen. Ett nyare kvalificerat Willys Malmöarkiv
har också granskats för alla 74 namn utan att ge nya kvalificerade lösningar
för kvarvarande hinder. Nästa steg nedan behåller sina beviskrav.

## Konkret nästa arbete

1. Implementera gemensam beredning först när inköp, råvaruinsats, komponent-
   utfall och skafferibokföring kan hållas isär i befintliga modeller.
   [Beredningsgranskningen](reviews/recipe-coverage-full-20261027/preparation-review.md)
   beskriver äggkälla, balans, tider, näringsgrund, återstående kod och tester.
   Mungbönskällan anger volymutbyte; kaffekällan anger tillsatt vatten.
   Dessa är inte belägg för receptens efterfrågade massa/slutvolym.
2. Viktprishindret för de fyra hela oxfiléartiklarna är löst i fortsättningen:
   separat ordinarie taxa används genom befintliga pris-/mängdresolvers,
   med hela uppskattade förpackningar. Den gamla
   [diagnosen](reviews/recipe-coverage-full-20261027/tenderloin-price-contract-gap.json)
   är historisk; den obelagda rabattgränsen är fortfarande inte godkänd.
3. Den exakta 44-artikelskön är kvar lokalt. Tre försök stannade före
   handlaranrop när den gemensamma serverleasen var upptagen. Respektera
   låset; återuppta bara när ordinarie operation är klar. Koden ändrar inte
   produktion, runtimekonfiguration eller scheduler vid arkivkomplettering.
4. Mynta, tamarindpasta, masa harina och pärlkorn har fortfarande 200
   varianter där respektive grupp är enda hindret. Se arbetsmatrisens
   konkreta skillnader mellan bladmassa, styrka/enhet och kulinarisk form.
   Saknat prissatt SKU i referensen bevisar inte frånvaro på marknaden.
5. Ny godkänd pris-/sortimentsversion kan undersökas i befintliga tillåtna
   källor/kontexter med ordinarie lås och validering. Först om en ny handlare,
   källa eller allowlist behövs ska ett konkret separat beslutsunderlag tas
   fram. Inget sådant breddningsbeslut har begärts eller fattats här.

Efter ändrad runtime/data behövs nya aktuella kvitton för hela nämnaren,
oförklarade förluster ska stoppas, och samma fullständiga A/B2-begäranden
ska jämföras. Befintliga hashstabila bevis återanvänds. Eventuell fortsättning
ska redovisa återstående etappbudget; ingen ny session får nollställa den.

## Historisk kontrollpunkt efter PR #22 — då ej integrationsgodkänd

Ägarens konkreta Hemköp-/Coop-mynta och tre övriga råvaror är granskade i
[rapporten](reviews/recipe-four-staples-20261027.md). De två Lundartiklarna
fanns redan i underlaget. 91 generiska myntadefinitioner har versionerats
separat från 40 bladkrav, och en källbunden uppskattning ger 68 nya hela
korgar: 1 717 inklusive uppskattningar, exakt fortsatt 1 008.
Tamarindens gram/koncentration och rätt prissatta masa-/pärlkornsprodukter
återstår. 146 varianter har nu en av dessa fyra grupper som enda hinder;
det är villkorad potential, inte verifierade nya korgar.

**A-prisgrinden faller: 295,41 mot 283,24 kr.** Den gamla menyn kostar ännu
283,24 kr vid ny checkout. B2 är helt identisk, 731,20 kr. Granskningen och
myntarättningen sparas därför i en utkast-PR och får inte integreras ännu.
Samma journal har 281.5558 s kvar; full verifiering efter en ny
sökrättning kräver ett uttryckligt utökat budgetbeslut. Ingen sådan
utökning, automatisk fortsättning eller produktionsaktivering är beslutad.

## Godkänd förlängning och slutförd fyravarugranskning

Ägaren beslutade uttryckligen ”Utöka med 15 minuter och slutför”. Samma
journal har nu 4 500 s total ram; tidigare förbrukning kvarstår. Den generella
sökregressionen är rättad genom återanvändning av statisk prioritet per
måltidsplats. Slutliga prov ger A 281.31 kr och i separat nyägarkörning
281.31 kr, båda högst tidigare 283,24 kr. B2:s hela korg är identisk.
Ny full verifiering på slutlig metod ger 1 717/2 200 inklusive uppskattningar,
+68; exakt 1 008, inga förluster och 2 727 verifierade kvittofiler.
Prisgrinden passerar utan ändrade krav. [PR #23](https://github.com/ossebosse/smako/pull/23)
kan integreras efter grön CI. [Slutrapporten](reviews/recipe-four-staples-20261027.md)
beskriver alla fyra varor och de precisa kvarvarande källbehoven.

Etappen är verifierad inom den godkända ramen: 3991.5507 s använda,
508.4493 s kvar. Full täckning är fortsatt ett öppet mål med 483
varianter kvar; inga nya produktfakta har antagits för att stänga dem.

## Fortsättning utan total tidsgräns

Ägaren beslutade: ”Fortsätt. Du har ingen tidsgräns. Om du hittar onödiga
tider på ci eller andra processer åtgärda.” Den tidigare etappgränsen är
därmed upphävd för fortsatt arbete. Samma journal behåller all historisk
förbrukning och använder null för obegränsad total ram. Enskilda
operationers watchdog, två CPU:er, 3 GiB minnesgräns och gemensamt lås
består. Arbetet fortsätter från PR #23 / main 4f77ad3: 1 717 hela
korgar inklusive uppskattningar, 483 kvar. Undersök och åtgärda verkliga
CI-/processflaskhalsar utan att minska testtäckning eller kvalitetsgrindar.

## Ny verifierad kontrollpunkt utan total tidsgräns

1747/2 200 hela korgar inklusive uppskattningar, +30; exakt 1020 hela,
1022 insatslösta, 453 kvar. Inga förlorade korgar. Två nya A-prov klarar
281,31 kr och B2:s hela korg är identisk. Se [rapporten](reviews/coverage-continuation-20261027.md).
CI är integrerad via PR #24: 9:50 mot 20:35 med hela testurvalet kvar.
Fortsatt kod-/källarbete återstår; full täckning är inte klar.

## Nästa verifierade kontrollpunkt 2026-10-28

1 784/2 200 hela korgar inklusive uppskattningar, +37; exakt 1 049 hela och
1 051 insatslösta, 416 kvar. Alla original och tidigare korgar består.
Fem exakt bundna produktdeklarationer ger avrunnen massa utan nya priser
eller receptändringar. A 281,31 kr i båda slutprov och B2:s hela korg identisk
731,20 kr. Alla 2 835 kvittohashar verifierade. Se
[rapporten](reviews/reviewed-drained-foods-20261027.md). Full täckning återstår;
ägarens fortsättning utan total tidsgräns och ordinarie resurs-/källkrav består.

## Produktfakta och nästa kontrollpunkt 2026-10-28

1 802/2 200 hela korgar inklusive uppskattningar, +18; exakt 1 062 hela och
1 064 insatslösta, 398 insatshinder kvar. Alla tidigare korgar och original
består. Risnudlar, sardiner och svart löste har 19 nya exakta relationer.
A 281,31 kr i båda slutprov och B2:s hela korg identisk 731,20 kr; samtliga
2 866 kvittohashar passerar. [Rapport](reviews/product-facts-20261028.md).
Full täckning återstår. Samma obegränsade totaljournal och resurs-/källkrav;
CI balanseras till tre obligatoriska partitioner med alla testnoder kvar.
