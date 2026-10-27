# Fortsatt recepttäckning och snabbare CI 2026-10-27

**1 747/2 200 hela korgar inklusive uppskattningar**, +30 mot PR #23.
Exakt läge har 1020 hela korgar och 1022 insatslösta varianter.
453 varianter återstår. Alla 2 200 ursprungsreferenser och 2 462 aktiva
varianter består; inga tidigare verifierade korgar har förlorats.
Detta är en verifierad kontrollpunkt i det fortsatta uppdraget om full täckning.

## Nya granskade kopplingar

| Råvara | Verifierat underlag | Omfattning |
| --- | --- | --- |
| Vattenkastanjer | Spicefield 220 g netto / 140 g avrunnet, artikel 101285963_ST / GTIN 7611612109376 | En exakt CityGross Malmöpost |
| Bambuskott | Spicefield 410 g netto / 200 g avrunnet, artikel 101285964_ST / GTIN 7611612109383 | En exakt CityGross Malmöpost |
| Popcornmajs | Garant 500 g och Garant Eko 400 g, enbart opoppade majskorn | 15 exakt bundna Willys-/Hemköpsposter |
| Psylliumfröskal | Fiberhusk 300 g och Lindroos Premium 200 g, malda/pulveriserade fröskal | 10 exakt bundna poster |
| Rimmat fläsk | Scan 375 g, skivat rått rimmat sidfläsk som uttryckligen ska tillagas | Sju exakt bundna poster |

Mathems leverantörsuppgifter och visuellt lästa originaletiketter anger de
avrunna mängderna. Sidorna publicerar inget GTIN; identiteten har granskats
mot hela varumärket, varianten, nettovikten och etiketten. Inget nytt pris
har hämtats eller kopplats genom fuzzy namnmatchning. De exakta köpidentiteterna
finns i [vattenkastanjegranskningen](coverage-continuation-20261027/water-chestnut-review.json)
och [bambuskottsgranskningen](coverage-continuation-20261027/bamboo-review.json).

Den tidigare godkända 44-artikelskön kunde köras med båda ordinarie
operationslåsen: 40 nya dokument, en redan verifierad artikel och tre saknade.
En CRLF/LF-skillnad i köns hash rättades genom en separat normaliserad fil
med identisk artikelordning och spårbart original. Ingen kontroll försvagades.
Befintlig Axfood-faktaprojektion kompletterade 244 produktposter utan
faktakonflikter. De fem rena/råa deklarationerna har därefter individuellt
granskat fullständigt innehåll i 32 bundna poster. Generisk råprojektion
fortsätter lämna fullständighet okänd tills sådan granskning finns.

[Artikelinsamlingen](coverage-continuation-20261027/article-collection.json),
[faktaprojektionen](coverage-continuation-20261027/axfood-details-review.json)
och [de fem sammansättningsgranskningarna](coverage-continuation-20261027/plain-contents-review.json)
håller underlagen åtskilda. Fiberhusks sesam-/senapsspår består. Kopplingarna
skapar inga allergen- eller ekogodkännanden. De nya smördegsdeklarationerna
innehåller 20 procent smör och godkänns därför inte som veganska.

Deklarerad avrunnen massa använder befintlig mängdprojektion även i exakt
läge. Köpt nettomassa, paketavrundning, pris, butik och observationstid består.
Mängd-/identitetskonflikter blockerar fortsatt; exakt mängd gör inte omstridd
eller saknad näring användbar. Populationsutbyten kräver fortfarande uttryckligt
uppskattningsval. Inga recept eller deras gram/tillagningstider ändrades här.

## Pris och upprepat arbete

Ett mellanprov gav A 281,31 kr men återprovet 283,24 kr. Detta godkändes inte.
Profilen visade upprepad klassning av fasta spärrfraser. Regelord och deras
namn-/kategoriscope beräknas nu en gång; kandidatklassningens regler,
matchningsordning, prisprioritering och tolv sekunders slutreserv består.
Kompletta klassningssvar, bevis och säkerhetsnivåer blev identiska för alla
89 458 produkter. [Jämförelsen](coverage-continuation-20261027/exclusion-scope-equivalence.json)
och [alla fyra tidsprov](coverage-continuation-20261027/search-timing-review.json)
redovisar även det tidigare underkända återprovet. Ingen benchmarkmeny används
som startförslag och inget globalt optimum påstås.

| Prov | Hela korgen | API, sparning och GET | Separat käll-/biblioteksförberedelse |
| --- | ---: | ---: | ---: |
| A, ny ägare | 281.31 kr | 51.86 s | 90.69 s |
| A, separat ny ägare | 281.31 kr | 52.17 s | 68.58 s |
| B2, ny ägare | 731.20 kr | 32.25 s | 70.02 s |

A klarar föregående 281,31-kronorsgräns i båda slutproven. B2:s hela korg
är identisk, 731,20 kr. Detta är lokala separata prov med två CPU och 3 GiB,
inte p95- eller samtidighetsmätning.

## CI och verifiering

[PR #24](https://github.com/ossebosse/smako/pull/24) är integrerad som main
e68627f. Samtliga 4 069 då aktuella tester ingick: noll fel, 63 skip/xfail.
CI tog 9 min 50 s mot tidigare 20 min 35 s, cirka 52 procent kortare tid.
Två testpartitioner måste båda lyckas. En kall publiceringskedja återanvänder
befintlig exakt receptcache och behåller identiska noder. Föråldrade
PR-körningar avbryts och testtider sparas i JUnit.
[Jobbtiderna](coverage-continuation-20261027/ci-hosted-measurement.json)
skiljer hosted CI från lokala mätningar. Dagens partitioner innehåller samma
aktuella testnoder exakt en gång, enligt [kontrollen](coverage-continuation-20261027/ci-partitions.json).

312 riktade tester samt Ruff och compileall för alla nio ändrade Pythonfiler
passerar. Ny full bibliotekskontroll verifierar 2769 kvittofiler
med aktuella beroendehashar och inga förluster. De två tidigare exakta
checkout-avslagen under tvåbutikstaket kvarstår och räknas inte som godkända.

Samma frysta Malmöprisfil används: 89 458 produkter, 52 kontexter, klockan
2026-10-23T06:00:02.869273+00:00, fyra middagsportioner, en frukost-/mellanmålsportion,
högst två butiker och inget skafferi. Faktaversionens SHA-256 är
`87620c6b799a75fae97d414bef1ff3b37e6757736b14c64655a6f5c0a4a1934a`; metodhashen är
`52aeb5a649d98e38760aaa35b71ee850154712870d52e67b010c694eb7031554`. Hela begärandena är oförändrade och alla slutkorgar
auditkontrollerade. Råa offentliga benchmarkkvitton och kontoregistreringar
förblir lokala; rapporterna innehåller endast normerade resultat och hashreferenser.

Ägaren har upphävt den totala tidsgränsen. Samma journal behåller all tidigare
förbrukning, även misslyckade/avbrutna prov. Per-operation-watchdog, resursgränser
och operationslås består. Legacy är standard och V2 opt-in. Ingen betaaktivering,
scheduler-, profil- eller allowliständring ingår; Coop 730400 är fortsatt Online Syd.

## Fortsatt arbete

[Arbetsmatrisen](coverage-continuation-20261027/work-matrix.md) följer alla 76
ursprungliga grupper. Nästa konkreta kodsteg är att granska de hämtade
Falkenbergdeklarationernas uttryckliga räkmasseformulering och utöka befintlig
mängdparser, följt av fulla korgar. Äggdelning och kokta baljväxter behöver
fortfarande gemensam inköps-/komponent-/skafferibokföring. Tamarindens gram och
koncentration, exakt prissatt nixtamaliserad masa harina, pärlkorn och övriga
sortimentsluckor kvarstår. Saknad träff i referensen bevisar inte marknadsfrånvaro.

[Full verifiering](coverage-continuation-20261027/verification.json),
[nya korgar](coverage-continuation-20261027/newly-verified.json) och
[alla kvarvarande källbehov](coverage-continuation-20261027/blockers.json).
