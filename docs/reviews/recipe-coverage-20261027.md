# Recepttäckning: 1 569 verifierade tvåbutikskorgar av 2 200

Delresultat från main `be0c528`, runtimecommit `7697492`, enligt
[uppdraget](../CODEX-SOL-NEXT-20261027-RECIPE-COVERAGE.md).
**100-procentsuppdraget är inte färdigt.** Alla ursprungliga 2 200 referenser
finns kvar, liksom samtliga 2 462 aktiva varianter. Inga recept, instruktioner,
ingredienser, portionsmängder eller personliga krav har skrivits om.

## Uppmätt före/efter

| Fast nämnare 2 200 | Exakt | Inklusive uttryckligen tillåtna uppskattningar |
| --- | ---: | ---: |
| Individuellt produkt-/mängdlösta före | 738 | 931 |
| Individuellt lösta efter första käll-/modellomgången | 933 | 1 520 |
| Individuellt lösta efter samlad slutkontroll | **969 (44,0 %)** | **1 569 (71,3 %)** |
| Nytillkomna / förlorade individuellt lösta | **231 / 0** | **638 / 0** |
| Verifierad komplett korg, högst två butiker | **967 (44,0 %)** | **1 569 (71,3 %)** |
| Individuellt lösta men checkout blockerad | 2 | 0 |
| Fortsatt insatsblockerade | 1 231 | 631 |
| Ej färdigkontrollerad sökning i slutkontrollen | 0 | 0 |

Uppskattningskolumnen inkluderar den exakta. 600 varianter saknar exakt
insatsstöd men har uppskattat stöd. Ytterligare två har exakt insatsstöd men
saknar godkänd exakt tvåbutikskorg. Därmed finns **602 verifierade korgar bara
i uppskattningskolumnen i denna etapps bevis**; detta är inte ett generellt
omöjlighetsbevis för en framtida exakt sökning. Ingen mängdstandard ändras.

Den första omgången frigör 589 hela varianter i uppskattningsläget. Den andra
frigör ytterligare 49. Dessa marginalvinster gäller hela ID:n; överlappande
ingrediensförekomster summeras inte.

## Fryst referens och bevis

Samma namngivna Malmöunderlag `combined-prices.json` från 2026-10-23,
SHA-256 `06cbf0b12e619f09dd3709b808916d1c74676859d246ad72f74d52d0e6d91857`,
89 458 produkter och exakt samma 52 butikskontexter. Pris-/testklockan är
`2026-10-23T06:00:02.869273+00:00`. Middagar kontrolleras för fyra portioner,
frukost/mellanmål för en, utan skafferi, extras eller personliga närings-,
allergen- och ekobegränsningar. Butikstaket är två.

Fakta har två uttryckligen nya versioner, med bevarade källtider. Nya
produktdeklarationer hämtades 2026-10-27; de gör inte de historiska priserna
nya. Basens fakta-SHA är
`914327f31e06b4c81840c3c8f79959babf8da67e1041255714514ee5a3c13516`.
Slutversion, alla kontexter, normaliserade villkor och metodhash finns i
[coverage.json](recipe-coverage-20261027/coverage.json). Där finns samtliga
ursprungs-ID:n, aktuella ID:n, båda utfallen, blockerande insatsscope,
konkreta källbehov och korgreferenser. [Blockerlistan](recipe-coverage-20261027/blockers.json)
och [kvittornas beroenden och SHA](recipe-coverage-20261027/basket-receipts.json)
hör till samma scope. De fulla, oförkortade korgkvittona ligger under den
angivna lokala checkpointkatalogen och är återbyggbara från dessa frysta data.

Den gemensamma korgkontrollen använder `PersonalPlanner.basket(final=True)`:
förpackningsavrundning, rätt butikspris, köp-/kampanjvillkor och befintlig audit.
Det är giltighetsbevis, inte globalt lägsta pris eller personligt godkännande.
Två exakta checkout-avslag passerar med tre butiker: halloumi-/aubergine-
rislagrens utökade variant, 295,35 kr, och caponata-/kikärtsbrödets utökade
variant, 283,43 kr. De ersätter inte tvåbutiksutfallen. Se
[separat diagnos](recipe-coverage-20261027/retained-review.json).

## Implementerade käll- och modellrättningar

`definition_only` är fortfarande ett behov, inte ett generellt godkännande.
Registret kan nu bära en separat granskad, exakt produkt-/formrelation och
ett separat mängdbevis. Relationerna binds till butik/priskontext, stabil GTIN eller artikelkod,
hela namnet, varumärket, kategorin och förpackningen. Det granskade
ursprungssnapshotet bevaras. Nuvarande fakta måste vara bundna till aktuell
produkt och aktuellt snapshot. Identisk sammansättning får därför återanvändas
vid en ren prisuppdatering; den nya kassan använder det nya priset. Utan
stabil identitet krävs fortfarande samma produkt/snapshot.
Ändrad sammansättning, identitetskonflikt eller saknad proveniens stoppar
relationen. Personliga fakta och prisbehörighet kontrolleras därefter som tidigare.

139 konkreta relationer för 14 råvarugrupper använder dokumenterade
populationsutbyten ur [USDA SR28](https://www.ars.usda.gov/northeast-area/beltsville-md-bhnrc/beltsville-human-nutrition-research-center/methods-and-application-of-food-composition-laboratory/mafcl-site-pages/sr11-sr28/).
Exempel är purjolök, salladslök, butternutpumpa, päron och palsternacka.
Köpets brutto-/nettovikt och receptets ätliga mängd hålls isär. Utbytena
gäller bara granskade gramförpackningar eller källbelagda representativa
viktförpackningar, i uppskattningsläget. Krukvikt, okänd styckvikt, lösvikt
utan stödd metod och tillagad vikt omfattas inte. Källextrakt, råpost,
förlustdel, hash, metod och tillämpningsscope är versionshanterade.

Den befintliga Axfood-insamlaren användes för 22 valda befintliga artikelkoder:
två bevarade dokument återanvändes och 20 relevanta dokument hämtades, alla
med verifierade svar. Samma godkända Willysbutik 2176, högst 1/s, lokalt
kommunrelälås och befintligt server-/dataplanlås användes. Inga nya butiker,
scheman, breda crawlar eller driftinställningar infördes. Slutligt immutable
arkiv är `b11ed75863be1547755ee78be5143ba737d5ea3564acc1cadaa0feb6b4ebf0a8`
under `D:/smako-data/axfood-product-details/releases/`.
Urval, före-/efterhashar och konflikter finns i källjournalerna bredvid rapporten.

Detta ger limejuicens faktiska sammansättning, naturell kvarg, jordnötssmör,
färsk potatisgnocchi och uttryckligt avrunnen kaprismängd. En verklig negativ
gnocchiartikel visade sig vara torr durumvetepasta och förblir utesluten.
Keso förlorar inte längre sitt livsmedelsnamn när varumärket också heter Keso.
Naturell kvargs källbelagda ordföljd och gnocchins färskpastabeteckning stöds.

En deklarerad GTIN i ett verifierat artikelbundet detaljdokument kan nu
återanvändas som produktfakta i befintlig leverantörskedja, utan att ändra
prisproduktens identitet. Det möjliggör [Abbas exakta deklaration](https://www.dabas.com/productsheet/07311171007013)
av 200 g netto och 150 g avrunnen tonfisk. En snedstrecksetikett ensam räcker
fortfarande inte. Rå prisidentitet, faktisk köpt nettomassa och förbrukad
avrunnen mängd förblir skilda. Femton näringskonflikter för ekologiskt
jordnötssmör bevaras; de görs inte till godkänd näring för ett personligt krav.

## Återupptagning och begränsad verifiering

`check_recipe_coverage.py` deduplicerar insatsscope och skriver atomiska
kvittor per ursprungs-ID, läge och version. Hela pris-/faktafilen, klockan,
aktuella receptet, registret, runtime/metod, villkor och kontrollprogrammet
binds till kvittot. Ändrat beroende eller skadat bevis ger omkontroll.
Ett tidsavbrott heter `search_incomplete`, aldrig PASS eller omöjlighet.
I första mätningen sparades tio avbrott. Samma version återupptogs med
tre sekunders variantgräns utan omräkning av de redan verifierade korgarna.
Efter den andra källversionen och den slutliga rättningen för prisuppdateringar
gjordes nya samlade fullkontroller; gamla beroendehashar tvingades inte att
gälla för nya fakta/metoder. Slutlig kontroll tog 213,3917 s plus 26,7559 s
för kvittoverifiering/sammanställning. Båda gav oförändrade täckningstal.

Kör från reporoten med `PYTHONPATH=backend;.;scripts/recipe_layer`, genom
`scripts/recipe_layer/budgeted_check.py` och samma befintliga budgetjournal.
Kontrollprogrammens `--help` beskriver indata och checkpointvägar. De stora
frysta pris-/fakta-/råfilerna är lokal data, inte Git-data; följ
[DEVELOPMENT](../DEVELOPMENT.md) vid återställning. Ett klonat litet testunderlag
ersätter inte dessa källor. Ingen automatisk fortsättning startas.

674 riktade regressioner passerar på slutlig runtime. Därutöver passerar
kontrollmodulens 30 slutprov efter tillagda beroende-/källkontroller; antalen
överlappar. Bland proven finns fel form/produkt/enhet, brutto kontra ätlig/
avrunnen mängd, samtycke, paketavrundning, saknad proveniens, motstridiga
deklarationer, allergi/eko och invalidering vid ändrade fakta/priser/recept.
Ruff, compileall och diffkontroll passerar. Ordinarie GitHub-CI krävs grön
på slutligt PR-huvud före mainintegration.

Alla tunga körningar är seriella i samma supervisor: två CPU, hårt 3 GiB.
Högsta observerade jobbcommit är 1 617 113 088 byte, cirka 1,506 GiB.
Även avbruten första källinventering och ett avbrutet kallt referensprov
är debiterade. Etappen använder 1 827,7125 s; journalen har totalt
7 172,6967/7 200 s använda och **27,3033 s (0,46 minuter) kvar**.
Två små publika referenshämtningar debiterades i efterhand med observerad
terminaltid, sammanlagt 6,7027 s. De är separat märkta och påstås inte vara
supervisorbegränsade prestandaprov; de stora verifieringsjobben är det.

## A/B2: giltiga sparade svar och bevarad prisreferens

Samma sparade råval, 52 butiker och tvåbutikstak används. B2 behåller hela
731,20-kronorskorgen och samtliga sparade begäransfält exakt; slutlig
API/checkout/save/GET-tid är **32,6722 s**. A ger en full sparad och återläst
korg på **52,2790 s för 290,82 kr**, med 1 508 kvalificerade kandidater jämfört
med tidigare 960. Se [A](recipe-coverage-20261027/A.json),
[B2](recipe-coverage-20261027/B2.json) och
[strikt korgjämförelse](recipe-coverage-20261027/B2-comparison.json).

Den tidigare A-receptkombinationen verifierar **297,18 kr** genom samma
aktuella planner/checkout/audit, skalad till fem middagar med fyra portioner.
Slutliga A är 6,36 kr billigare än den kända giltiga referensen. Den
begränsade sökningen bevisar fortfarande inte globalt lägsta pris.
[Referenskvittot](recipe-coverage-20261027/A-reference-checkout.json) skrevs
först efter den sparade API-planen, användes inte som sökfrö och ingår inte
i API-tiden. Det verifierar aktuell kassa, inte en ytterligare kall API-plan.

**Rättelse:** det tidigare separata referensprovet som angav 276,38 kr
saknade portionsskalning. Det beloppet jämförde fel mängder och är ogiltigt
som prisreferens. Båda referensdrivrutinerna använder nu befintlig
portionsskalning. [Rättelsekvittot](recipe-coverage-20261027/reference-correction.json)
bevarar det felaktiga bevisets hash, orsak och ersättare. Första etappens
faktiska A-resultat, 306 kr/52,3819 s på runtime `ee3d5ed`, bevaras där som
historiskt mätresultat. Slutprovet ovan kördes efter sista runtimeändringen.

Tiderna ovan är nya API-prov, inga nya browsertider. Före API:t kostade
den observerade laddningen/förberedelsen **98,5562 s för A och 80,1325 s för B2**;
detta är inte 30–60 s från tom installation. Ingen full pris-/prestandarelease
kvalificeras här. A har inga personliga näringsmål; B2:s minst 35 g protein
följer fortsatt uttrycklig ESTIMATED-policy. A:s råa globala ingrediensgräns
är fortsatt inte ett aktivt måltidsbundet 10–15-krav.

## Vad som återstår till 2 200

631 varianter blockeras av 78 grupper även när uppskattningar är tillåtna.
Störst är mynta (131, varav 83 med enbart denna kvarvarande grupp),
tamarindpasta (93/53), masa harina (31/31), avrunnen mozzarella (30/30),
pärlkorn (27/24) och citrongräs (27/15). Sista talen är villkorade övre
marginaler, inte genomförda vinster. Samtliga sällsynta grupper och varje
berört ID finns i blockerlistan.

Mynta behöver ett bevis som gäller den faktiska blad-/stjälkpresentationen;
rotad kruka och torr krydda godkänns inte. Den bevarade tamarindprodukten är
ett 435-ml-koncentrat, inte styrkt kärnfri osötad pasta med receptets styrka
i gram. Masa harina-träffarna är bland annat masala, inte nixtamaliserat
majsmjöl. Flera sällsynta varor saknar en verifierad SKU i det frysta
sortimentet. Detta är konkreta käll-/retrieval-/sortimentshinder, inte ett
bevis att varan saknas på hela marknaden. Gör inte om samma fruktlösa sökning
eller minska nämnaren. Ett annat sortiment eller ett kulinariskt granskat
receptalternativ kräver ett eget deklarerat scope och bevarade original-ID:n.

Fortsatt prioritet är dessa källgap tills de stängts eller ett precist
externt hinder kräver ägarens beslut. Återstående 27,3 s räcker inte för
en ny källfamilj och samlad verifiering. Enbart upprepad fullkontroll och
sammanställning kostade senast cirka fyra minuter, före källarbete; nya
A/B2-prov kräver dessutom cirka 4,5 minuter inklusive laddning. Fortsätt
från angivna checkpoints med faktiska källbelägg och en ny uttrycklig budget,
inte genom att nollställa den befintliga. Legacy är fortsatt standard, V2 opt-in. Ingen
beta, produktion, profil eller scheduler har aktiverats eller ändrats.
