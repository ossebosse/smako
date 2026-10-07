# B – optimering av veckosökningen, kvalificering pågår

Detta är isolerad utveckling. Ingen del av B har aktiverats på betan.

## Oförändrat jämförelseunderlag

Basruntime `fd2cfda5490ac93295e6a2cef6b6b8408497f89e`, paket-SHA
`342b74f913ce0625ee78bcdf283f02937273e9b36b730d26216ec55ffd5014e3`.
Ny runtime `54cb2e8159a126de26fa11cb1d393dc275238fd3`.
Alla 38 recept-/faktafiler, 15 frontendfiler och import-/förberedelsemoduler
matchar basens hash. De 24 + 6 recepten och deras tidigare kvalificeringar
är bevarade; inga nya fakta eller recept har lagts till.

Huvudfallet använder det verkliga P3-biblioteket med 182 recept. Skalprovet
återanvänder exakt den tidigare generatorn och P2:s innehåll: 176 → 352 →
880 recept. Tilläggen är syntetiska belastningsposter med skilda mängder och
grundrättsidentiteter, inte nya granskade recept. P2→P3 ändrade endast data.
Det separata skalimagen med P2-innehåll är inget leveranspaket.

Fryst prisartefakt SHA-256
`f82d66103e830b82b7d919fe847fd5b3ef85c5e323e0a2133c338f064dfb8768`,
köpklocka `2026-10-04T07:19:16.028059+00:00`. Alla 2 233 refererade råfiler
har verifierats. Detta är berikad historisk replay, inte aktuella priser.
Ingen testdatabas eller testklocka förs över till produktion.

## Profil och ändring

Ett avgränsat cProfile-prov av den gamla koden på 5× avbröts kontrollerat
efter 657,27 s (646,42 CPU-användarsekunder). Det är diagnostik, inte ett
slutfört prestandaprov. Det nådde veckosökningen: 5 209 utvärderingar och
5 728 korgberäkningar. Inkluderande tider omfattar varandra och summeras inte:

| Anrop | Antal | Inkluderande sekunder |
| --- | ---: | ---: |
| `nutrition_evidence` | 1 583 991 | 240,09 |
| `_nutrition_evidence` | 1 408 196 | 219,43 |
| `input_evidence` | 1 408 196 | 203,20 |
| Korgoptimering | 9 546 | 190,93 |

Receptets fulla identitet gjorde likadant produktunderlag till separata
cacheposter för varje recept. Det större biblioteket omsatte cachen och
upprepade produkt-/referensprövningar under veckosökningen.

Ändringar:

1. `ada436763c8a`: faktaversionen beräknas med strömmande JSON och exakt
   samma kanoniska byte/hash, utan full kopiering av alla nästlade fakta.
   Förändrade eller nya fakta ingår fortfarande i signaturen.
2. Samma commit: befintliga begränsade recept-/kandidatcacher behåller ofta
   använda poster i stället för att tömmas helt när gränsen nås. Gränserna
   höjs inte; borttagna rena beräkningar kan alltid göras om.
3. `54cb2e8159a1`: varje exakt recept valideras innan dess produktunderlag
   får återanvändas. Därefter beror insatsunderlaget på metodversion,
   rättfamilj, ingrediensform, produktidentitet, enhet, efterfrågade
   näringsfält och medgivanden inom samma begärans eget produkt-/faktaunderlag.
   Äldre näringsmetoder behåller full receptidentitet.

Detta delar inte receptidentiteter, veckotillstånd, portionsresultat eller
användares förutsättningar. Receptmängd, portionsantal och slotidentitet
prövas fortsatt i den individuella näringsberäkningen. Samma oberoende
slutliga checkout/audit körs. Sökordning, budget, priser, produkter, krav,
butikstak och gemensam veckokorg har inte ändrats.

## Hittills verifierat

80 riktade prov passerade efter den sista kodändringen, inklusive
receptberedning, underlagscache, personlig prestanda/ekvivalens, granskad
kycklingnäring och erbjudandevägen. Ruff och compileall passerade.
Ett avgränsat föreprov med fd2:s verkliga `nutrition_evidence` fallerar:
152 produktberäkningar för 152 recept. Efter: 30 skilda metod-/familjegrupper,
identiska värden och källreferenser, fortfarande 152 egna receptvalideringar.
Manipulerat mängdsigill stoppas. Tidigare prov av opåverkade status-/importdelar
är återanvända versionsbevis, inte nykörda tester.

Första parade kalla huvudprovet, inga förberedda artefakter:

| Mått | Före | Efter |
| --- | ---: | ---: |
| Fakta | 23,25 s | 15,50 s |
| Planerare | 75,50 s | 74,39 s |
| Fakta + plan + serialisering | 98,94 s | 90,07 s |
| Inköp | 741,15 kr | 741,15 kr |

Hela planresultatet matchar efter normalisering av bygg-ID, mättider,
genereringens `data.pricing_timestamp` och ordningen i den identiska
medlemsmängden. Produkternas observationer, avtal och samtliga övriga
resultatfält jämförs oförändrade. En körning är inte median eller klicktid.

## Miljö och återstående kvalificering

Windows lokala Docker, två CPU och 3 GiB per isolerad process, inga parallella
tunga planerare. Data-VHDX verifierad på
`D:\docker\DockerDesktopWSL\disk\docker_data.vhdx`; inputs/results i namngivna
volymer där. Paket, lokala loggar och råbevis ligger på D:.
Samma lokala basimage och Pythonberoenden används före/efter. Den lokalt
återbyggda basimagen är inte den historiska serverimagen; historiska
servermätningar redovisas separat och blandas inte med dessa parade värden.

Full 1×/2×/5×-matris, tre kalla/varma huvud-/skalprov, kompletterande
profilfall och paketerade webbläsar-/lagringsprov pågår. Kandidaten är
**ännu inte slutkvalificerad eller redo för aktiveringsbeslut**.
Råa test- och verktygsfel bevaras under
`.local/willys-storage-search-20261007/`, inklusive avbrutna profiler.
