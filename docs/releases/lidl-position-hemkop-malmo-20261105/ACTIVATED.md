# Lidl-butikspositioner från JSON-LD och Hemköp Malmö-kampanjer (scheduler)

Aktiverad 2026-11-05 10:45 UTC. Ägarbeslut samma dag: rätta och aktivera direkt.

## Orsak

- **Lidl**: Nattens butiksinventering 2026-11-05 04:00 UTC fick
  `official_position_missing` för alla 213 butiker. Lidl.se har tagit bort
  Bing-länken som Smako läste position ur. Ingen butik valdes inom Lund,
  `approved` tömdes och Lidls kampanjer föll ur prisunderlaget.
- **Hemköp Malmö**: Butikskampanjer för 4114/4199/4212 avvisades av
  schemagrinden (`displayVolume`, `promotionProductOrdinaryComparePriceUnit`
  växlar null/sträng). 4247 (exakt 60 kampanjer) avslutas med en tom-lista-sida
  i stället för `null`.

## Ändring

Kod `b25b76b412ed` (main). Fyra filer, bas byte-identisk med aktiv scheduler
`source-ops-102e92b59547`:

- `grocery_data/app/connectors/lidl/models.py`: position från sidans
  schema.org `GeoCoordinates`; finns båda källorna måste de stämma, motstridiga
  JSON-LD-positioner avvisas.
- `grocery_data/app/connectors/hemkop/schema_review.py`: två fält till i
  granskade nullbara fält (endast null + string).
- `grocery_data/app/connectors/hemkop/models.py`,
  `grocery_data/app/connectors/hemkop/physical_offers.py`: kampanjkällan
  tillåter tom lista på avslutande sida (katalogen kräver fortfarande `null`).

## Driftsättning och prov

- Paket sha256 `5e0b928bf0324a5766078ebcf30fe2a94162a0e77413168ae2e9ba23a8b67acc`,
  bygge utan nätverk `sha256:3fc9aaac745c35d90103fac1d6dbb8b9fdaeb8392c2004d0ad0db6b89f6fc404`.
- Offlineprov i kandidaten: filhashar, position ur verklig butikssida
  (Magistratsvägen 6: 55.7205, 13.20542), Malmö-diffen godkänd.
- Lidl-, Hemköp- och kampanjschematester gröna.
- Compose-config före/efter: endast image och BUILD_ID; inget jobb pågick;
  appen orörd.

## Engångskörning Lidl Lund

`mon_thu` tillåter ingen dagtidsinventering. Engångskörning 10:54 UTC under
ordinarie driftlås (väntade på lagringsunderhållet), med
`PRICE_COLLECTION_CADENCE=legacy` endast för den processen och
`next_inventory_check` satt till nu. Backup av tillståndet:
`lidl-municipal/1281/source-state.before-manual-20261105T105426.json`.
Resultat: 213/213 butiker med position, 0163 och 0303 valda, 71 godkända
kampanjrader per butik. Publicering via ordinarie demand-refresh.
Cron och schema oförändrade. Malmö-Lidl och Hemköp Malmö tas av ordinarie
körningar (Hemköp dagligen 05:17).

## Återställning

Compose utan `/opt/smako/overrides/source-ops-b25b76b412ed.json`
(bild `sha256:c6458570…`, BUILD_ID `source-ops-102e92b59547`).
