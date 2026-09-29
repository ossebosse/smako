# Coop/X:-tra: ordinarie refresh/rebuild – separat releaseunderlag

Kontrollerat 2026-09-22 14:41:15 Europe/Stockholm. **Tekniskt verifierat i isolerad driftmiljö; inget aktiverat i produktion.** Ingen Windows- eller aktiv schemaändring. Ingen bildmodell eller betald API. Den väntande ICA-leveransen, Primat och användardata är bevarade.

## Beslut och exakt omfattning

Redo för separat aktiveringsbeslut för den partiella kommunstyrda Coop/Stora Coop-integrationen. Slutkodens ordinarie byggväg ger **493 aktuella butik–variantposter i nio Lundbutiker**. X:-tra kan aktiveras separat: den verkliga textinsamlingen gav **9 aktuella poster**, totalt 502 när tillägget var på. Full reklambladstäckning eller komplett sortiment påstås inte.

Inga kvarstående kodblockerare identifierades i dessa kontroller. Operatörsbeslut och ny färskhetskontroll krävs före skarp aktivering. Testvolymen innehåller även tydligt märkta felfall och får **inte kopieras till produktion**; ett rent första ordinarie jobb skapar riktiga beständiga källreferenser.

Verifierad image: `smako-coop-candidate:refresh-integration-20260922`, `sha256:73371776b99a8b240435e2d575473d746bda5f694d1b3a6a485273be2ff12924`. 285 paketerade moduler hashkontrollerade mot slutkoden. Samma befintliga startväg, `/opt/ica-venv` och UID 10001 verifierade; Playwright 1.58.0. Appkoden ligger i imagen. Endast privata data och testharness monterades. Två CPU och 5 GiB minnesgräns; ingen flerdagarsstabilitet påstås.

## Ändrad ordinarie väg

`deploy/scripts/run_daily_refresh.py` → befintligt operationslås → `python -m grocery_data daily-refresh` → `coop_offer_job.run_offer_job` för förfallna kommunbutiker → befintlig collector/validering/OWN → `_build_production_price_universe` läser godkända beständiga källreferenser → befintlig PriceUniverse-byggare/publicering → skyddad runtime-reload. Alla senare byggen läser källreferenserna automatiskt; inga manuella Coop-byggargument behövs.

`source_plan` är en lokal förfallokontroll utan prisanrop. Kommunval, källversioner, kampanjtillämplighet och publiceringsstatus ingår i lokal byggversion. Giltigt underlag hämtas inte om vid basrebuild. En separat publicerings-/reloadretry behövs även om Coop-innehållet är oförändrat.

Beständig standardroot: `/srv/app/var/grocery/coop-municipal-offers` i befintlig grocery-volym. `config.json` sparar kommun, flaggor och city-bindning; `<kommunkod>/source-state.json` sparar hela inventeringen, val, felstatus, godkända relativa OWN-referenser med hash, nästa uppdatering, byggkvitto, publicering och reload. `attempts/` bevarar immutable råunderlag och snapshots. Befintlig demand-status ligger i `DEMAND_REFRESH_STATE_PATH`. Ingen ny prisdatabasarkitektur eller parallell prissättare.

Hämtning, källgodkännande, publicering och reload har separata tidsfält. Misslyckad hämtning behåller endast fortfarande giltiga godkända referenser. Validerat tomt flöde återkallar just den butikens tidigare referenser; felaktigt/saknat/otydligt flöde är inte tomt. Alla försök använder befintligt operationslås och atomiska tillståndsbyten.

## Uppmätta cykler

| Prov | Coop + eventuell X:-tra i publicerat PU | Jobbexit | Körtid | Health/ready |
|---|---:|---:|---:|---|
| A: verklig insamling, första publicering | 493 | 0 | 376.8 s | 200/200 |
| B: ny lokal rebuild, ingen Coop-hämtning | 493 | 0 | 337.5 s | 200/200 |
| B2: verkligt uppdaterad Primat-bas, kvarvarande Coop | 493 | 0 | 370.7 s | 200/200 |
| C: ny process, endast beständigt kommun-/källtillstånd | 493 | 0 | 309.9 s | 200/200 |
| D: injicerat transportfel för en förfallen butik | 493 | 0 | 284.7 s | 200/200 |
| Verklig återhämtning från samma butik | 493 | 0 | 290.8 s | 200/200 |
| X:-tra på, verklig butiksspecifik PDF-hämtning | 502 | 0 | 286.8 s | 200/200 |
| X:-tra av, Coop kvar | 493 | 0 | 283.8 s | 200/200 |
| Injicerat reloadfel, separat väntestatus | 493 | 2 | 268.2 s | 200/200 |
| Slutkod: verifierat nollsvar (muterat testunderlag) | 438 | 0 | 282.7 s | 200/200 |
| Slutkod: kampanjutgång (explicit köpdatum i Coop-provider) | 0 | 0 | 271.0 s | 200/200 |
| Slutkod: verklig återhämtning efter nollsvar/utgångsprov | 493 | 0 | 289.4 s | 200/200 |
| Slutkod: nästa rebuild, reload och 15/20 | 493 | 0 | 334.9 s | 200/200 |

Första nio-butiksinsamlingen och basuppdateringen gjorde verkliga nätanrop. Omstart återanvände samma beständiga testvolym, utan initial inventeringsfil eller kommunflaggor. Pris, fysisk butik, paket, kampanjvillkor och proveniens jämfördes mellan A/B/basrebuild, inte bara HTTP-status eller antal.

Felfallet på Värpinge var en explicit transportinjektion. Nollsvarsprovet muterade ett bevarat verkligt källsvar och körde normal parser, collector, OWN, rebuild och reload; det är **inte** ett påstående om ett verkligt tomt flöde. Endast Värpinges 55 poster försvann: 493 → 438. Ny verklig hämtning återställde kvalificerat underlag. Produkterna är återobserverade, inte 55 nya produktidentiteter.

Utgångsprovet satte en uttrycklig framtida **inköpsdag i Coop-providern**, efter de bevarade kampanjernas slut. Samma ordinarie jobb publicerade då noll Coop-poster med giltig bas kvar. Baskällornas färskhet använde verklig klocka. Separat checkoutprov avvisade det utgångna gruppköpet. Inga observationstider flyttades. Verkliga kampanjbyten över flera dagar har inte observerats. Färska källor ersatte äldre underlag; utgångna Stora Coop-avtal återanvändes inte som fallback. Antalen avser de faktiska nya källsvaren.

Reloadfelet gav exit 2 och `publication_or_reload_pending`, med oförändrad senaste lyckade reload och 15 minuters retry. Slutprovet kvitterade exakt publicerat PU-ID och återställde `reloaded`. Publiceringsvalidering avvisade en injicerad ogiltig artefakt utan att ändra privat aktivt manifest. Giltig rollback och omstartens återläsning passerade; rollback med +48 h testklocka avvisades.

## Slutkodens planering och prisbevis

Ny ordinarie rebuild efter återhämtningen följdes av verkligt HTTP-planeringsanrop mot privat app och separat testidentitet: HTTP 201, **536.27 kr**, 50.288 s. Oförändrad 15/20-profil, fryst receptpool, 40/30/20-krav, inga medlemskap och högst två inköpsställen. 332 interna basket-audits passerade; sparad plan var identisk efter återläsning. Full meny, valda produkter, butikskombination och köp finns i `server-results/lifecycle/cycle-final-plan.json`. Ingen ny besparing påstås.

Representativt Coop-gruppköp verifierades separat med riktig produkt/matchning/checkout/audit: Kärnvetemjöl, **2 × 2 kg för 26 kr**, utan fabricerat ordinarie restpris. Godkända produkter tvingades inte in i vinnande meny. Prisroller, medlemskap, köpgränser och tidigare näringsrättningar behölls. Näringsreferensversion och samtliga 15 valda näringskontroller är identiska med B2. Katalogens samlade facts_version skiljer sig mellan insamlingscyklerna; detta är inte en ny parad besparingsjämförelse. Båda versionerna finns i `facts-continuity.json`.

Slutligt privat PU: `price-universe:3a22bf2ddd7a90abe38832e804565cf995f468f862bdbd730864a6f4c7909ce1`. Produktionsmanifestets SHA-256 är fortsatt `ff76c9f6bc5c54b778872870b6655050cc74e25e386b62a081663676dfe5b429`; produktionens image och health/ready kontrollerades separat i `live-health.json`.

## Nästa uppdatering och färskhet vid beslutet

Alla tider nedan är Europe/Stockholm. Det är **testkandidatens beräknade tider**, inte ett installerat produktionsschema.

| Baskälla | Verklig äldsta observation | Nästa kontroll/hämtning | Hårt stopp | Skäl |
|---|---|---|---|---|
| coop | 2026-09-21 03:17:55 | 2026-09-22 14:41:05 | 2026-09-23 03:17:55 | base_35h_deadline_or_campaign_coalescing |
| hemkop | 2026-09-22 03:55:34 | 2026-09-23 14:55:34 | 2026-09-24 03:55:34 | base_35h_deadline_or_campaign_coalescing |
| willys | 2026-09-22 01:31:28 | 2026-09-23 12:31:28 | 2026-09-24 01:31:28 | local_relay_35h_deadline |
| primat | 2026-09-22 13:38:03 | 2026-09-24 00:22:45 | 2026-09-24 13:38:03 | base_35h_deadline_or_campaign_coalescing |

En redan passerad tid betyder förfallet arbete för nästa ordinarie behovskontroll. Baspriserna har kvar varning vid 36 h och stopp vid 48 h. Fulla källsnapshotar användes; den begränsade lokala sökprojektionen byggdes aldrig om till bas. Primat uppdaterades med verklig transport under B2; andra fortfarande giltiga baskällors ursprungliga observationer bevarades.

| Kommunbutik | Senaste lyckade verkliga observation | Nästa källkontroll | Skäl/status |
|---|---|---|---|
| Coop Värpinge Lund (3659) | 2026-09-22 14:29:29 | 2026-09-24 01:29:29 | coop_35h_source_check_before_48h_stop |
| Stora Coop Lund (2696) | 2026-09-22 13:22:45 | 2026-09-24 00:22:45 | coop_35h_source_check_before_48h_stop |
| Coop Veberöd (1158) | 2026-09-22 13:22:51 | 2026-09-24 00:22:51 | coop_35h_source_check_before_48h_stop |
| Coop Trollebergsvägen (3837) | 2026-09-22 13:22:56 | 2026-09-24 00:22:56 | coop_35h_source_check_before_48h_stop |
| Coop Flöjtvägen (3839) | 2026-09-22 13:23:01 | 2026-09-24 00:23:01 | coop_35h_source_check_before_48h_stop |
| Coop Klostergården (3820) | 2026-09-22 13:23:05 | 2026-09-24 00:23:05 | coop_35h_source_check_before_48h_stop |
| Coop Mårtenstorget (3813) | 2026-09-22 13:23:10 | 2026-09-24 00:23:10 | coop_35h_source_check_before_48h_stop |
| Coop Genarp (3841) | 2026-09-22 13:23:15 | 2026-09-24 00:23:15 | coop_35h_source_check_before_48h_stop |
| Coop Vildgåsen Lund (3656) | 2026-09-22 13:23:19 | 2026-09-24 00:23:19 | coop_35h_source_check_before_48h_stop |
| X:-Tra Skansvägen (3658) | 2026-09-22 13:59:41 | 2026-09-23 23:00:00 | Avstängd; sparad tid gäller vid återaktivering. campaign_boundary_or_72h_source_check |

Coop/X:-tra behåller sin befintliga 35 h kontroll före 36/48 h-gränserna, eller tidigare kampanjgräns. Detta är ingen daglig fullhämtning. Misslyckad källa får 15 minuters första retry och begränsad backoff; källans giltighet förlängs aldrig. Kampanjstart/-slut utlöser lokal ombyggnad, medan checkout också kontrollerar köpdatum oberoende av scheduler. Nästa inventeringskontroll: 2026-09-25 13:22:35. X:-tra avstängt innebär inga X:-tra-prisanrop.

Verifierat rollbackunderlag: `5f631fd9cb6549c40d683e77e056d16a74f6dd8b7159846cf4f18884325889a7`. Äldsta basobservation 2026-09-21 03:17:55; hårt stopp 2026-09-23 03:17:55. Dessa tider måste kontrolleras på nytt vid aktivering; artefaktens byggtid är inte dess prisobservation.

## Tester, evidens och nästa operatörssteg

202 unika berörda regressioner passerade, Ruff och compileall passerade. Se `verification.json`, `code-closure.json`, `scheduler-bootstrap.json`, `compose-check.json` och `server-results/lifecycle/final-checks.json`. Schedulerbootstrap skapade endast privat containerkonfiguration; ingen cron-daemon eller produktionsuppgift startades. Malmö och X:-tra-formatluckor från tidigare leverans kvarstår separat; ingen ny kommuninventering gjordes.

1. Besluta separat om Coop-aktivering och eventuell X:-tra-opt-in. Bekräfta image-SHA, beständig volym och körkonto. Använd det förberedda `deploy/coop-runtime.override.yaml` med befintlig Compose och `--no-build`; det har ännu inte tillämpats.
2. Hämta förfallna baskällor genom deras befintliga godkända transport och säkerställ färskt kodkompatibelt rollbackunderlag precis före aktivering. Återanvänd inte denna rapports gamla tidsstämplar som nytt underlag.
3. Låt rent ordinarie refresh-jobb skapa municipal state i produktionsvolymen, validera, publicera och kvittera reload. Ingen manuell tillskottslista eller särskilt byggskript behövs. Behåll användarnas profiler och områdes-/butiksval.
4. Samordna bild/tagg/flaggor och befintlig lätt demand-tick med den väntande ICA-releasen som **separat operatörssteg**. Denna leverans ändrar inte ICA-aktivering, Windows-uppgift eller aktiva scheman. Kontrollera health/ready och ett separat sparat/återläst testanrop efter ett framtida godkänt skarpt steg.

Exakta genomförda kommandon och privata kataloger finns i `COMMANDS.md`. Inget av ovanstående operatörssteg har utförts i produktion.
