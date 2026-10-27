# Mynta, tamarindpasta, masa harina och pärlkorn — 2026-10-27

Utgångspunkt: main `8dac239`, efter PR #22. Ägaren bad om konkret granskning
av de fyra råvarorna och visade myntaprodukter hos Hemköp och Coop.
**68 nya hela receptkorgar är verifierade: 1 717 av 2 200 inklusive
uppskattningar, från 1 649.** Den exakta nivån är oförändrad: 1 010
insatslösta och 1 008 hela korgar. Inga tidigare verifierade original-ID:n
har förlorats. 483 varianter/68 grupper återstår; full täckning är inte klar.

**Prisregressionen är rättad och leveransgrinden passerar.** A kostar nu
281.31 kr mot tidigare 283,24 kr; en separat körning med ny ägare och
nytt sparläge ger 281.31 kr. B2 behåller exakt hela sin korg på
731.20 kr. Slutlig integration av [PR #23](https://github.com/ossebosse/smako/pull/23)
följer godkänd CI. Det tidigare underkända resultatet 295,41 kr finns kvar
som historiskt bevis i commit `a58973a` och `A-price-regression.json`.

## Vad som ändrats

Originalen skiljer på 91 varianter med ”Mynta, rå ätlig vikt” och 40 med
uttryckligen plockade blad. Importregistret hade lagt båda under samma
bladkrav. De 91 generiska varianterna har fått nya versioner med ett eget
krav på ansade blad och mjuka stjälkar. Ingrediensgram, andra råvaror och
befintliga tillagningsmoment består. Sköljning, borttagning av grova/skadade
delar och vägning efter ansning är nu uttryckliga; en aktiv minut har lagts
till. Alla gamla receptbytes finns kvar med sina ursprungliga hashvärden.
De 40 bladrecepten behåller både innehåll och striktare produktkrav.

[Norska Matvaretabellen, post 06.259](https://www.matvaretabellen.no/mynte-ra/)
anger 85 procent ätlig del för rå mynta, Mentha L., med FoodEx2-delen blad
och andra mindre växtdelar. Granskningen tillämpar detta som en
**populationsuppskattning för ansad mynta**, aldrig som exakt bladmassa.
Det innebär 21,25 g beräknad användbar mängd per köpt 25-g-förpackning.
En efterfrågan på 25 g ansad mynta kräver två sådana förpackningar.
Faktiskt ansad mängd ska vägas i köket.

Tio individuellt granskade produkt-/butiksposter använder befintlig
mängdprojektion och exakt identitetskontroll: åtta i Malmöreferensen och
de två separata Lundexempel som ägaren visade. Hemköps artikel är
`101599969_ST`; Coops GTIN är `7300156599834`. Coop är fortsatt
**Coop Online Syd 730400**, online fulfillment, inte fysisk hyllpriskontext.
Köpt bruttovikt, priser och observationstider ändras inte. Krukor, torkad
mynta, te, kattprodukter och andra ej granskade förpackningar godkänns inte.
Inga allergen-, eko- eller näringsdeklarationer har skapats av schablonen.

Den här skillnaden löser myntainsatsen i 91 varianter. 68 har därmed en
fullständigt verifierad korg; 23 har andra hinder kvar. Alla 2 200
ursprungsreferenser och 2 462 aktiva varianter består. Jämförelsen tillåter
bara den uttryckligt registrerade övergången mellan manifesten och exakt
uppsättning efterföljande recept-ID:n. Gamla kvitton godkänner aldrig de
nya receptversionerna.

## De andra tre varorna

| Vara | Faktiskt fynd | Kvarvarande uppgift | Varianter där detta nu är enda ingredienshindret |
| --- | --- | --- | ---: |
| Tamarindpasta | Chua Hah Seng Tamarindpaste Sour Concentrate, artikel `101674821_ST`, 435 ml, finns i sju referensposter. | Exakt förpacknings nettovikt eller tillämplig densitet, samt granskad koncentration och kärnfri sammansättning. Recepten efterfrågar gram pasta; ml får inte räknas som g. | 63 |
| Masa harina | Befintligt P.A.N.-mjöl `101365159_ST`/`7591002000547` är förkokt majsmjöl. | Ett exakt prissatt nixtamaliserat mjöl från tillåten källa. Vanligt majsmjöl/polenta ersätter inte originalreceptens masa harina. | 31 |
| Pärlkorn | GoGreen `101188530_ST`/`7310130002885`, 500 g, är klippta korngryn. Urtekram har en tillverkardeklarerad matchande pärlkornsprodukt, artikel 1012040, 400 g. | Koppla en matchande hel polerad kornprodukt till ett exakt prissatt SKU i tillåten kontext. Titelordet ”korngryn” i vissa recept får inte ändra ingredienskrav, vatten eller kokförlopp. | 24 |

Källor och avgränsningar finns i [den konkreta fyravarugranskningen](recipe-four-staples-20261027/source-review.json).
Tillverkaren beskriver [P.A.N. som förkokt majsmjöl](https://us.allofpan.com/product/pre-cooked-white-corn-meal-2lb-gluten-free/).
[Coops GoGreen-deklaration](https://www.coop.se/handla/varor/skafferi/flingor-m-sli/gryn/korngryn-7310130002885/)
anger klippt korn; [Urtekrams pärlkorn](https://www.urtekram.se/mat/ris-gryn--pasta/parlkorn/)
anger polerade kornkärnor. Dessa produktledtrådar importerar inga nya priser.
Saknat kvalificerat SKU i vårt underlag betyder inte att varan saknas på marknaden.

Det meningsfulla manuella arbetet är därför att komplettera tre precisa
produkt-/förpackningsuppgifter, inte att reda ut hundratals korgar var för
sig. Antalen i tabellen är villkorad potential, ingen utfästelse om
verifierade nya korgar. 40 bladmyntavarianter återstår, varav 28 har enbart
det hindret.

## Verifiering och avgränsning

Samma Malmöprisfil används: 89 458 produkter, 52 kontexter, klockan
`2026-10-23T06:00:02.869273+00:00`, fyra middagsportioner, en frukost-/mellanmålsportion,
högst två butiker och inget skafferi. Faktafilens SHA-256 är oförändrad:
`30fd1d335bc43c4c67fad89aebcece4ae970106268b9a7cf8a64fa5cbb1ae0cd`.
Ny metodhash:
`70c233f8440dac886eeb8644da1e4583bb373e968e58c91e3e919001a81cefb5`.

En ny full genomgång med slutlig runtime har kontrollerat båda mängdlägena
för samtliga 2 200 originalreferenser, med tre sekunder per enskilt
korgförsök. Inga ofullständiga sökningar återstår. Två tidigare exakta
checkout-avslag kvarstår under tvåbutikstaket och räknas inte som godkända.

Sökrättningen återanvänder oförändrad prioritet per måltidsplats inom samma
anrop. Tidigare räknades samma pris-/preferensprioritet om för varje ankare.
Ingen ny rangordning, kandidatgräns, receptspecifik regel eller benchmark-
startmeny har införts. Tidsgränsen och tolv sekunder för slutkontroll består.
Dagsspecifika prioriteter hålls isär även när receptet är detsamma.

De fullständiga sparade A/B2-begärandena är oförändrade. A gav
**281.31 kr på 52.05 s** API/save/GET efter
96.93 s separat förberedelse. Den andra kalla
A-körningen gav **281.31 kr på 52.16 s** efter
77.77 s förberedelse. B2 gav **731.20 kr på
33.41 s** efter 77.72 s förberedelse;
hela dess sparade korg är identisk. A hann pröva
70 respektive
92 hela menyer,
mot 54 i det underkända provet. Detta är lokala singelprov med två CPU:er och
3 GiB minnesgräns, ingen garanti för p95, samtidighet eller globalt optimum.

[Den historiska prisregressionen](recipe-four-staples-20261027/A-price-regression.json),
[rättningen och de två nya A-proven](recipe-four-staples-20261027/A-regression-resolution.json),
[91 versionsändringar och 40 bevarade bladrecept](recipe-four-staples-20261027/recipe-review.json)
och [fyravarugranskningen](recipe-four-staples-20261027/source-review.json)
håller källor, recept och prisvalidering spårbara. Leveransverifieraren
behåller den strikta prisgrinden; ingen tolerans har lagts till.

Ägaren godkände uttryckligen ”Utöka med 15 minuter och slutför”. Samma
budgetjournal har därför utökats från 3 600 till **4 500 sekunder**, utan
nollställning av tidigare arbete. Misslyckade prov och ny verifiering ingår.
Ordinarie hostad PR-CI redovisas separat.

Legacy är fortsatt standard och V2 opt-in. Ingen ny priskälla, utvidgad
Coop-allowlist, liveinsamling från handlare, produktion/beta-aktivering
eller schedulerändring ingår.

Slutkontrollen har verifierat **2 727 kvittofiler** och samtliga aktuella
beroenden. B2:s hela sparade korg är identisk. Båda exakta Lundprodukterna
passerar den uppskattade mängdkopplingen och avvisas som bevis för blad-only
eller exakt ätlig massa. **530 unika riktade testfall** passerar: 504 tidigare hashstabila fall
och 26 sökregressionstest, inklusive ett nytt prov för cache per måltidsplats.
Ruff och compileall passerar. Hostad PR-CI är separat från detta.

Journalens slutpunkt är **3991.5507 s använda, 508.4493 s kvar av
4500 s**. Förlängningen är bokförd med ägarens beslut. Samtliga 2 727
kvittoberoenden och A/B2-prisgrindar passerar efter rättningen; ingen
produktionsaktivering ingår.

[Verifieringsstatus](recipe-four-staples-20261027/verification.json),
[68 nya hela korgar](recipe-four-staples-20261027/newly-verified.json),
[Lundexemplen](recipe-four-staples-20261027/lund-user-examples.json),
[hela täckningen](recipe-four-staples-20261027/coverage.json) och
[alla ursprungliga grupper](recipe-four-staples-20261027/work-matrix.md).
