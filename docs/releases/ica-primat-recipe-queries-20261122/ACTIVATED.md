# Fler Primat-sökningar för ICA (scheduler)

Aktiverad 2026-11-22 21:07 UTC. Ägarbeslut samma kväll: gratisnivån hos
Primat, bredare ICA-täckning ("Gunnesbo över två nätter"; se avvikelse nedan).

## Orsak

ICA och Lidl kom sällan med i inköpen. Gunnesbo (Lund) och Västra Hamnen och
Caroli (Malmö) har ordinarie priser bara från 48 riktade Primat-sökningar;
många vanliga receptvaror saknades (ägarens plan: ICA 13 av 31 ingredienser).

## Ändring

Kod `7ec9a6767a22` (main):
- `backend/app/services/primat_recipe_queries.py` (ny): 100 vanliga
  receptingredienser som de 48 sökningarna inte täcker.
- `backend/app/services/production_primat_refresh.py`: 48 sökningar med
  limit 100 + 100 med limit 50, 1,1 s mellan anrop: 149 anrop per stad.
- `backend/app/providers/primat.py`: `search_products(..., limit=...)`.
- `grocery_data/__main__.py`: planens anropstak räknas från listan.
- `scripts/build_source_patch.py`: `--primat-refresh` tar med de tre
  backendfilerna.

Avvikelse från "två nätter": Primats katalograder (`/prices`) saknar
förpackningsstorlek, och det slutna prisunderlaget kräver en
observationstid per stad och högst 48 h ålder. Riktade sökningar ger färdiga
varor med storlek och jämförpris inom en natt. Uppskattat ~13 000 rader per
natt för båda städerna, under gratisnivåns 20 000.

Liveprov 2026-11-22 (Gunnesbo, 15 ingredienser som saknades i ägarens plan):
13 fick pris med förpackning; salladslök och rödlök saknas fortfarande.

## Driftsättning och prov

- Paket `build_source_patch.py --primat-refresh` (bas `e6d4ceaca5bc`,
  parent `d1e8a87`), sha256
  `7bf9f4b9f9c55f7d87652ea4692ce45c74d60ede93d84067ab1780287895b883`,
  runtimefilerna verifierade byte för byte mot pinnad bild.
- Bygge utan nätverk: `sha256:192cf3ae7f4aef2c675a84539e966813f915a9e1ac14f3b11cfcc3a9e0e1bf61`,
  tagg `smako-scheduler:source-ops-7ec9a6767a22`. Bildkonfiguration lika
  med `IMAGE-CONFIG.json`; filhashar, import och 148 sökningar/149 anrop
  kontrollerade i kandidaten.
- Override `/opt/smako/overrides/source-ops-7ec9a6767a22.json` (endast
  scheduler). Filistan = appens lista + schedulerns egna overrides
  (`db8710ad08fe`, `102e92b59547`, `b25b76b412ed`, `e6d4ceaca5bc`) + ny.
  Compose-config före/efter skiljer bara i image och BUILD_ID.
- Inget jobb pågick; `up -d --no-deps scheduler`; appen orörd. Ingen databas
  ändrad; senaste backup `20261122T191719Z`.
- Torrkörning Lund + Malmö efter byte: `maximum_requests_per_city` 149,
  Primat `planned_from_verified_contexts`.

Tester: berörda gröna (Primat-refresh, insamlingsschema, frusen cache,
managed refresh, källpatch-lineage); hela sviten utan live/slow grön utom
ett WebKit-webbläsarprov som saknar webbläsare i molnmiljön.

## Återställning

Compose utan `/opt/smako/overrides/source-ops-7ec9a6767a22.json`
(bild `sha256:790ca46a…`, BUILD_ID `source-ops-e6d4ceaca5bc`).

## Kvar att verifiera

Första körningen mån/tors 03:17: Primat-cachen för Lund och Malmö skrivs med
148 sökningar, radåtgång under dygnskvoten, och fler ICA-varor i Gunnesbo,
Västra Hamnen och Caroli.
