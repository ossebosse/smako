# Frysta edamamebaljor och återanvända paketofferter, 2026-10-28

**1 830 av 2 200 hela korgar inklusive uppskattningar**, två fler än efter
PR #28. Exakt läge har 1 066 insatslösta och 1 064 hela korgar, också +2.
370 varianter har fortfarande insatshinder. Alla original, 2 462 aktiva
varianter och tidigare verifierade korgar består. Full täckning återstår.

Garant Edamamebönor Frysta, 500 g, är granskad i nio befintliga kontexter.
Artikel 101328931_ST och konsument-GTIN 7340083484575 stäms av mot det
hashverifierade Axfoodarkivet. Åtta Willys-/Hemköprader saknar GTIN i
Product men har samma exakta artikel i källfakta; ingen kod hittas på.
Den kompletta leverantörsdeklarationen och det visuellt lästa originalfotot
anger frysta sojabönor i skidor, 500 g. Receptens egna steg kräver frysta
baljor som ångas, och deras mängd avser inköpsvikt inklusive oätlig balja.
Ingen bönandel eller näring per gram balja antas. Se
[källgranskningen](plain-food-facts-20261028/source-review.json) och
[faktabevarandet](plain-food-facts-20261028/facts-preservation.json).

Atairs rena citruspektin E440, 10 g, har också identifierats exakt. Det
godkänns däremot inte för de två kvarvarande konfektrecepten: deras steg
kräver gult högmetoxylerat pektin för fasta fruktbitar. Den första
provisoriska kopplingen togs därför bort och definitionen förtydligades.
Det provisoriska talet 1 832 räknas inte som levererat. Vanligt syltpektin
och de motstridiga näringsdeklarationerna ger inget sådant godkännande.
Originalrecept och doser är oförändrade. Webverktygets textutdrag markeras
uttryckligen som utdrag; dess hash påstås inte vara en hämtad HTTP-kropp.

## Befintlig offertcache

Olika grambehov för samma exakta fasta produkt ger ofta samma antal paket.
Den befintliga anropscachen återanvänder nu offertens konstanta fält för
samma frysta kandidatobjekt, enhet och paketantal, med högst 8 192 poster.
Den ordinarie mängdresolvern och källans köpgräns körs fortfarande varje
gång. Aktuellt ingrediensnamn, behov och rest hämtas från det nya behovet.
Erbjudanden, kampanjgrupper, PurchaseTerms, uppskattade mängder, andra
försäljningsformer och egna kalkylatorer/resolvers följer sina vanliga vägar.
Priser, källscope, audit och hårda användarkrav är oförändrade.

Alla fält och fel är identiska för 156 920 verkliga offerter per genomgång
i ordningen före/efter/efter/före, med tom anropscache varje gång och
likhetskontrollen utanför båda tidtagningarna. Isolerad median är
6,517 till 6,089 s. Detta är ingen allmän API-latensgaranti. Se
[likhetsbeviset](plain-food-facts-20261028/quote-template-equivalence.json).
En direkt räknare visade att recept-ID-cachen redan beräknar varje ID en
gång; den ändrades inte efter det missvisande stickprovsresultatet.

## Slutprov och bevarande

| Prov | Giltig korg | API, sparning och återläsning | Separat förberedelse |
| --- | ---: | ---: | ---: |
| A, ny ägare | 278,76 kr | 53.66 s | 99.20 s |
| A, oberoende ny ägare | 278,76 kr | 53.70 s | 79.36 s |
| B2 | 731,20 kr | 32.78 s | 76.69 s |

A:s båda korgar är billigare än föregående 281,31 kr. B2:s hela optimerade
korg är identisk. Samma fullständiga begäranden, butikstak, klocka och priser
används. Alla slut-audits passerar. Tidigare misslyckade och instrumenterade
prov bevaras separat i [diagnostiken](plain-food-facts-20261028/diagnostics-and-withdrawn-review.json).
Den begränsade sökningen är inget bevis för globalt lägsta pris.

Alla 2 896 aktuella kvittofiler och deras beroenden är verifierade. Den fulla
kontrollen startar med tre sekunders watchdog per variant och behöver ingen
extra genomgång för enstaka tidigare ensekundsgränser. 78 riktade tester,
Ruff och compileall passerar. Oförändrade CI-partitioner kontrolleras med
en samlad insamling och autentiserad återanvändning av den tidigare nodlistan:
alla gamla 4 121 noder består, 13 tillkommer, totalt 4 134 exakt en gång.
Full hosted CI med alla tre obligatoriska delar krävs före integration.
PR #28:s redan gröna CI tog 8:06; den ursprungliga jämförelsen var 20:35.

Metod: `0c75b15c21ed8452910f9ff5504153fab1ec270bdd11b834f726567ba366d48d`.
Fakta: `.local/source-rice-review-20261028/facts-reviewed-v3.json`,
SHA `3794f1e0ce28bcca1a65a798e0238a7186868cf4c04af7fc18e8827fbaafbffc`.
Slutprov: `.local/source-rice-review-20261028/final-v4`.
Samma frysta Malmöprisunderlag, 52 kontexter, 89 458 produkter, fyra
middagsportioner/en frukost- eller mellanmålsportion, högst två butiker,
inget skafferi och klockan 2026-10-23T06:00:02.869273+00:00 används.

Tre ytterligare exakta risnudelartiklar har en förberedd insamlingskö men
inga handlaranrop: serverns gemensamma operationslås är upptaget.
Låsets ägare lever; arbetets status är inte styrkt. Inget lås, schema eller
runtimeunderlag ändras för att komma förbi detta. Den begränsade
[nya källpiloten](coverage-source-pilot-20261028.md) är fortsatt ett separat
beslutsunderlag. Ingen produktion eller beta aktiveras; legacy är standard.
