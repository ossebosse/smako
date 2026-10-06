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

Elva positiva mobilflöden på slutimagen: tre riktade navigations-/återanslutnings-
resor per webbläsare, ordinarie huvudklick i båda, sexreceptspaketets fasta
sparnings-/renderingsdiagnostik i båda samt äldre menyflöde med flagga av.
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
omöjligen kan återkomma. Slutliga individuella kvalificeringar och tids-/skal-
prov redovisas separat när respektive råkörning är färdig.
