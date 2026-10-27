# Fler verifierade receptkorgar genom granskade förpackningar

**1 784 av 2 200 hela korgar inklusive uppskattningar**, +37 mot PR #25.
Exakt läge har 1 049 hela korgar och 1 051 insatslösta varianter (+29).
416 varianter har fortfarande insatshinder. Alla 2 200 original och
2 462 aktiva varianter består, utan förlorade tidigare korgar. Detta är en
kontrollpunkt inom det fortsatta uppdraget, inte full recepttäckning.

| Produkt i CityGross Malmö Hyllie | Artikel / GTIN | Netto / avrunnet |
| --- | --- | --- |
| Falkenberg stora handskalade räkor | 101334340_ST / 7340083487538 | 400 / 200 g |
| Falkenberg handskalade räkor | 101690222_ST / 7311043015993 | 280 / 140 g |
| Monte Castello kronärtskockshjärtan | 101602829_ST / 7311043010936 | 400 / 240 g |
| Sevan vinblad i lag | 101243232_ST / 7331217011699 | 620 / 350 g |
| Stollenwerk surkål | 101194302_ST / 4068500810242 | 680 / 650 g |

Fem nya relationer är bundna till exakta produkt-, kontext- och snapshot-ID:n.
[Räkgranskningen](reviewed-drained-foods-20261027/shrimp-review.json) binder
visuellt lästa originaletiketter och leverantörsuppgifter till exakta GTIN
från det redan verifierade Axfoodarkivet. De kokta, skalade räkorna är
uttryckligen färdiga att använda. Råa eller oskalade räkor kvalificeras inte.
Katalogens befintliga varumärkesfält bevaras även där de är missvisande.

[Konservgranskningen](reviewed-drained-foods-20261027/preserved-review.json)
håller varje fälts källbevis separat. Deliteas primära kronärtskockssida anger
uttryckligen netto/avrunnet och EAN, och den färska exakta Axfooddeklarationen
bekräftar förpackningsetikett och hela innehållet. Sidans lästa webbextrakt är
märkt med verktygets fyra månader gamla crawl, inte en ny lyckad HTTP-hämtning.
Den lokala direkthämtningen fick 403 och kringgicks inte.

Sevans aktuella tillverkarsida och visuellt lästa etikett visar rätt konsument-
GTIN och 620/350 g. Ingredienstexten stämmer med det färska artikeldokumentet:
NATRIUMDISULFIT. Äldre återförsäljartext med KALIUMDISULFIT används inte som
fakta. Tillverkarens olika näringsuppgifter kvarstår som uttrycklig
supplier_nutrition_conflict; inga näringsvärden eller avrunnen näringsgrund
godkänns. Kartongens x12 räknas inte som en konsumentförpackning.

Stollenwerks tillverkarkatalog, visuellt kontrollerad sida 21, anger artikel
81212, konsument-GTIN, 680 g netto och 650 g avrunnet. 720 ml avser glasets
storlek och används inte som livsmedelsvolym eller densitet. Katalogens
publiceringsdatum är okänt. Den färska exakta Axfooddeklarationen bekräftar
680/650 g och hela innehållet vitkål/salt.

Befintlig projektion av granskad deklarerad avrunnen massa accepterar nu
även cooked_drained, förutom preserved_drained. Alla tidigare bindningar,
sammansättningshashar och mängdkonfliktsspärrar gäller. Nettoköp, avrundning,
pris, butik och källtid ändras inte. Exakt deklarerad mängd behöver inget
uppskattningsval. Osäkra populationsutbyten gör det fortfarande. Fullständiga
ingredienser ger inga allergen-, eko- eller näringsgodkännanden.
Inga recept, gram, tillagningstider eller prisposter har ändrats.

| Slutprov, separat ny ägare | Korg | API/save/GET | Separat förberedelse |
| --- | ---: | ---: | ---: |
| A | 281,31 kr | 52,00 s | 97,53 s |
| A, oberoende återprov | 281,31 kr | 52,16 s | 76,23 s |
| B2 | 731,20 kr | 32,58 s | 77,77 s |

A och B2 använder identiska fullständiga sparade begäranden. Även de första
slutprovens hela optimerade korgar är identiska med föregående kontrollpunkt.
Samtliga passerar checkout-audit och A:s prisgrind. Tiderna är separata
lokala Windowsprov med två CPU och 3 GiB, inte p95 eller samtidighetsprov.

52 riktade regressioner passerar i den sparade slutkörningen, inklusive
fem verkliga produktfall med fel form, ändrad sammansättning/snapshot,
mängdkonflikt, paketavrundning och personliga spärrar. Ruff och compileall
passerar för alla fyra ändrade Pythonfiler. CI-partitionerna innehåller
samtliga 4 100 aktuella testnoder exakt en gång. Hosted CI krävs före merge.
Ny full bibliotekskontroll tog 229,72 s och verifieraren kontrollerade alla
2 835 kvittofiler och aktuella beroenden. Två exakta checkout-avslag under
tvåbutikstaket kvarstår och räknas inte som godkända.

Referensen är oförändrat Malmö: 89 458 produkter, 52 kontexter, klockan
2026-10-23T06:00:02.869273+00:00, fyra middagsportioner, en frukost-/mellanmåls-
portion, högst två butiker och inget skafferi. Faktaversionens SHA-256:
f3d272dd0978101582386c3aeba92a1705a3126355af73494cbb1aba6ce4ad39. Metod: 1e6bd1c73f31acef2a4f4384d118084643346c1357c8267acda0e4c02e24fe92.
[Verifiering](reviewed-drained-foods-20261027/verification.json),
[nya hela korgar](reviewed-drained-foods-20261027/newly-verified.json) och
[kvarvarande källbehov](reviewed-drained-foods-20261027/blockers.json).

Samma obegränsade totaljournal bevarar all historik, även misslyckade prov.
Per-operation-watchdog, en tung arbetare, resursgränser och operationslås
består. Ingen beta-/produktionsaktivering, scheduler-, profil- eller
allowliständring. Legacy är standard och V2 opt-in; Coop 730400 är Online Syd.

Arbetet fortsätter med faktisk saknad mängd-/sortimentsevidens och gemensam
beredning av exempelvis äggdelar. Saknad träff i denna referens betyder inte
att varan saknas på marknaden. Alla 76 ursprungliga grupper finns kvar i
[arbetsmatrisen](reviewed-drained-foods-20261027/work-matrix.md).
