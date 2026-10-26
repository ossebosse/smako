# Sol: rätta receptinnehåll, förbättra köpbarhet och mät personlig planering

**Efter PR #15 och granskning 2026-10-26:** nästa uppdrag finns i
[kvarstående receptfel, veckosökning och cache](CODEX-SOL-NEXT-20261026-WEEK-SEARCH.md).
Det ersätter detta dokuments etappordning. Använd aktuellt saldo i samma
journal, inte det historiska startsaldot nedan. Befintliga resultat behålls.

Ägarens nästa uppdrag efter granskningen av PR #14, main `ed36c0f`,
2026-10-26. Arbeta i `D:\Projects\Smako`, hämta aktuell main utan att
skriva över annat arbete och följ AGENTS, DEVELOPMENT och senaste HANDOFF.
Läs [produktmålet](PRODUCT-GOAL.md) och
[planeringsarkitekturen](PLANNING-ARCHITECTURE.md).

Detta dokument bestämmer nästa etapps ordning och omfattning. Massimporten
är genomförd; återgå inte till 45 varianter per leverans. Det äldre
[receptuppdraget](CODEX-SOL-NEXT-20261025-RECIPE-INTAKE.md) är bakgrund.
[V2-uppdraget](CODEX-SOL-NEXT-20261025-PREPARED-PLANNING.md) och arkitekturen
gäller fortsatt som riktning, men full V2-implementation och separata
1 000-/5 000-prov är inte leveranskrav i denna avgränsade etapp.

Leverera tre saker i ordning: korrigerade receptändringar, verifierade
förbättringar av produktkopplingarna och ett litet ärligt prov av personlig
planering med det verkliga biblioteket. Ingen ny stor testmatris.

## 1. Utgångspunkt och granskningens fynd

Läs [importens slutrapport](reviews/recipe-integration-all-20261026.md),
dess `all-recipes.json`, `structural-summary.json`, `purchase-blockers.json`
och [hinderlista](reviews/recipe-integration-all-20261026/HINDER.md).

- Alla 800 källkandidater/2 200 varianter är representerade. Totalt finns
  2 462 aktiva varianter/934 registrerade grundrätter. Det är inte bevis
  för 800 kulinariskt unika nya grundrätter eller 2 462 köpbara recept.
- De 166 originalfilerna och det ursprungliga biblioteket är bevarade.
  Behåll dem och publiceringshistoriken; börja inte importera om från noll.
- På behörigt fryst Malmöunderlag från 23 oktober har 704/2 200 varianter
  alla ingrediensinköp lösta i exakt läge; 1 496 är blockerade. Vid separat
  uttryckligt `estimated`-val är det 888 lösta/1 312 blockerade. Det är
  individuell insatstäckning, inte giltiga veckomenyer med alla personliga krav.
- Den oberoende granskningen körde `test_all_intake_links.py`,
  `test_recipe_intake_review.py`, `test_recipe_budget_check.py` och
  `test_recipe_preparation_cache.py` genom `scripts/verify_offline.py`:
  **472 PASS**. Dessa prov upptäckte inte innehållsfelen nedan.
- Importens åtta huvudfall var låsta receptval med `NOT_REQUESTED` för
  näring. Ett nionde prov använde estimated. Förberedelsens cirka 132 s
  är inte användarlatens, och 30–60-sekundersmålet är fortfarande omätt
  för fria personliga veckoval med det nya biblioteket.

Följande är reproducerade fel i importen, inte bara hypotetiska risker:

1. `smako-thai-snack-tapioca-pearl-pudding`, simple/extended, köper fryst
   mango men instruerar användaren att skala och tärna mangon. Upptining
   saknas. I authoring är mango dessutom listad i `uses` i stegen som kokar
   pärlorna, trots att texten lägger mangon på puddingen först vid servering.
2. `smako-mexican-snack-chunky-guacamole` har frysta avokadotärningar och
   upptining men behåller instruktionen att dela avokadon och väga rått
   fruktkött utan skal och kärna. Produktform, mängdbasis och beredning
   behöver beskriva samma råvara genom hela receptet.
3. `smako-mexican-tofu-pinapple-skewers:simple` blir 63 min utan upptining,
   medan `smako-thai-chicken-pineapple-skewers:simple` blir 555 min med
   åtta timmars upptining. Båda använder fryst ananas som ska skäras och
   träs på spett. Regeln känner igen ordet `rosta` men missar `Tillaga
   mitt i ugnen`; tiderna följer därmed inte en granskad beredningsmodell.

Spåra från `scripts/recipe_layer/complete_intake_delivery.py`, särskilt
`frozen_preparation` och ändringen av ingrediensetiketter. Exempel finns
i `reviewed-all-20261026/batch-05`, `batch-06`, `batch-11` och `batch-13`.
337 varianter har fått sådana ändringar till frysta ingredienser och 99
har fått åtta timmars upptining. Det betyder inte att alla 337 är fel,
men en rättning av bara de tre exemplen är otillräcklig.

## 2. Rätta den berörda receptklassen först

- Inventera samtliga berörda varianter via ändringsjournalen. Kontrollera
  faktiskt använd produktform, ätlig mängd, skärning/skalning, upptining,
  upphettning, kylning och stegens beroenden. Ta även med redan ändrad
  hallonberedning och behåll sakligt motiverade säkerhetssteg och källstöd.
- Låt verklig ingrediensanvändning styra. Ett helt stegs `uses` plus ett
  ord som `koka` bevisar inte att varje listad ingrediens upphettas. Rätta
  felaktiga `uses` och välj explicit granskade processer där automatiken
  saknar tillräckligt underlag. Lägg inte bara fler ord i samma regex.
- Skriv fullständiga användbara instruktioner för den produkt som köps.
  Frysta skalade tärningar får inte ärva instruktioner för en hel färsk
  frukt. En ändring av råvaruform ska omfatta både krav och steg.
- Bedöm tid och beroenden per faktisk beredning. Bevara nödvändig väntan;
  kapa inte tiden för att passera filtren och lägg inte schablonmässigt
  åtta timmar på varje kall användning. Oberoende moment får överlappa
  bara när receptets tillagningskedja faktiskt medger det.
- Kontrollera aktiv-, väntetid och total tid samt tidsfiltrens beteende.
  Lägg riktade regressioner som hade fångat fynden, inklusive mango som
  kall topping efter en varm beredning och ananas som skärs före ugnssteg.
  Testa det publicerade receptet och de härledda tiderna, inte bara
  importhjälparens interna etiketter.
- Publicera rättade versioner genom ordinarie author → validate → diff →
  import. Återkalla ersatta versioner enligt befintligt kontrakt och behåll
  oförändrade historiska bytes/referenser för sparade planer. Kontrollera
  att den gamla importhjälparen inte kan återinföra samma fel vid omkörning.
- Redovisa per berört ID: rättat, verifierat oförändrat eller konkret
  kvarstående hinder. Ändra inte orelaterade recept eller standardfilter.

## 3. Förbättra köpbarheten där det ger verklig effekt

Prioritera med `purchase-blockers.json` och redan behöriga produkt-/faktadata.
Limejuice blockerar 445 varianter, ingefära 402, salladslök 139, mynta 131
och majs 116 i exakt läge. Talen överlappar och får inte summeras som
frigjorda recept. Välj åtgärder efter både möjlig effekt och verkligt
tillgängligt källstöd; rapportera vad som kan rättas i kod respektive data.

1. Sök först efter befintliga tillåtna deklarationer, korrekta produktnamn,
   råvaruformer och mängduppgifter. En vara kan finnas i butiken även när
   matchningen eller dess bevis saknas. Rätta konkreta kopplingsfel.
2. Skilj inköpt bruttomängd, ätlig receptmängd och tillagningsform. Återanvänd
   befintliga källbelagda omvandlingar där kontraktet medger det. Anta inte
   att hela roten/frukten har samma vikt som dess ätliga del. Ett saknat
   generellt stöd för ansning ska beskrivas som ett modellbehov, inte
   döljas genom att alla recept görs om till frysta ingredienser.
3. `estimated` förblir ett uttryckligt separat val. Flytta inte användare
   dit för att förbättra täckningssiffran. Okända ingredienser, allergener,
   ekologiska egenskaper och sammansättning får inte bli positiva intyg.
4. Bevara exakt produkt-/butiks-/snapshotbindning. Testa berörda kopplingar
   vid ändrad produkt/fakta/packning/version och avvisa inaktuella bevis.
   Ingen fri namnmatchning får tilldela auktoritativa priser.
5. Kör en gemensam inventering efter den sammanhängande rättningen och
   redovisa verkligt nytillkomna köpbara varianter i båda lägena samt vad
   som återstår. Enbart fler ingrediensdefinitioner räknas inte som ökad
   köpbarhet. Behåll exakta avslag och nästa saknade källa i hinderlistan.

Alla 104 ingrediens-/formluckor behöver inte lösas före nästa planeringsprov.
Källdata som saknas ska få en avgränsad kompletteringslista; använd inte
tiden till upprepade identiska misslyckade sökningar. Bred ny insamling
ingår inte. Axfoods tidigare principgodkännande ändrar inte källscope.

## 4. Få verkliga användarprov och en avgränsad prestandaförbättring

Använd det korrigerade aktuella biblioteket och befintliga riktiga
UI/API-begäranden. Behåll samma underlag, testklocka, resurser och krav vid
jämförelser. Ta först ett standardfall och ett nytt kombinationsfall.
Om de fastnar: profilera den konkreta flaskhalsen inom budgeten och gör
högst en sammanhängande avgränsad förbättring före nytt prov. Återstarta
inte alla fall efter varje liten ändring eller en större omskrivning.

Sikta på följande sex representativa fall; börja inte med en kartesisk matris:

| Fall | Vad som ska prövas |
| --- | --- |
| A | Standardvecka med fri receptsökning och de faktiska standardkraven |
| B | Ny kombination: valda matkök, ändrat proteinmål och bara kyckling/vegetariskt |
| C | Ändrat antal måltider/portioner och ingrediens-/tidsgränser |
| D | Ett uttryckligt allergi-/uteslutningskrav kombinerat med ekologiskt krav |
| E | Ett annat butikstak inom samma urval; 1..N provas om komplett stöd finns |
| F | Ny testägare eller nya val efter versionsbyte av pris-/faktaunderlaget |

Spara de exakta begärandena innan provet. Ändra inte ett blockerat falls
krav för att göra det grönt; lägg vid behov till ett separat genomförbart
fall. Ett ännu ej implementerat val redovisas som sådant. Exponera inte
större butikstak genom enbart höjda UI/API-gränser.

- Varmt gemensamt underlag får användas, men inte enbart identiska
  menycacheträffar. Nya preferenser och ägare ska faktiskt prövas.
- Redovisa totalt inlästa recept och hur många som återstår efter varje
  krav-/produkt-/faktasteg samt faktiskt sökta kandidater. Tusentals
  inlästa med nästan alla blockerade bevisar inte tusentals sökbara recept.
- Mät till färdiga recept, aktuell gemensam checkout/audit, save och GET.
  Ta minst ett verkligt browserprov av ett lyckat nytt val, om något
  sådant fall lyckas. Skilj browserns knapptryck-till-synlig-lista från
  API-/motortid, kö och bakgrundsförberedelse. Fejkade pris-/plan-API:n
  kvalificerar inte användarlatens.
- Näringsfall ska faktiskt tillämpa valda näringskrav. `NOT_REQUESTED`
  får inte vara intyg för protein-, fett-, kolhydrat- eller kalorival.
- Kontrollera pris och giltighet mot matchande bevarad referens eller
  verifierad tidigare giltig vinnare efter aktuell checkout. Olika
  bibliotek/krav/priser är inte en direkt regressionsjämförelse. Saknas
  jämförbart bevis: redovisa det. Bevara prisgränsen och användarens krav.
- Saknas två behöriga matchbara prisversioner: redovisa verklig
  veckouppdateringslatens som omätt. Små syntetiska versions-/kampanjprov
  får kontrollera korrekthet, men ersätter inte verklig latensmätning.
- Kontrollera cachelivscykeln vid versionsbyte/full cache i ett litet
  riktat prov. Den tidigare färska cachekatalogen visade förberedelsekostnad,
  inte att återkommande uppdateringar undviker kapacitetsgränsen 4 096.

Arkitekturen är fortsatt gemensamt versionsbundet underlag, personlig
sökning och exakt gemensam checkout. Förbered inte varje profil eller
butikskombination. Om en ny V2-del behövs: håll den opt-in, följ befintliga
kontrakt och rapportera återstående funktioner. Full V2 behöver inte byggas
för att denna etapp ska kunna avslutas med verifierade användbara resultat.

## 5. Samma budget och tydliga stoppregler

Fortsätt **samma** journal:
`docs/reviews/recipe-integration-800-20261025/budget.json`.
Vid uppdragets skrivning: **2 125,9999 s förbrukade, 5 074,0001 s kvar**
(35,43 respektive 84,57 minuter av totalt 120). Läs aktuellt saldo vid
start; detta dokument beviljar ingen ny budget och nollställer inget.

- Använd `scripts/recipe_layer/budgeted_check.py` och dess gemensamma
  OS-låsning. En dyr arbetare åt gången. Räkna uppstart, förberedelse,
  produktinventering, profilering, misslyckanden och omtag i samma journal.
- Behåll två CPU och hårt 3 GiB; minnesmål högst 2,5 GiB inklusive
  versionsöverlappning. Mät den verkliga arbetaren och ange mätmetoden.
- Personliga prov över 60 s missar produktmålet. Testövervakaren avbryter
  senast vid 75 s och städar egna arbetare. Detta gör inte en avbruten
  sökning till en giltig meny eller ett bevis om omöjlighet.
- Deklarera även förberedelsens stoppgräns före start. Gör ingen ny dyr
  baslinjekörning när identisk användbar evidens redan finns. Starta inte
  samma tidsöverskridande strategi igen utan en konkret ändring eller fråga.
- Små meningsfulla regressioner, Ruff, compileall och ordinarie CI ligger
  utanför benchmarkbudgeten. Döp inte om en lång mätning till regression
  för att kringgå gränsen. Ingen återstart av 252 celler, inga duplicerade
  5 000-recept och ingen automatisk fortsättning över natten.
- Avsluta vid budgetgränsen med mätresultat och nästa tydliga hinder.
  Alla 1 496 blockerade varianter och hela V2 är inte villkor för att få
  lämna en ärlig, avgränsad leverans. Ingen mätarbetare lämnas igång.

## 6. Leverans och slutrapport

Gör små granskade commits och integrera på main enligt DEVELOPMENT.
Kör riktade semantiska regressioner och relevanta befintliga tester,
Ruff/compileall samt ordinarie CI inklusive tillämpliga browserprov före
integration. Bevara bytebundna original och historisk evidens.

Skriv `docs/reviews/recipe-quality-and-planning-20261026.md` med kompakt
maskinunderlag och uppdatera HANDOFF. Rapporten ska ange:

1. Exakta receptfel, granskningens omfattning, rättade nya versioner och
   kvarstående hinder; tillagnings-/tidskontrakt före och efter.
2. Produktkopplingar som faktiskt förbättrats, nytillkomna köpbara varianter
   och återstående dataluckor, separat för exakt och estimated.
3. Varje personligt provs krav, verkliga kandidatantal, utfall, pris,
   audit/näringsstatus, total tid och eventuell timeout. Redovisa få
   observationer som få observationer; påstå inte verifierad p95.
4. Förberedelsekostnad, cache-/versionsbeteende och minne separat från
   användarlatens. Ange om 30–60 s uppnåddes i just de mätta fallen.
5. Faktiskt budgetsaldo och ett avgränsat förslag på nästa största förbättring.

Lämna legacy som standard och `library_merge_generations=False`.
Integration på main är inte beta-/produktionsaktivering. Ingen driftuppgift,
produktionens användarprofil eller bred insamling ändras av detta uppdrag.
