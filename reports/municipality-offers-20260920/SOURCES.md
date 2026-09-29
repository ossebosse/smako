# Befintliga flöden och faktiska luckor

Primat, användarprofiler, aktiv källa och ICA-baspriskatalogens paus är oförändrade. Ingen ny prisintegration aktiverades.

| Kedja | Befintlig pris-/erbjudandekedja | Färsk kontroll och exakt stopp |
| --- | --- | --- |
| Willys | `WillysClient` → `WillysParser._offers` → SourceOffer → collector/promotions → OWN provider → PriceUniverse | 2176/2244 aktiverades och lästes tillbaka separat i vanlig anonym session; samma tre detalj-ID:n hämtades separat. 3 offentliga gruppavtal vardera. Alla tre i 2176 finns i aktivt OWN och som äldre produkter i aktivt PU. Inga 2244-poster där. Den första begränsade kategorisidan hade 0 kampanjer, inte bevis på tomt butiksflöde. |
| Hemköp | egen transport och butiks/facet-kontroll, delar produkt-/promotionsprimitive med Willys | 4224/4114: 3 detaljkampanjer vardera utöver första katalogsidan. 4224 redan OWN/äldre PU; 4114 inte aktivt. `potentialPromotions` försvinner inte generellt i importen. Däremot tappas `offerStatus`, `applied`, `productCodes` och flera källvillkor ur SourceOffer. `Vilande` tillsammans med `applied=true` ska inte lösas med ett antagande. |
| Coop fysisk | `CoopBrowserOffersTransport` → sanerat kortkuvert → `CoopParser` → offers_only; separat från online 730400 | 3839: 19 prisrader och 19 avtal; 3815: 51 rader och 43 avtal. Inga parsefel, men inte 70 köpklara produkter. Kortens deklarerade total saknas, transporten använder DOM-stabilitet. Därför är källans fullständighet inte bevisad med en oberoende totalsiffra. |
| Coop online | `CoopOnlineCatalogConnector` → OWN 730400 → provider/PU | Senaste aktiva OWN har 11 344 produkter och 819 promotions, observerade 20/9. Det är **onlinepris i Syd**, inte bevis på hyllpris eller medlemsavtal i Flöjtvägen/Bulltofta. Ny fullcrawl behövdes inte för denna granskning. |
| City Gross | befintlig REVIEW-bounded `CityGrossClient`/Loop54 → parser → SourceOffer | Hyllie `3211`/site `169`: första 30 gav ett avtal; ett avgränsat, tillåtet utökat 100-radersprov gav fyra. Alla 100 parsergodkända, men BOBs `2DL/1L` ger ingen säker fast förpackning. Ingen full katalog eller import hävdas. |
| Lidl | befintlig public-default-region-källa, q/api/search → parser v4 → offers_only | 30 rader på första sidan, 27 parsade, tre avvisade (se sparade failures). Både aktuella och framtida perioder finns. Primär lucka för nya butiksköp är region-/butiksgiltighet och strikta köp-/identitetsvillkor, inte brist på en connector. |

## Coop: förlust av information kan beläggas utan bilder

Två avgränsade omkontroller använde **samma** browsertransport. Ett rapportinstrument fångade bara relevant offentlig datum-/villkorstext som transporten redan läser före sanering. Inga cookies, tokens, personlig inloggning eller bilder lästes. Resultat finns i `coop-3839-date-context.json` och `coop-3815-date-context.json`.

- Sidan visar både **Vecka 38 / Aktuellt reklamblad** och **Vecka 39 / Kommande reklamblad**. Detta bevisar tillgänglig periodinformation på sidan, men binder inte automatiskt varje annons till hela veckan.
- Yoggi 1000 g: full synlig text säger **”Gäller ej laktosfri”**. Den sparade aria-posten saknar undantaget; parsern kan därför inte bevara det. Detta är ett konkret transport-/fälturvalsproblem, inte bildberoende.
- Korten ”Se 3 varor”, ”Se 7 varor” etc sparas med `href=null`. Underliggande variant-ID/GTIN är inte belagda. `SourceProduct.external_product_id` och GTIN kan vara null; matchning till onlineprodukt får inte ske bara på namn.
- Bulltoftas Shot, alkoholfri öl, färdiglagad kyckling, olivolja, senap, yoghurtbägare, Lego och stekpanna blir `regular_price=sale_price` med tom offers-lista. Den annonserade prisuppgiften finns, men aktuellt ordinarie köp efter kampanjen är inte belagt. De åtta raderna är ett konkret första prisrollsproblem.
- Inga av dessa färska fysiska butiksrader finns i aktivt OWN/PU. Uppgifterna har bevarats i rapportens råsvar; de har inte accepterats för checkout.

## Vad som kan sägas om bildberoendet

Strukturerat/textuellt material bevisades för samtliga fem kedjor. En komplett jämförelse med samtliga aktuella reklamblad gjordes inte. Därför anges **okänd bildberoende differens**, inte ”allt kvarvarande finns bara i bilder” eller ”inga luckor”. Befintliga flyer-URL:er finns bland annat i Willys/Hemköps butikssvar. Inga bildmodeller eller betalda API-anrop användes.

## Miljö och blockeringar

Priskontrollerna kördes i Windows Python 3.12, samma tillåtna lokala transporttyp som Willys-reläet. Coop använde installerad Playwright Chromium, utan modell. Hemköp, City Gross och Lidl har här färsk **Windowsverifiering**, inte en ny server-/scheduleracceptans. Befintliga färska server-OWN-källor lästes read-only och verifierar redan fungerande insamling för Coop 730400 och Hemköp 4224; de är inte bevis på serverkörning av de nya provkontexterna.

Hemköp Karhögstorgs tidigare fulltraverseringsfel återförsöktes inte. ICA:s direkta katalog återförsöktes inte. Lantmäteriet: offentlig metadata 200, en enda faktisk geometribegäran 401 Missing Credentials; ingen retry eller alternativ åtkomst för att kringgå kravet.
