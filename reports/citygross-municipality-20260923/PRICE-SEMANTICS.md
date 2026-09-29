# City Gross prissemantik, 23 september 2026

Alla exempel är butiksspecifika `online_price` från den offentliga Loop54-katalogen. Den fysiska butikens `siteId` och onlinekatalogens `storeNumber` bevaras separat. Detta underlag visar inte att priserna gäller fysisk hyllkant. Samma pris i två butiker nedan är verifierat i respektive butiks eget svar; inget pris kopieras mellan butiker.

I OWN/PriceUniverse uttrycks fullkatalogens kanal genom `source_channel=catalog`,
`source_role=basket`, `price_context=online_store` och `coverage=full_online_catalog`.
Katalogetiketten tar alltså inte bort det uttryckliga beviset för onlinekontext.

## Fynd och rättning

CityGrossParser v4 återanvänder SourceOffer, normalisering, OWN och befintliga PriceContract/checkout. Katalogens redan hämtade kampanjer tappades för `type=1`, `effectType=ItemsTotal`, `minQuantity=1`: de blev OTHER. En uttrycklig 1-varugrupp blir nu publikt enkelkampanjpris eller medlemspris, medan grupper om minst två varor förblir flerköp. Endast `activePromotion` får ändra aktuell prisroll. Ordinarie köppris, kampanjpris och medlemspris bevaras separat.

| Butik | Faktiska råprodukter | Tidigare tappade ItemsTotal×1 | minAmount=300, spärrade rabattavtal | Källobservationer UTC |
|---|---:|---:|---:|---|
| Malmö Hyllie 3211/site 169 | 13523 | 254 | 11 | 2026-09-23T08:04:51.365362+00:00 – 2026-09-23T08:07:07.369337+00:00 |
| Staffanstorp 3229/site 11 | 13780 | 248 | 11 | 2026-09-23T08:07:38.127747+00:00 – 2026-09-23T08:10:02.292326+00:00 |

Hyllies 254 enkelkampanjer var alltså hämtade men inte bevarade som kvalificerade kampanjavtal. Exempel: Grillkorv med Skinn 640 g (`100308301_ST`), 39,95 kr 21–27/9, ordinarie 47,95 kr. Regressionen använder faktisk sparad råpost.

Elva Libero-varianter per butik anger medlemskap och ett minsta köpbelopp på 300 kr. Det villkoret stöds inte av befintligt köpavtal och tas därför inte bort: råkampanjen bevaras som OTHER med `minimum_spend_unsupported`, rabattpriset får inte användas, och belagt ordinarie köppris ligger kvar. OWN stoppar OTHER före medlemsprisgrenen. CouponId, okänt medlemsvillkor, ogiltigt köptak och saknad giltighetsperiod blir också icke-köpbara rabattavtal; ett aktivt osäkert rabatterat currentPrice kan inte bli ordinarie pris.

Full audit av båda faktiska råkatalogerna: 27 303 produkter kunde parsas utan parsefel. Hyllie har 1 215 flerköp, 263 enkelkampanjer, 17 medlemsprisavtal och 11 blockerade OTHER; Staffanstorp 1 216, 264, 11 och 11. Räknarna gäller produkt–kampanjkopplingar och är inte antal unika kampanjer. Se [maskinell fullaudit](price-semantics-source-audit.json).

## Köpbegränsningar och källbevarande

`maxAppliedPerReceipt` behåller befintlig betydelse: maximalt antal rabatterade paket för enkelpris respektive rabatterade grupper för flerköp. `maximumQuantity` är ett separat tak för antal försäljningsenheter i den offentliga butikens varukorg; det ersätter aldrig rabattaket. [Officiellt frontendkontrakt](https://www.citygross.se/static/js/main.07a64bf6.js) kopplar fältet till kvantitetsväljaren och skickar antal med `unit="Piece"`. Utdrag, källhash och tid finns i [källbevis](live-offers-probe/maximumQuantity-evidence.json). Inget inloggnings-/varukorgsanrop utfördes.

`maximum_purchase_units`, `official_product_url` och `quantity_limit_source_url` bevaras i SourceProvenance genom PriceUniverse och köp. Befintlig BasketCalculator och audit avvisar överskridet tak även när samma produkt fördelas på flera receptingredienser. 25/26-gräns, flerköpets separata rabattak och manipulerad korg verifieras. Viktpris utan belagt antal försäljningsenheter spärras vid sådant tak; kg omtolkas inte som paket.

Parsern bevarar full `raw_prices`, `raw_promotion`, minAmount, couponId, originalgränser, datum, onlinekanal, butik, produkt-/variant-ID, GTIN, URL och förpackning i OWN:s interna källunderlag. Konsumentgränssnittet exponerar validerade säkra prisfält och provenance, inte obearbetade källpayloads. Jämförpris och lowestPriceLast30Days blir inte köppris.

## Offers-only när full katalog saknas

`CityGrossRowApprovedOfferConnector` återspelar faktiskt hämtade, butikskontrollerade katalogsidor utan nya nätanrop eller ändrade observationstider. Den använder ordinarie parser, gemensam `partial-row-approved-offers-v1`, radvalidering, collector och OWN. En aktiv, känd, daterad PCE-kampanj för exakt GTIN/variant/förpackning kan publiceras separat med coverage `offers_only` och fortsatt onlinekanal. Baspris görs inte tillgängligt från denna partiella källa. Ofullständig helkatalog, ursprungliga transportfel och karantän finns kvar i bevisen; inga fullhetsgrindar sänks.

Den separata offentliga `/api/v1/offers?store=3211&size=100&currentweekoffer=true`-proben gav HTTP 200 och total=0. Det betyder inte att Hyllie saknar erbjudanden: samma tillfälles 100 katalogprodukter hade fyra kampanjer. Ingen separat fysisk erbjudandeimport är belagd av det svaret.

## Aktuella belagda exempel

Alla exempel har publika villkor (ej medlemskrav eller minsta köpbelopp), källans `maxAppliedPerReceipt=0` (inget uttryckligt rabatttak) och separat varukorgstak 25 försäljningsenheter. Exakt köp av flerköpets antal krävs för det angivna grupppriset. Produktlänken kräver rätt vald butik för visat sortiment; råkällan binder varje pris till storeNumber. Datum är källans lokala kalenderdatum.

### [Malmö Hyllie](https://www.citygross.se/butiker/hyllie) – storeNumber 3211, siteId 169, kommun 1280

| Produkt / variant | Förpackning och pris | Giltighet | Kampanj-ID | Observation UTC |
|---|---|---|---|---|
| [BARILLA Lasagneplattor](https://www.citygross.se/matvaror/skafferiet/pasta-ris-och-mos/barilla-lasagneplattor-p100058571_ST) · 100058571_ST · GTIN 8076809523738 | 2 × 500G för 42 kr; ord. 22.95 kr/paket | 2026-09-07–2026-10-04 | 1615919,2500314227 | 2026-09-23T08:04:51.365362+00:00 |
| [GARANT EKO Basmatiris](https://www.citygross.se/matvaror/skafferiet/pasta-ris-och-mos/garant-eko-basmatiris-p101362902_ST) · 101362902_ST · GTIN 7340083496332 | 1KG för 44.95 kr; ord. 49.95 kr/paket | 2026-09-07–2026-10-04 | 1615868,2500314049 | 2026-09-23T08:05:50.885827+00:00 |
| [ZETA Spaghetti](https://www.citygross.se/matvaror/skafferiet/pasta-ris-och-mos/zeta-spaghetti-p101807605_ST) · 101807605_ST · GTIN 7350027796084 | 2 × 400G för 22 kr; ord. 12.95 kr/paket | 2026-09-21–2026-09-27 | 1630449,2500318762 | 2026-09-23T08:06:47.335731+00:00 |

### [Staffanstorp](https://www.citygross.se/butiker/staffanstorp) – storeNumber 3229, siteId 11, kommun 1230

| Produkt / variant | Förpackning och pris | Giltighet | Kampanj-ID | Observation UTC |
|---|---|---|---|---|
| [BARILLA Lasagneplattor](https://www.citygross.se/matvaror/skafferiet/pasta-ris-och-mos/barilla-lasagneplattor-p100058571_ST) · 100058571_ST · GTIN 8076809523738 | 2 × 500G för 42 kr; ord. 22.95 kr/paket | 2026-09-07–2026-10-04 | 1616925,2500314227 | 2026-09-23T08:07:38.127747+00:00 |
| [GARANT EKO Basmatiris](https://www.citygross.se/matvaror/skafferiet/pasta-ris-och-mos/garant-eko-basmatiris-p101362902_ST) · 101362902_ST · GTIN 7340083496332 | 1KG för 44.95 kr; ord. 49.95 kr/paket | 2026-09-07–2026-10-04 | 1616874,2500314049 | 2026-09-23T08:08:38.642104+00:00 |
| [ZETA Spaghetti](https://www.citygross.se/matvaror/skafferiet/pasta-ris-och-mos/zeta-spaghetti-p101807605_ST) · 101807605_ST · GTIN 7350027796084 | 2 × 400G för 22 kr; ord. 12.95 kr/paket | 2026-09-21–2026-09-27 | 1630473,2500318762 | 2026-09-23T08:09:42.841013+00:00 |

Varje exempels fullständiga råreferens finns i [offer-examples.json](offer-examples.json). Ingen återobservation är konstruerad vid replay.

## Verifiering och säkerhetskopior

Riktade parser-/offers-only-/OWN-/köptaksregressioner använder märkta fixtures och faktisk sparad källa. De är offline/replay, inte nya nätanrop. Exakta sluttesttal redovisas i huvudrapporten. Parser v4 är slutversion för kommunreplay.

Förändrade befintliga filer säkerhetskopierades före redigering: `grocery_data/app/connectors/citygross/parser.py`, `connector.py`, `grocery_data/app/services/offer_rows.py`, `backend/app/services/basket_calculator.py`, `basket_auditor.py`, under `backups/` med samma sökvägar. `row_approved_offers.py`, semantik- och köptakstester samt evidensfixture är nya filer. ICA/Coop/X:-tra/Willys-priser, Primat, produktion, Windows och aktiva scheman har inte aktiverats eller ändrats av denna semantikdel.
