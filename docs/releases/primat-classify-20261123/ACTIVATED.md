# Primat-varor klassas som insamlade varor

Aktiverad 2026-11-23 18:28 UTC (scheduler). Ägarens "Build that" och
"Yes, merge and activate".

## Orsak

Test mot betan samma kväll (`POST /api/plan`, gäst, Lund): blandad plan valde
Willys + Coop; bara Gunnesbo gav ingen plan – alla 1 685 recept stoppades i
produktkvalificering. Alla Primat-varor hade `semantic_confidence=low` och
omappad `canonical_food` (Lund 3 454, Malmö 4 896), eftersom Primat-rader inte
går genom klassningen som Smakos egen insamling gör
(`ProductNormalizer` → `OwnGroceryPriceProvider._backend_semantics`).

## Ändring (main `25cbf48`)

- `grocery_data.app.normalization.food_identity(name, category_path)`:
  samma regler som insamlingen, publikt.
- `backend/app/services/collected_semantics.py`: identitet → backendens
  matnamn och roll, husdjursmat avvisas.
- `PrimatPriceProvider._parse_product` sätter `canonical_food`,
  `product_role`, `product_form`, `semantic_confidence` därifrån.
- Planeraren säger "Vi hittar inte varor till recepten i de valda butikerna
  … Välj fler butiker." när inga varor kvalificerar, i stället för att
  hänvisa till näringsvärden (appkod; följer med nästa appsläpp).

Mätt på dagens cacher: Lund 1 127 av 3 454 klassade (48 livsmedel), 48
avvisade; Malmö 1 639 av 4 896, 57 avvisade.

## Driftsättning

Scheduler `source-ops-25cbf488ca83` (`sha256:737d6462e91d…`), paket
`build_source_patch.py --primat-refresh` (byggt i molnet eftersom
datorns sessionsdisk var full), runtimefiler verifierade, bygge utan nätverk,
compose-diff endast image/BUILD_ID, inget jobb igång. Kandidatprov:
ICA Rapsolja → `cooking_oil`, `high`.

Effekt när cacherna skrivs om: schemalagd Primat-uppdatering 2026-11-24 01:10.
Planprov schemalagt 2026-11-24 08:50.

## Återställning

Compose utan `/opt/smako/overrides/source-ops-25cbf488ca83.json`.
