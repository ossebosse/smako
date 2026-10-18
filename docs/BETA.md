# Aktivera från main på den befintliga betan

Källa: `main` i `https://github.com/ossebosse/smako.git`.
Mål: https://beta.smako.nu. Det finns ingen automatisk deployment vid push.
En aktivering väljer alltid en bestämd commit och image, så senare commits
på `main` inte ändrar en pågående release.

## Förutsättningar

- Installera utvecklingsmiljön enligt [DEVELOPMENT.md](DEVELOPMENT.md).
- Behörig operatör behöver SSH-alias `smako` till befintlig server samt
  rättighet att köra `sudo -n python3` och hantera Docker. SSH-nycklar och
  serveradress tillhandahålls av projektets förvaltare, aldrig genom Git.
- Befintlig installation använder `/opt/smako/compose`, containrarna
  `smako-app-1`, `smako-scheduler-1`, `smako-caddy-1`, data i `/srv/smako/data`
  och det gemensamma driftlåset. Detta flöde installerar inte en ny server.
- Läs aktuell [HANDOFF.md](HANDOFF.md), [OPERATIONS.md](OPERATIONS.md) och
  senaste aktiveringsrapport. Senast dokumenterade appkod vid införandet av
  denna guide är `e041451`, BUILD_ID `joint-week-refinement-app-e041451`.
  [Aktiveringen](releases/joint-week-refinement-20261016/ACTIVATED.md) har fyra
  godkända liveprov. Uppstartsväntan är undersökt men ännu inte rättad.

## Vanlig appändring

Hjälparen `scripts/beta_release.py` gör appbytet enligt samma förfarande som
den verifierade aktiveringen 2026-10-16. Den paketerar bara ändrade filer under
`backend/app/`, ovanpå den **faktiskt aktiva** appbilden. Den använder befintlig
exakt patchmatchning i `build_source_patch.py`; filerna måste bli identiska
med den valda Git-versionen. Ingen dold `.local`-katalog från en annan dator
behövs. `.local` nedan är bara nya utdata i din klon.

### 1. Hämta main, kontrollera drift och skapa paket

```powershell
git switch main
git pull --ff-only
git status --short
.venv/Scripts/python.exe -X utf8 scripts/smako_ops.py status

# Ersätt e041451 med senast aktiverade appkod enligt aktuell releasejournal.
.venv/Scripts/python.exe scripts/beta_release.py prepare --from-commit e041451 --commit main --workdir .local/beta-release
```

Arbetskopian ska vara ren; paketet läser enbart committade Git-blobbar.
`prepare` läser aktuell app via SSH, men ändrar inget på servern. Granska
`.local/beta-release/review.json`, Git-diffen och berörda testresultat.
Enbart dokumentationsändringar kräver ingen apprelease; verktyget säger då
att det saknas appändringar. Använd en ny utdatamapp för varje nytt paket.

Om aktiv fil har andra ändringar än Git-basen, om en fil tas bort eller om
beroenden, databasstruktur, grocery-kod eller körbara deploy-filer har ändrats i
intervallet, avbryts detta begränsade appflöde. Gör en separat granskad release
för den förändringen; kopiera inte hela main över den aktiva bilden på chans.
`deploy/.env.production.example` är dokumentation och paketeras aldrig.
Ändringar där ändrar inte serverns miljöfil. Appmoduler vars namn innehåller
`requirements` är vanlig appkod och ingår i den exakta filgranskningen.

### 2. Bygg och verifiera kandidatbilden

```powershell
.venv/Scripts/python.exe scripts/beta_release.py build --workdir .local/beta-release
Get-Content .local/beta-release/build.json
```

Bygget använder den pinnade aktiva basbilden och kör utan nätverk. Det verifierar
filhashar före/efter patchen, compileall och att inga andra runtimefiler ändrats.
Ingen container byts. Resultatet har exakt kandidat-image och BUILD_ID.
Serverunderlaget finns under `/opt/smako/evidence/<release-id>/`.

Verifiera dessutom kandidatens ändrade funktioner med relevanta offlineprov
och vid behov isolerad HTTP-/browsermiljö med separata data. Exempel på
importkontroll av exakt kandidatbild, med image-ID från `build.json`:

```powershell
ssh smako 'sudo -n docker run --rm --network none --read-only --entrypoint python sha256:<kandidatens-image-id> -c "from app.main import app; print(app.title)"'
```

Importkontroll ersätter inte funktionstester. Kör aldrig kandidatprov mot
produktionens skrivbara användardatabas. Ett byggfel lämnar bild/loggar på
servern för diagnos; försök inte tyst återanvända ett ofärdigt release-id.

### 3. Aktivera den verifierade kandidaten

```powershell
.venv/Scripts/python.exe scripts/beta_release.py activate --workdir .local/beta-release --checks-passed
```

Detta är det uttryckliga skrivande steget. Hjälparen kontrollerar att samma
basbild fortfarande kör och att kandidatkvittot är oförändrat, tar befintligt
driftlås, kräver lugn menytrafik, säkerhetskopierar båda SQLite-databaserna
och kontrollerar kopiorna. Den ändrar endast appens image och BUILD_ID via
ett nytt compose-override. Scheduler, proxy, volymer och övrig miljö bevaras.

Om låset är upptaget görs inget appbyte. Låt det ordinarie jobbet bli klart
och kör samma aktiveringskommando igen. Avbryt inte prisinsamlingen och
kringgå inte låset. Vid annan felorsak: läs fel och serverunderlag först.
Skriptet återställer föregående wrapper/appbild vid fel efter bytet och
återställer aldrig produktionsdatabaserna. Om transporten bryts är utfallet
okänt tills driftstatus och serverns `activation-success.json` har lästs;
starta inte en konkurrerande aktivering.

### 4. Verifiera och journalför

```powershell
.venv/Scripts/python.exe -X utf8 scripts/smako_ops.py status
curl.exe -fsS 'https://beta.smako.nu/ready?postal_code=22350'
curl.exe -fsS 'https://beta.smako.nu/ready?postal_code=21120'
```

På Linux/macOS används `curl`. Båda ska svara ready med kandidatens BUILD_ID.
Aktiveringssteget kontrollerar också detta och att tidigare plan-/profilrader
är bevarade. Kontrollera publicerat/laddat prismanifest och gör ett relevant
publikt användarprov: skapa meny, granska köp-/kravkontroller, återläs sparad
meny. Mät första anropet separat från uppvärmda anrop.

Spara en sanerad rapport under `docs/releases/<release>/`, uppdatera
`docs/HANDOFF.md` och committa/pusha till `main`. Ange kodcommit, image,
BUILD_ID, tid, tester, databevarande och kvarvarande begränsningar.
Spara aldrig full compose-miljö, cookies, privata profiler eller backupfiler i Git.

## Andra releasetyper

För ny server, scheduler, databasmigrering eller Windowsrelä behövs separat
verifierad plan. Befintlig paketerare är:

```powershell
.venv/Scripts/python.exe scripts/build_release.py --commit main --output .local/full-release
```

Den skapar källpaket och aktiverar inget. Utgå från aktuell drift och relevanta
delar av `deploy/compose.yaml`, `deploy/compose.release.yaml` och
`deploy/scripts/install_relay_release.ps1`. Historiska driftsättningsguider
beskriver sina dåvarande miljöer; kör inte deras daterade kommandon blint.

Den versionshanterade apphjälparens paketeringsspärrar och klonstart verifieras
separat vid införandet. En ny liveaktivering körs först när det finns en
faktisk granskad appändring att leverera; dokumentationsreleasen byter inte betan.
