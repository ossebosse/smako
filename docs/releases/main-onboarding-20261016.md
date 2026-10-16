# Main och start från en ny klon

Utgångspunkt: GitHubs dåvarande standardgren `master` låg på `bdf0a3a`.
Aktuellt arbete fram till `4eedaa5` låg 25 commits före och var en rak
fortsättning på samma historik. `main` är skapad från denna fortsättning,
pushad och vald som GitHubs standardgren. `origin/HEAD` pekar på `main`.
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
- Kodcommit `8a1bb63` verifierades i en ren klon med egna Git-objekt och en
  ny Python 3.12-venv. Installation från `requirements-dev.txt` lyckades och
  `pip check` rapporterade inga brutna beroenden.
- `scripts/dev.py --check` migrerade från tom databas till `f7b2c3d4e5a6`
  och importerade appen. Ingen gammal lokal konfiguration eller databas kopierades.
- Samma 29 avgränsade tester passerade i den nya miljön på 28,90 s. Läsning
  från ursprungsrepots backend, grocery-kod och rapporter var spärrad, liksom
  externt nätverk. Verifieringsloggen visade inga blockerade läsförsök.
- Lokal server startades med `scripts/dev.py --port 8767`. `/personal`,
  `/health`, `/api/personal/state` och `/static/personal.js` gav HTTP 200.
- En separat klon direkt från GitHub, utan explicit grenval, fick automatiskt
  `main` på `8a1bb63` med ren arbetskopia. Slutrapporten tillkommer därefter
  som dokumentationscommit på samma huvudgren.
- Ingen ny liveaktivering har gjorts för denna verktygsändring.

Betan kör fortsatt `joint-week-refinement-app-e041451`. Uppstartsväntan är
utredd men inte åtgärdad. Ingen automatisk deployment kopplas till Git-push.
