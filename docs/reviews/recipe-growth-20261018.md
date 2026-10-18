# 20 nya recept: kontrollerad mätning av bibliotekstillväxt 2026-10-18

20 nya recept har skapats med ordinarie `author`, importerats i ett isolerat testbibliotek och köpbarhetskontrollerats i Lund och Malmö. Biblioteket ökar från 222 till 242 recept (+9,0 %). Alla 20 klarar standardfiltret och köpbarhetskontrollen i båda städerna, utan author-varningar. Inga recept eller runtimeändringar har aktiverats i produktion.

**Slutsats:** fler recept kan öka beräkningstiden med dagens sökning. Effekten skiljer sig mellan städer och profiler och är inte proportionell mot receptantalet. De nya recepten väljs i samtliga fyra provade menyer och sänker priset i alla fyra. Detta prov mäter avvägningen; det ändrar inga söktak eller gör någon prestandaoptimering.

För Malmö ökar varm standardplanering 15,8 % och varm näringsplanering 23,1 %.
Standardökningen finns i båda körordningarna: 21,5 % i första blocket och 10,0 %
i det omvända blocket. Lund visar ingen tydlig ökning; små skillnader där bör
tolkas försiktigt. Menypriset sjunker 2,6–9,8 % beroende på profil. Detta är
ett mätresultat för dessa recept och underlag, ingen generell skalningsgaranti.

## Uppmätt planeringstid

Sekunder, median inom respektive grupp. Kall betyder ny process och egen tom förberedelsecache. Varm betyder efterföljande planering i samma process; en färdig meny återanvänds inte.

| Stad och profil | Läge | Före: 222 | Efter: 242 | Skillnad | Mätningar per arm |
| --- | --- | ---: | ---: | ---: | ---: |
| Lund, alla makron | kall | 138.82 | 142.65 | +3.83 s (+2.8 %) | 1 / 1 |
| Lund, alla makron | varm | 146.76 | 140.40 | -6.36 s (-4.3 %) | 2 / 2 |
| Lund, standard | kall | 46.36 | 45.20 | -1.17 s (-2.5 %) | 2 / 2 |
| Lund, standard | varm | 37.94 | 37.11 | -0.84 s (-2.2 %) | 4 / 4 |
| Malmö, alla makron | kall | 32.22 | 36.29 | +4.07 s (+12.6 %) | 1 / 1 |
| Malmö, alla makron | varm | 24.79 | 30.51 | +5.72 s (+23.1 %) | 2 / 2 |
| Malmö, standard | kall | 54.99 | 64.64 | +9.65 s (+17.6 %) | 2 / 2 |
| Malmö, standard | varm | 49.60 | 57.45 | +7.85 s (+15.8 %) | 4 / 4 |

## Menypris och faktisk användning

Alla 36 planeringar passerar ordinarie checkout-audit och profilens kvalitetskontroller. Varje stad/profil/arm ger samma resultat-hash i samtliga upprepningar. Resultatet får ändras mellan biblioteken: syftet är att prova nya recept, inte att kräva samma vinnare.

| Stad och profil | Före, kr | Efter, kr | Nya rätter i vinnande meny |
| --- | ---: | ---: | --- |
| lund, all-macros | 813.14 | 792.10 | Kyckling i oreganosås med zucchini, med ris; Kyckling i paprikasås med spenat, med ris |
| lund, standard | 548.76 | 516.54 | Kikärtor i paprikasås med spenat, med ris; Kyckling i paprikasås med spenat, med ris |
| malmo, all-macros | 1012.83 | 915.84 | Kyckling i paprikasås med spenat, med ris; Kyckling i spiskummintomat med paprika, med ris |
| malmo, standard | 534.92 | 482.75 | Röda linser i kokossås med ingefära och ärtor, med ris |

## Var tiden används

Median av varma körningar. Kandidatkontroll och veckosökning är separata övergripande steg. Underliggande spårningssteg överlappar och ska inte summeras.

| Stad/profil | Kandidatkontroll före → efter, s | Veckosökning före → efter, s | Korgberäkningar före → efter |
| --- | ---: | ---: | ---: |
| lund/standard | 5.34 → 6.32 | 28.79 → 26.48 | 2043 → 1900 |
| lund/all-macros | 10.38 → 10.03 | 132.55 → 126.59 | 12441 → 12044 |
| malmo/standard | 8.79 → 9.00 | 34.22 → 41.67 | 1472 → 1878 |
| malmo/all-macros | 9.65 → 14.01 | 8.57 → 9.66 | 424 → 499 |

## Metod och avgränsning

- Kod: `ad0411f0e45a07d157241856c38e9c31773d8cf5`, identisk runtimekod med main `1647c3839d850fa82fa440e31ddda6e56df51bc9` (endast tre dokument skiljer). Samma containerimage `sha256:93bbfd2ebe3764cddd559422ed1fce53197359b6f0aabde50619dfc6a81cd8f7` i båda armarna. Endast bibliotekets datamapp skiljer.
- Server: sekventiella containrar, nätverk avstängt, 2 CPU och 3 GiB minnesgräns, kod och bibliotek skrivskyddade under mätningen. Ingen produktionsdatabas eller privat planlagring monterad.
- Samma frysta offentliga priser, produktfakta, butiksscope och klocka `2026-10-18T05:12:49.467392+00:00` i varje jämförelse. Indatahashar verifieras av den befintliga acceptansmatrisen. Dataarkivets SHA-256: `ea895f92ec8bb6f4d6d953eb93243fcfebc37bf6df809ec118bbfc053aeee670`.
- Standard: fem middagar för fyra personer. Alla makron: samma antal, protein 40–90 g, kolhydrater 10–130 g, fett 1–60 g och högst 1 000 kcal per portion. Två butiker, estimated inköpsläge, näringsestimat tillåtna.
- Ordinarie sökinställningar: seed 40, refinement 90, varianturval på. Inga tak eller kvalitetskrav ändrade. Testet är ingen ny uncapped-jämförelse.
- Varje process kör en kall och två varma planeringar. Standard upprepas i en andra process per arm med omvänd ordning. Totalt 12 processer och 36 planeringar. Lund börjar med baslinjen och Malmö med det utökade biblioteket; andra standardblocket vänder ordningen.
- Tidtagningen omfattar PersonalPlanner-konstruktion och create. Läsning av pris-/faktaartefakter sker före tidtagningen. Ingen HTTP-kö, belastningstest, OS-diskcachetömning eller populations-p95 mäts. Näringsprofilen har färre upprepningar än standard; små skillnader ska tolkas försiktigt.
- Importen skapar en ny biblioteksgeneration (11 → 12), precis som normal author-import. Resultatet gäller dessa 20 recept och den vanliga importsökningen; det är inte ett generellt linjärt mått per recept.

## Recept och verktyg

Testpaketet innehåller fem smaksättningar vardera med kyckling, nötfärs, röda linser och kikärtor. Alla har tio räknade ingredienser och använder redan kända ingrediensidentiteter. Utkasten är inte provlagade eller godkända för produktion.

Första försöket gav 20/20 köpbara i Lund men bara 8/20 i Malmö: limejuice och kvalificerad fryst majs saknades i Malmöunderlaget. Utkasten ändrades till citronjuice och rå morot. Ett mellanliggande skrivfel med morot/as_sold stoppades av author; korrekt raw_edible användes i slutprovet. Inga pris-, fakta- eller kvalificeringsregler ändrades. Slutpaketet ger 20/20 i båda städerna.

Ordinarie CLI: `python -m app.services.meal_library_cli author drafts.json --output pack.json --report author.json --import --prepare 2 --prepare 4 --universe prepared-universe.json --facts product-facts.json --clock 2026-10-18T05:12:49.467392+00:00 --purchase-mode estimated`. Importen måste köras mot en isolerad kopia av bibliotekets datamapp. Tidprovet använder `backend/scripts/planner_acceptance_matrix.py --repeat 3` med egna cachemappar för varje process.

Author-regression: 10 tester PASS. Relevanta experimentskript har kontrollerats med Ruff och compileall. Runtimekoden är oförändrad; tidigare full regression och CI från rättelsegranskningen har inte körts om.

## Underlag

- [Mätvärden, CPU-tider, spridning, sökspår och hashjämförelser](recipe-growth-20261018/measurements.json)
- [De 20 author-utkasten](recipe-growth-20261018/drafts.json)
- [Det standardiserade importpaketet](recipe-growth-20261018/pack.json)
- [Author- och köpbarhetsrapporter för båda städerna](recipe-growth-20261018/qualification.json)
- [Biblioteksmanifest och integritetskvitto](recipe-growth-20261018/library-receipt.json)

Fulla JSON-rapporter, importerade paket, exakta körskript och tidigare utkast bevaras i serverns `/opt/smako/evidence/recipe-growth-20261018/experiment-results.zip` samt lokalt under `.local/recipe-growth-20261018`. Endast egna temporära prisutpackningar och förberedelsecachemappar rensas efter arkiv-/hashkontroll. Produktionsbiblioteket påverkas inte.

Slutkvitto: arkivet innehåller 180 filer, är 2 374 298 byte och har SHA-256
`456d2c8c9475e783436374a0f0a1526db3413d1f7ee656e889be7606e91d5b5e`.
14 pris-/faktafiler verifierades mot det bevarade dataarkivet före rensning.
854 063 903 byte egna tillfälliga filer togs bort. Produktionskontroll
2026-10-18 16:05 UTC: ready/HTTP 200, oförändrad build
`joint-week-refinement-app-e041451`, prewarm false i både container och miljöfil,
inga testcontainrar kvar. Ledigt 19,16 GB mot beräknat behov 13,99 GB.
