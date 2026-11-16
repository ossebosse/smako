# Näringsdeklarationer och ingredienser med produkterna

Läget 2026-11-16 och vägen dit att varje produkt Smako planerar med bär sin egen
deklaration (näring per 100 g/ml och ingredienslista), hämtad med produkten.

## Var deklarationerna finns per kedja

| Kedja | Källa | Läses in |
|---|---|---|
| Coop | Katalograden (`nutrientInformation`, `nutrientLinks`, `listOfIngredients`) | Ja, sedan tidigare |
| City Gross | Katalograden från `/api/v1/Loop54/products`: GS1-fältet `foodAndBeverageExtension` (`nutrientInformations`, `ingredientStatement`) och `markings`. I produktion ligger källan per butik i `citygross-municipal/<kommun>/attempts/.../collection/<butik>/own.sqlite` med `raw/` bredvid, inte i huvuddatabasen | **Ja, från denna ändring** |
| Willys/Hemköp | Katalograden saknar deklaration; den finns i produktsidan `/axfood/rest/p/{kod}` | Läsare finns; i produktion är `AXFOOD_PRODUCT_DETAIL_ROOT` inte satt och arkivet har 103 dokument |
| ICA | Erbjudandesidan har bara EAN, namn och pris | Nej; ingen deklaration i hämtad data |
| Lidl | Erbjudanden | Via befintligt GTIN-/leverantörsregister där det finns |

## City Gross (läses nu)

Katalograderna som redan samlas in innehåller leverantörens GS1-deklaration. De
sparade raderna i `grocery_data/tests/fixtures/citygross/municipal-promotion-evidence-20260923.json`
(oförändrade publika rader för butik 3211) visar formen. Regler i
`personal_source_facts._citygross_nutrition`:

- `preparationState` är 0 både för torr och tillagad deklaration (buljong:
  318 och 6 kcal/100, båda 0). Därför gäller i stället: deklarationens enhet
  måste vara varans egen (g/ml), förpackningar som "200G/5L" (koncentrat som
  ger en volym) får ingen deklaration, och en torr basvara med SLV-referens
  (ris, pasta, linser …) under 60 % av referensens kcal räknas som tillagad
  (t.ex. jasminris 136 kcal/100 g) och blir okänd.
- En per-100-deklaration väljs före portionsdeklarationen; finns bara en
  mätbar deklaration räknas den om till 100. Flera eller oklara ger okänt.
- `measurementPrecision` 0 är ett deklarerat värde. Annat (t.ex. "<0,5 g") blir
  en gräns i `nutrition_limits`, aldrig ett värde.
- Samma energikontroll som Coop/Axfood: kJ och kcal måste stämma (max 8 kJ
  eller 8 %) och högst 1000 kcal/100 g. Annars är kcal okänt och konflikt anges.
- Tomma platshållare på icke-mat (bas 0, inga näringsämnen) är ingen konflikt.
- `markings` är samma GS1 T3777-koder som Coops `accreditedTags`
  (`KRAV_MARK`, `EU_ORGANIC_FARMING`, `KOTT_FRAN_SVERIGE` …).
- Ingredienslistan är bevis för Ät inte och djurprodukter, aldrig ett bevis för
  att allergener saknas (`ingredients_complete` förblir falskt).
- City Gross deltar nu i den befintliga exakta GTIN-kopplingen mellan kedjor.

Uppmätt på produktionsdata 2026-11-16 (Malmö, butik 3211, 13 986 varor, aktiv
universe): 6 582 varor får näring och 9 794 ingredienslista. Spärrar: 1 238
oklara baser, 486 fel enhet, 210 koncentrat, 69 misstänkt tillagade, 78
kJ/kcal-konflikter. Faktaberäkningen för Malmö tog 32 s (cachas sedan).

Effekt i den frysta Malmö-referensen (52 butiker, 344 receptingredienser): 50
ingredienser har minst en vara med näring i dag. 263 har minst en City
Gross-kandidat (4 019 kandidatrader) och får deklaration om raderna i produktion
har fältet som de sparade raderna. Detta måste räknas på serverns katalograder
innan siffran används. Faktaprojektionen växer med ungefär 50 MB för 13 600
City Gross-varor. `FACTS_VERSION` är höjd så att gamla projektioner byggs om.

## Willys och Hemköp (förberett, kräver beslut)

Hämtaren (`scripts/fetch_axfood_product_details.py`), arkivet och läsaren finns.
Nytt: `backend/scripts/axfood_detail_priority.py` ordnar koderna efter vad
receptbiblioteket behöver (varor utan deklaration, mest använda ingredienser
först). Hemköp-koder som också står i Willys-listan tas bort, eftersom läsaren
använder Willys-dokumentet för samma artikelkod. Hämtaren tar listan med
`--priority-codes`; den godkända katalogkön och dess bevis är oförändrade och
bara ordningen ändras.

Körd 2026-11-16 från ägarens dator (som Willys-reläet), 1/s respektive 0,1/s,
med prioritetslistor från aktiva Malmö- och Lund-universum och godkända
kataloger Willys 2114 och Hemköp 4247. Ny release
`f87b8df135a7245c136038bfbdc35a35f55d35566dab602a1146006b94507652`:
2 822 verifierade Willys-dokument (167 saknas) och 505 Hemköp (110 saknas),
mot tidigare 111 och 12. Den ligger på servern under
`grocery/axfood-product-details/releases/` men är **inte aktiv**: bytet sker
genom att `AXFOOD_PRODUCT_DETAIL_ROOT` i app och scheduler pekar på den nya
releasen vid nästa appbyte (i dag satt i `overrides/beta-all-2b65533af00d.json`).

I Malmö-referensen blev det 3 055 Willys-koder (cirka 51 minuter vid 1 anrop/s)
och 702 Hemköp-koder (cirka 2 timmar vid 0,1 anrop/s).

Föreslagen drift (körs inte från molnsessioner):

1. Räkna City Gross-rader med deklaration på servern (endast läsning).
2. Skapa prioritetslistor från aktiv PriceUniverse och dess fakta.
3. Hämta Willys och sedan Hemköp med `--approved-snapshot`, `--priority-codes`,
   `--base-release` och `--publish` under det delade driftlåset.
4. Montera releasen read-only och sätt `AXFOOD_PRODUCT_DETAIL_ROOT` i ett
   separat godkänt appbyte enligt `docs/releases/axfood-reader-20261023/PROPOSED.md`.
5. Upprepa var 30:e dag (befintlig journal sköter omprövning).
