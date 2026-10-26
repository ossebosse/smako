# Sol: nästa etapp efter PR #12 — förberett underlag och gemensam sökning

**Aktuell prioritering 2026-10-26:** följ först
[receptkvalitet, köpbarhet och avgränsad personlig mätning](CODEX-SOL-NEXT-20261026-RECIPE-QUALITY-AND-PLANNING.md).
Massimporten är klar. V2-riktningen nedan kvarstår, men hela implementationen
och 1 000-/5 000-proven är inte leveranskrav i den nya avgränsade etappen.
Budgeten är redan påbörjad och delas fortsatt: använd befintlig intakejournal
och aktuellt saldo. Ordet ”ny” i den ursprungliga budgettexten nedan ger inte
en ny budget vid nästa sessionsstart.

Tillägg efter ägarens receptleverans 2026-10-25: läs först
[receptuppdraget](CODEX-SOL-NEXT-20261025-RECIPE-INTAKE.md). Prioritera
ingrediens-/innehållsarbete före stora skalprov och använd den verkliga
granskade samlingen när den är tillgänglig. Nedanstående V2-riktning gäller
fortsatt; benchmarkbudgeten delas med receptuppdraget och dubbleras inte.

Utgångspunkt main `d27e0cf`; hämta aktuell main i `D:\Projects\Smako` utan
att skriva över annat arbete. Följ `AGENTS.md`, `DEVELOPMENT.md` och aktuell
`HANDOFF.md`. Läs först [produktmålet](PRODUCT-GOAL.md), därefter
[den uppdaterade arkitekturen](PLANNING-ARCHITECTURE.md) och
[Sols senaste rapport](reviews/personal-choice-latency-20261025.md).

Detta är ett nytt, avgränsat implementationsuppdrag. Det ersätter det
avslutade `CODEX-SOL-NEXT-20261025.md`. Målet gäller 30–60 sekunder för nya
personliga val och tusentals recept. Att denna etapp börjar med små fall
begränsar inte produktmålet. Återstarta inte den gamla 252-cellsmatrisen.

## 1. Gör en exakt karta över blockerarna

Återanvänd redan frysta riktiga UI-begäranden A–E och deras mätunderlag.
Jämför inte gamla direktanrop med nya API-tider eller olika sökpolicyer.
Ingen ny bred baslinjematris behövs.

- D: skilj tid/antal i offertberäkning, konstruktion/hashning av kandidater,
  materialisering av butiksdelmängder, menyutvärderingar, personliga närings-/
  ekospår, historiska publiceringar och kompletterande slutjämförelser.
- E: dokumentera varför 46/66 kandidater föll på produktkvalificering och
  varför bara två klarade allt. Gruppera exakta orsaker: saknad köpbar vara,
  felaktig matchning/form/enhet, saknade tillämpliga fakta, verklig kravkonflikt
  eller sökbegränsning. Spåra några representativa avslag till källreferens.
- Rita en kort tabell från UI-val till normaliserat API-fält och faktiskt
  tillämpat krav. Ta med dolda/ärvda standarder såsom `balanced`, variations-
  och ingrediensgränser; skilj dem från uttryckliga ändringar. De får inte
  tyst stängas av för att få E att passera.
- Kontrollera var `PackageCostCache` faktiskt används i personliga flödet,
  inklusive dess livslängd och nyckelkostnad. Numerisk memoisation som redan
  återställdes får inte återinföras utan en ny, mätbar förklaring till vinst.

Rätta konkreta matchnings-/projekteringsfel med befintligt godkänt underlag
och riktade tester. Saknas källdata: lämna en prioriterad lista över exakta
luckor och hur många användarfall/recept de blockerar. Ingen fabricerad näring,
allergen-/ekostatus eller tillfällig sänkning av krav. Axfoods tidigare
principgodkännande gäller; bred ny insamling ingår inte i denna etapp.
Använd redan tillåtna spårbara näringsreferenser/uppskattningar där deras
form- och användningskontrakt faktiskt passar, med bevarad status. Det är
inte ett tillstånd att anta okänd allergen- eller ekologisk information.

## 2. Implementera en sammanhängande V2-prototyp

Prioritera en fungerande vertikal del genom befintligt API/planjobb till
gemensam checkout, sparning och återläsning, under den nya opt-in-policyn
`smako-prepared-personal-v2`. Behåll legacy/V1 oförändrade. Följ arkitekturens
beroendegränser; skriv inte om hela applikationen.

Leveransen ska åtminstone innehålla:

1. Gemensamma versionsbundna strukturer för det aktuella bibliotekets recept
   och relevanta produkt-/faktakopplingar, återanvändbara mellan olika krav
   och ägare. Förbered inte exakt testprofil E eller varje personlig kombination.
2. En personlig sökväg som använder aktuellt manifest utan att återspela
   alla historiska generationer. Testa att fler historiska publiceringar med
   samma aktiva innehåll inte startar fler fulla sökningar i V2. Bevara aktuella
   giltiga tidigare vinnare som kandidater och redovisa ny kvalitetspolicy.
3. En mätbar minskning av det verkliga arbetet i korg-/butikssökningen:
   återanvänd exakta paketdelar när profileringen stöder det, minska upprepade
   helkorgsutvärderingar och ersätt full materialisering av butiksdelmängder
   i den nya sökvägen. Behåll alla relevanta produkt-/kampanjalternativ.
4. Deadline genom hela anropet, inklusive inre dyra loopar och audit/save.
   Ge full giltig lista eller korrekt separat status. En blockerad lista
   eller en avbruten sökning räknas inte som lyckat prestandaprov.
5. Flytta bevisat fristående jämförelser med färre butiker från huvudsvaret
   till efterfrågad komplettering, om de bidrar till kostnaden. Behåll riktig
   prisberäkning, kravkontroll och full inköpslista före leverans.

En prototyp som inte täcker ett val ska vara tydligt otillgänglig för det
fallet och räknas som kvarstående arbete. Inget tyst bortfall av exempelvis
eko-, frukost-, allergi- eller flerpacksvillkor. Enbart ett nytt felbesked
eller sänkt sökbudget uppfyller inte uppdraget.

Välj eventuell ny solver först efter litet jämförande prov med exakt
checkout och kända optima. Om korrekt modellering av gemensamma kampanjer
eller näring hindrar den avgränsade leveransen: dokumentera det konkreta
hindret och bästa verifierade deländring. Behåll prototypen opt-in och
rapportera återstående arbete; starta ingen obegränsad omskrivning.

## 3. Förbered större butiksval och prisuppdatering i samma riktning

Implementera och testa kontraktet 1..N/alla valda, där N kommer från det
faktiska normaliserade butiksurvalet. UI, API, sparning/återläsning, butiksvy
och optimerare ska vara överens. Äldre sparade heltalstak behåller betydelsen.
Höj inte bara UI:s tre/API:s fyra medan kombinatoriska loopar ligger kvar.
Aktivera inte ett ofärdigt utökat butiksval för legacy-defaulten; exponering
ska följa en komplett verifierad sökväg. Redovisa färdig backend och faktisk
UI-tillgänglighet var för sig.

Anslut förberedelsen till befintlig versionslivscykel i isolerad miljö.
Visa vad som byggs vid installation, nya recept, nya fakta och nya priser,
vad som återanvänds samt total tid/minne för det. En sen äldre beräkning får
inte publicera sig över en ny version. Kampanjgräns ska gälla utan nytt ID.
Sök i befintliga behöriga underlag efter två matchbara prisversioner; om de
saknas, behåll verklig veckolatens som omätt och använd tydligt syntetiska
korrekthetsprov. Ingen driftuppgift eller produktionsaktivering startas.

## 4. Små korrekta prov först, sedan få användarprov

Använd uttömmande små orakel för exakt pris och feasibility: gemensamma
ingredienser, olika förpackningar/flerköp, kopplade kampanjer, butikstak,
faktisk produktnäring och ekologisk kostnadsandel. Testa ändrade profiler,
ägare, skafferi, medlemskap, fakta, prisdatum, eviction och versionsbyte.
Kandidater som gallras säkert ska kunna förklaras av giltiga gränser.

Testa K=1, 2, 4 och alla valda i ett litet butiksunderlag med känt optimum,
samt minst ett större urval med 10 eller fler butiker. Därutöver riktade
gräns-/kombinationsprov för hela valkatalogen i produktmålet; ingen full
kartesisk prestandamatris. Lägg inte ett exponentiellt orakel på det stora fallet.

Prestandaprioritet i ordning:

1. Första A och D med 262 recept; full lista, aktuell audit och GET.
2. Första oförändrade E. Om källdata fortsatt blockerar: behåll utfallet och
   lägg till ett separat ärligt genomförbart kombinationsfall för latens.
   En syntetisk lösbar fixtur får inte ersätta verklig täckning i rapporten.
3. Ny ägare, ändrade val och ett förberett återanrop; minst ett verkligt
   browserprov av ett lyckat nytt personligt val utan mockad plan-/pris-API.
4. När den nya vägen klarar 262 utan pris-/giltighetsregression: ett begränsat
   storleksprov med 1 000 och ett med 5 000 på V2, med stoppgräns. Detta är nya
   skalprov för aktuell sökväg, inte återstart av den gamla V1-matrisen.
   Ange unika recept, tillåtna/kvalificerade kandidater och faktisk sökdomän;
   5 000 inlästa men bara 262 sökbara räknas inte som uppnådd skala.

Jämför pris mot matchande legacy/V1 och tidigare giltig vinnare. Gamla dyra
referensresultat får användas med verifierade identiska indata/mätkontrakt;
saknad jämförelse markeras omätt. Påstå inte global optimalitet utan giltigt
bevis för hela domänen. Oförklarad pris-/utfallsregression stoppar utvidgning.

## 5. Budget och leverans

Ny sammanlagd benchmarkbudget: **högst 120 minuters väggtid för hela etappen**,
inklusive uppstart, förberedelse, profilerare och omtag. Första diagnos/
mikroprototyp högst 20 minuter av dessa. Utvidga inte en misslyckad strategi
med större cacher eller fler hela körningar utan nytt konkret fynd.

V2:s användaranrop har 60-sekunders produktmål; testövervakaren bryter senast
vid 75 sekunder för att fånga fel i deadlinehanteringen. Allt över 60 är
ett missat mål. Ett redan känt långsamt basanrop får vid behov mätas en gång
med högst fem minuter, men återanvänd hellre korrekt tidigare evidens.
Förberedelse har egen deklarerad batchgräns inom totalbudgeten, inte ett
undantag från den. Ingen automatisk fortsättning över natten.

Håll samma två CPU/3 GiB, seriellt, högst 2,5 GiB som minnesmål inklusive
versionsöverlappning. Redovisa maskinavvikelser utan hopblandade tidskvoter.
Korta regressioner, implementation och ordinarie CI är separata från
benchmarkbudgeten; döp inte om lång prestandakörning för att kringgå den.
Ruff, compileall och relevant/full ordinarie CI inklusive browserprov ska
passera före integration. Dokumentations-/databrist är inte en grön menycell.

Leverera granskade små commits på main och
`docs/reviews/prepared-personal-planning-20261025.md` med kompakt maskinunderlag
och uppdaterad HANDOFF. Ange:

- Vad som faktiskt implementerats och återstår, inklusive val som ännu saknas.
- Första nya val kontra återanrop; förberedelsekostnad separat; browser/GET
  och kö skilda från motor-/profilerartid. Antal observationer och spridning.
- Pris, audit, datatäckning, blockerade/avbrutna fall och eventuell optimalitetsgräns.
- Skalning av aktuella recept, butiker och historiska publiceringar; minnespeak.
- Hur långt vi är från 30–60 sekunder och nästa största konkreta hinder.

Lämna legacy som default och `library_merge_generations=False`. Integrerad
experimentkod är inte produktionsaktivering eller ett uppnått produktmål.
Om etappen inte räcker: avsluta med verifierade delresultat och ett avgränsat
förslag, inte en ny mångdygnskörning.
