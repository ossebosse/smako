# Nästa uppdrag till Sol: förberedelsekostnad, minne och slutverifiering

**Ersatt arbetsordning 2026-10-25:** Följ
[CODEX-SOL-NEXT-20261025.md](CODEX-SOL-NEXT-20261025.md).
Etappen nedan avslutades på beställarens begäran. Starta inte om dess
fullmatris eller 5 000-prov; avsnitt 5 är inte längre ett aktivt uppdrag.
Bevara tidigare evidens och korrekthetskontrakt. Nästa etapp gäller nya
personliga val med 262 recept och en sammanlagd benchmarkbudget på två timmar.

Utgångspunkt: main `66bd85e`, runtime `9162f0f`, efter PR #8.
Arbeta i `D:\Projects\Smako` enligt `AGENTS.md`, `DEVELOPMENT.md` och
aktuell `HANDOFF.md`. Hämta aktuell main utan att skriva över annat arbete.
Implementera i avgränsade grenar och små granskbara commits; integrera
färdiga delar till main. Det här dokumentet anger nästa steg efter de
rättade granskningsfynden, inte en beställning att återimplementera dem.

Läs [arkitekturbeslutet](CODEX-SOL-ARCHITECTURE-20261023.md),
[granskningen](reviews/sol-architecture-review-20261024.md) och
[rättningsrapporten](reviews/sol-architecture-fixes-20261024.md).

## 1. Bevara det som nu fungerar

De två granskade felen är rättade. En oberoende omkörning av de 126 riktade
testerna passerade på main `66bd85e`. Malmö/fördelning/5 000 ger 988,32 kr
för både legacy och v1 i tre körningar, samma meny/hash och godkänd audit.
Rårapporternas hashar har kontrollerats mot det committade maskinunderlaget.

Följande är fasta korrekthetskrav under optimeringen:

- Båda cachevägarna låter nytillkomna sparade menyidentiteter från rätt
  ägare konkurrera. Ogiltiga menyer ersätter inte en giltig vinnare.
- Referens, föregående giltig vinnare och gamla fullbibliotekssökningens
  oberoende kandidat kan konkurrera efter aktuell checkout. Ingen gammal
  kassasumma eller näringskontroll återanvänds som ett nytt godkännande.
- Ägargränser, raderingsepok, faktaversion, återkallelser, lås, skafferi och
  prisdatum förblir korrekta även efter processomstart och cacheförlust.
- Axfoods godkända katalog + basrelease, LKG, negativa svar och återupptagning
  ska fortsätta fungera. Historiska bugprober som asserterar gamla fel är
  evidens; använd de nya permanenta regressionstesterna som acceptansprov.

Behåll `library_search_policy=legacy` och `library_merge_generations=False`
som standard tills hela standardgrinden faktiskt är verifierad. Ingen
produktionsaktivering eller ökad samtidighet ingår i detta uppdrag.

## 2. Profilera och minska förberedelsekostnaden först

Nuvarande Malmöprov: första v1-anropet tog **740,87 s**, varav **215,41 s**
var nya legacy-förberedelser över elva publiceringar. Därefter tog
menyträffarna cirka **8,4 s**. Detta är en stor skillnad mellan första
förberedelse och återanvändning. Gamla fullbibliotekssökningen får inte tas
bort för att vinna tid och återinföra prisregressionen.

Gör först en fasprofil på just detta reproducerbara fall, med fasta
indata och seriell körning på två CPU/3 GiB. Redovisa tid, antal verkliga
utvärderingar, träffar/missar och minnesökning för:

1. inläsning, modellbyggande, index och hashning;
2. kvalificering av recept;
3. referens och legacy-spår per publicering;
4. budgeterad förbättring per publicering;
5. slutkontroller, certifikat och databas-I/O.

Åtgärda den största uppmätta kostnaden först. Utred särskilt upprepad
utvärdering av oförändrade recept/korgar och om samma prefixarbete görs om
från början i varje legacy-förberedelse. Dela rena, exakt nycklade
delberäkningar och återanvänd färdiga resultat. Om ett söktillstånd ska
återupptas mellan publiceringar krävs bevis/test att det motsvarar den
oberoende legacy-körningen; en föregående vinnare som nytt seed är inte
tillräckligt, eftersom den kan ändra sökväg och pris.

Behåll oberoende tillstånd där ordning eller mutation påverkar sökningen.
Skippa inte publicerade föregångare på kalla körningar och påstå ändå
monotonicitet. Öka inte K eller utvärderingsbudget som ersättning för en
förklaring till kostnaden. Proxyprioritering får inte bli obevisad gallring.

Förberedelse kan schemaläggas inom befintliga planjobb/admission, men att
flytta samma arbete till bakgrunden räknas inte som minskad beräkningstid.
Redovisa både total kostnad och användarens väntetid. Jobs ska ge sann
progress och kunna avbrytas mellan avgränsade arbetsenheter. Starta ingen
ny extern kö eller automatisk driftuppgift.

Leverera en matchad före/efter-mätning på samma maskin och samma cacheläge.
Första förberedelsen ska bli snabbare än den nuvarande implementationen
utan sämre giltighet/pris. Sätt ett konkret uppmätt delmål efter fasprofilen
och dokumentera utfallet; utlova inte konstant kallstartstid för godtyckliga
nya personliga krav. Jämför också mot legacy och redovisa kvarstående merarbete.

## 3. Skapa verklig minnesmarginal

Målet för nästa iteration är **högst 2,5 GiB cgroup-peak** inom oförändrat
3 GiB-tak. Senaste samlade körningen nådde 2,906 GiB och omstartsprovet
2,639 GiB. Ingen av dessa visar att målet är uppnått.

Mät var de stora objekten lever och frigörs. Undersök särskilt samtidig
materialisering av publiceringskohorter, duplicerade kandidater och
produktgrafer, sökspår samt förberedelse-/offertcachernas sammanlagda storlek.
En maxgräns per cache är inte en total minnesbudget.

Materialisera endast nödvändigt prefix där det bevarar ordning/semantik,
släpp avslutade söktillstånd och dela endast bevisat immutabla värden.
Diskcertifikat och prisgarantins referens/vinnare får inte försvinna för
att RAM evikteras. Testa också tillfälligt minne vid versionsbyte och
serialisering. Lägg inte till workers eller större containergräns för
att få provet att passera.

## 4. Mät cachelägen var för sig

Använd separata processer/kataloger där det krävs. Dokumentera vad som
fanns vid start och vad som skapades under varje körning:

| Fall | Vad som ska verifieras |
| --- | --- |
| Ny process, tom app-/förberedelsecache, ny ägarstore | Verklig kostnad att bygga bibliotekets underlag och certifikat |
| Ny process, varm offentlig diskcache, tom ägarstore | Kostnad för ny personlig kontext trots förberedda offentliga data |
| Ny process, varm disk och sparade certifikat | Återstart utan omsökning av färdiga publiceringar |
| Upprepning i samma process | Varm planering inklusive ny slutkontroll |
| RAM-eviction och borttagen härledd cache | Återhämtning, bevarad ägarhistorik och oförändrad prisgaranti |
| Ny giltig/ogiltig sparad meny | Rätt vinnare utan onödig full omsökning |

Tom appcache betyder inte kall OS-disk. Rensa inte en delad servers
OS-cache för testets skull. Om isolerat kallt OS-underlag saknas, skriv
att det inte är mätt. Skilj hela processens väggtid, plananrop, kötid,
förberedelse och audit. Kör minst tre mätningar per jämförbart läge;
redovisa spridning och cacheträffar, inte bara bästa provet.

## 5. Pilot, därefter hela verifieringen

Efter riktade korrekthetstester: återkör Malmö/fördelning/5 000 med målet
988,32 kr eller billigare på det frysta underlaget. Fortsätt med standard,
fördelning och organic-share i Lund och Malmö vid 262 och 5 000. Piloten
ska identifiera kvarstående minnes-/kallstartsproblem före en dyr fullmatris.

När piloten håller: slutför den definierade matrisen för alla sju profiler,
båda städerna, 262/1 000/2 000/5 000, gamla respektive nya sökpolicyn och
v5-referensen vid 262. Inventera cellerna med alla dimensioner och separera
originalfakta från berikade fakta; ett historiskt antal på 252 är inte i
sig en fullständighetskontroll. Kör den Axfood-faktaarm som den tänkta
releasen ska använda och ange exakt manifest/täckning.

Acceptansvillkor:

- Noll oförklarade pris-/utfallsregressioner mot bas, föregående
  publicerade storlek och legacy på samma fulla bibliotek och kontext.
- Samtliga levererade menyer klarar aktuell audit och alla kvalitetskrav.
- 3 GiB hårt tak och redovisad 2,5 GiB-marginal; ingen OOM eller dold swap.
- Varmt, färdigförberett 5 000-bibliotek uppfyller arkitekturens högst
  1,25 gånger motsvarande 262-tid per profil och är inte långsammare än
  jämförbar nuvarande fullbibliotekskörning. Det är inte en kallstartsgaranti.
- Saknad evidens, avbrott och ofullständig sökning hålls skilda från
  godkänd cell och bevisad omöjlighet. Tidigare versioners resultat räknas
  inte automatiskt som slutkodens resultat.

Vid ett nytt konkret fel: bevara motexemplet och rätta det före fortsatt
standardkvalificering. Lämna policyn opt-in om någon grind återstår.

## 6. Axfood och slutleverans

Ägarens godkännande av Axfood-berikningen gäller fortsatt. Reader-releasen
och insamlingsarbetet är separata från denna prestandaetapp. Beskriv ärligt
att nuvarande arkiv är partiellt (103 verifierade dokument); hävda inte
full täckning eller återverifiering av det saknade historiska Malmöarkivet.
En större godkänd faktarelease kräver ny invalidation, projektion och
profiljämförelse enligt det befintliga arkitekturbeslutet. Den här etappen
ska inte tyst ändra aktiv fakta-/prisversion, insamlingsschema eller drift.

Kör relevanta regressionstester, Ruff och compileall under arbetet samt
full CI inklusive browserprov på slutkoden. Behåll de nya cache-/Axfood-
regressionerna. Spara maskinläsbar cellstatus, kommandon, resursgränser,
kod-/metod-/biblioteks-/indatahashar, tider, minne och auditutfall.

Uppdatera HANDOFF och skriv en ny rapport som tydligt anger:
vad som ändrats, vad som verifierats, hur mycket första förberedelsen och
minnet förbättrats, vilka grindar som passerar och vad som eventuellt
återstår. Avsluta inte med enbart ”tester gröna” eller varm cachetid om
förberedelsekostnad, minne eller matris fortfarande saknar godkänt underlag.
