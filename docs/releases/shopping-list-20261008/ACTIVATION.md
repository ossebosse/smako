# Separat framtida appbeslut – inköpslista

**Inte aktiverad.** Nuvarande beta är meal-library-42fab888ffd7.

Runtime: `38a85dafa18a1fbc63834649fb6af38990bf33ef`.
BUILD_ID: `shopping-list-38a85dafa18a`.
Image: `sha256:dce98e90a79f887e1f0b14bc94d4fcd542e8d187eae865c7401d9a6c23325d02`.
Paket: `smako-shopping-list-38a85dafa18a.zip`, 129631 byte,
SHA-256 `eb1b3596555ab2dfbe62bfa62b8f4476d349faf2b6fb6e767b7cf714fd040d7c`.
Imageexport: 594099712 byte,
SHA-256 `dc9067c9032786b0404f05519f3129033e2c9c57f8bfe90a57fd2143851e0dcd`.
Paket och export ligger på D: under `.local/shopping-list-20261008/`.

Detta är ett granskat tolvfilers appdelta på exakt d17a4c07-imagen. Basens filer
kontrolleras vid bygget. Leveransimagen innehåller också tidigare måltidsbibliotek
med åtta nytillkomna recept och senare status-/incidenträttningar.

Byggkommandot (ange ett nytt utmål; paket skrivs aldrig över):

```powershell
.venv/Scripts/python.exe -X utf8 scripts/build_shopping_patch.py --commit 38a85dafa18a1fbc63834649fb6af38990bf33ef --output .local/shopping-list-reproduce
```

Ett framtida godkänt byte ska följa befintlig app-only-driftväg: läs aktuell
identitet och operationsstatus, verifiera paket/image, vänta ut jobb, konsistent
backup av senaste PlanStore och privata tillstånd, operationslås, granska upplöst
Compose-diff endast för app.image/BUILD_ID. Behåll COMPLETE_RECIPES_ENABLED=true.
Ladda verifierad image utan serverbygge. Byt enbart app med --no-deps --no-build
--pull never. Behåll alla mounts, användardata, proxy och källprocesser.
Verifiera /ready, aktivt manifest, serverad JavaScript-hash, privat lista,
helkorg, sparad GET, gamla/nya revisioner och ägarisolering mot aktuella priser.
Installera aldrig replayklocka, testharness eller testvolymer i produktion.

COMPLETE_RECIPES_ENABLED=false stänger receptfunktionen, **inte den nya
inköpslistan**. Ingen flagga-av-återgång för just inköpslistan finns. Äldre binärers
läsning av nya one_of-revisioner är inte kvalificerad. Vid fel behövs en bedömd
framåträttning eller kvalificerad binär; återställ aldrig en äldre databas över
senare arbete. Ingen aktivering är utförd genom denna dokumentation.

Verifieringskommandot mot redan konfigurerad isolerad replayapp:

```powershell
.venv/Scripts/python.exe -X utf8 scripts/release_verification/shopping_list_browser.py --output .local/shopping-new-evidence --restart-container smako-shopping-packaged-38a85dafa18a
```

Appkoden kommer från imagen; endast separat replayharness och testlagring mountas.
Hemliga sessionsdata, stora råsvar, planer och imageexport ligger utanför Git.
