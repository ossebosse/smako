# Näringsvärden för lösvikt, burkar och kryddor; uppskattad vikt alltid på (2026-11-25)

Aktiverad 2026-11-25 21:40 UTC. App **app-3a58ee0fba39-5f00a1b9**
(`sha256:2cf21273f743…`), bas `app-10a3567c2499-130792a7`. Scheduler orörd.
Backup före byte: `/srv/smako/backups/20261125T213002Z`.

Gren `feature/loose-food-nutrition` (`ac3b789`), releasegren
`release/loose-food-20261125` (`3a58ee0`, aktiv `10a3567` + `main..ac3b789`).

## Ägarens begäran

- ”Tillåt uppskattad vikt” ska alltid gälla och inte gå att välja bort.
- Kött som säljs per vikt ska få näringsvärden från Livsmedelsverket eller liknande.
- Sallad, salladslök, mynta, rädisor m.m. ska gå att köpa: ”Just find a way”.

## Rättelse

Tidigare skrev jag att sallad, salladslök, mynta och rädisor inte gick att köpa
för att de säljs per styck/knippe. Det stämde bara i exakt läge, som bara mitt
prov använde. Beta-gränssnitten planerar redan med uppskattad vikt. Det verkliga
hindret var att lösa varor saknar näringstabell.

## Ändringar

- `api/plan.py`, `api/personal.py`: planer från gränssnitten körs alltid med
  `purchase_planning_mode="estimated"`. Valet i `index.html` är borta (dolt fält),
  `app.js` återställer inte längre ett sparat ”exakt”.
- `services/loose_food_reference.py` (ny): enkla lösvaror utan egen tabell får
  generiska referensvärden, markerade som uppskattning:
  - Livsmedelsverket (65 livsmedel i `slv-20261125-loose.json`): nötkött, högrev,
    innanlår, fläskkött, karré, lamm, kyckling (lår/bröst), kycklinglever, torsk,
    makrill, räkor, rotfrukter, sallad, rucola, gräslök, kål, pak choi, chili,
    avokado, ananas, risnudlar, korngryn, sardeller, bambuskott, surkål,
    vattenkastanjer, saltgurka m.fl.
  - Matvaretabellen: salladslök, schalottenlök, chilipulver (chiliflakes,
    anchochili), karri (för garam masala, närmaste kryddblandning), kapris,
    currypasta, vitpeppar, senapsfrön; vitt/rött vin och balsamvinäger per
    100 ml med publicerad vikt per dl.
  - USDA FoodData Central: citrongräs (hela stjälkar räknas på inköpt vikt,
    övre gräns, eftersom det mesta tas bort).
  - Konserverad tonfisk, sardiner, mozzarella i lag m.m.: avrunnen referens även
    när burken har egen tabell (den gäller innehållet med lag).
  - Myntablad efter rensning: Livsmedelsverket 7194 ”Grönmynta blad”.
  - Kattmat, pastej, baguettesallad m.m. matchar aldrig.
- En produkttabell som saknar ett makro räknas som ingen tabell för dessa varor.

## Prov

- Nya `test_loose_food_reference_20261125.py`, `test_estimated_weight_always_20261125.py`;
  uppdaterade `test_nutrition_reference.py` (159 referenser) och
  `test_mint_leaf_preparation.py` (myntablad har nu näringsvärden). Relaterade
  prov för beredning, avrunna varor, oliver, ägg och referenser går igenom.
  Kvarvarande fel i bl.a. `test_cheap_bases_20261119.py`, `test_top_five_alternatives.py`
  gäller biblioteksstorlek och saknade granskningsfiler, och finns före ändringen.
- Serverkörning mot livebild med ändrade filer, en stad per container, 5
  middagar × 4, blandad kost (2 kyckling, 1 fisk, 2 kött), minst 45 g protein,
  uppskattad vikt, baslager hemma:

  | | Före | Efter |
  |---|---|---|
  | Lund: nya middagar som klarar kraven | 22 av 145 | 96 |
  | Lund: alla middagar som klarar kraven | 250 | 487 |
  | Lund: planens kostnad | 989,56 kr | 812,95 kr |
  | Malmö: nya middagar som klarar kraven | – | 94 |
  | Malmö: planens kostnad | – | 812,93 kr |

  Två nya rätter (tonfisklåda, pasta al forno med tonfisk) är bland de 40
  billigaste; den billigaste kombinationen väljer ändå äldre rätter.
- Kandidatbild: `from app.main import app` ok, 159 referenser, dolt fält i index.
- Efter aktivering: `/ready` Lund och Malmö ready med nytt BUILD_ID, inga fel i
  apploggen.

## Kvar

Saknar fortfarande näringsvärden: grönsaksfond (52 rätter; koncentrat och färdig
fond kan inte skiljas säkert), ostronsås (32), salvia, makrutlimeblad, saffran,
worcestershiresås, kryddnejlika. Andra stopp: ”ingen komplett korg i valda
butiker” (40) och kategorifördelningen (26).
