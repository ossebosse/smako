# Mindre dubbelarbete i faktaladdningen

[PR 56](https://github.com/ossebosse/smako/pull/56) tar bort en onödig
djupkopiering och återställning av nyss beräknade källfakta. Samma färdiga
projektion används direkt när diskcachen saknar underlag. Serialiseringen
läser fälten utan att först kopiera hela trädet; en diskträff återställs
och versioneras som tidigare. Källbyteskontroller och spärr mot att spara
partiella projektioner består.

Deklarationslistorna får dessutom anropslokala namn-/GTIN-index. De begränsar
indata till befintliga exakta kontroller av variant, märke, förpackning,
GTIN och konflikter. Alias och tvetydiga dubbletter bevaras. Index byggs
från aktuella rader vid varje anrop; inga produkt- eller användarbeslut
cachas mellan anrop. Recepturval, prisoptimering och 60-sekundersdeadline
ändras inte.

## Mätning på betans aktuella underlag

| Mätning | Före | Efter |
| --- | ---: | ---: |
| Kall faktaladdning | 35,414 s | 26,863 s |
| Kall planering, sparning och ägd GET | timeout 60,024 s | godkänd 55,273 s |
| Varm faktaladdning | 12,872 s | 11,615 s |
| Varm planering, sparning och ägd GET | 26,905 s | 24,947 s |
| Verifierat pris i varmt prov | 110,55 kr | 110,55 kr |

Även den kalla kandidaten levererade en slutkontrollerad meny för 110,55 kr.
Samtliga 54 515 faktaposter, alla deras fält och hela faktaversionen är
identiska med ursprungsimplementationen. Jämförelsen räknade om originalet
med separat tom cache efter kandidatproven, så kandidatens cache inte kunde
ge originalet ett falskt likhetsresultat.

Val: en italiensk middag för två, 10–15 ingredienser, mjölk 1 l,
Lund 22350/3 km/17 valda priskontexter, högst en butik och uttryckligt
uppskattningsläge. Isolerad container med exakt aktiv baskod och
planeringskonfiguration, inklusive Axfoods produktdetaljrelease,
skrivskyddade offentliga underlag, inget nät, 4 GiB och nya syntetiska
ägare/testdatabaser. Två kandidatmoduler injicerades endast i testprocessen;
deras AST överensstämmer med filerna i det faktiska releasepaketet.

Prisåterställningen tog separat 91,794/92,230 s före anropen. Tabellen
inkluderar inte den tiden, HTTP, kö eller browser. Enstaka kalla/varma
prov bevisar inte p95, samtidighet eller alla kombinationer av nya val.
De varma proven använder nya testdatabaser men samma menyval.

Profilering med cProfile visade 54 477 asdict-anrop och över sju miljoner
inre kopieringsanrop vid kall faktaladdning. Profilerarens tider används
inte som vanliga svarstider. Kvarvarande stora kostnader omfattar
detaljkällornas filkontroller och receptkvalificering; de har inte slopats.

## Verifiering

134 distinkta riktade fall passerar, liksom Ruff och compileall. Nya test
verifierar full diskåterställning med samma fakta/version, alias som
normaliseras lika, tvetydiga namn-/GTIN-dubbletter och ändrade deklarationer.
Befintliga prov för korrupta råbytes, läsfel och ofullständiga projektioner
består. En ny GTIN-testfixtur använde först fel nollutfyllnad; fixturen
rättades och kördes om grönt. Produktionsregler ändrades inte för testet.

Full CI och publikt betaresultat finns i
[aktiveringsjournalen](../../releases/menu-work-reduction-20261031/ACTIVATED.md).
Se även [maskinunderlaget](EVIDENCE.json).
