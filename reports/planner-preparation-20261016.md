# Plannerförberedelser och testmatris, 2026-10-16

Punkt 1–2 är implementerade och verifierade lokalt på grenen
`perf/planner-preparation-matrix`, kodcommit `f2855df`, bas `b77e033`.
**Inte aktiverat på betan.**

## Vad som ändrades

- Befintliga `combined_performance_probe.py` har ett `--matrix`-läge med tio
  personliga profiler. Samma frysta indata, klocka och butiksval används före/efter.
  Beräkning, CPU, verifiering, uppstart och minne redovisas separat.
- Befintliga `meal_prepared_artifacts` och universumets begränsade cache används
  för 84 ingredienssökningar. Exakt samma produktindex och granskade alias används.
  Indexet binds till inventering, butikskontexter, biblioteksinnehåll och kod.
- Samma förberedelse anropas från befintlig uppstart/omladdning och från
  `meal_library_cli prepare/build --universe`. Befintliga källfakta, mängd- och
  näringsberäkningar återanvänds. Näringsreferensernas och deklarationernas
  JSON-innehåll ingår nu också i artefakternas kod-/databindning.
- Befintlig PerformanceTrace mäter ekosökning separat och räknar prövade
  ekodelmängder. Admission-kön har en separat span när en trace är aktiv.
  Offlineproven passerar inte den kön och anger därför kötid som okänd.

Ett försök med en extra gemensam näringscache togs bort: varma jämförelser
gav ingen tydlig vinst och exakt hashning/skyddskopiering tillförde arbete.
Experimentets mätvärden finns separat i JSON-rapporten. Slutresultaten nedan
avser koden utan den extra cachen. Ingen ny prismotor eller datakälla införs.

## Underlag och metod

Historisk replay med fryst klocka 2026-10-15 13:00 UTC: 26 840 produktposter,
19 sparade priskontexter från urvalet inom 3 km från 22225, högst två butiker,
kompletta recept och tillåtna närings-/mängduppskattningar. Routingpostnumret
i det sparade anropet är 22350. Ingen ny insamling eller uppdatering av priser.

Lokal Windows 11, Python 3.12.10, Intel i7-8750H (6 kärnor/12 logiska CPU).
Proven kördes efter varandra, utan samtidig belastningsmätning. Referensarmen
kopplar förbi endast de nya förberedelserna; äldre fungerande cacher finns kvar.
Den tidiga referensarmen kopplade även förbi den då experimentella näringscachen.
Enskilda mätvärden finns i den [lokala JSON-rapporten](planner-preparation-20261016.json),
som hålls utanför Git enligt projektets regel för rapportdata.

| Fryst indata | SHA-256 |
| --- | --- |
| `combined-prices.json` | `14e5ce6f6978fe6b70ef0770b91eb4b361132291e98e0e9c342cd1a424ab9b00` |
| `combined-facts.json` | `0d874ccb9cdf3891bbee90c90b74a6ed78ae96fb3b085192fd3c0baddd2a12e1` |
| `combined-request.json` | `060525073a151169f2c229b00b74c57f54b85c6dd7f37c14a336c943c8a2d4b8` |

Alla slutprov använder runtime-signaturen
`18aee7a7054a4225602be4cc98f65f56420d5da5853ee43a62b052994b579c2e`.

Varje profil har en ny process och egen ny diskcache, följt av en varm körning
med en ny PersonalPlanner. Eko har en full körning per arm; den planerade andra
referenskörningen avbröts och räknas inte. Färdiga menyer återanvändes inte.
Nätanslutningar blockerades under beräkningen, och syntetiskt privat tillstånd
kontrollerades oförändrat efter varje körning. Inläsning och kvalitetskontroll
ingår inte i tabellens beräkningstid.

## Resultat

Sekunder anges som processkall / processvarm. Diskförberedelsen ingår i den
första tiden här; det separata uppstartsprovet visas längre ned.

| Profil | Referens, s | Slutversion, s | Inköpskostnad, kr | Utfall |
| --- | ---: | ---: | ---: | --- |
| Standard, fem middagar | 63.00 / 40.19 | 65.02 / 38.74 | 674.16 | Meny, audit PASS |
| Minst 40 g protein | 31.85 / 8.10 | 42.20 / 8.45 | 1216.11 | Meny, audit PASS |
| Samtidiga makro-/energigränser | 32.19 / 8.29 | 33.00 / 8.43 | 1216.11 | Meny, audit PASS |
| Veganskt, minst 20 g protein | 30.41 / 3.14 | 29.07 / 3.24 | 478.17 | Meny, audit PASS |
| Fördelning av proteinkällor | 47.01 / 18.12 | 42.46 / 17.99 | 1119.68 | Meny, audit PASS |
| Frukost/mellanmål med viktgränser | 27.08 / 1.96 | 26.22 / 1.97 | 85.55 | Meny, audit PASS |
| Mjölkallergi | 26.13 / 1.18 | 26.94 / 1.14 | — | Avslag, samma kod/steg |
| Ekologiska animalier | 27.62 / 1.41 | 25.71 / 1.45 | — | Avslag, samma kod/steg |
| Minst 300 g protein (negativ kontroll) | 29.39 / 3.05 | 27.63 / 3.51 | — | Avslag, samma kod/steg |
| Minst 20 % ekologisk kostnad | 474.28 / — | 482.48 / — | 434.13 | Meny, audit PASS |

Alla tio profiler ger samma utfall före/efter. Sju ger en meny, tre ger avslag.
Det är utfall i denna testmix, inte appens generella täckningsgrad.
För levererade menyer är hela recept, inköpskorg, näringskällor, audit och
skafferifördelning identiska. Kassasummor stämmer, inga mängder är okända och
begärda näringsgränser, butikstak, kostval och proteinfördelning kontrolleras.
Avslag är inte lyckade leveranser. Mjölkallergi och ekologiska animalier har
fortfarande dataluckor; 300-gramsprovet ger ingen meny inom den befintliga sökningen.

Standardprovet gav 5 olika recept från
3 matkök. Proteinprovet gav
5 olika recept från
1 matkök. Den befintliga
variationen bevaras; etappen tillför inga nya recept eller sökvarianter.

Det separata uppstartsprovet för 40 g protein tog
**10.29 s** för ingrediensförberedelsen,
därefter **22.88 s** för första menyn och
**8.18 s** för nästa. Resultatet var identiskt
med referensen. Detta är flyttat arbete, inte ett test av full webbserveruppstart.

Provens högsta observerade processminne var
**818 MiB**. Det är processens högvattenmärke,
inte hela webbserverns minnesbehov eller en dimensionering för samtidiga användare.

## Flaskhals och kvarvarande mål

Ekofallet tog **482.48 s**, varav ekosökningens nästlade span
var **426.20 s** (88.3 %).
Det gjorde **382 864**
ekodelmängdsprövningar över 1 812 anrop. Den befintliga gränsen
256 gäller en delberäkning, inte hela menyn. Korgen kostade 434.13 kr
med 23.50 % verifierad ekologisk kostnad.
Nästlade spantider får inte summeras till total tid.

Förberedelserna ger ingen tydlig generell förbättring av redan varma menyer.
Målet 30 sekunder för vanliga profiler och provmålet 60 sekunder är inte
uppnått för hela matrisen. Nästa prestandaarbete bör fokusera på återkommande
ekokorgsberäkningar och veckosökningen, med oförändrade pris-/kvalitetskontroller.
Ingen sökbudget har sänkts här, och resultatet bevisar inte globalt lägsta kostnad.
Ingen samtidig HTTP-belastning eller 95:e percentil för verklig användartrafik har mätts.

## Verifiering

411 offlineprov passerar i 18 berörda testmoduler. Testerna omfattar
käll-/recept-/enhetsgränser, exakt aliasåtervinning, nytt underlag efter negativa
träffar, trasig diskcache, uppstart/omladdning, kömätning samt befintlig planering.
Ruff och compileall passerar. Inga UI-ändringar eller nya browserprov.

Körbeskrivning, mål och gränser: [arbetskontraktet](../docs/planner-performance.md).
Detaljerade lokala loggar finns under `.local/planner-preparation/` och
`.local/verification/planner-preparation-final.xml`; indata och cachefiler är ignorerade.
