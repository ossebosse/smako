# Integrationsgranskning och fortsatt receptskalning, 2026-10-23

Arbetet utgår från `2efb62f219b31fa6a81c16ba71363b4207cb2dfe` och
[`CODEX-NEXT-20261023.md`](../CODEX-NEXT-20261023.md). Rapporten kompletteras
med den pågående matrisen innan leverans. Sammanslagna kohorter är fortsatt
av som standard. Ingen produktionsaktivering, schedulerändring,
butiksinsamling eller skrivning till aktiva prismanifest ingår.

## Verifierad integration

GitHub-CI på exakt hämtad main: **2 950 PASS, 10 XFAIL, 53 SKIP**, inga fel.
[Körning 39907572666](https://github.com/ossebosse/smako/actions/runs/39907572666)
inkluderar installation av Chromium/WebKit och webbläsartester.
Kandidaten `5e5bc89` har **2 985 PASS, 10 XFAIL, 53 SKIP** i samma CI.
[Körning 39911776590](https://github.com/ossebosse/smako/actions/runs/39911776590).
Tre senare tillagda prov av den verkliga slutkontrollen och privat
skafferifördelning passerar också lokalt; slutlig CI redovisas vid integration.

### Aktuella serverfakta

En isolerad export använde de faktiska aktiva prisartefakterna och
`load_retained_facts` mot serverns SQLite/råsnapshots, båda monterade
skrivskyddat. Ingen butikskälla anropades. Varje artefakt verifierades mot
manifestets SHA-256 före läsning. Fakta exporterades av main-koden, med
Axfood-produktdetaljer fortsatt avstängda. Varje stad har sin egen frysta
exportklocka och hashmanifest.

| Underlag | Lund | Malmö |
| --- | ---: | ---: |
| Prisprodukter | 44 754 | 89 458 |
| Produktfakta | 42 697 | 71 138 |
| De 40 integrerade recepten: godkänd kvalificering och kassakontroll | 40/40 | 40/40 |
| Produkter med ”ägg” i namnet | 190 | 333 |
| Godkända skalägg | 97 | 186 |
| Godkända med användbar mängd i gram | 97 | 186 |

Alla godkända unika äggnamn granskades: hela skalägg, inga sammansatta
äggprodukter. De råa besluten bevarar namn, kedja, butik, produkt, ingredienser,
förpackning och mängd. Detta är aktuellt sortiment vid exporten, inte en
fullständighetsgaranti för framtida produkter.

En separat innehållskontroll verifierar alla 40 recept och skalning till
1/2/4/6 portioner: **160 struktur- och mängdkontroller**, beroendeordning,
16 kött-/fiskrecepts angivna 63/72/74 °C samt **53 skalbara vattenmängder**.
Tidigare redovisad ospecificerad mängd kokvatten och linstyp är kvar som
redaktionella begränsningar. Ingen provlagning påstås.

Driftens `ready` svarade 200 och publicerat/laddat prismanifest var identiskt.
Coops behållna kvalificerade baspriser hade en separat åldersvarning.
Exporten gör inte deras observationer yngre. Granskningen ändrade ingen drift.

### Mängd och konflikter

`_mass_blocking` undantog alla konfliktnamn som började med `nutrition`.
Undantaget begränsas nu till de sju faktiskt kända näringskonflikterna.
Okända konflikter, inklusive okända namn med samma prefix, blockerar mängden.
Exakt belagd avrunnen mängd får fortfarande användas vid en oberoende
näringskonflikt. Näringskonflikten bevaras.

93 riktade prov passerar. Nya negativa fall omfattar annan produkt, butik,
snapshot, förpackningsmängd eller enhet, saknad hash, ogiltig mängd och flera
motstridiga mängdbevis. Pris, originalförpackning och näringsspärrar bevaras.

## Lund 1 000: den tidigare prisökningen

Det exakta historiska underlaget finns i den återfunna serverexporten,
med faktahash `409ac1fbbba7c81bd87cce69434c60e85121862938ca252238c1f4fbbcb36c2e`.
Samma klocka och priser reproducerar avvikelsen:

| Sökning | Pris, kr | Varm körning, s |
| --- | ---: | ---: |
| Main, per paket | 474,43 | 24,86 |
| Geometriska kohorter, K16 | 474,43 | 28,07 |
| Geometriska kohorter, K32 | 478,35 | 21,23 |
| Geometriska kohorter, K48 | 469,84 | 30,01 |

K32 går från en annan ersättningsföljd till 479,85 kr; parförfiningen når
478,35 kr. Main går via bland annat äggcurryn och når 474,43 kr i den andra
förfiningen. Kraven ogiltigförklarar inte den billigare menyn. Kostnaden är
icke-monoton i heuristikens K: större prövad mängd ändrar även sökvägen.
K48 rättar detta konkreta fall men är inte ensamt bevis för ett standardbyte.
Tiderna är lokala; flera mätprocesser förekom och de är inte serverkapacitet.

## Ändringar under prövning

- **Små pooler:** det valbara sammanslagna läget räknar alla fullständiga
  veckokombinationer när högst 4 096 kombinationer finns. Symmetrin används
  bara för genererade utbytbara platser utan privata skafferiuttag eller
  produktlås. Alla krav och korgkontroller körs; vinnaren går sedan genom den
  oberoende slutkontrollen. Nio riktade prov inkluderar ett dyrare lokalt
  minimum som kräver tre samtidiga byten, privat skafferi och en avvisad
  slutkontroll. Globalt lägsta produkt-/näringspris påstås inte.
- **Offertminne:** de nya mapparna för namngivna offerter, frysta korgrader
  och radoberoende offertuppsättningar ingick inte i den befintliga
  cachebudgeten. De omfattas nu av samma tömning; även två strukturella
  sidomappars poster räknas. 73 offert-/korgprov passerar. Effekten på Malmö
  5 000 måste mätas innan 3 GiB-gränsen kan påstås vara uppfylld.
- **Mätbarhet:** acceptansverktyget kan uttryckligen återanvända en
  förberedelsecache mellan processer och redovisar bibliotekssignaturen.
  46 kontraktsprov passerar; fullbiblioteksreferensen är fortsatt v5.
- **Kallstart, separat experiment:** en full förberedelsecache läste ändå
  storleken på varje sparad fil för varje miss. En avgränsad tidig kontroll
  prövas i egen worktree; cachekapacitet och innehållsvalidering består.

## Mätprotokoll och återstående resultat

Serverns integrationsmatris kör original-main med respektive utan 10 %
screening: sju profiler i båda städerna, `--repeat 3`, seriellt i separata
containrar med två CPU och 3 GiB. Varje process använder tom syntetisk
användarstatus och `--network none`. Första processanrop och två uppvärmda
anrop redovisas var för sig.

Den breda lokala skalningsmatrisen använder 262/1 000/2 000/5 000 recept och
main/K16/K32/K48, samt v5-referens utan begränsningar vid 262. Pris-/faktaunderlag
läses en gång per stad och bibliotek, med ny tom användarstatus vid varje
meny. Offentlig förberedelse återanvänds som i en varm appprocess. Detta
protokoll betecknas uttryckligen som delad process och ersätter inte kallstart.
Syntetiska testrecept importerades genom ordinarie `author --import` i
Git-worktrees. Main-checkoutens receptbibliotek ändrades inte.

Kodsignaturernas samtliga 123 källfiler har byteverifierats mellan
skalningsbiblioteken. Windows CRLF/LF gav först olika signaturer för samma
Pythoninnehåll; den första proxykörningen bevaras separat och jämförs inte
som en körning med samma kodsignatur. En ny proxykörning använder enhetliga
byte och ny cachekatalog. Två lokala stadsmatriser och korta separata
experiment överlappar; lokala tider är därför inte ett kapacitetslöfte.

**Pågående:** kompletta matristabeller, prisspärrar mellan biblioteksstorlekar,
utfall mot full pool för proxyurval, kallstart med samma slutkod samt
Malmö 5 000 minne. Inget standardbyte är godkänt genom denna delrapport.

## Ägarbeslut utanför uppdraget

Axfoods återstående 503 Hemköp-hämtningar, lagringsplats, uppdateringsrytm
och aktivering av `AXFOOD_PRODUCT_DETAIL_ROOT` behöver separat beslut.
Ingen sådan hämtning eller aktivering gjordes. Den tidigare detaljsamlingen
återfanns inte i denna klons kända lokala underlag; effekten av berikning med
den samlingen kan därför inte redovisas som verifierad här.

[`PR #7`](https://github.com/ossebosse/smako/pull/7) är utkast tills
granskningens återstående resultat har bedömts. Alla experimentella söklägen
och eventuella avvikelser ska redovisas före integration.
