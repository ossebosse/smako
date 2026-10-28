# Hela frysta majskolvar med verifierat antal, 2026-10-28

**1 864/2 200 hela korgar inklusive uppskattningar**, två nya. Exakt läge
har 1 068 insatslösta och 1 066 hela korgar, också två nya hela. 336
varianter har insatshinder kvar. Alla original, 2 462 aktiva varianter
och tidigare verifierade korgar består. Full täckning återstår.

## Produkt och recept

[Findus egen produktsida](https://www.findus.se/var-mat/gronsaker/majskolvar)
anger två förvällda frysta kolvar i 400-g-förpackningen. Konsument-GTIN
7310500019628 finns i sidans produktbildsbeskrivning och stämmer med
den redan prissatta City Gross-artikeln 100722988_ST i Malmö Hyllie.
Den granskade textutläsningen finns i [underlaget](whole-corn-20261028/manufacturer-declaration.json).
Det är inte en ny prisobservation eller en visuellt granskad etikettbild.

Två [separata receptversioner](whole-corn-20261028/recipe-review.json) använder
en hel fryst förvälld kolv per portion och värmer från fryst före grillstekning.
De tidigare versionernas 180 g rå hel kolv är kvar i historiken. Inget
antagande görs om att en kolv väger 200 g eller om ätlig kärnmassa.
Tillagningstiden är en författaruppskattning med kontroll av färdighet;
recepten är inte provlagade.

Befintlig mängdprojektion stöder tillverkarens exakta styckeantal.
Inköp och skafferibokföring skiljer antal från förpackningens bruttogram.
Tre kolvar kräver två tvåpack; ett kontrollerat antal bokförs före
förbrukning. Fel GTIN, butik, förpackning, källa eller innehåll avvisas.
Gram- och volymförfrågningar får ingen styckekonvertering. Ätlig näring
och obelagda personliga produktfält förblir okända.

Alla tidigare fakta är identiska och en enda ny exakt produktrelation
tillkommer. Priser, prisobservationstider, källurval och butikstak ändras
inte. Se [bevarandekontrollen](whole-corn-20261028/facts-preservation.json).

## Sökning och onödigt arbete

Första A-provet blev 281,31 kr och stoppade leveransen. Samma 1 734
middagsrecept kvalificerades, men tidsgränsen avbröt sökningen före den
billigare menyn. Gränsen på 60 sekunder och de 12 sekunder som reserveras
för slutkontroll och sparning består.

Den befintliga butikskontrollen räknar nu fram identiska saknade butiker
en gång per ingrediensrad, i stället för en gång per saknad butik.
[Jämförelsen](whole-corn-20261028/sparse-mask-equivalence.json) behåller
exakt samma butiksidentiteter. Menysökningen återanvänder också lika
paketmängders överlappning i sin sortering; [samma menyförslag och vinnare](whole-corn-20261028/search-equivalence.json)
bevaras, inklusive individuella dagars prioriteter och stabila likheter.
Korgberäkning, butikstak, kampanjer, audit och användarkrav består.

## Kontroller

| Prov | Korg | API, sparning och återläsning | Separat förberedelse |
| --- | ---: | ---: | ---: |
| A, ny ägare | 278.76 kr | 53.47 s | 99.85 s |
| A, oberoende ny ägare | 278.76 kr | 53.70 s | 76.81 s |
| B2 | 731.20 kr | 32.36 s | 76.43 s |

Fullständiga begäranden är oförändrade. A klarar högst 278,76 kr i båda
proven; hela B2-korgen är identisk med tidigare 731,20 kr. Alla
2932 kvittofiler och aktuella beroenden är hashkontrollerade.
Inga gamla korgar förloras. Inget globalt optimum påstås.

587 riktade tester, Ruff och compileall passerar. CI har 4201
noder exakt en gång; samtliga 4 170 tidigare noder är autentiserade och
bevarade. Grön hosted CI krävs före integration. PR #32 är redan
integrerad på main 8270a9f; dess CI tog 7:44 mot tidigare 8:30 med hela
testurvalet kvar, [verifierat underlag](whole-corn-20261028/prior-hosted-ci.json).

Metod: `1bd67745a63fbcac37fda42e641f304b6e125f1f81e084651a61c36d411d9e83`.
Fakta: `.local/additional-source-review-20261028/facts-reviewed-v1.json`,
SHA `b90a733a50f7ba52f5a6ef47a27c0d23abe2a97879655d1e6ea239dc8f0609ae`. Slutprov: `.local/additional-source-review-20261028/final-v3`.
Samma frysta Malmöreferens, 89 458 produkter/52 kontexter och högst två
butiker, samma klocka och portionsantal. Legacy är fortsatt standard.

Den [separata källpiloten](coverage-source-pilot-20261028.md) har uppdaterade
produkt- och leveransvillkor men inväntar ägarbeslut. Mungbönornas exakta
komplettering väntar på ordinarie operationslås. Studien för kokt mung/beluga
är ännu inte tillämpningsgodkänd. Samma obegränsade budgetjournal,
en tung arbetare, två CPU och 3 GiB gäller. Ingen driftaktivering ingår.
