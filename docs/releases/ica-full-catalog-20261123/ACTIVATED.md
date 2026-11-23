# Hela ICA-katalogen från Primat och 14 dygns prisålder

Aktiverad 2026-11-23 (scheduler 15:40 och 15:5x UTC, app ~16:00 UTC).
Ägarbeslut samma dag: alla ICA-butiker som Primat har med full katalog, hel
hämtning utspridd över dagar inom gratisnivån; prisåldern 48 h ersätts med
14 dygn för alla kedjor. "Ja, slå ihop och aktivera" gavs i chatten.

## Ändring (main `ca08017`)

- `e24cc5f` Insamlare: `primat_ica_catalog.py`, `deploy/scripts/run_primat_ica_catalog.py`,
  cron `37 07 * * *` (`PRIMAT_ICA_CATALOG_ENABLED=true`).
- `d6c1ea7` En prisåldersinställning: `MAX_PRICE_AGE_HOURS`/`PRICE_AGE_WARNING_HOURS`
  i stället för hårdkodade 48 h (jobb, hårda stopp, diagnostik, FreshnessPolicy).
- `eae3836` Katalogläge (`PRIMAT_ICA_CATALOG_SOURCE=true`): när en runda är klar
  och varje butik har ≥ 1 000 matvaror med förpackning ersätter katalogen de
  148 sökningarna.
- `ca08017` Katalogfilen ligger under `PRICE_UNIVERSE_CACHE_ROOT` (persistent
  montering); första körningen föll på att `/srv/app/var` inte är skrivbar.

## Driftsättning

- Scheduler `source-ops-ca08017afde0` (`sha256:7dd64e6dccd3…`), via
  `source-ops-eae38366c507` (`sha256:1c1437173dd1…`). Paket med
  `build_source_patch.py --primat-refresh`, runtimefiler verifierade mot
  pinnade bilder, bygge utan nätverk, filhashar och import kontrollerade.
  Override `/opt/smako/overrides/source-ops-ca08017afde0.json`: image, BUILD_ID,
  `MAX_PRICE_AGE_HOURS=336`, `PRICE_AGE_WARNING_HOURS=240`,
  `OWN_GROCERY_MAX_AGE_HOURS=336`, `PRIMAT_ICA_CATALOG_ENABLED=true`,
  `PRIMAT_ICA_CATALOG_SOURCE=true`. Compose-config före/efter skiljer bara i dessa.
- App: samma bild (`app-d3bad43b756e-ccf6ce69`), override
  `/opt/smako/overrides/price-age-14d-20261123.json` med de tre åldersvärdena;
  återskapad, `healthy`, `/ready` visar 240/336 h. Appkoden för
  statusvyer följer med nästa ordinarie appsläpp.

## Prov efter byte

Första katalogsteget (manuellt, 2026-11-23 ~15:55 UTC): 5 butiker
(Gunnesbo; Västra Hamnen, Mobilia, Caroli, Maxi Malmö), kvot 9 554 använt före,
budget 9 946, använt 9 851: erbjudanden 5 551, katalog 2 800 (14 sidor),
förpackning 1 500 uppslag (alla hittade).

## Samma dag, före detta

- Disk 98 % → 74 % (105 oanvända images, 171 stoppade testcontainrar
  från oktober borttagna med ägarens ja); backup lyckades igen 11:11 UTC.
- Rättning `a632476` (begränsad Primat-wrapper tog inte `limit`), scheduler
  `source-ops-a63247600922` 10:04 UTC; manuell Primat-körning gav aktiva
  prisunderlag Gunnesbo 4 223, Västra Hamnen 3 261, Caroli 2 920 Primat-varor.

## Kvar

- Följa rundan (≈ 10–14 dygn första gången, mån/tors tar sökningarna ~13 000
  rader före kl. 07:37); katalogläget slår på av sig självt när rundan är klar.
- Mobilia och Maxi Malmö samlas in men används inte i priser förrän
  identitetsflödet verifierat dem (postnummer 21120 returnerar dem inte).
- `/ready` visar `degraded`: äldsta baspris i Lund är från 2026-09-23 (fanns före).

## Återställning

Scheduler: compose utan `source-ops-ca08017afde0.json` (och
`source-ops-eae38366c507.json`) ger `source-ops-a63247600922` med 48 h.
App: compose utan `price-age-14d-20261123.json`.
