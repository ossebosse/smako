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
