# Konkreta före/efterexempel

Kontrollerat 21 september 2026 cirka 09:44 Europe/Stockholm. Alla nedanstående
aktuella annonser har källdatum **21–27 september 2026**. Före = föregående
parser körd offline på samma sparade färska svar; efter = slutkodens isolerade
import. Detta är inte en jämförelse av två aktiva produktionsmanifest.

| Butik / annons | Före | Efter | Officiell källa |
|---|---|---|---|
| Flöjtvägen: Coop färsk pasta fettuccine, 300 g, 15 kr | Kortpris läst men datum null och ingen exakt strukturerad variantkoppling | Publikt kampanjköp, exakt 300 g-variant, ordinarie null, 21–27/9; 1 förpackning kostar 15 kr, audit PASS | [Flöjtvägen](https://www.coop.se/butiker-erbjudanden/coop/coop-flojtvagen/), annons `1297-42361-1140058`, variant `7340011392347` |
| Bulltofta: John’s Selection (Irland) nötfärs 20%, 500 g, 59,90 kr | Medlemspris och maxtext i kortet, men datum null och utan exakt strukturerad variant | Medlemsavtal med max 3 förpackningar/hushåll, 21–27/9, ordinarie null. Ett paket 59,90 kr; två 119,80 kr. Medlemskap av och fyra paket blockeras; audit PASS för tillåtet köp | [Bulltofta](https://www.coop.se/butiker-erbjudanden/coop/coop-bulltofta/), annons `1267-36480-1138433`, variant `7392055078800` |
| Flöjtvägen: Arla Bregott, 350–500 g, 39,90 kr | Gruppkort med förpackningsintervall; synlig extra villkorstext tappad | Sex uttryckliga varianter med respektive 350/500 g, medlemskap, datum och ”Gäller ej ekologiskt”; bevarat gemensamt köpavtal. I isolerat PU, inte påstått valt i meny | [Flöjtvägen](https://www.coop.se/butiker-erbjudanden/coop/coop-flojtvagen/), titel ”Bregott” |

Prisroller: Bulltoftas aktuella Glitterset 199 kr blev tidigare ordinarie
`regular_price=199`. Nu bevaras källans `Regular Price` och köppris 199 i ett
datumbegränsat SourceOffer, medan ordinarie pris är null. Köp blockeras av
styckkontrakt och oklara `isPil`, inte felaktigt globalt godkänt. Historiska Shot
33 kr från 20/9 har också en verklig regression: fel ordinarie roll rättad,
men ingen påhittad kampanjperiod och ingen aktuell import från gammalt kort.

Vetemjöl från båda butikerna: **2 för 26 kr, 2 kg/st**. Gruppvillkoret och
datumen går hela vägen till korrekt checkout, men audit stoppar receptköpet
på låg taxonomisk säkerhet. Ordinarie restpris förblir null.

Individuella publika annons-URL:er saknas i denna källa. Länkarna går till rätt
fysisk butik; titel och exakt käll-ID anges för återfinnande. Ovanstående
variantnummer behandlas som opaka Coop-ID:n, inte som verifierade GTIN.
