# Paketets driftgräns och innehåll

Oberoende lokal slutgranskning jämförde `402a5c9` med runtime
`17a9c1330dcc72ff9750a3fa680fa6982f7ed99b` samt läste det faktiska ZIP-paketet.
Inga fjärranrop eller driftändringar gjordes av granskningen.

- `deploy/` inklusive relä-/cron-/policykonfiguration, Dockerfile, .dockerignore,
  insamlare, connectors, refresh-/kommunkod, PriceUniverse-runtime och
  releasebyggare är oförändrade. Lunds femkällorspolicy och 36/48-gränser är
  identiska. Granskningen avser dessa avgränsade driftvägar, inte ett påstående
  om att hela appens planeringskod är oförändrad.
- `complete_recipes_enabled` är `False` som standard och när miljövariabeln
  saknas. Servern avvisar avstängda complete-anrop med `FEATURE_DISABLED`.
  ZIP-paketet aktiverar inte flaggan. Ordinarie Uvicorn är Dockerstarten.
- ZIP-SHA är `d3327b9137d4310707118b5272bc826ed0403ebd6d0c0ab935bb1196efee060a`.
  Alla 651 innehållsfiler matchar både manifest och Git-blobbar; `RELEASE.json`
  ger 652 poster totalt. Privat state, databaser, riktiga miljöfiler och privata
  nycklar påträffades inte. Nya `scripts/recipe_layer/*` ingår inte.
- Befintliga replayverktyg och reläskript ligger kvar oförändrade. Miljöexemplet
  har två placeholders och en tom API-nyckel, och undantas dessutom från imagen.
  SLV-402-underlaget innehåller en historisk offentlig kvalificeringssökväg och
  hash; själva råresultatet eller privat tillstånd följer inte med.
- Produktdeklarationerna utökas från 13 till 20; tidigare 13 är exakt bevarade.
  Den befintliga flyer-parsern kan läsa dem genom oförändrad `exact_declaration`.
  Detta är källkomplettering, utan nya priser eller ändrade insamlingsinställningar.

[Aktiveringsanvisningen](ACTIVATION.md) begränsar en senare installation till
appen. [Dagens separata readiness-kontroll](CURRENT-OPERATION.json) visar att
produktionen fortsatt kör `74c9077`; denna lokala paketgranskning ersätter inte
framtida operatörskontroll av aktiv konfiguration och lagring.
