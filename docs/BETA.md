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
  senaste aktiveringsrapport. Appens BUILD_ID är `app-327fa573eb3f-0541cf49`;
  schedulern är `source-ops-8a53beb80e43`.
  [Mindre uppvärmning och färre filkontroller](releases/prewarm-detail-reads-20261031/ACTIVATED.md)
  är senaste appaktiveringen. Två Pythonfiler från kod `327fa573eb3f`;
  fem isolerade menyer snabbare med identiska korgar. Se journalens publika prov.
  [Föregående faktarättning](releases/menu-work-reduction-20261031/ACTIVATED.md)
  och övrig runtime består.
  [Stora Coop-kopplingen](releases/stora-coop-syd-base-20261029/ACTIVATED.md)
  dokumenterar de separata faktiska baserna och den exakta slutpatchen.
  [Senaste Coop-källrättning](releases/coop-remaining-sources-20261029/ACTIVATED.md)
  dokumenterar de skilda faktiska baserna: första app-/källrättningen 2600390d3943
  följdes av tre schedulerfiler 47b1f0fdb717. Appens äldre Coop-baser/collector
  kräver den dokumenterade exakta backporteringen; kopiera inte hela main över runtime.
  Recept-/beräkningskod består. Två adminfiler i första releasen gav normal cacheinvalidering.
  Den tidigare [Coop-fälträttningen](releases/coop-environmental-code-20261029/ACTIVATED.md)
  uppdaterade tio butiker med en fyrfils-patch ovanpå appbas `fac3a7e021a0`
  och schedulerbas `2b65533af00d`.
  Använd faktiskt aktiv fil/image som bas vid nästa exakt granskade release.
  [Samlad aktivering](releases/beta-ica-recipes-20261028/ACTIVATED.md) innehåller
  ICA/tvånattspolicy och hela det integrerade recept-/beräkningsarbetet.
  Windowsuppgiftens registreringsbyte återstår med administratörsrättighet.
  [Senaste dashboardrättning och driftkontroll](releases/dashboard-operations-20261028/ACTIVATED.md)
  visar ICA-baspriser, Willys körjournaler och de då kvarvarande Coop-källfelen.
  Tidigare runtimefunktioner för admin bevarades med granskad exakt patchning;
  config.py är därför inte en ren kopia av main. Historiskt
  [medlemskap](releases/membership-20261021/ACTIVATED.md) och dess tre additiva
  kontotabeller består. Se även
  [basbildens granskning](releases/planner-startup-20261018/ACTIVATED.md)
  innan en ny ändring av config.py paketeras.

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

# Använd den granskade Git-bas som motsvarar faktiskt aktiva filer enligt senaste journalen.
.venv/Scripts/python.exe scripts/beta_release.py prepare --from-commit 2d2181aabfb4 --commit main --workdir .local/beta-release
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

Bygge och aktivering kör först den gemensamma
[lagringsretentionen](storage-maintenance.md) under driftlåset. Blockerad
retention stoppar releasen med ett lokalt kvitto. Slutbilden återställer
basbildens runtimekonfiguration från ett nytt filsystemlager; upprepade
patchreleaser bygger därför inte en allt längre kedja av gamla lager.
Konfiguration och filhashar jämförs med förväntat resultat. Efter lyckat bygge
roteras egna avslutade images och oanvänd byggcache. Aktiva, rollback-,
väntande och okända images skyddas.

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

Releasebackupen använder samma kompletta, roterande backupkatalog som den
dagliga backupen. Inga nya databasdubletter läggs i releaseunderlaget.
Efter aktiveringen körs underhållet igen. Ett fel där rapporteras uttryckligen
som **aktiverad app men blockerad retention**, inte som ett uteblivet appbyte.

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
verifierad plan.

En samlad release måste prova faktisk schedulerbild mot ett helt inaktivt
prisbygge i berörda kommuner. Kommuterande filpatchar bevisar inte kompatibla
produktmodeller: jämför också konsumentens och byggarens fält-/köpkontrakt.
Schedulerns cronfil skapas under uppstart; invänta och verifiera färdiga jobb
innan en saknad fil betraktas som startfel. Se
[incident och korrigering](releases/beta-ica-recipes-20261028/REVIEW.md).

Befintlig paketerare är:

```powershell
.venv/Scripts/python.exe scripts/build_release.py --commit main --output .local/full-release
```

Den skapar källpaket och aktiverar inget. Utgå från aktuell drift och relevanta
delar av `deploy/compose.yaml`, `deploy/compose.release.yaml` och
`deploy/scripts/install_relay_release.ps1`. Historiska driftsättningsguider
beskriver sina dåvarande miljöer; kör inte deras daterade kommandon blint.

En avgränsad schedulerpatch kan paketeras med `scripts/build_source_patch.py`.
Den kräver nu även `--base-config <privat-inspect.json>`: exakt
`docker image inspect` för den pinnade `--base-image`. Filen ska ligga
utanför Git. Slutbilden plattas på samma sätt som appreleasen.
Om den äldre runtimefilen har CRLF men Git har LF kan `--base-files` ange
ett privat `{image, files}`-inventarium med base64-kodade originalfiler.
Endast bevisat identiskt Pythoninnehåll efter radslutsnormalisering tillåts;
byggkontrollen kräver fortfarande originalets exakta bytehash. Andra
runtimeavvikelser avvisas.
Jämför dess `Config` med paketets `IMAGE-CONFIG.json`, verifiera granskade
filhashar och kör relevanta offlineprov före separat kontrollerad aktivering.
En ny installation eller uppdaterad scheduler kör städningen vid start och
via befintliga backup-/refreshjobb; ingen extra timer installeras.

Den versionshanterade apphjälparens paketeringsspärrar och klonstart verifieras
separat vid införandet. En ny liveaktivering körs först när det finns en
faktisk granskad appändring att leverera; dokumentationsreleasen byter inte betan.
