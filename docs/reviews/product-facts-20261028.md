# Produktfakta och jämnare CI, 2026-10-28

**1 802 av 2 200 hela korgar inklusive uppskattningar**, +18 mot PR #26.
Exakt läge har 1 062 hela korgar och 1 064 insatslösta varianter (+13).
398 varianter har fortfarande insatshinder. Alla 2 200 ursprungliga
referenser, 2 462 aktiva varianter och tidigare korgar består. Full täckning
är fortsatt målet; detta är en verifierad kontrollpunkt.

| Granskad vara | Identitet och form | Exakta kontexter |
| --- | --- | ---: |
| Garant breda risnudlar | Artikel 101716026_ST, GTIN 7311043018758, 250 g; platta torra risband, ris/vatten | 9 CityGross/Willys/Hemköp |
| Eldorado sardiner i solrosolja | Artikel 101321848_ST, GTIN 7340083483448, 120 g netto / 85 g avrunnet | 9 CityGross/Willys/Hemköp |
| Ahmad Tea Ceylon löste | Artikel 101254695_ST, 500 g; tillverkaren anger Black tea, etiketten LOOSE TEA | 1 CityGross Malmö |

[Källgranskningen](product-facts-20261028/source-review.json) binder hela
varumärket, varianten, nettovikten, artikeln och aktuell sammansättning.
Risnudlarnas exakta GTIN och fullständiga deklaration bekräftas av det redan
verifierade Axfoodarkivet. Leverantörens originalfoto visar platta risband;
ingen numerisk bredd härleds. Sardinetikettens deklaration är **85 g**, läst
på originalbilden i 1000 pixlar; en liten miniatyr räcker inte för mängdbevis.
Tempo Runmarös primära artikel bekräftar samma GTIN/artikel/netto. Mathems
leverantörstext anger sardiner, solrosolja och salt. Tomatsås är separat.

Ahmad Teas egen sida anger osmaksatt svart te för Ceylon 500-g-lösviktsvarianten.
Originalbilden har visuellt verifierade ord Ceylon Tea, 500 g och LOOSE TEA.
Den exakta CityGrossartikeln saknar GTIN; inget hittas på för den. Relationen
är manuellt granskad mot full variant/netto och bunden till artikel/kontext.
Det är receptens torra processmängd till rökning, inte en bryggd dryck eller
ett antaget volymutbyte. Inga prisuppgifter från dessa externa sidor används.

En generell torrhetsheuristik nekade Garants verkliga torra nudlar därför
att vatten står i ingredienslistan. Den tillåter nu sådan tillverkningsvatten-
deklaration endast efter en exakt granskad relation för torr form, med samma
sammansättning och källidentitet. Kokt/färdig vara och ogranskade relationer
fortsätter nekas. Det nya positiva regressionsfallet föll före rättningen.
Sardiner använder den befintliga deklarerade avrinningsvägen. Alla gamla
registerrader består; exakt 19 länkar har lagts till.

[Kontrollen av fakta](product-facts-20261028/facts-preservation.json) bekräftar
att bara 19 avsedda poster ändras/tillkommer. Alla andra produktfakta och
befintliga personliga/näringsfält är identiska. Sardinernas näring för avrunnen
fisk är fortfarande okänd. Nya poster har inga allergen- eller ekogodkännanden.
Inga recept, tillagningstider, prisposter, butiksscope eller observationstider
har ändrats. [Ytterligare källfynd](product-facts-20261028/additional-source-findings.json)
redovisar bland annat styrkt äggvitenettovikt men ofullständig/motstridig
sammansättning; den aktiveras inte som färdig lösning.

## Prisgrind och återanvänt arbete

Ett tidigare återprov gav 283,24 kr och stoppade kontrollkedjan före B2 och
bibliotekskontrollen. [Alla fyra A-prov](product-facts-20261028/search-timing-review.json)
är bevarade. Ingen dyr provkorg eller benchmarkmeny används som sökfrö.

Två rena funktioner för normaliserad offentlig namn-/kategoritext återanvänder
nu sina oföränderliga sträng-/tuple-resultat, med högst 8 192 poster vardera.
De läser inga priser, personliga profiler eller produktfakta. Alla 89 458
produkters kompletta klassningssvar, bevis och säkerhetsnivåer är identiska
före/efter. Den isolerade kontrollen gick från 29,53 till 25,04 s enligt
[jämförelsen](product-facts-20261028/text-classification-equivalence.json).
Det är inte en uppmätt generell API-förbättring. Menysökningen behåller
kandidater, villkor, deadline och tolv sekunders slutreserv; inget globalt
optimum påstås.

| Slutprov med separat ny ägare | Korg | API/save/GET | Separat förberedelse |
| --- | ---: | ---: | ---: |
| A | 281,31 kr | 52,04 s | 96,31 s |
| A, oberoende återprov | 281,31 kr | 53,76 s | 75,83 s |
| B2 | 731,20 kr | 32,36 s | 76,33 s |

Hela sparade begäranden är identiska med föregående kontrollpunkt. B2:s hela
optimerade korg är identisk. Samtliga slutprov passerar checkout-audit och
A:s prisgrind. Detta är separata Windowsprov med två CPU och 3 GiB, inte
p95 eller samtidighet. Förberedelse före anrop redovisas separat, inte dold
som om den ingick i ett levererat resultat på 30–60 sekunder.

## CI och verifiering

[PR #26](https://github.com/ossebosse/smako/pull/26) är integrerad som main
5c329aa. Dess hosted CI tog 11:41, alla 4 100 tester ingick, noll fel och
63 skip/xfail. [Jobbtiderna](product-facts-20261028/pr26-hosted-ci.json) visar
cirka 604 s för core-teststeget och 353 s för planner. Fem uppmätt långsamma
filer, sammanlagt 214,57 s testtid, flyttas därför till en tredje obligatorisk
partition. Den startar inga webbläsare och slipper browser-/systeminstallationen.
Nya testfiler hamnar automatiskt i core; alla tre partitioner krävs av backend.
Det nya hosted utfallet måste mätas i denna PR, inte antas från filernas tider.
[Underlag](product-facts-20261028/ci-balancing-review.json) och
[alla 4 103 testnoder exakt en gång](product-facts-20261028/ci-partitions.json).

338 riktade tester och Ruff/compileall för fem ändrade Pythonfiler passerar.
Ny full kontroll och hashverifiering omfattar 2 866 kvittofiler med aktuella
beroenden. Ett exakt fall var först search_incomplete vid en sekund och
kördes om med tre sekunders beräkningsutrymme; alla övriga giltiga kvitton
återanvändes. Inga ofärdiga sökningar räknas som godkända. Två tidigare
exakta checkout-avslag under tvåbutikstaket kvarstår och räknas inte in.

Samma frysta Malmöreferens gäller: 89 458 produkter, 52 kontexter,
2026-10-23T06:00:02.869273+00:00, fyra middagsportioner, en frukost-/mellanmåls-
portion, högst två butiker och inget skafferi. Fakta-SHA: b56734ee54f2453c5e14bb1cbd38a1404ddd4a201259c51a15a88bfda09765e3.
Metod: 249dbc07d415409a312427445504480a2e6dd5580ac267acfab9f9b6f1af65b3.
[Full verifiering](product-facts-20261028/verification.json),
[nya korgar](product-facts-20261028/newly-verified.json) och
[kvarvarande hinder](product-facts-20261028/blockers.json).

Samma obegränsade totaljournal bevarar all historik, inklusive misslyckade
prov. En tung arbetare, watchdog, två CPU, 3 GiB och operationslås består.
Ingen beta-/produktionsaktivering, scheduler-, profil- eller allowliständring.
Legacy är standard, V2 opt-in; Coop 730400 är fortsatt Online Syd. Granskningen
av dess försvunna köpbegränsningsfält medför inget undantag från kvalificering.
Arbetet fortsätter med återstående verkliga mängd-/sortimentsluckor och
berednings-/skafferistöd. Saknat SKU i referensen betyder inte marknadsfrånvaro.
