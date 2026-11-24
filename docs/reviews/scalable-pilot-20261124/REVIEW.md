# Innehållsgranskning: skalbara mängder i piloträtterna (2026-11-24)

Modellassisterad granskning (Claude), som språkgranskningen 2026-11-02. Inte
provlagat. Paket: `backend/app/data/recipes/incoming/scalable-pilot-20261124/pack.json`
(23 versioner, alla med `design.scaling: "reviewed_ranges"`). Varje version
lästes med ingredienser, roller och alla steg. Frågan per rätt: stämmer
stegen, tiderna, kärlet och de fasta mängderna (sås, smaksättning, deg,
vätska) för varje mängd i intervallet? Stegtexterna ändras inte.

## Godkända utan ändring

| Rätt | Intervall | Bedömning |
|---|---|---|
| Pastapanna med smulad tofu (2 p) | tofu 240–440 g, pasta 100–160 g | Pastan kokar i vatten som tillsätts lite i taget; vätskan följer mängden. |
| Potatispanna med kikärtor och paprika (2 p) | kikärtor 180–360 g, potatis 280–480 g | Potatisen tillagas med "lite vatten" under lock; ryms i en stor panna. |
| Potatispanna med tofu och kål (2 p) | tofu 240–440 g | Tofun vänds in mot slutet; ryms i en stor panna. |
| Ärtpasta med keso och citron (2 p) | keso 190–370 g, pasta 120–190 g | Pastan kokas enligt förpackning; såsen späds efter behov. |
| Kycklingsoppa med zucchini och småpasta (4 p, tre varianter) | kyckling 490–970 g, pasta 180–280 g | Kycklingen fräses före buljongen. Pastan kokar i soppans fasta 1 500 ml; högst 280 g suger upp lite mer vätska, inom rimlighet. |

## Godkända med lägre övre gräns

| Rätt | Före | Efter | Skäl |
|---|---|---|---|
| Lins- och morotssoppa (2 p) | linser 120–240 g | 120–200 g | Spiskummin, tomat och morot är fasta; över 125 % blir soppan mjölig och smaken tunn. |
| Stekbröd med kycklingfyllning (4 p, tre varianter) | kyckling 540–1 040 g | 540–880 g | Fyllningen ska rymmas i fyra vikta bröd av fast degmängd. |
| Ugnsfalukorv med potatis och senap (4 p, tre varianter) | falukorv 490–970 g | 490–810 g | Stegen beskriver en hel korv med skåror i en form. |
| Stekbröd med spenattofu (4 p, tre varianter) | tofu 460–900 g | 460–760 g | Fyllningen ska rymmas i fyra vikta bröd. |
| Ragù på kyckling med pasta (4 p, tre varianter) | kyckling 570–1 110 g | 570–930 g | Kycklingen sjuder 40 min i fast tomat- och vattenmängd och ska täckas. |
| Stekt blodpudding med äpplen och rotsaker (4 p, tre varianter) | blodpudding 540–1 040 g | 540–880 g | Skivorna steks i samma panna som sedan används till äpplen och rotsaker. |

Undre gränserna (75 % av huvudråvaran, 70 % av tillbehöret) är godkända för
alla: mindre mängd ändrar inga steg.

## Kvar till nästa omgång

- Fiskplaki, laxcartoccio, tofudal (1.x) och kycklingbiryani: äldre format
  utan aktiv tid; behöver uppmätt eller granskad aktiv tid innan ny version.
- Soppor och grytor där huvudråvaran kokar i fast vattenmängd (fava, gul
  ärtsoppa, minestrone m.fl.): behöver ett granskat förhållande vatten per
  gram innan de kan skalas.
- Provlagning av ytterlägena i minst ett par rätter innan intervallen
  betraktas som provade.

## Ägarbeslut och helt planprov (2026-11-24)

Ägaren: AI-granskningen räcker; rätterna provlagas inte, små fel godtas.

Helt planprov på dagens Lund-prisdata (58 685 varor) i en engångscontainer på
servern (4,5 GB, 2 kärnor, utan nätverk, produktionsdata skrivskyddad, egen
plandatabas): bilden `app-1032ff8a39be-31d9e0ed` med skalningskoden från
`feature/scalable-recipes` ovanpå och pilotpaketet importerat (23 versioner,
0 avvisningar). Biblioteket fick 3 355 recept varav 57 skalade syskon.
Resultat i `backend/app/data/recipes/incoming/scalable-pilot-20261124/e2e-lund-20261124.jsonl`.

- Pilotens rätter, en middag, inga gränser: originalrecept, inga syskon (50 s kall).
- Protein minst 34,9 / 39,9 g: tofupastan med 360 g tofu (`base-m120s100`).
- Protein minst 46,9 g: tofupastan med 440 g tofu (`base-m147s100`), 51,8 g.
- Protein minst 91,9 g: `NUTRITION_TARGET_NOT_MET` med intervallet 27,7–40,9 g.
- Hela biblioteket, tre middagar utan gränser: 38,5 s, inga syskon.
- Hela biblioteket, tre middagar, protein minst 35 g: 47,2 s; gränsen nåddes
  med originalrecept.
