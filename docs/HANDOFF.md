# Smako – aktuell status 12 september 2026

Live: https://beta.smako.nu/personal, build `personal-v2-five-dinners-20260912c`.
Appkod `e626ac0`. [R1–R9-matris](product/personal-planning-v2.md) ·
[Full rapport: fem middagar, blockeringsfördelning, acceptans och drift](../reports/smako-five-dinners-20260912.md).

- Femmiddagsmålet PASSERAR: 5 × 4, Balanserad/max 2 butiker, ≥20 g protein/≤800 kcal.
  Hela paket 677,43 kr; Coop Online Syd + Willys Lund. Alla fem ESTIMATED.
- Nya kandidater: stekt torsk/äggnudlar/vitkål och couscoussallad/tofu/tomat.
  Tredje kolhydraten och beredningskedjor öppnade; inga sänkta variationskrav.
- Mina val: ”Tillåt spårbara näringsuppskattningar”, aktivt val, standard av.
- Exakt tidigare tremiddagsmeny 426,52 kr. Eko ≥25 %: 480,05 kr, faktisk andel 50,54 %.
  Strikt produktbaserat A2 utan uppskattningar 30,38 kr, VERIFIED.
- Skafferifallet: 500 g ris i faktiskt lager oförändrat, 500 g reserverat över fem middagar;
  annan meny 688,73 kr. Rest från hela paket räknas inte som uppäten näring.
- 30 SLV-mappningar, 10 dokumenterade tillagningskopplingar + en granskad insatssummering.
  Samma 449 produkter: 83/46/78 deklarationer/eko/full näring; noll nya Coop-produktfakta.
- Blockeringsfördelning i UI/API: första kandidatavslag per steg och menygrenar per sökdjup.
  Gammal pool 88 → 80 beredningsavslag/8 godkända; variation stoppar vid fjärde middag.
- R3/R6/R7/R8 IMPLEMENTED_AND_VERIFIED; R1/R2/R4/R5/R9 PARTIAL.
  Tillagad vikt och fulla allergener DATA_BLOCKED; variationspoolen fortfarande begränsad.
- 250 distinkta berörda tester, sista 89 fokuserade; Chromium/WebKit HTTPS passerar.
  Nätverkslös serverimage med dagens data passerar. Noll externa konsumentanrop; inga nya goldens.
- Backup 20260912T053012Z; 130 äldre revisioner bevarade, 140 efter HTTPS-proven.
  Driftlås, prismanifest/scheduler oförändrade, läskompatibel rollback utan databasrestore.
- Nästa: fler kompletta beredningskedjor och godkänt Coop-detaljschema. OIDC, Willys-task/relay,
  ICA OWN och kallprestandaomskrivning fortsatt avgränsade. Basmeny 244,49 kr oförändrad.
