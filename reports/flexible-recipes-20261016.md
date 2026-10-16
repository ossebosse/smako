# Flexibla receptfamiljer – steg 4

Lokalt arbete i `D:\Projects\Smako`, gren `feature/flexible-recipe-families`,
bas `094557a`, implementation `07f7fd7`. Ingen aktivering på betan eller insamling av nya priser.

## Leverans

Ett generellt dataformat för granskade råvarubyten och mängdkombinationer
byggs med `meal_library_cli expand` till vanliga receptpaket. Det återanvänder
befintlig innehållsvalidering, atomär import, versionshistorik, förberedelsecacher,
produktkvalificering, näring och gemensam korgoptimering.

Varje variant har egna steg, komponentmängder, tillagningsmetadata och
granskningsuppgifter. Mängdval måste ligga på godkänt intervall/steg. Okända
ingredienser, dubblerade byten, oregistrerade mängder, felaktiga komponenter,
stegreferenser och kollisioner i variantidentitet avvisas. Ingen fri kombination
av byten sker under en menybeställning. Högst 16 listade varianter per familj.

Ett nytt grundrecept och dess varianter kan importeras med enbart data. Ett
regressionsprov använder ett tidigare okänt recept-ID, importerar en senare
variantversion och verifierar både den nya kandidaten och den äldre sparade
versionen. Ett separat prov kontrollerar att ett nytt variantlivsmedel kommer
med i förberedd sökning även när samma prisuniversum återanvänds.

Ett befintligt undantag är rättat: `adaptation=products` gäller också frukost
och mellanmål utan uttryckliga `recipe_choices`. Varianter får inte kringgå valet.

[Författarformat och arbetsflöde](../docs/flexible-recipes.md).

## Första innehållspaketet

Tre befintliga grundrätter har sju nya varianter. Alla tidigare poster behålls.
Innehåll och tillagningsplaner är strukturellt granskade, inte fysiskt provlagade.
Köp och näring kontrolleras separat vid planering.

Återspelning mot samma frysta pris-/faktaunderlag som tidigare prestandaprover:
19 tillåtna butikskontexter, maximalt två butiker, uppskattat köp, uttryckligen
tillåtna näringsuppskattningar, tomt skafferi. Klocka 2026-10-15 13:00 UTC.
Detta är historisk återspelning, inte dagens pris- eller lagergaranti.

| Rätt/variant | Inköpskorg | Protein per portion, uppskattat |
|---|---:|---:|
| Rostad morot/kikärtor, grundrecept, 2 portioner | 242,34 kr | 32,90 g |
| Mer kikärtor, mindre couscous | 242,34 kr | 33,98 g |
| Potatis i stället för couscous | 240,41 kr | 27,98 g |
| Broccoli i stället för morot | 252,21 kr | 36,75 g |
| Vita bönor i stället för kikärtor | 242,84 kr | 31,94 g |
| Tomat-/couscoussoppa, grundrecept, 2 portioner | 101,88 kr | 19,78 g |
| Soppa med mer kikärtor | 101,88 kr | 23,53 g |
| Yoghurtgryn, grundrecept, 1 portion | 65,30 kr | 9,70 g |
| Yoghurtgryn med mer yoghurt | 65,30 kr | 13,00 g |
| Kvarg i stället för yoghurt | Avvisad | Köpbar kvarg saknar kvalificerat underlag |

Priserna gäller hela förpackningar för respektive provkorg, inte förbrukad
råvarukostnad. Samma förpackningar räcker till vissa större mängder. Det billigare
potatisalternativet ger samtidigt lägre protein; användarens näringsgränser
avgör om varianten får användas. Näringen är beräknad från variantens faktiska
ingredienser och källor, aldrig kopierad från grundreceptet.

Sex av sju nya varianter samt samtliga tre grundrecept klarar korgrevision och
alla fyra makronäringsberäkningar i provet. Kvargalternativet förblir avvisat;
inga produkt- eller näringskrav har sänkts. Tidiga utkast kring bröd/keso togs
ur det lokala utkastpaketet efter att återspelningen visat saknad köpbarhet.

## Verifiering

269 offlineprov passerar: 263 regressioner i tio moduler, fem förberedelseprov
(inklusive ett helt nytt variantlivsmedel) och ett återspelningsprov med de tio
rätterna ovan. XML och åtkomstloggar finns under `.local/verification/`
med prefix `flexible-regression`, `flexible-future-cache` och
`flexible-source-replay`. Inga rapportläsningar eller blockerade externa
källanrop registrerades. Ruff, compileall och `git diff --check` passerar.

Fyra profiler kördes sekventiellt med befintlig acceptansmatris och samma frysta
underlag. Kall körning använder separat förberedelsekatalog per profil; varm
körning gör om själva menyn i samma process. Eko kördes en gång. Inga andra
tunga testkörningar gjordes samtidigt. Före-värdena kommer från föregående
etapps sparade verifiering; detta är små mätserier, inte kapacitets-/p95-bevis.

| Profil | Före kall/varm | Efter kall/varm | Pris före och efter |
|---|---:|---:|---:|
| Fem standardmiddagar | 61,56 / 37,74 s | 85,78 / 58,46 s | 674,16 kr |
| Fem middagar, minst 40 g protein | 32,66 / 7,98 s | 32,59 / 8,79 s | 1 216,11 kr |
| Frukost/mellanmål med portionsvikt | 27,77 / 1,95 s | 29,06 / 4,31 s | 85,55 kr |
| Tre middagar, minst 20 % eko | 216,52 / ej kört | 316,28 / ej kört | 434,13 kr |

Alla fyra profiler klarar korgrevision och valda gränser. Standard-, protein-
och ekoprofilen har samma fulla semantiska resultat som referensen.
Frukostprofilen väljer automatiskt den nya varianten med mer yoghurt:
uppskattad serverad vikt 400 i stället för 300 g per portion, inom samma valda
100–600 g. Mellanmålet och den sammanlagda inköpssumman är oförändrade.
Den profilen har därför avsiktligt en annan semantisk hash.

**Tidsregressionen är verklig:** standard och eko tar längre tid. Fler
alternativ kvalificeras och den befintliga jämförelsen med tidigare bibliotek
kör ytterligare sökning när det nya paketet bidrar med kvalificerade recept.
För eko ökar det observerade kallprovet med cirka 100 s. Att återanvända mer
arbete mellan biblioteksgenerationerna är därför ett konkret nästa
prestandasteg innan omfattande innehållsexpansion. Skyddet mot dyrare menyer
har behållits; ingen sökbudget eller användargräns sänktes för att dölja ökningen.

Det lokala biblioteket innehåller nu 197 registrerade receptposter på 100
grundidentiteter. Det nya paketet tillför sju varianter, inga nya grundrätter.
Manifestets SHA-256:
`461354a5898621ba6ad850610ebc0dae8d9840b728acdd945ba70d04cca92aa6`.

Rådata finns lokalt i `.local/flexible-recipes/replay.json`, `matrix/` och
`matrix-summary.json`. Källhashar finns i `.local/planner-preparation/inputs/matrix-inputs.json`.
Frysta priser: `14e5ce6f6978fe6b70ef0770b91eb4b361132291e98e0e9c342cd1a424ab9b00`.
Frysta fakta: `0d874ccb9cdf3891bbee90c90b74a6ed78ae96fb3b085192fd3c0baddd2a12e1`.

Större bibliotek kräver fortfarande prestandamätning. Fler registrerade varianter
ökar antalet kandidater, och befintlig jämförelse med tidigare bibliotek kostar
tid men skyddar mot ett dyrare slutresultat. Denna etapp gör recepten flexibla;
den bevisar inte globalt lägsta pris eller serverkapacitet.
