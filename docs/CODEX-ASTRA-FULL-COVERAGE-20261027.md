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

## Konkret nästa arbete

1. Implementera gemensam beredning först när inköp, råvaruinsats, komponent-
   utfall och skafferibokföring kan hållas isär i befintliga modeller.
   [Beredningsgranskningen](reviews/recipe-coverage-full-20261027/preparation-review.md)
   beskriver äggkälla, balans, tider, näringsgrund, återstående kod och tester.
   Mungbönskällan anger volymutbyte; kaffekällan anger tillsatt vatten.
   Dessa är inte belägg för receptens efterfrågade massa/slutvolym.
2. Utred den befintliga viktprisvägen för fyra källbundna hela oxfiléartiklar.
   Identitet/form fungerar, men en kilotaxa får inte bli ett paketpris.
   [Diagnosen](reviews/recipe-coverage-full-20261027/tenderloin-price-contract-gap.json)
   skiljer detta tekniska hinder från saknade produktfakta.
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
