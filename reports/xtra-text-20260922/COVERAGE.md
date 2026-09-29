# X:-tra Skansvägen – sid- och annonsvis texttäckning

Verifiering: **2026-09-22T07:46:32.791175+02:00**. Ursprunglig observation: **2026-09-21T17:56:02.943342+00:00**, inte föryngrad.

[Officiell butik](https://x-tra.se/butiker/skansvaegen) · [Officiell PDF](https://dr.coop.se/Butik/?store=216525). Butiks-ID 3658, PDF-konto 216525, Skansvägen 2, Lunds kommun 1281.

PDF SHA-256: `065efd248050a6761a45adad7695186048484f76e9d6d1aebe05f18458c4aa18`. Metadata binder dokumentet till X:-tra Skansvägen. Tryckt v.39: 21–27 september 2026; varje sidas utgåve-ID cx_2639 verifieras. Sida 8 begränsas till torsdag 24–söndag 27 september. Alla åtta sidor finns.

**Partiell täckning.** 57 identifierade textannonser har klassificerats. Antalet eventuella ytterligare bildannonser/okända annonser är okänt, inte noll. Ingen bildanalys, OCR eller extern tjänst används. Textblock, typsnitt och koordinater återges i JSON; en sida med läsbar text är inte bevis på komplett annonsidentifiering.

| Sida | Textannonser/priser | OWN | PU nu | Blockerade köp | Okända ytterligare annonser |
|---|---:|---:|---:|---:|---|
| 1 | 6 | 1 | 1 | 5 | okänt |
| 2 | 12 | 3 | 3 | 9 | okänt |
| 3 | 10 | 2 | 2 | 8 | okänt |
| 4 | 4 | 0 | 0 | 4 | okänt |
| 5 | 5 | 2 | 2 | 3 | okänt |
| 6 | 7 | 1 | 1 | 6 | okänt |
| 7 | 8 | 0 | 0 | 8 | okänt |
| 8 | 5 | 1 | 0 | 4 | okänt |

Totalt 10 importerade i isolerat OWN, 9 i PriceUniverse för 22 september, 1 framtida (Snacktomater), 47 blockerade för köp. Ingen tidigare X:-tra-import finns i det jämförda kommununderlaget: 0 redan täckta. Förkörningar/replay är inte nya prisobservationer eller ytterligare nya annonser.

Fullständigt snapshotkontrakt: **10/57 = 17,54 %**, under oförändrade 95 %. Snapshot är BROKEN; det uttryckliga partiella radkontraktet publicerar endast de tio godkända raderna i isolerad OWN. 57/57 gick att representera som SourceProduct/SourceOffer med råfält; detta är inte 57 godkända köp. Kvalitetsvarningens kritiska larmnivå 70 % är separat från snapshotkravet på 95 %.

## Konkreta köp och källjämförelse

Separat kontrollavläsning av originalets textblock finns i testfixturens `manual-reference.json`. Det är inte extern mänsklig bildgranskning. Köppris måste tillhöra samma annonskolumn/rad, ha entydiga decimalsiffror/enhet och dessutom stämma med tryckt jämförpris och belagd förpackning.

| Annons | Köp | Jämförpris | Referens (inte ordinarie köppris) | Text-/prisspann | Audit |
|---|---|---|---|---|---|
| [s3a7 Couscous](https://dr.coop.se/Butik/?store=216525#page=3) | 15 kr/st, 500 g/förpackning | Jfr-pris 30:-/kg. | Tidigare lägsta pris 19:78/st. | text 2 (block 11), 3 (block 11), 4 (block 11); pris 53 (block 39), 54 (block 39), 55 (block 39) | PASS |
| [s3a9 Ekologisk tomatpuré](https://dr.coop.se/Butik/?store=216525#page=3) | 2 för 30 kr, 200 g/förpackning | Jfr-pris 75:-/kg. | Ord. pris 19:77/st. | text 8 (block 14), 9 (block 14), 10 (block 14); pris 23 (block 24), 24 (block 24), 25 (block 25) | PASS |
| [s5a1 Gul lök i nät](https://dr.coop.se/Butik/?store=216525#page=5) | 19.90 kr/nät, 3000 g/förpackning | Jfr-pris 6:63/kg. | saknas | text 2 (block 4), 3 (block 4); pris 4 (block 4), 5 (block 4), 6 (block 5) | PASS |

Alla tre: publika priser utan medlemskrav, 21–27 september, ingen köpgräns eller pant angiven i respektive annons. Inget ordinarie köppris eller GTIN har skapats. Tomatpuréns 30 kr gäller två 200 g-förpackningar; ett obelagt köp av en för 15 kr stoppas. Löken köps som ett helt nät på 3 kg för 19,90 kr. Referensen 19:78 för couscous respektive 19:77 för tomatpuré används inte som restpris.

Tre ingrediensmatchningar och köp/audit PASS, ingen näringsgodkänd helmeny. Flytande honung når OWN/PU men matchning till ingrediensen honung avvisas (produktens canonical_name är flytande honung). Ingen ny matchningsregel införs.

## Samtliga identifierade annonser

Varje rad länkar till rätt PDF-sida. Fullständiga koordinater, råtexter, prisdelar, villkor, källhash, observation, SourceOffer-ID och PU-ID finns i `final-acceptance/result.json` och `source-products.json`.

| Sida/ruta | Titel | Annonserat pris | Medlem | Period | OWN/PU/status | Exakt återstående hinder |
|---|---|---|---|---|---|---|
| [s1a1](https://dr.coop.se/Butik/?store=216525#page=1) | Snacks | 2 för 40 kr | nej | 2026-09-21–2026-09-27 | extraherad; köp blockerade | Flera annonserade varianter; exakt köpvariant inte belagd; Fast förpackningsinnehåll saknas eller är intervall/ca/multipack; Oberoende jämförpriskontroll stöds inte eller saknas |
| [s1a2](https://dr.coop.se/Butik/?store=216525#page=1) | Bröd | 2 för 35 kr | ja | 2026-09-21–2026-09-27 | extraherad; köp blockerade | Flera annonserade varianter; exakt köpvariant inte belagd |
| [s1a3](https://dr.coop.se/Butik/?store=216525#page=1) | Färsk fläskfilé | 69.90 kr/kg | nej | 2026-09-21–2026-09-27 | extraherad; köp blockerade | Fast förpackningsinnehåll saknas eller är intervall/ca/multipack; Oberoende jämförpriskontroll stöds inte eller saknas; Kilopris bevarat; konkret köpmängd saknar stödd kontraktsform |
| [s1a4](https://dr.coop.se/Butik/?store=216525#page=1) | Bregott storpack | 49.90 kr/st | nej | 2026-09-21–2026-09-27 | extraherad; köp blockerade | Flera annonserade varianter; exakt köpvariant inte belagd |
| [s1a5](https://dr.coop.se/Butik/?store=216525#page=1) | Toalettpapper 24-pack | 79 kr/st | nej | 2026-09-21–2026-09-27 | importerad OWN + PU | inga köphinder i aktuellt textkontrakt |
| [s1a6](https://dr.coop.se/Butik/?store=216525#page=1) | Potatis i påse | 9.90 kr/st | nej | 2026-09-21–2026-09-27 | extraherad; köp blockerade | Flera annonserade varianter; exakt köpvariant inte belagd |
| [s2a1](https://dr.coop.se/Butik/?store=216525#page=2) | Drickyoghurt | 2 för 18 kr | nej | 2026-09-21–2026-09-27 | extraherad; köp blockerade | Jämförprisets enhet matchar inte belagd förpackningsenhet; Vätska: behållare/panttillämplighet inte kvalificerad av textadaptern; Flera annonserade varianter; exakt köpvariant inte belagd |
| [s2a2](https://dr.coop.se/Butik/?store=216525#page=2) | Färskost | 2 för 24 kr | nej | 2026-09-21–2026-09-27 | extraherad; köp blockerade | Flera annonserade varianter; exakt köpvariant inte belagd |
| [s2a3](https://dr.coop.se/Butik/?store=216525#page=2) | Salami | 19.90 kr/st | nej | 2026-09-21–2026-09-27 | extraherad; köp blockerade | Flera annonserade varianter; exakt köpvariant inte belagd |
| [s2a4](https://dr.coop.se/Butik/?store=216525#page=2) | Leverpastej | 9.90 kr/st | nej | 2026-09-21–2026-09-27 | importerad OWN + PU | inga köphinder i aktuellt textkontrakt |
| [s2a5](https://dr.coop.se/Butik/?store=216525#page=2) | Tepåsar | 2 för 35 kr | nej | 2026-09-21–2026-09-27 | extraherad; köp blockerade | Flera annonserade varianter; exakt köpvariant inte belagd; Fast förpackningsinnehåll saknas eller är intervall/ca/multipack; Oberoende jämförpriskontroll stöds inte eller saknas |
| [s2a6](https://dr.coop.se/Butik/?store=216525#page=2) | Kaffekapslar 50-pack | 135 kr/st | nej | 2026-09-21–2026-09-27 | extraherad; köp blockerade | Flera annonserade varianter; exakt köpvariant inte belagd; Oberoende jämförpriskontroll stöds inte eller saknas |
| [s2a7](https://dr.coop.se/Butik/?store=216525#page=2) | Munkens Svarta Ost | 99 kr/kg | nej | 2026-09-21–2026-09-27 | extraherad; köp blockerade | Fast förpackningsinnehåll saknas eller är intervall/ca/multipack; Oberoende jämförpriskontroll stöds inte eller saknas; Kilopris bevarat; konkret köpmängd saknar stödd kontraktsform |
| [s2a8](https://dr.coop.se/Butik/?store=216525#page=2) | Granola | 37 kr/st | nej | 2026-09-21–2026-09-27 | extraherad; köp blockerade | Flera annonserade varianter; exakt köpvariant inte belagd |
| [s2a9](https://dr.coop.se/Butik/?store=216525#page=2) | Flytande honung | 30 kr/st | nej | 2026-09-21–2026-09-27 | importerad OWN + PU | inga köphinder i aktuellt textkontrakt |
| [s2a10](https://dr.coop.se/Butik/?store=216525#page=2) | Snabbkaffe original | 59 kr/st | nej | 2026-09-21–2026-09-27 | importerad OWN + PU | inga köphinder i aktuellt textkontrakt |
| [s2a11](https://dr.coop.se/Butik/?store=216525#page=2) | Havredryck | 2 för 28 kr | nej | 2026-09-21–2026-09-27 | extraherad; köp blockerade | Vätska: behållare/panttillämplighet inte kvalificerad av textadaptern |
| [s2a12](https://dr.coop.se/Butik/?store=216525#page=2) | Bregott | 49.90 kr/st | nej | 2026-09-21–2026-09-27 | extraherad; köp blockerade | Flera annonserade varianter; exakt köpvariant inte belagd; Tryckt jämförpris motsäger tilldelat köppris/förpackning |
| [s3a1](https://dr.coop.se/Butik/?store=216525#page=3) | Thai Cube | 2 för 69 kr | nej | 2026-09-21–2026-09-27 | extraherad; köp blockerade | Flera annonserade varianter; exakt köpvariant inte belagd; Fast förpackningsinnehåll saknas eller är intervall/ca/multipack; Oberoende jämförpriskontroll stöds inte eller saknas |
| [s3a2](https://dr.coop.se/Butik/?store=216525#page=3) | Fruktdryck | 2 för 29 kr | nej | 2026-09-21–2026-09-27 | extraherad; köp blockerade | Vätska: behållare/panttillämplighet inte kvalificerad av textadaptern; Flera annonserade varianter; exakt köpvariant inte belagd |
| [s3a3](https://dr.coop.se/Butik/?store=216525#page=3) | Virgin olivolja | 49 kr/st | nej | 2026-09-21–2026-09-27 | extraherad; köp blockerade | Vätska: behållare/panttillämplighet inte kvalificerad av textadaptern |
| [s3a4](https://dr.coop.se/Butik/?store=216525#page=3) | Hamburgerbröd | 16.90 kr/st | nej | 2026-09-21–2026-09-27 | extraherad; köp blockerade | Uttryckligt variant-/behörighetsvillkor ännu inte kvalificerat |
| [s3a5](https://dr.coop.se/Butik/?store=216525#page=3) | Smör-/Pajdeg | 2 för 35 kr | nej | 2026-09-21–2026-09-27 | extraherad; köp blockerade | Flera annonserade varianter; exakt köpvariant inte belagd; Fast förpackningsinnehåll saknas eller är intervall/ca/multipack; Oberoende jämförpriskontroll stöds inte eller saknas |
| [s3a6](https://dr.coop.se/Butik/?store=216525#page=3) | Japansk soja | 27 kr/st | nej | 2026-09-21–2026-09-27 | extraherad; köp blockerade | Vätska: behållare/panttillämplighet inte kvalificerad av textadaptern |
| [s3a7](https://dr.coop.se/Butik/?store=216525#page=3) | Couscous | 15 kr/st | nej | 2026-09-21–2026-09-27 | importerad OWN + PU | inga köphinder i aktuellt textkontrakt |
| [s3a8](https://dr.coop.se/Butik/?store=216525#page=3) | Vegetariskt protein | 2 för 89 kr | nej | 2026-09-21–2026-09-27 | extraherad; köp blockerade | Flera annonserade varianter; exakt köpvariant inte belagd; Fast förpackningsinnehåll saknas eller är intervall/ca/multipack; Oberoende jämförpriskontroll stöds inte eller saknas |
| [s3a9](https://dr.coop.se/Butik/?store=216525#page=3) | Ekologisk tomatpuré | 2 för 30 kr | nej | 2026-09-21–2026-09-27 | importerad OWN + PU | inga köphinder i aktuellt textkontrakt |
| [s3a10](https://dr.coop.se/Butik/?store=216525#page=3) | Färsk kycklingfilé | 45 kr/st | nej | 2026-09-21–2026-09-27 | extraherad; köp blockerade | Flera annonserade varianter; exakt köpvariant inte belagd |
| [s4a1](https://dr.coop.se/Butik/?store=216525#page=4) | Munskölj Soft mint | 55 kr/st | nej | 2026-09-21–2026-09-27 | extraherad; köp blockerade | Vätska: behållare/panttillämplighet inte kvalificerad av textadaptern |
| [s4a2](https://dr.coop.se/Butik/?store=216525#page=4) | Shower gel | 2 för 35 kr | nej | 2026-09-21–2026-09-27 | extraherad; köp blockerade | Vätska: behållare/panttillämplighet inte kvalificerad av textadaptern; Flera annonserade varianter; exakt köpvariant inte belagd |
| [s4a3](https://dr.coop.se/Butik/?store=216525#page=4) | Tandkräm | 2 för 45 kr | nej | 2026-09-21–2026-09-27 | extraherad; köp blockerade | Flera annonserade varianter; exakt köpvariant inte belagd; Fast förpackningsinnehåll saknas eller är intervall/ca/multipack; Oberoende jämförpriskontroll stöds inte eller saknas |
| [s4a4](https://dr.coop.se/Butik/?store=216525#page=4) | Tvättmedel | 35 kr/st | nej | 2026-09-21–2026-09-27 | extraherad; köp blockerade | Flera annonserade varianter; exakt köpvariant inte belagd; Oberoende jämförpriskontroll stöds inte eller saknas |
| [s5a1](https://dr.coop.se/Butik/?store=216525#page=5) | Gul lök i nät | 19.90 kr/nät | nej | 2026-09-21–2026-09-27 | importerad OWN + PU | inga köphinder i aktuellt textkontrakt |
| [s5a2](https://dr.coop.se/Butik/?store=216525#page=5) | Äpplen Royal Gala | 19.90 kr/kg | nej | 2026-09-21–2026-09-27 | extraherad; köp blockerade | Fast förpackningsinnehåll saknas eller är intervall/ca/multipack; Oberoende jämförpriskontroll stöds inte eller saknas; Kilopris bevarat; konkret köpmängd saknar stödd kontraktsform |
| [s5a3](https://dr.coop.se/Butik/?store=216525#page=5) | Blombukett | 79.90 kr/st | nej | 2026-09-21–2026-09-27 | extraherad; köp blockerade | Fast förpackningsinnehåll saknas eller är intervall/ca/multipack; Oberoende jämförpriskontroll stöds inte eller saknas |
| [s5a4](https://dr.coop.se/Butik/?store=216525#page=5) | Päron conference | 19.90 kr/kg | nej | 2026-09-21–2026-09-27 | extraherad; köp blockerade | Fast förpackningsinnehåll saknas eller är intervall/ca/multipack; Oberoende jämförpriskontroll stöds inte eller saknas; Kilopris bevarat; konkret köpmängd saknar stödd kontraktsform |
| [s5a5](https://dr.coop.se/Butik/?store=216525#page=5) | Morötter i påse | 16.90 kr/st | nej | 2026-09-21–2026-09-27 | importerad OWN + PU | inga köphinder i aktuellt textkontrakt |
| [s6a1](https://dr.coop.se/Butik/?store=216525#page=6) | Kolsyrat vatten 6-pack | 34 kr/st | ja | 2026-09-21–2026-09-27 | extraherad; köp blockerade | Pant tillkommer men belopp/antal inte belagt; Flera annonserade varianter; exakt köpvariant inte belagd; Fast förpackningsinnehåll saknas eller är intervall/ca/multipack |
| [s6a2](https://dr.coop.se/Butik/?store=216525#page=6) | Godispåse | 20 kr/st | nej | 2026-09-21–2026-09-27 | importerad OWN + PU | inga köphinder i aktuellt textkontrakt |
| [s6a3](https://dr.coop.se/Butik/?store=216525#page=6) | Glasstrutar 8-pack | 2 för 50 kr | nej | 2026-09-21–2026-09-27 | extraherad; köp blockerade | Flera annonserade varianter; exakt köpvariant inte belagd; Oberoende jämförpriskontroll stöds inte eller saknas |
| [s6a4](https://dr.coop.se/Butik/?store=216525#page=6) | Fikabröd | 2 för 35 kr | nej | 2026-09-21–2026-09-27 | extraherad; köp blockerade | Flera annonserade varianter; exakt köpvariant inte belagd; Fast förpackningsinnehåll saknas eller är intervall/ca/multipack; Oberoende jämförpriskontroll stöds inte eller saknas |
| [s6a5](https://dr.coop.se/Butik/?store=216525#page=6) | Kakrullar | 2 för 32 kr | nej | 2026-09-21–2026-09-27 | extraherad; köp blockerade | Flera annonserade varianter; exakt köpvariant inte belagd; Fast förpackningsinnehåll saknas eller är intervall/ca/multipack; Oberoende jämförpriskontroll stöds inte eller saknas |
| [s6a6](https://dr.coop.se/Butik/?store=216525#page=6) | Proteinbar | 2 för 35 kr | nej | 2026-09-21–2026-09-27 | extraherad; köp blockerade | Flera annonserade varianter; exakt köpvariant inte belagd |
| [s6a7](https://dr.coop.se/Butik/?store=216525#page=6) | Chokladkaka | 25 kr/st | nej | 2026-09-21–2026-09-27 | extraherad; köp blockerade | Flera annonserade varianter; exakt köpvariant inte belagd; Fast förpackningsinnehåll saknas eller är intervall/ca/multipack; Oberoende jämförpriskontroll stöds inte eller saknas |
| [s7a1](https://dr.coop.se/Butik/?store=216525#page=7) | Lego Spiderman bil | 249 kr/st | nej | 2026-09-21–2026-09-27 | extraherad; köp blockerade | Fast förpackningsinnehåll saknas eller är intervall/ca/multipack; Oberoende jämförpriskontroll stöds inte eller saknas |
| [s7a2](https://dr.coop.se/Butik/?store=216525#page=7) | Paninigrill | 129 kr/st | nej | 2026-09-21–2026-09-27 | extraherad; köp blockerade | Fast förpackningsinnehåll saknas eller är intervall/ca/multipack; Oberoende jämförpriskontroll stöds inte eller saknas |
| [s7a3](https://dr.coop.se/Butik/?store=216525#page=7) | Kiddy I-Pet Bag | 49 kr/st | nej | 2026-09-21–2026-09-27 | extraherad; köp blockerade | Fast förpackningsinnehåll saknas eller är intervall/ca/multipack; Oberoende jämförpriskontroll stöds inte eller saknas |
| [s7a4](https://dr.coop.se/Butik/?store=216525#page=7) | Modellera 10-pack | 19 kr/st | nej | 2026-09-21–2026-09-27 | extraherad; köp blockerade | Fast förpackningsinnehåll saknas eller är intervall/ca/multipack; Oberoende jämförpriskontroll stöds inte eller saknas |
| [s7a5](https://dr.coop.se/Butik/?store=216525#page=7) | LED Lampa | 69 kr/st | nej | 2026-09-21–2026-09-27 | extraherad; köp blockerade | Fast förpackningsinnehåll saknas eller är intervall/ca/multipack; Oberoende jämförpriskontroll stöds inte eller saknas |
| [s7a6](https://dr.coop.se/Butik/?store=216525#page=7) | Hårfön | 129 kr/st | nej | 2026-09-21–2026-09-27 | extraherad; köp blockerade | Fast förpackningsinnehåll saknas eller är intervall/ca/multipack; Oberoende jämförpriskontroll stöds inte eller saknas |
| [s7a7](https://dr.coop.se/Butik/?store=216525#page=7) | Ledlampa | 2 för 40 kr | nej | 2026-09-21–2026-09-27 | extraherad; köp blockerade | Flera annonserade varianter; exakt köpvariant inte belagd; Fast förpackningsinnehåll saknas eller är intervall/ca/multipack; Oberoende jämförpriskontroll stöds inte eller saknas |
| [s7a8](https://dr.coop.se/Butik/?store=216525#page=7) | Plattång | 129 kr/st | nej | 2026-09-21–2026-09-27 | extraherad; köp blockerade | Fast förpackningsinnehåll saknas eller är intervall/ca/multipack; Oberoende jämförpriskontroll stöds inte eller saknas; Text med Max ännu inte säkert klassificerad som köpgräns/annan begränsning |
| [s8a1](https://dr.coop.se/Butik/?store=216525#page=8) | Pizza | 2 för 40 kr | nej | 2026-09-24–2026-09-27 | extraherad; köp blockerade | Flera annonserade varianter; exakt köpvariant inte belagd; Fast förpackningsinnehåll saknas eller är intervall/ca/multipack; Oberoende jämförpriskontroll stöds inte eller saknas |
| [s8a2](https://dr.coop.se/Butik/?store=216525#page=8) | Hushållsost | 69.90 kr/kg | nej | 2026-09-24–2026-09-27 | extraherad; köp blockerade | Flera annonserade varianter; exakt köpvariant inte belagd; Fast förpackningsinnehåll saknas eller är intervall/ca/multipack; Oberoende jämförpriskontroll stöds inte eller saknas; Kilopris bevarat; konkret köpmängd saknar stödd kontraktsform |
| [s8a3](https://dr.coop.se/Butik/?store=216525#page=8) | Smörgåspålägg | 2 för 35 kr | ja | 2026-09-24–2026-09-27 | extraherad; köp blockerade | Flera annonserade varianter; exakt köpvariant inte belagd; Fast förpackningsinnehåll saknas eller är intervall/ca/multipack; Oberoende jämförpriskontroll stöds inte eller saknas |
| [s8a4](https://dr.coop.se/Butik/?store=216525#page=8) | Snacktomater | 24.90 kr/st | nej | 2026-09-24–2026-09-27 | importerad OWN; framtida, ej PU nu | inga köphinder i aktuellt textkontrakt |
| [s8a5](https://dr.coop.se/Butik/?store=216525#page=8) | Färsk fläskkarré | 59.90 kr/kg | nej | 2026-09-24–2026-09-27 | extraherad; köp blockerade | Fast förpackningsinnehåll saknas eller är intervall/ca/multipack; Oberoende jämförpriskontroll stöds inte eller saknas; Kilopris bevarat; konkret köpmängd saknar stödd kontraktsform |

## Avgränsade kvarstående hinder

Bregott s2a12: 49,90 kr, 750 g, tryckt jämförpris 78,67 kr/kg; 49,90/0,75 = 66,53 kr/kg. På s1a4 stämmer 66,53, men variantgruppen är ändå blockerad. Ingen av sidorna används för att tyst skriva över den andra.

Vatten s6a1: 34 kr, medlemspris, 6 × 1,5 liter och ”Pant tillkommer”. Belopp saknas och multipack/variantgrupp är inte kvalificerade. Övriga vätskors konservativa behållarspärr är en adapterbegränsning; den innebär inte ett påstående om att exempelvis olivolja har pant.

Kilopriser bevaras som prisuppgifter, men ca-vikt omvandlas inte till en fast paketvikt. Intervall och blandade varianter får inte en påhittad SKU/GTIN. Gemensamma villkor och sidans kortare datum finns med källspår i SourceOffer. Begränsade medlemsköp kräver dessutom ett belagt kampanj-ID över X:-tra-butiker; en butiksspecifik dokumenthash duger inte för ett gemensamt hushållstak.

Parsern är återanvändbar för samma dokumentmall och härleder datum, sidor, annonskolumner och produkter ur indata. Ändrad/okänd layout spärras; den är inte en generell parser för alla PDF-mallar. Bildinnehåll kan innehålla uppgifter som denna textinsats inte identifierar. Full reklambladstäckning är därför inte belagd.

## Överlappande orsaker (summeras inte till 47)

- 29: Flera annonserade varianter; exakt köpvariant inte belagd (`exact_advertised_variant_unverified`).
- 29: Oberoende jämförpriskontroll stöds inte eller saknas (`independent_price_package_check_unavailable`).
- 27: Fast förpackningsinnehåll saknas eller är intervall/ca/multipack (`fixed_package_unverified`).
- 7: Vätska: behållare/panttillämplighet inte kvalificerad av textadaptern (`container_deposit_applicability_unverified`).
- 6: Kilopris bevarat; konkret köpmängd saknar stödd kontraktsform (`weight_price_not_supported_for_concrete_purchase`).
- 1: Jämförprisets enhet matchar inte belagd förpackningsenhet (`comparison_unit_basis_unverified`).
- 1: Tryckt jämförpris motsäger tilldelat köppris/förpackning (`printed_comparison_conflicts_with_purchase`).
- 1: Uttryckligt variant-/behörighetsvillkor ännu inte kvalificerat (`additional_condition_requires_review`).
- 1: Pant tillkommer men belopp/antal inte belagt (`deposit_amount_unverified`).
- 1: Text med Max ännu inte säkert klassificerad som köpgräns/annan begränsning (`purchase_limit_unparsed`).
