# Fler köpbara råvaror och Malmö-ersättningar aktiverat

Aktiverad **2026-11-07 14:10 UTC** på https://beta.smako.nu.
Main `bdd956c7351d`, app **app-bdd956c7351d-f0f775c9** (bild `sha256:03c2955db657…`,
bas `sha256:1b78d0c11cc0…`). Schedulern orörd. Ägaren godkände aktiveringen
2026-11-07 14:29 lokal tid ("Yes") efter grön CI för `bdd956c`.

## Ändring (åtta filer)

- Granskade godkännanden utan GTIN knyts till butikens artikelnummer (217 av 226),
  hämtat ur produktfakta bundna till exakt samma vara och insamling. Utan detta
  matchade 0 av 226 på dagens data, och 145 receptvarianter (nötkött, lammkött,
  lammfärs, tempeh, sojadryck, senapsfrön, puffat ris, alkoholfri öl) gick inte
  att planera. Registrets sökindex hittar länkarna via artikelnummer.
- Färsk koriander och gräslök efter identitet (exakt vikt ≤150 g); grov- och
  mellanmalen svartpeppar; "fint salt"; bredare namnregler för lax, vit fisk,
  kyckling, nötfärs, tomat, potatis och gul lök.
- Ägarbeslut: exakt förpackningsvikt när ätlig/avrunnen vikt saknas, för listade
  identiteter: fast avokado, riven mozzarella, rispapper, konserverade bambuskott,
  naturell varmrökt lax, ädelost.
- 134 receptvarianter med råvaror som ingen Malmöbutik säljer får granskade nya
  versioner: tamarindkoncentrat → lime-/citronjuice, tapiokastärkelse →
  potatismjöl, färsk makrill → laxfilé, grön mango → syrligt grönt äpple,
  chana dal → gula ärtor. Inte provlagat. Kvitto:
  `docs/reviews/malmo-unavailable-20261107/recipe-review.json`.

Effekt på Malmö-underlaget 2026-11-07 (0ff24174), uppskattningsläge: 120 + 7 + 30
+ 114 receptvarianter blir lösbara; fler varor per basingrediens (t.ex. koriander
1→18, lax 29→50, kyckling 153→194, potatis 119→152). Se projektets
`claude/varutackning-20261107.md`.

## Verifiering

- CI `tests` grön för `bdd956c` (alla partitioner och coverage-overview).
- Bygget: endast de åtta granskade filerna ändrade, 1 385 övriga körtidsfiler
  oförändrade. Kandidatbilden isolerad (utan nätverk, skrivskyddad): appen
  importeras, 2 851 aktiva recept, 0 med tamarindkoncentrat, 217 artikellänkar.
- Aktivering: lugn trafik, backup `/srv/smako/backups/20261107T140021Z`,
  endast appbilden bytt. Bevarat: 337 planversioner, 151 privata tillstånd,
  2 konton, 1 session. Lagringsunderhåll före och efter: complete.
- `/ready` 22350 och 21120: ready, `app-bdd956c7351d-f0f775c9`.
  `/ready/preparation` 21120: 200, bibliotek och båda prisunderlagen ready.
- Publikt prov, ny gäst, 21120, 3 recept × 2 portioner, högst två butiker:
  skapad och sparad (201) på cirka 46 s, återläst i samma session med rätt
  BUILD_ID; varukorgsrader VERIFIED.

## Genomförande

Hjälparens bygg- och aktiveringsjobb (oförändrad workerkod, samma
lagringsunderhåll) kördes fristående på servern via `nohup` och följdes via
logg, eftersom sessionens skal avbryter kommandon efter cirka tre minuter och
en bruten SSH-ström annars kunde avbryta aktiveringen. Ett första försök
avbröts lokalt under lagringsunderhållet före bygget; underhållsprocessen
fick köra klart (13:46–13:53 UTC) innan bygget startades. Tillfälliga filer
i `/tmp` är borttagna.

## Kvar

- 20 av de 134 nya versionerna blockeras av andra råvaror (uradlinser, musslor,
  groddade mungbönor, mangold, bittergurka, kokta ägg).
- Tapiokapärlor, klibbigt rismjöl, uradlinser och bittergurka säljs inte i Malmö
  och definierar sina rätter; inga ersättningar.
- 9 godkännandelänkar saknar artikelnummer och förblir insamlingsbundna.
