# Postnummer och måltidsfönster

Utveckling på `feature/postcode-meal-dialogs`, från aktiverade Mina val.

## Beteende

- Mina val börjar med verkligt postnummer. Lokalt GISCO-underlag kopplar detta
  till referenspunkt och kommun; det interna prisområdets byggnyckel visas inte.
- Närmaste kartlagda butiks-/upphämtningsposition behöver ligga inom 10 km.
  Okänt postnummer, okända positioner, uteblivna priser och utanför täckning
  hanteras separat. Radiegränser använder oavrundat avstånd.
- Butiksval: 1–5 km, kartlagda inköpsställen i kommunen eller rullbar krysslista.
  Även kommuner med fler än 40 inköpsställen kan väljas (Malmö: 63).
  Måltidsval låses upp efter bekräftat, icke-tomt butiksval. Ändringar låser
  åter måltidssteget; sena svar från tidigare postnummer får inte ta över.
- Middag/frukost/mellanmål har Fördelning, Portionsvikt och Näringsvärden som
  separata dialoger. Min/max delar spår med två dragbara, tangentbordsstyrda
  handtag. Null/standard, noll och tidigare decimalgränser bevaras.
- Fördelningen delar måltidsantalets budget. Vid minskat antal ryms fördelningen
  genom att begränsa i visningsordning. Kostval utesluter otillåtna kategorier.
- Receptstil kvar: väljer receptmotor/bibliotek, inte enbart ingrediensantal.

## Geografiska begränsningar

Avstånd är fågelväg från en ungefärlig postnummerreferenspunkt, inte adress eller
körväg. Flera svenska postnummer har samma ortspunkt i GISCO:s underlag.
UI anger detta före butiksvalet och visar källa/licens. Detta är inte en garanti
för att en butik ligger inom radien från användarens faktiska bostad.

Butiker kommer från befintligt publicerat kommununderlag. Radien filtrerar det
området; ingen ny kommunkombinerad prisartefakt skapas. Om hemkommunen inte
finns men en kartlagd butik ligger inom 10 km används närmaste kartlagda område,
vilket namnges i UI; kommunvalet är då avaktiverat. Gränsöverskridande korgar
mellan flera publicerade kommunartefakter är inte införda här.

Svenskt utdrag (18 916 postnummer) ur GISCO 2025 ligger i
`backend/app/data/postal/se-gisco-2025.json`. Ursprunglig URL, SHA-256,
hämtningstid, kolumner och CC-BY-SA 4.0-attribution ingår. Återskapa med
`scripts/import_postal_locations.py INPUT.zip OUTPUT.json`. Originalets
kommun-ID används, aldrig gissning från ortnamn eller postnummerprefix.
Källdataarkivet är lokal, ignorerad arbetsdata och distribueras inte i appen.

## Verifiering

- 14 testfall (12 Chromium/WebKit, 2 API-kontrakt): huvudval, sparade krav, tillval, dialoger,
  tangentbord, faktisk dragning av båda handtagen, gemensam fördelningsbudget,
  butiksradie, kommun, manuellt val, tomt val och invalidation.
- 7 geografiska/kommunala testfall: verkliga lokala postnummer, negativa svar,
  9,999/10,001-km-gräns, lager kontra upphämtning, isolerade kommunartefakter.
- 45 befintliga personliga planerings-/köplägestestfall.
- Ruff, compileall och JavaScript-syntaxkontroller.
- Mobilbilder granskade vid 390 px; inga horisontella överflöden.

## Aktiverad på betan

Aktiverad 2026-10-11 18:24:07 UTC (20:24 svensk tid). Appcommit
`93c4f9ac4505a1cf8f839f8928ee6e965ee32e35`, BUILD_ID
`postcode-meals-93c4f9ac4505`. [Aktiveringsbevis](ACTIVATED.json).

Bild: `sha256:81501a07c22e49f1e889f89a6f1f0d3cdd1879172c64fe30b5498ad10be938b2`.
Paket: `6a7200626eae4515548dd1defc44a2e79dffe8760b06ad35c0562b75065e42f1`.
Tio appfiler som delta på exakt föregående betabild. Befintliga basfilhashar
matchade testad Git-bas; nytillagda filer saknades i basen som förväntat.

66 riktade lokala testfall passerar. Den isolerade kandidaten använde båda
kommunernas register och publicerade underlag. Chromium skapade en middag
för två portioner med valt Willys-underlag i Lund, räknade om och läste
identisk sparad plan (97,2 s inklusive kontroller). Checkout-audit och
summakontroll passerade. WebKit verifierade hela Malmövalet (63 inköpsställen),
reglage, tillval och mobilbredd. Okänt postnummer och Stockholm utanför
aktuell täckning gav separata, korrekta svar. Fem statiska filer hashverifierades.

På publika `https://beta.smako.nu/personal#choices` passerade samma nya
planflöde med checkout-audit och identisk återläsning (57,4 s). WebKit/Malmö-
kontrollen och samtliga fem filhashar passerade också; inga sidfel observerades.
Detta är automatiserad mobilvy, inte ett fysiskt iPhone-prov.

Aktiveringen väntade på befintligt driftlås, kontrollerade lugn planering,
tog SQLite-backup och bytte endast appbild och BUILD_ID. Samtliga 257 tidigare
planrevisioner och 83 privata tillstånd hashbevarades före publik testplan.
Mountar, övrig miljö, prismanifest, scheduler, proxy och övriga containrar
bevarades. Windowsuppgiften ändrades inte. Driftkontrollen efter aktivering
visar samma publicerade/laddade Lund-manifest, fem obligatoriska källor
publicerade/laddade och `/ready` för nya BUILD_ID. Lund och Malmö har aktiva
underlag med äldsta användbara priser cirka 23,7 respektive 22,7 timmar gamla.

Serverbevis och skyddad backup:
`/opt/smako/evidence/postcode-meals-93c4f9ac4505`.
Lokala testbevis: `.local/postal-final/` samt tidigare `.local/postal-choices/`.
Testcontainrarna är stoppade, SSH-tunneln stängd och driftlåset släppt. Ingen
aktiveringsväntare återstår.

## Återgång

Tidigare bild:
`sha256:8040a97b586b310a48b260012746798eefd87d8d945feee08d1bcf585f9978b5`.
Den tidigare Compose-wrappern finns i serverbevisets `compose-wrapper.before`.
Återgång ska ske under samma driftlås och behålla senaste databasen. Återställ
inte den äldre databasbackupen som normal appåtergång.
