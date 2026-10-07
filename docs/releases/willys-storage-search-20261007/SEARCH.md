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

Första fulla parade 5×-provet är också klart:

| Mått | Före | Efter |
| --- | ---: | ---: |
| Planerare | 764,86 s | 421,42 s |
| Veckosökning, del av planeraren | 659,42 s | 325,85 s |
| Fakta + plan + serialisering | 786,50 s | 437,60 s |
| Hela containerkörningen, inklusive syntetisk import/förberedelse | 866,53 s | 516,53 s |
| Inköp, syntetiskt belastningsfall | 725,34 kr | 725,34 kr |

Planerartiden minskade cirka 45 % i detta par. Samtliga recept, mängder,
produkter, kanaler, köp-/närings-/allergenresultat och audit matchar.
En ytterligare diagnostisk skillnad redovisas uttryckligen:
`omitted_context_events` 1 076 831→1 069 500. Den räknar utelämnade
anrop efter samma gräns på 4 096 spårkontexter. Träff i `clean_recipe_cache`
återanvänder resultatet och hoppar över upprepade `resolve`-/`event`-anrop;
den nya ersättningsordningen ger färre sådana upprepningar. Alla bevarade
spårkontexter, faktiska sökhändelser och stopporsaker är identiska. Räknarens
råa värden och den första oklassificerade diffen bevaras. Den normaliseras
bara i resultatjämförelsen; inga webbläsarfel eller serverfel undantas.

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

## Kompletterande huvudprov och webbläsare

Tre kalla nyberäkningar (fakta + planerare + serialisering) ger median
97,67→91,00 s. Tre varma nyberäkningar ger 51,09→48,39 s. Ny process
med giltiga beständiga förberedelser: 57,96→54,74 s, ett par.
Dessa spann exkluderar inläsningen av prisartefakten och processstart;
rådata redovisar även dem separat. Inget färdigt resultat återanvänds.

| Klick till renderat huvudresultat, utan kö | Före | Efter |
| --- | ---: | ---: |
| Chromium, första kalla klicket | 94,188 s | 87,078 s |
| Chromium, varm nyberäkning | 55,984 s | 54,234 s |
| WebKit, varm nyberäkning | 55,687 s | 53,234 s |

60-sekundersmålet nås i de två varma knappflödena, men inte från kallt
tillstånd. En mätning per rad bevisar inte en percentil eller generell gräns.

Tretton strikta mobilwebbläsarprov har passerat (tre före, tio efter).
För varje ursprunglig menyavsikt finns exakt en tung beräkning i serverns
logg, korrelerad med begärans-ID. Byte och omräkning är separata avsikter.
Chromium och WebKit täcker publikt/personligt, enkel/genomarbetad middag,
frukost, mellanmål och kombinerad vecka. Kontrollerade statusavbrott,
förlorat accepterat startsvar, omladdning, dold sida och lämna/återkomst
behöll samma jobb; appomstart och flagga av behöll sparade revisioner.
Råa nätfel från felinjektion finns kvar; oväntade sidfel har inte undantagits.
Detta är mobil layout och simulerad synlighet, inte fysisk iPhone eller
verifierat byte mellan operativsystemets appar. Se BROWSER-EVIDENCE.json.

Fulla resultat i tolv hittills färdiga före/efter-par matchar efter ovan
redovisad normalisering. Samtidighets-, äldre profil- och skalprov fortsätter.
