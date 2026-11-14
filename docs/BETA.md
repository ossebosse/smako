# 2026-11-14: Småfixar efter betatest aktiverade

Main `c2de0d344288`. App **app-c2de0d344288-55a9c6d4**, scheduler orörd.
Klarspråk när Smako saknar uppgifter för allergier, Ät inte, portionsvikt och
näring; batterier, tändstickor, våtservetter, bindor, deodorant, rakblad,
disktabletter, djurmat och kattsand räknas som inte mat; rätt singularformer
(1 vara, 1 portion); /personal säger att butikerna ska bekräftas; provgränssnitten
skickar högst två likadana rätter per måltidstyp och lägger till frukost och
mellanmål med små knappar under Middag. Nya ?v= och skalcache v45 så att
installerade kopior hämtar de ändrade filerna. 11 appfiler, importkontroll ok,
bas `09b7740076c1` (image `2432685ec7a8`), ny image `9560994abaee`. Aktiverad
2026-11-14 11:54 UTC, säkerhetskopia `20261114T114313Z`; `/ready` ready för
22350 och 21120. Bygge och aktivering fristående på servern som tidigare i dag.
Se testrapporten i projektet (testrapport-beta-20261114).

# 2026-11-14: Måltidskort med fördelning, portionsvikt och näring i provgränssnitten aktiverat

Main `09b7740076c1`. App **app-09b7740076c1-a3b5499c**, scheduler orörd.
/ui/a och /ui/b har nu måltidskort som /personal: Middag med antal, portioner
och knapparna Fördelning, Portionsvikt och Näringsvärden; frukost och mellanmål
läggs till under Fler måltider och får egna kort. Receptkorten visar näring per
portion. 5 appfiler (statiska), importkontroll av kandidaten ok, bas
`ac78802c4281` (image `dc594821923f`), ny image `2432685ec7a8`. Aktiverad
2026-11-14 07:53 UTC, säkerhetskopia `20261114T074502Z`; `/ready` ready för
22350 och 21120 med nya BUILD_ID. Bygge och aktivering kördes fristående på
servern (kod från `beta_release.py`, startad med `setsid nohup`), eftersom
enhetens skal avbryter bakgrundsprocesser när anropet slutar. Första
byggförsöket väntade på driftlåset under den dagliga insamlingen.

# 2026-11-13: Konto, skafferi och köp i provgränssnitten, Kött och förpackningsvikt aktiverat

Main `ac78802c4281`. App **app-ac78802c4281-02c83b8d**, scheduler orörd.
Provgränssnitten /ui/a och /ui/b har konto, skafferi och köp; frågeguiden har
valet Kött (middagar med kött, övriga måltider som vanligt); typade skafferirader
kraschar inte längre; när en vara saknar avrunnen vikt räknar Smako med
förpackningens vikt och visar notisen "vikten är med spad" (ägarbeslut
2026-11-13, se PLANNING-ARCHITECTURE.md). 22 appfiler, importkontroll av
kandidaten ok, bas `3e490544632a` (image `47d0bee21857`), ny image `dc594821923f`.
Aktiverad 2026-11-13 17:41 UTC, säkerhetskopia `20261113T173006Z`; `/ready`
ready för 22350 och 21120 med nya BUILD_ID, tidigare rader bevarade.
Första aktiveringsförsöket 17:04 UTC avbröts när klientanslutningen föll och
rullades automatiskt tillbaka; andra försöket kördes fristående på servern.
Lärdom: kör `activate` från en anslutning som överlever hela steget (cirka
10 minuter), annars rullas bytet tillbaka.

# 2026-11-12: Egna varor, provgränssnitt och lösvikt i matplanen aktiverat

Main `3e490544632a`. App **app-3e490544632a-749e98be**, scheduler orörd.
Generiska egna varor köps som de varor de namnger, billigaste vinner även med
lösvikt; samma vara i andra kedjor kan läggas till; två provgränssnitt väljs på
/admin. Matplanen tar nu också lösvikt när den är billigare än en exakt
förpackning (ägarbeslut 2026-11-12). Rättat: `/api/plan` kraschade på den nya
frozenset-policyn i urvalscachen. 24 appfiler, importkontroll av kandidaten ok,
retention före/efter complete, båda /ready svarar med nytt BUILD_ID.
Bygge och aktivering kördes losskopplade på servern med samma workerkod som
`beta_release.py` (laptopens skal tillåter högst 180 s per anrop).
Aktiverad 2026-11-12 07:04 UTC.

---

# 2026-11-10: Snabbare menysökning aktiverat

Main `82b9ce411660`. App **app-82b9ce411660-7332b1f6**, scheduler orörd.
Exakt samma menyer, snabbare: Malmö 2 portioner/3 butiker 117 s (avbrott) → 38 s,
2/4 270 → 46 s, Lund 2/3 22 → 15 s. Publikt prov Malmö 2/3: 39,8 s, VERIFIED.
Backup `/srv/smako/backups/20261110T194041Z`.
[Aktiveringsjournal](releases/planner-speed-20261110/ACTIVATED.md).

---

# 2026-11-09: Mina val Frågor aktiverat

Main `78c2649a2bf2`. App **app-78c2649a2bf2-083247bf**, scheduler orörd.
Fjärde mobilvisningen av Mina val (åtta frågor). Daglig rensning av gamla
Docker-images på servern (`smako-image-retention.timer`).
[Aktiveringsjournal](releases/choice-guide-20261109/ACTIVATED.md).
Föregående: 2026-11-08 snabbare sökning vid tre butiker,
[journal](releases/cap3-store-search-20261108/ACTIVATED.md).
Malmö 1 portion/3 butiker 64 s (avbrott) → 40 s; Lund 1/3 fungerar (medlemsbesparingsfixen).
Kvar: Malmö 2 portioner/3 butiker och 4+ butiker hinner inte inom 60 s.

---

# 2026-11-07 kväll: Kedjeövergripande produktgodkännanden aktiverat

Main `e02a2ef7f0db`. App **app-e02a2ef7f0db-1d6fdb43**, scheduler orörd.
Granskade varor med GTIN/artikelnummer gäller i alla butiker i kedjan: Lund 1 741 → 659
blockerade receptvarianter. Kvarvarande fel: Lund 1 portion/3 butiker ger HTTP 500 i
medlemsbesparingen (fanns före). [Aktiveringsjournal](releases/chain-wide-approvals-20261107/ACTIVATED.md).

---

# 2026-11-07: Fler köpbara råvaror och Malmö-ersättningar aktiverat

Main `bdd956c7351d`. App **app-bdd956c7351d-f0f775c9**, scheduler orörd.
Godkännanden knutna till artikelnummer (nötkött, lamm, tempeh m.fl. planerbara
igen), bredare råvaruidentiteter, förpackningsvikt för listade varor och
134 receptversioner med köpbara ersättningar för råvaror som Malmö inte säljer.
Publikt prov i Malmö: meny skapad, sparad och återläst, VERIFIED.
Bevarat: 337 planversioner, 151 privata tillstånd. Backup
`/srv/smako/backups/20261107T140021Z`.
[Aktiveringsjournal](releases/produce-coverage-20261107/ACTIVATED.md).

---

# 2026-11-07: Snabbare planering, "alla valda butiker" och City Gross-namn aktiverat

Main `e63953efb720`. App **app-e63953efb720-6d2ce025**, scheduler orörd.
Butikstak upp till alla valda butiker; exakt snabbare prissättning och
menysökning (identiska korgar i 34/34 prov, Malmö hela kommunen ca 2–3 gånger
snabbare); återanvänd receptkvalificering; 90 s för planer med fler än 30
butiker. City Gross-namnet slår igenom först när schedulern uppdateras.
Publikt prov i Lund: Stora Coop Lund och Willys Lund, 168,37 kr, VERIFIED.
Bevarat: 336 planversioner, 150 privata tillstånd. Backup
`/srv/smako/backups/20261107T081316Z`.
[Aktiveringsjournal](releases/speed-storecap-20261107/ACTIVATED.md).

---

# 2026-11-06: Stora Coop i stället för nätbutiken och butiksadresser aktiverat

Main `191f173f1e19`. App **app-191f173f1e19-e452c67c**, scheduler orörd.
Med alla butiker i kommunen jämförs Stora Coop Lund i stället för Coop Online
Syd, vars baspriser butiken redan har. Plan och inköpslista visar adress, t.ex.
"Willys Lund, Magistratsvägen 22". Publikt prov i Lund: Stora Coop Lund och
Willys Lund, 168,37 kr, VERIFIED. Bevarat: 335 planversioner, 149 privata
tillstånd. Backup `/srv/smako/backups/20261106T074611Z`.
[Aktiveringsjournal](releases/stores-stora-coop-20261106/ACTIVATED.md).

---

# 2026-11-05: Mina val (Din mat, Inköp), Pescetariskt och omväxling aktiverat

Main `431ddb3ac0f2`. App **app-431ddb3ac0f2-28522b51**, scheduler orörd
(source-ops-e6d4ceaca5bc). Hela main sedan 2026-11-01 följde med: textgenomgång,
receptvarianter och adminfiler. Mina val har sex steg; Gillar/Undvik med
allergimarkering; Pescetariskt som kostval; omväxling Lite/Lagom/Mer.
Grocery-ändringar som redan fanns i schedulern lämnades på appbildens version
(`--keep-app-grocery`). Publikt prov: tre pescetariska middagar, en fisk, tre
matkök, VERIFIED, 278,70 kr, återläst. Bevarat: 333 planversioner,
147 privata tillstånd. Backup `/srv/smako/backups/20261105T203020Z`.
[Aktiveringsjournal](releases/mina-val-dinmat-20261105/ACTIVATED.md).

---

# 2026-11-01: Uppvärmda prov och samordnad faktaläsning/GC aktiverat

[PR 59](https://github.com/ossebosse/smako/pull/59), main `b47e07febe6e`.
App **app-b7c8d0506e23-c18e4ba9**, scheduler source-ops-8a53beb80e43.
[Mätning](reviews/warm-facts-gc-20261101/REPORT.md) och
[aktiveringsjournal](releases/warm-facts-gc-20261101/ACTIVATED.md).

Varma prov kräver nu `/ready/preparation`: färdigt bibliotek och båda aktuella
kommunerna, rätt bygge och pris-ID:n. Gemensam uppvärmning är fortsatt på.
Normaljobb efter primning: median 24,226 → 21,694 s; faktaladdning
7,112 → 6,682 s; planerarens städning 4,722 → 2,401 s. Tre fulla GC blir två
plus generation 1. Minnestoppar i praktiken oförändrade; alla 20 menyprov godkända,
med identiska motsvarande korgar och samtliga 150 513 fakta över Lund/Malmö.
Det större fallet kvar på 51,3 s; uppvärmningen tog 85,0 → 92,6 s, ingen starttidsvinst.
Publikt efter uttrycklig uppvärmningsgrind: **28.469 och 25.203 s**,
båda verifierade/sparade, 110,55 kr. PR-/main-CI gröna (4 442 pass, 63 skip).
Full backup `/srv/smako/backups/20261101T064110Z`; tidigare användarrader, miljö, mountar och
prismanifest bevarade. Retention complete. Se rapportens omfattning och begränsningar.

---

# 2026-11-01: Varma menyprov kontrollerade; uppvärmning kvar på

Betan ligger kvar på `app-327fa573eb3f-0541cf49`. Ingen runtimeaktivering.
`SOURCE_FACTS_PREWARM_ENABLED=true` och V2:s begränsade uppvärmning behålls:
varm upprepning 22,358 → 21,648 s; första efter färdig uppvärmning
27,334 → 24,629 s. Tre nya val hade 0,145–1,016 s högre medeltid;
ingen generell tidsvinst påstås. 20/20 audit/sparning/ägd återläsning godkända,
identiska motsvarande recept, varukorgar och faktaversioner.
Det tidigare publika 53,500 s-provet överlappade förberedelsen; vanlig
`/ready` intygar inte att denna är färdig. Dagens publika prov: 32,391 och 28,359 s,
båda verifierade, 110,55 kr. Skäl till på/av, mätgränser och alla observationer:
[uppföljning](reviews/warm-prewarm-20261101/REPORT.md).

---

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
  senaste aktiveringsrapport. Appens BUILD_ID är `app-c2de0d344288-55a9c6d4`;
  schedulern är `source-ops-8a53beb80e43`.
  [Uppvärmda prov och samordnad faktaläsning/GC](releases/warm-facts-gc-20261101/ACTIVATED.md)
  är senaste appaktiveringen. Sex Pythonfiler från kod `b7c8d0506e23`;
  verifierade varma jämförelser och minnesmaxima. Se journalens publika prov.
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
.venv/Scripts/python.exe scripts/beta_release.py prepare --from-commit c2de0d344288 --commit main --workdir .local/beta-release
```

`c2de0d344288` är appen som aktiverades 2026-11-14 11:54 UTC. Appbildens egen
grocery-kopia är äldre än Git; använd `--keep-app-grocery` om intervallet
bara innehåller grocery-Python som redan levererats till schedulern. De äldre
Coop-filerna i runtime (`price_universe_runtime.py`,
`production_price_universe_build.py`, saknad `coop_syd_base.py`) är medvetet
kvar på Git-versionen i basen och ändras inte av ett appflöde. Byt bas efter
nästa aktivering till den commit som då körs.

Arbetskopian ska vara ren; paketet läser enbart committade Git-blobbar.
`prepare` läser aktuell app via SSH, men ändrar inget på servern. Granska
`.local/beta-release/review.json`, Git-diffen och berörda testresultat.
Enbart dokumentationsändringar kräver ingen apprelease; verktyget säger då
att det saknas appändringar. Använd en ny utdatamapp för varje nytt paket.

Om aktiv fil har andra ändringar än Git-basen, om en fil tas bort eller om
beroenden, databasstruktur, grocery-kod eller körbara deploy-filer har ändrats i
intervallet, avbryts detta begränsade appflöde. Leverera då förändringen med
schedulerpatch eller full release nedan; kopiera inte hela main över den aktiva
bilden på chans.
Appbilden har en egen, äldre kopia av grocery-koden; schedulern får sina
grocery-ändringar genom schedulerpatchar. Om intervallet bara innehåller sådana
redan levererade grocery-Pythonfiler kan `prepare --keep-app-grocery` användas.
De paketeras då inte, utan listas i granskningen som kvar på appbildens version.
En ändrad appfil vars importrader mot en sådan modul har ändrats stoppar
fortfarande, liksom grocery-beroenden, data och andra filer än `.py`.
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

För uppvärmt prov krävs HTTP 200 från `/ready/preparation` med färdigt bibliotek,
rätt BUILD_ID och samtliga aktuella pris-ID:n. Väntan ligger utanför menyklockan.
Webbläsarverktyget `scripts/release_verification/complete_recipe_browser.py`
stöder `--warm-build-id <BUILD_ID>` och en `--warm-universe-id <ID>` per aktiv
kommun; båda krävs tillsammans. Hämta förväntade ID:n från den granskade
driftstatusen. Partiell/saknad rapport eller avvikande bygge får inte räknas som varmt.
Den första menyn efter gemensam förberedelse särredovisas från upprepade och nya val.

Spara en sanerad rapport under `docs/releases/<release>/`, uppdatera
`docs/HANDOFF.md` och committa/pusha till `main`. Ange kodcommit, image,
BUILD_ID, tid, tester, databevarande och kvarvarande begränsningar.
Spara aldrig full compose-miljö, cookies, privata profiler eller backupfiler i Git.

## Andra releasetyper

Ny server, databasmigrering och Windowsrelä kräver en egen plan.
Scheduler- och grocery-kodändringar får aktiveras direkt, utan separat
granskningsrelease, när relevanta tester är gröna: paketera med
`build_source_patch.py` enligt nedan, ta backup och byt schedulerbild.
Verifiera första körningen efteråt i driftstatus och journalföra som vanligt.

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
filhashar och kör relevanta offlineprov före aktivering.
En ny installation eller uppdaterad scheduler kör städningen vid start och
via befintliga backup-/refreshjobb; ingen extra timer installeras.

Den versionshanterade apphjälparens paketeringsspärrar och klonstart verifieras
separat vid införandet. En ny liveaktivering körs först när det finns en
faktisk granskad appändring att leverera; dokumentationsreleasen byter inte betan.
