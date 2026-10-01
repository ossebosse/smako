# Driftspärrar: komplettering 2026-09-30

**Nyare förkontroll 2026-10-01:** operatören har registrerat testuppgiften;
den är fortfarande inte startad. [S4U-PREFLIGHT.md](S4U-PREFLIGHT.md)
ersätter nedanstående historiska registreringshinder och anger aktuell
körpolicy/mottagarkontroll. Återregistrera inte uppgiften.

**INTE REDO.** Detta är kompletterande driftprov, inte nya resultat för hela
testsviten. Arbetsgren `release/lund-relay-20260929`, ren utgång
`1d578b2cb53225f9d73cf891c2c0d7445d22bf78`. Senare arbete bevarades.
Produktionskod och de identifierade paketen från `bdc9f7df417084641d0a712e3dad188dad1ad7d4`
är oförändrade. Nya filer är provverktyg och underlag; paketerarens urval
utesluter `scripts/release_verification/` och dokumentation.

## Kort beslutsmatris

| Kontroll | Utfall | Belägg / kvarstående hinder |
| --- | --- | --- |
| Obevakad verklig hämtning och leverans | **BLOCKERAD** | Ingen S4U-testuppgift registrerad/körd. Operatörssteget nedan behövs; terminal/replay är inte S4U-bevis. |
| Samordnat versionsbyte och köhantering | **BLOCKERAD** | Gammal giltig artefakt kan inte kvitteras som publicerad med originalpolicyn: saknat obligatoriskt Primat-underlag. Full kedja gammalt par → nytt par → återgång är inte godkänd. |
| Planläsning efter återgång till faktisk produktionsbild | **BLOCKERAD** | 15/20: HTTP 200 med 64 fältförluster; uppskattat köp: 200 med 12 skillnader; öppet kampanjval: 500. Samma efter faktisk omstart. |
| Omräkning på faktisk produktionsbild | **BLOCKERAD** | 15/20 och uppskattat köp ger 422; kampanjval ger 500. Varken omräkningsstöd eller en genomgående säker vägran är bevisad. |
| Återstart med nya bilden efter misslyckad återgång | **PASS för planläsning** | Alla tre GET 200, identiska planer, sparade requests och källversioner, även efter ytterligare processomstart. Alla 37 tidigare revisionsrader bevarade. |
| Fem tidigare releasekritiska testfel | **PASS i tidigare releasebevis** | Samma fem exakta ID:n/orsaker som i RESULTS: 5 fail +35 pass →40 pass. Inte omkörda eller omräknade här. |

Maskinläsbart, begränsat underlag: [OPS-EVIDENCE.json](OPS-EVIDENCE.json).
Råa testplaner, cookies, testnycklar, uppgifts-XML och loggar hålls privat.
Inga produktionsbeslut följer av denna matris.

## Windows: registrering och körning är olika fel

Aktiv uppgift är fortfarande `\Smako Willys Local Relay`, Ready,
`ossia` / **S4U / Limited**, dagligen 01:30. Senast körd 2026-09-30
01:30:01 svensk tid, resultat **1**. Den har inte startats, ändrats eller
registrerats om av detta arbete. Exportens SHA-256 (UTF-8 från PS7):
`c781d10ce504aa172d8006f365f7ad167ac2ca23688fcf629d1b0851c5ff6755`.

Anropande identitet är `LAPTOP-I109S875\ossia`, medium integrity; gruppen
Administrators och gruppen för lokala administratörskonton är deny-only.
Processen är inte upphöjd. Task Scheduler-mappen är `\`, med SYSTEM/
Administrators full kontroll och Authenticated Users FW i mappens DACL.
Befintlig uppgift har dessutom uttryckliga användarposter. Dessa är olika
objekträttigheter; åtkomst till den befintliga uppgiften bevisar inte rätt att
registrera S4U-uppgifter. Privata exakta DACL:er sparas i
`.local/drift-verification/s4u/scheduler-permissions.json`.
TaskScheduler/Operational är avstängd; ingen logg eller säkerhetspolicy ändrades.

Det tidigare registreringsförsökets fullständiga anrop, ErrorRecord och
HRESULT finns **inte bevarade** i tillgängliga underlag. Belägget är
`Åtkomst nekad`, inte en uppmätt full felkod. Ingen kod som 0x80070005 får
presenteras som återfunnen mätning. Den kvarvarande gamla testharnessen
pekade på `3916e888d8da` och `-CheckInstall`; den saknar körningslogg/session
och skulle inte ha bevisat aktuell liveinsamling. Inget nytt
registreringsförsök har gjorts utan avsett godkännande/behörighet.

Den aktiva uppgiftens senaste körning nådde däremot verklig insamling och
upload. Logg `20260929T233009Z-38d2276382404742b0eecc501a1d0e7a.jsonl`
visar 1251 anrop, 18 939 rader, upload och serverimport, följt av exit 1.
Artefakt `3e9c966015a948a0b021c13058fa660d`, SHA-256
`05ab5b72790d7e270072945fd5090ca205dac0c4a174463233885ad10700c4b3`.
Serverrapport `refresh-report-20260930T001339.277354Z-8eb608ca.json`
bekräftar `required_external_cache_unavailable`, Primat
`active_cache_unavailable`, 0 provideranrop och `fatal`. LKG låg kvar från
23 september och var stale. Detta är ett publicerings-/baspolicyfel efter
leverans, inte bevis på att Windows vägrade starta eller SSH saknade nät.

Senast belagda lyckade leverans: **2026-09-23 02:17:02 +02**, artefakt
`8e0c317865404417a5d3620964ffdc7a`, snapshot
`b418ece7825643a6af69bb75e03284cd`, `normal_managed_refresh` och
`task_success` i motsvarande logg. Loggarna anger
`scheduled_or_manual_not_inferred`; Windows händelselogg saknas. Senast
lyckade **obevakade** leverans kan därför inte fastställas säkert.

## Minsta operatörssteg: endast testregistrering

Granska [prepare_s4u_probe.ps1](../../../scripts/release_verification/prepare_s4u_probe.ps1)
och [run_s4u_probe.ps1](../../../scripts/release_verification/run_s4u_probe.ps1).
Förberedelseläget har körts i vanlig PS7 och verifierats. Det skapar bara
lokala testfiler; ingen uppgift registreras eller startas.

Efter uttryckligt godkännande för **just testregistreringen**, öppna
**PowerShell 7 som administratör, under samma ossia-konto**, och kör:

```powershell
& 'D:\Projects\Smako\scripts\release_verification\prepare_s4u_probe.ps1' -Register
```

Skriptet registrerar endast `\Smako Lund bdc9 S4U isolated verification`,
utan schematrigger, utan automatisk start och utan `-Force`. Körkonto hämtas
från den aktiva uppgiften; LogonType förblir **S4U**, RunLevel **Limited**.
Upphöjningen gäller registreringen, inte reläprocessen. Befintliga uppgifter
skrivs aldrig över. Ingen egen elevation eller ändring av rättighetspolicy
görs. Full ErrorRecord, exceptionkedja/HRESULT, caller, mapp och DACL sparas
lokalt vid fel. Om även detta nekas: stanna, lämna felunderlaget; ändra inte
S4U, konto eller policy som automatisk åtgärd.

Testuppgiften anropar en hashad observatörskopia under
`D:\Projects\Smako\.local\drift-verification\s4u`, som startar exakt
`D:\smako-local-relay\releases\bdc9f7df4170\deploy\scripts\start_packaged_relay.ps1`
i en separat PS7-process. Paketets arbetskatalog är versionsbunden.
Konfiguration `s4u/relay.json`, tillstånd `s4u/state`, köer och kvitton är
egna. Kommunbindningen är uttrycklig 1281 för **nya** hämtningar; inga gamla
artefakter har ändrats eller fått påhittad bindning.

Isolerad mottagare `smako-lund-ops-s4u` använder den verifierade nya bilden,
endast `/var/tmp/smako-repo-release-20260929/ops-verification/s4u-data:/work`,
egen testnyckel och inbox `/work/raw/source-inbox/willys`. Inga
produktionsvolymer, publicerade portar, automatiska omstarter eller scheman.
Nätläge `none` hindrar mottagarens externa prisanrop; SSH-transport sker från
Windows till värden och därefter `docker exec` i just testcontainern.
Faktisk serving kontrollerades till 44 132-manifestet, inte bara HTTP 200.
De 2232 aktiva råfilerna och artefakthashen kontrollerades utan fel.

Registrering är inte tillstånd att omedelbart köra en föråldrad testmiljö.
Innan teststart: starta om den isolerade mottagaren vid behov, kontrollera dess
bild-ID, bind mounts, faktiska serving, äldsta basobservationer och nuvarande
36/48-gränser. Låt ordinarie behovsstyrning uppdatera förfallna underlag.
Spara sedan ett tidsbegränsat `s4u/receiver-ready.json` med `image` och
`expires_utc` från kontrollen. Ingen sådan startspärrfil fabriceras här.
När testkörningen är godkänd kan operatören köra:

```powershell
Start-ScheduledTask -TaskPath '\' -TaskName 'Smako Lund bdc9 S4U isolated verification'
```

Observatören sparar faktiskt konto/SID, principal, session-ID, Interactive,
exitkod och processlogg. `s4u/state` är avsiktligt utan framgångskvitto och
återspelningsartefakt så att första godkända provet måste göra verklig
källhämtning. Verifiera liveanrop, ursprunglig observation/hash, SSH-upload,
mottagarvalidering, operationslås, import, publicering, faktisk reload och
beständigt kvitto. Därefter återleverans och `not_due` utan nya prisanrop.
Willys-transporten använder HTTP-klienten; ingen browserprofil behövs för
denna källa. Offline-browserstart från releaseprovet bevisar inte S4U.

SSH använder systemets OpenSSH, befintlig lokal aliasdefinition och
`~/.ssh/smako_ed25519` (inte EFS-markerad). Inga nycklar kopieras till Git.
Nyckel-/konfigurationsåtkomst och faktisk autentisering i S4U är fortfarande
oprövade. Microsoft beskriver S4U:s begränsning för nätverksautentisering och
krypterade filer i [säkerhetskontexter för uppgifter](https://learn.microsoft.com/en-us/windows/win32/taskschd/security-contexts-for-running-tasks).
Det avgör inte ensamt hur vår HTTP- och privata SSH-nyckeltransport fungerar.
Vid fel ska det faktiska steget/loggen styra ett separat förslag; inget tyst
byte till SYSTEM, Highest eller InteractiveToken.

## Versions- och återgångsprov

Produktionsbilden kontrollerades på nytt till
`sha256:54dde8382599ac30beee8bffd05d8cefff232e1ea5c81f1fd7f302db0d591c1f`,
`price-recovery-lund-20260914a`. Produktionsdata lästes via **read-only**
mount; SQLite-backup och oförändrade DB/WAL-/manifesthashar före/efter
kopieringen gav konsistent provkopia och två `quick_check=ok`.
Ett första read-only SQLite-backupförsök fastnade på journalåtkomst och
stoppades; endast den separat skapade, verifierade `old-pair-data-v2`
användes. Det ofullständiga målet bevarades. Inga aktiva lås eller scheman
ändrades för kopieringen.

Gammal giltig, verklig artefakt återspelades via den exakta äldre bildens
ordinarie `grocery_data.source_cli import`. Originalpolicyn behölls.
Import/rebuild slutade exit 1, ingen reload: obligatorisk extern cache
saknas. Snapshotantalet var **174 före och efter**, snapshotinventeringens
hash och aktivt manifest oförändrade. Köartefakten var byteidentisk och
gamla kvittot bevarades. Detta stoppar förslaget att först tömma gamla kön
med lyckad publicering; ingen falsk kvittens eller policyförsvagning infördes.
Gamla och nya artefakter/kvitton hålls separata med originalhashar.
Full koordinerad övergång är därmed **inte genomförd**. Se den entydiga,
villkorade ordningen i [ACTIVATION.md](ACTIVATION.md).

Det nya parets **separata replaydel** kördes också på nytt: exakt installerat
Windows-pakets startskript, egen `replay-state`, riktig SSH-autentisering,
ordinarie inbox/import och kvitto `already_active` för den bevarade
`76eabee0…`-artefakten. Samma 147 snapshots med identisk inventeringshash
före/efter, samma manifest och faktiskt serving 44 132. Ingen nyinsamling,
ingen dubbelimport, inga ändrade observationer. En ny Windows-process gav
`not_due` med explicit `external_price_requests=0`, kvittot kvar.
Detta är interaktiv paket-replay, inte S4U eller en ny atomisk publicering.
[WINDOWS-EVIDENCE.json](WINDOWS-EVIDENCE.json) skiljer delprovet från den
blockerade samordnade övergången. Testmottagaren lämnades stoppad med
beständigt tillstånd; inga scheman installerades. Återstart inför godkänt
test sker med `ssh smako docker start smako-lund-ops-s4u`, följt av nya
bild-/volym-/serving-/färskhetskontroller innan startspärrfil skapas.

HTTP-proven kördes med `--network none`, utan ändrad klocka. De gamla fyra
profilproven hör fortsatt till **42 491** / `1e1b3695…`. Ett nytt försök på
detta underlag stoppade ett nu för gammalt fysiskt Hemköp-köp med 422.
Återgångens tre nytillkomna planer skapades i stället på **44 132** /
`price-universe:624e4de9d762221ad0754f2c21051ae9003cde3f2a5b866a623966821952a6fa`.
Manifest-SHA `29c195a4ef8c7faab8971cb758d8b25a1aee14f18838b607cd637c0109ebe973`,
artefakt-SHA `6cebdbb47c8cb61312091ca42e16681e9dcd8d08b602e08410bb99ed6ad30d6b`.
Ny källa innebär ny produktnyckel: gammal pizzanyckel avvisades, därefter
valdes den aktuella belagda raden via samma butik/kampanj och verifierades i
ordinarie produktsökning. Recept eller källtid ändrades inte. Nuvarande
pizzaobservation var 2026-09-30 11:18:13Z, öppet 2-för-79-val, fortsatt
villkorat/UNVERIFIED och inte godkänd receptingrediens.

Äldre bild med det **nya** manifestet startar inte:
`ActivePreparedUniverseManifest.oldest_base_observed_at: extra_forbidden`.
Ingen validering ändrades. Separat diagnostik med `PRICE_UNIVERSE_REQUIRED=false`
skiljdes från det huvudsakliga återgångsprovet med äldre, äkta
produktionsmanifest i en separat read-only prisrot, originalpolicy och
`PRICE_UNIVERSE_REQUIRED=true`. Den senaste plandatabasen behölls hela tiden.
Det huvudsakliga provet gav samma 64/12 fältförluster och 500 före/efter
omstart. Förlorade fält omfattar receptberedning, köptermer, kampanjens
källreferenser, prisbasis, merchandise/deposit och ändrat `regular_unit_price`.
Planens toppnivå-ID för källversion räcker alltså inte som kompatibilitetsbevis.
500 orsakas av `PlanRequest.personal.extras.0.kind`: äldre kod godtar bara
`generic`/`exact`, inte `campaign`.

Originalmanifestet `96ca8bfb…` laddades faktiskt men gav `/ready` **503**,
0 användbara kontexter och cirka 231 timmar gamla priser. Återställning av
originalbild/originalpolicy kan inte kallas full drift eller fungerande
nyplanering när Primat-baser saknas. Omräkning provades separat: två 422 och
kampanjplan 500. Den nya bilden läste därefter alla tre sparade planerna
identiskt, inklusive mängder, pris-/näringsstatus, recept och källreferenser;
ytterligare omstart gav samma resultat. Ingen äldre plandatabas återställdes.
Ingen kompatibilitetsfix i produktionskod har gjorts; säker återgång är en
kvarstående konkret blockerare.

## Tidigare releasebevis och nästa gräns

Oförändrade tidigare utfall: Windows ren klon **3455 pass, 0 fail, 0 skip**
uppdelat 1806/1649; **16 autentiska Lidl-pass**; frontend **30 pass**,
check/build PASS; Chromium/WebKit **4 slutliga formulärflöden PASS** med
separata verkliga HTTP-planprov. Dockerbilden kontrollerades på slutcommiten;
hela Linux-sviten på bdc9 kördes inte om (föregående commit 3445 pass,
1 plattformsskip). Tidigare avbrutna/disk-/timingkörningar behåller sina
begränsningar i RESULTS. Dessa siffror är återanvända releasebevis, inte nya
körningar. Här kördes kompletterande verkliga Docker-/HTTP-/köprov och
statiska kontroller av de nya provverktygen: Ruff check/format för åtta
Pythonfiler, compileall och syntaxkontroll av båda PowerShell-skripten PASS.
Förberedelseskriptet kördes utan registrering; produktionsförslagets XML
jämfördes strukturellt och skiljer endast Arguments/WorkingDirectory.
S4U-observatörens verkliga körning är fortfarande EJ PRÖVAD.

Senast verifierad äldsta verkliga basobservation är **2026-09-29 11:53:03Z**,
cirka 28,4 timmar vid dessa prov. Detta är en tidsstämplad observation, inte
ett framtida aktiveringsintyg. Aktuell kandidat och alla äldsta basobservationer
måste omprövas vid faktisk aktivering med oförändrade 36/48-gränser.

Testregistreringen utfördes senare av operatören; se
[aktuella förkontroller och startgräns](S4U-PREFLIGHT.md).
Fortfarande återstår S4U-livekedjan, köövergångens blockerare och verifierad
läskompatibel återgång. Femkällorspolicy, serveraktivering och byte av aktiv
Windows-uppgift är fortfarande **tre separata, ej fattade beslut**.
