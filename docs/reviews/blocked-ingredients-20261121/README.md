# Blockerande ingredienser i middagarna (2026-11-21)

Ägarens begäran 2026-11-21: ”lös alla blockerande ingredienser”, enligt regeln från 2026-11-20 (leta upp varan och se varför den blockeras; hittas den inte, säg det; säljs den verkligen inte, föreslå ett alternativ; byt aldrig tyst).

## Mätning
Betans planerare kvalificerade varje middag för sig mot de aktiva prisunderlagen (Lund och Malmö, kostval Allt, 2 portioner, uppskattat inköpsläge, högst 2 butiker). 51 ingrediensidentiteter stoppade recept med ”authored ingredient input form is incompatible with product”.

| | Lund kvalificerade / stoppade | Malmö kvalificerade / stoppade |
|---|---|---|
| Före | 2070 / 454 | 2213 / 284 |
| Efter | 2306 / 149 | 2349 / 106 |

## Orsak
De flesta identiteterna är `definition_only` utan någon granskad varulänk, eller med länkar till artiklar som inte längre säljs i Lund och Malmö. Varorna fanns ofta i butikerna under ett annat namn eller varumärke (Coop, Willys, Hemköp). Två fel till: butikernas egen sökindexering lägger t.ex. ”Glutenfri Polenta Eko” under polenta och ”Böngroddar Ekologisk” under böngroddar, så varan hittades aldrig för majsgryn eller groddade mungbönor.

## Åtgärd
- 28 identiteter (namn och form) fick en granskad etikettregel i `PACKAGE_WEIGHT_IDENTITIES` (`backend/app/services/intake_product_links.py`): namnmönster, hylla, uteslutna ord, uteslutna ingredienser och exakt förpackningsvikt. Mönstren är kontrollerade mot varje vara som matchar sökordet i båda städerna.
  - Mozzarella i lag, halloumi, majsgryn/polenta, kokta räkor, kronärtskockshjärtan, sushiris, surkål, sardiner, vinblad, gelatinblad, svart te (Lipton Yellow Label i gram), vattenkastanjer, kokt musselkött, böngroddar och groddade mungbönor (samma vara), salsa verde på tomatillo, lufttorkad skinka, kokta gröna linser, råa vannameiräkor, silkestofu, vegansk smördeg (smördeg utan smör, mjölk och ägg), matjessill, nori, ghee, guanciale, saltgurka.
  - Avrunna former (lag, olja, vatten) planeras på förpackningsvikten enligt ägarbeslut 2026-11-13. Inköpslistan visar nu notisen ”avrunnen vikt kan vara lägre” även för dessa (gällde inte tidigare för bambuskott).
  - Torra, rena och blandade livsmedel (`dry`, `plain`, `mixture`) omfattas av samma regel som `definition_only`.
  - En vara med motstridiga mängd- eller identitetsuppgifter i sin faktaruta godtas aldrig via regeln.
- Varor som matchar en etikettregel hittas nu oavsett hur butiken har indexerat dem.

## Hittas inte i de stora kedjorna (förslag, inget är bytt)
| Ingrediens | Recept | Vad som finns | Förslag |
|---|---|---|---|
| förkokt vitt majsmjöl (arepa) | 9 | bara vanligt majsmjöl och polenta | inget likvärdigt; byt rätterna till majstortillas eller polenta, eller låt dem vara |
| klibbigt rismjöl | 2 | bara vanligt rismjöl | vanligt rismjöl (konsistensen blir inte seg) |
| tapiokapärlor | 2 | inget | inget alternativ; rätterna kan inte lagas |
| uradlinser | 2 | belugalinser | belugalinser |
| bittergurka | 2 | inget | zucchini (mildare) |
| mungbönsstärkelse | 1 | bara i glasnudlar | majsstärkelse eller potatismjöl |
| bläckfisk, rå | 1 | bara panerade ringar | inget bra; räkor ändrar rätten |
| vetegluten | 1 | inget | fast tofu |
| sattu | 1 | kikärtsmjöl (styckvikt) | kikärtsmjöl rostat i torr panna |
| fjälster | 1 | inget | inget |
| mangold | 1 | bara i en salladsmix | spenat eller grönkål |
| fläsklever | 1 | bara leverpastej | kycklinglever |
| kalvlägg med ben | 1 | inget | högrev (annan rätt) |
| runda risnudlar | 1 | Bamboo Tree Vermicelli är granskad som tunn, inte rund | risvermicelli |

## Finns bara i annan form (receptet behöver en ny version)
- gröna mungbönor, kokta: bara torkade (Garant Eko 500 g, Eldorado 800 g). Låt receptet koka torkade bönor.
- svarta linser, kokta: bara torkade belugalinser. Låt receptet koka dem.
- kokta ägg: ägg säljs råa. Låt receptet koka äggen.

## Finns men behöver mer utredning
- ungnötslever och nötinnanlår (lövbiff): finns bara i Malmö (Willys, Hemköp, City Gross).
- kokbanan och rättika: bara ca-vikt-varor; recepten stoppas ändå i Lund.
- fläsksida med svål: bara sidfläsk i bit med ca-vikt (svål oklart) eller rimmat.
- musslor med skal (levande): ICA säljer per kilo och Falkenberg 1 kg fryst (Willys); oklart om de är förkokta.
- nötkött (2 recept i Lund) och bröd (rågbröd/pita, 2 recept).
