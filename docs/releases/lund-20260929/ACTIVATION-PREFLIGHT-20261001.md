# Aktiveringsprotokoll: stopp före byte, 2026-10-01

**AVBRUTET FÖRE PAUS/BYTE – ingen produktionsaktivering genomförd.**
Användaren har uttryckligen godkänt femkällorspolicyn, servern inklusive
begränsad läsåtergång och Windows-byte av endast Arguments/WorkingDirectory,
villkorat av aktuella förkontroller. Dessa tre beslut ska inte begäras igen.
Användarens avsnitt B kräver stopp om befintligt schema inte kan upprätthålla
färskheten. Denna nya förkontroll fallerar just där. Tidigare PASS för
köövergång, idempotens, S4U och begränsad återgång återtas inte.

Maskinläsbara, sanerade observationer och beräkningar:
[ACTIVATION-PREFLIGHT-20261001.json](ACTIVATION-PREFLIGHT-20261001.json).
Full XML och begränsat driftunderlag ligger privat i
`D:\Projects\Smako\.local\activation-20261001`; inga hemligheter eller
privata planer kopierades till Git. Detta är en förkontroll, inte en
genomförd konsekvent backup eller ett produktionsacceptansprov.

## Beslut och releaseidentitet

Första tidsstämplade kontrollen var 18:40:03 UTC / 20:40:03 Europe/Stockholm.
Arbetskopian var ren på `release/lund-relay-20260929`, dokumentationscommit
`6d84984e6e882becb9e49747c0b85d9016283855`. Inga applikationsändringar gjordes.

| Kontroll | Aktuellt utfall |
| --- | --- |
| Runtime | `08c137475d9ca96a6ef7673245a639c8c5c9e922`, matchar bevisen |
| Server-/återgångsbild | `sha256:d8a166fa7ee162cd0570f9d8089ff800e00d9c949ac3c674e387c5fff1538dd7` |
| Server-ZIP | SHA `c20f8ad6ce316df121117c32cb44dc308a8d73011d097ec8799be095883b1e22` |
| Runtimefiler i slutbild | 621 matchande filer, inga avvikelser; pip check/offline-Chromium PASS, read-only och utan nät |
| Bdc9 Windows-ZIP | SHA `299ff34ecb7b5976e317afeef54719c9286d0ecd64c2807cee58533945de57d7` |
| Installerat bdc9-paket | 624 filer matchar; verkligt startskript `-CheckInstall` via uppgiftens PS7 passerade, inga nätanrop |
| Effektiv PS7-policy | RemoteSigned utan Bypass/ändrad policy; inget behov att byta körkonto eller RunLevel konstaterat |
| Policy | Exakt fem kontexter i oförändrad paketerad `lund-own-five-base-20260928-v1`; policyhash i JSON |
| Aktuell Windows-XML | `c781d10ce504aa172d8006f365f7ad167ac2ca23688fcf629d1b0851c5ff6755`, oförändrad |

Nyare Windows-ZIP används inte. Det godkända transportmålet för ett senare
byte är fortfarande scheduler/receiver och kommuninbox 1281. Den nya privata
produktionskonfigurationen och kommunarbetsytan har ännu inte skapats;
testkonfiguration användes endast för det läsande installationsprovet.

## Faktisk produktion, läst utan ändringar

- App och scheduler kör fortfarande bild `54dde838…`; `OWN_SOURCES_ONLY=false`.
- Compose: `/opt/smako/current/deploy/compose.yaml` och `/opt/smako/compose.vps.yaml`.
  Appens pris- och råvolymer är read-only. Ingen ny Compose-konfiguration har
  installerats eller slutrenderats med produktionshemligheter.
- `/ready` gav **503**. Status-API gav 200 men **freshness=stale**, universe
  `96ca8bfb…`, **36 906** råproduktposter. Befintligt aktivt manifest har SHA
  `1fd662ffdbd32d2ab471e0cb6a5c3d7e8057c50be2157bbb7a9334980fd9a8fa`.
  Detta är ett redan befintligt driftläge, inte resultat av ett utfört byte.
- Senaste produktionsplandatabasen innehöll **170 revisionsrader**. Ingen
  testdatabas, testidentitet, profil eller plan har skrivits till produktion.
- Gamla inboxen inventerades läsande: 17 artefaktsökvägar. Det gamla lokala
  kvittots hash/artefaktreferens finns i JSON. Ingen ny kvittens skapades.
- Scheduler hade endast `cron -f` vid avläsningen. Befintliga låsfiler finns;
  deras ägarskap/aktivitet har inte slutkontrollerats eller lås tagits eftersom
  paus-/backupfasen inte påbörjades. En kvarliggande fil kallas inte aktivt lås.
- Faktisk server-cron: backup 02:47, refresh 03:17, Coop-retry 06:17.
  Nästa sådana tider är 2026-10-02 lokal tid. Serverns behovsstyrningsflagga
  saknas i befintlig miljö; inget schema eller flaggvärde ändrades.
- Windows-uppgiften är Ready, nästa faktiska start **2026-10-02 01:30 +02:00**
  (2026-10-01 23:30 UTC). Senaste start var 2026-10-01 01:30:01, resultat 1.
  Den återstartades inte. Den separata S4U-testuppgiften startades inte heller.

Den bevarade **kandidatens** 44 066-underlag (`19cd1da8…`) lästes separat
18:47:37 UTC / 20:47:37 lokal tid: fem obligatoriska kontexter FRESH,
äldsta serverade observationer 10,734–12,638 timmar. Dessa är autentiska
observationer, inte ny hämtning, ny publicering eller faktisk produktion.
Det ersätter inte återstående råfils-/kampanj-/frivillig-källkontroller.

## Ny konkret blockerare: dygnstrigger plus 35-timmarsbehov

Installerade bdc9 `grocery_data/local_relay.py` använder `base_35h` när
kommunbindning finns. Före `observed_from + 35h` returnerar den `not_due`.
XML har en CalendarTrigger dagligen 01:30, utan repetitionsintervall.
Servern använder LOCAL_RELAY och dess scheman ersätter inte Windows-hämtningen.

Följande är **beräkning, inte framtida körbevis**, med den autentiska
liveobservationen 2026-10-01 09:44:37 lokal tid som initialt underlag:

| Schemalagd start | Beräknat utfall med oförändrade regler |
| --- | --- |
| 2 oktober 01:30 | 15,756 h gammalt → not_due |
| 3 oktober 01:30 | 39,756 h → hämtning möjlig; förstacykeln har marginal |
| 4 oktober 01:30 | Cirka 24 h efter föregående hämtning → not_due |
| 5 oktober 01:30 | Cirka 48 h → ny hämtning börjar vid hårda gränsen |

Det verkliga liveprovet tog **49 min 9,198 s**, med första observationen
14,057 s efter uppgiftsstart. Om samma tidsåtgång upprepas i sista raden
sker ny leverans cirka **48 min 55 s efter föregående bas hårda stopp**.
Med uppgiftens befintliga PT3H-budget saknas nästan tre timmar.
35/36/48-regler, källtid och not_due får inte ändras för att dölja detta.
StartWhenAvailable/WakeToRun eliminerar inte glappet på en tillgänglig dator.

### Minsta robusta föreslagna schematillägg – separat beslut, inte utfört

Behåll 01:30 och lägg till kontrollstarter **09:30 och 17:30** Europe/Stockholm
för samma uppgift, fortfarande ossia/S4U/Limited, IgnoreNew och PT3H.
Tre jämnt fördelade kontroller per dygn ger högst åtta timmars väntan på
behovsgränsen: **35 + 8 + 3 = 46 h**, två timmars normal marginal till 48 h.
Vid en timmes återgång till vintertid blir längsta lokala intervall nio
timmar och marginalen en timme. Förseningar/avstängd dator/nätfel måste
fortfarande övervakas; detta är inte en garanti mot externa avbrott.

Detta är två extra **kontroller**, inte tre fullhämtningar per dygn:
befintlig not_due och alla färskhetsregler behålls. Två kontroller per dygn
ger upp till 12 h fasväntan; tillsammans med 35 h och full PT3H-budget blir
det 50 h och saknar generell marginal. Förslaget ändrar ingen applikationskod.

Detta går utanför godkännandet att endast ändra Arguments/WorkingDirectory.
Därför har inga triggers, körpolicyer eller säkerhetsinställningar ändrats.
Efter ett separat schemabeslut återupptas aktuella förkontroller; de redan
godkända tre produktionsbesluten behöver inte tas om.

## Ej utfört och fortsatt ordning

Ingen paus, konsekvent cutover-backup, låst relay_transition-inventering,
installation, uppgiftsändring, produktionsimport, proxyändring eller rollback
har gjorts. Alla jobb fortsätter med sina tidigare inställningar. Inga
verifieringsplaner har skapats i produktion. Ingen push eller radering.

Efter schemabeslut krävs fortsatt granskning av den privata slutkonfigurationen
mot serverns faktiska scheman och behovsstyrning, samtliga råfiler, kampanjer,
frivilliga källfel/karantän, transport, rättigheter, lås och då aktuell basålder.
Därefter följs befintlig paus/backup/byte/verifiering enligt ACTIVATION.
Ingen framtida schemakörning är ännu verifierad. Uppgiftsändringens eventuella
behov av operatörsbehörighet är inte prövat genom ett skrivförsök här.

Nästa separata etapp, endast dokumenterad: kampanjuppdateringar med huvudfönster
söndag–måndag och onsdag–torsdag i Europe/Stockholm samt mätning av
basprisförändringar mellan autentiska hämtningar inför framtida intervallbeslut.
Inga sådana funktioner, intervall eller automationsjobb har införts.
