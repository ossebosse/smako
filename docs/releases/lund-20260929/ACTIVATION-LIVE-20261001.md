# Lund 1281: produktionsaktivering 1–2 oktober 2026

**AKTIVERAT: normal produktionsdrift, båda schemana återupptagna.** Detta protokoll avser faktisk
produktion. Äldre förkontroll- och behörighetsstopp är historik. Inga nya
applikationsändringar eller paketbyggen ingår i aktiveringen.
Maskinläsbara hashvärden, tider och utfall finns i
[ACTIVATION-LIVE-EVIDENCE.json](ACTIVATION-LIVE-EVIDENCE.json).

## Godkänd och installerad omfattning

Fem separata godkännanden är givna: femkällorspolicyn, servern med begränsad
läsåtergång, bdc9-reläbytet, Windows 01:30/09:30/17:30 och serverns behovskontroll
var 15:e minut. Backup behåller 02:47. Alla tider är Europe/Stockholm.
35-timmars behovsgräns, 36-timmarsvarning och 48-timmarsstopp är oförändrade.
Ingen Malmö-aktivering, säkerhetspolicyändring, städning eller remote-push.

| Identitet | Verifierat värde |
| --- | --- |
| Serverruntime | `08c137475d9ca96a6ef7673245a639c8c5c9e922` |
| Server-/återgångsbild | `sha256:d8a166fa7ee162cd0570f9d8089ff800e00d9c949ac3c674e387c5fff1538dd7` |
| Server-ZIP SHA-256 | `c20f8ad6ce316df121117c32cb44dc308a8d73011d097ec8799be095883b1e22` |
| Aktivt valt Windows-paket | `D:\smako-local-relay\releases\bdc9f7df4170` |
| Relä-ZIP SHA-256 | `299ff34ecb7b5976e317afeef54719c9286d0ecd64c2807cee58533945de57d7` |
| Policy | `lund-own-five-base-20260928-v1`, SHA-256 `a2053bd41157fe818c9c9d437cba540d423b249a8232e2baebb49e94f1e954a1` |

Arbetsgren `release/lund-relay-20260929`, ren start på dokumentationscommit
`5a002f0e6346e8afb85afadef82cf1d5e9fefcf5`. Senare verifierings-/driftdokumentation
ändrar inte runtimeidentiteten. Reläets 624 filer och installerade serverfiler
hashkontrollerades. Nyare Windows-ZIP används inte.

## Faktiskt byte, bevarande och källkedja

Operatörens uppdatering återlästes: samma befintliga uppgift, Disabled,
ossia/S4U/Limited, pinnad PowerShell, oförändrade skyddade XML-fält. Endast
godkända Arguments/WorkingDirectory, tre klockslag och tillfällig paus ändrades.
Effektiv PS7-policy är RemoteSigned; inga policyöverstyrningar gjordes.
Arbetsyta `D:\smako-local-relay\scopes\municipality-1281`, konfiguration
`D:\smako-local-relay\config\relay.json`. Kommuninboxen är
`/srv/app/var/raw_snapshots/source-inbox/municipality-1281`, transport till
`smako-scheduler-1`. Appens pris-/råvolymer är fortsatt read-only.

Gamla appen/schedulern stoppades **21:06:32 UTC / 23:06:32 CEST**. Skrivare
och lås väntades ut. Serverbackup avslutades 21:09:32 UTC. Nya appen och samma
bilds receiver startades under paus; receiver körde `sleep infinity` tills
acceptans. Ingen gammal och ny importerare skrev samtidigt. Originalpolicy,
gammal inbox/arbetsyta och senaste produktionsplaner bevarades.

Skyddad serverbackup: `/srv/smako/backups/lund-activation-20261001T2110Z`.
SQLite-backupernas quick_check passerade. `data.tar` innehåller båda databaser,
prisrot, manifest, råfiler och driftstatus med ACL/xattr. Hashar finns i JSON-beviset.
Windows-backup `.local/activation-live-20261001/windows-state.zip` verifierade
20 064 filhashar; ursprungliga NTFS-SDDL sparades privat för rättighetsåterställning.
Ett försök till ACL-bevarande med robocopy nekades och räknas inte som lyckad
backup; originalen ändrades inte. ZIP och sparade ACL är den verifierade kopian.

Slutpaketets `grocery_data.relay_transition` bevarade gamla kön under lås.
Servern: 16 mottagna men inte publicerade artefakter och en oläsbar ej
publicerad fil. Windows: 15 väntande artefakter, en kvitterad och befintligt
kvitto. Inga falska framgångskvitton eller kommunbindningar skapades; inga
gamla filer raderades. Gamla Primat-publiceringen behövde inte lyckas.

Tre giltiga autentiska Coop/Hemköp-kataloger återspelades med oförändrade
råhashar/tider, nät avstängt och ordinarie parser/validering/promovering:
11 428 / 6 232 / 5 092 parsade rader, noll karantän. Endast råmetadata och
källfiler återställdes; inga testplaner, identiteter eller produkt-/pristabeller
kopierades. Kvalificerade kommununderlag begränsades till 1281.

Kontrollerad bdc9-körning **21:18:19–21:30:12 UTC** återanvände liveartefakten
`049d1ce3a2e546f3922cbadd89e3d73f`, SHA-256
`5b1a2b6b01ba65338f224cdd6af432c8178f214b1612d5d54ec400ffe8f9362a`.
Ingen ny Willys-hämtning: ursprunglig observation är 07:44:37 UTC samma dag.
Validering → SSH → rätt inbox → import `304d09f31d704d7fac7f76ab5360fc41`
→ OWN → atomisk publicering → autentiserad faktisk reload → beständigt kvitto
passerade. Exakt en import, 1 250 råpayloads med samma tider/hashar/butik och
18 760 serverade Willys-rader från importen. Hela replayflödet tog 712 sekunder;
detta är inte ett nytt obevakat insamlingsprov. Det tidigare S4U-livebeviset består.

Återleverans gav `already_active`, fortfarande en import och byteidentiskt
lokalt kvitto. Ordinarie bdc9-start 21:37:48 UTC gav `not_due`, noll externa
prisanrop och oförändrad observation/kvittotid.

## Faktisk HTTP-acceptans

Profilmanifest: `price-universe:57ca714ed72b687bf1f2af9de7d48d233aac9b51bfd2500021bb4176b7a19a0d`,
**44 077** råproduktposter, 2 248 efter prisprojektion. Manifestfilens SHA-256
`adcbeaf79dc111f438fd62cc3458f6ca2ee4bbedc9177d1e10ed33a2d08872b0`.
Alla 2 232 refererade råfiler hashverifierades före planeringen. Detta är ett
annat manifest än historiska 42 491, 44 132 och S4U-provets 44 066 poster.

Separat ny verifieringsidentitet användes genom ordinarie HTTPS. Samtliga fyra
profiler behöll 15 måltider/20 portioner, 40/30/20 g protein, två butiker,
övriga val och runtime/receptlogik. Original och Willys Plus/Lidl Plus-kopia,
vardera exact/estimated: **440,72 kr**, två butiker, köp `VERIFIED`, checkout
PASS, mängder och totalsummor avstämda. Proteingolv faktiskt 40,8 / 35,5 / 22 g.
Näring är separat VERIFIED/ESTIMATED enligt källunderlag; allergenkrav var inte
begärda. Kalla profilanrop tog 167–195 sekunder, inte en snabbhetsgaranti.

| Aktuellt källbelagt köp | Faktiskt resultat |
| --- | --- |
| Cirka-vikt laxsida | Ett cirka 1 200 g paket, 166,80 kr; uppskattat köp. Exact vägras 422. |
| Lösvikt | 350 g, 31,15 kr; uppskattat köp. |
| Helt flerköp | Tre paket, 1 170 g, 25,00 kr; exakt mängd/köp. |
| Öppet pizzakampanjval | Två st, 79,00 kr; villkorat och `UNVERIFIED`, inget närings-/allergengodkännande. Exact ingrediens vägras 422. |

Två inledande provnycklar var felaktiga (kontextnyckel i stället för GTIN och
en historisk nyckel). Dessa 422-svar bevaras privat som provverktygsfel.
Slutprovet använder runtimebildens verkliga produktindex och nuvarande källrad;
app, validering och källunderlag ändrades inte för att få PASS.

Uttrycklig `POST .../change` med `action=recalculate` passerade separat:
samma plan-ID, revision 1→2, tidigare revision oförändrad, ny GET identisk,
checkout och proteinmål godkända. Detta är fungerande normal omräkning,
inte läsåtergång. De 170 ursprungliga produktionsrevisionerna är byteidentiska;
nio verifieringsrevisioner har tillkommit, totalt 179 vid kontrollen.

Nästa ordinarie behovskontroll behövde en lokal publiceringsavstämning:
21:50:12–22:00:38 UTC, exit 0, samma universum/prisinnehåll och oförändrade
observationer. Efterföljande verklig kontroll gav `not_due`, noll prisanrop och
byteidentiskt manifest samt oförändrade antal snapshots/råfiler/insamlingar.
Ny manifestfilhash efter atomisk ompublicering är
`7cf22ceb453492583f4cd5c1d5f4c432f9fe5ceee8ac6552dda4a5efc6f579d4`;
ändrad aktiveringstid är inte ändrad observationstid.

Faktisk appomstart 22:02 UTC: nio sparade revisioner lästes identiskt och annan
identitet fick 403. Råhashkontrollen upprepades: 2 232 godkända, noll fel.
Releasepekaren `/opt/smako/current` och `/opt/smako/compose` pekar nu på
slutpaketet och dess skyddade `activation-private.env`. Samma bild renderas
för app, migrate, scheduler, refresh-once och backup-once. Befintlig proxy
återskapades inte; dess tomma ACME-inställning behölls. Ett oanvänt
interpolationsvärde finns endast för den profilspärrade proxydefinitionen.
Paketets egna importsökvägar används, inga gamla kodkataloger.

Windows återupptogs **22:03:27 UTC / 00:03:27 CEST den 2 oktober**, med enbart
`Enabled=true`; återläst XML och ACL är oförändrade i övrigt. Uppgiften är Ready,
nästa körning **2 oktober 01:30**. Ingen ny registrering/förhöjning behövdes.
Serverns scheduler startades **22:03:52 UTC / 00:03:52 CEST**; faktisk process
`cron -f`, återläst cron `*/15 * * * *` och backup `47 02 * * *`. Gamla 03:17-
och 06:17-jobben finns inte i den aktiva crontabellen. Första omedelbara
crontab-läsningen föregick initieringen; efter initieringen verifierades filen
och processen. Ingen framtida schemakörning räknas som ett genomfört prov.

## Nästa kontroller och färskhetsmarginaler

Vid återupptagningen är nästa serverkontroll **2 oktober 00:15 CEST** och nästa
Windowskontroll **01:30**. Tabellen är prognos enligt aktuell behovsplan, med
oförändrade verkliga observationer. Kampanjsamordning efter minst 24 timmar
kan tidigarelägga serverhämtning. Hemköp hämtas som gemensam kedjekörning.

| Obligatorisk källa | Äldsta observation 1 okt, CEST | Beräknad hämtning, CEST | Källans hårda stopp, CEST |
| --- | --- | --- | --- |
| Coop Online Syd | 08:09:21 | 2 okt 19:15 | 3 okt 08:09:21 |
| Hemköp Brunnshög | 08:55:05 | 2 okt 19:45, tillsammans med Karhögstorg | 3 okt 08:55:05 |
| Hemköp Karhögstorg | 08:39:40 | 2 okt 19:45 | 3 okt 08:39:40 |
| Willys Lund | 09:44:43 | 3 okt 01:30 | 3 okt 09:44:43 |
| Willys Lund Nova | 10:03:35 | 3 okt 01:30, gemensam artefakt | 3 okt 10:03:35 |

Reläets gemensamma timer använder den tidigare verkliga artefaktobservationen
09:44:37: due 2 oktober 20:44:37, konservativt 48h-stopp 3 oktober 09:44:37.
Med tre timmars budget till **importerad/publicerad/laddad serving** från 01:30
återstår 5h14m37s marginal. Tidigare verklig S4U-helkedja var 49m9s; dagens
replay var 11m52s. Ingen av tiderna garanterar nästa livehämtning.
Serverbaserna har cirka 10h54m eller mer efter beräknad start plus två timmars
genomförandebudget. Budgeten omfattar hela kedjan, inte enbart processtart.

Manifestets konservativa äldsta basvärde är fortsatt **30 september 11:17:53Z**,
från frivilliga fysiska Hemköp-rader; det får inte ersättas med femtabellens
nyare observationer. Varning 2 oktober **01:17:53 CEST**, hård manifestgräns
**13:17:53 CEST**. Dessa och andra frivilliga källor är nästa förfallna arbete
omkring **00:30** enligt ordinarie behovsplan. Kontroll och publicering ryms
före gränsen med normal tvåtimmarsbudget, men framtida nätutfall är inte verifierat.

Tre Windowsstarter ger högst åtta timmars väntan: 35+8+3=46 timmar.
Vid höstens klockomställning 25 oktober är största glappet nio timmar och
budgeten 47 timmar; vid vårens omställning är största glappet fortsatt åtta.
Klockslagen är lokala utan låst UTC-offset. Försenad start/kvarvarande lås
förbrukar marginalen. En missad start kan ge 54–55 timmar och hårt stopp.
IgnoreNew, WakeToRun och StartWhenAvailable garanterar inte färskhet när
relädatorn eller nätet saknas. Operationslåset ska aldrig brytas som genväg.

## Omfattning, återgång och uppföljning

Fem onlinebaser är obligatoriska. Fysiska erbjudanden är partiella tillskott:
10 Coop/X:-tra-kontexter, tre Hemköp, två Lidl, en Willys-bladkontext och tolv
ICA-butiker i källunderlaget. Full fysisk täckning påstås inte. ICA redovisar
1 042 källrader, 1 000 parsade och 42 avvisade; X:-tra 11 kvalificerade och 39
karantänrader. En olöst Willys-registerrad kvarstår. City Gross är
`not_applicable` i Lund och är ingen obligatorisk källa.

Återgångsmålet förblir **samma pinnade bild**, `app.recovery:app`, med senaste
checkpointade plandatakatalogen read-only och befintlig autentisering.
503/exit 3 för skrivning/import/omräkning; 403 för fel ägare. Ingen gammal
plandatabas eller kö får återställas över nytillkommet tillstånd. Gamla bilden
är en backup, inte återgångsmål för nya planer. Tidigare isolerat återgångsprov
gäller; läsåtergång har inte aktiverats under detta lyckade leveransprov.

Tidigare releasebevis återanvänds, inte räknas om: fem ursprungliga testfel
rättade och PASS; 3 455 i uppdelad ren Windows-svit; 16 autentiska Lidl-prov;
30 frontendtester/check/build; fyra browserprov; 168 övergångsfokustester.
Se RESULTS och TRANSITION för exakt nämnare, Linux-/disk-/tidsbegränsningar.
Aktiveringens nya prov avser paket, Docker/Compose, verklig HTTP, replay,
idempotens, behovsstyrning och omstart. Ingen ny fullsvit/browserkörning påstås.

Separat nästa etapp: kampanjfönster natten söndag–måndag och onsdag–torsdag,
kompletterade av verkliga kampanjdatum, samt uppmätta basprisförändringar mellan
autentiska hämtningar inför framtida intervallbeslut. Inte implementerat här.
