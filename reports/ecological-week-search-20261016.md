# Ekosökning och veckosökning, 2026-10-16

Lokalt verifierad uppföljning till prioritet 1–2. Gren
`perf/ecological-week-search`, kodcommit `6449cea`, bas `cac3a2e`.
Ingen produktionsaktivering i denna etapp. Senast dokumenterade betaversion
är `recipe-nutrition-extras-app-7e402a7`.

## Resultat

Det tidigare långsamma ekoandelsfallet sjönk från **482.48 till
216.52 sekunder**, **55.1 % kortare tid**.
CPU-tiden sjönk från 458.31 till 194.14 sekunder.
Samma tre recept, samma korg på **434,13 kr** och samma verifierade ekologiska
kostnadsandel (23.49526639 %). Hela resultatets semantiska
hash, inklusive korg, recept, näringskällor, audit och skafferifördelning,
matchar tidigare version i alla levererade provmenyer.

| Profil | Utfall | Före, kall / varm (s) | Efter, kall / varm (s) | Köpbelopp (kr) |
| --- | --- | --- | --- | --- |
| standard | PASS | 65.02 / 38.74 | 61.56 / 37.74 | 674.16 |
| protein40 | PASS | 42.20 / 8.45 | 32.66 / 7.98 | 1216.11 |
| all-macros | PASS | 33.00 / 8.43 | 31.65 / 8.06 | 1216.11 |
| vegan | PASS | 29.07 / 3.24 | 27.45 / 3.09 | 478.17 |
| distribution | PASS | 42.46 / 17.99 | 41.28 / 17.23 | 1119.68 |
| organic-share | PASS | 482.48 | 216.52 | 434.13 |
| breakfast-snack-weight | PASS | 26.22 / 1.97 | 27.77 / 1.95 | 85.55 |
| allergy-milk | BLOCKED | 26.94 / 1.14 | 25.31 / 1.12 | — |
| organic-animals | BLOCKED | 25.71 / 1.45 | 25.77 / 1.41 | — |
| impossible-protein | BLOCKED | 27.63 / 3.51 | 27.02 / 3.38 | — |

Den tydliga tidsvinsten gäller ekofallet. För övriga redan varma profiler
är skillnaderna små; här påstås ingen stor generell hastighetsökning.

Ekoandelsfallet har ett slutligt kallprov per version. Övriga profiler kördes
två gånger vardera inom samma process, med en separat process per profil.
Inläsning av frysta prisartefakter och kontroll av provresultatet ligger utanför
menyberäkningstiden. Förberedelser inne i första `planner.create()` ingår.
Uppvärmning är processcache, aldrig återanvänd färdig meny. Varje profil hade
en egen, ny katalog för diskförberedelser i denna slutliga provomgång.
Kall disk-I/O varierar; enstaka mätningar är inte p95 eller serverkapacitet.
Kötid är inte mätt. Högsta observerade processminne i omgången: 805.21 MiB.

## Vad som ändrades

Ekosökningen återanvänder befintliga prisgränser och exakta kostnadsnycklar.
En delmängd hoppas över först när den bevisligen inte kan slå en redan
godkänd korg. Lika pris behåller det första resultatet. Gruppkampanjer,
delade erbjudandegränser och egna kalkylatorer går genom ordinarie checkout.
Kostnadsnycklarna tar nu bort butiker utan kvalificerade varor, precis som
full checkout redan gör, och behåller svar för samtliga efterfrågade butikstak.

Receptkontrollens godkända första måltid lämnas till veckosökningens befintliga
cache med högst 256 poster. Bara samma begäran och samma första måltid återanvänds.
En ensam måltid, redigerade scheman och den fullständiga slutkontrollen beräknas
fortfarande. Sökbudgeten, recepturvalet och användarkraven är oförändrade.

Ekosökningen bedömde 361 928 delmängder mot tidigare 382 864.
Skillnaden kommer från återanvänd kvalificering av den första måltiden.
Av de bedömda delmängderna avfördes 68 913 av den optimistiska kostnadsgränsen
och 203 653 av den exakta kostnadsnyckeln. 89 362 krävde
full checkout, mot tidigare 382 864. Inga kandidater tas bort för att
en viss tid eller ett lägre antal beräkningar har uppnåtts.

## Verifiering och reproduktion

342 offlineprov i 18 moduler passerar, samt Ruff och compileall för ändrade
Pythonfiler. Proven jämför med full beräkning av varje ekodelmängd och täcker
förpackningar, kampanjer, kopplade rabatter, delade köpgränser, lika priser,
butikstak, slutlig näring, skafferi och ändrade recept. Ett befintligt cacheprov
kontrollerar nu återanvända offertmängder: när bara en butik levererar behövs
inte längre en vektor över flera butikskombinationer.

Oförändrade serializer-varningar gäller syntetiska äldre testdata med
`semantic_confidence="low"` som sträng. Inga rapportläsningar eller blockerade
källanrop i offlineverifieringen. Ingen nätinsamling har gjorts.

Samma frysta 26 840 produkter, 19 tillåtna priskontexter, faktaunderlag och
historiska klocka som [föregående rapport](planner-preparation-20261016.md).
Indatahasharna kontrolleras av den befintliga matrisen. Kör exempelvis:

```powershell
$env:PYTHONPATH='backend;.'
$env:PYTHON_DOTENV_DISABLED='1'
.venv\Scripts\python.exe -X utf8 backend/scripts/combined_performance_probe.py --matrix --inputs .local/planner-preparation/inputs --output .local/ecological-week-search/recheck --label recheck --matrix-case organic-share --repeat 1 --baseline .local/planner-preparation/matrix/organic-share/final-organic-share.json
```

Lokala råfiler finns i `.local/ecological-week-search/verified/`, sammanställning
i `reports/ecological-week-search-20261016.json`, JUnit i
`.local/verification/ecological-week-final.xml` och källisolering i motsvarande
`ecological-week-final-access.json`. Råfiler är avsiktligt Git-ignorerade.

Delprov före den sista ändringen gav 361,75 s med bara den optimistiska gränsen,
sedan 210,52 / 185,02 s med exakta kostnadsnycklar och överförd första måltid.
Dessa är utvecklingsmätningar, inte ytterligare slutprov.

## Kvarstående gränser

Ekosökningen behöver fortfarande bli snabbare för målet 30–60 sekunder.
Tre provprofiler ger fortfarande samma avslag; ingen datalucka eller
näringsgräns har gömts. Matrisens sju levererade menyer av tio profiler är
inte en generell täckningsgrad. Ingen globalt billigaste meny eller kapacitet
för hundratals samtidiga användare är bevisad. Nästa arbete bör utgå från
slutprovets kvarvarande ekosökning och därefter mäta kö/HTTP-belastning i
testmiljö innan antal serverprocesser dimensioneras.
