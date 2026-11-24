# Coop Online Syd: platshållarenhet på fast förpackning

Aktiverad 2026-11-24 06:22 UTC (scheduler). Ägarens "Look into why Coop
ain't fetched anymore" / "And fix it" / "Yes, merge and activate".

## Orsak

Coop Online Syd (730400) har sedan 2026-11-05 publicerat `salesUnit: "0"` för
en vara (Hushållspapper Strong 8-pack, kategori 141448713). Parsern
behandlade det som schemaändring och kastade hela katalogen (≈11 400 varor)
vid varje körning: 9 `schema_changed`-fel i `parser_failures`, 7 retryfel,
Lunds och Malmös Coop-baspriser från 2026-11-05 (433 h) behölls som äldre bas.
Hämtningen fungerade (826 anrop, 0 HTTP-fel).

## Ändring (main `0292f98`)

`online_catalog_parser.py`: platshållarenhet (`"0"` eller tom) på en vara med
känd fast förpackning (ej ungefärlig vikt) = styckvara. Annan okänd enhet
fallerar som förut. Tester i `test_coop_online_catalog_parser.py`.

## Driftsättning och återställning av data

- Scheduler `source-ops-0292f98cfcaf` (`sha256:e8166ea119a9…`), paket
  `build_source_patch.py` (byggt i molnet), runtimefil verifierad, bygge utan
  nätverk, compose-diff endast image/BUILD_ID, inget jobb igång vid byte.
- Prov före byte: nattens sparade råhämtning (`e46937a2…`, 824 dokument,
  2026-11-23 03:45–04:12 UTC) gav med ny parser 11 456 varor, fullständig
  genomgång (12 607 rapporterade = 12 607 mottagna rader).
- `grocery_data replay --chain coop --snapshot-id e46937a2… --promote`:
  ny snapshot `ee442866b8c4…`, 11 456 varor, 0 karantän, healthy, aktiv.
  Inga nya anrop till Coop. Prisunderlagen publiceras om av ordinarie runner.

## Övriga källor (kontroll samma morgon)

- Inga andra parserfel sedan 2026-11-10.
- Willys Lund: lokalt relä, levereras onsdagar (senast 19/11).
- Willys Malmö: reläet har bara levererat Lund sedan 2026-11-05 (paketen
  halverades). Orsak på ägarens dator (`D:\smako-local-relay`), ej utredd.
- Hemköp 4212 och 4114: hoppas över i konfigurationen
  (`HEMKOP_STORE_EXTERNAL_IDS`); deras äldre underlag åldras ut.

## Återställning

Compose utan `/opt/smako/overrides/source-ops-0292f98cfcaf.json`.
