# Butikstak upp till alla valda butiker: mätning 2026-11-06

Kod: gren `store-set-search` `80627382c72d` (kandidat `app-80627382c72d-76de7352`,
bild `sha256:` enligt `.local/bench-storecap2/build.json`) mot aktiv app
`app-191f173f1e19-e452c67c`. Ingen aktivering.

## Metod

En behållare per bild, i följd, på betaservern efter morgonens insamling:
utan nätverk, skrivskyddad rot, appens datavolymer skrivskyddade, 4 GiB minne,
512 MiB `/tmp`. Plan-lagret pekade på `/tmp`; produktionens användardata
skrevs inte. Endast planerarens icke-hemliga inställningar fördes över
(`APP_ENV=development`, eftersom planeraren inte läser det och produktionsläget
kräver hemligheter). `scripts/release_verification/store_cap_benchmark.py` kör
`PersonalPlanner.create()` på det aktiva prisuniversumet per stad: riktiga recept,
produkter, fakta och kassakontroll, tom gästprofil.

Val: tre middagar, två portioner, blandad kost, fria matkök (Lite omväxling),
uppskattade mängder. Butiksurval från `/api/shopping-location`: Lund 18 (3 km)
och 32 (kommunen utan Coop Online Syd, som Stora Coop Lund ersätter), Malmö 31
(3 km) och 57 (kommunen). Tak 1, 2, 3, 4 och alla valda. Första fallet per stad
är uppvärmning. Fallen finns i `cases.json`, råvärden i `EVIDENCE.json`.

## Resultat

Samtliga 18 fall som båda bilderna kan köra (tak 1–4) gav **identisk korg**:
samma recept, butiker, produkter, förpackningar och totalsumma. Alla fall
VERIFIED. Den aktiva appen saknar valet alla valda (avvisas av modellen).

| Fall | Aktiv app, s | Kandidat, s | Kandidat, kr / butiker |
| --- | ---: | ---: | --- |
| Lund 18, tak 1 | 46,2 | 46,7 | 174,33 / 1 |
| Lund 18, tak 2 | 61,3 | 62,2 | 168,37 / 2 |
| Lund 18, tak 3 | 62,7 | 62,2 | 166,57 / 3 |
| Lund 18, tak 4 | 65,9 | 63,3 | 166,57 / 3 |
| Lund 18, alla | – | 65,8 | 166,57 / 3 |
| Lund 32, tak 1 | 61,3 | 62,0 | 174,33 / 1 |
| Lund 32, tak 2 | 81,2 | 80,3 | 168,37 / 2 |
| Lund 32, tak 3 | 83,3 | 81,8 | 166,57 / 3 |
| Lund 32, tak 4 | 94,6 | 78,2 | 166,57 / 3 |
| Lund 32, alla | – | 77,5 | 166,57 / 3 |
| Malmö 31, tak 1 | 69,3 | 67,1 | 171,73 / 1 |
| Malmö 31, tak 2 | 93,3 | 90,9 | 167,58 / 2 |
| Malmö 31, tak 3 | 103,8 | 95,6 | 166,52 / 3 |
| Malmö 31, tak 4 | 99,1 | 98,7 | 166,52 / 3 |
| Malmö 31, alla | – | 96,5 | 166,52 / 3 |
| Malmö 57, tak 1 | 178,1 | 178,2 | 171,73 / 1 |
| Malmö 57, tak 2 | 242,2 | 236,4 | 162,95 / 2 |
| Malmö 57, tak 3 | 253,3 | 244,4 | 161,50 / 3 |
| Malmö 57, tak 4 | 293,0 | 237,9 | 161,50 / 3 |
| Malmö 57, alla | – | 226,7 | 161,50 / 3 |

Alla valda butiker tar ungefär lika lång tid som tak 3 i samma urval, i alla
fyra urvalen. Tak 4 blev snabbare (Lund 32: 94,6 → 78,2 s; Malmö 57:
293,0 → 237,9 s) eftersom butiksmängdssökningen ersätter uppräkningen ovanför
tak 3. Tak 1–3 kör samma kod; skillnaderna där är brus (±8 s).

En första mätning av kandidat `44c496be77e8` gav 226,6 s för Lund 32 med alla:
uppräkningen användes fortfarande eftersom dominansgallringen lämnade färre än
20 000 delmängder (4 095 delmängder i var och en av 3 261 kassaberäkningar,
enligt cProfile). `80627382c72d` använder sökningen ovanför tak 3 redan från
1 000 delmängder.

## Begränsningar

- Ett fall per kombination, ett körtillfälle; ingen p95 eller samtidighet.
- Tiderna gäller den här mätmiljön och är högre än betans publika varma prov
  (25–50 s). Jämförelsen mellan bilderna är det som avgör.
- Malmö med alla 57 butiker tar redan i dag 3–5 minuter per plan, med alla tak.
  Det är ett befintligt problem i urvalet "hela kommunen", inte i det nya valet.
- Inga syntetiska elaka prisfall i produktion; sådana finns i
  `test_store_set_search.py` och visar att tak 10 av 33 butiker kan bli långsamt.
  Konsumentvalet är därför bara 1–3 eller alla valda.
