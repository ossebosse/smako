# AI-granskning: flexibla mängder i middagsbiblioteket (2026-11-25)

Ägarbeslut 2026-11-25: fler recept ska kunna skalas, och kryddor med mera som
hör till huvudråvaran ska följa med. Bara recept där det är rimligt, med
rimliga gränser. Granskningen är modellassisterad; ägaren godtar små fel och
rätterna provlagas inte.

Genereras av `scripts/recipe_layer/flex_dinners.py` från det aktuella
biblioteket (regler i skriptets beskrivning) och piloten
(`incoming/scalable-pilot-20261124`, dess sänkta tak gäller). Resultat:
**1992 middagsvarianter** i tre paket, 0 avvisningar. Utelämnade:
491 utan proteinhuvudråvara som är rimlig att skala,
267 med omätta processförluster eller äldre format.
Rapport per recept: `backend/app/data/recipes/incoming/flex-dinners-20261125/report.json`.

Metod: {'pot': 789, 'pan': 600, 'oven': 314, 'bake': 252, 'salad': 16, 'cold_assembly': 12, 'refrigerated_assembly': 9}.
Vanligaste huvudråvaror: kyckling 556, bönor 210, fisk 191, ägg 107, kikärtor 103, tofu 94, fläskfärs 92, fläskkött 90, lax 66, nötfärs 52, nötkött 48, tonfisk 48, svarta 43, ost 43, lammkött 33.
Vanligaste medföljare: salt 1658, rapsolja 1486, vitlök 346, citronjuice 345, gul lök 261, sojasås 217, persilja 202, spiskummin 195, svartpeppar 193, limejuice 183, senap 149, krossade tomater 127, dill 125, oregano 121, koriander 97.
Huvudråvaror som inte skalas: {'ägg som bindemedel': 150, 'torr i fast vatten': 32, 'redan vid taket': 3}.

## Granskning och ändrade regler

Två slumpvisa urval (30 och 22 recept) och riktade kontroller lästes i sin
helhet. Fel som ledde till regeländringar:

- Ägg som bindemedel (pastadeg, mannagrynskaka, potatiskaka, riskaka) fick
  intervall och drog med mjölk: ägg är huvudråvara bara i äggrätter (namnet)
  utan annat protein.
- Mjölk i en redning (kycklingkroketter) eller äggstanning (laxpudding) följde
  huvudråvaran: mjölk, grädde, mjöl och mannagryn följer aldrig.
- Panermjöl och ströbröd med rollen tillbehör fick intervall: bara riktiga
  tillbehör (ris, pasta, potatis, bröd, nudlar, couscous m.fl.) skalas.
- Fyllda, rullade, formade och skiktade rätter (chile relleno, limpa, kaka,
  kroketter, pudding, bullar) får högst 125 %; grytor, soppor och ugnsformar 130 %.

Kvarstående kända småfel: smaksättning kan följa fel huvudråvara i rätter med
två proteiner (till exempel sojasås till nudlar som följer tofun), och ris som
kokar i en buljong utan angiven vattenmängd kan få något för lite vätska vid
120 %. Ägaren godtar sådana fel.

## Full planner test, 2026-11-25 (Lund prices, throwaway container, 2 CPU, low priority)

Same script on the same code, with and without the 1 992 flex dinners imported.
Library: 3 298 recipes before, 8 012 after (4 714 scaled versions).

| Plan | Without flex | With flex | Cost without → with |
|---|---|---|---|
| No limits, 3 dinners | 90.8 s | 104.8 s | 270.74 → 270.74 kr |
| No limits, 5 dinners | 73.5 s | 79.6 s | 374.33 → 374.33 kr |
| Protein 35 g, 3 | 38.8 s | 68.4 s | 295.84 → 295.84 kr |
| Protein 45 g, 3 | 26.6 s | 56.5 s | 323.00 → 323.00 kr |
| Protein 45 g, 5 | 29.9 s | 81.0 s | 636.50 → 517.82 kr (two scaled dinners) |
| Vegetarian protein 35 g, 3 | 20.3 s | 39.7 s | 294.98 → 294.98 kr |
| Protein 40 g + 700 kcal, 3 | 28.8 s | 63.8 s | 324.40 → 324.40 kr |

Peak memory: 1 783 MB → 2 068 MB (+285 MB). Plans without limits pick no scaled versions.

### After "only the needed scaled version" (commit a8b2def)

| Plan | Without flex | All versions | Needed version only |
|---|---|---|---|
| No limits, 3 | 90.8 s | 104.8 s | 95.1 s |
| No limits, 5 | 73.5 s | 79.6 s | 77.6 s |
| Protein 35 g, 3 | 38.8 s | 68.4 s | 44.7 s |
| Protein 45 g, 3 | 26.6 s | 56.5 s | 37.3 s |
| Protein 45 g, 5 | 29.9 s (636.50 kr) | 81.0 s (517.82 kr) | 37.1 s (523.82 kr) |
| Vegetarian protein 35 g, 3 | 20.3 s | 39.7 s | 28.1 s |
| Protein 40 g + 700 kcal, 3 | 28.8 s | 63.8 s | 43.0 s |

Peak memory 2 018 MB. The 45 g / 5 plan now picks beef paprika at 120 % (closest that reaches) instead of 127 %.
