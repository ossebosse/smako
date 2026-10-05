# Genomförda ändringar och prövningsgränser

Ingen recepttext, ingrediensmängd, portionsgrund eller receptversion har ändrats. Biblioteket har fortfarande 152 versioner/62 grundrätter, varav innehållspaketet är 48 versioner och 14 nya grundrätter samt variationer i 10 tidigare familjer.

## Gemensamma kodvägar

- Ingrediensnamn normaliseras i en begränsad cache för enbart ren text (4 096 nycklar). Validering sker före återanvändning. Ingen produkt, prisobservation eller privat uppgift ingår.
- Misslyckade ingrediensuppslag återanvänds inom samma plannerbegäran (högst 1 024). Samma fullständiga uppslagsnyckel som för positiva resultat; nya anrop med andra fakta, datum eller ägarvillkor får nya cacher. Felobjekt skapas på nytt så att tidigare anrops annoteringar inte smittar nästa steg.
- Genomarbetade recept använder befintliga kanoniska alias vid kandidathämtning. Detta ger exempelvis `Chili Flakes` som kandidat för `chiliflakes`; det godkänner inte godtycklig styrka, form eller näring.
- `Risoni Pasta` når befintlig småpastaprövning som torr pasta. Fylld, kokt eller annan namngiven variant godkänns inte. Endast en uttrycklig produktbeskrivning från Garant tillåter det extra identitetsnamnet i deklarationsbindningen.
- Hela skalägg känns igen som råvaruidentitet. Separat ätbar mängd i gram krävs fortfarande; ingen styckvikt eller skalandel antas.
- Äpplets generiska referensmatchning accepterar den källbelagda lövkategorin `Äpple`/`Äpplen`, när faktisk fruktform, skal och frånvaro av motsägande sammansättning uppfyller befintliga krav. Det tillför ingen köpbar gramvikt.
- Korgmotorn återanvänder sina exakta prisvektorer över butikskombinationer. Alla delmängders Decimal-kostnad, kvalitetsrang och faktiskt använda butiker jämförs; endast kandidater som kan vinna enligt samma ledande ordningsnyckel materialiseras. Ursprunglig deterministisk produkt-/butikstiebreak och kampanjkopplade grenar behålls. Ingen sökbudget eller receptpool minskas. Oberoende slutaudit kvarstår. Om inga kandidater ger en köpbar rad återges rätt datastopp (`IncompleteBasketError`), även efter att irrelevanta butiker filtrerats bort.

## Källkompletteringar

1. **Santa Maria Paprikapulver 200 g.** Tillverkarens sida `paprika-stor` styrker mildhet och förpackningsidentitet 200 g, med separat kolli 6 enheter. Den befintliga butiksdeklarationens näring behålls; 37 g-variantens näring kopieras inte. Hämtning 2026-10-05T10:04:18.456371+00:00, råhash `256e13ecbbe543660b42d822bbffea1710373f22b4ecfa4454339b97c4636aff`. [Primärkälla](https://www.santamariaworld.com/se/produkter/paprika-stor/).
2. **Garant Risoni 500 g**, GTIN 7311043002030. Tillverkarens exakta beskrivning binder Risoni till pastakategorin, namnet och 500 g. Per 100 g: 353 kcal, 1,3 g fett, 72 g kolhydrat och 12 g protein. Produktfakta knyts till rätt variant och förpackning även när butiksraden saknar GTIN; inget GTIN skrivs in på den butiksraden. Hämtning 2026-10-05T10:04:21.042952+00:00, råhash `a4309a23226ca1e4c1bf33687237813d88fa7a889c59991b2a145002a06eafd6`. [Primärkälla](https://www.garantskafferiet.se/vara-produkter/skafferi/pasta/risoni/).
3. **SLV 588, äpple med skal.** Befintlig återanvändbar API-import, faktisk hämtning 2026-10-05T10:26:05.239562+00:00, dataversion 2026-06-29T00:33:28.58. Generisk referens per 100 g ätlig råvara; kräver befintligt uttryckligt näringsmedgivande. Referensen bevisar varken märkesdeklaration, allergensäkerhet eller inköpt/ätbar vikt. Råa API-svar och hash finns utanför Git, strukturerat versionsbundet innehåll i referensregistret. [Primärkälla](https://dataportal.livsmedelsverket.se/livsmedel/api/v1/livsmedel/588/naringsvarden?sprak=1).

Källkonflikter spärrar fortfarande. Tillverkardeklarationernas bindning kräver rätt namn/variant, märke, fast förpackningsmängd och enhet; känt men avvikande GTIN avvisas. Varken källa eller pris får nytt observationsdatum genom ett cacheträff. Nya källor med historiska priser redovisas uttryckligen som berikad historisk jämförelse.

## Resultat måste läsas på rätt nivå

Individuell kvalificering provar två portioner, högst två butiker, båda köplägena, full näringspanel och separata uppskattningsmedgivanden. Den visar inte att samma recept klarar huvudbegärans 30 g protein eller att det valts i en femmiddagsmeny. `QUALIFICATION.json` skiljer faktiskt första stopp från efterföljande, oberoende ingrediensprov. `MENUS.json` redovisar verkliga veckosökhändelser och slutval. Recept som inte valts under en begränsad sökning benämns inte automatiskt dyrare.

Innehållsgranskning, maskinell produkt-/närings-/köpprövning och fysisk provlagning är olika saker. Den här leveransen innehåller ingen fysisk provlagning eller uppmätt tillagningstid.

## Riktad rättning efter profilmätning

522502c gav samma meny men längre tid för 40 g-profilen. CPU-profileringen
visade 274 318 anrop till prisvektorer och 1 636 015 bevisat ofullständiga
butikskombinationer av 1 656 754. Näringsalternativens ändringsbara kandidatlistor
saknar avsiktligt återanvändbar quote-identitet. Dessa engångskorgar använder
nu samma exakta skalära beräkning med tidig ingredienstäckning som baslinjen.
Inga giltiga produkter, korgar eller söksteg tas bort.

Återanvändbara korgar behåller vektorerna. En ny begäranslokal cache med högst
256 mönster återanvänder butikernas fullständiga deterministiska rangordning.
Aktuella quote-objekt levererar pris, mängd, status och produkt; förändrad
rangordning eller butiksuppsättning får en annan nyckel. Cachen rensas med
befintlig session och dess minnesgräns. Tester jämför båda vägarna vid paketsteg,
prisordningsbyten, lika priser, ändrade mängder och butikstak.

Korgändringens runtime är 0da2828f5404905bea842b91f7feda4778661bba.
Slutmätningar och HTTP-prov gäller den byggda imagen; försöksmätningar från
äldre mellanversioner behålls separat och räknas inte som slutprestanda.

## Livscykel för söktillstånd mellan jobb

Den sammanhängande HTTP-serien på 0da2828 nådde minnesgränsen 3 GiB efter åtta
profiler. Detta var ett faktiskt appfel, inte fyra nya receptstopp. Underlaget
bevaras separat. En isolerad minnesdiagnos visade två retentionstyper:

- Ett avslutat feljobb höll kvar planner, 42 495 faktaobjekt och 44 194 indexposter
  via Task-objektets kedjade traceback. Vanlig skräpsamling frigjorde dem inte.
  Rensning av avslutade stackramars lokala variabler frigjorde plannerobjektet.
- Även framgångsrik sökning kunde lämna oåtkomliga cykler i äldsta generationen.
  Full skräpsamling efter huvudfall/Varierad minskade uppmätt RSS cirka 150–180 MiB.

2816d50 rensar därför avslutade felramar vid jobbfärdigställandet och samlar
endast oåtkomligt tillstånd före nästa antagna tunga beräkning. Feltyp, publika
fält, orsakskedja och traceback-positioner bevaras. Aktiva cacher, samtidighet,
sökordning, kandidater och budget ändras inte. Städningens väggtid mäts separat
från köväntan och ingår fortfarande i användarens totala väntetid.

Svaga referenser i tester bekräftar frigörandet utan ändrad ägaråtkomst eller
felrespons. 1 076 relevanta regressionstester passerar. Långvarig HTTP- och
webbläsarverifiering på den paketerade imagen redovisas separat i RESULTS.md;
de mekanistiska minnesproven ensamma bevisar inte stabilitet under alla profiler.
