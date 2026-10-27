# Fortsättning: ordinarie viktpris och 1 649 fullkorgar

Fortsättning efter PR #21/main `e8520bf`, på ägarens ”Fortsätt”. Samma etappbudget
används. Målet om alla 2 200 importerade varianter är **inte färdigt**.

## Resultat i oförändrad referens

| Mått | Före | Efter |
| --- | ---: | ---: |
| Exakt: individuellt lösta insatser | 1 010 | 1 010 |
| Exakt: verifierad hel tvåbutikskorg | 1 008 | 1 008 |
| Inklusive tillåtna uppskattningar: lösta insatser | 1 646 | 1 649 |
| Inklusive tillåtna uppskattningar: verifierad hel tvåbutikskorg | 1 646 | 1 649 |

Alla 2 200 originalreferenser och 2 462 aktiva varianter är bevarade. Inga
tidigare verifierade korgar eller insatslösta varianter har försvunnit i något
läge. Inga avbrutna eller oprövade korgar räknas som klara. **551 varianter/68
grupper återstår i uppskattningsläget.** De tre nya korgarna är simple,
standard och extended av `smako-swedish-whole-beef-mushroom-puff-shell`.

Malmöreferensen är fortfarande 89 458 produkter/52 kontexter, fyra portioner
middag och en frukost/mellanmål, högst två butiker och inget skafferi.
Klockan är `2026-10-23T06:00:02.869273+00:00`. Inga priser, observationstider,
produktfakta, recept eller tillåtna inköpskontexter har ändrats.

- Prisfil SHA-256: `06cbf0b12e619f09dd3709b808916d1c74676859d246ad72f74d52d0e6d91857`.
- Fakta SHA-256: `30fd1d335bc43c4c67fad89aebcece4ae970106268b9a7cf8a64fa5cbb1ae0cd`.
- Aktuell metod: `44adc0cb5d91d875b2d8d2d94ef85eabebce0a5e6bfb8f4b03c95860f98557ff`.
- Fullständigt scope: `97f970eae2b1a7c0bf420b2f0c8fca2001a1f02aeba42d41b8b082dc26048361`.

## Prisrättningen

Fyra redan granskade Naturkött-artiklar, hel oxfilé 1 800 g, stoppades när ett
kg-erbjudande utan verifierad rabattgränsenhet skickades till paketprisvägen.
De har ett separat ordinarie pris på 369 kr/kg. `user_pricing` använder nu det
priset via befintlig prisresolver när ordinarie taxa, viktform och känt
mängdunderlag är belagda. Okänd mängd, jämförpris ensamt, paketpris, blandade
prisenheter och andra obestyrkta erbjudandeformer godkänns inte av denna väg.

Den obelagda medlemstaxan 269 kr/kg med gränsen tre ligger kvar som
källmetadata och tillämpas inte. Ett identifierarprefix får inte skapa en
paketgränsenhet eller nya `PurchaseTerms`. Den redan befintliga vägen för
källbelagda paketgränser fortsätter ge korrekt rabatt. Separata gränser för
antal köpta varor och kravet på explicit uppskattningsval gäller fortfarande.

Befintlig `PurchaseQuantityResolver` avrundar till hela representativa paket:
800 g behov köper ett uppskattat 1 800-g-paket för 664,20 kr och redovisar
1 000 g överskott. Detta är varken ett exakt vägt köp eller 369 kr per paket.
Skafferibokföringen kräver faktiskt uppmätt mängd även när `purchase_terms`
saknas. Testet bekräftar att en uppmätt vikt 1 710 g lagras och att det
sparade köpkvittots beräkningsunderlag fortfarande är märkt uppskattat.

## Källarbete och de två exakta avslagen

Ett separat, redan insamlat Willys Malmöarkiv från 2026-10-27 verifierades
med befintlig `verify_source_artifact`: identitet, kommun/butiker, payloadhashar,
insamling, parser, produktantal och källålder. Alla 74 ingrediensnamn granskades
mot 3 051 unika butik/artikel-träffar. Inga nya kvalificerade varor löser de
kvarvarande hindren. Den nya myntaträffen var en kattleksak; nya köttstyckningar
täcker redan stödda former. Övriga nya träffar omfattar råa hela ägg,
riven mozzarella/färdig mat, smaksatta färdiga popcorn, torrt kaffe och
irrelevanta delsträngsträffar. Ingen namnsökning fick skapa en produktkoppling.

Detta är ett separat källscope, inte nya priser i referensen eller bevis för
frånvaro på hela marknaden. [Källgranskningen](recipe-weight-coverage-20261027/new-source-review.json)
bevarar artikel-ID:n, observationer och källhash. Samma tillåtna 44-artikelskö
försöktes en gång i fortsättningen och stannade vid upptagen lokal
kommunrelälease: **noll handlaranrop**. Inget lås eller driftläge ändrades.

De två tidigare exakta checkout-avslagen har nu en konkret diagnos. Efter
riktig mängdberäkning och exakt-korgpolicy har båda noll täckande en- eller
tvåbutiksuppsättningar; minsta uppsättning är tre butiker. Separata diagnostiska
korgar passerar audit med 298,79 respektive 296,27 kr. De räknas inte in i
referensens tvåbutikstäckning. Halloumi-/auberginerätten har åtta kvalificerade
trebutiksuppsättningar, caponata-/kikärtsrätten nio.
[Diagnosen](recipe-weight-coverage-20261027/exact-store-gap.json) innehåller
hela kandidat-/korgmängdsskillnaden och butiksgrafen.

## A/B2 och verifiering

| Fall | Pris | API, sparning och GET | Separat förberedelse |
| --- | ---: | ---: | ---: |
| A | 283.24 kr | 52.19 s | 97.46 s |
| B2 | 731.20 kr | 34.55 s | 76.40 s |

Båda fullständiga sparade begärandena är identiska med PR #21:s prov.
B2:s hela optimerade korg är också identisk. A:s prisförbättring består,
7,58 kr under den tidigare verifierade 290,82-kr-referensen. HTTP 201,
sparning, återläsning och checkout-audit passerar. Windows in-process TestClient,
två CPU och hårt 3 GiB; ingen browser-, Linux-, samtidighets- eller generell
60-sekundersgaranti och inget bevis för globalt lägsta pris påstås.

644 riktade regressioner passerar (fyra sedan tidigare markerade xfail),
plus ett nytt skafferifall. Den slutliga nya testfilen passerar alla 28 fall
utan varningar. Ruff och compileall passerar. Alla **2 659 kvittofiler**,
beroenden, sparade begäranden, recept-ID:n och tidigare journalhashar är
kontrollerade. Samma slutliga metod gäller hela biblioteket och A/B2.
Verifieraren kontrollerar nu också att inga tidigare verifierade korg-ID:n
förlorats och kan läsa den gemensamma fortsatta budgetjournalen separat.
Ordinarie GitHub PR-CI krävs före integration; se PR:s aktuella status.

[Verifieringsdata](recipe-weight-coverage-20261027/verification.json),
[hela täckningen](recipe-weight-coverage-20261027/coverage.json),
[kvittoindex](recipe-weight-coverage-20261027/basket-receipts.json),
[tre nya korgar](recipe-weight-coverage-20261027/newly-verified.json) och
[uppdaterade 76 ursprungsgrupper](recipe-weight-coverage-20261027/work-matrix.md).
Fulla offentliga benchmarkkorgar och råa källor ligger kvar lokalt under
`.local/recipe-weight-coverage-20261027/`; de är inte privata konsumentkvitton.

## Budget och återstående arbete

Journalen är fortfarande `recipe-coverage-full-20261027/budget.json`:
**2417.2708 s använda, 1182.7292 s kvar av 3 600 s**.
Fortsättningen har använt 1105.9030 s.
Alla misslyckade prov och omkörningar är debiterade. En tung lokal arbetare
har använts åt gången, med minst 600 s reserverat före slutkontrollerna.
Ordinarie hostad PR-CI redovisas separat från lokal referensbudget.

De 25 posterna vid PR #21 är oförändrade prefix i samma journal; två äldre
etappers journaler är hashstabila. PR #21:s leveransmanifest beskriver sin
historiska budgetpunkt och ersätts inte i efterhand. Den fortsatta journalens
aktuella hash ingår i denna kontrollpunkts leveransmanifest.

Full beredning med äggkomponenter, torrt till kokt och bryggt kaffe återstår.
Den granskade [beredningsspecifikationen](recipe-coverage-full-20261027/preparation-review.md)
kräver samköp, separata utfall, använda näringsmängder, tid och uppmätt
skafferibokföring; ingen ofullständig omvandling har aktiverats. De stora
faktaluckorna för mynta, tamarindpasta, masa harina och pärlkorn kvarstår.
De är varken lösta genom ett lägre kvalitetskrav eller ett beslut att byta
handlare/källscope. Det låsta källarbetet får återupptas när ordinarie drift
är klar. Nästa implementation ska stanna i befintliga modeller.

Legacy är fortsatt standard och V2 opt-in. Ingen beta-/produktionsaktivering,
schedulerändring, ny tilldelning eller automatisk fortsättning ingår.
