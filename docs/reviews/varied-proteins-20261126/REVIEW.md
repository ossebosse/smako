# 90 nya middagar: samma protein, olika tillagning (2026-11-26)

Ägarens beställning 2026-11-26: fler recept, med flera sätt att laga de
populära proteinerna, så att en vecka med bara kyckling (till exempel) inte
blir fem likadana middagar. Ägaren har sagt att AI-granskning räcker.
Recepten är inte provlagade.

## Vad som faktiskt hindrade en kycklingvecka

Före ändringen gav en vecka med fem kycklingmiddagar (fördelning
`{"chicken": 5}`) **ingen meny alls** i Lund, varken med eller utan
proteingräns, trots att 216–239 kycklingrätter klarade kraven. Förinställningen
Balanserad tillåter högst två middagar med samma huvudråvara.

Rättning (`services/same_protein_variety.py`):

- Begär användaren fler kycklingmiddagar än taket följer taket med.
- När tre eller fler middagar av ett slag begärs (kyckling, kött eller fisk)
  måste veckan i stället variera: ingen rättfamilj två gånger, högst två
  middagar på samma kolhydrat eller samma tillagningssätt, och två eller tre
  tillagningssätt. En fiskvecka i Malmö var annars fem risrätter.
- För kött och fisk ligger taket kvar på två per huvudråvara (annars blev det
  tre sardinrätter samma vecka).

Efter rättningen (serverkörning, uppskattat läge, 2 butiker, 4 portioner):

| Vecka | Lund | Malmö |
|---|---|---|
| 5 × kyckling, minst 45 g protein | 874,59 kr – schnitzel, rödbetsbädd i ugn, citronpasta, linsgryta, pulao | 773,78 kr – citronpasta, schnitzel, paprikagryta, ugnsbakad yoghurtkyckling, curry |
| 5 × kyckling, utan gräns | 591,02 kr | 562,06 kr |
| 5 × fisk, utan gräns | – | 616,95 kr – tonfisklarb, sardinwok, makaronilåda, laxsoppa, sillpudding |

## Recepten

Källa `scripts/recipe_layer/varied_proteins_20261126/` (samma kompakta format
som `protein_dinners_20261125`), standardiserade med `meal_library_cli author`
och importerade som sex `meal-pack-*` (90 `new_recipe`).

- **Inga dubbletter:** första utkastet hade 126 rätter. Jämfört mot alla 1 377
  bas-ID i biblioteket (alla varianter) fanns 36 av dem redan (till exempel
  larb gai, gai yang, rogan josh, kycklingbiryani, sopa de lima, lax al
  cartoccio). De togs bort. Samma rättfamilj med ett annat protein är kvar med
  avsikt (till exempel saganaki på kyckling, souvlaki på kyckling).
- **Variation:** sidorna är potatis, pasta, polenta, bulgur, bröd, tortillas,
  nudlar och ris, och metoderna ugn, panna, grill, gryta och wok. 36 kyckling,
  26 kött, 28 fisk och skaldjur.
- **Mängder och steg:** som förra omgången. Huvudråvaran har ett granskat
  intervall, stärkelsetillbehör ett mindre; inga gram för huvudråvaran i
  stegen; vatten i ml; säkerhetstemperaturer (kyckling 74 °C, färs 72 °C,
  fisk 63 °C, helt fläsk 68 °C). Alla har 10–15 räknade ingredienser och inga
  varningar från `author`.
- **Ändrat efter köpbarhetsprovet:** fänkålsfrön (gick inte att köpa i Lund),
  salvia, kryddnejlika, torkade limeblad och böngroddar (saknade näringsvärden)
  byttes mot timjan, kryddpeppar, spiskummin, koriander eller togs bort.

## Näring som också rättades

- Ostronsås: USDA FoodData Central 174529 (”Sauce, oyster, ready-to-serve”).
- Bröd utan näringstabell: Livsmedelsverkets brödsorter efter etiketten
  (pitabröd, nanbröd, hamburgerbröd, surdeg, baguette, ciabatta, tunnbröd,
  tortilla, formfranska, fullkorn, limpa; annars vitt bröd 202). Knäckebröd,
  skorpor, kex, bullar och glutenfritt räknas inte som bröd. I Malmö stoppade
  bröd tidigare 169 rättvarianter.
- Torkade nudlar och pasta som har vatten i ingredienslistan godtas när den
  egna tabellen visar minst 300 kcal per 100 g (torkad vara).

## Köpbarhet och protein

Blandad vecka (2 kyckling, 1 fisk, 2 kött), minst 45 g protein per portion:
**69 av 90 i Lund och 80 av 90 i Malmö** klarar alla krav. Av resten är
7 skaldjursrätter som inte ryms i den fördelningen (¹ i tabellen; de är
köpbara), några ligger under 45 g protein, fyra rätter saknar en komplett
korg med två butiker i Lund och två thairätter saknar näringsvärde för
breda risnudlar i Lund. Alla rätter som klarar kraven i en blandad vecka:
564 i Lund och 606 i Malmö.

| Kök | Rätt | Typ | Familj | Metod | Tillbehör | Ingredienser | Lund | Malmö |
|---|---|---|---|---|---|---|---|---|
| Svenskt | Kycklinglår på plåt med rotfrukter, rosmarin och vitlök | Kyckling | plåträtt | oven | rotfrukter | 10 | ja | ja |
| Svenskt | Kycklingburgare med senapsdressing, tomat och knaprig sallad | Kyckling | kycklingburgare | pan | bröd | 11 | ja | ja |
| Svenskt | Kyckling Kiev med vitlökssmör, potatismos och ärtor | Kyckling | kyckling kiev | oven | potatis | 11 | ja | ja |
| Svenskt | Kycklingsallad med äpple, valnötter och ädelost | Kyckling | kycklingsallad | pan | bröd | 12 | ja | ja |
| Svenskt | Kycklingpytt med potatis, rödbetor och stekt ägg | Kyckling | kycklingpytt | pan | potatis | 10 | ja | ja |
| Svenskt | Kyckling i senapsgräddsås med svamp, pressad potatis och haricots verts | Kyckling | kyckling i senapssås | pan | potatis | 10 | ja | ja |
| Svenskt | Krämig kycklingsoppa med rotfrukter, dill och grovt bröd | Kyckling | kycklingsoppa | pot | bröd | 10 | ja | ja |
| Svenskt | Ugnsbakad kyckling med rödbetor, fetaost och bulgur | Kyckling | kyckling med rödbetor | oven | bulgur | 10 | ja | ja |
| Svenskt | Stekt fläsk med löksås, kokt potatis, morötter och lingon | Kött | fläsk med löksås | pan | potatis | 10 | under 45 g | under 45 g |
| Svenskt | Köttsoppa med nötkött, rotfrukter och grovt bröd | Kött | köttsoppa | pot | bröd | 10 | under 45 g | ja |
| Svenskt | Stekt nötkött med rödvinssås, rostad potatis och ugnsrostade morötter | Kött | rödvinsbiff | pan | potatis | 10 | ja | under 45 g |
| Svenskt | Laxpudding med skirat smör och dill | Fisk/skaldjur | laxpudding | oven | potatis | 10 | ja | ja |
| Svenskt | Stekt lax med pepparrotskräm, rödbetor och dillpotatis | Fisk/skaldjur | lax med pepparrot | pan | potatis | 10 | ja | ja |
| Svenskt | Kokt torsk med äggsås, potatis och skirat smör | Fisk/skaldjur | äggsås | pot | potatis | 10 | ja | ja |
| Svenskt | Hemgjorda fiskbiffar med kapriskräm och potatismos | Fisk/skaldjur | fiskbiffar | pan | potatis | 13 | ja | ja |
| Svenskt | Ugnsbakad vit fisk med tomat, fänkål och citronpotatis | Fisk/skaldjur | fisk med fänkål | oven | potatis | 10 | ja | ja |
| Svenskt | Räkpasta med citron, dill, spenat och parmesan | Fisk/skaldjur | räkpasta med dill | pan | pasta | 10 | ja¹ | ja¹ |
| Italienskt | Pollo piccata med citron, kapris och rostad potatis | Kyckling | piccata | pan | potatis | 12 | ja | ja |
| Italienskt | Pollo alla parmigiana med tomatsås och pasta | Kyckling | parmigiana di pollo | oven | pasta | 11 | ja | ja |
| Italienskt | Risotto med kyckling, svamp och timjan | Kyckling | risotto | pot | risottoris | 11 | ja | ja |
| Italienskt | Panzanella med grillad kyckling, tomat och gurka | Kyckling | panzanella | pan | bröd | 10 | ja | ja |
| Italienskt | Pasta med hemgjord pesto, kyckling, potatis och haricots verts | Kyckling | pesto genovese | pan | pasta | 10 | ja | ja |
| Italienskt | Ugnsbakade gnocchi med kyckling, spenat och tomat | Kyckling | gnocchi al forno | oven | gnocchi | 10 | ja | ja |
| Italienskt | Lasagne alla bolognese med bechamel | Kött | lasagne | oven | pasta | 14 | ej 2 butiker | ja |
| Italienskt | Brasato – nötkött bräserat i rödvin med polenta | Kött | brasato | pot | polenta | 12 | ej 2 butiker | ja |
| Italienskt | Fläskkött med peperonata, vitt vin och rostat bröd | Kött | peperonata | pan | bröd | 10 | ja | ja |
| Italienskt | Stufato – fläskgryta med vita bönor, rosmarin och tomat | Kött | stufato | pot | bröd | 11 | ja | ja |
| Italienskt | Vit fisk alla livornese med oliver, kapris och potatis | Fisk/skaldjur | livornese | pot | potatis | 11 | ja | ja |
| Italienskt | Pesce all'acqua pazza med tomat, vitt vin och bröd | Fisk/skaldjur | acqua pazza | pot | bröd | 10 | ja | ja |
| Italienskt | Risotto med lax, citron och spenat | Fisk/skaldjur | risotto al salmone | pot | risottoris | 10 | ja | ja |
| Italienskt | Räkor i tomat- och vitlökssås med krämig polenta | Fisk/skaldjur | gamberi con polenta | pan | polenta | 12 | ja¹ | ja¹ |
| Grekiskt | Kotopoulo souvlaki – kycklingspett med pitabröd, tzatziki och tomatsallad | Kyckling | souvlaki | pan | bröd | 11 | ja | ja |
| Grekiskt | Kotopoulo lemonato – citronkyckling i ugn med potatis och oregano | Kyckling | lemonato | oven | potatis | 10 | ja | ja |
| Grekiskt | Kycklinggryta i kanelkryddad tomatsås med pasta | Kyckling | kokkinisto | pot | pasta | 12 | ej 2 butiker | ja |
| Grekiskt | Kotosoupa avgolemono – kycklingsoppa med ris, ägg och citron | Kyckling | avgolemono | pot | ris | 10 | ja | ja |
| Grekiskt | Kyckling med haricots verts, tomat och potatis i en gryta | Kyckling | kotopoulo me fasolakia | pot | potatis | 10 | ja | ja |
| Grekiskt | Kycklinggryta med kanel och apelsin, serverad med ris och yoghurt | Kyckling | kapama | pot | ris | 11 | ja | ja |
| Grekiskt | Kotopoulo saganaki – kyckling i paprika- och tomatsås med feta och bröd | Kyckling | saganaki | pan | bröd | 12 | ja | ja |
| Grekiskt | Tas kebab – kryddig nötgryta med tomat och smörig pilaff | Kött | tas kebab | pot | ris | 15 | ja | ja |
| Grekiskt | Keftedes med myntayoghurt, ugnspommes och grekisk sallad | Kött | keftedes | pan | potatis | 12 | ja | ja |
| Grekiskt | Fläskgryta med selleri, dill och ägg-citronsås | Kött | hirino me selino | pot | bröd | 10 | ja | ja |
| Grekiskt | Kreatopita – köttfärspaj i filodeg med grekisk sallad | Kött | kreatopita | oven | filodeg | 13 | ja | ja |
| Grekiskt | Grillad fläskkarré med citronpotatis och tzatziki | Kött | brizola | pan | potatis | 10 | ja | ja |
| Grekiskt | Stekt vit fisk med skordalia, rödbetor och grönsallad | Fisk/skaldjur | skordalia | pan | potatis | 10 | ja | ja |
| Grekiskt | Kakavia – grekisk fisksoppa med potatis och citron | Fisk/skaldjur | kakavia | pot | bröd | 11 | ja | ja |
| Grekiskt | Ugnsbakad lax med citron, dill och kritharaki med spenat | Fisk/skaldjur | lax med kritharaki | oven | pasta | 10 | ja | ja |
| Grekiskt | Räkspett med vitlök och citron, bulgursallad och yoghurt | Fisk/skaldjur | räkspett | pan | bulgur | 11 | ja¹ | ja¹ |
| Grekiskt | Psari savoro – stekt fisk i rosmarin- och vinägersås med potatis | Fisk/skaldjur | savoro | pan | potatis | 11 | ja | ja |
| Indiskt | Tandoorikyckling i ugn med kachumbersallad, myntayoghurt och bröd | Kyckling | tandoori | oven | bröd | 14 | ja | ja |
| Indiskt | Saag murgh – kyckling i kryddig spenatsås med bröd | Kyckling | saag | pot | bröd | 12 | ja | ja |
| Indiskt | Kadai murgh – kyckling med paprika, tomat och rostade kryddor | Kyckling | kadai | pan | bröd | 14 | ja | ja |
| Indiskt | Kycklingvindaloo med potatis och vinäger | Kyckling | vindaloo | pot | potatis | 14 | ja | ja |
| Indiskt | Kerala-ishtu – mild kycklinggryta med kokos, potatis och ris | Kyckling | ishtu | pot | ris | 12 | under 45 g | ja |
| Indiskt | Shami kebab av nötfärs och linser med myntachutney och sallad | Kött | shami kebab | pan | bröd | 15 | ja | ja |
| Indiskt | Kofta curry – nötfärsbullar i tomat- och yoghurtsås med ris | Kött | kofta curry | pot | ris | 13 | ja | ja |
| Indiskt | Nihari – långkokt nötgryta med ingefära och bröd | Kött | nihari | pot | bröd | 14 | ja | ja |
| Indiskt | Kryddig fläskwok med vitkål, ingefära och ris | Kött | chilli pork | pan | ris | 14 | ja | ja |
| Indiskt | Amritsari fisk – kryddpanerad fisk med ugnspotatis och myntachutney | Fisk/skaldjur | amritsari | pan | potatis | 14 | ja | ja |
| Indiskt | Chingri malai – räkcurry med kokos och kardemumma | Fisk/skaldjur | malai curry | pot | ris | 13 | ja¹ | ja¹ |
| Indiskt | Tandoorilax med spiskumminris och gurkraita | Fisk/skaldjur | lax tandoori | oven | ris | 14 | ja | ja |
| Indiskt | Meen pollichathu – fisk bakad i paket med kryddig tomat-löksås och ris | Fisk/skaldjur | pollichathu | oven | ris | 14 | ja | ja |
| Indiskt | Krispiga kryddräkor med citronris och kokosflingor | Fisk/skaldjur | rava fry | pan | ris | 14 | ja¹ | ja¹ |
| Mexikanskt | Tinga de pollo på krispiga tostadas med bönor och avokado | Kyckling | tinga | pot | majstortillas | 14 | ja | ja |
| Mexikanskt | Pozole verde – grön kycklingsoppa med majs, rädisor och tortillas | Kyckling | pozole | pot | majstortillas | 14 | ja | ja |
| Mexikanskt | Enchiladas suizas – kyckling i tortillas med grön sås och ost | Kyckling | enchiladas suizas | oven | tortillas | 13 | ja | ja |
| Mexikanskt | Chilaquiles rojos med kyckling, stekt ägg och crème fraiche | Kyckling | chilaquiles | pan | majstortillas | 14 | ja | ja |
| Mexikanskt | Tamal de cazuela – ugnsbakad polenta med kycklingfyllning och salsa | Kyckling | tamal de cazuela | oven | polenta | 14 | under 45 g | ja |
| Mexikanskt | Pollo adobado – kryddmarinerad ugnskyckling med potatis och majssallad | Kyckling | pollo adobado | oven | potatis | 14 | ja | ja |
| Mexikanskt | Albóndigas – nötfärsbullar med ris i rökig tomatsås och tortillas | Kött | albóndigas | pot | majstortillas | 15 | ja | ja |
| Mexikanskt | Carne guisada – långkokt nötgryta med spiskummin och tortillas | Kött | carne guisada | pot | tortillas | 14 | under 45 g | ja |
| Mexikanskt | Chile colorado – fläskgryta i röd chilisås med ris och bönor | Kött | chile colorado | pot | ris | 13 | ja | ja |
| Mexikanskt | Cochinita pibil – citrusbräserat fläsk med picklad rödlök och tortillas | Kött | cochinita pibil | pot | majstortillas | 14 | ja | ja |
| Mexikanskt | Ugnsbakade paprikor fyllda med nötfärs, ris och ost med tomatsalsa | Kött | chiles rellenos | oven | ris | 14 | under 45 g | ja |
| Mexikanskt | Caldo de res – nötköttssoppa med majs, kål och potatis | Kött | caldo de res | pot | potatis | 14 | ja | ja |
| Mexikanskt | Camarones al mojo de ajo – vitlöksräkor med lime, ris och svarta bönor | Fisk/skaldjur | mojo de ajo | pan | ris | 12 | ja¹ | ja¹ |
| Mexikanskt | Lax med mango- och avokadosalsa, svarta bönor och ris | Fisk/skaldjur | salmón con salsa de mango | pan | ris | 12 | ja | ja |
| Thailändskt | Pad krapao gai – kycklingwok med basilika, chili och stekt ägg | Kyckling | pad krapao | pan | ris | 12 | ja | ja |
| Thailändskt | Pad see ew – breda risnudlar med kyckling, broccoli och ägg | Kyckling | pad see ew | pan | breda risnudlar | 11 | näring saknas | ja |
| Thailändskt | Kaeng kari gai – gul kycklingcurry med potatis och gurkrelish | Kyckling | gul curry | pot | ris | 13 | ja | ja |
| Thailändskt | Khao pad gai – stekt ris med kyckling, ägg och gurka | Kyckling | khao pad | pan | ris | 14 | ja | ja |
| Thailändskt | Nötkött med svartpeppar, lök och paprika och jasminris | Kött | pad prik thai dam | pan | ris | 11 | ja | ja |
| Thailändskt | Kaeng hung lay – nordthailändsk fläskgryta med ingefära och ris | Kött | kaeng hung lay | pot | ris | 12 | ej 2 butiker | ja |
| Thailändskt | Kuay teow neua – nudelsoppa med nötkött, kryddad buljong och pak choi | Kött | nudelsoppa | pot | breda risnudlar | 13 | näring saknas | under 45 g |
| Thailändskt | Moo palo – fläsk bräserat i soja och kanel med kokta ägg och ris | Kött | moo palo | pot | ris | 10 | ja | ja |
| Thailändskt | Pla nueng manao – ångkokt fisk i lime-, vitlöks- och chilisås med ris | Fisk/skaldjur | pla nueng manao | pot | ris | 11 | ja | ja |
| Thailändskt | Pla pad cha – wokad fisk med chili, ingefära, basilika och ris | Fisk/skaldjur | pad cha | pan | ris | 13 | ja | ja |
| Thailändskt | Tod mun pla – thailändska fiskkakor med gurkrelish och ris | Fisk/skaldjur | fiskkakor | pan | ris | 13 | under 45 g | ja |
| Thailändskt | Khao tom pla – risgröt-soppa med fisk, ingefära och vitlöksolja | Fisk/skaldjur | khao tom | pot | ris | 13 | ja | ja |
| Thailändskt | Goong kratiem – vitlöksräkor med peppar, jasminris och gurksallad | Fisk/skaldjur | goong kratiem | pan | ris | 12 | ja¹ | ja¹ |
| Thailändskt | Kaeng som pla – syrlig fisk- och grönsakscurry med ris | Fisk/skaldjur | kaeng som | pot | ris | 11 | under 45 g | ja |