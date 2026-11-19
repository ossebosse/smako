# Billiga råvaror som ger omväxling (2026-11-19)

Ägarbeslut 2026-11-19: Claude skriver recepten själv (beställningen till Chat är indragen). Målet är fler rätter på billiga råvaror med få rätter, så att veckorna varierar utan att bli dyrare. AI-författade utkast, inte provlagade.

- **49 grundrätter, 147 varianter** (simple, standard, extended). Standard och extended har 10–15 räknade ingredienser och väljs med standardvalet.
- Källa: `scripts/recipe_layer/cheap_bases_20261119.py` och `cheap_bases_data_20261119.py`. Paketet `smako-cheap-bases-20261119`; tillägget i manifestet är bokfört i `library-transition.json`.
- 60 planerades. 11 ströks som för lika befintliga grundrätter: kålpudding (kålpuddinggryta finns), stuvade makaroner med falukorv (finns), raggmunk (finns med kikärtsröra), rotmos med fläsk (fläsklägg med rotmos finns), giouvarlakia (youvarlakia finns), kai palo (finns), rödbetsrisotto (finns med kyckling), pasta med vitkål (pizzoccheri finns), italiensk gul ärtsoppa, keema på fläskfärs (färskeema finns), kycklinglever med lök (fegato alla veneziana finns).
- Korv stroganoff behölls trots att fläskstroganoff finns: en egen klassiker med falukorv. Grekiska lahanodolmades behölls trots svenska kåldolmar: äggcitronsåsen och smaksättningen skiljer. Mexikansk gul ärtsoppa (tomat, spiskummin, tortillastrimlor) behölls bredvid den svenska. Granska gärna dessa tre.

## Köpbarhet
Betans plandiagnostik 2026-11-19 (Lund 25 butiker, Malmö 54 butiker) visar att olivolja, mozzarella, rimmat fläsk, majstortillas, fisksås, mynta, balsamvinäger, majsgryn och risottoris inte går att köpa i minst ett av områdena. De ersattes: rapsolja, ost, tortillas, ljus soja, persilja, rödvinsvinäger; rimmat fläsk togs bort. `test_cheap_bases_20261119.py` håller listan.
Recepten är inte kvalificerade mot betans varor ännu. Författarverktygets kvalificering kräver import i den körande appen, och den äldre prisartefakten saknar de flesta råvaruindex. Kontroll sker efter aktivering med vanliga planer och den dagliga kontrollen av recept som saknar köpbara varor.

## Grundrätter (standardvariantens namn och huvudråvara)

**Svenskt**
- Korv stroganoff med grädde, senap och ris (falukorv)
- Stekt blodpudding med stuvad vitkål, potatis och lingon (blodpudding)
- Vitkålssoppa med frikadeller, morot och potatis (vitkål)
- Leverbiffar med stekt lök, gräddsås, potatis och lingon (kycklinglever)
- Pytt i panna med falukorv, stekt ägg och rödbetor (falukorv)
- Havrebiffar med morot och ost, gräddsås och potatis (havregryn)

**Grekiskt**
- Lahanorizo med dill, citron och fetaost (vitkål)
- Lahanodolmades med fläskfärs, dill och äggcitronsås (vitkål)
- Sikotakia med citron, oregano och ugnspotatis (kycklinglever)
- Ugnsbakade gula ärtor med tomat, morot och dill (gula ärtor)
- Pasta med tonfisk, tomat, oliver och oregano (tonfisk)
- Biftekia på fläskfärs med citronpotatis och tzatziki (fläskfärs)
- Patates yahni med morot, ärtor och fetaost (potatis)
- Rödbetor med skordalia, kokta ägg och vitbönor (rödbeta)
- Briam med potatis, morötter, paprika och fetaost (morot)

**Italienskt**
- Kål- och potatissoppa med ris, rosmarin och parmesan (vitkål)
- Tonfiskbullar med citron och persilja i tomatsås, med ris (tonfisk)
- Fläskfärsbullar med fänkålsfrö i tomatsås, pasta och parmesan (fläskfärs)
- Korv och potatis i ugn med paprika, lök och rosmarin (falukorv)
- Potatisfrittata med lök, parmesan och tomatsallad (ägg)
- Potatisgnocchi i tomatsås med basilika och parmesan (potatis)

**Mexikanskt**
- Picadillo med fläskfärs, potatis, morot och ärtor, med ris (fläskfärs)
- Krispiga potatistacos med ost, vitkålssallad och tomatsalsa (potatis)
- Tonfisktostadas med tomat, lök, koriander och svarta bönor (tonfisk)
- Kycklinglever med lök, tomat och chili, ris och bönor (kycklinglever)
- Korv a la mexicana med tomat, lök, paprika och chili, med ris (falukorv)
- Mexikansk gul ärtsoppa med tomat, morot och krispiga tortillastrimlor (gula ärtor)
- Charrobönor med bruna bönor, korv, tomat och rökig paprika (bruna bönor)
- Albóndigas med ris och persilja i fyllningen, morot och zucchini i tomatbuljong (fläskfärs)
- Papas con huevo med salsa roja och tortillas (ägg)
- Sopa de col med potatis, morot, majs och lime (vitkål)

**Indiskt**
- Vitkål och ärtor med ingefära, tomat och garam masala, med ris (vitkål)
- Ghugni med gula ärtor, potatis, tomat och ingefära, med ris (gula ärtor)
- Kaleji masala med ingefära, vitlök och garam masala, med ris (kycklinglever)
- Kryddiga tonfiskcutlets med kachumbersallad (tonfisk)
- Dum aloo med ingefära, tomat och garam masala, med ris (potatis)
- Rödbetscurry med kokos, senapsfrön, ingefära och linser, med ris (rödbeta)
- Gajar matar med ingefära, tomat och kikärtor, med ris (morot)
- Kålkofta i kryddig tomatsås med ingefära och garam masala, med ris (vitkål)
- Rajma på bruna bönor med ingefära, tomat och garam masala, med ris (bruna bönor)

**Thailändskt**
- Wokad vitkål med vitlök, chili och soja, ris och stekt ägg (vitkål)
- Wokad kycklinglever med ingefära, salladslök och ostronsås, med ris (kycklinglever)
- Yam tuna med citrongräs, rödlök, tomat och jordnötter, med ris (tonfisk)
- Stekt ris med tonfisk, ägg, salladslök och ärtor (tonfisk)
- Klar kålsoppa med fläskfärsbullar, morot, vitpeppar och koriander, med ris (vitkål)
- Kai jeow moo sap, frasig omelett med fläskfärs, ris och chilisås (ägg)
- Röd curry med potatis, morot och kikärtor, lime och koriander (potatis)
- Khao tom med fläskfärs, ingefära, stekt vitlök och salladslök (fläskfärs)
- Sötsur wok med korv, paprika, gurka och tomat, med ris (falukorv)
