# Separat prototyp: exakta receptnycklar och formsignaturer

Efter [beredningsvalideringsprovet](VARIED-VALIDATION-MEMO-RESULT.md) återstår
upprepad rekursiv hashning av frysta receptdesigner och kanonisering av alla
ingredienser när `resolve` bygger sin befintliga cache-nyckel. Denna prototyp
återanvänder endast dessa rena värden, inom samma plannerbegäran.

`RecipeComputationCache.key` tar **en ny snapshot vid varje anrop**: namn,
portioner, hela ingredienslistan med orundade mängder, instruktioner, samtliga
beredningsfält och den ordnade formordboken samt hela den frysta designen.
Objektidentiteten lokaliserar föregående snapshot; en träff kräver fortfarande
exakt värdelikhet. En stark referens hindrar återanvändning av Python-ID. Ändrade
listor, former, mängder eller en ersatt design med samma innehålls-SHA får ny
nyckel. Identiska värden interneras och nyckelns rekursiva hash beräknas en gång.
Hashkollisioner jämförs med hela värdet och kan inte godkänna en falsk träff.

`forms_for` bygger samma ordnade tuple av `(form, product_requirements)` som den
tidigare filtreringen, grupperad per kanoniserat synligt ingrediensnamn. Uppgiven
`canonical_name` används inte som sanning. Dubbletter och ordning bevaras. Varje
åtkomst använder den exakta receptnyckeln ovan. De rena formsignaturerna räknas
separat från de fyra befintliga beräkningarnas 416 poster; samtliga nya tabeller
är requestlokala och begränsade till 512 poster. Ingen befintlig gräns höjs.

Produktmatchning, källa, konflikter, mängd, villkor, näring, audit och sökförslag
går fortsatt genom sina tidigare vägar. Custom-normalizer-beteendet i
`MenuOptimizer` är oförändrat. Ingen kandidat, ordning, kostnadsgräns eller
sökbudget ändras. Detta ligger i en separat commit och ingick **inte** i det
profilerade 516,211-sekundersresultatet.

246 riktade tester passerar, inklusive 37 nya tester för alla ingrediens- och
designfält, mängdskillnad 1e-10, ersatt design med samma SHA, hashkollision,
ordnade alias/dubbletter, samtliga 104 recepts formsignaturer, cachegränser och
hela syntetiska plan-/auditresultat med respektive utan nyckelinternering.
Befintliga mutationstester för formordbok/ordning och custom normalizer passerar.
Ruff och compileall passerar. Befintliga syntetiska enumvarningar kvarstår.

En lokal mikroprofil, tre upprepningar av 20 000 rena funktionsanrop, gav följande
medianer. Detta mäter **inte** en användarbegäran, nätanrop eller en hel plan:

| Rent arbete | Tidigare | Prototyp |
|---|---:|---:|
| Exakt receptnyckel och hash | 0,194543 s | 0,028255 s |
| Ordnad formsignatur för samma ingrediens | 2,614448 s | 0,030989 s |

Råmikroprofilen ligger utanför Git i `.local/recipe-key-microbenchmark.json`.
Nyckelinterneringen och formsignaturerna behöver därefter jämföras med samma
autentiska fria Varierad-begäran; resultatlikhet ska bedömas före eventuell
integration och en profilerad diagnostid får inte kallas rent benchmark.
