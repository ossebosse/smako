# Kategorimedveten receptsökning aktiverad 2026-10-21

Status: slutförd. Appen är aktiverad; liveprov, efterretention och
slutlig driftkontroll är godkända. Båda reläleveranserna är kvitterade.

Aktiverad **00:27:05 UTC / 02:27:05 svensk tid**, efter användarens
uttryckliga godkännande. Kod `73306acc382d153936a2329d9bc819014a575dcc`
är integrerad på main via [PR #6](https://github.com/ossebosse/smako/pull/6).

- BUILD_ID: `app-73306acc382d-0d139487`.
- Image: `sha256:0ad2b6021e6a71b5a849edb42430d0a94c33ea152e58984353de8124182a0830`.
- Föregående image: `sha256:574025c92df8ffc6dec47d0200c20750eb863fe6b69e214710bd56abdfffb79d`.
- Verifierad backup: `20261020T233117Z` i ordinarie backupkatalog.
- Serverkvitto: `/opt/smako/evidence/app-73306acc382d-0d139487/activation-success.json`.

## Ändring och verifiering före aktivering

Omöjliga receptkategorier gallras före produktmatchning. Befintlig arbetsbudget
fördelas över möjliga kategorier med skydd för pris, matkök, förpackningar och
olika grundrätter. Receptbyte räknar in de fasta grannrätterna. Hela den
kvalificerade poolen finns kvar för reservsökning; bibliotek och slutkontroller
är oförändrade. Endast tre granskade appfiler ändrades, 696 runtimefiler är
hashidentiska med basbilden. Bildens konfiguration och filhashar är verifierade.

Full CI: 2 854 PASS, 10 kända XFAIL, 53 SKIP.
[Kodens CI](https://github.com/ossebosse/smako/actions/runs/39493853316) och
[main-integrationen](https://github.com/ossebosse/smako/actions/runs/39497003297)
är godkända. 26 riktade tester, Ruff och compileall är godkända.
Exakt kandidatbild klarar appimport, admininställning, bibliotekets 222
registrerade recept, kategoriurval och återstående kapacitet vid byte.

Alla 24 frysta jämförelsekörningar och två fullpoolskontroller passerade.
För 1 kyckling, 2 vegetariska och 2 övrigt kött sjönk kall tid i Lund
74,40 → 35,63 s och Malmö 102,05 → 47,54 s, med samma pris och antal matkök.
Helt vegetariskt i Lund blev något långsammare. Detta är inte en generell
latensgaranti eller ett bevis på globalt lägsta pris.
[Full metod, resultat och begränsningar](../../reviews/category-aware-recipe-search-implementation-20261020.md).

## Databevarande och drift

Ordinarie källjobb fick avslutas innan det gemensamma driftlåset togs.
Inga källjobb, scheman eller Windowsuppgifter avbröts eller ändrades.
Backupens SQLite-integritet, främmande nycklar och filmanifest verifierades
innan appbytet. Jämförelsen efter bytet bevarar samtliga tidigare
**304 planrevisioner och 115 privata tillståndsrader**, inklusive radhashar.

Endast appcontainern ersattes. Scheduler, proxy, mountar och aktiva
prismanifest bevarades. Enda miljöändringen är BUILD_ID. Både Lund och Malmö
har ready 200 med rätt BUILD_ID och användbara obligatoriska kontexter.
Äldre kvalificerade grundpriser behåller sina observationstider; åldersvarningar
är inte borttagna för att få en grön status.

Willys-incidentens saknade kvittens återställdes 2026-10-20 20:11:30 UTC
genom återleverans av exakt redan aktiv Lundartefakt, `already_active`.
Inga nya priser samlades in i den åtgärden. Det tidigare schemalagda
försökets felkod lämnas som historik. Vanlig konkurrens om driftlåset kan
fortfarande skjuta upp en enskild leverans.

## Efterkontroller

Fyra publika menyprov med nya syntetiska gäster passerade (`202 → 201`).
Varje meny har fem olika grundrätter, högst två tillåtna butiker, godkänd
korgkontroll, inga okända mängder/underskott och identisk sparad återläsning.

| Kommun | Val | Meny, s | Inköpssumma, kr | Byte, s |
| --- | --- | ---: | ---: | ---: |
| Lund | Standard | 72,76 | 550,13 | – |
| Lund | 1 kyckling, 2 veg, 2 övrigt kött | 45,28 | 709,38 | 18,16 |
| Malmö | Standard | 62,08 | 553,65 | – |
| Malmö | 1 kyckling, 2 veg, 2 övrigt kött | 44,17 | 702,32 | 21,48 |

Båda bytena gav en annan grundrätt i samma kategori. De fyra fasta rätterna,
exakta kvoterna och den föregående planrevisionen bevarades; den nya revisionen
gick också att återläsa. Detta är funktionella HTTP-prov med aktuella priser
och pollning, inte en ny kontrollerad jämförelse mot den gamla versionen.

Driftkontroll 00:36–00:39 UTC: båda kommunerna ready 200, alla 14
obligatoriska kontexter kvalificerade, publicerade och laddade.
Nattens ordinarie Malmöpaket fick `RefreshAlreadyRunningError`
00:24 UTC under backupen. Det kvalificerade paketet återlevererades först
efter godkänd efterretention, med ny lokal basinsamling spärrad.

Efterretentionen avslutades 01:06:23 UTC med `complete`; releasekommandot
avslutades med exit 0. Den tog cirka 39 minuter och tog bort 822 981 253 byte:
32 pensionerade snapshots, 10 976 råfiler och två äldre prisartefakter.
SQLite har dessutom 2 420 813 824 återanvändbara byte. Den upprepade
referenskontrollen är en separat driftkostnad; ingen säkerhetskontroll
har kortats i denna release.

Malmös prisbygge avslutades med kod 0, men första återleveransen fick
`source published but runtime activation not confirmed` efter en fördröjd
laddningsbekräftelse. Avläsning 01:40 UTC bevisade att exakt den publicerade
versionen var laddad och ready 200. Återleverans av samma paket gav därefter
`already_active` **01:46:20 UTC** och reläets exit 0.

- Artefakt: `feb88adddb6299ad8fc744518cbbd9587447f130e43ee8d75752714956937352`.
- Snapshot: `f72bf5acfa3e40e88a458fcacdb28310`.
- Ursprunglig observation: `2026-10-20T16:17:06.288733+00:00`, oförändrad.
- Laddad/publicerad version: `price-universe:06c433309ebb798f534948f02366c36d88a0dd1d026e5e90556e50bc324df59f`.

Slutkontroll **01:46 UTC**: Lund och Malmö ready 200 med rätt BUILD_ID,
samma publicerade/laddade version per kommun, alla 14 obligatoriska kontexter
kvalificerade/publicerade/laddade och ingen väntande lokal reläleverans.
Servern har cirka 81,45 GB ledigt, över beräknat behov 22,67 GB. Senaste
avläsningen av HTTP 5xx-metriker är tom. Tjänstekontroll 01:31 UTC visade
alla tre tjänster igång, noll omstarter och ingen OOM; schedulerns image och
BUILD_ID är oförändrade.

Coops basunderlag är fortsatt STALE (cirka 74 timmar) men kvalificerat och
användbart enligt gällande prispolicy. Dess källtid har inte förnyats.
Låskonkurrens och sena laddningskvitton kan fortfarande ge fel i enskilda
schemakörningar; denna återställning ändrar inte schema eller reläkod.
Underlag sparas lokalt i `.local/category-search-20261020/`.
Inga privata profiler, cookies, databaser eller hemligheter ingår i Git.
