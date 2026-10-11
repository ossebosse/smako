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

Aktivering och verklig menyverifiering dokumenteras separat när genomförda.
