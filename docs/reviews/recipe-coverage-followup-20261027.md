# Fortsättning: mängdspärr rättad och 1 605 verifierade tvåbutikskorgar

Från main `4093d33`, enligt [fortsättningsuppdraget](../CODEX-SOL-NEXT-20261027-COVERAGE-FOLLOWUP.md).
Mängdrättningen är separat commit `cac2a91`; samlad käll-/kontrollkod är
`e8c58ef`. **100-procentsmålet är inte uppnått.** Alla 2 200 ursprungs-ID:n
och 2 462 aktiva varianter bevaras. Recept, portioner, priser, personliga
krav, standardläge och butiksscope har inte ändrats.

## Resultat i samma frysta referens

| Mått, nämnare 2 200 | Exakt före → efter | Inklusive tillåtna uppskattningar före → efter |
| --- | ---: | ---: |
| Alla insatser individuellt produkt-/mängdlösta | 969 → **999** | 1 569 → **1 605** |
| Nya / förlorade insatslösta | **30 / 0** | **36 / 0** |
| Komplett verifierad tvåbutikskorg | 967 → **997 (45,3 %)** | 1 569 → **1 605 (73,0 %)** |
| Insatslösta men checkout blockerad | 2 → 2 | 0 → 0 |
| Insatsblockerade | 1 231 → 1 201 | 631 → **595** |
| Ofullständig/ej kontrollerad slutlig sökning | 0 | 0 |

Estimated inkluderar exact. 606 varianter saknar exakt insatsstöd men har
uppskattat stöd. 608 fullkorgar är verifierade endast i uppskattningskolumnen,
inklusive de två exakta checkout-avslagen. Det är inte ett framtida
omöjlighetsbevis. Inget uppskattningsval görs åt användaren.

Mozzarellan frigör 30 hela varianter i båda lägena. Romansallad frigör sex
ytterligare hela varianter i estimated. Ingrediensförekomster summeras inte.
Kvarvarande estimated-hinder omfattar 76 grupper. Alla ursprungs-/aktuella
ID:n, scope, nästa källåtgärd och korgreferenser finns i
[coverage.json](recipe-coverage-followup-20261027/coverage.json),
[blockerlistan](recipe-coverage-followup-20261027/blockers.json) och
[kvittoindexet](recipe-coverage-followup-20261027/basket-receipts.json).

## Rättad mängdspärr

Före rättningen returnerade `project_usable_quantity` en granskad uppskattning
innan den befintliga `_mass_blocking`-kontrollen nåddes. Isolerade prov för
`nutrition.package_quantity` och `nutrition.unknown_quantity` gav därför
felaktigt 96 g från den granskade 100-g-förpackningen. De två proven fallerar
på ursprunglig kod och passerar efter rättningen.

Alla projektioner kontrollerar nu samma befintliga mängdkonfliktspolicy
innan resultat accepteras. Även `intake_product_links` använder den policyn
vid efterföljande relation/kvalificering; en direkt ingång eller en redan
projicerad produkt kan inte låna ett godkännande med motsägelsefulla fakta.
Ingen separat lista med konfliktundantag har införts.

Regressionerna omfattar `nutrition.package_quantity`, `package_quantity`,
`usable_quantity`, okända konflikter och uppvärmd granskningscache följd av
ändrade fakta. Normal uppskattning utan kompletta näringsfakta, uteblivet
estimated-samtycke och prisuppdatering med oförändrad identitet bevaras.
En känd ren konflikt i `nutrition.protein_g` blockerar inte en oberoende
mängdrelation, men samma motstridiga näring ger ingen näringsreferens.

Det verkliga faktaunderlaget innehåller inga av de reproducerade
mängdkonflikterna. Sju befintliga `organic`-konflikter bevaras och undantas
inte från den befintliga policyn. Ingen uppmätt variant behövde förloras
av korrekthetsskäl; nämnaren och alla förluster kontrollerades ändå på nytt.

## Verkliga källförbättringar

**Mozzarella:** [Galbanis leverantörsblad på Dabas](https://www.dabas.com/productsheet/08000430133035)
anger exakt konsument-GTIN 08000430133035, 125-g-förpackning och 125 g
jämförmängd med uttrycklig basis *Per avrunnen vikt*. Full mjölk-/salt-/löpe-/
citronsyraformula styrker naturell ost. Befintlig `parse_dabas` och
`supplement_catalog_facts` används; inga fabrikerade tillverkarfält skapas.

Nio befintliga exakta GTIN-/varumärkes-/förpackningsrelationer godkänns:
en City Gross-kontext och åtta ICA-kontexter. De senare är produktbundna,
variantupplösta erbjudanden med exakt källmängd och utan kritiska blockerare.
De får sina befintliga köp-/kampanjvillkor prövade av samma checkout.
Granskningen godkänner varken ett grupp-/okänt erbjudande eller ett pris.
Köpt förpackning, avrunnen ost, lag och näringens beredningsbasis hålls isär;
bladets ospecificerade näringsbasis görs inte om till exakt avrunnen näring.
As-sold-mozzarella utan lag kräver fortfarande ett eget produktbevis.

**Sallad:** åtta relationer för exakt namngivna gramförpackningar
`Romansallad Ekologisk Klass 1` och `Romansallad Import Klass 1` använder
USDA SR28-post 11251, cos/romaine, rå: 6 % förlust för rotstock/kärna,
94 % uppskattat ätligt utbyte. Detta använder samma tidigare verifierade
USDA-arkiv/FOOD_DES-hash och samma befintliga metod som övriga granskade
råvaror. Det gäller endast estimated; varken kruka, dressing, färdig
salladsrätt eller andra salladssorters utbyte godkänns generellt.

Före-/efterfakta, källhashar och relationer finns i
[enrichment.json](recipe-coverage-followup-20261027/enrichment.json) och
[public-acquisition.json](recipe-coverage-followup-20261027/public-acquisition.json).
Ett nytt leverantörsblad hämtades och parsades; två andra exakta Dabas-URL:er
gav 404 och bevaras som misslyckanden. Importregistret behåller även sin
historiska definitionsgranskning; aktuellt köpstöd anges av `reviewed_links`.

## Resthinder och avgränsad insamling

| Kvarvarande grupp i estimated | Blockerade | Enda kvarvarande grupp, villkorad övre marginal |
| --- | ---: | ---: |
| Mynta | 131 | 92 |
| Tamarindpasta | 93 | 53 |
| Masa harina | 31 | 31 |
| Pärlkorn | 27 | 24 |
| Nötkött | 27 | 17 |
| Citrongräs | 27 | 15 |

Marginalerna är inte uppmätta ytterligare vinster. Myntans ensamma hinder
ökar när salladsluckan stängs i överlappande recept.
[Särskild källgranskning](recipe-coverage-followup-20261027/source-review.json)
anger prövade positiva/negativa artiklar och konkret nästa åtgärd.

Befintligt verifierat 25-g-myntadokument anger nettovikt och smak, inte
användbar bladmängd. 100-g-artikeln behöver fortfarande ett exakt detaljbevis;
429-g-krukans totalvikt kan inte användas. Tamarindträffen är ett 435-ml-
koncentrat, utan styrkt motsvarande pastastyrka och g-mängd. PAN:s vita
förkokta majsmjöl och masalaträffar styrker inte nixtamaliserat mjöl.
Urtekrams producentblad beskriver polerade kornkärnor, artikel 1012040/400 g,
men inget motsvarande exakt prissatt SKU i den frysta referensen verifierades.
GoGreen korngryn och Pågens Guldkorn-bröd ersätter inte pärlkorn.
Nytt sortiment kräver egen deklarerad källa/pris-/butikskontext; inga nya
handlare eller priser blandas in här. Detta är inte ett bevis om hela marknaden.

Sju befintliga Willys-artiklar köades för relevant detaljkomplettering.
Två avgränsade försök avstod före nätanrop eftersom det befintliga lokala
kommunrelälåset var upptaget: **noll handlaranrop**. Inget lås kringgicks
och inget nytt arkiv eller schema aktiverades. Kö och avslag finns bredvid
rapporten. Fortsätt vid ledig befintlig insamlingslease, med samma godkända
scope, och hämta inte om redan verifierade dokument utan behov.

## Fryst scope, återupptagning och kontroll

Samma 89 458 prisprodukter och 52 butikskontexter från Malmöunderlaget
2026-10-23 används. Prisfilens SHA-256 är
`06cbf0b12e619f09dd3709b808916d1c74676859d246ad72f74d52d0e6d91857` och
klockan `2026-10-23T06:00:02.869273+00:00`. Middag fyra portioner,
frukost/mellanmål en; två butiker, inget skafferi/extras/personliga krav.
Nya källfakta har egen version med SHA-256
`4f808c14e8bc8ab3e3719805ee59a2a2257b7953271ba56d346ed764fafe4cd3`.
Nya faktatider förnyar inte de historiska prisobservationerna.

Metodhash är `1247b60415262b1c1238642c81d7aa63547821c780ece3229922e0cb8e59958e`.
Alla 2 200 kontrollerades på nytt med `PersonalPlanner.basket(final=True)`;
2 604 beroendebundna kvitton omfattar 2 602 verifierade och två exakta avslag.
Fulla kvitton ligger i `.local/recipe-coverage-followup-20261027/checkpoints`;
frysta fakta i samma katalogs `facts.json`. De lokala stora pris-/fakta- och
råfilerna är inte Git-data. Följ [DEVELOPMENT](../DEVELOPMENT.md) vid återställning.

Kontrollprogrammen kan nu även jämföra mot föregående fulla täckningsrapport.
De behåller ursprungs-ID:n och avvisar ändrad klocka, prisfil, butiker, portioner,
butikstak, skafferi, receptmanifest eller begäransvillkor. Ny fakta-/metodversion
kräver nya kvitton; gamla beroendehashar skrivs inte om. Timeout är ofullständig
sökning. Slutlig kontroll tog 220,3316 s, verifiering/sammanställning 28,5490 s.

487 riktade regressioner, Ruff, compileall och diffkontroll passerar.
Ordinarie CI krävs på slutligt PR-huvud före mainintegration. CI:s status och
integrationscommit ska läsas i PR-kontrollerna och integrationskvittot.

## A/B2 och prisbegränsning

Hela sparade A- och B2-begäran matchar tidigare begäran exakt.
B2 behåller också hela strukturerade **731,20-kronorskorgen** exakt,
API/checkout/save/ägd GET **33,7535 s**. A ger giltig full sparad och återläst
korg på **52,4272 s för 317,82 kr**. Se [A](recipe-coverage-followup-20261027/A.json),
[B2](recipe-coverage-followup-20261027/B2.json) och respektive jämförelsekvitto.

**A kvalificerar inte prisparitet.** Tidigare A-receptförslag verifierar
fortfarande **290,82 kr** genom aktuell checkout och audit, skalat till
samma fyra portioner. Den begränsade sökningen missar en känd giltig billigare
kombination med **27,00 kr**. [Referenskvittot](recipe-coverage-followup-20261027/A-reference-checkout.json)
skrevs efter det uppmätta API-resultatet, användes inte som sökfrö och ingår
inte i API-tiden. Ingen global optimalitet, pristolerans eller pris-/
prestandarelease godkänns av de snabba svaren. Prisgapet är ett releasehinder.

Laddning/förberedelse före API:t är **101,9719 s för A och 77,9956 s för B2**.
Detta är inte 30–60 s från tom installation. Inga nya browsertider anges.
A verifierar fortfarande inte ett aktivt måltidsbundet 10–15-krav; B2 behåller
sitt uttryckliga uppskattningsval och minst 35 g protein enligt befintlig policy.

## Budget och nästa arbete

Den nya journalen använder **772,9932/1 200 s**, med **427,0068 s (7,12 minuter)
kvar**. Källarbete stängdes med 948,2167 s kvar, före reserverad slutverifiering.
Samtliga tunga körningar är seriella under befintlig supervisor: två CPU,
hårt 3 GiB; högsta jobbcommit **1 569 783 808 byte, cirka 1,462 GiB**.
Misslyckade körningar, 404 och uppskjutna insamlingsförsök räknas. Fyra små
externa webbsökningar debiteras med konservativt avrundade UTC-intervall;
de påstås inte vara supervisorbegränsade Python-prestandaprov.

Gamla journalen är orörd: SHA-256
`0d7402418b9027ba84df692247cc41b18313a4ed3aded367b088a715898a0380`,
7 172,6967 s använda/27,3033 s kvar. Ingen rest flyttades, budget nollställdes
eller automatisk fortsättning startades. Ny budget är inte uttömd; fortsatt
källarbete kräver de redovisade faktiska beläggen/ledig insamlingslease eller
ett separat beslut om nytt sortiment, följt av korrekt omverifiering.

Nästa prioritet är fortfarande de 595 insatshindren, inklusive sällsynta
råvaror, samt A:s verifierade prisgap. En ny samlad täckningskontroll och
sammanställning kostade senast cirka 249 s; A/B2 inklusive laddning cirka
268 s till. Undvik nya små ändringsomgångar som inte lämnar plats för slutprov.
Legacy är standard, V2 opt-in. Ingen beta, produktion, profil eller scheduler
har aktiverats eller ändrats.
