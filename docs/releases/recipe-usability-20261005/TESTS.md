# Verifieringsomfattning

Runtimekandidat: `2816d50e4a14dd118015a4c047f2346435b981ef`.
Slutliga HTTP-, webbläsar-, kvalificerings- och mätresultat sammanställs i RESULTS.md.
Detta dokument beskriver testernas avgränsning, inte en ersättning för de proven.

## Automatiserade regressioner

1 076 tester i 46 relevanta backendtestfiler: PASS, 31,79 s, 17 befintliga
Pydantic-varningar. Körningen omfattar korg/purchase terms, personlig planering,
receptlager, produktfakta, näring, sökåteranvändning, jobb och admission.
Logg: `.local/recipe-usability-20261005/regressions-memory.log`.
Ruff och riktad compileall: PASS. Ingen fysisk provlagning utförd.

Riktade nya prov i `test_recipe_usability.py` kontrollerar bland annat:

- Förpackningsenhet och kolli förblir skilda; saknad näring skapas inte.
- Källbunden mildhet ändrar bara sitt avsedda fält. Annat GTIN, annan
  förpackning, variant eller motstridig identitet får inte samma deklaration.
- Småpasta avvisar fel råvaruform; skaläggsidentitet skapar inte ätbar gramvikt.
- Äppelreferensen förblir generisk och avvisar motsägande form/sammansättning.
- Textcachen är begränsad och validerar fortfarande. Negativa ingrediensfel
  återanvänds endast inom rätt plannerbegäran och returnerar nya felobjekt.
- Vektor- och skalär korgprövning ger samma svar vid lika priser, mängdsteg och
  förändrade priser. Rangordningsmönster binds om till aktuella quote-objekt.
- Tom köpbar kandidatklass ger normalt datastopp i båda korgvägarna.

Befintliga tester täcker cacheberoenden, datum, medlemskap, portioner, skafferi,
butikstak, receptversioner, okända/motstridiga fakta, kampanjer och orundade
proteingränser. Sökåteranvändning jämförs även mot exakt referens på små fall.
Kvalitetsspärrar och oberoende slutaudit är kvar i ordinarie kodväg.

`test_plan_jobs.py` och `test_planner_admission.py` bekräftar dessutom:

- Ett avslutat fel kan läsas av rätt ägare utan att dess planner hålls vid liv.
- Feltyp, orsak och publika fält bevaras när avslutade stackramar frigörs.
- Oåtkomliga sökcykler samlas före nästa tunga jobb; städtiden återställs i rätt
  begäranskontext. Aktiva fakta eller användarresultat töms inte.
- Dubbelstart delar befintligt jobb, olika medlems-/ägarvillkor delar inte resultat,
  kögränser och antalet samtidiga beräkningar är oförändrade.

## Verklig integration

Kvalificering och menyprov använder hela frysta PriceUniverse-underlaget med
alla 2 233 refererade råfiler. Samma receptmängder, sökbudget, köpdag och
användarval gäller A/B/C. C använder senare hämtade fakta och redovisas därför
som berikad historisk replay. Det är inte ett prov mot aktuella produktionspriser.

HTTP- och webbläsarproven kör en manifestverifierad app-image med ordinarie
API, planlagring och slutaudit i en separat isolerad datakatalog, 2 CPU/3 GiB.
Endast fryst klocka/artifact-loader och mätinstrumentering finns i testharnessen;
inget av detta installeras eller föreskrivs för produktion.

En uttryckligt vald ny receptversion i ett separat bytesprov bevisar integration,
inte fritt ekonomiskt menyval. `WEEK-PARTICIPATION.json` håller dessa slutsatser
åtskilda genom de faktiskt registrerade fria sökhändelserna.

WebKit och Chromium är automatiserade datorwebbläsare, även när vyn är mobil.
Ingen fysisk iPhone har verifierats. Skärmbilder kompletterar DOM-/layoutkontroll.
