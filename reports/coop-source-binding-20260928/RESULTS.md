# Resultat: återställd aktuell Coop-källa

**PASS i isolerad femkällorskandidat. Ingen produktionsaktivering.**

Grundorsak och förväntade/observerade identitetsfält finns i [ANALYSIS.md](ANALYSIS.md). Två nya villkorsfält avvisades av det stängda schemat och gav missvisande identitetsfel. Nu bevaras villkoren och spärras per berörd rad. Providerns explicita versionslista omfattar v3 och den granskade v4; okända versioner är fortsatt spärrade.

## Faktisk insamling och serving

Ny verklig insamling: 28 september 2026, 11:01 UTC, från varje upptäckt butiks egen officiella sida/API-bindning. Kommuninventeringen har tio inside och 768 outside, inga unknown: nio strukturerade Coop/Stora Coop samt separat X:-tra. Inventeringen återanvändes inom giltig kontrolltid. Inga erbjudanden kopierades mellan butiker.

| Butik (ID) | Källa/ledger | Godkänd kampanjperiod | Hämtade varianter | Källbindning/schema | Radgodkända | Karantän | Serving före → efter | Nästa rebuild/omstart |
|---|---|---|---:|---|---:|---:|---:|---:|
| Coop Veberöd (1158) | [API 106595](https://external.api.coop.se/dke/offers/sorting-groups/106595) | 2026-09-28–2026-10-04 | 397 | PASS | 39 | 358 | 0 → 39 | 39 / 39 |
| Stora Coop Lund (2696) | [API 105760](https://external.api.coop.se/dke/offers/sorting-groups/105760) | 2026-09-21–2026-10-04, 2026-09-28–2026-10-04 | 363 | PASS | 68 | 295 | 6 → 68 | 68 / 68 |
| Coop Vildgåsen Lund (3656) | [API 216523](https://external.api.coop.se/dke/offers/sorting-groups/216523) | 2026-09-28–2026-10-04 | 98 | PASS | 11 | 87 | 0 → 11 | 11 / 11 |
| Coop Värpinge Lund (3659) | [API 216526](https://external.api.coop.se/dke/offers/sorting-groups/216526) | 2026-09-28–2026-10-04 | 315 | PASS | 32 | 283 | 0 → 32 | 32 / 32 |
| Coop Mårtenstorget (3813) | [API 106430](https://external.api.coop.se/dke/offers/sorting-groups/106430) | 2026-09-28–2026-10-04 | 397 | PASS | 39 | 358 | 0 → 39 | 39 / 39 |
| Coop Klostergården (3820) | [API 106435](https://external.api.coop.se/dke/offers/sorting-groups/106435) | 2026-09-28–2026-10-04 | 315 | PASS | 32 | 283 | 0 → 32 | 32 / 32 |
| Coop Trollebergsvägen (3837) | [API 106444](https://external.api.coop.se/dke/offers/sorting-groups/106444) | 2026-09-28–2026-10-04 | 98 | PASS | 11 | 87 | 0 → 11 | 11 / 11 |
| Coop Flöjtvägen (3839) | [API 106445](https://external.api.coop.se/dke/offers/sorting-groups/106445) | 2026-09-28–2026-10-04 | 98 | PASS | 11 | 87 | 0 → 11 | 11 / 11 |
| Coop Genarp (3841) | [API 106447](https://external.api.coop.se/dke/offers/sorting-groups/106447) | 2026-09-28–2026-10-04 | 98 | PASS | 11 | 87 | 0 → 11 | 11 / 11 |

Totalt 2179 hämtade butiksbundna variantrader, 254 godkända och 1925 karantän. Det är butiksposter, inte lika många unika varor. Ingen av de nio butikerna har noll godkända poster. Detta är fortsatt partiell erbjudandetäckning, inte godkänt fullsortiment. Befintlig full-snapshotstatus och kvalitetsgräns har inte skrivits om.

X:-tra Skansvägen (3658) är separat: befintligt officiellt PDF-underlag observerat 28 september 07:03 UTC, kampanj 28 september–4 oktober, sex serving-poster före/efter/rebuild/omstart. Ingen ny X:-tra-hämtning gjordes; dess källa, felstatus och nästa hämtning hålls separat.

Den faktiska appinstansen ökade från 41755 till 42003 poster. Samtliga fem obligatoriska onlinekontexters poster, source-snapshots och observationer är exakt oförändrade. Coop Online Syd är fortfarande online_fulfillment/online_price, inte en fysisk Coop-butik.

## Publicering, omstart och negativt prov

- Ordinarie import/rebuild/publicering/reload med slutlig image: exit 0, 248.01 s; reload verifierad mot faktisk appinstans.
- Nästa ordinarie rebuild med uttryckligt injicerat frivilligt Coop-jobbfel: exit 0, 246.87 s; reload verifierad mot faktisk appinstans.
- Andra bygget behöll exakt samma produkthash och godkända Coop-källreferenser. Felet redovisas i ordinarie refreshrapport som failed_optional_source/ConnectionError. Fungerande obligatorisk bas och fortfarande giltiga Coop-erbjudanden finns kvar.
- Två faktiska appstarter vid HTTP-proven läste samma serving-innehåll. Samtliga nya Coop-kontexter och antal verifierades efter omstart; noll utgångna fysiska Coop-erbjudanden fanns i serving.
- Dessa lokala rebuild-/HTTP-prov kördes utan extern nätåtkomst. Orelaterade optional-hämtningar var uttryckligen uppskjutna i testharnessen, men deras ordinarie provider/import var kvar. Inga basobservationer föryngrades.

## Kampanjövergång med verkliga sparade utgåvor

Replay av 27 september respektive de faktiskt nyhämtade svaren 28 september, med respektive oförändrade observationstider. Detta är inte en ny hämtning. För alla nio butiker skiljer sig dokumenthash och nytt radgodkännande. Ett gammalt dokumentgodkännande återanvänds inte för den nya utgåvan.

| Butik | Godkända i sparad 27/9-utgåva | Utgångna vid 28/9 | Godkända i ny utgåva | Utgångna som följde med |
|---|---:|---:|---:|---:|
| Coop Veberöd | 68 | 68 | 39 | 0 |
| Stora Coop Lund | 71 | 65 | 68 | 0 |
| Coop Vildgåsen Lund | 44 | 44 | 11 | 0 |
| Coop Värpinge Lund | 55 | 55 | 32 | 0 |
| Coop Mårtenstorget | 68 | 68 | 39 | 0 |
| Coop Klostergården | 55 | 55 | 32 | 0 |
| Coop Trollebergsvägen | 44 | 44 | 11 | 0 |
| Coop Flöjtvägen | 44 | 44 | 11 | 0 |
| Coop Genarp | 44 | 44 | 11 | 0 |

De sex tidigare fortsatt giltiga Stora Coop-raderna hade period 21 september–4 oktober. Aktuella butiksbundna källsvar och godkännanden prövas på nytt; tidigare bevis tillåter inte andra butiker eller nya villkor.

## Planering, checkout/audit och sparning

Ordinarie /api/plans på samma godkända femkällorsprofil: 15 måltider/20 portioner, samma näringskrav, butikstak och ursprungliga val. Original/Plus-kopian och exact/estimated prövas separat. Ingen receptändring eller höjd sökbudget.

| Profil | HTTP | Kostnad kr | Köpstatus | Checkout/audit | Sparad GET / omstart |
|---|---:|---:|---|---|---|
| original-exact | 201 | 445.29 | VERIFIED | PASS, totals reconciled | PASS / PASS |
| original-estimated | 201 | 445.29 | VERIFIED | PASS, totals reconciled | PASS / PASS |
| plus-exact | 201 | 445.29 | VERIFIED | PASS, totals reconciled | PASS / PASS |
| plus-estimated | 201 | 445.29 | VERIFIED | PASS, totals reconciled | PASS / PASS |

Fulla requests, produktval, antal förpackningar, nutrition och audit finns i `results/http-results.json` och `profile-summary.json`. Planeringens nätåtkomst var spärrad. Godkänd källimport betyder inte att varje erbjudande har nödvändiga närings-/receptmappningar eller blir valt av planeraren.

## Kvarstående hinder och releasebeslut

Ingen extern uppgift behövs för den rättade schema-/versionskonflikten. Nya krav på andra inköp och prissteg är fortfarande uttryckligt spärrade eftersom den befintliga köpmodellen inte hanterar dem. Övriga redan kända radblockerare är kvar; exempelvis pant kräver uttryckligt belopp och rörliga paket kräver faktiskt köpunderlag. Dessa får inte göras köpbara genom antaganden.

`lund-own-five-base-20260928-v1` kvarstår som verifierad alternativ releasekandidat med detta isolerade Coop-tillägg. Originalpolicyn och dess Primat-hinder är oförändrade. ICA/Hemköps kommunluckor, äldre PurchaseTerms-kopplingar, Lidls/Willys nya kampanjbortfall, Malmö-publicering och historisk Lidl-fixture är separata, fortsatt olösta uppgifter. Tidigare femmiddagsmilstolpe påverkas inte.

Slutregression: 152 tester PASS, Ruff och compileall PASS; 589 imagefiler hashverifierade, beroendekontroll PASS. Lund och annan kommun täcks av befintliga retained-data-regressioner; ingen ny Malmö-publicering påstås. Tidigare kandidatens 337 bevisfiler är hashverifierat oförändrade.

Isolerad image: `smako-coop-source-binding:20260928-v4`, `sha256:fdaf9c4a61e97aecef0d86c2e8feb2424e2d475287dece0bac03ab9f800a4781`. Produktion står kvar på `/opt/smako/releases/price-recovery-lund-20260914a`. Privat basbackup, tidigare kandidat och samtliga mellanresultat finns kvar. Ingen ändring av produktionspolicy, schemaläggning, Windows, databasstruktur, Primat, användarval eller betalt API.
