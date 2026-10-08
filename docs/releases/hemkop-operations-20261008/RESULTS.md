# Prisdrift återställd; en intermittent appanmärkning kvarstår

Kontroll 2026-10-08 15:17:47 UTC: `/ready` 200, databas och PlanStore ok.
Samma dd12-app, kompletta recept på. Källfix och diagnosverktyg är aktiverade
enbart i scheduler. Ingen måltids-/prestandaaktivering eller Git-push.

## Fem obligatoriska baser

Äldsta produktobservation, inte replay-, import- eller byggtid. Kommun 1281 och
36/48-timmarsreglerna är oförändrade. Fulla ID:n finns i [FINAL.json](FINAL.json).

| Bas | Observation UTC | Ålder vid kontroll | Snapshotprefix | Serving |
| --- | --- | --- | --- | --- |
| Coop Online Syd | 8 okt 11:33:16 | 3,742 h | 0e91c5c39f9d | FRESH / laddad |
| Hemköp Brunnshög | 8 okt 13:58:34 | 1,320 h | e45cd4719bc6 | FRESH / laddad |
| Hemköp Karhögstorg | 8 okt 12:03:33 | 3,237 h | d621ab31a2af | FRESH / laddad |
| Willys Lund | 7 okt 23:31:27 | 15,772 h | 72c524df46c3 | FRESH / laddad |
| Willys Lund Nova | 7 okt 23:51:22 | 15,440 h | 72c524df46c3 | FRESH / laddad |

Coop är online_fulfillment; övriga fyra online_store. Separata äldre
erbjudandekällor ger fortfarande requires_attention; det betyder inte att
någon av dessa fem baser saknas eller är stale.

## Genomförd återhämtning

- Karhögstorg: vanlig replay av b662192…, 86 råfiler, 6 304 produkter,
  0 karantän, healthy/promoted. Alla ursprungliga hashvärden/tider bevarade.
- Brunnshög: ett nytt komplett ordinarie försök, 74 anrop, 5 131 produkter,
  790,611 s, 0 fel. Gamla motsägelsen 927a801e… bevarad. Ingen kampanjrad
  valdes bort, ingen atomisk garanti från källan påstås.
- Godkänd Coop och redan importerad Willys återanvändes. Det separata
  publiceringsförsöket gjorde ingen ny fullkataloghämtning; total tid 444,038 s.
- Ett ytterligare byggfel belades: nullable erbjudandevillkor jämförde str
  med None. Commit 08f7613 rättar ordningen för signatur och prisvektor.
  Fyra regressioner FAIL före/PASS efter; inga priser/villkor valdes bort.
- Manifest `bc39552c…` aktiverat 14:48:51 UTC och samma ID laddat i dd12.
  Artefakt SHA-256 `4d0590d59d3737e7ba0c7fd6963943dab1bc9f6d4fffc443488fe97860d63d22`.
  Samtliga 2 232 refererade råfiler, 115 265 661 byte, hashverifierade.
- Kontrollerad Windows Scheduler-start 14:50:51 UTC med fe795. Samma paket
  `d53486fb…` återlevererat; mottagaren svarade `already_active`. Exakt en import
  `72c524df…`. Beständigt last-success 14:53:39 UTC och task_success bekräftade.

## Kapacitet och bevarande

Jämförelsepunkten är föregående sparade kontroll 12:44 UTC, ingen ny påstådd
0-byte-observation. Decimal GB ledigt:

| Volym | Föregående kontroll | Slutkontroll |
| --- | ---: | ---: |
| Serverns gemensamma datavolym | 13,49 | 13,32 |
| Windows C: | 5,53 | 5,51 |
| Windows D: | 664,30 | 664,22 |

Observerad serverlågpunkt under tillfällig databaskopia: 9,79 GB. Kapacitetskrav
8,00 GB: två DB/WAL/SHM-kopior, två prisartefakter och 512 MiB reserv. Förkontroll
garanterar inte framtida skrivutrymme. Ingen ny stor rensning/arkivering här.
Ett litet v1-incidentindex bevaras en gång vid v2-migrering; inga råarkiv dupliceras.

Uppgifts-XML är semantiskt oförändrad: ossia/S4U/Limited, IgnoreNew, PT3H och
pinnad PowerShell. Ingen omregistrering. Befintliga D:-datavägar används fortsatt.
Tidigare 625-filers och S4U parent/child-tempbevis återanvänds för identisk fe795,
inte räknas som nya tester. Alla 216 gamla revisioner och 61 privata rader är
exakt bevarade; nu 222 respektive 63 efter verifieringsplanerna. Ingen DB-restaurering.

## Verkliga menyprov

Mobil layout, separata gästsessioner, dagens data, fem middagar/fyra portioner,
fem tillåtna kök, Balanserad, 10–15 ingredienser, högst tre butiker, uppskattat köp
och separat näringsmedgivande. Inget extra proteinmål sattes. Inga signerade
kontosessioner, fysisk iPhone-testning eller provlagning påstås.

- WebKit/personlig: PASS, klick till rendering 71,188 s.
- Chromium/publik: första försöket FAIL med status-GET 500/plain text.
  Apptelemetri bekräftar internal_error 14:51:24 UTC, request
  `9e96c548-6414-467b-ab7e-3d5e4fe6d779`.
- Chromium/publik, samma val och ny verifieringsidentitet: PASS, 60,875 s.
- Båda PASS-flöden: en jobbidentitet/en dyr start vid dubbelstart, omladdning,
  korrekt recept-/inköpsvisning, avstämd korg VERIFIED, byte, omräkning, tre
  revisions-GET och annan ägare 403/404. Inga oväntade pageerrors/nätfel där.
  Båda kostade 649,95 kr; detta är ett resultat, ingen historisk acceptansnivå.

**Första 500-felets exakta orsak är inte belagd; omkörningen är ingen rättning.**
En separat läsande dd12-prob visar dessutom att dess gamla sorteringshjälpare
kan kasta TypeError för 26 produkter i underlaget. Ingen kausal koppling till
HTTP 500 är bevisad. Konsumentappen är inte bytt. Nästa appärende ska använda
jobbet `3218c89521084fc7a1c6b53b622c7276`, request-ID:t och de bevarade råfelen.
Ändra inte prisunderlaget eller maskera 500 för att få gröna prov.

## Återanvändbar drift och kvarstående ärenden

Börja med [OPERATIONS.md](../../OPERATIONS.md). Installerad runtime
`ce326c1d7fcf5235e77ea4fcf2139d4fb25be849`; 173 tester PASS, Ruff/compileall PASS.
Status/reproduce och reparationsförkontroll är provade i slutimagen.
Index v2 har 13 incidenter; de två aktuella Hemköpsfallen är källåterhämtade.
Historiska Coop-fysiska schemafel och Lidl-kvalificeringsfel ligger kvar öppna
och separat klassificerade. Ingen extern notifieringstjänst har installerats
och inget utskickat larm påstås.

Inga scheman pausade: Windows 01:30/09:30/17:30, nästa 17:30 svensk tid vid
kontrollen; server var 15:e minut. Omedelbar behovskontroll gav not_due och
0 externa prisanrop. Befintlig global backoff till 18:37:43 UTC bevarad;
första tick därefter 18:45 UTC. Framtida automatisk framgång är inte verifierad.
