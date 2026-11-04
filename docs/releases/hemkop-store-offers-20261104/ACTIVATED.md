# Hemköps butikskampanjer: schemagranskning och daglig hämtning (scheduler)

Aktiverad 2026-11-04 17:16 UTC. Ägarbeslut samma dag: aktivera direkt.

## Orsak

Klubbdag 2026-11-04 (22 endagskampanjer hos Hemköp Lund Karhögstorg, t.ex.
Norrloumi 20 kr, ord. 34,07) syntes inte i Smako. Två fel:

1. Butikskampanjernas snapshots avvisades av schemagrinden vid varje körning
   sedan 2026-10-14 (Lund) och 2026-10-11 (Malmö): `hasPickingBaseStore` i
   butikslistan samt växlande null för `price`, `priceNoUnit`, `redeemLimit`,
   `promotionRedeemLimit`. `approved_store_ids` var därför tomt; inga
   butikskampanjer nådde prisunderlaget.
2. `mon_thu` hämtade butikskampanjer bara mån/tors 03:17; en endags klubbdag
   (onsdag) hinner aldrig med.

## Ändring

Kod `db8710ad08fee18dc45a3f7403c9ede78b5010c4` (main). Fyra filer, byte-
identiska bas mot aktiv scheduler `source-ops-8a53beb80e43`:

- `grocery_data/app/connectors/hemkop/schema_review.py`
- `grocery_data/app/services/collector.py`
- `grocery_data/app/services/campaign_refresh_policy.py`
- `grocery_data/app/services/hemkop_municipal_job.py`

Butikskampanjer hämtas dagligen 05:17 (tre timmars omförsöksfönster).
Butiksinventering och baskataloger behåller mån/tors.

## Driftsättning

- Paket `build_source_patch.py` (bas 8a53beb80e43, parent 874152d), sha256
  `e71259499a76dadb41d60286c7ee39b4140afb82fe7ae75322d349c765314526`.
- Bygge utan nätverk: `sha256:3337142a2143bac672baa5ff4823ae6669c57154d6f1afc0e294994b39afb2b2`,
  tagg `smako-scheduler:source-ops-db8710ad08fe`.
- Offlineprov i kandidaten: filhashar, import, schemagranskning av de
  verkliga diffarna (godkänd). Bildkonfiguration oförändrad.
- Override `/opt/smako/overrides/source-ops-db8710ad08fe.json` (endast
  scheduler). Compose-config före/efter skiljer bara i image och BUILD_ID.
- `up -d --no-deps scheduler`; appen orörd. Ingen databas ändrad; senaste
  dagliga backup 20261104T014703Z.
- Plan efter byte: alla sju Hemköpbutiker (Lund 4123/4224/4517, Malmö
  4114/4199/4212/4247) `daily_offer_collection` 2026-11-05 04:17 UTC.

Tester: ~300 berörda tester gröna (schemagranskning, kampanjschema,
Hemköp-, Coop-, Lidl-, Willys-, City Gross-wiring, prisschema).

## Återställning

Kör samma compose-kommando utan den nya override-filen (bild
`sha256:35b377c8…`, BUILD_ID `source-ops-8a53beb80e43`).

## Kvar att verifiera

Första dagliga körningen 2026-11-05: att snapshots promoveras
(`approved_store_ids` ej tomt) och att butikskampanjer publiceras.
