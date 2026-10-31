# Mindre uppvärmning och färre upprepade filkontroller

[PR 57](https://github.com/ossebosse/smako/pull/57) prioriterar aktuella
receptvyer vid V2-uppstart. Äldre planer använder fortsatt befintlig exakt
historikvalidering vid behov. Legacy och V1 behåller tidigare uppvärmning.
Det flyttar den äldre historikens kostnad till första användningen av den;
historiska recept eller återkallelser tas inte bort.

Axfoods publicerade detaljarkiv får en anropslokal kataloglista, högst 8 MiB
för namn och set, samt två små metadatauppsättningar för katalogerna.
Befintlig dokumentcache har separat 32 MiB-budget; inga sådana strukturer
behålls mellan anrop. Listan används enbart för
att fastställa att båda filerna saknas. Varje negativt uppslag kontrollerar
katalogens aktuella identitet, mode och ändringstider. Ändrad katalog,
symbolisk kataloglänk, läsfel eller överskriden budget ger ordinarie läsning.
Manifestfrånvaro används aldrig som bevis för filfrånvaro. Befintliga,
olistade, korrupta, negativa HTTP-svar och återkallade metadata valideras som
tidigare. Inga produktbeslut eller negativa svar lagras mellan anrop.

## Mätning mot aktiv betaversion

| Komplett meny, audit, sparning och ägd återläsning | Före | Efter | Samma pris |
| --- | ---: | ---: | ---: |
| Italiensk, två portioner, kallt | 56,118 s | 49,688 s | 110,55 kr |
| Italiensk, samma val, varmt | 26,327 s | 20,925 s | 110,55 kr |
| Nytt val: svensk, två portioner | 26,770 s | 21,703 s | 104,23 kr |
| Nytt val: grekisk, två portioner | 26,167 s | 21,639 s | 106,90 kr |
| Nytt val: italiensk, en portion | 28,904 s | 26,555 s | 88,61 kr |

Alla fem menyer har identiska valda recept, hela serialiserade varukorgar
och priser. Samtliga 54 515 faktaposter, alla deras fält och hela versionen
är identiska efter separat omräkning med originalkod och tom artefaktcache.
Kall faktaladdning minskade 27,736 → 21,751 s; varm upprepning 12,146 → 7,025 s.

Isolerade containrar med exakt aktiv bild/planeringsmiljö, inklusive Axfoods
release, skrivskyddade offentliga källor, inget nät, 4 GiB och nya syntetiska
testdatabaser. Prisåterställning tog separat 92,199/91,860 s före mätningarna.
HTTP, admission/kö och UI ingår inte här. Ett prov per fall/version bevisar
inte p95, samtidighet eller hela valkatalogen. Ett första mätverktygsfel före
planeringen rättades och räknas inte som ett menyprov.

## Separat receptuppvärmning

Två kalla isolerade processer med tom härledd cache: **31,946 → 17,203 s**.
Topp-RSS vid avslutad uppvärmning: **419 636 → 350 640 KiB**, cirka 67 MiB
lägre. Alla 2 462 aktuella recept, fullständigt serialiserade för vart och
ett av portionsantalen 1–4, har identiska kontrollsummor. Kandidaten har
ingen materialiserad historik vid mätgränsen; ett äldre utgivet recept
valideras därefter korrekt på begäran. Tiderna gäller receptuppvärmningen,
inte hela appuppstarten. Minnesstädningens skydd är oförändrade; hela
menyprocessens toppminne var i stort sett oförändrat.

## Verifiering

131 riktade tester passerade lokalt, ett symlänksfall kräver Linux. Ruff och
compileall passerade. Full Linux-CI: 4 417 pass, 63 skip, inga fel, inklusive
symlänksfallet och bevarad recepttäckning. Testsvar täcker nytillkomna och
föräldralösa filer, katalogbyte/ändring under läsning, begränsad budget,
läsfel, metadata utan råfil samt befintliga korruptions-/återkallelsegrindar.
Releasepaketets båda Pythonmoduler är AST-bundna till den uppmätta koden.

Se [maskinunderlaget](EVIDENCE.json) och
[aktiveringsjournalen](../../releases/prewarm-detail-reads-20261031/ACTIVATED.md).
