# Butiker och täckning – separat femkällorspolicy

Poster nedan lästes ur den publicerade serving-instansen. Butiksposter är inte ett antal unika erbjudanden. Baskatalogernas kanal är online; ingen rad omklassas till hyllpris. Samtliga listade prisposter var datumgiltiga 28 september 2026; detta betyder inte att alla har komplett köpform, näring eller receptkvalificering.

| Butik | Kontext/kanal | Serverade poster | Täckning | Äldsta observation UTC |
|---|---|---:|---|---|
| Coop Online Syd | online_fulfillment | 11481 | full_catalog | 2026-09-27T15:17:27.749113+00:00 |
| Stora Coop Lund | physical_store | 6 | offers_only | 2026-09-27T16:15:48.764237+00:00 |
| X:-Tra Skansvägen | physical_store | 6 | offers_only | 2026-09-28T07:03:48.577047+00:00 |
| Hemköp Lund Brunnshög | online_store | 5100 | full_catalog | 2026-09-27T16:03:01.101148+00:00 |
| Hemköp Lund Karhögstorg | online_store | 6163 | full_catalog | 2026-09-27T15:47:48.320867+00:00 |
| ICA Kvantum Malmborgs Tuna | physical_store | 33 | offers_only | 2026-09-28T07:02:58.967475+00:00 |
| ICA Kvantum Brunnshög | physical_store | 21 | offers_only | 2026-09-28T07:02:54.660827+00:00 |
| ICA Nära Satelliten | physical_store | 17 | offers_only | 2026-09-28T07:03:02.925127+00:00 |
| Maxi ICA Stormarknad Gunnesbo, Lund | physical_store | 25 | offers_only | 2026-09-28T07:03:11.049099+00:00 |
| ICA Nära Söderlivs, Lund | physical_store | 19 | offers_only | 2026-09-28T07:03:04.938728+00:00 |
| ICA Supermarket Fäladstorget | physical_store | 24 | offers_only | 2026-09-28T07:03:07.090738+00:00 |
| ICA Supermarket Linero Torg | physical_store | 22 | offers_only | 2026-09-28T07:03:08.960740+00:00 |
| ICA Nära Jägaren, Lund | physical_store | 16 | offers_only | 2026-09-28T07:03:01.246500+00:00 |
| ICA Kvantum Malmborgs Clemenstorget | physical_store | 34 | offers_only | 2026-09-28T07:02:57.174513+00:00 |
| Lidl Åkerlund och Rausings väg 1 | physical_store | 3 | offers_only | 2026-09-28T07:03:57.413940+00:00 |
| Lidl Magistratsvägen 6 | physical_store | 3 | offers_only | 2026-09-28T07:03:57.413940+00:00 |
| Willys Lund | online_store | 10165 | full_catalog | 2026-09-27T15:13:51.988516+00:00 |
| Willys Lund Nova | online_store | 8603 | full_catalog | 2026-09-27T15:26:20.132876+00:00 |
| Willys Hemma Lund Stortorget | physical_store | 14 | offers_only | 2026-09-28T07:04:26.504487+00:00 |

Fem obligatoriska baskataloger ger 41 512 tillgängliga prisposter av 41 704 importerade basrader (192 uttryckligen slut i lager). 243 datumgiltiga butikserbjudandeposter ger totalt 41 755 poster i 19 priskontexter. Dessa siffror räknar butiker separat, inte unika produkter/kampanjer.

## Begränsningar och bortfall

- Clemenstorget: 34 kvalificerade fysiska erbjudandeposter, ingen full Primat-bas. Gunnesbo: 25 egna fysiska erbjudandeposter; dess Primat-katalog ingår inte i alternativet.
- Coop Online Syd är online_fulfillment/online_price. Kommunens fysiska Coop-flöden är separata. Den verkliga 28 september-hämtningen av strukturerade fysiska flöden avvisades med `Coop shared structured store/source evidence mismatch`. Tidigare godkända och fortfarande giltiga sex poster från Stora Coop Lund respektive X:-tra Skansvägen finns kvar. Värpinge, Veberöd, Trollebergsvägen, Flöjtvägen, Klostergården, Mårtenstorget, Genarp och Vildgåsen Lund har inga datumgiltiga bidrag i denna publicering. Ingen utgången förra-vecka-post har gjorts aktuell.
- Lidl: 3 kvalificerade kandidater av 402 per butik, 399 i karantän per butik. De två butikskopiorna innebär 3 unika kvalificerade produkt-ID:n, inte 6 nya erbjudanden. Orsaker på produktnivå finns i källrapporternas qualification/decisions.
- Willys Hemma Stortorget: 14 kvalificerade produkt-/grupprader ur 34 annonskandidater, 20 karantänrader. Variantuppdelningar och öppna grupper gör att rader inte är samma nämnare som annonser. Orsaker inkluderar konflikt mellan webbvisare/PDF-text, öppna kritiska villkor och otillräcklig produkt-/prisbindning.
- City Gross: verifierat noll kommunbutiker i Lund; ingen grannkommun lånas.
- ICA använder ännu ortsurval Lund, inte full gemensam kommuninventering. Hemköp använder de tidigare godkända två baskontexterna, inte ny kommuninventering. Kommunjobb för Coop/X:-tra, Willys, Lidl och City Gross använder beständigt 1281 och officiell inventering.
- Äldre köptermer i kedjeimporterna kvarstår. Legacy-rader utan PurchaseTerms räknas inte här automatiskt som exakta köp; ordinarie PersonalPlanner och checkout måste kvalificera vald rad.

Fullständiga kontext-ID:n, observationer, snapshot-ID:n och köpformskapabilitet: `results/actual-serving-*.json`. Officiella butikskällor, även upptäckta/okända/ej bidragande butiker: `results/source-coverage.json`. Verkliga hämtningsutfall: första refresh-rapporten; senare markerade felinjektioner är inte nya nätinsamlingar.
