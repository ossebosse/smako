# Willys-lagring och veckosökning – två separata resultat

## A. Lagringsfix klar; driftåterställning blockerad

Senaste fulla driftkontroll: **7 oktober 2026, 15:05 UTC**. Betan kör rätt
dd12-image och har kompletta recept på. Serverns faktiska datavolymer har
**0 byte tillgängligt**, `/ready` är 503 och planlagringen ger
`SQLITE_IOERR_SHMSIZE`. Alla fem obligatoriska baser är äldre än 48 timmar.

Den separata reläkandidaten **fe795e5b04f5** är installerad och lokalt
verifierad. Den binder temporärfiler till den befintliga kommunarbetsytan på
D: och inför kapacitetskontroller. Windows nekade registreringsändringen;
uppgiften använder fortfarande **bdc9**, med oförändrat konto, S4U/Limited,
schema och övrig XML. S4U-provet för den nya starten återstår.

Den redan färdiga 8f4b-artefakten på D: har samma hash. Ingen ny kontrollerad
insamling, leverans, import eller publicering har utförts. Produktionsplanprov
och `not_due` efter återhämtning återstår. Ingen app har bytts eller återinstallerats.

Komplettering 15:32 UTC: servern är fortsatt full. Den ordinarie uppgiften
startade 17:30 svensk tid med bdc9 och har påbörjat insamling; slutstatus
är ännu okänd. Den har varken startats manuellt eller avbrutits av oss.

**Behövs för att fortsätta A:** serverutrymme samt administratörskörning av
den redan avgränsade uppgiftsändringen. Därefter S4U-prov och den ordinarie
kedjan med ny giltighetskontroll. Inget nytt appgodkännande efterfrågas.
[Full driftstatus](A-STATUS.md), [maskinrapport](A-STATUS.json),
[retentionförslag utan radering](RETENTION-DRY-RUN.md).

## B. Verifierad ny kandidat; inte aktiverad

Runtime **54cb2e8159a126de26fa11cb1d393dc275238fd3**. Recept, fakta,
importväg, måltidsval, statusflöde, butikstak, sökbudget och oberoende audit
är bevarade. Ändringen återanvänder identiskt näringsunderlag efter separat
receptvalidering, använder befintliga cachegränser med LRU och beräknar
samma faktahash utan en stor mellanliggande kopia.

Samma frysta underlag och lokala miljö, två CPU och 3 GiB:

| Mått | Före | Efter |
| --- | ---: | ---: |
| Hela kalla huvudprocessen, median av tre | 118,37 s | 111,16 s |
| Varm ny huvudberäkning, median av tre | 51,09 s | 48,39 s |
| Hela kalla 5×-processen, median av tre | 892,01 s | 534,79 s |
| Varm ny 5×-beräkning, median av tre | 775,67 s | 419,03 s |
| Chromium, varmt huvudklick, ett par | 55,984 s | 54,234 s |
| WebKit, varmt huvudklick, ett par | 55,687 s | 53,234 s |
| Chromium, kallt huvudklick, ett par | 94,188 s | 87,078 s |

5× minskar cirka **40 % kallt och 46 % varmt**. Samma 620 relevanta
recept och 12 781 veckoutvärderingar prövas. Skalsynteterna räknas inte som
nya riktiga recept. Kallt huvudklick når fortfarande inte 60-sekundersmålet,
och 5× tar flera minuter. Sökningen är fortsatt begränsad; globalt optimum
är inte bevisat. [Alla tider, CPU, minne och mätgränser](PERFORMANCE.md),
[profil och oförändrat sökarbete](SEARCH.md).

**37 fullständiga före/efter-par matchar** efter redovisad metadatanormalisering.
60 planresultat klarar villkorskontrollen. Huvudmenyn är oförändrat 741,15 kr;
enkla middagar 262,28 kr, frukost 40,70 kr, mellanmål 56,86 kr, kombinerad
vecka 418,17 kr och variationsfallet 787,56 kr. Detta är berikad historisk
replay, inte aktuella offerter eller nya besparingar på mat.

206 backendtester, 14 strikta mobilwebbläsarprov, fyra äldre 15/20-profiler
med 40/30/20-krav samt 30 individuella receptkvalificeringar har passerat.
Privat skafferi, gemensamt inköp, receptbyte, omräkning, ägarisolering,
appomstart och flagga av har verifierats. Invalidering och äldre revisioner
har passerat. Initiala samtidighetsfel och telemetrivarningar ligger kvar
med separat bedömning; omkörningar presenteras inte som en appfix.
[Testbevis och begränsningar](TESTS.md), [slutkontroll](QUALIFICATION.json),
[förberedelse och verklig gemensam förpackning](PREPARATION.md).

## Leverans

- ZIP: `smako-server-54cb2e8159a1.zip`, SHA-256
  `98446fac69395c8f7eded6c15f23f8194b5e26dffde1810e83cb5a9007338667`.
- Image: `sha256:8a537fc4d333d9fc17fd06916061ed481ba433951126688df51b6b4da19766f3`.
- Verifierad imageexport: `smako-week-search-54cb2e8159a1-image.tar`, SHA-256
  `ec82580cc0a7c6d001bfda93dd0f2b8fc48938cda5d0ea5f57f7d93d9879ff19`.
- Filerna finns under
  `D:\Projects\Smako\.local\willys-storage-search-20261007\package-54cb2e8159a1\`.

**B är klar för separat aktiveringsbedömning. Ingen aktivering av B eller
Git-push har gjorts.** [App-only-anvisning för just denna kandidat](ACTIVATION.md).
Driftförkontrollerna måste klara A:s aktuella hinder före ett framtida byte.
Flagga av i samma image är provad; en äldre binäråtergång är inte kvalificerad.
