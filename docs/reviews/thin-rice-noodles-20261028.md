# Tunna torra risnudlar: verifierad täckning, 2026-10-28

**1862 av 2 200 hela korgar inklusive uppskattningar**, 0 fler
än efter PR #30. Exakt läge har 1066 insatslösta och 1064 hela
korgar, 0 nya hela. 338 varianter har fortfarande insatshinder.
Alla original, 2 462 aktiva varianter och tidigare verifierade korgar består.
Full täckning återstår. Den nya produktkopplingen löser risnudelkravet i tre
varianter; deras andra kvarvarande krav redovisas i arbetsmatrisen. Antalet
nya hela korgar ovan är uppmätt, inte antaget från produktträffarna.

## Källor och avgränsning

Två exakta befintliga artiklar får granskade relationer till risvermicelli
i torr form: Farmer 1 mm, 400 g, i sex kontexter och Bamboo Tree 1,2 mm,
400 g, i åtta. Axfoods fullständiga produktdeklarationer och ursprungliga
etikettbilder binder artikel, konsument-GTIN, innehåll och paketstorlek.
Farmer blötläggs före tillagning. Bamboo Tree har kompletterande exakt
GTIN-belägg för torr förvaring och åtta minuters kokning. Bildens ord
”fresh” behandlas därför inte som kokt våt massa. Bild- och källhashar finns i
[källgranskningen](thin-rice-noodles-20261028/source-review.json).

Innehållsandelar och näringsvärden för Bamboo Tree skiljer sig mellan
Axfood och [Delitea](https://www.delitea.se/bamboo-tree-risvermicelli-12mm-400g).
Näringen förblir okänd och konflikten finns kvar uttryckligen. Ingen
ekologisk status, animalisk klassning eller allergifrihet antas. Samma
ingredienskomponenter och 400-g-paket ger inte godkännande för breda eller
uttryckligen runda nudlar. Endast den tunna formen kvalificeras.

Golden Dragon-artikeln 101195653_ST saknas i det avgränsade Willys-anropet.
Det visar inte frånvaro på marknaden eller i City Gross. Primära
leverantörsuppgifter för EAN 7300009507009 skiljer sig om tillsatt salt;
produkten får ingen ny relation. Se
[CT Food](https://ctfood.se/rice-vermicelli-bun-gao-30x400g-golden-dragon/) och
[Nordlie Food](https://nordliefood.dk/asiatiske-specialiteter/asiatiske-specialiteter-asiatiske-specialiteter/bun-gao-vermicelli-ris-nudler/).

Insamlingen skedde med befintliga lokala och serverbundna operationslås,
efter att föregående operation avslutats. Två artiklar hämtades, en misslyckades.
Inga priser, prisobservationstider, recept, tillagningstider eller runtimevägar
ändras. De frysta produktobjektens saknade GTIN fylls inte i på gissning;
leverantörens GTIN binds genom den redan belagda artikelidentiteten.
Alla övriga fakta och personliga fält är bevarade i
[beviset](thin-rice-noodles-20261028/facts-preservation.json).

En separat [direkt namnsökning](thin-rice-noodles-20261028/literal-candidate-audit.json)
över alla 89 458 referensprodukter hittar inga rispappersartiklar eller
nya kvalificerade produkter för de större torrvarugrupperna. Bland träffarna
finns färdigmat och andra varugrupper; de godkänns inte. Detta gäller den
frysta referensen, inte marknadens hela sortiment.

## Verifiering

| Prov | Giltig korg | API, sparning och återläsning | Separat förberedelse |
| --- | ---: | ---: | ---: |
| A, ny ägare | 278.76 kr | 52.01 s | 98.97 s |
| A, oberoende ny ägare | 278.76 kr | 51.96 s | 77.79 s |
| B2 | 731.20 kr | 33.19 s | 77.63 s |

Fullständiga begäranden är oförändrade. A får inte bli dyrare än 278,76 kr;
hela B2-korgen är identisk med föregående 731,20 kr. Alla 2928
kvittofiler och beroenden är hashkontrollerade. Inga tidigare korgar förloras.
Detta är verifierade sökresultat, inget globalt optimumbevis.

72 riktade tester passerar, varav 19 nya. Ruff och compileall passerar.
CI har 4170 noder exakt en gång: 3575 core,
135 planner och 460 integration.
Alla tidigare 4 151 noder är autentiserade mot grön PR #30 och bevarade.
Full grön hosted CI krävs före integration. Föregående CI tog 8:54,
jämfört med ursprungliga 20:35, med samtliga tester kvar.

Metod: `9113f04df621a53f67de4d16b422e762a9c56641352fdf585b798124c3d1ec8b`.
Fakta: `.local/remaining-source-review-20261028/facts-reviewed-v1.json`,
SHA `2d408381863982f4ff5f6a8dd172c431d84c1a1dc6f0401795b83e7666f58c59`. Slutprov: `D:/Projects/Smako/.local/remaining-source-review-20261028/final-v1`.
Samma frysta Malmöreferens: 89 458 produkter, 52 kontexter, högst två butiker,
fyra middagsportioner/en frukost- eller mellanmålsportion, inget skafferi och
klockan 2026-10-23T06:00:02.869273+00:00.

Samma obegränsade journal, en tung arbetare, två CPU, 3 GiB och operationslås
består. Separat källpilot inväntar ägarbeslut. Ingen ny handlare, produktion,
beta, scheduler eller profil aktiveras. Legacy är standard.
