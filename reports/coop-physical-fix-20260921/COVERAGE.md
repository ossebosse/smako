# Slutlig täckning – Coop fysisk offers_only

Verklig insamling 21 september 2026 kl. 09:44 Europe/Stockholm. Två uttryckligt
valda butiker ur befintlig inventering; detta är inte en kommunfullständig körning.
Kommunernas okända butikstillhörigheter är oförändrade. Ingen produktionsaktivering.

| Butik | Annonsgrupper i källan | Extraherade varianter | Radgodkända | Karantän | Isolerad OWN | Isolerat PU | Observerat Stockholm |
|---|---:|---:|---:|---:|---:|---:|---|
| Coop Flöjtvägen (3839) | 22 | 135 | 44 | 91 | 44 | 44 | 2026-09-21T09:44:43.497257+02:00 |
| Coop Bulltofta (3815) | 56 | 356 | 68 | 288 | 68 | 68 | 2026-09-21T09:44:48.383861+02:00 |

Totalt 78 annonsgrupper / 491 källvarianter, 112 radgodkända och 379 i karantän.
Kategoridubbletter och gruppförälder räknas inte en gång till. Bulltoftas DOM
hade 55 penningpriskort men källan 56 grupper: den extra gruppen innehåller
74 varianter med 20% rabatt utan verifierad prisgrund. Dessa finns kvar som
extraherade prisuppgifter och i nämnaren, inte som köppris på 20 kr.

Full parserläsning: 135/135 respektive 356/356 utan parserfel. Efter köpvalidering
44/135 = 32,59% och 68/356 = 19,10%. Fullsnapshot är därför fortsatt `broken`,
inte godkänd mot 95%. Tröskel och nämnare är oförändrade. Endast det uttryckliga
partiella radkontraktet publicerades i isolerad OWN, med alla bortfall synliga.
Ingen aktiv beta-PriceUniverse har ändrats. Isolerat ID: `price-universe:f1d420611279a85cf6e3cbcdf812ca2711a2ee1cbb2f81fad1eb020ae781d9b4`.

Tidigare audit 20 september hade 70 textkort och **0 verifierat nya köpklara
importer**. Den hade andra kampanjer; 70 får inte jämföras direkt med dagens
491 variantposter. `before-parser-comparison.json` kör i stället gamla parsern
offline mot exakt dagens råsvar: 22 respektive 55 kort, med tappade datum och
utan strukturerad variantidentitet. Det är inte ett mått på aktiva betapriser.

De 112 posterna är nya i denna tomma isolerade databas, inte bevisligen 112 nya
eller billigare marknadserbjudanden. Den sista lokala ombyggnaden återanvände
samma råsvar och förnyade inga observationer. Tidigare försökskataloger behålls
som historik; `final-live` misslyckades på Bulltoftas nya schemafält och är inte
slutacceptansen. Slutkodens underlag är `final-live-v2` och `final-acceptance-v2`.

## Kvarstående hinder

Antal per orsak överlappar; summera inte orsaker som om de vore olika poster.
Varje exakt berört käll-/variant-ID, råreferens och felorsak finns i
`quarantine.json` och fullständiga råfält i butikens `*-extracted.json`.

### Coop Bulltofta

- `fixed_purchase_package_unverified`: 18 varianter.
- `deposit_amount_unverified`: 30 varianter.
- `mixed_variant_group_checkout_unsupported_without_ordinary_price`: 191 varianter.
- `purchase_price_role_unverified`: 74 varianter.
- `piece_purchase_contract_not_supported`: 62 varianter.
- `bounded_checkout_contract_unverified`: 74 varianter.
- `source_is_pil_requires_review`: 13 varianter.
- `approximate_package`: 3 varianter.

### Coop Flöjtvägen

- `fixed_purchase_package_unverified`: 14 varianter.
- `mixed_variant_group_checkout_unsupported_without_ordinary_price`: 84 varianter.
- `deposit_amount_unverified`: 36 varianter.
- `approximate_package`: 1 varianter.

Okänd pant avser källtexten ”Pant tillkommer.” utan belopp; varken noll eller
standardpant antas. Osäkra gruppblandningar och ungefärliga/viktbaserade köp
behåller källpriset men går inte in i köpunderlaget. Fem enstaka styckvaror
saknar befintligt korrekt paketköpsstöd. Procentraderna kan dessutom ha samma
styckkontraktsproblem; därför överlappar antalen.

Den sena schemakontrollen hittade `isPercentageDiscount` och `isPil` i verklig
Bulltofta-data. Procentflaggan bevaras och hindrar penningprisförväxling.
`isPil` finns på 13 varianter i nio annonser; betydelsen är inte säkert verifierad.
Alla 13 köpblockeras, varav nio annars hade godkänts. Därför är slutantalet
68, inte tidigare preliminära 77. Källa och priser finns kvar för granskning.

## Checkout, audit och receptnytta

Sex verkliga köpfall kördes: pasta 300 g / 15 kr och nötfärs 500 g / 59,90 kr
(Coop-medlem, max 3 förpackningar/hushåll) klarar både checkout och audit i
båda butikerna. Mjöl: exakt två 2 kg-förpackningar för 26 kr, ingen tillåten
singelförpackning för 13 kr. Priset och mängden stämmer, men audit säger nej
på låg semantisk säkerhet för ingrediensklassificeringen. Hindret har inte
rundats. Se de sex `proof-*.json` i slutacceptansen.

Matcher→checkout→audit för pasta verifierades även i verkliga källfixturtester,
liksom medlemskap av/på, maxgräns över alias och ogiltiga kampanjdagar.
PriceUniverse har 31 varianter med hög taxonomisk säkerhet (9 + 22); detta är
**inte** 31 verifierat näringsgodkända receptprodukter. Ingen full näringsbegränsad
15/20-körning gjordes i denna avgränsade rättning och ingen besparing hävdas.

Färsk insamling: 11.441 s. Slutkodens isolerade ombyggnad och
sex checkout/audit-fall: 3.457 s. Python 3.12 på befintlig
Windowsmiljö, befintlig Playwright Chromium. Serverruntime är inte verifierad
av detta prov. Ingen bildanalys, modellkostnad, ny prenumeration eller driftändring.
