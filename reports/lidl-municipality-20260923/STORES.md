# Lidl: butiker och källbelagda erbjudanden, 23 september 2026

Nationell officiell sitemap: 212 butiksdetaljer, samtliga hämtade. Samma SCB-geometri gav Lund 2 innanför/210 utanför och Malmö 8 innanför/204 utanför. Ingen okänd eller misslyckad inventeringsrad i denna nätkörning. Fel-/okändfall bevaras av koden och prövas med märkta testinjektioner. [Alla upptäckta rader](all-stores.json).

Varje vald butik nedan har tre godkända `offers_only`-poster. 380 är det gemensamma strukturerade källflödets poster, inte 380 butiksspecifika eller nationellt bevisade priser. Bara tre har granskad produktkoppling till den aktuella nationella kampanjen. Övriga 377 ligger utanför köpimporten med radorsak. Ingen fullkataloghälsa påstås: den ursprungliga låga täckningsgraden behålls i mätningen.

| Kommunkod | Officiell butik / TNC-ID | Kommunstatus | Hämtade kandidatposter | OWN | PriceUniverse | Karantän | Köpverifiering |
|---|---|---|---:|---:|---:|---:|---|
| 1281 | [Lidl Åkerlund och Rausings väg 1](https://www.lidl.se/s/sv-SE/butiker/lund/akerlund-och-rausings-vaeg-1/) — 0303 | innanför | 380 | 3 | 3 | 377 | 2 källbelagda köp godkända |
| 1281 | [Lidl Magistratsvägen 6](https://www.lidl.se/s/sv-SE/butiker/lund/magistratsvaegen-6/) — 0163 | innanför | 380 | 3 | 3 | 377 | 2 källbelagda köp godkända |
| 1280 | [Lidl Hyllie Kyrkoväg 45A](https://www.lidl.se/s/sv-SE/butiker/limhamn/hyllie-kyrkovaeg-45a/) — 0193 | innanför | 380 | 3 | 3 | 377 | 2 källbelagda köp godkända |
| 1280 | [Lidl Delsjögatan 3](https://www.lidl.se/s/sv-SE/butiker/malmoe/delsjoegatan-3/) — 0167 | innanför | 380 | 3 | 3 | 377 | 2 källbelagda köp godkända |
| 1280 | [Lidl Knivgatan 1B](https://www.lidl.se/s/sv-SE/butiker/malmoe/knivgatan-1b/) — 0153 | innanför | 380 | 3 | 3 | 377 | 2 källbelagda köp godkända |
| 1280 | [Lidl Östergatan 12](https://www.lidl.se/s/sv-SE/butiker/malmoe/oestergatan-12/) — 0340 | innanför | 380 | 3 | 3 | 377 | 2 källbelagda köp godkända |
| 1280 | [Lidl Södra Förstadsgatan 124](https://www.lidl.se/s/sv-SE/butiker/malmoe/soedra-foerstadsgatan-124/) — 0145 | innanför | 380 | 3 | 3 | 377 | 2 källbelagda köp godkända |
| 1280 | [Lidl Spångatan 11](https://www.lidl.se/s/sv-SE/butiker/malmoe/spangatan-11/) — 0284 | innanför | 380 | 3 | 3 | 377 | 2 källbelagda köp godkända |
| 1280 | [Lidl Torupsgatan 2](https://www.lidl.se/s/sv-SE/butiker/malmoe/torupsgatan-2/) — 0314 | innanför | 380 | 3 | 3 | 377 | 2 källbelagda köp godkända |
| 1280 | [Lidl Västra Varvsgatan 42](https://www.lidl.se/s/sv-SE/butiker/malmoe/vaestra-varvsgatan-42/) — 0330 | innanför | 380 | 3 | 3 | 377 | 2 källbelagda köp godkända |

## Samma belagda nationella kampanj i samtliga tio butiker

[Officiellt aktuellt reklamblad](https://www.lidl.se/l/sv/reklamblad/gaeller-21-9-27-9-i-alla-butiker-erbjudanden-vecka-39/ar/0), 21–27 september. Officiell metadata anger samtliga butiker i Sverige. Detta omfattar endast följande granskade produkter, inte hela regionflödet.

| Produkt / käll-ID | Förpackning | Köppris | Villkor |
|---|---|---:|---|
| [SOL&MAR Majssnacks ost & bacon / 11137878](https://www.lidl.se/p/sol-mar-majssnacks-ost-bacon/p11137878) | 100 g | 9,90 kr | Publikt erbjudande. Bladet visar ett frånpris; strukturerad exakt variant anger 9,90. Ingen prissänkning eller ordinarie köppris påstås. |
| [Culinea Hamburgare / 11214016](https://www.lidl.se/p/culinea-hamburgare/p11214016) | 1,8 kg, nöt, 85 % kötthalt | 159 kr | Allmänt Lidl Plus-pris, högst två förpackningar per hushåll över recept och butiker. |
| [Pågen Lingongrova / 11218552](https://www.lidl.se/p/paagen-lingongrova/p11218552) | 500 g | 17,90 kr | Allmänt Lidl Plus-pris. Ingen ytterligare köpgräns belagd. |

För alla tre: ordinarie köppris är okänt/null. Överstrukna priser är inte ordinarie köppriser. Källans datumfönster bevaras. Ingen pant är tillämplig för dessa verifierade förpackningstyper; detta generaliseras inte till drycker. Kampanjgiltighet är inte lagergaranti.

Produktbindningen bygger på exakt varumärke, namngiven variant och förpackning i dokumenttext samt en unik strukturerad produkt med explicit EAN. Reklambladet har inga produktobjekt eller produkt-EAN-join; identitetsgranskningen och dokumenthashen är därför uttryckligen låsta. Se `grocery_data/app/connectors/lidl/fixtures/municipal_document_text_20260923.json` och `current-publication.json`. Inga bilder analyserades.

## Köp och produktfakta

Representativa köp av Lingongrova och hamburgare har körts genom ProductMatcher, medlemsprissättning, BasketCalculator och BasketAuditor för varje fysisk butik. Utan Lidl Plus blockeras dessa två köp när ordinarie pris saknas. Två hamburgerförpackningar i två butiker kostar 318 kr; en tredje förpackning i ytterligare recept/butik blockeras.

[Pågens deklaration via Dabas](https://www.dabas.com/productsheet/07311071330525) har exakt GTIN 07311071330525 och 500 g. Deklarationen anger per 100 g som såld 266 kcal, 8,8 g protein, 3 g fett och 47 g kolhydrat. Den separata deklarationens observationstid och version bevaras. Hamburgare och majssnacks har inte fått gissade näringsvärden eller generell receptbehörighet. Hamburgare godkänns inte som rå nötfärs; snacks med ostsmak godkänns inte som ost.

Pris-/köpkvittenser: `runtime-final-1280/purchases.json` och `runtime-final-lund/purchases.json`. Sammanställningen av publicerings- och uppdateringsprov finns i RUNTIME.md.
