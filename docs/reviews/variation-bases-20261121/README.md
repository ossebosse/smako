# 100 fler middagar där utbudet är tunt (2026-11-21)

Ägarens begäran 2026-11-21: ”Generera 100 fler recept där det spelar roll.” Svar på frågan: 100 nya grundrätter, var och en i tre varianter (simple, standard, extended), alltså 300 recept. AI-författade utkast, inte provlagade.

## Var det spelar roll
Mätning på betan 2026-11-21 (Lund, en rätt i taget, 2 portioner, kostvalen Allt, Vegetariskt, Veganskt och Fisk) visade var de billiga rätterna saknas:

| Segment | Grundrätter | Under 70 kr | Under 100 kr |
|---|---|---|---|
| Fisk (rätter som bara passar Allt/Fisk) | 102 | 4 | 11 |
| Kött | 301 | 7 | 53 |
| Vegetariskt med ägg/mejeri | 156 | 13 | 67 |
| Veganskt | 170 | 56 | 123 |

Därför: **31 fiskrätter** (vit fisk, tonfisk, sardiner, sill, musslor), **38 kötträtter** (kyckling, kycklinglever, fläskfärs, blandfärs, fläskkött, karré, falukorv, isterband, rimmat fläsk, kokt skinka), **16 vegetariska** med ägg och mejeri och **15 veganska**. Sex kök, som tidigare. Dyra råvaror undviks; fisk och kött används i måttliga mängder med billiga tillbehör.

- Källa: `scripts/recipe_layer/variation_bases_20261121.py` med `variation_data/fish/meat/veg/common_20261121.py`. Paketet `smako-variation-bases-20261121`; tillägget i manifestet är bokfört i `library-transition.json`.
- Grönsaksfond är bibliotekets flytande koncentrat (180 ml-flaska): recepten anger koncentratets ml och vattnet i steget.
- Inga dubbletter av befintliga namn eller grundrätts-id. Rätter som redan fanns (t.ex. fasolakia, khao man gai, kai luk koei, baingan bharta) ströks ur planen.
- Varje ingrediens pekar på en identitet med köpbar vara (`test_variation_bases_20261121.py`), standard och extended har 10–15 räknade ingredienser, och säkerhetstemperaturerna (74 °C kyckling och lever, 72 °C färs, 63 °C fisk) står i stegen.

## Köpbarhet
Kvalificering 2026-11-21 mot de aktiva prisunderlagen (Lund 9f06b3bc…, Malmö 3455769f…), en vecka per recept, uppskattat inköpsläge, högst 2 butiker, med `scripts/recipe_layer/qualify_candidate_library.py` och ändringarna i `blocked-ingredients-20261121`: **standard 100/100 och extended 100/100 i både Lund och Malmö**. Simple-varianterna har färre än 10 räknade ingredienser och stoppas därför av standardvalet i kvalificeringen (som för tidigare paket); deras ingredienser finns i standard- och extended-varianterna.

## Grundrätter (standardvariantens namn och huvudråvara)

**Svenskt**
- Sillpudding med potatis, lök, dill och smält smör (matjessill)
- Varm potatissallad med inlagd sill, ägg, rödlök och senapsdressing (ätklar inläggningssill)
- Fiskbiffar med dill, kokt potatis och snabb remouladsås (fisk)
- Pocherad fisk med äggsås, dill och potatis (fisk)
- Tonfiskpaj med purjolök, ost och tomatsallad (tonfisk)
- Stekt potatis med sardiner, rödlök, kapris och gräddfilssås (sardiner)
- Ugnsbakad fisk med purjolök, tomat och dillgrädde, med ris (fisk)
- Kycklinggryta med curry, äpple, purjolök och grädde, med ris (kyckling)
- Fläskpannkaka med lök och lingon, med vitkålssallad (rimmat fläsk)
- Falukorvsgratäng med tomat, senap och potatismos (falukorv)
- Kycklinglevergryta med champinjoner, lök, timjan och grädde, med ris (kycklinglever)
- Fläskfärsbiffar med stekt lök, gräddsky, potatis och lingon (fläskfärs)
- Isterband med rotmos, senap och persilja (isterband)
- Fläskkalops med morötter, kryddpeppar, lagerblad och potatis (fläskkött)
- Makaronipudding med skinka, ost och ärtor (kokt skinka)
- Potatis- och purjolökssoppa med kokt ägg, ost och bröd (potatis)
- Ugnsomelett med potatis, spenat, lök och ost (ägg)
- Morotsbiffar med keso, dillyoghurt och potatis (morot)
- Linsbiffar med potatis, lingon och löksky (linser)
- Vitkålspytt med potatis, rökig tofu och senap (tofu)
- Potatis- och linsgryta med morot, dill och senap (linser)

**Grekiskt**
- Sardiner med citronpotatis, oregano och tomatsallad (sardiner)
- Giouvetsi med tonfisk, liten pasta, tomat och fetaost (tonfisk)
- Psarokeftedes – fiskbiffar med dill, bulgur och tzatziki (fisk)
- Spanakorizo – spenatris med fisk, dill, salladslök och citron (fisk)
- Varma vita bönor med tonfisk, rödlök, tomat och citronpotatis (tonfisk)
- Kotopoulo kokkinisto – kyckling i tomat, kanel och vin med pasta (kyckling)
- Makaronia me kima – spaghetti med fläskfärssås, kanel och vin (fläskfärs)
- Fläskkarré med citron, oregano, vitlök och ugnspotatis (fläskkarré)
- Kyckling med gröna bönor, potatis och dill i tomat (kyckling)
- Hirino me lahano – fläsk- och vitkålsgryta i tomat med kryddpeppar och citron (fläskkött)
- Kotopilafo – kyckling och ris i tomat med kanel och citron (kyckling)
- Fläsk och potatis i tomatsås med kanel, vin och oregano (fläskkött)
- Strapatsada – äggröra med tomat, feta och oregano, med citronpotatis (ägg)
- Kolokithokeftedes – zucchinibiffar med feta och dill, bulgur och tzatziki (zucchini)
- Stekt halloumi med citronlinser, tomat och dill (halloumi)
- Arakas laderos – ärtor, potatis och morot i tomat med dill och bröd (ärtor)
- Kolokithia yahni – zucchini, potatis och kikärtor i tomat med bulgur (zucchini)

**Italienskt**
- Fisk alla livornese med tomat, oliver och kapris, med polenta (fisk)
- Acqua pazza – fisk i tomat- och vitlöksbuljong med potatis och oliver (fisk)
- Spaghetti med musslor, vitlök, tomat, chili och persilja (blåmusselkött utan skal)
- Risotto med tonfisk, citron, ärtor och persilja (tonfisk)
- Pasta med sardiner, broccoli, vitlök, chili och citron (sardiner)
- Ragù på fläskfärs, morot och selleri med pasta och parmesan (fläskfärs)
- Kycklinglever med salvia, lök och vin, med krämig polenta (kycklinglever)
- Maiale al latte – mjölkbräserad fläskkarré med salvia, citron och potatis (fläskkarré)
- Kyckling och potatis i tomatsås med rosmarin, vitlök och oliver (kyckling)
- Pasta al forno med korv, broccoli, tomat och ost (falukorv)
- Pasta e piselli – pasta med ärtor, skinka, lök och parmesan (kokt skinka)
- Polpettone – färslimpa med parmesan och persilja, ugnspotatis och tomatsås (blandfärs)
- Spaghetti med zucchini, ägg, parmesan, vitlök och citron (ägg)
- Polenta med svamp, vitlök och timjan, stekt ägg och parmesan (polenta)
- Riso e patate – ris- och potatissoppa med rosmarin, tomat och parmesan (potatis)
- Pasta e fagioli – bön- och pastasoppa med rosmarin och tomat (bönor)
- Rostad vitkål och potatis med vitlök, rosmarin, vita bönor och citron (vitkål)

**Mexikanskt**
- Arroz con atún – tomatris med tonfisk, ärtor, morot och lime (tonfisk)
- Caldo de pescado – fisksoppa med potatis, morot, chili och lime (fisk)
- Sardinas en salsa roja – sardiner i tomat- och chilisås med ris och bönor (sardiner)
- Tinga de atún – rökig tonfisk i tomat med tortillas, bönor och kålsallad (tonfisk)
- Pescado al mojo de ajo – fisk i vitlöksolja med ris och bönor (fisk)
- Arroz con pollo – kyckling och tomatris med paprika och ärtor (kyckling)
- Puerco en salsa roja – fläsk och potatis i röd chilisås med ris (fläskkött)
- Pollo a la mexicana – kyckling med tomat, lök och jalapeño, ris och bönor (kyckling)
- Calabacitas con pollo – kyckling med zucchini, majs, tomat och tortillas (kyckling)
- Burritos med kryddig fläskfärs, ris, bönor, ost och salsa (fläskfärs)
- Huevos rancheros – stekta ägg i salsa med tortillas och bönmos (ägg)
- Quesadillas med svarta bönor, majs, ost och tomatsalsa (ost)
- Chilaquiles verdes – tortillachips i grön salsa med stekt ägg och ost (ägg)
- Sopa de lentejas – linssoppa med tomat, morot, potatis och lime (linser)
- Tacos med rökig smulad tofu, limekål och tomatsalsa (tofu)

**Indiskt**
- Tonfisk-keema med ärtor, tomat, ingefära och ris (tonfisk)
- Sardincurry med tomat, kokos, senapsfrön och lime, med ris (sardiner)
- Machher jhol – fisk- och potatisgryta med tomat, ingefära och ris (fisk)
- Fiskcurry med tomat, kokos och ingefära, ris och lime (fisk)
- Murgh tari – kycklingcurry med tomat, ingefära och potatis, med ris (kyckling)
- Murgh saag – kyckling i spenatsås med ingefära, tomat och ris (kyckling)
- Kycklingbiryani med yoghurt, ingefära, stekt lök och mynta (kyckling)
- Mulligatawny – kryddig kyckling- och linssoppa med äpple och kokos (kyckling)
- Murgh chole – kyckling och kikärtor i tomatcurry med ingefära och ris (kyckling)
- Kofta på fläskfärs i tomatcurry med ingefära och koriander, med ris (fläskfärs)
- Äggbiryani med stekt lök, tomat, ingefära och koriander (ägg)
- Dahi aloo – potatis i yoghurtsås med spiskummin, ingefära och ris (potatis)
- Tofu bhurji med potatis, tomat och ärtor, med ris (tofu)
- Aloo matar – potatis och ärtor i tomatcurry med ingefära och ris (potatis)
- Masoor dal med spenat, tomat och vitlökstadka, med ris (linser)

**Thailändskt**
- Larb på tonfisk med lime, chili, rödlök och koriander, med ris och gurka (tonfisk)
- Sardiner wokade med tomat, chili, vitlök och lök, med ris och stekt ägg (sardiner)
- Fiskbullar i röd curry med bambuskott och ris (fisk)
- Nudelsoppa med fiskbullar, pak choi, vitlök och koriander (fisk)
- Wokad fisk med chili, vitlök, paprika och ostronsås, med ris (fisk)
- Gai pad khing – wokad kyckling med ingefära, svamp och salladslök, med ris (kyckling)
- Kuay tiew gai – klar kycklingnudelsoppa med pak choi, vitlök och koriander (kyckling)
- Gaeng pa moo – djungelcurry med fläsk, bönor och bambuskott (fläskkött)
- Moo kratiem – vitlöksfläsk med vitpeppar, ris och gurka (fläskkarré)
- Larb gai – hackad kyckling med lime, chili och koriander, ris och sallad (kyckling)
- Tom kha med svamp, citrongräs och kokt ägg, med ris (ägg)
- Pad pak ruam – wokade grönsaker med vitlök, ägg och ris (ägg)
- Wokad tofu med kål, broccoli, ingefära och soja, med ris (tofu)
- Röd curry med tofu, potatis och bönor, med ris och lime (tofu)
- Pad khing tofu – tofu med ingefära, svamp, lök och salladslök, med ris (tofu)