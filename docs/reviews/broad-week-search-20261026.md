# Bred veckosökning, 2026-10-26

**Oförändrat A levererar en fullständig femmiddagsvecka för fyra:
297,18 kr, API/checkout/save/ägd GET 53,3724 s och verklig Chromium
knapp→synlig inköpslista+GET 55,1185 s.** Browserns hela sparade begäran
och hela korg är identiska med API-provets. Inget nytt variation-intent
har lagts till. **B2 behåller exakt sin giltiga korg på 731,20 kr**,
nu API/save/GET 30,8191 s.

Leverans enligt [BROAD-WEEK](../CODEX-SOL-NEXT-20261026-BROAD-WEEK.md),
från main `2dd7183`, mätkod `11b5b97`. [Maskinkvittot](broad-week-search-20261026/delivery.json)
binder råkvitton, källor, tester, minne, budget och jämförelser. Legacy är
standard, V2 opt-in och `library_merge_generations=False`. Ingen beta,
produktion, scheduler, profil, insamling eller receptimport aktiveras.

## Vad som ändrades

Överlämnade förstamåltidsresultat skyddas nu tills deras ursprungliga
tur kommer. Nya missar får bara använda den lediga delen av **samma
256-postersbudget**, räknad över väntande resultat och fortsatt cache
tillsammans. Inga 960 fulla korgar eller större LRU införs. Ordinarie
kandidatordning, stabila likaprisval, färska finalkontroller och fallback
behålls. Det isolerade 300-kandidatprovet går från 300 nya beräkningar/
noll återanvändningar till **44 nya/256 återanvändningar**. Ursprunglig,
omvänd och roterad ordning samt likaprisfall har samma utfall som utan
återanvändning; mätningen är ett syntetiskt korrekthetsprov, ingen verklig
användarlatens.

För nya genererade aktuella V2-urval med fler än 64 alternativ i någon
slot föreslår befintlig `MenuOptimizer` hela menyer före prissättning.
Små urval, legacy/V1, redigerade scheman och receptbyten behåller sin
tidigare sökväg. Talet 64 väljer algoritm, begränsar inte aktiva recept.

Den breda vägen använder detta anrops redan kvalificerade pris-/paketsignaler
som kompakt prioriteringsunderlag. Den prissätter inga första-, andra-,
tredje- eller fjärdemåltidskorgar igen. Struktur, fördelning, distinkta
baser och faktisk variation kontrolleras medan en meny byggs. Sedan
prövar den samma riktiga gemensamma checkout som tidigare, med alla
gällande närings-, eko-, mängd-, pris-, butiks- och medlemsvillkor.

Prioriterade och ursprungliga första-receptankare varvas. Gemensamma
kvalificerade paket styr förslagsordning, medan hela korgens faktiska
kostnad avgör vinnaren. Hela nya ankarmenyer och enskilda byten förbättrar
en redan giltig kandidat. En avgränsad struktursökning per ankare hindrar
att ett inkompatibelt prefix förbrukar hela tiden. Alla alternativ finns
kvar; uppskjutna grenar är inga bevisat omöjliga eller för dyra recept.
Små kombinationsrum prövas uttömmande för korrekthetsoraklen.

Förbättringen använder samma absoluta begäransdeadline, inklusive kö och
kvalificering. **Tolv sekunder reserveras för aktuell checkout/audit,
save och svar.** Befintliga kooperativa kontroller får en snävare nästlad
deadline även inne i förbättringens checkout. Vid det stoppet behålls
den giltiga kandidaten och den yttre slutkontrollbudgeten återställs.
Användaravbrott och den absoluta deadlinen får fortfarande avbryta allt.
Det är ingen universell exakt 60-sekundersgaranti.

Endast bästa fulla resultat och pågående utvärdering behålls. Högst
4 096 kompakta menyidentiteter/utvärderingsslutsatser hindrar onödig
omräkning. Permutationer slås bara samman när befintlig anropsidentitet
fastställer likvärdighet; privat skafferiallokering/lås behåller ordning.
Ingen personlig kvalificering eller vinnare delas mellan ägare eller
består till nästa anrop. Överlämningen fylls bara för samma genereringsanrop,
aldrig för byte av låst slot; exakt recept-/mängdidentitet måste matcha.

UI bevarar nu frånvaron av intentmetadata i äldre återställda begäranden.
Först ett nytt uttryckligt standardval skapar nytt intent. Färska V2-val
och redan sparat nytt intent behåller sitt kontrakt. Därmed kan A provas
i browser med **samma** ursprungliga betydelse, utan smygändring av kraven.

## Verkligt A, matchat B2 och källor

Samma bevarade Malmöunderlag från 23 oktober: 89 458 produkter och
71 138 faktarader, fryst klocka `2026-10-23T06:00:02.869273+00:00`.
Alla tre prov har identiska pris-, fakta- och bibliotekshashar samt metod
`781b05f922d7a696dcf8c8c83df6bf8cb5624f15afdae535e473f6b9c880f006`.
Aktuellt bibliotek är fortsatt 2 462 varianter/934 baser.

| Prov | Färdig leverans | Tid | Korg |
| --- | --- | ---: | ---: |
| Tidigare A, återanvänd baslinje | Ingen lista, SEARCH_INCOMPLETE | 60,2828 s till avslag | saknas |
| [A, första nya API-provet](broad-week-search-20261026/A1.json) | Checkout/audit/save/ägd GET | **53,3724 s** | **297,18 kr** |
| [A, verklig browser](broad-week-search-20261026/A-browser.json) | Knapp→synlig full lista+GET | **55,1185 s** | **297,18 kr** |
| [B2, matchad regression](broad-week-search-20261026/B2-regression.json) | Checkout/audit/save/ägd GET | **30,8191 s** | **731,20 kr** |

Det är ett nytt A-API-anrop och ett separat A-browseranrop med nya lokala
testägare/processer, utan förvärmd identisk färdigplanscache. Samma
versionsbundna offentliga underlag får återanvändas. Inget andra eller
tredje A-API-försök behövdes. Den gamla misslyckade A-körningen gjordes
inte om som oförändrad baslinje. Kötid/transport ingår i de yttre tiderna;
ingen separat köpercentil eller samtidighetsbelastning är mätt.

[A:s strikta jämförelse](broad-week-search-20261026/A-browser-comparison.json)
verifierar hela råa och normaliserade sparade begäran och hela
`optimized_basket`, utan undantagna fält. `use_pantry=False` och frånvaro
av variation-intent bevaras. Browsern gör en dyr POST, inga JavaScriptfel
registreras och omladdning återläser samma plan utan ny beräkning.
[Skärmbilden](broad-week-search-20261026/A-browser-shopping.png) visar hela
listan utan konto-/sessionshuvud.

A behåller fem middagar × fyra portioner, 52 tillåtna butikskontexter,
inköpstak två, 10–15 ingredienser, sitt ursprungliga fria kost-/köksurval,
estimated och alla normaliserade äldre variationsfält. Huvudråvarutak två,
familjetak två och kolhydrattak tre är oförändrade. Fem olika baser väljs:

- Grekiskinspirerad gul ärtkräm med mjuk lök och potatis – enkel.
- Ugnsfalukorv med skårad potatis och senap – enkel.
- Italienskinspirerad pasta- och linssoppa med rotselleri – enkel.
- Pastapanna med smulad tofu.
- Svenskinspirerad gul ärtsoppa med senap och bröd – enkel.

Korgen fördelas på City Gross Malmö Hyllie **52,95 kr** och Willys Malmö
Emporia **244,23 kr**, båda inom valt scope. Inköp är VERIFIED och aktuell
checkout-audit passerar. A saknar aktiva personliga portionsnäringsmål;
status är **NOT_REQUESTED**, inga proteinvärden intygas. Inga aktiva
allergi-/ekokrav läggs till eller tas bort. Råa äldre top-level-standarder
har sin befintliga betydelse och ändras inte till nya personliga mål.

[B2-jämförelsen](broad-week-search-20261026/B2-comparison.json) verifierar
hela sparade begäran och exakt samma hela korg som PR #17:s giltiga
referens. Protein, 3 kyckling/2 vegetariska, grekiskt/italienskt, variation,
butikstak, audit och save/GET passerar igen. Protein är fortsatt ESTIMATED
48,882/48,631/45,188/36,755/39,965 g per portion, alla minst 35 g.
**Noll oförklarad prisregression**; den tidigare enstaka API-tiden var
30,2549 s. Enstaka prov är ingen statistisk latensjämförelse.

## Arbete, tid och minne

A har fortsatt **2 021 råa/960 kvalificerade** recept. I det nya API-provet:

- Första strukturellt och gemensamt checkout-/kravgiltiga hela kandidaten
  efter **34,9840 s från begärans början**, 509,64 kr.
- Bästa giltiga resultat uppdateras **nio gånger inklusive första
  kandidaten**, till 297,18 kr.
- **58/960 ankare** behandlas, 902 skjuts upp. 1 084 av 4 800 slotbundna
  alternativ berörs under konstruktion/byten; 3 716 skjuts upp. Inget
  alternativ är globalt säkert uteslutet. Detta räknar inte alla tänkbara menyer.
- Sökdjup 1–4 gör **noll nya korgutvärderingar**; kompakt redan kvalificerad
  evidens används. Djup fem startar 317 hela utvärderingar: 316 giltiga,
  en avbryts för slutkontrollreserven. Två tidigare utvärderade menyidentiteter
  hoppas över, inte två nya fulla resultat ur en delad användarcache.
- Kvalificering **26,7992 s**, veckosökning **13,2791 s**, instrumenterad
  planner-total **41,8217 s**. Faser är nästlade och ska inte summeras
  okritiskt. Yttre API/save/GET är 53,3724 s.

Browsern når första giltiga kandidat efter 34,8120 s, prövar 59 ankare och
323 giltiga hela korgar, och levererar exakt samma vinnare. Den större
delen av menyrymden är fortfarande oprövad. Resultatstatus är
**VALID_SOLUTION, global_optimum_proven=False**. A saknade en äldre giltig
prisreferens; dess gamla timeout är ingen nollkronorsreferens.

Första A-jobbets laddning/preparation/registrering före anropet tar
**104,4956 s** (källaddning 55,9231 s, gemensam preparation 45,4295 s).
Browserns förberedelse tar **83,9425 s**, gemensam del 20,5290 s; B2:s
totala förberedelse 77,1297 s. Detta är inte 55 s från en tom installation.
Faktiska jobb kostar 159,7772 / 149,5045 / 108,8791 s inklusive start/avslut.

Två CPU och hårt **3 GiB job-commit** gäller för den faktiska Windows-
interpretern. Högsta totala commit: **A API 1,466 GiB, A-browser 1,506 GiB,
B2 1,388 GiB**, under målet 2,5 GiB för dessa prov. Tidigare blockerade A
hade 1,464 GiB; observerad API-skillnad är cirka +2,28 MiB, ingen isolerad
kausal heapmätning. De 341 kompakta menyidentiteterna i API-provet räknar
**230 589 byte inklusive deras nycklar och värden**; det är inte hela
processens eller alla hjälptabellers minne. Allt ingår i jobbets totalpeak.
Ett svagt referensprov visar högst två levande fulla sökresultat.
En verklig pris-/faktaversion används; två fulla versioners överlapp är
fortfarande omätt.

## Verifiering, köpbarhet och budget

**121 avslutande riktade tester passerar**, inklusive hela browsermodulen
i Chromium/WebKit, kopplad kampanj där billigast individuellt blir dyrare
gemensamt, paket/butikstak, variation, senare kandidat, riktiga närings-/
ekoproduktalternativ och mjukt stopp inne i checkout. Tidigare överlappande
körningar 95, 38, 25 och 22 PASS summeras inte. Ändrad identitet, final-
kontroll, fallback, ägarscope och deadline-/revisionsskydd är provade.
Ruff/compileall passerar; ordinarie CI inklusive browser krävs grön före merge.

Ett nytt syntetiskt näringsprov misslyckades först eftersom dess påhittade
serveringssteg saknade granskad beredningsgrund. Fixturen använder nu
befintlig verifierad kall kvargberedning; runtimegrinden försvagades inte.
Två startfel före dataladdning/API är också bevarade och **0,0496 s**
debiteras: felaktig binär i skriptposition respektive saknad importväg.
Inga användaranrop hade börjat i dessa fel. Alla rålogghashar finns lokalt.

Ingen ny köpbarhetsinventering görs. **738 exakt/931 inklusive tillåtna
uppskattningar av 2 200**, fortfarande individuell insatslösbarhet.
[Återanvändningskvittot](broad-week-search-20261026/coverage-reuse.json)
binder oförändrade källor, recept/modeller och tio oförändrade centrala
kvalificerings-/kravfunktioner. Sök-/rapportändringar är ingen ny
produkt-, närings- eller hylltillgångskvalificering.

Samma [journal](recipe-integration-800-20261025/budget.json):
**5 344,9842 s använda / 1 855,0158 s kvar = 30,92 minuter av 120.**
Etappen debiterar **418,2104 s**, inklusive all laddning/preparation,
API, browser, B2 och startfelen. Ingen nollställning, stor matris,
identisk timeoutomkörning eller nattlig fortsättning.

Största kvarvarande uppmätta del är personlig kvalificering, cirka 26,8 s,
följt av API-/lagrings-/svarsarbete utanför planner-spannen och begränsad
prisförbättring. Säkert mer återbruk där kräver fortsatt korrekt beroende-
och ägarscope. p95, samtidighet, verklig veckouppdatering, prisversionsöverlapp,
hela valkatalogens kombinationer och UI-butikstak 1..N är fortsatt egna
okvalificerade produktkrav. Källberikning för limejuice/ansad mängd är en
separat etapp; inget sådant underlag har fabricerats här.
