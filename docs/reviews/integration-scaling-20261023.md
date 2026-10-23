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
Kandidaten `f778e68` har **2 996 PASS, 10 XFAIL, 53 SKIP** i samma CI.
[Körning 39918497269](https://github.com/ossebosse/smako/actions/runs/39918497269).
Kandidaten `652e7ac` har **3 005 PASS, 10 XFAIL, 53 SKIP** i samma CI,
inklusive minnes- och referenskontrollerna.
[Körning 39921655367](https://github.com/ossebosse/smako/actions/runs/39921655367).

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

Den nya sökningen arkiverar dessutom färdigförfinade vinnare vid hela
publiceringsprefix upp till 512 och vid 1 000/2 000/5 000 recept. Arkivet
påverkar inte den geometriska huvudsökningens väg. En första variant som
matade tillbaka prefixens förfinade vinnare ändrade sökvägen och förlorade
469,84-kronorsmenyn; den varianten ersattes. Kontrakt
`smako-merged-library-search-v3` behåller den ursprungliga vägen och
arkiverar billigare giltiga prefixresultat separat. Ny körning på exakt
historiskt underlag, 1 000/K48: **469,84 kr**, 125,96 s första anrop och
36,12 s varmt. Det är ingen garanti för alla godtyckliga biblioteksstorlekar.

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
  har integrerats. Full katalog återanvänds via en begränsad ögonblicksbild
  som binds till katalogens ändringstid. Varje faktisk skrivning genomgår
  fortfarande ordinarie antal-/bytegränser; varje läsning verifierar innehåll.
- **Historikminne:** historikvalideringen serialiserade hela det skalade
  biblioteket och byggde ytterligare modellträd. Den återanvänder nu samma
  registrerade källobjekts skalade version; äldre eller andra källobjekt
  skalas separat. Alla strukturkontroller och indexets kontroll av
  motstridiga versioner består. Bibliotekssviten passerar lokalt.
- **Oföränderliga receptdelar:** skalning och kandidatkopior delar de
  frysta modellträden; receptlistor och beredningens formulärdata kopieras.
  1 310 skalningar av alla 262 recept till 1/2/4/6/12 portioner ger exakt
  samma serialiserade värden som tidigare, utan ändrade källrecept.
  Ett schemaomfattande prov kräver att varje delad underdel förblir
  rekursivt oföränderlig. Den globala cachen för rena recept-ID:n använder
  svaga referenser och håller därför inte avslutade anrops recept vid liv.

## Mätprotokoll och återstående resultat

Serverns integrationsmatris kör original-main med respektive utan 10 %
screening: sju profiler i båda städerna, `--repeat 3`, seriellt i separata
containrar med två CPU och 3 GiB. Varje process använder tom syntetisk
användarstatus och `--network none`. Första processanrop och två uppvärmda
anrop redovisas var för sig.

**Slutfört:** alla 14 par gav samma utfall, pris och semantiska hash i alla
tre iterationer. Malmö vegan gav `SEARCH_BLOCKED` i båda armarna;
övriga 13 profiler gav godkänd meny och slutkontroll. Tiderna är direkt
offlineplanering på servern, ingen last-/kökapacitet.

| Stad/profil | Pris i båda, kr | Varm median tidigare → standard, s |
| --- | ---: | ---: |
| Lund standard | 487,85 | 26,26 → 24,83 |
| Lund protein40 | 775,32 | 52,74 → 51,11 |
| Lund all-macros | 802,68 | 118,92 → 118,35 |
| Lund vegan | 347,90 | 12,84 → 12,85 |
| Lund distribution | 761,45 | 29,26 → 29,67 |
| Lund organic-share | 314,24 | 96,61 → 79,31 |
| Lund breakfast-snack-weight | 64,06 | 2,70 → 2,76 |
| Malmö standard | 511,46 | 30,82 → 28,98 |
| Malmö protein40 | 1 000,86 | 16,47 → 16,55 |
| Malmö all-macros | 1 000,86 | 17,15 → 16,73 |
| Malmö vegan | blockerat | 4,02 → 3,77 |
| Malmö distribution | 996,22 | 18,30 → 17,17 |
| Malmö organic-share | 321,16 | 145,84 → 132,58 |
| Malmö breakfast-snack-weight | 53,16 | 6,05 → 6,08 |

[Maskinunderlag](integration-scaling-20261023/results.json) innehåller
alla 84 iterationer, originalrapporternas SHA-256 samt faktiska indatahashar.
[Sammanställaren](integration-scaling-20261023/summarize.py) markerar
saknade celler som okända och jämför både pris, utfall och hash.

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

De parallella lokala körningarna uttömde Windows minne. Deras 37 sparade
skalningsceller är felsökningsunderlag och räknas inte som slutmatris.
En seriell servermatris med `5e5bc89` stoppades också: första cellen,
Malmö 5 000 standard, dödades av containerns **3 GiB-gräns efter 327,64 s**.
Dockers separata `oom`-händelse verifierar orsaken. Offertcacheändringen
ensam löste alltså inte minnesproblemet. En fasdiagnos stoppas kontrollerat
vid 2,78 GiB; den ledde till historikändringen ovan. Inga minnesgränser höjs.

**Full minneskontroll med `652e7ac`:** Malmö 5 000 standard slutfördes i
en ny process inom samma 3 GiB-gräns: godkänd slutkontroll, **511,46 kr**,
**2 988 081 152 byte peak RSS** (2,78 GiB) och 2 986 541 056 byte högsta
cgroup-minne. Ny separat CLI-process med samma kodsignatur, bibliotek,
indata, sökinställningar och varma diskcache gav samma meny/hash och pris:
123,74 respektive 124,44 s planering. Båda hade 8 217 cacheträffar,
2 142 missar, inga skrivningar eller ogiltiga poster. CLI-processens
separat redovisade modellinläsning tog 32,88 s; import, fil-I/O och
containerstart ingår inte i planeringstiderna. Full processväggtid ska
fortfarande mätas. [Maskinunderlag](integration-scaling-20261023/memory-and-cache.json).
Detta använder det tidigare 5 000-biblioteket. Slutmatrisen kontrollerar
samtliga profiler med de strikt nästlade biblioteken och samma minnestak.

Ett separat lokalt kallstartsexperiment vid Lund 5 000 använder två nya
processer med samma kodsignatur `894ef9911b79afd26f9a2962045cade65027e1801b84a0624ef6e16ac642fd2b`,
bibliotek och indata. Första processen: 500,75 s, 4 119 cacheträffar,
6 241 missar och 4 099 skrivningar. Nästa process: 134,72 s,
8 218 träffar, 2 142 missar och noll skrivningar; samma meny/hash,
499,31 kr. Den första körningen överlappade andra lokala minneskrävande
jobb: tiderna är observationer och bevisar inte en isolerad cacheeffekt.
Missarna i nästa process hör till cachetaket, inte olika kodsignaturer.
Denna kod föregår prefixarkivet; dess pris är inte slutkandidatens resultat.

Proxyprovet behöll hela basbiblioteket och de åtta lägst rankade tilläggen
per generation/proteinkategori: 272 av 946 kandidater i Lund 1 000,
487,85 kr, 122,40/33,24 s första/varma anropet. Rangordningen tog cirka
84/4,3 s. Full kvalificering och slutkontroll kvarstod för valda kandidater.
Priset måste jämföras mot full pool innan urvalet kan rekommenderas.
Ingen produktionssamplare har införts.

Slutmatrisens reproducerbara
[körverktyg](integration-scaling-20261023/run_matrix.py) använder samma
`PersonalPlanner`, syntetiskt tom privat status och oberoende slutkontroll.
Fullbiblioteksreferensen är fortsatt v5; CLI avvisar nu dessutom en
referens från ett annat eller ospecificerat receptbibliotek.

Den ursprungliga biblioteksbyggaren delade i 500-receptspaket och avslutade
med ett delpaket vid respektive slutstorlek. Därmed fick samma recept olika
paketproveniens mellan 1 000 och större bibliotek. Slutmatrisens publiceringar
bevarar i stället varje tidigare fullständigt receptvärde, inklusive
proveniens och innehållshash. Alla fyra bibliotek har byteidentisk metodkod
med signatur `2b996b1133054cbebe202258c864b4776b61e2923a672cc4ee61447a51951f9b`.
Lund körs med en lokal process åt gången; Malmö seriellt på servern med
två CPU och 3 GiB. Plattformar och mätprotokoll hålls uttryckliga i resultaten.

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
