# Smako V2 – personlig planering

2026-09-12. Ingång: https://beta.smako.nu/personal. Release `personal-v2-five-dinners-20260912c`.
[Aktuell rapport: fem verifierade middagar](../../reports/smako-five-dinners-20260912.md) · [tidigare näringsrapport](../../reports/smako-dinner-nutrition-20260911.md) · [V2/OIDC](../../reports/smako-personal-planning-v2-gaps-20260911.md).
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
| R2 Skafferi: CRUD/sök/scanner, enheter, konto/gäst, saldo/reservation/köp/förbrukning/överskott | PARTIAL | `personal_store.py`, `account.py`, bokförings-/OIDC-/restoretester. Bekräftat generiskt torrt ris ger näring med explicit uppskattningsval: fem middagar reserverar 500 g, faktiskt lager 500 g oförändrat vid generering; annan meny 688,73 kr. `test_five_dinners.py`, Chromium/WebKit HTTPS. Gäst, delvis förbrukning, samtidighet, äldre bokföring och radering verifierade. Generell Authlib OIDC med state/nonce/PKCE testad offline. Tre OIDC-värden och livekontoacceptans återstår; e-post ger inget ägarskap. Befintlig katalogkoppling krävs även för exakt skafferitilldelning. |
| R3 Fördelning: tydliga kategorier, en huvudproteinkälla, giltiga summor/fria delval | IMPLEMENTED_AND_VERIFIED | Befintliga `MealSettings`, `distribution_ok`, `optimize_slots`; regression av kandidatval och konkreta motsägelsefel. Vegetarisk/vegansk/fisk/kyckling/övrigt kött kvar tydligt i UI. |
| R4 Eko: kostnadsandel efter rabatt över alla matköp och separat animaliskt krav | PARTIAL | `personal_source_facts.py`, `personal_planner.py`, `test_personal_qualified_facts.py`: 25 % eko-middag 55,73 kr; tre uppskattade middagar + eko 25 % kostar 480,05 kr med 50,54 % källstödd ekoandel, HTTPS-verifierat; separat animaliskt eko-frukost 50,34 kr; båda verklig HTTPS. Kostnad efter rabatt, mat-extras med, skafferi/icke-mat utanför; noll nya matinköp uttryckligt. Verifierat eko kräver inte animalieklassning; annars krävs källstöd. Okänd status aldrig positiv. Begränsat urval; full animalieklassning och vissa sammansatta/avrunna produkter kvarstår. |
| R5 Portion/näring: tillagad ätbar vikt, makron per portion, källa/enhet/grund, omkontroll | PARTIAL | `nutrition_reference.py`, `personal_nutrition.py`, `personal_planner.py`, `test_five_dinners.py`. Fem middagar × 4, Balanserad/max 2, protein ≥20 g/kcal ≤800 PASSERAR: 677,43 kr, samtliga ESTIMATED efter aktivt standardavstängt val. Nya kandidater: stekt torsk/äggnudlar/vitkål och couscoussallad/tofu/tomat. 30 SLV-mappningar, 10 dokumenterade tillagningskopplingar och en snävt granskad insatssummering utan påstådd retentions-/viktfaktor. Exakt tidigare tremiddagsmeny 426,52 kr och strikt A2 30,38 kr kvar. Fryst, nätverkslös serverimage, Chromium/WebKit HTTPS. Full blockeringsfördelning vid fel. Tillagad vikt/ogranskad beredning fortsatt DATA_BLOCKED; variationspool fortfarande begränsad. 83/46/78 deklarationer/eko/makron i oförändrad 449-pool, noll nya produktfakta. Specialproduktavgränsning behålls och konservtomat/annan couscous-/tofuform avvisas även med bättre metadata. |
| R6 Recept: öppna/redigera/ta bort/fylla/byta efter köp, hel korg/reservation, historik vid fel | IMPLEMENTED_AND_VERIFIED | Sparad personlig requests null-värden får inte tappa Balanserads presetregler; rundturstest. `personal_store.py`, `plan_store.py`, change-API, `test_personal_booked_revisions.py`, fryst och HTTPS Chromium/WebKit. 2 l mjölk + 1 kg ris köps för 70 kr; ändring till 1 l + 1,2 kg ger endast helt 500 g rispaket/15 kr, gamla köp oförändrade. Delvis konsumtion, byte två gånger, tomt tillfälle, verklig samtidig uppdatering, replay, stale och återanvänd historisk revision testade. |
| R7 Frukost/mellanmål: relevanta recept, egna värden/gränser, dag/måltid, gemensam korg | IMPLEMENTED_AND_VERIFIED | Befintliga tre frukostar/tre mellanmål och separat måltidskonfiguration bevarade. Frysta och HTTPS-prov med middag + frukost + mellanmål + extras. Datagränserna i R1/R4/R5 kvarstår. |
| R8 Extras: bekräftat generiskt med egenskaper, exakt variant låst, noll recept, explicit skafferi, icke-mat | IMPLEMENTED_AND_VERIFIED | Befintlig sök/scanner-koppling och gemensam allokering. Regression för mjölk 1,5 %, exakt servett, noll recept, lås och butikskonflikt. HTTPS efter bokfört köp behåller uttrycklig extramängd och produktlås. |
| R9 Pris: faktisk mekanism/radsumma/paket/villkor, grupper, använt/tillgängligt, fysisk/online | PARTIAL | ENGINE SUPPORT = IMPLEMENTED_AND_VERIFIED i befintliga kalkylator/optimerare/audit. Explicit källgrupp, medlemskap, datum, tak, konkurrens, paketallokering, kontext och kandidatval testade; syntetiskt motorresultat visas i båda webbläsarna. LIVE_DATA_UNAVAILABLE: 0 kompletta källavtal trots 1 523 råa mix-markeringar. Inga kampanjer eller jämförelsepriser uppfunna. Beräkningsgränser ger DATA_BLOCKED. |

## Release, regression och nästa operatörssteg

Appkod `e626ac0`, release `personal-v2-five-dinners-20260912c`. Fulla menyer, produkt-ID:n,
referens-/fakta-/prisversioner och beräkningsgrunder finns i aktuell rapport.
Samma 449-raders pool före/efter: 83 ingrediensdeklarationer, 46 ekologiska och
78 kompletta produktmakron. Generiska beredningsuppskattningar är inga nya
produktdeklarationer. Inga nya Coop-detaljer samlades i denna milstolpe;
föregående tio begärda detaljer stoppades av schema, noll accepterade dokument.

250 distinkta berörda regressionstester i denna milstolpe; sista kodversionen har 89 fokuserade
passerande tester. Ruff, Python 3.12 compileall och JS-kontroll passerar.
Chromium/WebKit på faktisk HTTPS med riktiga formulär/API passerar slutkoden.
Fysisk iPhone ej testad. Konsumentplanering/sökning har noll externa källanrop;
fryst serverprov kördes utan nätverk. Historiska köp/reservationer och R6/R9 bevaras.
Samma basmeny 244,49 kr; kall 14,791 s, varm 0,722 s (föregående 14,477/0,717 s).
Enskilda mätningar, ingen prestandaomskrivning eller ändrade goldens.

Backup `20260912T053012Z`; driftlås under appbyte, 130 äldre planrevisioner
hashbevarade (140 efter HTTPS-proven), prismanifest/scheduler oförändrade.
Rollback kan läsa nya modeller men spärrar ändringar som äldre motorn inte
stöder. Ingen databasrestore eller radering av användardata gjordes.

Tredje kolhydraten couscous och två nya kandidater är nu verifierade. Nästa
avgränsade arbete: ytterligare komplett mängd-/beredningskedja;
färsunderlaget saknar nåbar pepparpost 6661,
Hasselback behöver full potatis/smör/ströbröd-kedja. Utred godkänd Coop-klients
schemastopp utan bredare insamling. Fulla allergener och tillagad portionsvikt
är fortsatt DATA_BLOCKED. OIDC är ett separat, orört operatörssteg.
