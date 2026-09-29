# Verklig 15/20-jämförelse, 22 september 2026

Samma kompletta källdatabas och Primat-cache, oförändrad originalbegäran, medlemskap av och max två inköpskontexter. Prisdag 2026-09-22, Europe/Stockholm.
Basarmens 106 genererade recept fryses som indata för B. Planeraren, matcharen, näringsprövningen, checkout och audit körs på riktigt via HTTP i båda armarna. Ingen modell eller betald API-tjänst.

| Mått | A utan kommun-Coop | B med kommun-Coop |
|---|---:|---:|
| Kostnad, kr | 536.27 | 536.27 |
| Planeringsanrop, sekunder | 40.44 | 43.731 |
| Bygg + fakta + HTTP, sekunder | 215.421 | 234.415 |
| Måltider | 15 | 15 |
| Portioner | 20 | 20 |
| Inköpskontexter | 2 | 2 |

**Kostnadsskillnad: 0.00 kr. Inga nya fysiska Coop-rader valdes.**

Båda väljer Coop Online Syd och Willys Lund. Coop Online är online_fulfillment, inte fysiskt hyllpris eller bevis om en viss fysisk Coop-butik. Inga nio fysiska butiker slås ihop med Online. Profilens befintliga kanalval är oförändrat; resultatet är inte ett prov med enbart fysiska butikskanaler.

## Valda produkter

Samma produkt-ID, butik, kvantitet och debitering i båda armarna verifieras i selected-products.json.

| Kanal/butik | Produkt | Köpta förpackningar | Förpackning | Radkostnad kr |
|---|---|---:|---|---:|
| Coop Online Syd | Knäckebröd Husman | 1 | 520.0 g | 15.62 |
| Coop Online Syd | Tomater Krossade | 2 | 390.0 g | 15.68 |
| Coop Online Syd | Kvarg Naturell 0,3% | 5 | 500.0 g | 97.50 |
| Coop Online Syd | Röda linser Hela | 1 | 900.0 g | 29.29 |
| Coop Online Syd | Riven ost Cheddar | 1 | 150.0 g | 19.50 |
| Coop Online Syd | Spaghetti | 1 | 1000.0 g | 13.95 |
| Willys Lund | Torskfilé | 2 | 400.0 g | 187.80 |
| Willys Lund | Kycklingfilé 2-delad Frysta | 1 | 800.0 g | 75.61 |
| Willys Lund | Morötter Klass 1 | 1 | 1000.0 g | 14.90 |
| Willys Lund | Äggnudlar | 2 | 250.0 g | 18.72 |
| Willys Lund | Långkornigt Ris | 1 | 1000.0 g | 19.90 |
| Willys Lund | Vitkål Strimlad Klass 1 | 2 | 400.0 g | 27.80 |

## Näring och verifiering

493 radgodkända priser; 105 har matchning i ingredienspoolen, 93 överlever poolens urval. 22 når faktisk ingrediens-/näringsprövning i den frysta receptpoolen. **0 har verifierat produktbundet näringsunderlag; 0 klarar tillskottets näringsprövning.**
Alla produkt-ID:n, namn, butiker, matchningar och specifika receptbortfall finns i product-qualification.json. Ett pris får finnas kvar trots saknad näring. Vi härleder inte GTIN från sifferliknande käll-ID:n och gissar inga näringsvärden.
Originalprofilen har allow_nutrition_estimates=true, oförändrat i båda armarna. Befintlig källbunden referensnäring i basen är alltså tillåten enligt samma profil; nya deklarationer eller uppskattningar har inte lagts till. 40/30/20 g protein per portion kontrolleras för samtliga måltider.
B:s 332 registrerade verkliga korgkontroller passerar audit. Båda slutkorgarna och samtliga köprader är VERIFIED; HTTP 201, sparning/identisk återläsning, health/ready 200. A:s vanliga basket-anrop har samma obligatoriska audit; B har dessutom explicit anropslogg.

## Tidsmätningens omfattning

En slutlig körning per arm. Ingen statistiskt säker prestandaförbättring eller flerdagarsstabilitet påstås. De tidigare baseline/coop-final-körningarna är pilotkontroller med ekonomiskt genererad receptpool och ersätter inte denna frysta jämförelse.
