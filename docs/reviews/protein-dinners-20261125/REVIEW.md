# 145 nya middagar med kött, fisk och kyckling (2026-11-25)

Ägarens beställning 2026-11-25: fler middagar som når ett proteinmål billigt,
främst kött (gris, lårfilé), vardagsfisk och kyckling, spridda över de sex
köken och skalbara från början. Ägaren har sagt att AI-granskning räcker och
att små fel är acceptabla. Recepten är inte provlagade.

## Innehåll

| Kök | Kött | Fisk/skaldjur | Kyckling | Totalt |
|---|---|---|---|---|
| Svenskt | 13 | 8 | 4 | 25 |
| Italienskt | 10 | 9 | 7 | 26 |
| Grekiskt | 10 | 8 | 6 | 24 |
| Indiskt | 9 | 7 | 8 | 24 |
| Mexikanskt | 10 | 8 | 6 | 24 |
| Thailändskt | 8 | 8 | 6 | 22 |
| **Totalt** | **60** | **48** | **37** | **145** |

Källa: `scripts/recipe_layer/protein_dinners_20261125/` (kompakt data, en fil
per kök, `build.py` skriver `smako-recipe-authoring-v1`). Paketen gjordes med
`meal_library_cli author` och importerades som sex nya `meal-pack-*`.

## Granskning (AI)

- **Rätterna:** etablerade, klassiska rätter eller tydliga vardagsrätter i
  respektive kök. Jämförda mot alla 940 befintliga middagars bas-ID och namn;
  inga ID-krockar (import: 145 `new_recipe`). Ett ren proteinbyte av en
  befintlig rätt har undvikits (till exempel bara en pad thai).
- **Mängder:** 4 portioner. Huvudråvaran har ett granskat intervall
  (ungefär −20 % till +50 %), stärkelsetillbehör −30 % till +20 %. Kryddor,
  marinad och stekfett i huvudråvarans komponent följer med; mjölk, grädde,
  mjöl, ägg, ströbröd, ost, kokosmjölk, yoghurt och krossade tomater gör det inte.
- **Steg:** skrivna så att de stämmer för hela intervallet (”stek köttet”, inga
  gram för huvudråvaran). Torr skalbar råvara (ris, pasta, bulgur) kokas utan
  fast vattenmängd. Säkerhetstemperatur anges för kyckling (74 °C), färs (72 °C)
  och fisk (63 °C); helt kött 68 °C, lammstek 60 °C.
- **Standardval:** alla 145 har 10–15 räknade ingredienser, så de väljs med
  standardinställningarna. Inga varningar från `author`.
- **Anpassningar som är medvetna och synliga i namn/etikett:** kritharaki är
  vanlig pasta med etiketten ”Kritharaki (risformad pasta)”; pita- och nanbröd
  köps som bröd; klibbigt ris som ”Klibbigt ris eller sushiris”; thaibasilika
  som basilika; strösocker i stället för palmsocker; chipotle ersatt av ancho
  och rökt paprika (rätterna heter ”rökig”, inte chipotle); tomatillosås på
  burk i chile verde och salsa verde-rätterna.

## Köpbarhet (ägarbeslut 2026-11-20)

Varje recept kvalificerat som en egen vecka i ordinarie planerare mot dagens
aktiva prisunderlag, uppskattat inköpsläge, högst 2 butiker, i en tillfällig
container med appens image och skrivskyddade data. **145/145 i Lund och
145/145 i Malmö.** Första körningen stoppade 15 recept i Lund; åtgärdat så här:

- *Mörkt muscovadosocker* (11 thairätter): varan finns i Lunds butiker
  (”Muscovadorörsocker Mörkt”) men identiteten fick ingen köpbar vara i Lund
  (gick i Malmö). Ersatt med strösocker. Länkningen bör ses över separat.
- *Rökt makrill:* bara makrill i tomatsås finns i Lund. Rätten använder nu
  varmrökt lax (”Varm potatissallad med varmrökt lax, ägg och rädisor”).
- *Kalops, skinkpaj, kotopita:* gick bara med tre butiker (äppelcidervinäger
  respektive purjolök fanns bara på Hemköp i Lund). Vinägern ersatt med
  palsternacka i grytan, purjolöken med gul lök.

## Recepten

Pris = en veckas inköp för just den rätten, 4 portioner, högst 2 butiker
(hela förpackningar, därför högre än portionskostnaden).

| Kök | Rätt | Typ | Ingredienser | Minuter | Lund kr | Malmö kr |
|---|---|---|---|---|---|---|
| Svenskt | Köttbullar med gräddsås, potatismos och lingon | Kött | 11 | 43 | 307 | 307 |
| Svenskt | Kalops med kokt potatis och persilja | Kött | 10 | 133 | 392 | 352 |
| Svenskt | Biff Rydberg med äggula, senapsgrädde och potatis | Kött | 10 | 50 | 569 | 567 |
| Svenskt | Raggmunk med stekt fläsk, lingon och kålsallad | Kött | 11 | 53 | 318 | 297 |
| Svenskt | Pytt i panna med stekt ägg och saltgurka | Kött | 10 | 56 | 266 | 255 |
| Svenskt | Ugnsstekt fläskkarré med rotfrukter och senapssås | Kött | 10 | 74 | 258 | 257 |
| Svenskt | Tacopaj med nötfärs, ost och krispig sallad | Kött | 13 | 60 | 307 | 291 |
| Svenskt | Sjömansbiff med potatis, lök och öl | Kött | 10 | 92 | 539 | 538 |
| Svenskt | Pepparrotskött med kokt potatis | Kött | 11 | 115 | 394 | 350 |
| Svenskt | Stekt fläskkarré med svampsås, potatis och haricots verts | Kött | 10 | 30 | 298 | 298 |
| Svenskt | Fiskgryta med räkor, saffran och vitlökscrème | Fisk/skaldjur | 12 | 43 | 374 | 375 |
| Svenskt | Hemgjorda fiskpinnar med potatismos, ärtor och remouladsås | Fisk/skaldjur | 13 | 35 | 366 | 365 |
| Svenskt | Stekt lax med stuvad spenat och kokt potatis | Fisk/skaldjur | 11 | 25 | 346 | 308 |
| Svenskt | Stekt sej med brynt smör, ägg, räkor och pepparrot | Fisk/skaldjur | 11 | 28 | 329 | 329 |
| Svenskt | Makaronilåda med tonfisk, ärtor och ost | Fisk/skaldjur | 11 | 49 | 177 | 176 |
| Svenskt | Varm potatissallad med varmrökt lax, ägg och rädisor | Fisk/skaldjur | 11 | 27 | 336 | 331 |
| Svenskt | Kycklingfrikassé med morötter, champinjoner och ris | Kyckling | 11 | 34 | 306 | 298 |
| Svenskt | Kycklinglårfilé med potatisgratäng och haricots verts | Kyckling | 10 | 64 | 261 | 260 |
| Svenskt | Kycklingpaj med broccoli och ost | Kyckling | 12 | 73 | 280 | 279 |
| Svenskt | Torskrygg med ugnsrostade rödbetor, pepparrotscrème och potatis | Fisk/skaldjur | 13 | 43 | 376 | 377 |
| Svenskt | Räkpaj med dill, purjolök och ost | Fisk/skaldjur | 13 | 72 | 252 | 252 |
| Svenskt | Grillad kyckling med krämig potatissallad och rädisor | Kyckling | 14 | 38 | 324 | 321 |
| Svenskt | Skogsgryta med fläsk, svamp och grädde, potatismos och lingon | Kött | 12 | 63 | 311 | 311 |
| Svenskt | Skinkpaj med stekt lök och ost | Kött | 13 | 74 | 280 | 225 |
| Svenskt | Lammstek med rosmarin, rostad potatis och rödvinssås | Kött | 10 | 104 | 458 | 556 |
| Italienskt | Fläskscaloppine med champinjoner, vitt vin och potatis | Kött | 11 | 33 | 390 | 390 |
| Italienskt | Spezzatino – nötgryta med potatis, morötter och rött vin | Kött | 12 | 113 | 501 | 439 |
| Italienskt | Ugnsstekt fläskkarré med fänkål, rosmarin och potatis | Kött | 12 | 80 | 421 | 394 |
| Italienskt | Salsiccia med vita bönor i tomat och salvia | Kött | 11 | 36 | 365 | 351 |
| Italienskt | Fläskinvoltini med parmesan och salvia i tomatsås, med polenta | Kött | 13 | 47 | 420 | 397 |
| Italienskt | Tagliata – skivad biff med rucola, parmesan och rostad potatis | Kött | 10 | 38 | 686 | 649 |
| Italienskt | Peposo – pepprig nötgryta med rött vin och krämig polenta | Kött | 12 | 142 | 610 | 558 |
| Italienskt | Fläskkarré alla pizzaiola med kapris, oliver och potatis | Kött | 10 | 23 | 312 | 312 |
| Italienskt | Cannelloni med köttfärs, tomatsås och bechamel | Kött | 13 | 57 | 398 | 391 |
| Italienskt | Fläskgryta med ärtor, tomat och vitt vin | Kött | 11 | 72 | 314 | 309 |
| Italienskt | Cacciucco – toskansk fiskgryta med musslor, räkor och rostat bröd | Fisk/skaldjur | 12 | 33 | 402 | 402 |
| Italienskt | Linguine med räkor, zucchini, citron och chili | Fisk/skaldjur | 10 | 20 | 397 | 395 |
| Italienskt | Ugnsbakad lax med salsa verde, potatis och haricots verts | Fisk/skaldjur | 10 | 22 | 407 | 372 |
| Italienskt | Gratinerad fisk med örtbröd, ugnstomater och potatis | Fisk/skaldjur | 11 | 35 | 385 | 385 |
| Italienskt | Risotto med fisk, räkor och musslor | Fisk/skaldjur | 12 | 35 | 545 | 545 |
| Italienskt | Lasagne med lax, spenat och citronbechamel | Fisk/skaldjur | 12 | 59 | 426 | 359 |
| Italienskt | Torsk med kikärtor, rosmarin, tomat och spenat | Fisk/skaldjur | 10 | 24 | 369 | 369 |
| Italienskt | Panerad fisk alla milanese med tomatsallad och potatis | Fisk/skaldjur | 13 | 26 | 406 | 406 |
| Italienskt | Ugnspasta med tonfisk, ricotta, spenat och mozzarella | Fisk/skaldjur | 12 | 39 | 200 | 200 |
| Italienskt | Pollo alla diavola – stark kyckling med citron, potatis och rucola | Kyckling | 11 | 59 | 347 | 347 |
| Italienskt | Kycklinggryta med paprika, oliver och tomat på polenta | Kyckling | 11 | 45 | 355 | 331 |
| Italienskt | Penne med kyckling, broccoli, vitlök och parmesan | Kyckling | 10 | 16 | 302 | 279 |
| Italienskt | Tagliatelle med kyckling, champinjoner och timjan | Kyckling | 12 | 24 | 347 | 344 |
| Italienskt | Ugnsrostad kyckling med potatis, rödlök och citron | Kyckling | 10 | 58 | 318 | 318 |
| Italienskt | Gnocchi med kyckling, spenat och ädelostsås | Kyckling | 10 | 27 | 352 | 352 |
| Italienskt | Parmesanpanerad kyckling med tomatsallad och citronpotatis | Kyckling | 12 | 40 | 395 | 379 |
| Grekiskt | Moussaka med köttfärs, aubergine och potatis | Kött | 15 | 83 | 434 | 418 |
| Grekiskt | Pastitsio – grekisk pastagratäng med köttfärs och bechamel | Kött | 15 | 77 | 410 | 396 |
| Grekiskt | Giouvetsi – nötkött och kritharaki i tomat och kanel från ugnen | Kött | 13 | 115 | 483 | 417 |
| Grekiskt | Soutzoukakia – kryddiga färsbiffar i tomatsås med ris | Kött | 13 | 47 | 346 | 324 |
| Grekiskt | Fläskgyros med pitabröd, tzatziki och pommes från ugnen | Kött | 13 | 38 | 308 | 310 |
| Grekiskt | Lammfrikassé med sallad, dill och äggcitronsås | Kött | 10 | 99 | 435 | 435 |
| Grekiskt | Kokkinisto – nötkött i tomatsås med potatismos | Kött | 14 | 104 | 535 | 486 |
| Grekiskt | Tigania – fläsk i vin och senap med oregano och potatis | Kött | 12 | 38 | 337 | 311 |
| Grekiskt | Papoutsakia – fyllda auberginer med köttfärs och bechamel | Kött | 13 | 53 | 400 | 384 |
| Grekiskt | Stifado – nötgryta med pärllök, rött vin och kanel | Kött | 12 | 141 | 568 | 503 |
| Grekiskt | Garides saganaki – räkor i tomat och fetaost med ris | Fisk/skaldjur | 13 | 27 | 418 | 417 |
| Grekiskt | Ugnsbakad fisk med citron, oregano och potatis | Fisk/skaldjur | 11 | 60 | 348 | 348 |
| Grekiskt | Laxsouvlaki med tzatziki, pitabröd och tomatsallad | Fisk/skaldjur | 12 | 35 | 428 | 374 |
| Grekiskt | Psarosoupa – fisksoppa med grönsaker och äggcitron | Fisk/skaldjur | 12 | 44 | 372 | 372 |
| Grekiskt | Räkor och kritharaki från ugnen med tomat och fetaost | Fisk/skaldjur | 13 | 42 | 408 | 404 |
| Grekiskt | Stekt lax med citron- och dillkritharaki och spenat | Fisk/skaldjur | 11 | 19 | 416 | 384 |
| Grekiskt | Fisk på ugnsrostade grönsaker – briam med potatis och zucchini | Fisk/skaldjur | 13 | 70 | 376 | 375 |
| Grekiskt | Stekt fisk på gul ärtpuré med rödlök och kapris | Fisk/skaldjur | 11 | 58 | 335 | 334 |
| Grekiskt | Kyckling och kritharaki från ugnen med tomat och kanel | Kyckling | 13 | 50 | 336 | 322 |
| Grekiskt | Kycklinggyros med pitabröd, tzatziki och ugnspotatis | Kyckling | 14 | 38 | 361 | 363 |
| Grekiskt | Ugnsbakad kyckling med fetaost, tomat och oliver och bulgur | Kyckling | 12 | 39 | 336 | 318 |
| Grekiskt | Kotopita – kycklingpaj i filodeg med fetaost och dill | Kyckling | 13 | 70 | 361 | 361 |
| Grekiskt | Yoghurtmarinerad kyckling med tomatbulgur och gurksallad | Kyckling | 14 | 64 | 356 | 356 |
| Grekiskt | Kyckling på ugnsrostade grönsaker med zucchini, aubergine och potatis | Kyckling | 13 | 68 | 342 | 341 |
| Indiskt | Butter chicken – kyckling i krämig tomat- och smörsås med ris | Kyckling | 14 | 62 | 327 | 325 |
| Indiskt | Chicken tikka masala med ris och gurkraita | Kyckling | 14 | 53 | 301 | 287 |
| Indiskt | Chicken jalfrezi med paprika, lök och tomat och ris | Kyckling | 14 | 25 | 307 | 286 |
| Indiskt | Dhansak – kyckling och röda linser med pumpa och ris | Kyckling | 14 | 45 | 297 | 297 |
| Indiskt | Chettinad-kyckling med svartpeppar, fänkål och kokos | Kyckling | 14 | 41 | 323 | 324 |
| Indiskt | Do pyaza – kycklinggryta med dubbelt med lök och ris | Kyckling | 13 | 49 | 291 | 289 |
| Indiskt | Kati rolls – kryddig kyckling, ägg och lök i tunnbröd med myntayoghurt | Kyckling | 14 | 52 | 378 | 336 |
| Indiskt | Achari-kyckling med senapsfrön, fänkål och yoghurt | Kyckling | 15 | 45 | 326 | 321 |
| Indiskt | Saag gosht – lamm och spenat med kryddor | Kött | 13 | 119 | 389 | 399 |
| Indiskt | Madrascurry med nötkött, kokos och tomat | Kött | 15 | 132 | 448 | 405 |
| Indiskt | Bhuna gosht – stekt lammcurry med tjock kryddsås och nanbröd | Kött | 15 | 113 | 397 | 396 |
| Indiskt | Seekh kebab av lammfärs med nanbröd, raita och lök | Kött | 15 | 41 | 388 | 388 |
| Indiskt | Xacuti – fläskgryta från Goa med rostad kokos och kryddor | Kött | 15 | 84 | 291 | 283 |
| Indiskt | Peppar-stekt fläsk från Kerala med lök och ris | Kött | 13 | 54 | 295 | 288 |
| Indiskt | Lammbiryani med stekt lök, yoghurt och mynta | Kött | 14 | 108 | 406 | 405 |
| Indiskt | Pasanda – nötkött i yoghurt- och mandelsås med ris | Kött | 14 | 50 | 422 | 415 |
| Indiskt | Aloo gosht – lammgryta med potatis och tomat | Kött | 15 | 100 | 408 | 424 |
| Indiskt | Amritsari fish – friterad fisk i kikärtssmet med myntachutney och sallad | Fisk/skaldjur | 14 | 30 | 348 | 348 |
| Indiskt | Räkmasala i tomat och kryddor med ris | Fisk/skaldjur | 15 | 30 | 414 | 403 |
| Indiskt | Fisk tikka med yoghurtmarinad, citronris och gurksallad | Fisk/skaldjur | 15 | 36 | 348 | 348 |
| Indiskt | Fiskbiryani med stekt lök, kryddor och raita | Fisk/skaldjur | 14 | 53 | 365 | 353 |
| Indiskt | Fiskkofta i tomatcurry med ris | Fisk/skaldjur | 14 | 35 | 352 | 362 |
| Indiskt | Räkpulao med ärtor, kryddor och raita | Fisk/skaldjur | 14 | 37 | 393 | 392 |
| Indiskt | Moilee – fisk i mild kokossås med gurkmeja och ingefära | Fisk/skaldjur | 14 | 22 | 326 | 326 |
| Mexikanskt | Chili con carne med kidneybönor, ris och gräddfil | Kött | 14 | 49 | 303 | 301 |
| Mexikanskt | Tacos med carne asada, lime, pico de gallo och avokado | Kött | 14 | 53 | 641 | 640 |
| Mexikanskt | Barbacoa – långkokt nötkött med ancho, tacos och lök | Kött | 13 | 178 | 487 | 436 |
| Mexikanskt | Bistec a la mexicana – nötkött med tomat, lök och jalapeño, ris och bönor | Kött | 13 | 28 | 376 | 376 |
| Mexikanskt | Chile verde – fläskgryta i grön tomatillosås med ris | Kött | 13 | 97 | 312 | 312 |
| Mexikanskt | Fläsk i adobo med ancho, apelsin och ris | Kött | 15 | 80 | 344 | 339 |
| Mexikanskt | Enchiladas rojas med köttfärs, bönor och ost | Kött | 14 | 54 | 377 | 350 |
| Mexikanskt | Alambre – nötkött, paprika och lök med smält ost i tortillas | Kött | 13 | 27 | 440 | 437 |
| Mexikanskt | Tacos med chorizo och potatis, rödlökssallad och avokado | Kött | 12 | 39 | 292 | 292 |
| Mexikanskt | Milanesa – panerad fläskschnitzel med ris, bönor och salsa | Kött | 13 | 35 | 291 | 291 |
| Mexikanskt | Camarones a la diabla – starka räkor i tomat och ancho med ris | Fisk/skaldjur | 14 | 35 | 405 | 404 |
| Mexikanskt | Pescado a la talla – ugnsgrillad fisk med röd chilimarinad, ris och salsa | Fisk/skaldjur | 13 | 30 | 359 | 359 |
| Mexikanskt | Räktacos med kålsallad, avokado och limekräm | Fisk/skaldjur | 14 | 24 | 432 | 427 |
| Mexikanskt | Lax med mangosalsa, limeris och svarta bönor | Fisk/skaldjur | 12 | 25 | 365 | 365 |
| Mexikanskt | Enchiladas verdes med fisk, spenat och tomatillosås | Fisk/skaldjur | 13 | 43 | 388 | 376 |
| Mexikanskt | Fiskburritos med svarta bönor, ris och chipotlekräm | Fisk/skaldjur | 13 | 28 | 384 | 403 |
| Mexikanskt | Fiskbollar i tomat- och anchobuljong med ris | Fisk/skaldjur | 14 | 31 | 346 | 346 |
| Mexikanskt | Lax med rökig glaze och majssallad med lime och ost | Fisk/skaldjur | 13 | 22 | 374 | 342 |
| Mexikanskt | Pollo asado – citrusmarinerad kyckling med ris, bönor och salsa | Kyckling | 14 | 59 | 301 | 301 |
| Mexikanskt | Kycklingfajitas med paprika, lök, guacamole och tortillas | Kyckling | 14 | 31 | 381 | 352 |
| Mexikanskt | Quesadillas med kyckling, svarta bönor och ost, med salsa och sallad | Kyckling | 14 | 34 | 342 | 351 |
| Mexikanskt | Kyckling i grön tomatillosås med ris och bönor | Kyckling | 12 | 38 | 302 | 302 |
| Mexikanskt | Kyckling i rökig tomat- och chiligräddsås med ris | Kyckling | 14 | 41 | 367 | 344 |
| Mexikanskt | Flautas – krispiga rullade tacos med kyckling, kål och kräm | Kyckling | 14 | 56 | 310 | 302 |
| Thailändskt | Pad kra pao – fläskfärs med basilika, chili och stekt ägg | Kött | 14 | 26 | 323 | 313 |
| Thailändskt | Panang neua – nötkött i krämig röd curry med jordnötter | Kött | 14 | 22 | 436 | 435 |
| Thailändskt | Massaman curry med nötkött, potatis och jordnötter | Kött | 15 | 120 | 499 | 441 |
| Thailändskt | Pad see ew – breda risnudlar med fläsk, broccoli och ägg | Kött | 12 | 22 | 312 | 310 |
| Thailändskt | Pad prik khing – fläsk och haricots verts i röd currypasta | Kött | 12 | 25 | 281 | 247 |
| Thailändskt | Suea rong hai – grillad biff med chilisås, klibbigt ris och grönsaker | Kött | 14 | 43 | 659 | 649 |
| Thailändskt | Khao pad moo – stekt ris med fläsk, ägg och gurka | Kött | 14 | 33 | 262 | 253 |
| Thailändskt | Röd curry med fläsk och pumpa | Kött | 12 | 25 | 284 | 284 |
| Thailändskt | Pad thai med räkor, ägg, böngroddar och jordnötter | Fisk/skaldjur | 13 | 22 | 437 | 435 |
| Thailändskt | Tom yum goong – syrlig räksoppa med citrongräs, svamp och ris | Fisk/skaldjur | 13 | 24 | 352 | 351 |
| Thailändskt | Pla rad prik – krispig fisk med söt chili- och vitlökssås | Fisk/skaldjur | 13 | 23 | 399 | 387 |
| Thailändskt | Choo chee pla – fisk i tjock röd kokoscurry med limeblad | Fisk/skaldjur | 13 | 25 | 371 | 361 |
| Thailändskt | Khao pad goong – stekt ris med räkor, ägg och lime | Fisk/skaldjur | 14 | 33 | 393 | 391 |
| Thailändskt | Röd curry med räkor och ananas | Fisk/skaldjur | 12 | 21 | 389 | 389 |
| Thailändskt | Pla tod kamin – gurkmeje- och vitlöksstekt fisk med ris och gurksallad | Fisk/skaldjur | 14 | 27 | 398 | 383 |
| Thailändskt | Räkor och glasnudlar i gryta med ingefära och svartpeppar | Fisk/skaldjur | 11 | 24 | 431 | 425 |
| Thailändskt | Khao man gai – pocherad kyckling med ingefärsris, buljong och sås | Kyckling | 12 | 57 | 283 | 283 |
| Thailändskt | Gai yang – grillad kyckling med citrongräs, klibbigt ris och gurksallad | Kyckling | 15 | 64 | 345 | 342 |
| Thailändskt | Tom kha gai – kokossoppa med kyckling, citrongräs och svamp | Kyckling | 13 | 24 | 300 | 278 |
| Thailändskt | Khao soi – nordthailändsk currynudelsoppa med kyckling | Kyckling | 14 | 37 | 340 | 337 |
| Thailändskt | Kycklingsatay med jordnötssås, gurkrelish och ris | Kyckling | 14 | 48 | 334 | 333 |
| Thailändskt | Wokad kyckling i ostronsås med broccoli och svamp | Kyckling | 14 | 25 | 337 | 329 |
## Planerartest (Lund, slängcontainer, 2 CPU, låg prioritet)

Samma skript med dagens bibliotek och med de 145 rätterna monterade
(8 012 → 8 709 recept inklusive skalade versioner).

| Plan | Utan | Med | Kostnad |
|---|---|---|---|
| Inga mål, 5 middagar | 79,2 s | 80,3 s | 374,33 kr båda |
| Protein 35 g, 3 | 46,2 s | 48,3 s | 295,84 kr båda |
| Protein 45 g, 3 | 38,8 s | 40,1 s | 323,00 kr båda |
| Protein 45 g, 5 | 38,6 s | 41,4 s | 523,82 kr båda |
| Vegetariskt protein 35 g, 3 | 29,5 s | 29,5 s | 294,98 kr båda |
| Protein 40 g + 700 kcal, 3 | 42,8 s | 45,6 s | 324,40 kr båda |
| 45 g, 5 × 4 portioner, 2 kyckling/1 fisk/2 kött | 88,8 s | 90,9 s | 989,56 kr båda |

Toppminne 2 020 → 2 091 MB. Med dagens priser och 2 butiker valde planeraren
samma rätter i alla testveckor: de nya rätterna är kvalificerade alternativ
(byte av rätt, variation, undvikna senaste rätter) men var inte billigast här.

## Varför de nya rätterna inte valdes (utredning 2026-11-25)

Plan: Lund, 5 middagar × 4 portioner, minst 45 g protein, 2 butiker, basvaror
hemma (salt, peppar, olja, mjöl, socker).

- **De flesta kommer aldrig med.** Med exakt inköpsläge (standard) klarade
  19 av 145 nya rätter kvalificeringen. Stopp: hela köttstycken (nötkött,
  fläskkött, fläskkarré, lammkött) är viktvaror som kräver ”uppskattad vikt”;
  sallad, salladslök, mynta och rädisa i gram hittar ingen köpbar vara.
  Med uppskattat läge 22 av 145: viktvarorna saknar näringsvärden, så proteinet
  kan inte styrkas. Köpbarhetskontrollen före import kördes utan näringsmål och
  i uppskattat läge och fångade inte detta.
- **De som kommer med är dyrare.** Median per rätt (4 portioner, hela
  förpackningar) 383–397 kr mot 309–333 kr för befintliga. De billigaste
  befintliga bygger på billigt protein (kycklinglever, fryst kycklinginnerfilé,
  rimmat fläsk med bruna bönor, linser och tofu) och få ingredienser. De nya
  har dyrare protein (lax 180–200 kr, färs 91–119 kr för 750 g, lårfilé
  100 kr) och fler tillbehör som köps som hela förpackningar.
