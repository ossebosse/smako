# Varor och butikspriser från kvitton (2026-11-24)

Aktiverad 2026-11-24 16:35 UTC. App **app-1032ff8a39be-31d9e0ed**
(`sha256:d4fc44f19193…`), bas `app-d3bad43b756e-ccf6ce69`
(`sha256:dcd9f39cacbb…`). Scheduler orörd (`source-ops-00e68d1aa835`).

## Innehåll

Main `bff1442`. Releasegren `release/receipt-items-20261124` = `d3bad43` +
samma ändring (`1032ff8`), eftersom main efter `d3bad43` också har appfiler
som bara levererats till schedulern (Primat-klassning m.m.); de kräver nyare
grocery-kod och följer med nästa samlade appsläpp.

Ägarbeslut 2026-11-24 (`member_rewards.py`, `receipt_prices.py`,
`user_pricing.py`, `price_universe_runtime.py`, `personal_planner.py`):

- Osäkra och saknade kvittorader ger poäng först när streckkoden skannas.
- Skannad vara som butikens Smako-lista saknar blir tillfällig vara i
  butiken; skannad Smako-vara till annat pris lär Smako butikens pris.
  Två olika medlemmar med minst 7 dagar emellan gör den fast (+3 poäng);
  60 dagar utan köp och den glöms. Inställningar och lista (ta bort) på
  admin-fliken Matplanering.
- Planeringen använder det direkt, utan nytt prisbygge: lägre butikspris
  som daterad kampanj "enligt kvitto", bekräftat högre pris ersätter
  ordinarie, ny vara med streckkod som finns i en annan butik planeras som
  kopia av den varan (dess deklaration och allergenkontroll). En version i
  plandatabasen ingår i prisdatans färskhetsidentitet. Okända streckkoder
  planeras inte ännu.
- En liten mus hämtar varje vara Smako tar emot i kvittodialogen.
- Nya tabeller i plandatabasen (`member_store_items`,
  `member_store_item_sightings`, `member_store_items_version`), additiva.

## Prov

- Lokalt: `test_receipt_store_items_20261124.py` (17) och uppdaterade
  kvittotester; ~100 planerar-/pristestfiler med `not live and not slow`.
  Fem fel (`test_personal_offer_path.py` ×3, `test_official_offer_facts.py`,
  `test_recipe_resolution.py`) är identiska utan ändringen.
- Kandidatbild: 13 granskade filer ändrade + 1 ny, 1 435 runtimefiler
  oförändrade; importprov utan nätverk; funktionsprov i kandidatbilden mot
  temporär databas (kvitto → butikspris 24,95 kr planeras direkt).
- Efter aktivering: `/ready` Lund och Malmö ready med nytt BUILD_ID och
  336 h prisålder; ny `mine.js` serveras; `/api/member/store-items` kräver
  inloggning; inga fel i apploggen. Lagringsretention complete före och efter.

## Avvikelser under aktiveringen

- Bygget kördes först via SSH som bröts efter 3 min; bilden blev klar men
  byggarens kontroller hann inte köras. Den avbrutna underlagsmappen ligger
  kvar som `/opt/smako/evidence/app-1032ff8a39be-31d9e0ed.interrupted-20261124T1550Z`.
  Samma bygg- och aktiveringsarbetare (`scripts/beta_release_workers`) kördes
  sedan frånkopplat på servern med `setsid nohup`; kvitton i
  `.local/beta-release-receipts-20261124/`.
- Första aktiveringen (≈16:00 UTC) rullades tillbaka av skriptet:
  `environment changed beyond build`. Appens 14-dygnsprisålder från 2026-11-23
  (`price-age-14d-20261123.json`) var bara satt på containern, inte i
  `/opt/smako/compose`, så återställningen gav 48 h. Med ägarens ja lades
  overriden permanent i `/opt/smako/compose` (kopia
  `/opt/smako/compose.before-price-age-20261124`) och appen återskapades
  (336 h verifierat) före ny aktivering.
- Andra försöket stoppade på planerar-CPU (uppvärmning efter omstart), inget
  byte; tredje försöket aktiverade.

## Kvar

- `/opt/smako/compose` beskriver fortfarande en äldre scheduler (BUILD_ID
  `08c1374…`, 48 h) än den som kör (`source-ops-00e68d1aa835` med sina
  overrides). Återskapa inte schedulern via wrappern innan dess overrides
  lagts in där.
- Okända streckkoder till morgonens prisbygge; ett fullt planprov med
  butikskopia genom kassan.

## Återställning

`/opt/smako/compose` utan `-f /opt/smako/overrides/app-1032ff8a39be-31d9e0ed.json`
ger `app-d3bad43b756e-ccf6ce69` (behåll price-age-raden).
