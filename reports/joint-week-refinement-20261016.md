# Parvisa veckobyten och mindre inköpsöverskott

Lokalt arbete i `D:\Projects\Smako`, gren `feature/joint-week-refinement`,
bas `4357323`. Nästa steg efter granskningen av punkt 5: gemensamt giltiga
receptbyten och mindre överskott vid samma inköpssumma. Ingen betaaktivering,
push, insamling eller ändring av användarens krav ingår.

## Beteende och återanvändning

Den befintliga veckosökningen körs färdigt: startsökning, enskilda byten och
högst 128 tidigare parförslag. Dess sökordning och budget är kvar. En separat
referens håller den bästa fullständiga korgen enligt inköpssumma och överskott,
utan att det sekundära måttet ändrar den tidigare sökvägen.

Ett avslutande parsteg väljer direkt bland kvalificerade recept. Ett alternativ
behöver alltså inte klara ett enskilt byte först. Två samtidiga byten kan
tillsammans återställa exempelvis veckans måltidsfördelning. Alla slutkrav
kontrolleras före prissättning och den valda menyn granskas oberoende igen.

Urvalet återanvänder `stratified_candidate_shortlist` och redan kvalificerad
`VariantSearchEvidence`. Högst åtta alternativ per position prioriteras efter
enskilt pris, gemensamma exakta produkter/ingredienser och kulinarisk bredd.
Prisledda par varvas med par med gemensamma råvaror. Det extra steget får högst
256 förslag och 32 nya korgberäkningar per biblioteksökning; separata snävare
butiksjämförelser har egna budgetar. Exakt samma vecka som redan prövats i
parsteget hoppas över. Räknare och gränser följer med i sökdiagnostiken.

Allt prissätts genom befintliga `PersonalPlanner.basket` och `BasketOptimizer`:
gemensamma behov, skafferi, förpackningsstorlekar, butikstak, kampanjer och
medlemsvillkor. Ingen parallell prismotor eller förenklad slutkostnad införs.
Prissignalerna i urvalet är heuristik och får inte godkänna ett köp.

Vid `surplus_mode=minimize` väljs vid lika verklig inköpssumma den meny som
lämnar lägst andel av betald varukostnad i oanvänd användbar mängd, därefter
lägst kvarvarande förpackningsandel. Pant ingår inte i matvärdet. Måttet dras
aldrig av från inköpssumman. Gram, milliliter och stycken hålls separata;
okända mängder räknas inte som noll och uppskattningar märks. `allow_larger`
avaktiverar denna sekundära jämförelse. Samma regel används när en tidigare
giltig meny från ett snävare butiksval jämförs med den större sökningen.

Detta minskar inköpsöverskott, vilket även kan vara användbart skafferilager.
Det är inte ett mått på faktisk kassation eller matsvinn. Nya recept och
varianter deltar automatiskt; inga recept-ID:n är hårdkodade. Sökningen kan
fortfarande missa par utanför urvalet och byten av tre eller fler rätter.
Globalt lägsta pris eller konstant svarstid för stora bibliotek är inte bevisat.
Policyversion: `personal-policy-v2-10-joint-week-refinement`.

## Fryst acceptansmatris

Samma 22225-underlag som föregående etapp: 26 840 produkter, 19 tillåtna
butikskontexter och klockan `2026-10-15T13:00:00+00:00`. Indata binds till
SHA-256 i `.local/planner-preparation/inputs/matrix-inputs.json`.
Nätverk är blockerat. Inga färdiga menyresultat återanvänds. Kall/varm avser
processen per profil; artefaktladdning och separat resultatverifiering ligger
utanför nedanstående planeringstider. Tio profiler, 19 körningar.

| Profil | Före kall / varm, s | Efter kall / varm, s | Inköpssumma före = efter, kr |
| --- | ---: | ---: | ---: |
| Ekoandel minst 20 % | 121,86 / ej mätt | 125,04 / ej mätt | 434,13 |
| Standard | 49,91 / 25,94 | 53,35 / 26,80 | 674,16 |
| Minst 40 g protein | 33,50 / 8,43 | 38,66 / 8,73 | 1 184,12 |
| Frukost + mellanmål + vikt | 25,31 / 2,11 | 25,61 / 2,07 | 85,55 |
| Alla fyra makronäringskrav | 33,10 / 8,62 | 33,21 / 8,75 | 1 184,12 |
| Veganskt | 27,79 / 3,53 | 27,79 / 3,67 | 478,17 |
| Angiven måltidsfördelning | 34,40 / 10,16 | 35,27 / 10,53 | 1 107,34 |

Alla sju positiva profiler klarar den separata kontrollen av köp, mängder,
näringskrav, vikt, fördelning och övriga begärda krav. Ingen blir dyrare.
Mjölkallergi, ekologiska animalier och omöjligt proteinmål förblir blockerade
med samma felkod/steg: efter 25,73/1,15, 26,58/1,42 respektive 28,87/3,63 s.
Högsta observerade processminne är 829,03 MiB, tidigare 825,13 MiB. Detta är
enstaka lokala körningar, inte en serverlastmätning eller minne per användare.

Förändringen innebär mer sökning, inte en hastighetsoptimering. Ökningen i
varm standardkörning är cirka 0,9 s; ekofallet ökar cirka 3,2 s kallt.
Eko tar fortfarande över två minuter och behöver ytterligare prestandaarbete.
Variation mellan dessa få prover är inte en säker skattning av svarstid eller p95.

Rådata: `.local/joint-week-refinement/final/after-<profil>.json` och
`.local/joint-week-refinement/matrix-summary.json`. Tidigare jämförelseserie:
`.local/eco-variant-selection/final/after-<profil>.json`.
Slutseriens metodsignatur:
`6a8a640360de24dfcd7380d6ffe45b4960a1993b7044711d4998d5f4b0c778e0`.

## Överskott och prisnytta

| Profil | Värde av kvarvarande inköp före, kr | Efter, kr |
| --- | ---: | ---: |
| Ekoandel minst 20 % | 169,82 | 169,82 |
| Standard | 221,40 | 221,40 |
| Minst 40 g protein | 219,30 | 204,21 |
| Frukost + mellanmål + vikt | 45,95 | 45,95 |
| Alla fyra makronäringskrav | 219,30 | 204,21 |
| Veganskt | 155,55 | 155,55 |
| Angiven måltidsfördelning | 288,40 | 273,31 |

I tre profiler minskar beräknat kvarvarande inköp med **160 g och 15,09 kr**
per meny. Förpackningsandelarna minskar med cirka 0,178; mängden i ml är
oförändrad. Dessa profiler har befintligt godkända uppskattade mängder, vilket
redovisas som `ESTIMATED`. De övriga fyra profilerna har samma överskott.
Ingen lägre inköpssumma påvisas i denna verkliga, frysta matris. Kalla och varma
körningar har identiskt fullständigt resultat inom respektive profil.

Standard, frukost/vikt och vegan har samma fullständiga semantiska hash som
tidigare. För de fyra profiler vars hash ändrades återspelades föregående
sökbeteende genom att stänga av de nya två callbackarna och den sekundära
jämförelsen mellan butiksurval. Återspelningen måste matcha tidigare recept,
korg, näring, revision och skafferifördelning exakt via tidigare SHA-256 innan
överskottsvärdet godtas. Dessa referenskörningar delar process och används
enbart för kvalitet/överskott, inte i tidsjämförelsen ovan. Ekofallets ändrade
meny ger varken lägre inköpssumma eller lägre överskott.

Rådata och körhjälpare: `.local/joint-week-refinement/surplus-comparison.json`,
`reference/before-<profil>.json`, `reference.py` och `compare-surplus.py` under
samma lokala mapp. De nya parstegen hittar också förbättringar i syntetiska
tester där den tidigare sökningen inte kunde komma vidare: 60 → 10 kr med
skafferi och ett explicit gemensamt erbjudande. Det är ett konstruerat test,
inte ett aktuellt butikserbjudande eller en uppmätt konsumentbesparing.

## Verifiering och återkörning

**460 tester passerar** i 25 berörda moduler, 229,34 s, via
`scripts/verify_offline.py` med `SMAKO_VERIFY_LABEL=joint-week-regression`.
De 15 nya testen täcker par som bara är gemensamt giltiga, oförändrad tidigare
sökväg, separat budget, 300 framtida recept, avslag/ingen förbättring, verklig
korgberäkning med skafferi och gemensam kampanj, en/två butiker, olika enheter,
okända/uppskattade mängder, pant samt uttryckligt tillåtna större inköp.
Resterande tester täcker bland annat bibliotek, variation, näring, ekosökning,
snävare giltiga jämförelser, kampanjer, cacher och slutrevision.

Ruff och compileall passerar. Isoleringsloggen
`.local/verification/joint-week-regression-access.json` har tomma
`report_reads` och `blocked`. De 18 befintliga Pydantic-varningarna kommer från
syntetiska `semantic_confidence`-värden i prestandatesterna. Matrisen visar
även tidigare kända serialiseringsvarningar för `high` och `estimated`.

```powershell
$env:PYTHONPATH='backend;.'
$env:PYTHON_DOTENV_DISABLED='1'
.venv\Scripts\python.exe -X utf8 backend/scripts/combined_performance_probe.py --matrix --inputs .local/planner-preparation/inputs --output .local/joint-week-refinement/recheck --label recheck --matrix-case protein40 --repeat 2
```

Hela körlistan finns i `.local/joint-week-refinement/verify.ps1` och
matrisdrivaren i `.local/joint-week-refinement/matrix.py`. Frysta data och
råresultat stannar utanför Git; kod, tester och denna rapport versionshanteras.
