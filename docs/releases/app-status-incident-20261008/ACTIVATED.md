# Appfix aktiverad 2026-10-08

Användaren godkände aktivering, commit och push. App-only-bytet slutfördes
**17:02:10 UTC** på beta.smako.nu med redan byggd och verifierad image:

- Runtime-delta: `293fc6c49400f6f508eebb6772774d4fdfd995c9`.
- BUILD_ID: `app-incident-293fc6c49400`.
- Image: `sha256:c7295a8ea5dcb716f1580b46936da48bd63f24542bca7042e76a2903d9182c8d`.
- Paket: `smako-app-incident-293fc6c49400.zip`, 28 578 byte,
  SHA-256 `c75a23cd91d66c30b3a4517d977c33222f0e3e1288a8e2cce9945b8e75e71e78`.

Detta är dd12 med selektiv statusrättning och incidentinsamling. Måltids- och
sökoptimeringskandidaten är fortfarande inte aktiverad. Paketet byggdes inte om.

## Förkontroll och byte

Faktisk föregående app var dd12 (`c8362751…`). Befintlig Compose-wrapper och
senare source-ops-override lästes innan ändring. Upplöst konfigurationsdiff:
endast `services.app.image` och `services.app.environment.BUILD_ID`.
`COMPLETE_RECIPES_ENABLED=true` bevarades. Alla fyra runtimefilhashar och de
två JavaScript-filer som faktiskt serveras matchar kandidaten/basen.

Befintligt operationslås hölls under konsistent SQLite-backup och appbyte.
Plan-/grocery-backuper klarade integrity_check och foreign_key_check; deras
hashar och storlekar finns i [ACTIVATED.json](ACTIVATED.json). Skyddad lagring:
`/opt/smako/evidence/app-incident-activation-20261008/current-state-backup`.
Privata konfigurationskopior och radfingeravtryck finns där, utanför Git.
Ingen äldre databas återställdes.

Ingen menytrafik hade observerats på nästan två timmar. Två CPU-prov över
10 sekunder gav 0,03/0,04 CPU-sekunder; senaste 15 minuters plantrafik
kontrollerades igen efter backup. Detta är ett trafik-/tomgångsvillkor,
**inte en direkt räkning av processminnesjobb** eller garanti mot samtidiga
nytillkomna anrop. Inga aktiva användarjobb eller avbrutna jobb observerades.

Endast appen återskapades, med `--no-deps --no-build --pull never --timeout 900`.
Mounts, övriga container-ID:n och övrig appmiljö är oförändrade. Operationslåset
släpptes; inga scheman pausades eller ändrades. Serverutrymme före:
13 165 187 072 byte; direkt efter: 9 418 403 840 byte. Befintlig kapacitetskontroll
rapporterar tillräcklig marginal (cirka 8,0 GB beräknat behov). Ingen rensning.

## Faktiska produktionsprov

Vanliga knappflöden med separata verifieringsgäster, mobil layout och dagens
publicerade prisdata. Inga mockade menyer eller injicerade produktionsfel.

| Prov | Utfall | Klick till renderat resultat | Initial inköpstotal |
| --- | --- | --- | --- |
| Chromium, publik | PASS | 70,109 s | 649,95 kr |
| WebKit, personlig | PASS | 60,906 s | 649,95 kr |

Båda: dubbelklick gav en start-POST och ett jobb; omladdning återanslöt till
samma jobb. Fem fullständiga recept, inköpslista och korgaudit `VERIFIED` över
två butiker kontrollerades. Receptbyte ändrade grundrätt. Uttrycklig omräkning
och identisk sparad återläsning av revision 1/2/3 passerade. Annan ägare fick
403 för plan och 404 för jobb. Inga oväntade pageerror eller nätfel registrerades.
Råtiderna är enstaka aktiveringsprov, inte ett nytt prestandabenchmark.

Efter proven var **alla 222 tidigare revisioner och 63 privata tillståndsrader
identiska med backupens radfingeravtryck**. Den nya appens materialisering kunde
läsa samtliga 222 äldre revisioner. Proven tillförde sex revisioner och två
privata verifieringstillstånd. Ingen extra omstart efter proven gjordes.

Kontoinloggning/OIDC är inte konfigurerad (`/api/account/status: DATA_BLOCKED`).
Detta verifierar faktiska gästsessionsflöden, inte signerad kontoinloggning.
WebKit i mobil layout är inte fysisk iPhone-testning.

## Drift och kvarstående osäkerhet

`/ready` är 200, komplett receptflöde påslaget. Disk- och laddat manifest är
oförändrat `price-universe:bc39552cbb018b402f1d05fc0518728aa8d635d8e19a047e919b6e70642e1364`.
Alla fem obligatoriska baser är FRESH och laddade; exakta observationer och
kontrolltid finns i JSON. Ingen prisinsamling, reläregistrering eller källrelease
utfördes. Befintligt relä och schemaläggare bevarades.

Avgränsad driftstatus efter proven visar ingen ny 5xx-metrik. Incidentindexet
skapas först vid ett fel; frånvaro är inte bevis för att alla framtida fel är
uteslutna. Tidigare isolerade 58+58 riktade tester och negativa imageprov
återanvänds versionsbundet enligt [EVIDENCE.json](EVIDENCE.json), inte som nykörda.

**Originalets HTTP 500 är fortfarande FAIL med okänd exceptionkedja och
grundorsak.** Den här aktiveringen bevisar fungerande kontrollerade menyresor
och rättar den separat belagda domänfelshanteringen; den fyller inte historiska
luckor med antaganden. Återgångens begränsningar i [ACTIVATION.md](ACTIVATION.md)
gäller fortsatt; ingen binär återgång eller databasåterställning har utförts.

## Git och belägg

Aktiveringsrapporten committas på `fix/app-status-incident-20261008` och grenen
pushas till användarens `origin` efter granskning. Ingen merge till master,
force-push eller omskrivning av historik ingår. Remoten är publik; nytillkommande
historik har granskats för känsliga filvägar, stora filer och kända
hemlighetsmönster. Träffar var koduttryck och en uttrycklig redigeringstestfixtur.
Det är en avgränsad kontroll, ingen garanti att alla tänkbara hemligheter hittas.

Privata råprov och verktyg: `.local/app-incident-activation-20261008/`.
Browserrapporterna är hashbundna i JSON; sessionsuppgifter, privata planer,
backup och konfiguration pushas inte. Kompakt sanerat underlag:
[ACTIVATED.json](ACTIVATED.json).
