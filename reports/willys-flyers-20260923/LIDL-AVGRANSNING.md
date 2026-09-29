# Lidl-pilotens avgränsning och äldre testlucka

De befintliga bevisen och koden är återanvända, utan ny Lidl-insamling eller parserutvidgning.

380 strukturerade kandidater gav 351 parsergodkända produkter och 29 parseravvisningar. Tre av de 351 har granskad exakt koppling mellan den aktuella nationella publikationens dokumenttext och en unik strukturerad produkt: varumärke, namngiven variant, förpackning, källprodukt-ID och explicit GTIN. De har belagda datum och villkor. Reklambladet innehåller ingen direkt GTIN-join.

Övriga **377**, med en huvudorsak per kandidat och utan dubbelräkning:

| Huvudorsak | Antal |
|---|---:|
| Saknar granskad produktkoppling till nationell kampanj | 348 |
| Prisobjekt innehåller ett ännu oprövat fält | 27 |
| Rabattobjekt innehåller ett ännu oprövat villkor | 1 |
| Jämförpris är intervall eller approximation | 1 |
| Totalt | 377 |

De 348 kan dessutom sakna exakt förpackning eller andra fakta, men sådana sekundära orsaker räknas inte igen. De är **inte bevisat omöjliga att kvalificera**: pilotens manuella bevisregister granskar endast tre produkter. Det finns ingen `[:3]`, resultatkvot eller annan teknisk maxgräns på tre i insamlingen/kvalificeringsloopen; samtliga 380 behandlas. Begäran om 2–3 presentationsexempel ska inte uppfattas som belägg för fullständig kvalificeringsgranskning av övriga produkter. Den begränsade manuella bevismängden är ett kvarstående täcknings- och driftberoende.

**Ny kampanj sker inte automatiskt:** ny publikation eller PDF-hash kräver manuell dokumenttextgranskning och uppdaterat versionsbundet bevisregister innan import. Befintlig drift återkontrollerar den granskade kampanjen automatiskt, men behåller säkert stopp för ogranskade erbjudanden.

Källor: `reports/lidl-municipality-20260923/live-final-1280/collection/0145/result.json`, fälten `qualification.full_parse`, `decisions` och `retained_parser_quarantine`; `grocery_data/app/connectors/lidl/municipal_offers.py` och dess `fixtures/municipal_document_text_20260923.json`. Samma delade källflöde räknas en gång, inte en gång per butik.

## Historiskt test som inte gick att starta

`backend/tests/test_reviewed_lidl_nutrition.py` importerar vid modulladdning den saknade `reports/source-implementation-20260915/lidl_offer_adapter.py`. Modulen hänvisar också till äldre kampanj- och deklarationsfiler. Dessa återskapas inte med påhittade data.

Testmodulens skydd omfattar exakt GTIN/variant/förpackning och separat deklarationstid; deklarationshashar; spärr mot återanvändning på annan kampanj/snapshot; rå kycklinglårfilé endast i exakt tillåten tillagning utan avhällning och med uttryckligt estimatval; näringsgränsen kolhydrat <0,5; spärr mot ändrad/ofullständig deklaration; samt ostdeklarationens väg till recept, valt köp och audit utan ordinarie pris.

De nya Lidl-proven täcker närliggande principer: exakt GTIN/förpackning för Lingongrova, separat näringsprövning, spärr mot råvaruförväxling, kampanjutgång, okänt ordinarie pris, medlemskap och checkout/audit. De ersätter **inte** det äldre skyddet för de specifika ost-/kycklingdeklarationerna, rå-tillagad tillämpning eller kolhydratgränsen. Sökning i övriga tester hittar ingen likvärdig prövning av dessa specifika gamla bevis. Testluckan är fortsatt öppen och det historiska testet räknas inte som godkänt.
