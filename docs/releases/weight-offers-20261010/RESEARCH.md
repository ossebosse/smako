# Bevarade källbelägg och kvarstående luckor

Prisartefakt `price-universe:50c0bb0e83de94803b9eb6d06576cbe653e29a5f5d7a43abc5af9117c721cd5a`,
SHA-256 `a7255fb2ffeb810ff883c1247e1be65a59d5291ca2a858e6cbb059c6a3456f6f`.
Coop snapshot `8d1dba204e45414e96be4501fad38b2a`, butik 730400,
`online_fulfillment`, Coop Online Syd. Både artefakt och två refererade
originalråfiler lästes och SHA-256 verifierades. Ingen ny prishämtning.

Endpoint: POST `https://external.api.coop.se/personalization/search/entities/by-attribute`.
Autentiska tider, filstorlekar, sökvägsreferenser och fulla hashvärden finns i
EVIDENCE.json; råfiler ligger skyddat utanför Git.

| Produkt | Råreferens | Hämtning UTC | Belägg |
|---|---|---|---|
| Satsumas | `raw:98ce14924b29416ebe34b9b9226dd7#results.items[1]` | 2026-10-09 13:31:56.782848 | GTIN 2317302900005, cirka 140 g, försäljning per vikt, aktivt kampanj-ID 016001_144265, 20 kr/kg medlemspris. |
| Scan Fläskytterfilé | `raw:bf48747abff546d2be6d2ef663d37e23#results.items[7]` | 2026-10-09 13:33:04.893007 | GTIN 2320321600009, cirka 950 g, 105 kr/kg, tomma aktiva och undanhållna kampanj-ID-listor. |

Källan anger ST-beställning och ungefärlig vikt för Satsumas. Därför behålls
heltalsstycken i beräkningen; 1 000 g omtolkas inte till fritt exakt uppvägd mängd.
Normaliserade DB-rader innehåller representativa styckkostnader 4,186 respektive
99,75. Befintlig provider återläser källans 29,90 respektive 105 kr/kg korrekt
i den serverade artefakten. Ingen extra kg-konvertering infördes.

## Öppna konkreta ärenden

1. **Scan 65 kr/kg i användarens Coop-blad, 5–11 oktober.** Behöver belagd
   kampanjidentitet, exakt produkt/variant, butik/priskontext, medlemsvillkor,
   eventuell köpgräns och datum för den kontext som ska användas. Kontrollerat:
   användarens blad, serverad artefakt, normaliserad/source-produktrad,
   refererat originalråsvar och sökresultat. Det finns inget belägg att den
   fysiska bladkampanjen gäller Online Syd. Frånvaron i detta råsvar bevisar
   inte att kampanjen saknas i alla Coop-butiker. Ingen överföring efter namn.
2. **29 begränsade viktprisrader**, individuellt listade i WEIGHT-BLOCKERS.json.
   Saknat kontraktsstöd: vad begränsningen räknar (paket, vikt, köpgrupp) och
   giltigt restpris efter gränsen. Kräver variant-/källbundet belägg innan
   ordinarie PurchaseTerms kan kompletteras; sänk inte kontrollen.
3. **Övriga 957 okända köpmodeller och 404 öppna variantgrupper.** Inventering
   med exakta produkt-/butiks-ID:n finns i lokala comparison-inventory.json.
   Nästa arbete ska prioritera verkliga användarbehov och respektive saknat
   mängd-/variantfält. Antal synliga kampanjrader är inte antal räddade recept.
