# Separat framtida aktivering – inga paket aktiverade

Runtime `5786d5fa6a0febb7a581a70e583e5c876d494da2`.
Kandidatens app och källprocess är separat paketerade. Reläet ändras inte.

| Leverans | Paket | SHA-256 | Image | BUILD_ID |
| --- | --- | --- | --- | --- |
| app | `smako-comparability-app-5786d5fa6a0f.zip` | `750d8382398f192bafc5fbf844b8f60df2dceb4da870c27b6bcc6c274bf0ba5f` | `sha256:ca1b35327a553036d282089f20ff7b3956c737d6f83bd10c835ef3dd83b09c9f` | `comparability-app-5786d5fa6a0f` |
| source | `smako-comparability-source-5786d5fa6a0f.zip` | `60637d72a6f48268d5dd20e223f3d100f4a4295530791c170f7b2471edcf0081` | `sha256:63cc251fcc6f8d4632d1e9e2eb42330b31334beadaa56d235b54cd3bbf5e5742` | `comparability-source-5786d5fa6a0f` |

Paket på `D:\Projects\Smako\.local\comparability-fix-20261010\final-app-package\`
respektive `final-source-package\`. Gemensamt lokalt imagearkiv och dess hash
anges i EVIDENCE.json. Inget arkiv innehåller produktionens användarlagring.

Reproducerbar paketering från repo, med de två exakta basimages lokalt:

```powershell
.venv/Scripts/python.exe -X utf8 scripts/build_comparability_patch.py --commit 5786d5fa6a0f --target app --output .local/comparability-app-rebuild
.venv/Scripts/python.exe -X utf8 scripts/build_comparability_patch.py --commit 5786d5fa6a0f --target source --output .local/comparability-source-rebuild
```

Detta skapar hashkontrollerade byggpaket, inte en aktivering. Deras Dockerfile
kontrollerar basfilhashar innan filer kopieras. Appbas f00/image7635 och
källbas04e/image441e är separata. Appen behöver den tidigare redan granskade
Hemköp-modellrättningen från04e tillsammans med den delade parsern; denna
skillnad är explicit pinnad i byggmanifestet.

## Förkontroller vid senare godkänt byte

1. Läs aktuell driftstatus via `scripts/smako_ops.py status`, verklig app-,
   collector-/scheduleridentitet, Compose-wrapper `/opt/smako/compose`, mounts,
   kapacitet och operationslås. Utvecklingsbasens beta var205, källprocess04e,
   relayfe795. Skriv inte över senare förändringar.
2. Vänta ut berörda jobb. Ta befintlig konsistent backup med senaste
   PlanStore/privata data kvar. Kontrollera arkivets hash och läsbarhet före
   imageinläsning; inget serverbygge eller testdatabasbyte.
3. Källfixen ska bara gå till berörda befintliga insamlings-/API-processer som
   faktiskt använder dessa parsrar och catalog-serialisering. Granska hela
   upplösta Compose-diffen; använd aldrig en global imagevariabel som oavsiktligt
   byter konsumentappen. Bevara scheman, mounts, policy, relä och mottagarkontrakt.
4. Källvalidering/import/rebuild/publicering går genom ordinarie lås och
   kvalitetsgrindar. Denna etapps oktobersvar är bevis, inte tillstånd att
   publicera dem senare som färska. Nya prisunderlag kräver autentiska tider.
   Alla obligatoriska baskontexter och rätt fysisk butik/onlinekanal bevaras.
5. App-only-diffen begränsas till app.image och BUILD_ID. Kompletta recept
   förblir påslagna och befintliga miljövariabler/mounts bevaras. Installera
   aldrig `/evaluation/serve.py`, replayklocka eller lokal testlagring.
6. Kontrollera faktisk image, /ready, laddat manifest samt HTTP-filhasharna i
   EVIDENCE.json. Prova vanlig produktknapp, medlemsmärkning, exakt antal paket,
   uppskattat viktköp, kampanjval, audit, privat sparning, omladdning och ägarskydd
   mot dagens publicerade data med separata verifieringsidentiteter.

## Återgång och begränsningar

Ingen DB-migration. Äldre planer läses med sparade villkor. Nya revisioner kan
innehålla `purchase_units` och `limit_unit`; äldre binär mot dessa nya fält är
**inte kvalificerad** av den här leveransen. Återställ aldrig en gammal databas
över nya planer. Flagga av för kompletta recept stänger inte inköpslistefunktionen
eller källparsrarna och är ingen generell återgång för ändringen.
Vid fel: stoppa fortsatt aktivering/publicering, behåll data och senast giltiga
prisartefakt enligt befintlig driftväg; gör ett specifikt kompatibilitetsbeslut
innan eventuell binäråtergång. Denna rapport hävdar ingen utförd återgång.
