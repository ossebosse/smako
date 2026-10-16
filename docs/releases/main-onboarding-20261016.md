# Main och start från en ny klon

Utgångspunkt: GitHubs dåvarande standardgren `master` låg på `bdf0a3a`.
Aktuellt arbete fram till `4eedaa5` låg 25 commits före och var en rak
fortsättning på samma historik. `main` skapas från denna fortsättning.
Arkiv- och verifieringsgrenar bevaras utan att experiment återförs som nya ändringar.

README, DEVELOPMENT och BETA blir aktuella ingångar. Tidigare utvecklingsguide
bevaras uttryckligen som historik. Starthjälparen migrerar en isolerad lokal
databas med mockpriser. Den ersätter inte autentiska testdata eller behörighet
till servern.

Appreleasehjälparen återanvänder exakt patchmatchning och det tidigare
verifierade aktiveringsförfarandet: lås, lugn trafik, databaskopior, app-only
composebyte, versionskontroll för Lund/Malmö, databevarande och bildrollback.
Paketering läser Git och aktiv image; inga privata gamla `.local`-skript behövs.
Den begränsade hjälparen tillåter inte grocery-/scheduler-/beroende-/schemaändringar.

## Verifiering

- Lokal migrering till senaste schema och appimport passerar.
- 29 avgränsade tester för uppvärmning, admission och releasepaketering passerar.
- Paketeringsproven använder tillfälliga Git-repon och simulerad SSH-läsning:
  committade bytes, avvikande runtime, otillåtna ändringar, manipulerat paket,
  ej verifierad aktivering och dokumentationsändringar utan apprelease.
- Ruff och compileall passerar för nya Pythonfiler.
- Ren klon och ny virtuell miljö verifieras innan slutleverans; resultat läggs
  till här. Ingen ny liveaktivering har gjorts för denna verktygsändring.

Betan kör fortsatt `joint-week-refinement-app-e041451`. Uppstartsväntan är
utredd men inte åtgärdad. Ingen automatisk deployment kopplas till Git-push.
