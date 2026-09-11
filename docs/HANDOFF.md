# Smako – aktuell status 11 september 2026

Live: https://beta.smako.nu/personal, build `personal-v2-dinners-20260911c`.
Appkod `7b15c05`. [R1–R9-matris](product/personal-planning-v2.md) ·
[Full rapport: middagar, näringskällor, acceptans och rollback](../reports/smako-dinner-nutrition-20260911.md).

- R3/R6/R7/R8 IMPLEMENTED_AND_VERIFIED; R1/R2/R4/R5/R9 PARTIAL.
- Mina val: ”Tillåt spårbara näringsuppskattningar”, aktivt val, standard av.
- Tre tillagade middagar × 4, Balanserad/max 2 butiker, protein ≥20 g/kcal ≤800:
  426,52 kr. Fem/fyra middagar SEARCH_BLOCKED med nuvarande variationspool.
- Bekräftat generiskt ris: 500 g lager oförändrat, 320 g reserverat; annan meny 419,98 kr.
  Tre middagar + eko 25 %: 480,05 kr, faktisk källstödd ekoandel 50,54 %.
- Tidigare blåmögelost/getmjölk var för bred matchning, korrigerat. Strikt A2 30,38 kr.
- 30 SLV-mappningar, 9 beredningskopplingar. Samma 449 produkter: 83/46/78
  ingrediensdeklarationer/eko/full näring. Tio Coop-detaljer begärda, schemastopp, noll nya fakta.
- Tillagad vikt/fulla allergener DATA_BLOCKED; OIDC separat operatörssteg.
- 405 berörda regressionstester, sista 80 fokuserade; Chromium/WebKit HTTPS passerar.
  Fysisk iPhone ej testad. Noll externa konsumentanrop, inga ändrade goldens.
- Backup 20260911T171809Z; 120 äldre revisioner bevarade, 130 efter acceptans.
  Prismanifest/scheduler orörda; läskompatibel rollback utan databasrestore.
- Basmeny 244,49 kr oförändrad; kall 14,477 s/varm 0,717 s. Ingen prestandaomskrivning.
- Nästa: komplett tredje kolhydrat/beredningskedja och godkänt Coop-detaljschema;
  kall prestanda, Willys-task/relay, ICA OWN och OIDC fortsatt avgränsade.
