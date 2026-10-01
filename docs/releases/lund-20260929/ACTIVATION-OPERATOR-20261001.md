> Historik: operatörssteget är genomfört och uppgiften senare återupptagen.
> Se [faktiskt aktiveringsprotokoll](ACTIVATION-LIVE-20261001.md). Kör inte om ApplyPaused.

# Aktivering stoppad vid Windows-behörighet, 2026-10-01

**EJ AKTIVERAT.** Alla fyra avgränsade beslut är godkända. Schemat är inte längre
en godkännandespärr. Den faktiska registreringen av uppdaterat schema med paus
nekades **19:50:00 UTC / 21:50:00 svensk tid**, `0x80070005 E_ACCESSDENIED`.
Anrop: Task Scheduler COM `RegisterTask`, `TASK_UPDATE | TASK_DONT_ADD_PRINCIPAL_ACE`,
befintligt namn `\Smako Willys Local Relay`, ossia/S4U, befintlig Limited-nivå.
Anropande ossia var inte förhöjd. XML-validering lyckades; detta är ett
registreringsfel, inte ett körningsfel. Inget jobb startades.

## Minsta operatörssteg

Öppna PowerShell **som administratör med samma ossia-konto** och kör:

```powershell
& "C:\Users\ossia\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe" -NoProfile -NonInteractive -File "D:\Projects\Smako\scripts\release_verification\set_lund_task_paused.ps1" -ApplyPaused
```

Ingen ExecutionPolicy-överstyrning eller permanent säkerhetsändring behövs i
den verifierade PS7-kontexten. Skriptet är granskat och XML-validerat, men dess
förhöjda mutation är **inte utförd**. Det:

- Hashkontrollerar alla 624 filer i bdc9 och vägrar om den befintliga uppgiften
  avviker från den granskade originaldefinitionen.
- Stagerar de godkända bdc9-argumenten/arbetskatalogen och lokala
  01:30/09:30/17:30 i **samma** uppgift, med tillfälligt `Enabled=false`.
- Bevarar pinnad pwsh, ossia/S4U/Limited, ACL, IgnoreNew, PT3H,
  StartWhenAvailable, WakeToRun och alla övriga uppgiftsfält.
- Kontrollerar återläst XML/ACL och lämnar uppgiften **pausad**. Det startar
  ingenting och ändrar varken server, policy, kö, konfiguration eller tillstånd.

Det nekade försöket gällde schema+paus. Slutskriptet inkluderar dessutom de
redan godkända Arguments/WorkingDirectory för att minska operatörsstegen;
denna slutversion har enbart validerats, inte registrerats. En ändrad definition
vägras, inte skrivs över. Privat före-/efter-XML finns under
`.local/activation-approved-20261001/`. Efter operatörssteget måste faktisk
uppgift läsas tillbaka. Serverförkontroller, serverpaus, låsväntan, konsistenta
backuper och byte fortsätter sedan enligt ACTIVATION.md. **Aktivera eller starta
inte uppgiften manuellt innan det samordnade bytet och acceptansproven passerat.**

## Verifierat nu och oförändrad produktion

Arbetsgren `release/lund-relay-20260929`, startcommit `cd306501…`, ren vid start.
Runtimeändringar: inga. Identiska paket:

| Identitet | Värde |
| --- | --- |
| Serverruntime | `08c137475d9ca96a6ef7673245a639c8c5c9e922` |
| Server-/återgångsbild, tillgänglig | `sha256:d8a166fa7ee162cd0570f9d8089ff800e00d9c949ac3c674e387c5fff1538dd7` |
| Server-ZIP SHA-256 | `c20f8ad6ce316df121117c32cb44dc308a8d73011d097ec8799be095883b1e22` |
| Inaktivt installerat relä | `D:\smako-local-relay\releases\bdc9f7df4170` |
| bdc9 ZIP SHA-256 | `299ff34ecb7b5976e317afeef54719c9286d0ecd64c2807cee58533945de57d7` |
| Produktionsbild, oförändrad | `sha256:54dde8382599ac30beee8bffd05d8cefff232e1ea5c81f1fd7f302db0d591c1f` |
| Uppgifts-XML SHA före = efter | `c781d10ce504aa172d8006f365f7ad167ac2ca23688fcf629d1b0851c5ff6755` |

Produktion lästes 19:46:59 UTC: app/scheduler på gamla bilden, samma manifest
`96ca8bfb…`, 36 906 poster, 170 planrevisioner, `/ready 503`, `freshness=stale`.
Detta är samma **befintliga** fel som före försöket. Inget nytt driftsfel genom
byte har uppstått; inget byte har gjorts. 17 gamla inboxsökvägar kvar.
Schemat återläst: en daglig **01:30**-trigger, Ready, nästa körning
**2026-10-02 01:30 +02:00**. Gamla argument/arbetskatalog gäller fortfarande.
Serverns befintliga cron är oförändrad: backup 02:47, refresh 03:17, retry 06:17.
Ingen produktionsdatabasbackup eller köövergång påstås; dessa steg har inte nåtts.

## Behovskontroll och verkliga tidsmarginaler

Nytt prov på **separat kopierat** S4U-tillstånd, bdc9:s riktiga `local_relay.run`:
`not_due`, exit 0, **0 collection/push/activation**. Dessa anropsgränser spärrades
i provet. Kvitto byteidentiskt, observation `2026-10-01T07:44:37.057437Z`,
artefakt `5b1a2b6b…`. Originalets tillstånd är oförändrat. Detta är ett
not_due-/idempotensprov, ingen ny obevakad livehämtning och inget produktionsprov.

Beräkning för godkända tre tider, tre timmars budget till **laddad serving**:
35 + 8 + 3 = 46 timmar normalt; hösten 25 oktober ger högst nio timmars glapp,
totalt 47 timmar. Våren 28 mars 2027 ger ett sjutimmarsglapp, men största glappet
är fortsatt åtta timmar. Gränserna är oförändrade. En missad kontroll kan ge
54 timmar, 55 vid höstövergången. Försening eller lås förbrukar marginalen.
IgnoreNew/StartWhenAvailable/WakeToRun garanterar inte färskhet vid dator-/nätbortfall.
Kontrollera fjärrjobb och lås även efter Windows PT3H; bryt inga lås.

För liveartefaktens oförändrade källtid: due **2 oktober 20:44:37**, beräknad
hämtning **3 oktober 01:30**, serving cirka **02:19:09** med tidigare verklig
hela-kedjan-tid 49m9s, alternativt **04:30** med tretimmarsbudgeten. Hårt stopp
**09:44:37**; då återstår 5h14m37s med budgeten. Detta är en prognos efter korrekt
produktionsleverans, inte en faktisk framtida körning eller ett kvitto i nya
produktionsarbetsytan. Windows-nästa behovskontroll efter ett lyckat byte vore
2 oktober 01:30. Återläs alltid aktuell NextRunTime när uppgiften återupptas.

## Kandidatkällor, inte aktiverad produktion

19:51:39 UTC: fem obligatoriska serverade baser FRESH, 11,801–13,705 timmar.
Kandidatens manifest `19cd1da8…` har **44 066** poster. Senaste relevanta
aktiva källsnapshots i SQLite bekräftar tiderna. Historiska snapshots bevaras.
Alla tider i tabellen är svensk tid, +02:00; due är observation +35 timmar
innan eventuell tidigare ordinarie kampanjsamordning på serversidan.

| Bas | Äldsta serverade observation 1 okt | Due 2 okt | Källans +48h 3 okt |
| --- | --- | --- | --- |
| Coop Online Syd | 08:09:21 | 19:09:21 | 08:09:21 |
| Hemköp Brunnshög | 08:55:05 | 19:55:05 | 08:55:05 |
| Hemköp Karhögstorg | 08:39:40 | 19:39:40 | 08:39:40 |
| Willys Lund | 09:44:43 | 20:44:43 | 09:44:43 |
| Willys Lund Nova | 10:03:35 | 21:03:35 | 10:03:35 |

Willys samlas gemensamt enligt artefaktens tidigare observation **09:44:37**,
inte separata butikstimers. Serverbasernas faktiska nästa hämtning är **inte
fastställd**: slutlig privat serverkonfiguration/rendering och behovsplan ska
kontrolleras innan byte. Tabellens due-tider är inte utlovade körningar.

**Kandidatens konservativa manifestgräns är tidigare:**
`oldest_base_observed_at=2026-09-30T11:17:53.844785Z`, alltså 36h den 2 oktober
01:17:53 svensk tid och 48h **2 oktober 13:17:53**. Den får inte ersättas med
tabellens nyare tider eller rebuildtid. Kontrollera aktuell kandidat och ordinarie
behovsstyrd uppdatering vid fortsättning; dagens tabell är inte ett friskhetsintyg
för morgondagens aktivering. Full rå-/kampanjkontroll och faktisk serving återstår.

## Kvar före normal drift

| Kontroll | Status denna fortsättning |
| --- | --- |
| Tre tider/DST + kopierad not_due | PASS som beräkning respektive isolerat prov |
| Faktisk uppgiftsändring | BLOCKERAD av Windows-behörighet, oförändrad uppgift |
| Produktionens leverans/import/publicering/reload | EJ UTFÖRT |
| Nyplanering, fyra profiler och representativa köp i produktion | EJ PRÖVAT |
| Uttrycklig omräkning av sparad plan i normal produktion | EJ PRÖVAT, separat acceptanskrav |
| GET och identiskt innehåll efter omstart i ny produktion | EJ PRÖVAT |
| Begränsad läsåtergång | Tidigare isolerat PASS, inte aktiverad |

Stoppet motiverar inga applikationsändringar eller nya runtimepaket. PowerShell-
XML-validering, 624 reläfilhashar, not_due-prov, Python Ruff/compileall passerar.
Ett inledande läsprov mot stor SQLite i read-only container gav I/O-fel för
temporär sortering; samma läsning passerade med temporär sortering i minnet och
verifierad tom/saknad WAL. Ingen databas, WAL eller rättighet ändrades.
S4U-/övergångs-/återgångsbevisen är fortsatt giltiga inom sina provade gränser.

Separat nästa etapp, inte implementerad här: kampanjfönster natten söndag–måndag
och onsdag–torsdag i Europe/Stockholm, källornas faktiska kampanjdatum samt mätning
av basprisförändringar mellan autentiska hämtningar för framtida intervallbeslut.
Ingen Malmö-aktivering, städning, säkerhetspolicyändring eller push.
