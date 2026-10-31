# Två menyprov som nådde tidsgränsen, 31 oktober 2026

[PR 55](https://github.com/ossebosse/smako/pull/55) tar bort två bortkastade
helbibliotekshashningar från produktfaktornas mellanled. Alla 54 515 faktaposter
och hela slutversionen är identiska. Slutlig hashning och varje källdokuments
kontroll, konflikter, valda krav, priser, checkout, ägarskap och sparning består.
Deadlinen är fortfarande 60 sekunder. Detta minskar ett uppmätt hinder;
**kallstart är inte färdiglöst**.

De ursprungliga proven gav SEARCH_INCOMPLETE efter 61,875 respektive 61,719 s.
Deras HTTP-metriker finns, men inga beständiga steg eller exceptionkedjor.
De kan därför inte i efterhand bindas till en exakt kodrad. Ett nytt publikt
UI-prov före rättningen blev klart på 42,0 s. Det provet fångade förloppet men
gjorde ingen separat checkout-/GET-assertion och räknas inte som sådan evidens.

## Reproduktion och avgränsad rättning

Samma typ av val återskapades från UI: Lund 22350, 3 km och 17 priskontexter,
en italiensk middag för två, standardgränsen 10–15 ingredienser, mjölk 1 l,
högst en inköpsbutik och uttryckligt uppskattningsläge. Ny syntetisk ägare;
inga befintliga profiler lästes. Testet använde betans exakta appbild och
aktuella offentliga käll-/prisunderlag i en isolerad container utan nät,
med 4 GiB minnestak, skrivskyddade källmountar och nya testdatabaser.
Axfoods verkliga produktdetaljrelease och aktiva planeringsinställningar ingick.

| Mätning | Före | Efter |
| --- | ---: | ---: |
| Kallt anrop | timeout 61,449 s | timeout 60,017 s |
| Faktaladdning i kallt anrop | 39,876 s | 35,111 s |
| Varm faktaladdning | 17,281 s | 12,272 s |
| Varm planering + sparning + ägd GET | 33,372 s | 25,910 s |
| Verifierad korg i varmt anrop | 110,55 kr | 110,55 kr |

Det kalla felet uppstod under receptkvalificeringen, före menysökningen.
Den varma menysökningen tog ungefär 0,3 s. Spåret motiverar därmed en
avgränsad rättning i faktaladdningen, inte en ändrad optimeringsbudget.
En privat vanlig dict ersätter två tidiga versioneringar under Axfood-berikningen.
Den färdiga FactsCollection får fortsatt en ny hash av alla verkliga slutvärden.
Ingen ny cache eller versionsåteranvändning införs.

Provets återställning av prisunderlag tog separat 91,524/96,834 s före anropet.
Det ingår inte i tabellens anropstider. Kall process/förberedelse är alltså
fortsatt ett produktproblem. Tiderna är enstaka isolerade prov med bevarade
cacheeffekter, inte median/p95, samtidighetsbevis eller full valkatalog.
Totalförbättringen kan inte helt tillskrivas enbart hashningen; dess eget
faktasteg är uppmätt separat. API-kö, proxy och browsertransport ingår inte
i de isolerade planeringstiderna.

## Verifiering

140 distinkta riktade testfall verifierade: käll-/Axfood-/Coop-fakta,
ägarbundna artefakter, aktuell sökpolicy och förberedelse. De nya proven
kontrollerar full slutversion, oförändrad delad katalog och att senare
korrupta detaljbytes fortfarande upptäcks. Ruff och compileall passerar.
Första tomma testreleasen var en ogiltig fixtur; den ersattes med en giltig
release med en annan artikel och båda projektionsfallen kördes om grönt.
Full CI och aktiveringsbevis dokumenteras i den separata releasejournalen.

Se [maskinunderlaget](EVIDENCE.json). Lokala råspår och syntetiska testdatabaser
är inte incheckade. Den tidigare förenklade körningen utan Axfood-konfiguration
och med felaktig skafferirevision är diagnostik, inte ett lyckat acceptansprov.
