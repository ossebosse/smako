# Nästa uppdrag till Sol: kort väntan när användaren ändrar sina val

Datum: 2026-10-25. Dokumentationsbas: main `b604840`, efter PR #11.
Arbeta i `D:\Projects\Smako`. Läs `AGENTS.md`, aktuell `HANDOFF.md`,
`DEVELOPMENT.md` och `CONSOLIDATION.md`; hämta main utan att skriva över
annat arbete. Implementera en avgränsad förbättring, verifiera och integrera
granskade delar på main enligt repoets arbetsflöde.

**Detta ersätter nästa arbetsordning och testomfattning i
[CODEX-SOL-NEXT-20261024.md](CODEX-SOL-NEXT-20261024.md), särskilt avsnitt 5.**
Återuppta inte den stoppade 252-cellsmatrisen eller 5 000-körningarna.
Tidigare pris-, giltighets- och ägarkontrakt i
[arkitekturbeslutet](CODEX-SOL-ARCHITECTURE-20261023.md) gäller fortsatt.
Den begränsade etappen innebär ingen godkänd full standardgrind.

## 1. Produktfrågan som ska lösas

Användaren ska kunna välja matkök, ändra proteinmål och välja endast
kyckling/vegetariskt utan att varje ny kombination utlöser flera minuters
upprepat arbete på en redan startad server. Samma fråga gäller det första
planförslaget efter nya kampanjpriser. Mät från användarens begäran till
färdig, kontrollerad och sparad inköpslista, inte bara jobbets mottagningskvitto.

Nuvarande 7–12 sekunder gäller förberedda återanrop i vissa motorprov.
De är inte ett belägg för nya personliga kombinationer eller hela webbflödet.
`planner_context.py` binder hela begäran och relevant privat tillstånd;
nya val ger en ny kontext även när recept och produkter finns i RAM.
En ändrad pris-/faktaversion ogiltigförklarar kontexten. Befintlig
`plan_prewarm.py` värmer vissa standardfall, inte alla personliga krav.

Underlaget finns i [slutrapporten](reviews/preparation-memory-final-20261025.md)
och [detaljrapporten](reviews/preparation-memory-20261024.md). Bevara de uppnådda
förbättringarna: 24,79 procent kortare första anrop och 33,20 procent lägre
minnespeak i det matchade Malmö/fördelning/5 000-provet. De procenttalen
gäller det fallet, inte alla nya val.

**Produktmål att pröva:** högst 15 sekunder för ett exakt förberett återanrop
och högst 30 sekunder för första anropet med nya vanliga personliga val på
varm server, med dagens 262 recept och utan kö. Detta är utvecklingsmål,
inte nuvarande garantier eller lov att minska korrektheten. Redovisa också
hur långt från målet utfallet ligger. Utebliven måluppfyllelse ska resultera
i ett konkret besked om återstående kostnad, inte obegränsad fortsatt körning.

## 2. Arkitekturriktning: återanvänd delarbete mellan olika krav

Inventera först vilka läsberoenden de dyraste funktionerna faktiskt har.
Utöka befintlig planner och dess cache-/förberedelsemoduler; skapa ingen
andra pris-, närings-, korg-, refresh- eller kömotor. Välj den största
uppmätta återkommande kostnaden och genomför en sammanhängande förbättring.

Skilj följande beroenden i befintliga delberäkningar:

1. **Recept och opersonliga fakta.** Exakt receptinnehåll, klassificering,
   ingrediensnormalisering och andra bevisat rena strukturvärden får delas.
   Produktspecifik näring binder produktidentitet, form, faktaversion och
   relevanta metodversioner; den är inte automatiskt oberoende av produktval.
2. **Pris- och butiksunderlag.** Återanvänd opersonliga kandidater och rena
   offertdelar med fulla beroenden: manifest, artikel/butik, källscope,
   prisdatum/kampanjvillkor, mängd, förpackning och inköpsvillkor där de läses.
   Medlemskap och privata förmåner får inte bli offentliga cachevärden.
3. **Personlig sammansättning och slutkontroll.** Matkök, protein-/kostkrav,
   portioner, fördelning, allergier, skafferi, lås och historik tillämpas på
   aktuella indata. En ny kombination får återanvända oberoende byggdelar,
   men måste få en egen giltig bedömning och aktuell gemensam checkout/audit.

**Ta inte bort fält ur den fullständiga kontextnyckeln för att få fler
träffar.** Behåll den som gräns för personliga resultat och certifikat.
Om en dyr delberäkning får en smalare nyckel ska dess beroenden beskrivas
och testas separat. Inkludera negativa resultat, versionsbyte, återkallelser
och ägargränser. Gamla poster ska få säker miss när kontraktet ändras.

Byt inte ut den riktiga gemensamma korgberäkningen mot summor av receptpriser:
förpackningsavrundning, delade ingredienser, flerpack och butikstak kan göra
det fel. Näringsmål gäller den faktiska godkända produkten/portionen.
Grova index får bara filtrera bort kandidater när det är bevisat säkert;
topplistor eller avrundade näringsintervall får inte ändra möjliga vinnare.

Referens, tidigare giltig vinnare, legacy-kandidat och publiceringskedjans
oberoende söksemantik ska fortsatt bevaras där kontraktet kräver dem.
Återanvändning av strukturer får inte dela muterbart söktillstånd mellan
användare eller ändra ordning, skiljeregler och determinism. Hela sökresultat
från andra krav får inte behandlas som ett giltigt certifikat för nya krav.

Om kvarvarande sök-/prisgarantier hindrar 30-sekundersmålet efter den
avgränsade optimeringen: visa vilken fas som kostar och beskriv nästa
arkitekturval med dess konsekvens. Inför inte ett dolt sämre eller ofullständigt
resultatläge. Ett snabbt jobbkvitto eller en första delmeny är inte en färdig lista.

## 3. Prisuppdatering och bakgrundsförberedelse

Skilj installation/processomstart från ett nytt prisunderlag. Beskriv exakt
vad som kan återanvändas vid respektive händelse och vad som måste byggas om.
Efter ett validerat byte av PriceUniverse ska endast data med fortfarande
giltiga beroenden återanvändas. Gamla godkända priser får inte överleva som
godkännande av den nya korgen; kampanjens start/slut måste gälla även utan
nytt snapshot-ID. LKG och observationstid behåller befintlig betydelse.

Förbered gemensamma, opersonliga delar via befintlig förberedelse/admission
om profileringen visar att det hjälper första användaren. Det är tillåtet
att implementera och prova kopplingen isolerat inom etappen. Använd den
befintliga versions-/aktiveringslivscykeln, single-flight och avbrott; skapa
ingen ny scheduler eller extern kö. Bygg inte alla kombinationer av matkök,
proteinvärden och kostfördelningar i förväg. Privata historiker och menyer
ska stanna i ägarens lager.

Redovisa separat kostnad för bakgrundsförberedelse, tiden tills underlaget
är redo och användarens väntan både före och efter detta. Bakgrundsarbete
ska respektera befintlig admission och får inte tränga undan användarjobb.
En gammal förberedelse som avslutas efter ett versionsbyte får inte publiceras
som aktuell. Kall miss eller avbruten förberedelse måste ha korrekt fallback.
Att flytta samma arbete före knapptrycket är kortare väntan, inte i sig
minskad total beräkningskostnad. Påstå inte att en driftkoppling är aktiverad
bara för att dess kod och isolerade tester finns.

## 4. En liten, representativ mätning

Utgå från dagens exakta 262-receptsmanifest, samma frysta godkända pris-/
faktaunderlag och samma testklocka före/efter. Använd den redan godkända
Axfood-armen där den är avsedd; dokumentera dess partiella täckning utan att
dubblera hela matrisen. Först Malmö; Lund är en begränsad kontroll av standard
och kombinerade val om tidsbudgeten räcker. Ingen liveinsamling behövs.

Använd fem middagar, fyra portioner och högst två butiker där underlaget
stöder det. Bind verklig API-normalisering, medlemskapspolicy och tillåtet
postnummer. Skapa egna testägare med riktig sparad historik, inte privata
produktionsprofiler. Ingen direkt mutation av revisioner för att få cacheträff.

Frys följande giltiga begäranden innan före/efter-jämförelsen:

| Fall | Val som ska mätas |
| --- | --- |
| A | Standard utan extra personliga begränsningar |
| B | Valda matkök, exempelvis italienskt och indiskt, med UI:ts faktiska filtersemantik |
| C | Ändrat proteinmål, exempelvis minst 40 g per portion, via samma fält som UI använder; inte 40 procent |
| D | Endast kyckling/vegetariskt: tre kycklingmiddagar och två vegetariska, inga fisk-/köttmiddagar |
| E | Kombinationen B + C + D; det viktigaste användarfallet |

Avsaknad av godkänd meny får inte döljas genom att lätta krav. Registrera
`SEARCH_BLOCKED`, saknade fakta eller timeout med rätt innebörd; det bevisar
inte att en meny är matematiskt omöjlig. Om ett annat kombinationsprov behövs
för att mäta lyckad leverans ska det vara separat och uttryckligt redovisat.

Kör samma sekvens före och efter ändringen: varm gemensam server med A
förberett, därefter första B, C, D och E utan förhandsberäknade resultat för
dessa personliga kontexter. Upprepa E och återgå till A. Logga vilka lager
som var varma; föregående steg och sparad historik ska vara likvärdiga i båda
armarna. Förbered inte exakt E i bakgrunden och kalla sedan dess träff för
ett första anrop med nya val. En separat ny testägare ska också visa att
opersonligt arbete kan delas utan privata resultat från föregående ägare.

Prioritera sedan ett prisversionsbyte: mät första A och E före respektive
efter gemensam förberedelse av den nya versionen. Använd två behöriga,
validerade frysta prisunderlag om sådana finns. Om de saknas: redovisa luckan,
prova invalidation/kampanjgräns med tydligt syntetiska små regressionstester
och gör inget påstående om verklig veckouppdateringslatens. Starta inte
insamling eller en ny stor datainsamling för att fylla denna lucka.

Jämför nya koden både med oförändrad v1-bas och legacy där pris-/utfallsgrinden
kräver det. Tidigare oförändrade mätningar får återanvändas bara när kod,
indata, normaliserad begäran och mätgräns verkligen matchar.

## 5. Mätgränser, tidsbudget och stopp

**Högst två timmars sammanlagd väggtid för denna etapps prestandakörningar**,
inklusive profilering, förberedelser, omkörningar och uppstart. Budgeten
gäller hela etappen, inte per version/stad eller per återstart av agenten.
Journalför förbrukad tid. Vanlig kodläsning, implementation och korta
regressionstester/ordinarie CI räknas separat; använd dem inte som etikett
för att kringgå benchmarkbudgeten.

- Första profil-/baslinjeomgången får högst 30 minuter. Gör därefter den
  avgränsade förbättringen; starta inte en större matris automatiskt.
- Ett plananrop får högst fem minuter. Vid första timeout eller oväntad
  kraftig kostnadsökning: stoppa utvidgningen, bevara spår och diagnostisera.
  Tidsgränsen gäller testet, inte en ny produktregel eller ett godkänt resultat.
- Budgetera varje batch innan start. Kör en observation per nytt fall först.
  Upprepa viktigaste före/efter-fallen A/E tre gånger om budgeten räcker;
  återställ då likvärdiga startlägen för varje första-anropsprov. Tre
  efterföljande träffar är inte tre prov av nya krav. Ange annars antal
  observationer och osäkerhet. Ange aldrig p95 från tre prov.
- Vid budgettaket avslutas benchmarkarbetet med rapport. Ingen automatisk
  fortsättning över natten, nya 1 000/2 000/5 000-grupper eller fullmatris.
  Ytterligare lång verifiering blir ett separat, kostnadsbedömt uppdrag.

Kör seriellt på samma två CPU/3 GiB som tidigare, eller redovisa uttryckligen
annan maskin utan att blanda dess tider. Behåll högst 2,5 GiB som minnesmål,
3 GiB som hårt tak, och inga extra workers. Redovisa peak även vid
versionsbyte/serialisering. Använd isolerade data; rensa inte delad OS-cache.

Separera kö, inläsning, gemensam förberedelse, personlig kvalificering,
sökning, aktuell checkout/audit, save och klientens observerade sluttid.
Mät både utan profilerare och, där det behövs, separat med instrumentering.
In-process ASGI är serverflöde, inte verklig webbläsarlatens. Gör minst ett
begränsat browserprov av kombinationsfallet i isolerad miljö om underlaget
tillåter; annars ange det som omätt. POST/202 är aldrig sluttiden.

## 6. Korrekthet och leverans

Behåll befintliga regressioner och lägg riktade tester kring ändrade gränser:

- Ändrade matkök, proteinmål och kyckling/vegetariskt, separat och tillsammans;
  ingen otillåten middag eller näringsmiss får återanvändas som giltig.
- Samma profil hos olika ägare; relevanta ändringar i skafferi, lås, historik,
  medlemskap, portioner och butiker ger rätt omprövning.
- Ny pris-/faktaversion, återkallelse och kampanjgräns; även negativa cacheposter.
- Processomstart/eviction och sen förberedelse från gammal version; korrekt
  fallback, ingen stale publicering eller förlust av verifierad historik.
- Pris/utfall mot samma bas och legacy på de faktiskt provade kontexterna,
  med befintliga deterministiska skiljeregler och aktuell audit.

De flesta av dessa gränser ska provas med små riktade regressioner, inte
var sin dyr helkatalogskörning. Kör relevanta offlineprov, Ruff och compileall,
samt ordinarie CI inklusive befintliga browserprov på den slutliga koden.
En ändrad runtime är inte automatiskt kvalificerad av äldre mätningar.

Leverera små granskade commits på main, uppdatera `HANDOFF.md` och skriv
`docs/reviews/personal-choice-latency-20261025.md` med kompakt maskinunderlag:
kod-/indata-/metodhashar, begäranden utan privata uppgifter, cachelägen,
resurser, observationer, audit, pris, stopporsaker och återstående budget.
Redovisa per fall före/efter, första nya kombination respektive återanrop,
bakgrundskostnad och faktisk användarväntan. Svara uttryckligen på om
30-sekundersmålet nåddes för E utan förberedelse av exakt E, och vad som
visats efter nya kampanjpriser. Snabbare beräkning med sämre pris/giltighet
godkänns inte. Om målet missas: ange största återstående fas och en avgränsad
rekommendation, utan att fortsätta tills all historisk verifiering är klar.

Behåll `library_search_policy=legacy` och `library_merge_generations=False`
som standard. Ingen produktionsaktivering, schedulerändring, ökad samtidighet
eller aktiv pris-/faktarelease ingår. Axfood-berikningens tidigare godkännande
gäller fortsatt; det behövs inget nytt principgodkännande. Den här etappen
ändrar användarens väntan i utvecklingskoden och dess bevisläge, inte driftbeslutet.
