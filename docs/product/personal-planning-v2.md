# Smako V2 – personlig planering

2026-09-11. Ingång: https://beta.smako.nu/personal. Release `personal-v2-dinners-20260911c`.
[Aktuell rapport: middagar och spårbara uppskattningar](../../reports/smako-dinner-nutrition-20260911.md) · [tidigare V2-rapport/OIDC](../../reports/smako-personal-planning-v2-gaps-20260911.md).
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
   per-portionsmakron använder verkliga källfält där de finns. Bekräftad generisk skafferinäring och granskade beredningsuppskattningar är nu möjliga efter aktivt val. Övriga ofullständiga underlag blockerar berörda krav.

## R1–R9 acceptansmatris

| Krav | Status | Kod-/testevidens och kvarvarande hinder |
|---|---|---|
| R1 Smak/allergier: svensk granskad tolkning, mjukt/hårt, alla val/byten, privat sparande | PARTIAL | `personal_policy.py`, `personal_source_facts.py`, `test_personal_planning_v2.py`, `test_personal_source_facts.py`. För bred mjölk-/ostmatchning korrigerad; referenser intygar aldrig allergenfrihet. 7 991 Coop-deklarationer kopplade; positiva konflikter blockeras. Noll kompletta allergenregister i godkänt underlag → hårda krav utan komplett bevis DATA_BLOCKED, även produktbyte/skafferi/exakta extras. |
| R2 Skafferi: CRUD/sök/scanner, enheter, konto/gäst, saldo/reservation/köp/förbrukning/överskott | PARTIAL | `personal_store.py`, `account.py`, bokförings-/OIDC-/restoretester. Bekräftat generiskt torrt ris ger näring med explicit uppskattningsval: 500 g lager oförändrat vid generering, 320 g reserverat. `test_nutrition_reference.py`, verklig HTTPS. Gäst, delvis förbrukning, samtidighet, äldre bokföring och radering verifierade. Generell Authlib OIDC med state/nonce/PKCE testad offline. Tre OIDC-värden och livekontoacceptans återstår; e-post ger inget ägarskap. Befintlig katalogkoppling krävs även för exakt skafferitilldelning. |
| R3 Fördelning: tydliga kategorier, en huvudproteinkälla, giltiga summor/fria delval | IMPLEMENTED_AND_VERIFIED | Befintliga `MealSettings`, `distribution_ok`, `optimize_slots`; regression av kandidatval och konkreta motsägelsefel. Vegetarisk/vegansk/fisk/kyckling/övrigt kött kvar tydligt i UI. |
| R4 Eko: kostnadsandel efter rabatt över alla matköp och separat animaliskt krav | PARTIAL | `personal_source_facts.py`, `personal_planner.py`, `test_personal_qualified_facts.py`: 25 % eko-middag 55,73 kr; tre uppskattade middagar + eko 25 % kostar 480,05 kr med 50,54 % källstödd ekoandel, HTTPS-verifierat; separat animaliskt eko-frukost 50,34 kr; båda verklig HTTPS. Kostnad efter rabatt, mat-extras med, skafferi/icke-mat utanför; noll nya matinköp uttryckligt. Verifierat eko kräver inte animalieklassning; annars krävs källstöd. Okänd status aldrig positiv. Begränsat urval; full animalieklassning och vissa sammansatta/avrunna produkter kvarstår. |
| R5 Portion/näring: tillagad ätbar vikt, makron per portion, källa/enhet/grund, omkontroll | PARTIAL | `nutrition_reference.py`, `personal_nutrition.py`, `personal_planner.py`, `test_nutrition_reference.py`. Aktivt standardavstängt uppskattningsläge, 30 uttryckliga SLV-mappningar, 9 specifika beredningskopplingar. Tre tillagade middagar × 4 portioner, Balanserad/max 2 butiker, minst 20 g protein/max 800 kcal: 426,52 kr, 9/9 ingrediensrader täckta; bekräftat generiskt skafferi 419,98 kr med annan tredje rätt. Strikt A2 30,38 kr utan uppskattning. Chromium/WebKit HTTPS. Fem/fyra middagar SEARCH_BLOCKED med nuvarande begränsade variationspool; tillagad vikt/ogranskad beredning DATA_BLOCKED. 83/46/78 deklarationer/eko/makron i oförändrad 449-pool. Gamla ost/getmjölksacceptansen ersätts, inte längre giltig efter korrekt specialproduktavgränsning. |
| R6 Recept: öppna/redigera/ta bort/fylla/byta efter köp, hel korg/reservation, historik vid fel | IMPLEMENTED_AND_VERIFIED | Sparad personlig requests null-värden får inte tappa Balanserads presetregler; rundturstest. `personal_store.py`, `plan_store.py`, change-API, `test_personal_booked_revisions.py`, fryst och HTTPS Chromium/WebKit. 2 l mjölk + 1 kg ris köps för 70 kr; ändring till 1 l + 1,2 kg ger endast helt 500 g rispaket/15 kr, gamla köp oförändrade. Delvis konsumtion, byte två gånger, tomt tillfälle, verklig samtidig uppdatering, replay, stale och återanvänd historisk revision testade. |
| R7 Frukost/mellanmål: relevanta recept, egna värden/gränser, dag/måltid, gemensam korg | IMPLEMENTED_AND_VERIFIED | Befintliga tre frukostar/tre mellanmål och separat måltidskonfiguration bevarade. Frysta och HTTPS-prov med middag + frukost + mellanmål + extras. Datagränserna i R1/R4/R5 kvarstår. |
| R8 Extras: bekräftat generiskt med egenskaper, exakt variant låst, noll recept, explicit skafferi, icke-mat | IMPLEMENTED_AND_VERIFIED | Befintlig sök/scanner-koppling och gemensam allokering. Regression för mjölk 1,5 %, exakt servett, noll recept, lås och butikskonflikt. HTTPS efter bokfört köp behåller uttrycklig extramängd och produktlås. |
| R9 Pris: faktisk mekanism/radsumma/paket/villkor, grupper, använt/tillgängligt, fysisk/online | PARTIAL | ENGINE SUPPORT = IMPLEMENTED_AND_VERIFIED i befintliga kalkylator/optimerare/audit. Explicit källgrupp, medlemskap, datum, tak, konkurrens, paketallokering, kontext och kandidatval testade; syntetiskt motorresultat visas i båda webbläsarna. LIVE_DATA_UNAVAILABLE: 0 kompletta källavtal trots 1 523 råa mix-markeringar. Inga kampanjer eller jämförelsepriser uppfunna. Beräkningsgränser ger DATA_BLOCKED. |

## Release, regression och nästa operatörssteg

Appkod `7b15c05`, release `personal-v2-dinners-20260911c`. Fulla menyer, produkt-ID:n,
referens-/fakta-/prisversioner och beräkningsgrunder finns i aktuell rapport.
Samma 449-raders pool före/efter: 83 ingrediensdeklarationer, 46 ekologiska och
78 kompletta produktmakron. 71 möjliga tillagningsreferenser är generiska
uppskattningar, inte nya produktdeklarationer. Tio distinkta produktdetaljer
begärdes genom godkänd Coop-väg; schemastopp gav noll accepterade dokument.

405 distinkta berörda regressionstester; sista kodversionen har 80 fokuserade
passerande tester. Ruff, Python 3.12 compileall och JS-kontroll passerar.
Chromium/WebKit lokalt och faktisk HTTPS med riktiga formulär/API passerar.
Fysisk iPhone ej testad. Konsumentplanering/sökning har noll externa källanrop;
fryst serverprov kördes utan nätverk. Historiska köp/reservationer och R6/R9 bevaras.
Samma basmeny 244,49 kr; kall 16,102→14,477 s, varm 0,875→0,717 s.
Enskilda mätningar, ingen prestandaomskrivning eller ändrade goldens.

Backup `20260911T171809Z`; driftlås under appbyte, 120 äldre planrevisioner
hashbevarade (130 efter HTTPS-proven), prismanifest/scheduler oförändrade.
Rollback kan läsa nya modeller men spärrar ändringar som äldre motorn inte
stöder. Ingen databasrestore eller radering av användardata gjordes.

Nästa avgränsade arbete: granska en tredje kolhydrat/tillagningsmetod med
komplett mängd-/beredningskedja; färsunderlaget saknar nåbar pepparpost 6661,
Hasselback behöver full potatis/smör/ströbröd-kedja. Utred godkänd Coop-klients
schemastopp utan bredare insamling. Fulla allergener och tillagad portionsvikt
är fortsatt DATA_BLOCKED. OIDC är ett separat, orört operatörssteg.
