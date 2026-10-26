# Giltig vecka och aktuell produktlösbarhet, 2026-10-26

[Uppdraget](../CODEX-SOL-NEXT-20261026-VALID-WEEK-AND-COVERAGE.md) genomförs
från main `3a62cde`, via [PR #17](https://github.com/ossebosse/smako/pull/17).
**B2 levererar fem middagar/fyra portioner för 731,20 kr: API/save/GET
30,25 s, verklig Chromium knapp→synlig lista+GET 30,78 s.** Individuell
produktlösbarhet ökar från en nyuppmätt 733/920 till **738/931 av 2 200**,
netto **+5 exakt/+11 med tillåtna mängduppskattningar**, inga förluster.
Det bredare A blir fortfarande inte färdigt vid 60 s. Legacy är standard,
`library_merge_generations=False`, den nya sökvägen är opt-in. Ingen beta
eller produktion aktiveras.

## Vad köpbarhetstalen faktiskt mäter

Samma inventeringsdefinition som tidigare: varje ingrediensinsats i en
variant måste få minst en kvalificerad produkt-/mängdkandidat genom
befintlig `PersonalPlanner.resolve`, med aktuellt receptkrav, exakt
käll-/butiks-/produktidentitet och respektive mängdpolicy. Detta är
**individuell insatslösbarhet**, inte en verifierad gemensam tvåbutikskorg,
närings-/allergen-/ekogodkännande eller belägg för fysisk hylltillgång.
Estimated-talet inkluderar exakta fall. Definitionen ändras inte för att
räkna en vinst. Den personliga B2-veckan har separat checkout/audit.

| Samtliga 2 200 importerade varianter | Exakt | Med uttryckligen tillåtna uppskattningar |
| --- | ---: | ---: |
| Historisk PR #15-inventering | 733 | 920 |
| Ny fullinventering före kopplingsändring, inklusive strikt rågbröd | 733 | 920 |
| Ny fullinventering efter kokoskoppling | **738 (33,5 %)** | **931 (42,3 %)** |
| Nytillkomna / förlorade fullständigt insatslösta varianter | **5 / 0** | **11 / 0** |
| Fortsatt blockerade | 1 462 | 1 269 |

Alla 2 200 ursprungsreferenser mappas till unika nuvarande runtime-ID:n.
De 262 andra ursprungliga varianterna ligger separat och ingår inte i
dessa tal. Totalt fortfarande 2 462 aktiva varianter/934 baser, 39 aktuella
och sju historiska paketgenerationer. Inga recept, mängder, smaker,
beredningar eller ingrediensantal har skrivits om i denna etapp.

[Fullt kompakt inventeringsunderlag](valid-week-and-coverage-20261026/purchase-coverage.json)
innehåller båda lägenas hela aktuella ID-lista via referensindex, samtliga
insatsscope, före-/efterutfall, produktreferenser, nytillkomna/förlorade ID:n,
kvarstående hinder samt råunderlagens SHA/lokala kopior. Bara tolv
kvantitetsscope för `kokosflingor|dry` ändrar utfall; inga andra identiteter
har tillskrivits vinsten. Historiskt→ny baslinje är också jämfört per ID,
utan dolda vinster och förluster som tar ut varandra.

Rågbrödsvarianterna är index 271–273 i inventeringen. Alla tre är insatslösta
före och efter det striktare rågbrödskravet i båda mängdlägena. Kravet ger
alltså **noll förlorade varianter i detta underlag**; det är inte ett skäl
att återgå till pita och ingen ny prisreferens för rätt C.

## Verifierbar produktkoppling och kvarvarande källbehov

Retained-data-granskningen rangordnade luckor efter hela varianter som
skulle kunna frigöras, inte summan av överlappande ingrediensantal. Limejuice
och ätlig mängd för större grönsaksgrupper saknar fortfarande nödvändiga
deklarationer. Inga fullständiga ingredienslistor eller ätliga utbyten
fabriceras; ingefära som redan bara stöds i estimated flyttas inte till exakt.

Den avgränsade rättningen är aliasen **kokosflingor ↔ riven kokos ↔ kokos riven**.
Den granskade torra, rena varuklassen och förpackningarnas deklarerade
200 g fanns redan i befintliga form-/identitetsregler, men retrieval och
semantisk matchning saknade aliasen. Samma käll-/pris-/mängd-/formgrindar
används. Söta flingor, choklad/dessert, kokosmjöl, kokosmjölk och kokosolja
passerar inte receptets hela identitetskrav. Ett generiskt dessertköp får
inte heller bli kokosköp. Sammansättningsuppgifter som faktiskt finns får
fortfarande motsäga renhetskravet. Okända allergener/närings-/ekodata
blir inte kända genom aliaset.

[Källgranskningen](valid-week-and-coverage-20261026/source-review.json)
bevarar de 18 kokosradernas exakta produkt-/butiks-/snapshot-/paketuppgifter
och sammanfattar även limejuice, ingefära, salladslök, mynta och purjolök.
Limejuice kräver fortfarande innehållsbevis för ren juice; knippen,
krukor och hela rötters bruttovikt styrker inte ansad ätlig mängd.
Ingen bred insamling eller ny pris-/faktaversion har gjorts.

De två fullinventeringarna kostade 91,3165 + 75,5608 s; kompakt delta och
källkontroll ytterligare 1,5847 s: **168,4620 s, 2,81 minuter av deltaket
tolv minuter**. Start och full källaddning ingår. Nollställning av tidigare
inventeringsresultat eller omdefinition av räknaren används inte.

## Uttryckliga val före en känd standard

[Arkitekturtillägget](../PLANNING-ARCHITECTURE.md) skiljer mellan:

- måltidens enda kost-/proteinkategori, som används för tre kyckling/två vegetariska;
- kulinarisk primärklass, som används för gränsen samma huvudråvara;
- alla författade substantiella huvudproteinkällor, även flera i en blandrätt;
- grundrättens `base_id`, som fortfarande förenar dess varianter.

Nya V2-anrop sparar `variation_intent` med `default`, `explicit` eller
`unknown` per variationsfält. UI bevarar gamla okända värden och egna
gränser; förifyllda standarder skickas inte som skenbart uttryckliga val.
En äldre okänd standard kan ersättas genom ett nytt dokumenterat UI-val.
En uttrycklig egen gräns kan inte tas bort via standardvalets kryssruta.
Sparat nytt intent tappas inte om miljön byter till legacy: ägd GET
fungerar, medan en omräkning som inte kan respektera reglerna avvisas.

Före menyförsök räknas kapacitet med faktisk kulinarisk klassificering och
distinkta baser i den kvalificerade poolen. Endast en känd ärvd standard
som faktiskt kolliderar med en uttrycklig fördelning får höjas, till minsta
tillräckliga tak. Övriga krav består. Två hårda krav ger konkret konflikt;
okänd klassificering och otillräckliga delurval ger inget globalt
omöjlighetsbevis. Effektiv regel och anpassning sparas i checks och visas.

Original-B och dess sparade anrop är oförändrade och körs inte dyrt igen.
Det separata [B2-kvittot för definition/kapacitet](valid-week-and-coverage-20261026/B2-definition-and-capacity.json)
visar den enda råa ändringen: nytt fältursprung där huvudråvarustandarden
är känd standard och övriga gamla variationsfält förblir okända/bevarade.
Efter normalisering och policyupplösning ändras **enbart samma-huvudråvara-
taket 2→3**. Alla andra effektiva policyfält är lika. Den nya strukturvägen
hittade ett vittne efter 139 kombinationer i det gamla observerade
29-receptunderlaget. Detta underlag begränsar inte den verkliga B2-sökningen.

## Deadline även vid ändring av sparad plan

`POST /api/personal/plans/{plan_id}/change` omfattas nu av samma absoluta
deadline som ny planering, både direkt och som async-jobb. Kontexten följer
admission och arbetstråden; nästlade led förlänger inte den. Awaitad kötid
avbryts också. Befintliga inre loopkontroller gäller fortfarande, och
vanlig avbrytning stoppar och sammanfogar arbetstråden.

Lagringens låsväntan begränsas av återstående tid. Deadline före commit
rullar tillbaka revision, reservationer och mutationskvitto i samma
transaktion. Om full lagring redan committat när deadline märks returneras
`SEARCH_INCOMPLETE` med `committed_revision`; ägd GET och identiskt
återförsök återfår samma revision utan dubbelversion. Revisions- och
ägarskontroller behålls. Legacy får ingen ny 60 s-deadline.

Små simulerade klockprov visar deadline 60 i arbetstråden, stopp efter
simulerade 61 s, direkt/async-status, köväntan, transaktionsrollback,
sen commit/omkörning, vanlig avbrytning, annan ägares avslag och oförändrat
legacybeteende. De väntar inte en verklig minut. Serverdeadline och dess
kooperativa stopp är inte en universell exakt 60,000 s-gräns för transport/UI.

## Verklig B2-vecka och ett avgränsat A

Samma bevarade Malmöunderlag och testklocka som tidigare. B2 behåller
**52 butiks-ID:n, fem middagar × fyra portioner, tre kyckling/två vegetariska,
grekiskt/italienskt, protein≥35 g, högst tre samma huvudprotein, inköpstak två,
estimated och uttryckligt tillåten näringsuppskattning**. Endast ovanstående
standardkonflikt ändras. Ingen identisk färdigplanscache värms.

| Prov | Slutligt utfall | Tid | Totalsumma |
| --- | --- | ---: | ---: |
| [B2, nytt API-anrop](valid-week-and-coverage-20261026/B2.json) | Komplett, checkout/audit, save, ägd GET | **30,2549 s** | **731,20 kr** |
| [B2, ny browserägare](valid-week-and-coverage-20261026/B2-browser.json) | Verkligt knapptryck→synlig full lista+GET | **30,7820 s** | **731,20 kr** |
| [A, ett enda bredare anrop](valid-week-and-coverage-20261026/A.json) | HTTP422 SEARCH_INCOMPLETE, ingen levererad lista | **60,2828 s till avslag** | saknas |

Browserprovet använder verkliga lokala API-rutter utan mockade svar,
kontrollerar skickade normaliserade val, gör exakt en dyr POST och visar
inga JavaScriptfel. Omladdning återläser samma sparade plan utan ny
beräkning. [Skärmbilden](valid-week-and-coverage-20261026/B2-browser-shopping.png)
visar hela inköpslistan, utan konto-/sessionshuvud. Listan fördelas över
ICA Kvantum Malmborgs Mobilia (171,00 kr) och Willys Malmö Katrinelund
(560,20 kr), båda inom valt scope.

Veckan innehåller krosspotatis med kyckling/kikärtskrisp, kycklingfyllt
stekbröd, kycklingsoppa med zucchini/småpasta, broccoli/kikärtor/feta med
couscous samt tomatbakade vita bönor/feta/couscous. Fem olika baser,
fyra grekiska/en italiensk middag. Protein per portion är **48,882;
48,631; 45,188; 36,755; 39,965 g**, alla **ESTIMATED** med bevarad
insats-/källproveniens. Inköpskontrollen är VERIFIED och checkout-audit
passerar; det gör inte näringsuppskattningarna till laboratoriemätningar.
Inga aktiva allergi-/ekokrav tillkommer utöver B2:s val.

B2 filtrerar hela aktuella biblioteket till **681 råa/29 kvalificerade
kandidater**, med policyavslag 205, produkt 414, näringsgräns 33. 491
korgberäkningar, 15 022 paketberäkningar, 24 985 butikskombinationer och
222 246 undvikna delmängder registreras. Kvalificering 16,527 s och
veckosökning 3,958 s är instrumenterade faser, inte additiva totaldelar.
Sökningen är begränsad beam; **VALID_SOLUTION, inget globalt optimumbevis**.
B:s tidigare avslag innehåller inget matchbart pris. Ingen äldre giltig
B2-vinnare finns för prisparitet. Små uttömmande korg-/menyorakel behålls;
ett nytt acceptansfall är inte en matchad latens-/prisförbättring för B.

A får 2 021 råa och 960 kvalificerade kandidater. Vid deadline har sökningen
bara hunnit 699 förslag på djup två, med 697 påbörjade/696 färdiga
utvärderingar där. Totalt 2 617 korgar och 224 807 paketberäkningar.
Kvalificering 26,264 s, partiell veckosökning 26,333 s; fortsatt upprepning
av gemensamma korgar över en större kandidatpool är nästa konkreta
prestandahinder. Ingen A-vinnare, audit, save eller pris godkänns. Inget
identiskt timeoutomtag eller större matris körs.

A:s testhjälpare hade dessutom en separat samtidig skrivning till sin
progress-/slutfil (`WinError 32` i timertråden). Slutkvittot innehåller korrekt
HTTP422/SEARCH_INCOMPLETE och huvudprocessen avslutades med kod 0.
[Hjälparobservationen](valid-week-and-coverage-20261026/A-harness-observation.json)
bevarar logghash och åtskillnad från API-utfallet. Hjälparen stoppar och
sammanfogar nu progressskrivaren före slutskrivning. A körs inte om för detta.

## Förberedelse, resurser och kvarvarande räckvidd

B2-API:s första källaddning/förberedelse/registrering tar **112,3767 s**
före användaranropet: källaddning 56,0766 s, gemensam preparation 53,3113 s.
Den nya metodversionen lagrar 2 462 contentposter i den befintliga fulla
cachen och gallrar 2 462 gamla poster, ready med noll persistensfel.
Ny browserprocess har 4 926 träffar, noll missar/skrivningar, gemensam
preparation 20,0817 s. Total cachelagring 3 607 454 byte, inga höjda gränser.
Browserförberedelse totalt 83,7634 s; det debiterade hela browserjobbet
tar 121,3166 s inklusive process-/browseravslut. API-jobbet tar 143,6316 s.
Detta är inte 30 s från en första tom installation.

Två CPU och hårt 3 GiB commit gäller för faktisk Windows-interpreter i OS-jobb.
Jobbens högsta commit: B2-API 1,384 GiB, browser 1,396 GiB, A 1,464 GiB,
under målet 2,5 GiB. Det är Windows job-commit, inte Linux RSS/cgroup eller
p95. En ensam verklig pris-/faktaversion används fortfarande: verklig
veckouppdatering, två fulla prisversioners överlapp och samtidighetskapacitet
är omätta. Full V2, UI-tak 1..N och giltig snabb A för hela breda urvalet
är inte kvalificerade genom detta enda lyckade veckofall.

Sökningen slipper nu obligatorisk historisk modellmaterialisering vid
delning av redan exakt validerade aktuella recept; historiska referenser
har kvar sin fallback. Kompletterande samma-meny-butiksjämförelser och
upp till 24 produktkontrafaktiska checkouter tas bort från den obligatoriska
V2-leveransvägen. De väljer/förbättrar inte vinnaren. Slutlig faktiskt vald
checkout, näring, alla tillämpliga krav, audit och save behålls; oprövade
alternativ får inga prisomdömen. Legacy/V1 behåller sina jämförelser.

## Verifiering och budget

**678 riktade regressioner passerar**, inklusive publicerade receptkedjor,
historiska referenser, fulla intake-länkar, nya policy-/deadlinefall,
Chromium/WebKit och oförändrade små prisorakel. Separat tidigare
transportkörning 109 PASS överlappar och summeras inte. Ruff/compileall
passerar på ändrade Pythonfiler. Ordinarie CI inklusive browserinstallation
och hela sviten krävs grön på slutligt PR-huvud före mainintegration.
Ingen testgrind sänks för att göra CI grön.

Mätkoden är `b2f17b5`, metodsignatur
`3a78998c6de473d114bd790c3efac8ea03a76b10a99125ba606ce73215b4ffc5`.
Därefter tillkommer stödgrindar mot att nytt intent ignoreras i legacy,
UI-bevarande, tester och progressskrivarens skydd. V2:s uppmätta
pris-/sökmetod och B2:s positiva regelväg ändras inte av dessa kompletteringar.
[Maskinsammanställningen](valid-week-and-coverage-20261026/delivery.json)
binder käll-/bibliotek-/metodhashar, råkvitton och testloggar.

Samma [budgetjournal](recipe-integration-800-20261025/budget.json):
**4 810,7861 s använda / 2 389,2139 s kvar = 39,82 minuter av 120.**
Denna etapp debiterar 584,4733 s inklusive all källaddning, båda inventeringar,
strukturprov, första förberedelse, API, browser och misslyckat A. Inga
budgetar har nollställts, inga mätarbetare lämnas, och inga nya
insamlingar, nattliga uppgifter, drift-/profiländringar eller aktiveringar görs.
