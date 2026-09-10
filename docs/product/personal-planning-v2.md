# Smako V2 – personlig planering

2026-09-10. Ingång: https://beta.smako.nu/personal. Release `personal-v2-20260910c`.
Detta är acceptansstatus, inte ett påstående att hela milstolpen är färdig.
[Full rapport, tester och operatörssteg](../../reports/smako-personal-planning-v2-20260910.md).

## Gemensamt kontrakt och inventering

Receptbehov + uttryckliga extravaror − allokerat verkligt skafferi, därefter hela
förpackningar, villkorade priser och ett butikstak 1/2/3 för hela korgen. Samma
medlemskap/prisversion gäller allt. Icke-livsmedel påverkar köp och butikstak.
Lager, reservation, framtida köp, överskott och förbrukning är separata.

Återanvänt: befintlig generator, `MenuOptimizer`, `BasketOptimizer`,
`BasketCalculator`, `ProductSearchIndex`, scanner, HttpOnly gästägarsession,
`PlanStore`, historiska revisioner och raderings-/restore-ledger. Receptbyte och
kampanjer har utökats. Ingen parallell prismotor eller beställd extern tjänst.
Katalogen saknar tillgängliga spårbara allergen-/ingrediensdeklarationer,
ekostatus, full produktnäring och tillagningsutbyte. Namn/bilder är inte bevis.
Tidigare konto saknades; Authlib/OIDC finns nu men är inte operatörskonfigurerat.

## Tre återupptagbara delsteg

1. **Levererat/testat:** gemensam korg, noll recept, generiska/exakta extravaror,
   strukturerad receptredigering, tomma tillfällen, byten, historik och kampanjrader.
   Återuppta med R6/R9-begränsningarna nedan; inga prisgoldens har ändrats.
2. **Gästflödet levererat/testat:** uttryckligt profilsparande, privat skafferi,
   atomiska reservationer, idempotenta inköp/förbrukning, restförslag och radering.
   Kontoinloggning återupptas med verifierad OIDC-konfiguration och acceptans.
3. **Regler levererade/testade:** separata måltidstyper/portioner/proteinfördelning
   och tre faktiska planlägen. Eko-/näringsgränser har verkande spärrar och frysta
   evidenstester; produktionsverifiering är DATA_BLOCKED.

Delstegen släpptes tillsammans, följt av en verifierad komplettering för
jämförelser/erbjudanden. Börja återupptagning med `test_personal_planning_v2.py`.

## R1–R9 acceptansmatris

| Krav | Status | Kod-/testevidens och kvarvarande hinder |
|---|---|---|
| R1 Smak/allergier: svensk granskad tolkning, mjukt/hårt, manuella konflikter, alla val/byten, privat sparande | PARTIAL | `personal_policy.py`, API/UI; okänd allergi, sammansatta varor, spår, namnförfalskning och privat API testas. Hårda krav styr kandidater/slutkorg. Produktionsdeklarationer saknas → DATA_BLOCKED; ingen allergifrihet intygas. |
| R2 Skafferi: CRUD/sök/scanner, generiskt/exakt/enheter, konto/gäst, saldo/reservation/inköp/förbrukning, överskott/restförslag | PARTIAL | `personal_store.py`, `account.py`, planner; livscykel, samtidighet, migrering, ägare och restore testas. Gästflödet fungerar. Tre OIDC-inställningar och verklig inloggningsacceptans saknas. Ingen sammanslagning till redan fyllt konto; katalogkoppling krävs även för skafferitäckta behov. |
| R3 Fördelning: vegetarian/vegan/animaliskt, en huvudproteinkälla, giltiga summor och fria delval | IMPLEMENTED_AND_VERIFIED | `MealSettings`, `distribution_ok`, `optimize_slots`; kandidatvalstest och konkreta motsägelsefel. UI definierar vegetarisk/vegansk/fisk/kyckling/övrigt kött. |
| R4 Eko: verifierad kostnadsandel efter rabatt över alla matköp samt separat animaliskt krav inkl. ägg/mejeri | DATA_BLOCKED | Kostnadsandel och hel omoptimering implementerad; frysta tester för mat-extras, icke-mat, rabatt, ägg/mejeri och unknown. Produktionsstatus saknas; valt krav stoppar beräkningen utan sänkning. |
| R5 Portion/näring: tillagad ätbar vikt och makrogränser per portion, källa/enhet/grund, omkontroll, okänt inte noll | DATA_BLOCKED | `PortionLimits`, `_check_final`; portionsändring, saknat utbyte, ofullständiga/negativa/NaN/inf-data testas. Produktnäring och tillagningsunderlag saknas i produktion; också skafferiets näring blockeras. |
| R6 Recept: öppna/redigera/ta bort/fylla/byta, faktiska behov, hel korg/reservation/krav, historik vid fel | PARTIAL | Privata change-API:t, revisions-/ägartester och Chromium/WebKit. Övriga tillfällen hålls fasta; ogenomförbart byte bevarar tidigare revision. Efter bokfört inköp/förbrukning krävs ny plan; ändring av redan bokförd plan återstår. |
| R7 Frukost/mellanmål: relevanta recept, egna måltidsval/gränser, dag/måltid och gemensam korg | IMPLEMENTED_AND_VERIFIED | Befintlig generator utökad med tre frukostar/tre mellanmål; frysta och HTTPS kombinationsprov. Middagsgränser kopieras inte till mellanmål. Global ekoandel, animaliskt eko per måltidstyp. Datagränser enligt R1/R4/R5 kvarstår. |
| R8 Extravaror: bekräftat generiskt med egenskaper, exakt variant låst, noll recept, explicit skafferival, icke-mat | IMPLEMENTED_AND_VERIFIED | Sök/scanner-koppling och gemensam allokering; mjölk 1,5 %, exakt servett, butikskonflikt och nollrecepttester. HTTPS testar exakt vara och isolering. |
| R9 Pris: faktisk mekanism, radsumma/paket/villkor/giltighet/medlemskap, använt/tillgängligt och fysisk/online | PARTIAL | Befintlig prismotor och nya rader; flerköp under/över tröskel, medlemskap, strategiska köp och gamla korgar testas. Källstödda mix-and-match-grupper saknas och gissas inte. Okänd ordinarie kostnad ger ingen påhittad besparing. |

## Release och gränser

381 berörda regressionstester + 56 medlems-/scannerkontroller passerar.
Frysta mobilflöden: 18 kontroller/motor. Verklig HTTPS: 22 kontroller/motor.
Chromium/WebKit-emulering är inte fysisk iPhone-/kameraacceptans.
64 tidigare planrevisioner bevarades exakt vid första releasen, 70 vid B och 76 vid C.
Backup före release `20260910T191841Z`; V2-backup `20260910T192800Z` verifierad
och återläst till isolerad katalog med gällande raderingsledger.

Ingen användardata raderad. Kall plannerprestanda, Willys-task/relay,
ICA/Primat-normalisering, källinsamling och ICA OWN-research är orörda/uppskjutna.
Samma frysta gamla meny: 244,49 kr före/efter. Kall 18,17 → 18,82 s (+3,6 %),
varm 1,136 → 1,070 s; stickprov, ingen prestandaomskrivning.
