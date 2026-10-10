# Utförd käll- och appaktivering, 2026-10-10

Två separata byten under befintligt operationslås, utan serverbygge.

| Del | Runtime / BUILD_ID | Image |
| --- | --- | --- |
| Källprocess | `04e47c691e0c` / `source-ops-04e47c691e0c` | `sha256:441e1a2b357a8248ed5e75ddc513a05fbf1d1b347ece8ee323b4c18b74aa58ca` |
| Konsumentapp | `205cd8ca0f31` / `return-session-205cd8ca0f31` | `sha256:853d5b98b3df4a29e38bb5ff9d35a0d8add6ba247458e33a4e8c8a31073ec7a3` |

Källpaket: `smako-source-ops-04e47c691e0c.zip`, SHA-256
`04a0f6ea0457b55170dffeb9408254343165edb41b3dec0d0bdb40b617c54c75`.
Apppaket: `smako-return-session-205cd8ca0f31.zip`, SHA-256
`e2a9c287c5aa1e1dec98552fccd7857680485daaa121d3ca3319e3fc08314ab9`.

Källbytet ändrade endast scheduler.image och scheduler.environment.BUILD_ID.
Därefter återställdes ordinarie prispublicering och slutkvitto 08:15 UTC.
Appbytet bekräftades **09:55:31 UTC (11:55:31 svensk tid)**. Endast app.image
plus app.environment.BUILD_ID skilde i den fullständiga upplösta Compose-konfigurationen.
COMPLETE_RECIPES_ENABLED=true, mounts och alla andra containrar bevarades.
Samma manifest var aktivt före och efter appbytet: `50c0bb0e83de…`.

Appen före bytet var `shopping-list-6b10628f22d8`, inte den historiska dd12.
Fyra frontendfiler byttes ovanpå den faktiska 6b-imagen. Dess senare recept-,
inköpsliste- och backendfunktioner behölls. Ingen ny måltids-/prestandarelease.

## Förkontroller och lagring

Aktuella image-, paket- och filhashar kontrollerades. Inga plananrop senaste
15 minuter och två CPU-observationer 0,05/0,02 s under vardera 10 s gav
belägg för vila; detta är ingen direkt räknare över processens minnesjobb.
Konsistent SQLite-backup av aktuell PlanStore gjordes, integrity/FK-kontroller PASS.
Backup: 109 346 816 byte, SHA-256
`64f6e3d3fb15352527d4f23b3e42772946f547fb39ca9e409211a9e07950384a`.
240 revisioner och 74 privata tillstånd fanns före appbytet.
Ingen äldre databas installerades. Grocerys kontrollerade användartabeller var tomma.
Privat backup och upplösta konfigurationer ligger under skyddad serverlagring
`/opt/smako/evidence/return-activation-20261010/` och ingår inte i Git.

## Återgång och fortsatt drift

Båda äldre images bevarades. För denna begränsade UI-patch kan appen vid ett
separat återgångsbeslut återgå till den bevarade 6b-imagen med senaste data,
men då återkommer det kända statusfelet. Receptflagga av löser inte detta fel.
Återställ aldrig backup över senare användararbete.

Använd aktuell `/opt/smako/compose`, inte en äldre wrapper som förlorar den
aktiverade källrättningen. Inga globala imagevariabler ändrades. Den äldre
källimagen accepterar inte de nya granskade schemaväxlingarna; en källåtergång
kan åter blockera uppdatering och är inte en normal återhämtningsåtgärd.

Inga uppgifter är pausade. Windowsreläet fe795 och dess S4U/Limited-definition
är bevarade. Ordinarie scheduler kör vidare. Kontrollera aktuell status med
`.venv\Scripts\python.exe -X utf8 scripts\smako_ops.py status`.
Se RESULTS.md och maskinläsbara slutbevis för kontrollerna efter bytet.
