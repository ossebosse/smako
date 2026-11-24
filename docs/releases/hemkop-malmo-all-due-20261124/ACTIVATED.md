# Hemköp: alla förfallna butiker hämtas varje insamlingsnatt

Aktiverad 2026-11-24 08:07 UTC (scheduler). Ägarens "why is Hemköp in Malmö
inactivated? Shouldnt be" / "Merge and activate".

## Orsak

Hemköp Malmö var inte avstängt: alla fyra butiker (4114, 4199, 4212, 4247)
var valbara och deras butikserbjudanden hämtades samma morgon. Men
`run_daily_refresh.py` begränsade varje körning till den äldsta förfallna
butiken (`[:1]`), och första försöket i Malmö misslyckades varje natt
(ConnectorFetchError 02:44 UTC, lyckat omförsök cirka 05:00). Resultat: en
Malmö-katalog per insamlingsnatt, så varje butik uppdaterades bara ungefär
var 14:e dag. Elinegård 4212 (senast 2026-11-09) passerade 14-dagarsgränsen
och visades som inaktuell.

## Ändring (main `00e68d1`)

- `deploy/scripts/run_daily_refresh.py`: en körning tar alla förfallna
  Hemköp-butiker, äldst först.
- `backend/app/services/store_operations.py`: admintexten anger de
  konfigurerade gränserna i dagar i stället för "36/48 timmar". Appkod;
  följer med nästa appsläpp.

## Driftsättning

- Scheduler `source-ops-00e68d1aa835` (`sha256:0b7ba7bf59cf…`) från
  `build_source_patch.py`. Bas `source-ops-0292f98cfcaf`, runtimefilens
  hash verifierad (`74c65aab…`), diff mot runtime endast ändringen ovan.
- Bygge utan nätverk, patchhash och import kontrollerade i imagen.
- Compose-diff endast image och BUILD_ID, inget jobb igång vid byte.
  /ready 200.
- Effekt från torsdag 2026-11-26 03:17.

## Återställning

Compose utan `/opt/smako/overrides/source-ops-00e68d1aa835.json`.
