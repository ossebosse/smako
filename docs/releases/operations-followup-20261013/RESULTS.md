# Driftuppföljning och gemensamma kommunfixar – 13 oktober 2026

Rättningarna är aktiva. Coops granskade återspelning är godkänd och laddad i
Lund. Båda kommunerna är tillgängliga. Sex externa butikskällor och långsam
första menyberäkning kvarstår enligt avsnittet nedan.

| Kommun | Readiness | Obligatoriska baskontexter | Hela prisversionen |
| --- | --- | --- | --- |
| Lund | 200 | 5/5 FRESH | aging |
| Malmö | 200 | 9/9 FRESH | aging |

Slutkontroll: 2026-10-13T13:08:52.255847+00:00. Laddning verifierades mot rätt kommun,
inte enbart genom ett manifest på disk. `aging` beror på äldre valfria underlag;
samtliga obligatoriska baskontexter är FRESH. Gränserna 36/48 timmar består.

## Genomförda åtgärder

- **Prisinsamling:** Willys parser v5 hanterar den granskade nullable-number-
  förändringen utan att skapa saknade priser. ICA:s dubbla länkar till samma
  butikserbjudande normaliseras. City Gross-diagnostiken följer rätt kommuns
  godkända databasreferens. Dessa rättningar gäller gemensam kod för alla kommuner.
- **Coop:** separata offentliga API-versioner för ecommerce och personalization
  rättar 404-felet. Parser v3 tillåter exakt granskade frivilliga energi-/märkes-
  metadatafält; okända fält, typändringar och kommersiella villkor är fortsatt
  spärrade. Kommunens eget flöde äger fysiska erbjudanden och kör inte den gamla
  stadsbaserade hämtningen en gång till. Onlineinsamling begränsas fortsatt till 730400.
- **Återspelning:** hela katalogens råfiler hashkontrolleras strömmande med separata
  gränser, 32 MB per fil och 128 MB totalt. Första reparationsförsöket stoppades före
  mutation eftersom 42,8 MB sammanlagt överskred den tidigare 32 MB-gränsen.
  Incidentjournalens identitets-, runtime-, färskhets- och engångsspärrar består.
- **Samtidig drift:** ett personligt menyprov under prisuppdatering hittade
  `database is locked`. Den levande källdatabasen var i DELETE-läge. Managed refresh
  och guarded replay säkerställer nu WAL under samma operationslås, med FULL-
  durabilitet. Därmed kan läsare använda committade fakta under källskrivning.
  Samma rutin gäller efter restore och för kommande kommuner. Slutna hashbundna
  arkiv och byggkopior ändras inte. [SQLite WAL](https://sqlite.org/wal.html).
- **Publicering:** exakt laddat kommunmanifest kan kvitteras utan ombygge när
  underlag, hash och färskhet fortfarande stämmer. Kommunala kvittensjournaler
  följer med. Verkligt förfallna butiker, inventeringar och kampanjövergångar
  behåller vanligt källarbete. Verifierat i drift: Malmös väntande kvittens
  avslutades med `build_reused=true`, exitkod 0 och utan ett nytt prisbygge.
- **Backup och återställning:** missad daglig backup återförsöks av befintlig
  worker. Recovery scope v2 omfattar samtliga aktiva kommuners artefakter,
  register, godkända källdatabaser, journaler, privata data och raderingsjournal.
  Ett ändrat kommunregister gör en ny backup förfallen. Manuella one-off-tjänster
  använder samma granskade källimage och kommunrötter som schemalagd drift.
- **App:** samma validerade prisversion behåller sina beräkningscacher vid reload.
  Statuskontroller väntar inte på menyberäkningens cachelås. Glesa och ensamma
  butikskombinationer beräknas effektivare med oförändrade priser och urvalsregler.
  Två gamla testcontainrar är stoppade med automatisk återstart avstängd.

## Aktiv drift och verifiering

App: `ops-runtime-d7bcd3571125`, image
`sha256:96408f133010817d27944163441721623adb5a848b1cc396db455a908991fb83`.
Source och one-off-tjänster: `ops-price-recovery-7e28ff96f72d`, image `sha256:f45d9ae4ea8733ea336914db972285f162eee940b3fc135b4e706624551fb4ee`.
Endast granskade filpatchar lades på verifierade produktionsimages. Den separata
icke släppta ingrediensändringen `1518101` är inte aktiverad. Mountar, övrig
miljö, cron och andra tjänster verifierades oförändrade vid källaktivering.

Ordinarie Coop-hämtning `f3041b4cb3464fe898dbac344a64bb43` slutfördes 11:15 UTC:
820 anrop, 748/748 kategorier, 817/817 produktsidor, 11 292 unika produkter,
inga transportfel eller karantänrader. Den avvisades för sex metadatafält.
Granskad parser v3 återspelade exakt det sparade underlaget i produktion till
`6a0f76920461481289bc6d3df523a481`: inga nätverksanrop, 819 råfiler med identiska
hashar och ursprungliga observationstider, ingen generell schemaacceptans.
Källan promoverades och verifierades därefter i appens laddade Lund-version.
Publiceringsjobbets exitkod var 2; detta måste läsas tillsammans
med kvarstående valfria källbegränsningar och faktisk laddningsstatus.

ICA Bunkeflostrand 1003660: 84 hämtade rader, 79 parsade, 65 godkända enligt
befintligt radkontrakt och 19 utanför godkänd källa. Snapshot
`487735c2218749bcbe7e54bf7a7d6750` verifierades i laddad Malmö-version och rätt
fysisk butikskontext på Klagshamnsvägen 40. Detta är kvalificerade enskilda rader,
inte ett påstående om helt godkänd katalog. Hemköp 4247: 9 261 produkter,
119 anrop, inga insamlingsfel, snapshot `5f57a78acfb74228a2d65ed56f25bf2f`.
City Gross 3211: 13 652 produkter, 139 anrop, inga fel, snapshot
`db63eb4d7c8d4a10b15d000bb523009e`. Dessa tre källor verifierades laddade i Malmö. Det senare ordinarie försöket
för Hemköp 4199 slutfördes 12:31 UTC: 7 006 produkter, 94 anrop och inga
insamlingsfel, snapshot `15f3ce678b194af6bc260282259d06e9`. Även denna snapshot
verifierades därefter i laddad Malmö-version.

Offentlig Malmö-meny på aktiv app, fem middagar/två portioner/högst tre butiker:
396,375 s första anropet, 8,672 s upprepning. Båda HTTP 201, alla 17 kontroller
inklusive pris-/näringsaudit och identisk återläsning godkända. Readiness Lund,
Malmö och prisstatus svarade samtidigt HTTP 200 på 0,703 / 0,468 / 0,313 s.

Det första personliga slutprovet träffade databaslåset och avbröts med serverfel;
felet och stackspåret bevarades. Efter den aktiva databasrättningen klarade
personlig Malmö-meny kontrollen på 61,3 s, med godkänd checkout-audit,
identisk sparad återläsning och inga webbläsarfel. Ingen omräkning begärdes.

Nätverksavstängd jämförelse med fryst prisartefakt och klocka gav 856,115 →
602,441 → 440,016 sekunder för samma fullständiga meny. Resultatet, sökräknarna,
alla varianter, priser, recept och kvalitetskontroller var identiska efter att
endast tidsmätningar tagits bort. Detta är lokal jämförelse, inte garanterad livelatens.

Backup `20261013T083139Z`, slutförd 08:36 UTC, återställdes och verifierades
fullständigt 09:26 UTC i nätverksisolerad katalog: 60 filer, 6 117 333 859 byte,
Lund och Malmö, hashkontroller, semantiska databas-/prisjämförelser och aktuell
raderingsjournal. Produktionsdata återställdes inte. Övningen tog cirka 42 minuter.
Slutkontrollen bekräftar att alla tidigare 262
planrevisioner och 86 privata tillstånd är oförändrade.
Nu finns 268 respektive 88, efter tillkomna verifieringsplaner.
Inga nya OOM-kill sedan granskningen började 06:32 UTC. Båda kommunernas
Windowsreläer har ingen väntande leverans; schemalagda uppgiftens senaste resultat är 0.

## Kvarstående begränsningar

Sex butikskällor saknar kvalificerbart aktuellt underlag: Coop Malmö Central
3833, Kornettsgatan 3835, Djupadal 3831 samt X:-tra Skansvägen 3658,
Söderkulla 3646 och Nydala 3829. De tre Coop-källorna gav timeout utan verifierade
produktkort. Skansvägens och Söderkullas aktuella officiella publikationslänkar
leder till `dr-saknas`; Nydala saknar användbar publicering. HTTP 200 med tomt
objekt är inte bevis för en godkänd tom katalog. Ordinarie återförsök och
senaste giltiga underlag består. Nästa observerade återförsök är 18:11 svensk
tid för Malmöbutikerna och 19:16 för Skansvägen. Inga observationstider förlängs.

Källornas fullständiga råhälsa kan vara sämre än hälsan för de enskilda rader som
passerar uttrycklig granskning. ICA ovan och Lidls delvis parsade flygblad får
inte beskrivas som fullständigt godkända kataloger. Underlaget som inte kan
verifieras hålls utanför. Första offentliga menyberäkningen är fortfarande långsam.

## Funktionen för fler kommuner

Rättningarna ligger i gemensam registrering, insamling, import, diagnostik,
publicering, databasdrift och backup. Ingen ny kommun har aktiverats i produktion.
Isolerade regressionsprov registrerar Göteborg som tredje kommun och kontrollerar
backup/restore, kvittens, kvarvarande källfel, återförsökstider och samtidiga läsare.
Willys-provet använder också ett nytt syntetiskt butiks-ID. ICA prövas med
oberoende butikslänkar. Ny kommun använder aktiv schemaläggare och samma kod;
kapacitetsunderlag, officiella identiteter och oförändrade kvalitetsgränser krävs.
Se [kommunfunktionen](../../municipal_scaling.md).

Riktade tester för kommuner, backup/restore/radering, driftsättning, runtime,
Willys, ICA, Coop, diagnostik, lagring och varukorgspriser passerar. Sista
samtidighetsändringen passerar 62 refresh-/diagnostik-/byggkopieprov samt 53
lagrings-/driftsättningsprov. Kandidatens samtidiga läs-/skrivprov passerar också
på produktionsservern utan nätverk. Ruff, compileall och diffkontroll godkända.

## Evidens och återgång

Sammanfattad evidens finns i [EVIDENCE.json](EVIDENCE.json). Privat lokal evidens
finns i `.local/ops-followup-20261013/`; rådata, användaridentiteter och cookies
ligger inte i Git. Serverevidens finns under `/opt/smako/evidence/` för respektive
exakt BUILD_ID. Varje aktivering sparar föregående Compose-wrapper.

Kodåtergång görs under operationslåset till dokumenterad föregående image och
BUILD_ID, med oförändrade databaser och manifest. Återställ inte användardata
för en kodåtergång. Den levande databasens WAL-läge kan behållas vid kodåtergång;
slutna SQLite-kopior skapas med befintlig backupfunktion, aldrig genom att enbart
kopiera en aktiv huvudfil.
