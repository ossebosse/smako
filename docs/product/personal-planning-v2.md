# Smako V2 – personlig planering

2026-09-11. Ingång: https://beta.smako.nu/personal. Release `personal-v2-gaps-20260911c`.
[Full rapport, datatäckning, tester och operatörssteg](../../reports/smako-personal-planning-v2-gaps-20260911.md).
Ingen blanketacceptans av allergier, kontosynk, animaliskt eko eller portionsvikt.

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
| R4 Eko: kostnadsandel efter rabatt över alla matköp och separat animaliskt krav | PARTIAL | `_ecological_basket`, exakt källadapter och mat/icke-mat/rabatt/unknown-tester. 645 Coop + 323 Hemköp + 1 044 Willys positivt källmärkta rader. Faktisk HTTPS: 100 % kostnadsandel, 12,90 kr. Okänd status räknas inte positivt. Fullt animaliskt/sammansatt innehåll SOURCE_MISSING → DATA_BLOCKED; kravet sänks aldrig. |
| R5 Portion/näring: tillagad ätbar vikt, makron per portion, källa/enhet/grund, omkontroll | PARTIAL | `PortionLimits`, `_check_final`, käll-/gränstester. 6 725 kompletta Coop-deklarationer med användbar g/ml-grund. HTTPS: 100 g ris, 7,4 g protein/351 kcal, hel förpackning 22,67 kr. Tillagat utbyte, saknad/konfliktfylld näring och skafferiets näringsgrund DATA_BLOCKED. Inga g/ml-omräkningar eller vattenfaktorer gissas. |
| R6 Recept: öppna/redigera/ta bort/fylla/byta efter köp, hel korg/reservation, historik vid fel | IMPLEMENTED_AND_VERIFIED | `personal_store.py`, `plan_store.py`, change-API, `test_personal_booked_revisions.py`, fryst och HTTPS Chromium/WebKit. 2 l mjölk + 1 kg ris köps för 70 kr; ändring till 1 l + 1,2 kg ger endast helt 500 g rispaket/15 kr, gamla köp oförändrade. Delvis konsumtion, byte två gånger, tomt tillfälle, verklig samtidig uppdatering, replay, stale och återanvänd historisk revision testade. |
| R7 Frukost/mellanmål: relevanta recept, egna värden/gränser, dag/måltid, gemensam korg | IMPLEMENTED_AND_VERIFIED | Befintliga tre frukostar/tre mellanmål och separat måltidskonfiguration bevarade. Frysta och HTTPS-prov med middag + frukost + mellanmål + extras. Datagränserna i R1/R4/R5 kvarstår. |
| R8 Extras: bekräftat generiskt med egenskaper, exakt variant låst, noll recept, explicit skafferi, icke-mat | IMPLEMENTED_AND_VERIFIED | Befintlig sök/scanner-koppling och gemensam allokering. Regression för mjölk 1,5 %, exakt servett, noll recept, lås och butikskonflikt. HTTPS efter bokfört köp behåller uttrycklig extramängd och produktlås. |
| R9 Pris: faktisk mekanism/radsumma/paket/villkor, grupper, använt/tillgängligt, fysisk/online | PARTIAL | ENGINE SUPPORT = IMPLEMENTED_AND_VERIFIED i befintliga kalkylator/optimerare/audit. Explicit källgrupp, medlemskap, datum, tak, konkurrens, paketallokering, kontext och kandidatval testade; syntetiskt motorresultat visas i båda webbläsarna. LIVE_DATA_UNAVAILABLE: 0 kompletta källavtal trots 1 523 råa mix-markeringar. Inga kampanjer eller jämförelsepriser uppfunna. Beräkningsgränser ger DATA_BLOCKED. |

## Release, regression och nästa operatörssteg

413 samlade tester + 56 medlems-/scannerkontroller; efter sista isolerade gränsen
33 kalkylator-/audit-/grupptester. Ruff, Python 3.12 compileall och JS-kontroll passerar.
Chromium/WebKit lokalt och faktisk HTTPS, inklusive bokförd ändring, topup,
bevarad historik, sökning, laddningshotfix och data-blockering. Fysisk iPhone återstår.
Liveexempel: 300 ml skafferi; första köp 41,35 kr + tillägg 35,67 kr = 77,02 kr.
Coop Online Syd + Willys Lund, max två kontexter. Efter omberäkning: 0 kr återstår,
300 ml mjölk/400 g ris disponibelt. Syntetisk gästbokföring med verkliga katalogpriser.

Backuper `20260911T084740Z`, `20260911T090212Z`, `20260911T090702Z`; isolerad
restore och framåtkompatibel rollback verifierade. Gamla revisioner bevarade;
inga användardata raderade. Appbyte under samma lås som refresh/backup.
Samma gamla meny kostar 244,49 kr före/efter; kall 13,888 → 16,360 s (+17,8 %),
varm 0,785 → 0,780 s. Uppmätt regression; ingen prestandaomskrivning/ändrade goldens.

Nästa operatörssteg: välj/godkänn OIDC-leverantör och sätt tre dokumenterade värden
privat i `/opt/smako/production.env`; kör verifierad tvåenhets-/ägar-/raderingsacceptans.
Skaffa därefter komplett spårbar allergen-/animalie-/tillagningsdata och kompletta
kampanjavtal enligt fullrapportens källtabell. Inget nytt avtal är beställt.
