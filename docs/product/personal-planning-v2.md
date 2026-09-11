# Smako V2 – personlig planering

2026-09-11. Ingång: https://beta.smako.nu/personal. Release `personal-v2-qualified-20260911b`.
[Aktuell rapport: kvalificerade eko-/näringsfall](../../reports/smako-qualified-product-data-20260911.md) · [tidigare V2-rapport/OIDC](../../reports/smako-personal-planning-v2-gaps-20260911.md).
Ingen blanketacceptans av allergier, kontosynk eller hela katalogens eko-/närings-/viktstöd.

## Gemensamt kontrakt och inventering

Receptbehov + uttryckliga extravaror − allokerat verkligt skafferi, därefter hela
förpackningar, villkorade priser och ett butikstak 1/2/3 för hela korgen. Samma
medlemskap/prisversion gäller allt. Icke-livsmedel påverkar köp och butikstak.
Lager, reservation, framtida köp, överskott och förbrukning är separata.

Återanvänt: befintlig generator, MenuOptimizer, BasketOptimizer, BasketCalculator,
ProductSearchIndex, scanner, HttpOnly gästägare, PlanStore och raderings-/restore-ledger.
Ingen parallell prismotor eller ny extern tjänst. Källadaptern använder exakt
produkt/kontext/snapshot och verifierad sparad filhash; PriceUniverse ändras inte.
R3/R7/R8 har inte omdesignats. Kall prestanda, Willys-task/relay, ICA/Primat-
normalisering, källinsamling och ICA OWN-research är fortsatt avgränsade.

## Tre återupptagbara delsteg

1. **Levererat/testat:** gemensam korg, extravaror/noll recept, receptändring även
   efter köp/förbrukning, oföränderlig historik och generisk kampanjgruppsmotor.
   Livekampanjer återupptas först när kompletta källavtal finns.
2. **Gästflödet levererat/testat:** privat profil/skafferi, atomiska reservationer,
   idempotenta inköp/förbrukning och privat radering/restore. OIDC är konkret
   dokumenterat/offline-testat; operatörskonfiguration och verklig kontosynk återstår.
3. **Regler + partiell produktionsdata:** måltidstyper/fördelning, ekoandel och
   per-portionsmakron använder verkliga källfält där de finns. Ofullständiga
   allergen-, animalie-, skafferinärings- och tillagningsuppgifter ger DATA_BLOCKED.

## R1–R9 acceptansmatris

| Krav | Status | Kod-/testevidens och kvarvarande hinder |
|---|---|---|
| R1 Smak/allergier: svensk granskad tolkning, mjukt/hårt, alla val/byten, privat sparande | PARTIAL | `personal_policy.py`, `personal_source_facts.py`, `test_personal_planning_v2.py`, `test_personal_source_facts.py`. 7 991 Coop-deklarationer kopplade; positiva konflikter blockeras. Noll kompletta allergenregister i godkänt underlag → hårda krav utan komplett bevis DATA_BLOCKED, även produktbyte/skafferi/exakta extras. |
| R2 Skafferi: CRUD/sök/scanner, enheter, konto/gäst, saldo/reservation/köp/förbrukning/överskott | PARTIAL | `personal_store.py`, `account.py`, bokförings-/OIDC-/restoretester. Gäst, delvis förbrukning, samtidighet, äldre bokföring och radering verifierade. Generell Authlib OIDC med state/nonce/PKCE testad offline. Tre OIDC-värden och livekontoacceptans återstår; e-post ger inget ägarskap. Befintlig katalogkoppling krävs även för exakt skafferitilldelning. |
| R3 Fördelning: tydliga kategorier, en huvudproteinkälla, giltiga summor/fria delval | IMPLEMENTED_AND_VERIFIED | Befintliga `MealSettings`, `distribution_ok`, `optimize_slots`; regression av kandidatval och konkreta motsägelsefel. Vegetarisk/vegansk/fisk/kyckling/övrigt kött kvar tydligt i UI. |
| R4 Eko: kostnadsandel efter rabatt över alla matköp och separat animaliskt krav | PARTIAL | `personal_source_facts.py`, `personal_planner.py`, `test_personal_qualified_facts.py`: 25 % eko-middag 55,73 kr; separat animaliskt eko-frukost 50,34 kr; båda verklig HTTPS. Kostnad efter rabatt, mat-extras med, skafferi/icke-mat utanför; noll nya matinköp uttryckligt. Verifierat eko kräver inte animalieklassning; annars krävs källstöd. Okänd status aldrig positiv. Begränsat urval; full animalieklassning och vissa sammansatta/avrunna produkter kvarstår. |
| R5 Portion/näring: tillagad ätbar vikt, makron per portion, källa/enhet/grund, omkontroll | PARTIAL | `personal_nutrition.py`, `personal_source_facts.py`, kandidat-/slutkontroll och 20 kvalificeringstester. Verklig kall frukost med protein/kolhydrater/fett/energi och eko 30 % kostar 81,96 kr, 3/3 källbelagda behov. Exakt skafferi räknas i näring. Tillagad vikt, varma/avrunna beredningar utan förlustgrund, enhetsomräkning och generiskt skafferi förblir DATA_BLOCKED. 78 fulla deklarationer i samma 449-raders pool, 75 möjliga som såld vara före recept-/enhetskontroll. |
| R6 Recept: öppna/redigera/ta bort/fylla/byta efter köp, hel korg/reservation, historik vid fel | IMPLEMENTED_AND_VERIFIED | `personal_store.py`, `plan_store.py`, change-API, `test_personal_booked_revisions.py`, fryst och HTTPS Chromium/WebKit. 2 l mjölk + 1 kg ris köps för 70 kr; ändring till 1 l + 1,2 kg ger endast helt 500 g rispaket/15 kr, gamla köp oförändrade. Delvis konsumtion, byte två gånger, tomt tillfälle, verklig samtidig uppdatering, replay, stale och återanvänd historisk revision testade. |
| R7 Frukost/mellanmål: relevanta recept, egna värden/gränser, dag/måltid, gemensam korg | IMPLEMENTED_AND_VERIFIED | Befintliga tre frukostar/tre mellanmål och separat måltidskonfiguration bevarade. Frysta och HTTPS-prov med middag + frukost + mellanmål + extras. Datagränserna i R1/R4/R5 kvarstår. |
| R8 Extras: bekräftat generiskt med egenskaper, exakt variant låst, noll recept, explicit skafferi, icke-mat | IMPLEMENTED_AND_VERIFIED | Befintlig sök/scanner-koppling och gemensam allokering. Regression för mjölk 1,5 %, exakt servett, noll recept, lås och butikskonflikt. HTTPS efter bokfört köp behåller uttrycklig extramängd och produktlås. |
| R9 Pris: faktisk mekanism/radsumma/paket/villkor, grupper, använt/tillgängligt, fysisk/online | PARTIAL | ENGINE SUPPORT = IMPLEMENTED_AND_VERIFIED i befintliga kalkylator/optimerare/audit. Explicit källgrupp, medlemskap, datum, tak, konkurrens, paketallokering, kontext och kandidatval testade; syntetiskt motorresultat visas i båda webbläsarna. LIVE_DATA_UNAVAILABLE: 0 kompletta källavtal trots 1 523 råa mix-markeringar. Inga kampanjer eller jämförelsepriser uppfunna. Beräkningsgränser ger DATA_BLOCKED. |

## Release, regression och nästa operatörssteg

Aktuell release återanvänder produktfakta genom verifierad GTIN/förpackning med
fältproveniens och konflikthantering. Samma 449-raders pool: deklarationer
78 → 83, eko 45 → 46, fyra makron 73 → 78; komplett allergenunderlag fortfarande 0.
Inga produktdetaljhämtningar eller leverantörsanrop i konsumentflödet.

175 samlade regressionstester; efter sista sökfixen 28 direkt berörda och 81
fokuserade tester passerar. Appkod `e1c0db1`, fem deployade appfiler hashmatchade.
Ruff, Python 3.12 compileall och JS-kontroll passerar. Chromium/WebKit lokalt och
verklig HTTPS är verifierade; fysisk iPhone är inte testad. R6/R9 återanvänds.
Samma gamla meny 244,49 kr. Kall 16,181 → 16,102 s; varm 0,759 → 0,875 s.
Inga goldens ändrade och ingen prestandaomskrivning.

Backuper 20260911T140005Z och 20260911T140622Z; appbyte under befintligt driftlås.
Alla 109 revisioner före slutaktiveringen bevarade, inga användardata raderade.
Prismanifest/scheduler oförändrade. Rollback, fakta-/prisversioner och fulla
A–E-menyer/priser finns i aktuell rapport. Kontomodell och raderingsgarantier är bevarade.

Nästa operatör: verifierade receptutbyten/förlustgrunder, exakta enhetsomräkningar
och komplett allergenunderlag behövs för bredare stöd. OIDC-leverantör och tre
privata konfigurationsvärden är fortfarande ett separat operatörssteg enligt
föregående rapport; ingen ny tjänst eller kostnad har beställts.
