# Befintliga alternativ till masa harina och pärlkorn

Ägaren stoppade 2026-10-28 spåret med externa nätbutiker. PR #34 är stängd
utan merge. Dess kod och råunderlag bevaras på arbetsgrenen, men ingår inte
i main. Nya handlare kräver fysisk butik och nätpublicerade butikspriser
för samma butik. Arbetsordningen är att alltid granska befintliga alternativ
och Smakos faktiska bortsortering först. Samma budgetjournal bevaras.

## Konkret miss: Kornris fanns redan

Granskningsverktygets regex för pärlkorn innehöll `parlkorn`, `matkorn`,
`korngryn` och `barley` men saknade `kornris`. Därför blev tidigare rapportens
påstående om att bara klippta korngryn återfanns för snävt. En full genomgång
av samma 89 458 produkter hittar Frebaco Kornris, artikel `101364286_ST`,
med en exakt GTIN-ankare `7312560036232` och 1 000 g förpackning.

Fem katalogkontexter har redan eget pris: City Gross Malmö Hyllie,
Hemköp Malmö Kronprinsen, Triangeln och Värnhem samt Willys Malmö Limhamn.
Två ytterligare rader är fysiska Coop-erbjudanden från Forum Jägersro och
Stora Coop Stadion; deras separata kampanjvillkor får inte räknas som
allmänt baspris. Inga av dessa är en ny nätbutik.

Granskningssökningen tar nu med kornris. Detta ger kandidater att granska,
inte automatisk auktorisering av priser eller ett generellt alias.
Smakos verkliga receptupplösning ger fortfarande noll träffar för pärlkorn;
dess exakta ingrediensdefinition har ännu ingen granskad produktrelation.

[Fazers konsumentartikel i Dabas](https://www.dabas.com/productsheet/07312560036232)
beskriver lätt polerat korn och 13–15 minuters kokning i rikligt vatten.
Det är ett relevant alternativ inom befintliga butiker. De 27 berörda
receptvarianterna behöver dock granskas mot det verkliga kokförloppet:
flera anger absorption i bestämd vattenmängd och 30–40 minuter. Att enbart
koppla produkten och räkna korgar skulle lämna detta olöst.

GoGreen Korngryn och matvete är andra redan understödda alternativ.
En verklig resolverkontroll godkände två kontexter för vardera i deras
egna befintliga recept. Korngrynssökningen hittade fem kontexter; tre
stoppades av den exakta ingrediens-/formkopplingen, inte av prisjämförelsen.
[GoGreen](https://www.gogreen.se/produkter/korngryn/) beskriver klippt korn.
Klippta gryn och vete får därför inte omärkligt byta identitet till hela
polerade korn. Mathavre hittades i sju kontexter men saknade godkänd
upplösning i det undersökta anropet utan utfärdat mathavrerecept.

## Hemköps majsstärkelse finns redan och fungerar för stärkelse

Ägarens [Hemköp-artikel](https://www.hemkop.se/productDetail/Majsstarkelse-100181152_ST)
är Maizena Majsstärkelse 400 g, `100181152_ST`. Den återfinns i nio
katalogkontexter och samtliga nio passerade den verkliga upplösningen för
majsstärkelse. Totalt godkändes 18 Maizena-/Garant-rader. Produkten är alltså
inte generellt bortsorterad av Smako.

Den löser däremot inte originalens 31 masa-varianter: de använder mjölet
som deg i bland annat tamales, fyllda majsbröd och klimpar.
[Masecas leverantörsdeklaration](https://dabas.com/productsheet/07501077400050)
anger nixtamaliserad majs; Maizena-artikeln är stärkelse. Även vanligt
majsmjöl och förkokt P.A.N.-mjöl återfinns i underlaget men är inte belägg
för nixtamaliserad massa. En annan deg behöver en tydlig receptanpassning.
Granskningssökningen tar nu också med stärkelsen som jämförelsekandidat,
med oförändrad spärr mot att automatiskt godkänna den som masa harina.

## Bevis och avgränsning

[Maskinläsbara fynd](existing-store-alternatives-20261028/findings.json)
och [hashindex](existing-store-alternatives-20261028/evidence-index.json)
binder undersökningen till samma frysta priser, fakta, recept och klocka.
Sök-/beslutsloggen kommer från ordinarie `PersonalPlanner.resolve`.
Regressionstestet kör granskningsverktygets rapportväg och visar både
återfunnet kornris och att sökträffarna inte beviljar ingredienskontrakten.
421 riktade tester, Ruff och compileall passerar. Två radslutsändringar
från branchbytet återställdes först efter att en full hashkontroll gav
exakt samma runtime-signatur som main:s tidigare verifiering; inga
kodändringar krävdes och inga gamla kvitton skrevs om.

Runtime, produktfakta, priser, recept och mängdpolicy är oförändrade.
Main:s hashstabila kontroll återanvänds: 2 200 original, 1 066 exakt hela
korgar och 1 864 inklusive uppskattningar. Noll nya korgar är räknade i
denna granskning. Kvarvarande arbete är kornrisets produkt- och
receptkvalificering, de övriga befintliga alternativens exakta kopplingar
och fortsatt genomgång enligt ägarens korrigerade arbetsordning.
