# Näringskopplingar och extraval aktiverade

Appbytet verifierades 2026-10-15 16:37:09 UTC (18:37 svensk tid), efter
användarens instruktion ”Aktivera på betan”. Kodcommit `7e402a7`, gren
`fix/recipe-nutrition-extras`.

BUILD_ID: `recipe-nutrition-extras-app-7e402a7`.
Image: `sha256:f6f0c0e3b54574e7d50793c18a562903af87a326c017e652e028b3d3e5983174`.
Faktapolicy: `retained-catalog-facts-v11-nutrition-extras`.
Referenspolicy: `slv-component-input-v5-nordic-density`.
Se [ändring, källor och lokala prov](../../../reports/recipe-nutrition-extras-20261015.md).

## Versionsbyte och skydd av tillstånd

17 runtimefiler lades ovanpå den verkliga föregående appbilden,
`sha256:5f2558bb1443ec15d07a638655453fd1f51ac9c51bf6ef7a5e45015304e992ae`.
Samtliga 17 är byteidentiska med den lokalt testade koden; övriga 671
runtimefiler är oförändrade. Bygget kördes utan nätverk och verifierades
med filhashar och compileall. Tidigare 554 offlineprov och 14 browserprov
återanvänds för oförändrad, hashkontrollerad kod.

Befintligt gemensamt driftlås hölls under backup och appbyte. Ingen nylig
menytrafik och två låga CPU-mätningar krävdes före byte. Båda SQLite-
databaserna säkerhetskopierades online med efterföljande quick_check och
DELETE-journalläge på kopiorna. Produktionens databaser återställdes inte.
286 tidigare planrevisioner och 97 privata tillstånd är bevarade enligt
radhashar vid bytet. Aktiva prismanifest är byteidentiska före och efter.

Endast appens image och BUILD_ID ändrades i compose. Scheduler, proxy,
volymer, Windowsuppgift och insamlingsscheman bevarades. Ingen ny
prisinsamling startades och inga observationstider ändrades.

## Driftkontroll

Lund (22350) och Malmö (21120) svarar HTTP 200 med den nya BUILD_ID:n.
Publicerat och laddat Lund-manifest överensstämmer. Samtliga fem
obligatoriska Lundkällor är FRESH, kvalificerade och laddade.
Malmö har befintlig åldersvarning AGING; betan är ändå ready enligt
basprisernas gällande behåll-tills-ersatta-policy. Reläets kvitto är
oförändrat och ingen leverans väntar. Befintliga källvarningar kvarstår.

## Publika API-prov

Fyra flöden kördes mot beta.smako.nu med separata nya verifieringsidentiteter,
19 priskontexter inom 3 km från 22225, högst två inköpsställen och tillåtna
näringsuppskattningar. Varje prov gav HTTP 201, kassakontroll PASS,
avstämda summor, noll okända mängder och identisk sparad GET vid två
återläsningar. Inga nya browserprov gjordes under aktiveringen.

| Prov | Tid | Inköpssumma | Resultat |
| --- | --- | --- | --- |
| Fem middagar, fyra portioner, protein minst 40 g | 79.59 s | 1116.15 kr | PASS |
| Fem middagar med samtidiga makro-/energigränser | 22.64 s | 1116.15 kr | PASS |
| Frukost och mellanmål, två portioner, viktgränser | 75.95 s | 64.06 kr | PASS |
| Tre veganska middagar, protein minst 20 g | 17.02 s | 473.17 kr | PASS |

Proteinprovet ger uppskattningsvis 43,19–53,51 g protein per portion.
Makroprovet använder protein 40–90 g, kolhydrater 10–130 g, fett 1–60 g och
högst 1000 kcal per portion. Frukosten väger uppskattningsvis 300 g och
mellanmålet 140 g, inom gränserna 100–600 respektive 100–400 g.
Närings-/viktvärdenas status är ESTIMATED och bevaras i sparade planer.
Summorna avser hela inköpta förpackningar. Svarstiderna är enstaka API-prov,
inte normala svarstidsgarantier; första provet gjordes efter omstart.

Det första viktprovet skapade också en giltig plan men verifieringsskriptet
krävde felaktigt exakt samma mellanmål/vikt som i det lokala provet.
Betan valde ett annat tillåtet mellanmål. Skriptets kontroll rättades till
de begärda viktgränserna och flödet verifierades igen med sparade återläsningar.
Därför skapade verifieringen sammanlagt fem planer och fem privata tillstånd.

Slutkontroll 16:41:44 UTC: samtliga 286 tidigare planrevisioner och 97 privata
tillstånd är fortfarande hashverifierat bevarade. Totalt 291 revisioner och
102 tillstånd efter proven. Noll nya OOM-händelser eller containeromstarter.
Se [kompakt evidens](EVIDENCE.json).

## Kvarstående begränsningar

Aktiveringen innebär inte fullständigt underlag för alla kombinationer.
Mjölkallergi och krav på enbart ekologiska animalier kan fortfarande stoppas
av saknade produktuppgifter. Tillagad vikt saknas fortsatt för varma recept
utan belagt tillagningsutbyte. Ekoandelsvalet var långsamt i det tidigare
lokala provet (459 s) och har inte körts på nytt som liveprov här.

## Evidens och återgång

Skyddade lokala underlag: `.local/recipe-nutrition-extras/activation/`.
Serverevidens: `/opt/smako/evidence/recipe-nutrition-extras-7e402a7/`,
inklusive `backup-20261015T162938Z/`, filhashar, compose före/efter och
`compose-wrapper.before`. Fulla provsvar lagras endast lokalt.

Vid återgång: verifiera att aktuell compose fortfarande motsvarar denna
release, ta befintligt driftlås och invänta ledig app. Återställ sparad
wrapper atomiskt och kör endast app med
`up -d --no-deps --no-build --pull never app`. Behåll aktuella datavolymer
och databaser. Kontrollera readiness, manifest och befintliga revisioner.
Återgång återinför de tidigare näringsluckorna.

## Backup arkiverad 2026-10-19

Den avslutade releasebackupen finns nu förlustfritt komprimerad i
`/opt/smako/evidence/recipe-nutrition-extras-7e402a7/backup-20261015T162938Z.tar.gz`.
Alla filhashar, ägare och behörigheter verifierades före borttagning av den
okomprimerade kopian. Privat inventarium, kvitto och återställningsanvisning
finns intill arkivet. Se [lagringsjournalen](../../storage-maintenance.md).
Aktiva data och denna releases historiska verifieringsresultat är oförändrade.
