# De fem största ingredienshindren, 2026-10-28

**2 024 av 2 200 hela korgar i uppskattningsläget: 160 nya.** Samtliga fem
grupper har nu kvalificerade produkter i det befintliga referensunderlaget.
192 unika receptvarianter har uttryckliga nya versioner. 32 av dessa har
andra ingredienshinder kvar. Totalt återstår 176 varianter i biblioteket.
Alla tidigare hela korgar och de 2 200 ursprungsreferenserna bevaras.

Exakt läge har 1 142 insatslösta och 1 140 hela korgar, 74 nya hela.
De två tidigare korgar som hindras vid checkout är fortfarande blockerade.
Uppskattningstalet inkluderar exakta korgar och innebär inte att varje
recept fungerar med alla butikskombinationer eller personliga krav.

## Befintliga produkter och tydliga receptalternativ

| Tidigare hinder | Lösning i ny version | Berörda varianter | Nu hela korgar, uppskattning |
| --- | --- | ---: | ---: |
| Tamarindpasta | CHS tamarindkoncentrat, uppmätt i ml | 93 | 76 |
| Masa harina | P.A.N. förkokt vitt majsmjöl, anpassad deg | 31 | 31 |
| Citrongräs | Hela stjälkar, vikt före ansning | 27 | 18 |
| Pärlkorn | Frebaco kornris, separat kokning 13–15 minuter | 27 | 24 |
| Klibbigt ris | Oishii sushiris, anpassad kokning | 20 | 14 |

Grupperna överlappar. Tabellens sista kolumn får därför inte summeras;
den verifierade ökningen är 160 unika korgar. [Detaljer](top-five-ingredients-20261028/top-five-outcomes.json).

Produkterna fanns redan i underlaget. 24 exakta relationer i befintliga
City Gross-, Hemköp- och Willys-kontexter kopplas till fem egna definitioner.
Inga nya handlare, priser, butikskontexter eller prisobservationstider tillkommer.
Extern produktinformation används enbart som innehålls-/beredningsunderlag.
Coop-online får ingen ny fysisk prisetikett och dess crawlgräns består.
[Källgranskning](top-five-ingredients-20261028/source-review.json) och
[bevarandekontroll](top-five-ingredients-20261028/facts-preservation.json).

Kornris tillagas efter Frebacos anvisning. P.A.N. får egna degmängder,
vilosteg och formning; Maizena majsstärkelse blir inte godkänd som masa harina.
Tamarindkoncentrat mäts i ml med ny författad dos per komponent; inga gram
konverteras med antagen densitet eller styrka. Citrongräs anges som hel
inköpsvikt före ansning och har inget påstått ätligt utbyte. Sushiris får
absorptionskokning och nya namn; det markeras inte som glutinöst ris.

[Beredningsgranskningen](top-five-ingredients-20261028/cooking-review.json)
skiljer källdata från författade val. Smak, konsistens och tider är inte
provlagade. Okända närings-, allergen- och ekologiska fält förblir okända.
Alla ursprungliga ingredienser utanför dessa fem grupper och alla portioner
bevaras. En utökad klimpvariant fick en separat rättning efter att testet
hittat ett förskjutet steg; kycklingens hela koksteg och 74 °C-kontroll är
återställda. Även det återkallade försöket finns kvar i historiken.

## Prisregression och verifiering

Det första A-provet med det större urvalet kostade 281,31 kr och stoppade
leveransen. 1 884 middagsvarianter kvalificerades, men det arbetet lämnade
för lite tid åt menysökningen. Befintlig offertkod räknar nu en exakt
cache-nyckel en gång och kopierar frysta offertfält med en specialiserad
konstruktor. Alla 56 fält jämförs mot den tidigare kopieringen; framtida
fält måste också bevaras. Pris-, mängd-, kampanj-, käll- och auditregler består.

Samma urval kvalificerades på 33,33 mot 36,40 sekunder och A återkom till
278,76 kr. Detta är en mätning, inte bevis på globalt optimum.
[Jämförelsen](top-five-ingredients-20261028/search-cost-comparison.json).

| Prov, separat ny ägare | Total korg | API, sparning och återläsning | Separat förberedelse |
| --- | ---: | ---: | ---: |
| A | 278.76 kr | 53.72 s | 98.81 s |
| A-repeat | 278.76 kr | 52.47 s | 77.95 s |
| B2 | 731.20 kr | 32.63 s | 77.56 s |

Samma fullständiga A/B2-begäranden används. A klarar tidigare pris i två
oberoende prov; hela B2-korgen är identisk med tidigare 731,20 kr.
Alla 3166 aktuella kvittofiler och deras beroenden
är hashkontrollerade. [Slutkontroll](top-five-ingredients-20261028/verification.json).

335 riktade tester, Ruff och compileall passerar. CI:s 4258 testnoder
förekommer exakt en gång och alla 4 202 tidigare noder finns kvar.
Grön hosted CI krävs före integration; inget testurval har minskats.

Referensen är fortsatt Malmö, 89 458 produkter, 52 kontexter,
2026-10-23T06:00:02.869273+00:00, högst två butiker, fyra middagsportioner,
en frukost-/mellanmålsportion och inget skafferi. Metod:
`4da996ae1555570cf8ddea67a47529b5d4ede9b8cb8a52476684ec14b4f262ab`.
Fakta: `.local/top-five-ingredients-20261028/facts-reviewed-v1.json`,
SHA `23c45ae2e4f27222833028277b3b9ca9426a232408baa4971c9e8114b766abca`. Slutprov i samma lokala katalog,
`final-v3`. Originalnämnaren och bibliotekets 2 462 aktiva varianter består.
Ingen produktion, beta, scheduler eller profil har aktiverats eller ändrats.
