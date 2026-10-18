# Uppgift till Claude: skala Smako till tusentals recept och variationer

Beställd 2026-10-18. Utgå från aktuell `main`, läs `AGENTS.md`,
`docs/HANDOFF.md` och `docs/DEVELOPMENT.md`. Arbeta i en avgränsad gren.
Leverera implementation, mätunderlag och en granskning som Codex kan verifiera.
Denna uppgift beställer inte produktionsaktivering eller nya prisinsamlingar.

## Mål och första milstolpe

Gör det praktiskt möjligt att använda tusentals kvalificerade recept inklusive
variationer utan att sänka kvalitetskraven eller välja dyrare menyer för att
spara beräkningstid. Första beslutspunkten är **1 000 recept inklusive
variationer**. Redovisa alltid antal grundrecept, variationer och faktiskt
kvalificerade alternativ separat.

Första prestandamål: varm standardplanering under 30 sekunder på samma
serverresurser som referensen. Detta är ett acceptansmål som ska mätas, inte
ett redan styrkt löfte. Redovisa även kall tid, långsamma närings-/ekoprofiler,
HTTP-kö och samtidighet; göm inte kostnaden i förberedelser utanför mätningen.

## Utgångsläge och evidens

- [Recepttillväxt 222 → 242](reviews/recipe-growth-20261018.md): 20 nya
  author-recept sänkte menypriserna men ökade varm tid i Malmö med 16–23 %.
  Effekten var profilberoende och får inte extrapoleras linjärt.
- [Exakt återanvändning av butiksjämförelser](reviews/planner-exact-speed-20261018.md):
  kod `90ddeeb`, integrerad via `a70f3af`. Vid samma 242 recept blev Malmös
  varma standardtid 55,88 → 52,21 s och kalla ekotid 219,45 → 196,26 s.
  Identiska resultathashar och priser. Lund har ingen säkerställd tidsvinst.
- Malmöproven använder cirka 2,5 GB RSS. Samtidighet är därför också en
  kapacitetsfråga. Tidigare isolerade prov hade 2 CPU och 3 GiB minnesgräns.
- Dagens sökning har seedtak 40, förfiningstak 90 och varianturval.
  Befintlig vinnare är inte ett bevis för globalt billigaste möjliga meny.
- De 20 tillväxtrecepten är prototyper i testunderlaget, inte godkända
  produktionsrecept. Importera inte dem eller syntetiska skalningsrecept i
  produktionsbiblioteket som del av uppgiften.

## Arbetet

1. Profilera kandidatkontroll, receptförberedelser, närings-/ekokontroll,
   veckosökning och kassaberäkning separat. Beskriv vad som redan återanvänds
   och var kostnaden ökar med bibliotekets storlek. Börja med en reproducerbar
   referens innan kod ändras.
2. Utveckla befintlig förberedelse och cache så att oförändrat arbete kan
   återanvändas mellan anrop. Ändra endast berörda beräkningar när underlag
   ändras. Identiteten måste täcka relevanta receptversioner, mängder,
   produktfakta, prismanifest, butiksscope, inköpsvillkor, kampanjdatum och
   profilkrav. Följ befintliga artefakter och integritetskontroller; skapa inte
   ett parallellt pris- eller faktasystem. Mät byggtid, lagring och invalidation.
3. Dela gemensamt arbete mellan receptvariationer. Bevara varje variants
   exakta mängder, näringsvärden, ingrediensidentitet och inköpsvillkor.
   Att två variationer liknar varandra är inte tillräckligt för att slå ihop
   deras priser eller ta bort ett sökalternativ.
4. Undersök säker beskärning av sökningen med bevisade undre kostnadsgränser.
   Ta hänsyn till gemensamma förpackningar, kampanjer, butikstak och befintliga
   regler vid lika priser. Ett billigt separat recept är inte alltid bäst i
   en veckokorg. Befintlig vinnare och relevanta alternativ ska bevaras.
5. Mät skalning vid nuvarande storlek, 500, 1 000, 2 000 och 5 000 recept.
   Börja med 500/1 000 och använd resultatet för nästa steg. Större prov får
   avbrytas vid dokumenterad tids-/minnesgräns; redovisa utfallet öppet.
   Använd varierade receptfamiljer och kombinationer, inte bara kopior med
   nya namn. Skapa och validera testbibliotek genom ordinarie author/import.

## Pris- och korrekthetskrav

- På samma bibliotek och frysta indata ska rent beräkningsmässiga
  optimeringar behålla fullständig resultathash, pris och deterministisk
  tie-break. Hashen ska omfatta recept, korg, källbevis, näring och audit.
- Om själva sökningen förbättras får resultatet ändras, men får inte bli
  dyrare eller bryta något krav. Redovisa sådana ändringar separat från
  exakt återanvändning, inklusive lika-pris-regler och sekundära mål.
- Vid bibliotekstillväxt får nya recept ge en annan och billigare meny.
  Behåll en tidigare giltig kandidat som jämförelse under samma aktuella
  priser, profil och regler. En gammal meny får inte återanvändas utan ny
  kvalificering när underlaget har ändrats.
- Kör kontrollerade referenser utan tak/varianturval där det är praktiskt
  möjligt och små uttömmande fall för gränsernas korrekthet. Att matcha en
  `--uncapped`-referens bevisar inte automatiskt global optimalitet. Kontrollera
  uttryckliga metodflaggor; den tidigare kända referensvalideringsbristen får
  inte ge ett falskt godkännande.
- Om en profil blir dyrare ska orsaken rättas och ett otillräckligt tak vid
  behov höjas. Ta inte bort testet eller sänk kvalitetskraven.
- Bevara fakta-/integritetslås, prisursprung, exakta produktidentiteter,
  allergikrav, näringskrav, verifieringsnivåer och slutlig checkout-audit.

## Acceptans och verifiering

- Lund och Malmö, samma sju profiler som rättelsegranskningen samt relevanta
  negativa fall. Se [tidigare matris](reviews/review-fixes-verification-20261018.md).
- Samma pinnade kod, indata, klocka och resurser i jämförda armar. Skilj
  versionsbyte av bibliotek från algoritmändring. Kör upprepningar i båda
  ordningarna; redovisa råvärden och spridning, inte bara bästa tid.
- Separera ny process/tom cache, varm full planering och eventuell återläsning
  av färdig meny. Mät även förberedelse efter pris-, fakta- och receptändring.
- Redovisa CPU, RSS/peak, cachevolym/träffar, korgberäkningar och kvalificerade
  kandidater. Prova kontrollerad samtidighet i isolerad miljö; kalla inte
  medianen av ett fåtal prov för p95. Dokumentera tillräckligt stickprov om
  percentiler används.
- Full regression med återställt lokalt underlag, kända fel oförändrade,
  relevanta nya regressioner, Ruff, compileall och GitHub-CI inklusive
  webbläsartester. Återanvänd oförändrad, hashbunden evidens där det är giltigt.
- Inga prov får skriva i produktionsdatabaser, kringgå driftlåset, stoppa
  ordinarie uppdateringar eller fylla serverns lagring. Arkivera/verifiera
  underlaget före rensning av exakt identifierade egna temporära filer.

## Leverans och rapportmall

Leverera små granskbara commits/patchar, körkommandon, bibliotekens manifest,
indatahashar och maskinläsbara mätningar. Förklara hur nödvändigt större eller
privat underlag återfås utan att checka in det eller några hemligheter.

Rapporten ska innehålla:

1. Beslut: vad klarar 1 000 recept nu, och vad hindrar nästa nivå?
2. Ändringar och varför pris-/korrekthetskraven bevaras, inklusive lås och
   cacheinvalidation samt kvarstående begränsningar.
3. Tabell per storlek/stad/profil: grundrecept, variationer, kvalificerade
   kandidater, kall/varm tid, pris före/efter, hash och peak-minne.
4. Förberedelsekostnad, samtidighetsresultat och realistisk serverkapacitet.
5. Regression/CI med exakta PASS/XFAIL/SKIP och förklaringar.
6. Uppnådda och missade acceptansmål, avbrutna prov och rekommenderat nästa
   steg. Redovisa mätosäkerhet och skilj uppmätt beteende från prognos.

Skärp inte beskärning eller söktak enbart för att nå tidsmålet. Om 30 sekunder
inte nås med bevarad kvalitet ska leveransen visa det och förklara nästa åtgärd.
