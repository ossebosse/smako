# Versionsbundna prov

Slutruntime `fd2cfda5490a`, låst implementation `e2e5d248ee44`. Paket och image
identifieras i PACKAGE.json. Etapp B har inte aktiverats.

## Nyss körda källkodskontroller

97 relevanta Pythonprov passerade: måltidsimport/artefakter, befintligt
receptbibliotek, köks-/proteinfördelning, korgmotor, jobb, strikta
webbläsarobservatörer och felpresentation. Ruff för ändrade API-/testfiler,
compileall för API/tjänster samt tio Node-transportprov passerade.
Koden i de proven är hashidentisk med e2/fd; inga efterföljande runtimeändringar.
Råloggar finns under `.local/meal-library-20261006/`.

Meningsfulla före/efter:

- Samma 5 400 sökförslag gav före för många samtidigt levande korgobjekt;
  efter behålls högst 290, med samma vinnare och utvärderade förslag.
- Återkallade versioner var fortfarande aktuella före spärren; efter tas de
  bort från nya val och stoppas i omräkning. Historiska GET-materialiseringar
  bevaras.
- Retained PolicyConflict/PersonalConflict blev 500 i status-GET före;
  efter återges 422/409, samma ägare/jobbreferens och en körning. Oväntade
  programmeringsfel förblir serverfel.
- Strikt observatör skiljer exakt förlustinjicerat startsvar från oväntad
  ogiltig JSON. Det senare underkänns; inga breda WebKit-/statusundantag.

## Paketerade verkliga användarflöden

Fjorton positiva mobilflöden på slutimagen: tre riktade navigations-/återanslutnings-
resor per webbläsare, ordinarie huvudklick i båda, sexreceptspaketets fasta
sparnings-/renderingsdiagnostik i båda samt äldre menyflöde med flagga av och fem enkla middagar för två via den ordinarie knappen.
[Full evidens](BROWSER-EVIDENCE.json) bevarar tidsstämplar, jobbreferenser,
laddade JavaScript-hashar, DOM, statusanrop, injektioner och råa avbrott.
Varje återhämtningsgeneration binds till exakt en instrumenterad tung
beräkning. Byte och uttrycklig omräkning är separata avsiktliga jobb.

Fyra äldre 15/20-profiler kördes med oförändrade requests och 40/30/20-krav.
Alla fyra lästes oförändrat efter faktisk appomstart med samma ägare och
korrekta skafferirevisioner. Separat privat 300-g-skafferiprov fördelade ost
över alla tre måltidstyper; frukost-/mellanmålsbyte skapade tre oföränderliga
revisioner. Främmande ägare får 403 för plan och 404 för jobb.

En consistent, isolerad lagringskopia med 267 revisioner från flera tidigare
releaser materialiserades med slutkoden: request och plan oförändrade, samma
radfingerprint. Två historiska rader med återkallat innehåll kan fortfarande
läsas. Detta är internt lagringsprov, inte autentiserad HTTP-läsning av varje
historisk ägare. [Kompatibilitet](COMPATIBILITY.json).

Flagga av i samma nya image behåller sparade nya planer/revisioner läsbara
(WebKit) och det äldre menyflödet fungerar (Chromium). Ingen återgång till
äldre binär eller äldre databas kvalificeras. Ofärdiga minnesjobb påstås inte
överleva appomstart.

## Avgränsning och råa FAIL

Det första API-skafferiprovet tappade en statusanslutning med
RemoteProtocolError. Containern fortsatte utan OOM och samma jobb beräknades/
sparades en gång. Oförändrad omkörning passerade hela provet. Grundorsak är
fortsatt obelagd; omkörningen är ingen appfix. Rått FAIL och serverkorrelation
bevaras. A:s tidigare WebKit-latensavvikelse är ett separat fall.

Ett extra huvudfallsanrop valde felaktigt biblioteksläge för den gamla
middagsbegäran och fick korrekt 422. Det är verktygsval, inte försvagade
användarkrav. Andra bevarade verktygsfel gäller saknad PYTHONPATH,
fixtureåtkomst, Windows-filkodning och fel benchmarkfil. Det felaktiga
benchmarkresultatet 173,45 kr är inte P0 eller matbevis. Den korrigerade
harnessen är semantiskt hashidentisk med den låsta Git-koden; Windows-kopian
har endast CRLF i stället för LF. Alla giltiga jämförelseled använder samma
verifierade harness och inputs.

Kontrollerad mobil WebKit är inte fysisk iPhone. Simulerad dold sida är inte
bevis för operativsystemsombyte. Mockade frontendtester är separata från
ovanstående riktiga jobb. Ingen provlagning eller liveprisinsamling påstås.

## Återanvändning

Dd12:s tidigare status-, ägar-, idempotens- och admissionbevis återanvänds bara
för de oförändrade delarna; de räknas inte som nykörda i B. Historiska råa
FAIL för WebKit, socketfel, två innehållsfel, sökningens OOM och instrumenterat
SIG139 bevaras. Nyare PASS visar provad robusthet, inte att intermittenta fel
omöjligen kan återkomma. Slutliga individuella kvalificeringar, tidsmatris och 1×/2×/5×-skalprov är färdiga; råfilerna och begränsningarna redovisas separat.

## Slutlig innehålls- och uppdateringsprövning

Alla 24 + 6 recept kvalificerade i slutimagen, med full korg, numerisk näringsprövning och oberoende audit. Inga obligatoriska 30/40-g-mål i individproven. [Individuella utfall](QUALIFICATION.md). Hela P0–P3-tidsmatrisen är färdig, tre kalla och tre varma nyberäkningar per ordinarie fall, separat artefaktläsning och CPU-förberedelse. [Prestanda](PERFORMANCE.md), [skalning](SCALE.md).

Kontrollerad invalidering prövade oförändrat underlag, en ändrad näringsfakta, ett först saknat och sedan återinfört verkligt kvarg-SKU, ändrat pris, kampanjdatum och ny receptversion. Identiskt källunderlag gav en träff utan omskrivning; ny receptversion en ny strukturrad och 181 återanvända. Ändrad källsignatur återbyggdes konservativt. [Operander och faktiska korgar](INCREMENTAL.json). Injekterade uppgifter är endast testoperander, inte nya publicerade fakta. Ett separat fast tvåmåltidsprov använder 150 + 150 g av samma yoghurt och köper en 1 000-g-förpackning; inga besparingar tillskrivs det provet.

Det första prisändringsprovet ändrade endast ordinarie pris, medan lägre befintligt effektivt pris fortfarande var tillämpligt. Det gav ingen betalningsförändring. Ett kompletterande produktlåst prov ändrar hela det kontrollerade prisavtalet och visar 29,40→30,40 kr, oförändrad näring och godkänd audit. En riktig katalogkampanjs korg ger 39,00→56,70 kr dagen efter utgång. Fyra kandidater med otillräcklig semantisk kvalificering stoppas av samma audit och redovisas; första försökets assertion är bevarad. Detta är testverktygsomfattning, ingen ny appfix eller försvagat godkännande.

Två slutliga huvudklick utan omladdning under generering passerade: Chromium 63,812 s och WebKit 72,297 s. Samma fulla recept, korg, näring, audit och övriga icke-diagnostiska kontroller som tidigare huvudprov; en tung beräkning var. Ett första extra Chromium-försök startade utan readiness-grind och fick tomt startsidesvar, sedan testinitieringsfel på webbläsarens felsida. Rått FAIL bevaras, inga fellyssnare eller appregler ändrades. Föregående 63,875/63,281 s var prov med avsiktlig omladdning, inte ostörda huvudklick.
