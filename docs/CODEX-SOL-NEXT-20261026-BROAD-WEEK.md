# Sol: få det breda veckourvalet att leverera inom tidsmålet

Ägarens uppdrag efter granskningen av PR #17/main `719b927`, 2026-10-26.
Arbeta i `D:\Projects\Smako`, hämta senaste main och följ AGENTS,
DEVELOPMENT, PRODUCT-GOAL, PLANNING-ARCHITECTURE och HANDOFF.
Detta ersätter VALID-WEEK-AND-COVERAGE som nästa uppdrag. Läs först
[den oberoende granskningen](reviews/review-pr17-and-next-20261026.md)
och [Sols senaste rapport](reviews/valid-week-and-coverage-20261026.md).

## Avgränsning och utgångspunkt

Behåll framstegen: B2 ger en verklig femmiddagsvecka för fyra, 731,20 kr,
API/save/GET 30,25 s och strikt browserprov 31,86 s. Köpbarheten är
738 exakta/931 inklusive tillåtna uppskattningar av de 2 200 importerade
varianterna. Recept, källor, standardkonfliktens lösning, skafferival,
deadline och revisionsskydd ska bevaras. Oberoende 116 riktade tester
passerar. Inga nya blockerande korrekthetsfel har påvisats i PR #17.

Nästa huvuduppgift är **det breda A-fallet**, inte mer receptimport,
nya användargränser eller en stor allmän testmatris. A når 2 021 råa/
960 kvalificerade recept men får ingen lista vid 60,28 s. Sökningen
stannar på två av fem middagar. Färre filter får inte göra standardvalet
praktiskt oanvändbart. Ingen ny prisregressionstolerans godkänns.

## 1. Ta bort dubblerad första-måltidsberäkning

Det finns en konkret reproducerad cachebrist att börja med:

- `_candidates` i `personal_planner.py` beräknar enreceptskorgarna och
  behåller de sista 256 i `qualified_results` (omkring rad 2503).
- `MenuOptimizer.optimize_slots` för över dem till samma 256-posterscache
  som används vid fortsatt iteration i ursprunglig ordning.
- Äldre kandidaters omberäkningar tränger undan förberedda resultat innan
  iterationen når dem. A:s djup ett gör 960 utvärderingar och får noll
  träffar. Ett isolerat prov med 300 kandidater och de sista 256 förifyllda
  gav också 300 nya utvärderingar/noll träffar.

Återanvänd samma anrops redan utförda arbete med en genomtänkt,
minnesbegränsad överföring. Enbart större LRU eller en annan ordning utan
bevarad tie-break räcker inte. Överväg att konsumera resultaten när de
produceras, behålla kompakta ranknings-/giltighetsunderlag och endast de
fulla resultat som nästa steg behöver. Motivera det valda alternativet.

Behåll skillnaden mellan `final=False` och full veckoaudit. Pris-/fakta-/
butiksversion, mängder, måltidens identitet, skafferi, extravaror, lås,
krav och ägarscope ska matcha där ett resultat återanvänds. Resultat från
generering får inte felaktigt användas vid byte av en låst måltid eller
för en annan ägare. Ren offentlig förberedelse får fortsatt delas enligt
befintligt kontrakt; personlig kvalificering är inte en sådan artefakt.

Lägg små regressioner med fler än 256 kandidater, olika ordning och
likaprisfall, fallback, ändrade mängder/privata val och minnesgräns.
Visa både antal undvikna evaluatoranrop och samma korrekta utfall mot
okachad körning. Använd billiga evaluatorer för detta, inte långa verkliga
priskörningar eller tusentals duplicerade skenrecept som latensbevis.

## 2. Nå en fullständig giltig kandidat innan sökbudgeten tar slut

Enbart cachefixen bevisar inte att A klarar tiden. Nuvarande sökning
prissätter hela nästa bredd innan den går djupare. Med 960 kandidater
och beam åtta blir exakta delkorgar ett stort arbete före första fulla
veckan. Följ redan beslutad V2-riktning i befintlig sök-/checkoutkedja:

1. Använd kvalificerade recept och kompakta struktur-/produktuppgifter
   till att tidigt föreslå en hel vecka. Kontrollera fördelning, distinkta
   baser, matkök, huvudproteiner, aktiva hårda krav och kvarvarande
   kapacitet under konstruktionen. En strukturell kandidat är ännu inte
   godkänd; gör riktig gemensam checkout/närings-/ekokontroll.
2. Behåll en fullständig giltig bästa kandidat och förbättra dess verkliga
   gemensamma kassakostnad inom återstående tid. Återanvänd oförändrade
   behov och verifierade delberäkningar med rätt beroenden. Undvik att
   återutvärdera identiska menyer i olika ordning när ordningen faktiskt
   saknar betydelse; behåll skillnader vid privat skafferiallokering/lås.
3. Prioritering eller successivt bredare sökning får användas, men den
   får inte bli ett nytt permanent tak på aktiva recept eller en dold
   inskränkning av användarens val. Redovisa sökt, uppskjutet och säkert
   uteslutet underlag. Heuristisk prioritering är inte ett optimumbevis.
   Tysta pris-/faktakravslättnader eller bara de billigaste individuella
   recepten är inte en ersättning för gemensam korgoptimering.
4. Använd en mjuk stoppunkt för förbättring före den absoluta 60 s-gränsen,
   med uppmätt marginal för slutlig aktuell checkout/audit, lagring och UI.
   Tiden räknas från samma begärans början, inklusive kö och kvalificering.
   En full kandidat ska inte gå förlorad enbart för att förbättringssökningen
   förbrukar all slutkontrollstid. Returnera dock aldrig en ofullständig
   eller ej slutkontrollerad kandidat som framgång.

Utöka befintlig planner; inför ingen parallell prismotor, ny generell
scheduler eller stor solveromskrivning i denna etapp. Ingen allmän
omläggning av kvalificering krävs om den verifierade återanvändningen och
tidigare kompletta kandidater räcker. Förbered fortfarande gemensamt
underlag per recept/ingrediens/butik/prisversion, inte alla personliga
kombinationer eller alla butiksdelmängder.

Verifiera med små uttömmande orakel: individuellt billigast kan vara en
dyrare helkorg; delade ingredienser, pakettrösklar, kopplade kampanjer,
butikstak samt produktalternativ för näring/eko måste kunna påverka valet.
Testa en fälla där de första billiga recepten blockerar veckovariationen,
och att senare kandidater kan ge en giltig eller billigare full meny.
Bevara deadline-, avbrotts-, save/GET- och ägarskydd.

## 3. Liten, beslutande mätning på riktiga anrop

Använd `docs/reviews/valid-week-and-coverage-20261026/requests.json` och
kvittonas faktiska normaliserade anrop. **A ska vara oförändrat**, med
fem middagar/fyra portioner och dess övriga ursprungliga val. Behåll
aktuellt 2 462-bibliotek, samma Malmöunderlag, 52 tillåtna butikskontexter,
testklocka, inköpstak och mängd-/näringspolicy enligt det sparade A.
Om A saknar nytt variation-intent får du inte lägga till det i smyg.
B2 är ett separat regressionsfall med sin dokumenterade policy.

- Återanvänd befintligt misslyckat A som baslinje. Starta första nya A
  först efter relevant kodändring och små korrekthetsprov. Högst tre
  nya A-försök i etappen, varje ytterligare försök ska besvara en konkret
  fråga efter en ändring. Ingen upprepad oförändrad timeout.
- Redovisa tid till första fullständiga giltiga kandidat, tid och pris
  efter förbättring, slutlig checkout/audit/save/GET, återanvända respektive
  nya korgar på varje djup, sökta/uppskjutna kandidater, cacheminne och
  hela användaranropet. Registrera även om sökningen inte når full vecka.
- När A lyckas inom 60 s: gör ett verkligt browserprov med exakt samma
  skickade och sparade begäran och hela inköpskorgen, även skafferival.
  Ny personlig begäran/ägare, ingen förvärmd identisk färdigplanscache.
- Kör ett matchat B2 efter färdig ändring. Vid oförändrade krav, priser
  och underlag får det inte bli dyrare än kända giltiga **731,20 kr**.
  Verifiera protein, fördelning, variation, butiker och save/GET igen.
  Ingen osäker kandidat blir godkänd bara för att summan är lägre.
- A saknar tidigare giltig vinnare/pris. Säg det tydligt; dess gamla
  timeout är ingen nollkronorsreferens. Små orakel och B2 är stöd för
  priskvalitet, inte ett globalt optimumbevis för A eller hela produkten.

Gör inga nya köpbarhetsinventeringar om recept-/produkt-/mängdlogiken och
dess läsberoenden är oförändrade. Hänvisa då till 738/931 med samma tydliga
begränsningar. Om en sökändring påverkar kandidatgiltighet ska just den
ändringen verifieras; använd inte gammalt underlag som ett nytt godkännande.
Limejuice och ansade mängder är kända källbehov för nästa separata etapp;
ingen bred insamling, ny massimport eller fler rutinprofiler ingår här.

## 4. Budget och leverans

Fortsätt samma `docs/reviews/recipe-integration-800-20261025/budget.json`.
Senast **4 926,7738 s använda / 2 273,2262 s kvar = 37,89 minuter** av
totalt 120. Läs aktuell journal och nollställ inte. Det är mätbudget,
inte ett påstående om total utvecklingstid.

`budgeted_check.py`, gemensamt OS-lås, en dyr arbetare, två CPU,
hårt 3 GiB commit och mål högst 2,5 GiB inklusive versionsöverlapp gäller.
Start/laddning/förberedelse, misslyckanden och omtag debiteras. Ange
separata stoppgränser före start, högst 75 s testövervakning per
användaranrop; över 60 s är missat produktmål. Ingen nattlig fortsättning,
gammal 252-cellsmatris eller oändliga baslinjer. Avsluta med konkret
delrapport om försöksgränsen eller budgeten nås.

Kör relevanta fokuserade regressioner, Ruff/compileall och ordinarie CI
inklusive berörda browserprov. Undvik identiska verifieringsomtag utan
nya ändringar. Integrera verifierade små commits på main enligt DEVELOPMENT.
Skriv `docs/reviews/broad-week-search-20261026.md` och kompakta maskinkvitton;
uppdatera HANDOFF och arkitekturen endast där beslutet har konkretiserats.

Leveransen ska svara: försvann dubbelberäkningen, nåddes en full A-vecka,
vad blev verklig klicklatens och pris, bevarades B2:s pris/giltighet,
vilken total minneskostnad tillkom och vad är nästa kvarstående hinder?
Om ingen giltig A levererades ska det stå först, utan att minskat arbete
eller snabbt avslag räknas som färdig inköpslista.

`legacy` är fortsatt standard, `library_merge_generations=False` och
V2 opt-in. Ingen beta-/produktionsaktivering, scheduler-/profiländring
eller bred prisinsamling ingår. UI-butikstak 1..N, samtidighet och verklig
veckouppdatering är fortfarande egna oavslutade produktkrav.
