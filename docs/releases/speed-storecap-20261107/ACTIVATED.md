# Snabbare planering, "alla valda butiker" och City Gross-namn aktiverat

Aktiverad **2026-11-07 ca 08:20 UTC** på https://beta.smako.nu.
Main `e63953efb720`, app **app-e63953efb720-6d2ce025** (bild `sha256:1b78d0c11cc0…`,
bas `sha256:842d11663897…`). Schedulern orörd. Ägaren godkände aktiveringen
2026-11-07 06:53 ("Activate it"). Bygget väntade tills morgonens prisinsamling
(tre varv, ca 05:17–08:00 UTC) hade släppt driftlåset.

## Ändring (tio filer)

- Butikstak upp till alla valda butiker ("Handla i alla valda butiker",
  `store_cap: all_selected`) med exakt butiksmängdssökning.
- Snabbare prissättning: paketform per produkt återanvänds, och bara varje
  butiks vinnande offert byggs fullt.
- Menyer vars lägsta möjliga pris redan överstiger bästa funna hoppas över (exakt).
- Produktinventariet hashas en gång per prisdata.
- Receptkvalificering återanvänds mellan planer med samma förutsättningar
  (process-lokal LRU, 128 sammanhang).
- Planer med fler än 30 valda butiker får 90 s i stället för 60 s.
- City Gross-butiker visas som "City Gross <ort>". Effekt först när
  prisuniversumet byggs med den nya koden; det byggs i schedulern, som inte
  är uppdaterad i denna release.

Mätningar (samma prisdata, isolerade containrar): identiska korgar i alla
34 fall utan tidsgräns; Malmö hela kommunen 178–244 s → 72–83 s; Lund hela
kommunen 78–82 s → 35–41 s. Med 60 s gav tidigare beta inget resultat i 3 av
5 Malmö-kommunfall. Se `docs/reviews/quote-speed-20261106/REPORT.md`.

## Verifiering

- Endast appen bytt, enda miljöändring BUILD_ID, prismanifest och mountar
  bevarade. Bevarat: 336 planversioner, 150 privata tillstånd, 2 konton,
  1 session. Backup `/srv/smako/backups/20261107T081316Z`.
- `/ready` 22350 och 21120: ready, `app-e63953efb720-6d2ce025`.
- Publikt prov, ny gäst, 32 butiker i Lund, högst två: Stora Coop Lund och
  Willys Lund, 168,37 kr, VERIFIED, sparad (plan 3d718941…), 69 s.
