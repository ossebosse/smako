# Receptens varukopplingar aktiverade

Aktiveringen verifierades 2026-10-15 12:34:32 UTC (14:34 svensk tid), efter
användarens instruktion ”Aktivera det”. Kodcommit `07af5ac`, gren
`fix/recipe-product-links`.

Appens BUILD_ID är `recipe-product-links-app-07af5ac`, image
`sha256:5f2558bb1443ec15d07a638655453fd1f51ac9c51bf6ef7a5e45015304e992ae`.
Faktaprojektionen är `retained-catalog-facts-v10-supplier-package-link`.
Se [orsak och lokal verifiering](../../../reports/recipe-product-links-20261015.md).

## Avgränsat versionsbyte

Sju berörda filer transplanterades med entydiga sammanhang på den verkliga
aktiva appbilden, `sha256:7ccbbfd7fe2f2edec89bd2a8a50fbbf2ff5791ff2ab7891f6ff5f759cd9c376a`.
De sju resulterande filerna är byteidentiska med den lokalt testade koden;
övriga 676 runtimefiler är oförändrade. Bygget kördes utan nätverk.
Compose ändrar endast appens image och BUILD_ID. Scheduler, proxy, volymer,
Windowsuppgift och insamlingsscheman bevaras.

Det gemensamma driftlåset hölls under backup och byte. Första förkontrollen
stoppade före bytet på grund av nyliga menyförsök. Metadata visade att försöken
avslutats med 422; nästa försök krävde två minuter utan menytrafik samt två
låga CPU-mätningar. Inga pågående användarberäkningar avbröts.

Båda SQLite-databaserna säkerhetskopierades med online-backup och verifierades
med `quick_check`. Backupfilerna slutfördes i DELETE-journalläge.
De 284 befintliga planrevisionerna och 95 privata tillstånden bevarades enligt
radhashar. Aktiva prismanifest är byteidentiska före och efter bytet.
Ingen äldre databas återställdes, ingen prisinsamling startades och inga
observationsdatum ändrades.

## Drift och API-prov

Lund (`/ready?postal_code=22350`) och Malmö (`21120`) svarar HTTP 200 med
den nya BUILD_ID:n. Publicerat och laddat Lund-manifest överensstämmer;
samtliga fem obligatoriska källor är FRESH, kvalificerade och laddade.
Windowsreläet är fortsatt aktiverat utan väntande leverans. Befintliga
källvarningar ändras inte av denna apprelease.

Kundpostnummer 22225 ger 19 priskontexter inom 3 km. Prov använder enbart
dessa som tillåtna butiker, två portioner, högst två inköpsställen och inga
näringsgränser. Varje flöde använder en separat ny verifieringsidentitet.
Det är API-prov mot den publika betan, inte nya webbläsarprov.

| Prov | Resultat | Tid | Ingrediensbehov | Inköpssumma |
| --- | --- | --- | --- | --- |
| Färsbiffar med citronpotatis, tzatziki och tomatsallad | HTTP 201, audit PASS | 134,47 s | 14 | 288,90 kr |
| Fem grekiska middagar | HTTP 201, audit PASS | 45,34 s | 27 | 568,08 kr |

Det första provet använder Hemköp Lund Karhögstorg och Willys Lund. Femdagars-
provet använder endast Willys Lund och innehåller bland annat kikärtor,
vita bönor och citronjuice. Båda har noll okända mängder, avstämda summor och
identisk sparad GET vid två återläsningar. Summorna avser hela inköpta
förpackningar, inte portionskostnad. Första provet inkluderar uppbyggnad av
cache efter omstart och är ingen mätning av normal svarstid.

Slutkontroll 12:39:24 UTC bekräftar att samtliga tidigare radhashar är
bevarade även efter proven. Totalt finns 286 planrevisioner och 97 privata
tillstånd: proven tillförde två planer och två verifieringsidentiteter.
Noll nya OOM-händelser och noll automatiska containeromstarter.

Resultat och slutlig tillståndskontroll finns i [EVIDENCE.json](EVIDENCE.json).
Tillverkarens gramuppgifter för citronjuicens näring har fortfarande inte
omvandlats till ml utan verifierad densitet. Andra användarval kan därför
fortfarande kräva mer underlag.

## Evidens och återgång

Lokala skyddade underlag finns i `.local/recipe-product-links/activation/`.
Serverevidens finns i `/opt/smako/evidence/recipe-product-links-07af5ac/`,
inklusive backup `backup-20261015T122602Z/`, filhashar, compose före/efter och
`compose-wrapper.before`. Fulla provsvar ligger endast lokalt.

Vid återgång: verifiera att aktuell compose fortfarande motsvarar denna
release, ta befintligt driftlås och invänta ledig app. Återställ den sparade
wrappern atomiskt och kör endast app med
`up -d --no-deps --no-build --pull never app`. Behåll aktuella datavolymer och
databaser. Kontrollera readiness, manifest och tidigare planrevisioner.
Den föregående appbilden återinför de saknade ingredienskopplingarna.
