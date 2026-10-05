# Låst föreprov för receptens användbarhet

Utvecklingsgren: `feature/recipe-usability-20261005`, från `eac8239` på innehållsgrenen.
Ursprunglig runtime: `dbd89abbed0a0e3b9d8955badabb17615d6c8d09`.
Produktionsappen är separat: `complete-recipes-17a9c1330dcc`; ingen aktivering ingår.

Den omkörda kvalificeringen bekräftar **11/48 uppskattat och 7/48 exakt**.
Samtliga sju exakta versioner ingår i de elva uppskattade: överlapp 7, union 11.
Detta är samma 48 tillagda versioner i två körlägen, inte 18 olika fungerande recept.
De elva motsvarar sex grundrätter; de sju fyra grundrätter. De 48 versionerna
hör till 24 familjeförslag, varav tio överlappar äldre familjer. Bibliotekets äldre
104 versioner är en separat mängd och har inte skrivits om.

## Underlag och reproducerbarhet

- PriceUniverse: `price-universe:b8a677e3e46828048a1946edbeaeb75649cd35f208da826536561fcd4cc90b6c`.
- Artefakt SHA-256: `f82d66103e830b82b7d919fe847fd5b3ef85c5e323e0a2133c338f064dfb8768`.
- Fakta: `retained-catalog-facts-v9-ready-baked-bread:6d0a692188c0e3efbd674814ececf5ff21208aba0fcc2087c11700970ce473b5`.
- Replayklocka: `2026-10-04T07:19:16.028059+00:00`, den bevarade revisionens tid,
  inte ett påstått uppmätt ursprungligt klickögonblick.
- Alla 2 233 refererade råfiler och hela prisartefakten kopierades till en ny isolerad
  indatauppsättning och hashkontrollerades. Ingen gammal databas återställdes i drift.
- Samma sparade huvudbegäran: fem middagar, fyra portioner, Balanserad, fem
  tillåtna matkök, 10–15 ingredienser, proteinmål 30 g, tre butiker, uppskattat köp
  och separat näringsmedgivande, angivna medlemskap, tomt skafferi. Fem tillåtna
  matkök innebär inte ett nytt krav på exakt en rätt från varje kök.
- Sökbudget, 2 CPU, 3 GiB och en tung beräkning i taget bevaras.

Fulla sanerade request-/planresultat, profiler och råbevis ligger utanför Git under
`.local/recipe-usability-20261005` och `/var/tmp/smako-recipe-usability-20261005`.
`comparison-plan.json` låstes före resultatgranskningen med huvudfall, Billigast,
Varierad, grekiskt, grekiskt med skafferi, indiskt vegetariskt, blandat protein 40,
alla matkök samt samtliga fyra etablerade 15/20-profiler.

## Tre nya föreberäkningar

| Prov | Kall process till serialiserat resultat | Kall beräkning | Varm ny beräkning |
| --- | ---: | ---: | ---: |
| A1 | 91,37 s | 74,81 s | 64,70 s |
| A2 | 94,60 s | 78,48 s | 70,21 s |
| A3 | 93,44 s | 77,58 s | 67,57 s |

Alla tre ger 768,04 kr på detta historiska underlag. Beloppet är ett resultat,
inte ett hårdkodat acceptansvärde. Uppgifterna ovan är backendmått, inte klicktid.
Varm betyder en ny beräkning i samma process, utan färdigplancache.

## Uppmätt profil och prioritering

Separat tung cProfile-körning: 141 miljoner anrop. Kumulativa spann överlappar
och ska **inte summeras**. Av den profilerade planerartiden ligger cirka 103,7 s
i recept-/veckokorgar, 50,2 s i förpackningsoptimering, 22,4 s i audit och 19,7 s
i kandidatberedning. 2,9 miljoner upprepade delmängdsval och 870 000
kanoniseringar motiverar återanvändning av exakt samma rena delresultat.
Slutprestanda mäts utan cProfile. Oberoende slutaudit ska fortfarande köras.

De faktiska oberoende ingrediensstoppen visar bland annat saknad mildhetsuppgift,
saknade chilialias i kandidatinhämtning, småpastans hela produktnamn, äggidentitet,
avrunnen majs, pitans beredningsform samt mjölkens mängdbasis. Ett första fel
räknas inte som receptets enda fel; en enskild åtgärd räknas som räddning först
när hela oförändrade receptet kvalificeras.

Nya källor behåller verklig hämtningstid. Jämförelse C är därför uttryckligen
en **berikad historisk jämförelse**. A och B använder ursprungliga faktaregister.
