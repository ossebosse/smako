# Sol: rätta kvarstående receptfel och angrip veckosökningens flaskhals

**Uppföljning efter PR #16:** fortsätt med
[giltig vecka, tidsgräns vid omräkning och köpbarhet](CODEX-SOL-NEXT-20261026-VALID-WEEK-AND-COVERAGE.md).
Nedanstående uppdrag och dess dåvarande budget är historik. Rapportens
rättelse gäller: original-B innehåller 52 tillåtna butikskontexter, inte 55.

Ägarens uppdrag efter granskningen av PR #15, main `6b2e946`, 2026-10-26.
Arbeta i `D:\Projects\Smako`. Hämta aktuell main och följ AGENTS,
DEVELOPMENT, [produktmålet](PRODUCT-GOAL.md),
[planeringsarkitekturen](PLANNING-ARCHITECTURE.md) och HANDOFF.
Detta är nästa uppdrag efter
[receptkvalitet och personlig mätning](CODEX-SOL-NEXT-20261026-RECIPE-QUALITY-AND-PLANNING.md).

Genomför en avgränsad leverans: rätta de identifierade innehållsfelen,
förbättra gemensam korg-/butikssökning och gör förberedelsecachens
versionslivscykel hållbar. Visa effekten på det redan definierade B-fallet.
Full produktkvalificering, alla produktluckor och den gamla stora matrisen
är inte krav för denna etapp. Målet om giltig billigast möjlig veckoplan
inom 30–60 sekunder med tusentals recept kvarstår.

## 1. Utgångspunkt och nya granskningsfynd

Läs [PR #15:s rapport](reviews/recipe-quality-and-planning-20261026.md)
och maskinunderlagen i samma namngivna katalog. Läget är:

- 2 462 aktiva varianter/934 registrerade grundrätter. Alla 2 200
  levererade varianter är representerade; original och historik bevaras.
- Individuellt lösta ingrediensinköp: exakt 733/2 200, uttryckligt
  estimated 920/2 200. Netto +29/+32 mot PR #14. Inga generella
  personliga närings-/allergen-/ekointyg följer av dessa tal.
- F är en middag för två: browser 28,10 s, senaste API/GET 31,96 s,
  104,30 kr och uppskattat protein 20,7625 g mot kravet 20 g. Bara fyra
  kandidater kvalificerades. Det är ingen verifierad veckolatens.
- A/B/E blev inte klara vid 75 s. D gav DATA_BLOCKED. B räknade över
  1,5 miljoner butikskombinationer. Den begärandeägda identitetscachen
  har ingen verifierad förbättring av veckans slutlatens.
- Förberedelse med full cache: 4 096 poster, 8 796 missar, noll träffar
  och noll nya skrivningar. Säker fallback är testad, hållbar återanvändning
  över versionsbyten återstår. Verklig veckouppdateringslatens är omätt.
- Oberoende omkörning efter PR #15: 457 riktade tester passerar. Ändå
  finns nedanstående motsägelse i sex aktuella recept. Grön struktur-/
  regressionstestning är inte ett bevis för korrekt tillagningsbeskrivning.

### A. Sex spettvarianter har motsägande beredning

Berörda aktuella ID:n är version `1.0.2`, varianterna `simple`, `standard`
och `extended`, för båda dessa baser:

- `smako-thai-chicken-pineapple-skewers`
- `smako-thai-paneer-mango-skewers`

De instruerar först att tina frukten helt före trädning på spett, därefter
att väga upp **frysta** bitar och lägga dem direkt i en **varm panna**.
Den fortsatta verkliga tillagningen sker på spett i ugnen. Detta är
verifierat i aktiva `current_recipes()`, inte bara i gammalt författarunderlag.

Orsaken finns i `scripts/recipe_layer/amend_frozen_recipes.py`:
ersättningarna för `skölj eller ansa och skär mango/ananas i små bitar`
används utan hänsyn till det redan valda beredningssättet. Ett korrekt
inledande upptiningssteg neutraliserar inte den senare motsägelsen.

Rätta detta så att hela receptet följer samma granskade process:

1. Villkora eller ersätt textomvandlingen utifrån faktisk process. Behåll
   direkt upphettning där den hör hemma; använd tinade bitar som ska skäras
   och träs när processen är spett. Byt inte bara ett ord i slutrapporten.
2. Granska övriga recept som samma textersättningar ändrat. Redovisa
   omfattning och eventuella ytterligare rättningar utan att återställa
   korrekta mango-, guacamole-, hallon- eller färskformskrav.
3. Lägg regressioner för hela den publicerade kedjan och alla sex
   varianterna. Proven ska fånga direkt-fryst/panna efter upptining inför
   ugnsspett, samtidigt som verkliga direkt-fryst-i-panna-fall fungerar.
   Att bara kontrollera att ordet upptining finns tidigt är otillräckligt.
4. Ge rättade recept nya versioner genom author → validate → diff → import
   och återkalla ersatta versioner enligt befintligt kontrakt. Ändra inte
   historiska bytes eller sparade planreferenser. Omkörning ska vara säker.

### B. Rågbrödsrätten får inte köpa generiskt pitabröd

Utred och rätta
`smako-swedish-creamed-cabbage-chickpeas:1.0.0:simple` och eventuella
syskon med samma specifikationsfel. C:s titel lovar rågbröd, men insatsen
är generiskt `bröd|as_sold` utan rågkrav och vald produkt är pitabröd.
Se `remaining-content-issues.json` i föregående rapportkatalog.

Gör rågbrödskrav och verifierad produktkoppling konsekventa med receptet.
Om en innehållsgranskning i stället visar att generiskt bröd var avsikten,
motivera en uttrycklig rättning av namn, instruktion och krav tillsammans.
Välj inte omtolkning enbart för att få ett billigare eller grönt prov.
Publicera vanlig ny version och testa faktiskt tillåtet/avvisat brödval.
C:s gamla 108,45 kr är inte en giltig rågbrödsreferens att kräva oförändrad.

## 2. Prioritera det dyra arbetet i veckosökningen

Återanvänd B:s redan sparade profil och diagnos före ny dyr körning.
Enbart ytterligare memoisation av receptnamn/hashar är inte nästa huvudspår.
Utgå från den beslutade V2-riktningen i befintliga planerings-/prisvägar:

- Förbered versionsbundna, profileroberoende ingrediens-/produkt-/butiksdata
  för det aktuella biblioteket och återanvänd relevanta rena kostnadsdelar.
  Använd befintlig pris-/kampanjberäkning och exakt gemensam checkout.
- Minska upprepade helkorgsutvärderingar och full materialisering av samma
  butikskombinationer. Visa med räknare vilket arbete som faktiskt försvinner.
  Återanvänd oförändrade delar mellan kandidater där deras läsberoenden medger det.
- En ny V2-väg ska söka aktuellt manifest utan att historiska publiceringar
  multiplicerar varje personligt anrop. Bevara proveniens och historisk
  återläsning. Ändra inte legacy/V1:s kontrakt för att få jämförelsen grön.
- Håll ny sökpolicy opt-in, genom befintligt API till checkout, save och GET.
  Ingen ny parallell prismotor, driftkö eller scheduler. En avgränsad
  sammanhängande förbättring är viktigare än att skriva om hela systemet.
- Behåll gemensamma kampanjer, förpackningar, butikstak, näringskrav, eko,
  allergier, skafferi och ägarscope. En cache av gemensamt underlag får inte
  bli ett återanvänt personligt godkännande.
- Gallring som påstås vara säker behöver giltiga gränser. En heuristisk
  shortlist är inte hela bibliotekets bevisade optimum. Acceptera ingen
  oförklarad prisregression, högre prisgräns eller automatisk kravlättnad.
- Deadline ska omfatta inre dyra loopar och obligatorisk checkout/save,
  inte bara tiden mellan två kompletta plananrop.

Använd små uttömmande orakel med känd bästa korg för de ändrade delarna:
gemensamma ingredienser, flera paketstorlekar, kopplade kampanjer,
butikstak och produktval som påverkar näring/eko. Ett tidsbegränsat B utan
äldre giltig vinnare kan inte ensamt styrka oförändrad prisoptimalitet.
Redovisa kvarstående stödgränser; full V2 och utökat UI-tak 1..N är inte
automatiskt färdiga genom denna etapp.

## 3. Gör beräkningscachen användbar efter versionsbyte

Utgå från befintlig cache och dess byte-/postbudget. Inför en verifierad
livscykel för utbytbara beräkningsartefakter så att en fylld katalog inte
permanent hindrar nytt aktuellt underlag från att sparas och återanvändas.
Motivera eventuella kapacitetsändringar med faktisk total lagring och minne,
inte bara ett större gränstal eller en tom katalog inför varje mätning.

- Skilj återbyggbara cacheposter från källunderlag, publicerade recept och
  sparade planer. Retention får inte skriva om eller radera historiska bevis.
- Behåll exakt beroendebindning för recept, fakta, produkt, butik, pris,
  beräkningsmetod och kampanjgiltighet. Använd endast giltiga äldre delar.
- Samordna skrivning/aktivering enligt befintliga lås och versionsregler.
  En sen äldre beräkning får inte ersätta den nyare versionens beredskap.
- Testa full cache → ny version → faktisk lagring → träff vid återläsning,
  med oförändrat resultat mot korrekt omberäkning. Testa även avbrott och
  omstart samt säker fallback. Ett litet syntetiskt prov räcker för
  korrekthet; det ska inte presenteras som verklig veckouppdateringslatens.
- Håll aktuell och överlappande versions totalförbrukning inom budgeten.
  Mät första laddning/förberedelse separat från personlig klicklatens.

## 4. Mät B oförändrat och avbryt meningslösa omtag

Använd `docs/reviews/recipe-quality-and-planning-20261026/requests.json`,
nyckeln **B**, med samma bevarade Malmöunderlag, testklocka och resurser:
fem middagar/fyra portioner, grekiskt/italienskt, protein minst 35 g,
tre kyckling och två vegetariska, högst tre samma huvudprotein,
55 valda butikskontexter och inköpstak två. Behåll övriga normaliserade
standarder och det uttryckliga estimated-valet; ändra inte begäran för
att få ett endagsfall, lägre proteinmål eller färre butiker att passera.

1. Gör först små korrekthetsprov, sedan ett B efter en konkret ändring.
   Återanvänd tidigare B-kvitton för flaskhalsdiagnos. Om bibliotek eller
   metod skiljer sig ska skillnaden anges; pris-/latensjämförelser ska
   vara matchade. En ny dyr baslinje kräver en fråga som gamla data inte besvarar.
2. Registrera kandidatantal efter varje filter, faktiskt sökta menyer,
   korg-/butiksutvärderingar, cacheträffar, fas-/totaltid, minne, pris och
   audit/näringsstatus. Skilj minskat arbete från bara andra kandidater.
3. Räkna framgång först när full lista är kontrollerad, sparad och
   återläst. Ett snabbt avslag eller avbrott är inte en levererad meny.
4. Om B klarar 60 s utan påvisad giltighets-/prisregression: ta ett A och
   ett verkligt browserprov av det lyckade veckofallet inom kvarvarande
   budget. Ett lyckat endags-F får inte ersätta detta veckofall.
5. Om B fortfarande överskrider gränsen: använd spåret till en konkret
   rättning eller avsluta med avgränsat kvarstående hinder. Gör inte fler
   identiska timeoutkörningar, fler profiler eller större matris för sin egen skull.

Bara en behörig verklig pris-/faktaversion finns dokumenterad. Behåll
verklig veckouppdateringslatens som omätt om det fortfarande saknas en
andra matchbar version. Ingen bred pris-/faktainsamling krävs i denna etapp.
Limejuice och ätlig mängdbasis för ingefära/ansad grönsak kvarstår som
prioriterade käll-/modellbehov, men alla 105 luckor ska inte lösas här.

## 5. Budget, verifiering och överlämning

Samma journal gäller:
`docs/reviews/recipe-integration-800-20261025/budget.json`.
Senast verifierat **3 855,4145 s använda och 3 344,5855 s kvar**, alltså
**55,74 minuter kvar av totalt 120**. Läs aktuellt saldo; inget nollställs.

Använd `scripts/recipe_layer/budgeted_check.py` med gemensamt OS-lås,
en dyr arbetare åt gången, två CPU och hårt 3 GiB commit. Minnesmålet är
högst 2,5 GiB inklusive versionsöverlapp. Debitering omfattar laddning,
förberedelse, inventering, profilering, misslyckanden och omtag.
Användaranrop över 60 s missar målet; testövervakaren stoppar senast vid
75 s. Ange också förberedelsens stoppgräns före start och lämna inga arbetare.

Små riktade regressioner, Ruff, compileall och ordinarie CI är separata
från mätbudgeten. En lång mätning får inte döpas om till enhetstest.
Återstarta inte 252-cellsmatrisen, gör inga duplicerade 5 000-receptprov
och starta ingen automatisk nattlig fortsättning. Budgetslut ger en
tydlig delrapport, inte en ny tidsbudget eller ett falskt uppnått mål.

Integrera verifierade små commits på main enligt DEVELOPMENT, med
relevanta tester och grön ordinarie CI på slutligt huvud. Skriv
`docs/reviews/week-search-and-cache-20261026.md` med kompakt maskinunderlag
och uppdatera HANDOFF. Redovisa receptversioner och innehållsprov,
faktiskt minskat sökarbete, hållbar cacheåteranvändning, B:s fulla utfall,
pris-/giltighetsbevis och luckor, budgetsaldo samt nästa konkreta hinder.
Behåll legacy som standard och `library_merge_generations=False`.
Ingen beta-/produktionsaktivering, profiländring eller driftuppgift ingår.
