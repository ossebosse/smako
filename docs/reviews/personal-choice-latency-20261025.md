# Personliga val: avgränsad väntetidsmätning, 2026-10-25

**30-sekundersmålet för en färdig E-inköpslista är inte uppnått.** E ger
`SEARCH_BLOCKED`, inte en godkänd meny. B/C och standardens första privata
förberedelse blir måttligt snabbare; den dyra gemensamma korgberäkningen och
publiceringskedjan kvarstår. Ett förberett A-återanrop klarar 15 sekunder i
prefixprovet, men återgången till A efter E gör det inte.

Leverans: [PR #12](https://github.com/ossebosse/smako/pull/12), appkod
`5e4d47f`. Slutleveransens appträd är samma uppmätta appträd. Standarderna
`library_search_policy=legacy` och `library_merge_generations=False` kvarstår.
Ingen produktion, scheduler, insamling, aktiv pris-/faktarelease eller
samtidighet har ändrats. Ingen full standardkvalificering påstås.

## Ändringen och dess beroenden

`PreparedPriceUniverse` återanvänder **existensen av någon giltig kampanj per
butikskontext och svensk inköpsdag**. Exakt det validerade objektets produkter,
offerter och proveniens samt dagen är läsberoenden. Två dagar behålls, även
negativa resultat, under samma objekts lås. Första giltiga kampanjen räcker
för det redan befintliga existensvillkoret. Ett nytt prisobjekt har en ny tom
cache; en sen beräkning i ett pensionerat objekt skriver endast där.

Kartan innehåller inga priser, produktval, näringsbesked, medlemskap, privata
förmåner, menyer eller certifikat. Observationernas ålder och tillförlitlighet
beräknas fortfarande vid varje läsning. Individuella erbjudandens giltighet,
medlemskap, faktisk produktnäring, förpackningar, gemensam checkout och audit
prövas i befintliga vägar. Kampanjgränsen gäller även utan nytt snapshot-ID.

`beta_observability.price_universe_id` läser dessutom den aktiva identiteten
direkt. Ett ID behöver ingen beräkning av readiness. Faktisk readiness och
färskhetsinformation använder fortfarande `active_price_status` och de vanliga
grindarna. Klientens sluttid hålls skild från asynkron metriklagring.

Den fullständiga personliga kontextnyckeln är orörd. Metodsignaturen ändras
med appkoden, så äldre härledda kvalificeringar/certifikat får säker miss.
Sparad historik och privata lager flyttas eller raderas inte. De tidigare
minnes-/streaming-/prefixförbättringarna är kvar i implementationen. De gamla
24,79/33,20-procentstalen gäller sitt historiska 5 000-prov och återanvänds
inte som kvalificering av denna runtime; inga sådana prov har återupptagits.

## Frysta begäranden och mätgräns

[requests.json](personal-choice-latency-20261025/requests.json) fångades från
det riktiga personliga gränssnittet med den befintliga browserfixturen.
Endast fixturens plats ersattes av det frysta Malmöområdets `21120` och exakta
butiks-ID:n. Alla fall har fem middagar, fyra portioner och högst två butiker.
API:t normaliserar själv medlemskap till `all_advertised`, strategi, privata
revisioner och sparning. Testkonton registreras på riktigt i separata lokala
PlanStore; inga produktionsprofiler eller direkt ändrade revisioner används.

| Fall | Extra krav |
| --- | --- |
| A | Inga extra personliga begränsningar |
| B | Italienskt/indiskt; UI:ts fria val bland dessa matkök |
| C | `personal.meals[dinner].limits.min_protein_g=40` per portion |
| D | Kyckling 3, vegetariskt 2, kött 0, fisk 0 |
| E | B + C + D, oförändrade krav |

Samma exakta 262-receptsmanifest, pris-/faktabytes och testklocka används i
båda armar. Axfoods godkända partiella release omfattar 91 Willys- och tolv
Hemköpsdokument samt 18 negativa svar; full täckning påstås inte. Hashar,
metoder, resurser och observationer finns i
[evidence.json](personal-choice-latency-20261025/evidence.json) och
[source.json](personal-choice-latency-20261025/source.json).

Källunderlaget skiljer Git-blobhash från `measured_export` för den faktiskt
körda Windows-exporten med CRLF. Alla 213 appfiler i varje exporterad arm
har jämförts med respektive commit och med den monterade fjärrkopians
bytes. Samma appträd är verifierat; metodhashen i `evidence.json` gäller
de körda exportbytesen. En Linux-checkout med LF kan få en annan konservativ
metodhash och därmed korrekt cachemiss, utan ändrad programlogik.

Seriell Linux/Docker på samma evidensvärd, två CPU, 3 GiB inklusive swap
som hårt tak, UID/GID 10001, en planerare och inga extra workers. Vanliga
anrop är utan profilerare. Katalog/fakta/recept laddas före användaranropet;
den gemensamma uppstarten tar cirka 55 sekunder och redovisas separat.
OS-cache och värdens övriga arbete är inte kontrollerade. Resultaten är små
observationer, inte last-/p95-garantier.

Primär sluttid för **PASS** är POST till godkänt sparat svar och autentiserad
GET av hela inköpslistan. POST/202 är bara kvittot. Vid **BLOCKED** redovisas
tid till avslutat fel och ingen tid till färdig lista. ASGI är serverflöde;
statuspollningen är UI:ts två sekunder. Inläsning, initiering, kvalificering,
sökning/korg, aktuell audit och Save finns separat i maskinunderlaget.
Korg-/näringsfaser överlappar sökningen och ska inte summeras med den.
Ingen konkurrerande plan köas i den isolerade miljön; vanlig kötid är inte
separat profilerad. Browserprovet redovisas för sig.

## Före/efter

Prefixsekvensen var `A seed, A igen, B, C, D`. Båda armar stoppades vid D:s
första femminutersgräns. Ingen utvidgning av den sekvensen gjordes därefter.
För att ändå mäta huvudfallet användes en separat, matchad sekvens
`A seed, första E, E igen, A igen, ny ägare: A seed, första E`.
E hade ingen förberedd personlig kontext före första E i någondera armen.

| Observation, sekunder | Före | Efter | Utfall/pris |
| --- | ---: | ---: | --- |
| A, första privata förberedelse i prefixet | 200,72 | 187,32 | PASS, 362,26 kr |
| A, förberett återanrop efter A | 17,88 | 14,81 | PASS, samma pris/hash |
| B, första nya val | 138,69 | 128,74 | PASS, 553,05 kr |
| C, första nya val | 66,87 | 62,79 | PASS, 983,84 kr |
| D, första nya val | ≥300 | ≥300 | Timeout, ingen färdig lista |
| E, första efter A i målsekvensen | 12,97 | 12,06 | SEARCH_BLOCKED, ingen lista |
| E, upprepning | 7,99 | 7,34 | Samma blockeringskod/pool |
| A, återgång efter E | 17,18 | 16,42 | PASS, samma pris/hash |
| Annan ägare, första A efter offentlig uppvärmning | 188,10 | 177,52 | PASS, 362,26 kr |
| Annan ägare, första E efter egen sparad A | 13,42 | 12,29 | SEARCH_BLOCKED, ingen lista |

B/C är fortfarande **98,74/32,79 sekunder över 30-sekundersmålet**. Återgången
till A efter E ligger 1,42 sekunder över 15-sekundersmålet. Ett snabbt avslag
på E uppfyller inget leveransmål. Godkända A/B/C har samma semantiska
recept-/korg-/närings-/audit-/allokeringshash före och efter; aktuell audit,
full Save/GET och noll okända kvantiteter kontrolleras vid varje leverans.

Första A upprepades i tre separata, likvärdiga tomma app-/ägarcachelägen:
före **200,72 / 198,58 / 203,30 s**, efter **187,32 / 187,50 / 195,04 s**.
Medianen är 200,72 → 187,50 s, **6,59 procent kortare**. Alla sex gav samma
362,26 kr/hash och full godkänd lista. Före/efter-proven kördes seriellt,
inte i randomiserad ordning; värd-/OS-variation kan påverka små skillnader.

Första E efter A har två matchade observationer per arm: före
**12,97 / 13,20 s**, efter **12,06 / 12,22 s**, samtliga blockerade. Det tredje
fristående A/E-paret ryms inte i återstående budget. Den separata nya ägaren
ovan är en ägargränskontroll på redan varma offentliga strukturer, inte ett
tredje identiskt kallt prov. Ny ägare laddade noll personliga publiceringar;
exakt A-återanrop laddade sin enda tidigare publicering. Ingen p95 beräknas.

Den extra explicita legacy-kontrollen gav A på 76,86 sekunder genom GET för
samma 362,26 kr med egen godkänd audit. E gav samma `SEARCH_BLOCKED` efter
9,74 sekunder. V1:s oberoende legacy-kandidater per publicering finns kvar i
de faktiskt provade kontexterna. Detta är inte en full legacy-/standardgrind.

E kvalificerar två av 66 receptkandidater. 13 stoppas av policy/fördelning,
fem av näringsgränser och 46 av produktkvalificering. Den kvalificerade poolen
stoppas sedan av variationskapacitet (`dish_form`, högst två av samma form,
fem behövs). Det är ett belägg för denna kvalificerade pool, **inte global
matematisk omöjlighet**. Exempel i browsern visar saknad köpbar kapris/keso
och saknat tillämpligt näringsunderlag för bland annat ost/tomatpuré.

## Browser, förberedelse och prisbyte

Riktig Chromium 151, lokal Windowsklient över SSH-tunnel till den isolerade
HTTP-servern. Ingen plan-/pris-API mockas. A registreras, beräknas, sparas och
renderas som komplett inköpslista; därefter skickas första E via UI-knappen.
A-listan blev synlig efter 199,56 sekunder. För E kom 422 efter 12,50 sekunder
och det korrekta blockeringsbeskedet syntes efter **13,47 sekunder**. Ingen
färdig E-lista fanns. UI-begäran och rårapportens hash finns i
[browser.json](personal-choice-latency-20261025/browser.json).

Det första browserförsöket nådde A-listan på 193,81 sekunder men fastnade i
testverktygets navigering före E. Ett korrigerat omprov gjordes; en tidig
anslutningsreset under samma servers uppstart hanterades innan registrering.
Alla dessa tider, inklusive väntande isolerad server, belastar budgeten.

Ingen ny bakgrundsförberedelse eller driftkoppling har aktiverats. Den lilla
kampanjkartan byggs synkront vid första giltighetsläsningen och ingår i
start-/POST-tiden; dess egen byggtid har inte separat tidmätts. A-seed är en
riktig sparad användarberäkning, inte gratis bakgrundsarbete. E förvärms inte.
Omstart/eviction innebär korrekt miss; receptens innehållsregister kan leva
kvar vid prisbyte, medan nytt prisobjekt och full personlig prövning byggs om.

**Verklig veckouppdateringslatens är omätt.** Ingen andra behörig, validerad,
matchad fryst prisversion identifierades i etappens angivna underlag. Ingen
insamling startades för att fylla luckan. Små syntetiska regressioner visar
nytt pris 20→30, start/slut utan nytt snapshot-ID, negativa poster, aktuell
ålder, framtida observationer, omstart, single-flight och sen gammal version.
De är korrekthetsbelägg, inte mätning av en verklig kampanjpublicering.

## Minne, budget och stopp

Slutliga V2-prober läser cgroup även vid `atexit`, efter rapportserialisering
och stängning av klient/server. A/E-paret gav **1,284 GiB före / 1,245 GiB
efter**, och slutkodens legacy-kontroll **1,409 GiB**, utan swap eller OOM.
De tidigare V1-rapporterna läste peak före den sista rapportskrivningen:
prefixet visar 1,398/1,399 GiB, målsekvensen 1,308/1,305 GiB. Den scope-
begränsningen gör dem inte till slutliga serialiseringspeak. Ingen verklig
versionsbytespeak har mätts i denna etapp. Alla prov har 3 GiB som hårt tak;
de observerade värdena ligger under minnesmålet 2,5 GiB. Ett allmänt löfte om
peak vid versionsbyte eller alla personliga kombinationer lämnas inte.

Den stängda journalen summerar **7 027,84 s = 117,13 minuter av 120**.
**172,16 s återstår och används inte.** Alla starter, profileringar, avbrutna
prototyper, omtag och två konservativa förberedelseposter om sammanlagt
600 sekunder räknas. Alla reservationer är stängda och ingen mätcontainer
kör vidare. Vid första D-timeout stoppades sekvensens utvidgning; den korta
separata E-sekvensen dokumenteras ovan. Varken 252-cellsmatrisen eller något
5 000-prov har återupptagits. Implementation, korta regressioner och ordinarie
CI är separat arbete enligt uppdragets budgetregel.

## Verifiering och kvarvarande arbete

Riktade offlineprov för berörda pris-/readiness-/prewarm-/admission-/release-
gränser passerar: **92 offlineprov** i slutkontrollen. Nio nya kontraktsprov
täcker ändringen, UI-begärandenas utelämnade standardvärden och rapportens
budget-/utfallsintegritet. Ruff och compileall passerar. Ordinarie full CI
inklusive Chromium/WebKit på slutkoden kontrolleras via
[PR #12:s checkar](https://github.com/ossebosse/smako/pull/12/checks).
Diffgranskningen kontrollerar att privata kontexter, ägargränser, legacy,
referens, publiceringsordning och gemensam checkout inte ändrats.

Två försök med numerisk korgmemoisering gav inget tidslyft i den inledande
metoddiagnostiken och är återställda. Den första mätverktygsversionen gjorde
utelämnade modellstandarder uttryckliga och pollade var 0,2 sekund. Dess
observationer är därför märkta **uteslutna från UI-produktjämförelsen**.
De behålls som diagnostik och räknas fullt i budgeten. Den första omgången,
inklusive konservativ uppstartspost, stängdes vid 25,92 minuter; budgeten
återställdes aldrig vid metodrättningen.

Största återstående kostnaden är sökningens riktiga gemensamma korgberäkning:
före D-stoppet tog den 228 sekunder i basen. Den begränsade optimeringen löser
inte denna fas eller V1:s krav på oberoende förberedelse av publiceringarna.
Att hoppa över steg eller sänka sökbudgeten skulle ändra prisgarantin och har
inte införts. Nästa avgränsade arkitekturprov bör mäta och återanvända exakta
paket-/offertdelar genom befintlig `PackageCostCache`, med fulla produkt-,
mängd-, datum-, villkors- och metodberoenden, medan den gemensamma korgen och
aktuell audit behålls. En större cache eller mer förvärmning av personliga
kombinationer är inte visat som lösning. E behöver dessutom utredning av de
exakta produkt-/faktaluckorna i sin 66-receptspool för att kunna leverera fem
middagar. Ingen automatisk fortsättning eller lång verifieringsmatris är
planerad. Lund och full graföverlappning vid verkligt prisbyte är omätta.
