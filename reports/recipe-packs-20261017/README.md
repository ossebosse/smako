# Receptpaket 2026-10-17: kvalificering och tidsmätning

Frusen Lund-artefakt från granskningspaketet (universe `469136bc…`), exakt inköpsläge,
2 butiker, en rätt i taget (`qualify.py`). Källpaketen återskapas med skripten i
denna mapp; de publicerade paketen finns i `backend/app/data/recipes/`.

## Rättelser (blocked-recipe-fixes-20261017)

```
OK  dinner    15 ingr | Kikärtsmasala med rostad potatis och gurkraita | 226.09 | 35.2s
OK  dinner    15 ingr | Vit bönmasala med rostad potatis och gurkraita | 226.59 | 2.9s
OK  dinner    13 ingr | Tostadas med svarta bönor, majs och limekål | 227.46 | 2.7s
OK  dinner    13 ingr | Tostadas med vita bönor, majs och limekål | 227.46 | 2.6s
OK  dinner    14 ingr | Rökig kycklingpanna med potatis, paprika och limekräm | 279.26 | 2.8s
OK  dinner    14 ingr | Rökig tofupanna med potatis, paprika och limekräm | 250.07 | 3.5s
NEJ dinner    13 ingr | Basilikastekt fläskfärs med vitkål och vitlöksris | No complete basket can be built with the selected stores. | 1.4s
NEJ dinner    13 ingr | Basilikastekt smulig tofu med vitkål och vitlöksris | No complete basket can be built with the selected stores. | 1.5s
OK  dinner    15 ingr | Majs- och linspanna med osttäcke och limekål | 254.94 | 2.7s
OK  dinner    15 ingr | Majs- och färspanna med osttäcke och limekål | 270.06 | 2.7s
NEJ dinner    14 ingr | Syrlig risnudelsallad med kyckling, kål och jordnötter | No complete basket can be built with the selected stores. | 1.4s
NEJ dinner    14 ingr | Syrlig risnudelsallad med tofu, kål och jordnötter | No complete basket can be built with the selected stores. | 1.3s
NEJ dinner    13 ingr | Kokosbräserad torsk med spenat, lime och ris | No complete basket can be built with the selected stores. | 1.4s
NEJ dinner    13 ingr | Kokosbräserad kyckling med spenat, lime och ris | No complete basket can be built with the selected stores. | 1.6s
OK  dinner    13 ingr | Rostad broccoli och tofu med ingefärsglaze och nudlar | 219.96 | 3.5s
OK  dinner    13 ingr | Rostad broccoli och kyckling med ingefärsglaze och nudlar | 265.06 | 2.8s
```

## Basilikarättelser (basil-fixes-20261017)

```
OK  dinner    13 ingr | Basilikastekt fläskfärs med vitkål och vitlöksris | 203.26 | 34.1s
OK  dinner    13 ingr | Basilikastekt smulig tofu med vitkål och vitlöksris | 205.01 | 2.8s
OK  dinner    14 ingr | Syrlig risnudelsallad med kyckling, kål och jordnötter | 285.02 | 2.8s
OK  dinner    14 ingr | Syrlig risnudelsallad med tofu, kål och jordnötter | 231.36 | 2.6s
OK  dinner    13 ingr | Kokosbräserad torsk med spenat, lime och ris | 259.82 | 3.7s
OK  dinner    13 ingr | Kokosbräserad kyckling med spenat, lime och ris | 250.21 | 3.0s
```

## Nya recept (smako-new-recipes-20261017)

```
OK  dinner    12 ingr | Köttfärssås med morot, spaghetti och riven ost | 250.67 | 5.3s
OK  dinner    12 ingr | Kålpuddinggryta med fläskfärs, kokt potatis och senapskräm | 201.22 | 3.4s
OK  dinner    14 ingr | Fiskgratäng med spenat, dill och potatismos | 261.25 | 2.8s
OK  dinner    13 ingr | Matig linssoppa med morot, potatis och örtyoghurt | 177.25 | 2.6s
OK  dinner    12 ingr | Krämig kycklinggryta med champinjoner, spenat och ris | 229.26 | 2.9s
OK  dinner    12 ingr | Laxpasta med spenat, citron och dill | 240.56 | 2.6s
OK  breakfast 11 ingr | Frukostburrito med svarta bönor, ost och tomatsalsa | 181.06 | 2.5s
OK  breakfast 11 ingr | Varm frukostpanna med kikärtor, tomat, spenat och yoghurt | 152.89 | 2.5s
OK  breakfast 12 ingr | Tofuröra med spenat, tomat och rostat bröd | 177.94 | 3.3s
OK  breakfast 10 ingr | Ugnsbakad äppelhavre med kanel, jordnötter och kvarg | 196.2 | 2.8s
OK  snack     11 ingr | Hemgjord hummus med morots- och gurkstavar | 154.24 | 2.5s
OK  snack      5 ingr | Ugnsrostade kryddiga kikärtor | 77.09 | 2.3s
OK  snack      8 ingr | Tzatziki med rostade brödbitar | 110.34 | 2.4s
```

## Middagar i sex matkök (smako-cuisine-dinners-20261017)

```
OK  dinner    14 ingr | Kycklingkorma med kokos, spenat och ris | 251.55 | 35.8s
OK  dinner    14 ingr | Aloo gobi med kikärtor och citronris | 181.68 | 3.0s
OK  dinner    14 ingr | Jordnötsgryta med kyckling, vitkål och ris | 281.58 | 2.9s
OK  dinner    12 ingr | Stekt ris med tofu, ärtor, kål och sesam | 203.69 | 2.9s
OK  dinner    13 ingr | Chili sin carne med svarta bönor, morot och majs | 212.96 | 2.8s
OK  dinner    14 ingr | Kycklingtacos med bönröra, kålsallad och tomat | 270.73 | 3.7s
OK  dinner    12 ingr | Grekisk citronsoppa med kyckling, ris, spenat och dill | 208.57 | 3.0s
OK  dinner    12 ingr | Grekisk linsgryta med tomat, feta, persilja och bröd | 158.23 | 2.6s
OK  dinner    12 ingr | Kycklingcacciatore med champinjoner, paprika och pasta | 229.4 | 2.8s
OK  dinner    12 ingr | Pasta e ceci med tomat, morot, spenat och ost | 183.74 | 2.7s
OK  dinner    12 ingr | Krämig laxsoppa med potatis, morot och dill | 208.75 | 2.9s
OK  dinner    15 ingr | Köttfärslimpa med gräddsås, kokt potatis och pressgurka | 279.36 | 3.8s
```

## Planeringstid per biblioteksläge

Standardprofil 5×4, 2 butiker, `mode=complete`, 1 CPU, en körning per läge.
Alla lägen använder samma kod; bara manifestets aktuella paket skiljer.

```
Före receptarbetet {"s": 77.6, "kr": 638.47, "pool": 158, "kvalificerade": 117, "korgberakningar": 3667}
+ rättelser {"s": 80.7, "kr": 638.47, "pool": 158, "kvalificerade": 127, "korgberakningar": 3730}
+ 13 nya recept {"s": 103.3, "kr": 600.15, "pool": 164, "kvalificerade": 133, "korgberakningar": 4309}
+ 12 middagar {"s": 109.1, "kr": 535.06, "pool": 176, "kvalificerade": 145, "korgberakningar": 4491}
+ basilikarättelser {"s": 100.5, "kr": 535.06, "pool": 176, "kvalificerade": 151, "korgberakningar": 4570}
```

## Varför sex thairätter inte gick att handla

Basilika gick inte att köpa i exakt läge: krukbasilika har bara uppskattad vikt,
Coops skurna basilika 50 g har faktakonflikten `nutrition_basis` (stoppar varan i
`product_form_compatible`) och fryst finhackad basilika uteslöts av `pack:basil`.
Version 2.2.0 tillåter fryst finhackad basilika; alla sex kvalificerar.
