# Förberedelsekostnad och minne, 2026-10-24

Arbete enligt [nästa uppdrag](../CODEX-SOL-NEXT-20261024.md).
Kodändringarna i [PR #9](https://github.com/ossebosse/smako/pull/9) och
[PR #10](https://github.com/ossebosse/smako/pull/10) är integrerade på main,
senast som `ea7c7ae005f1ea10dd716b53d327427785e84e61`.
Aktuell runtime: `eeda184926f02e73ab76e71e50c740e9dcb01b02`,
med identiska appfiler i denna main-version. Slutverifieringen fortsätter.
**Etappen är ännu inte standardkvalificerad.** `legacy` och
`library_merge_generations=False` är oförändrade standarder. Ingen aktivering,
insamling, faktarelease, Windowsuppgift eller ökad samtidighet ingår.

## Senaste utfall: versionsbytesfelet rättat och tre omprov godkända

`b5c242d` klarade nedanstående plan-/cacheprov men missade den efterföljande
grinden för katalogserialisering och versionsbyte. Ett första rättningsförsök,
`19ef0b2`, skrev native JSON-bytes och släppte buffertar före validering/index.
Processens topp-RSS sjönk, men cgroup nådde ändå **2 930 454 528 byte
(2,729 GiB)** när mer filcache belastade gruppen. Inte heller detta prov
godkändes; inget av försöken öppnade pilotgrinden.

`eeda184` läser nu filens produkt-, kandidat- och indexrader stegvis. Varje
rad går genom sin native JSON-validator; de vanliga omslutande modellerna
kontrollerar därefter hela produktdigesten, index, kontext, snapshot och
lineage. Ingen rad, publicering eller kontroll utelämnas. JSON-syntax,
Unicode och avslut granskas också; en avklippt fil kan inte bli en komplett
kandidat. Den befintliga atomiska filskrivaren behåller storleks-/hashkontroll,
fsync, diskutrymmesreserv och validering av scratch-filen före ersättning.
Stora buffertar släpps före nästa graf och endast oåtkomliga objekt städas.

Tre seriella omprov på exakt samma underlag och två CPU/3 GiB passerar:

| Prov | Peak efter ordinarie skrivning | Hela versionsbytesprovets peak | Processens väggtid |
| --- | --- | --- | --- |
| 1 | 2 012 753 920 byte | 2 372 689 920 byte (2,210 GiB) | 141,59 s |
| 2 | 2 091 364 352 byte | 2 339 295 232 byte (2,179 GiB) | 144,78 s |
| 3 | 2 188 840 960 byte | 2 436 276 224 byte (2,269 GiB) | 146,00 s |

Alla håller båda katalogernas 89 458 produkter och 71 138 faktarader vid
liv. Produktdigest, observationstider och hela den 191 730 753 byte stora
skrivna filens hash är exakt oförändrade. Ingen OOM eller swap. Dessa
diagnostikprov levererar ingen meny och ersätter inte plan-/auditgrinden.
Mätverktyget använder explicit GC/trim vid fasgränser, likadant i före- och
efterproven. Därefter har ytterligare tre prov körts utan sådan hjälp:
endast runtimekodens egna städgränser används i den vanliga följden
skrivning → överlappande inläsning/atomiskt byte. Alla tre passerar med
**2,023 / 2,039 / 2,030 GiB**, utan OOM/swap och med båda katalogerna samt
fakta kvar. Alla filer är byteidentiska med originalet. Processerna tog
143,94 / 145,60 / 143,47 s. [Ordinarie minnesprov och exakta kommandon](preparation-memory-20261024/runtime-only-memory.json).
Filcache ingår fullt i måttet och ingen OS-cache har rensats. Båda tidigare
misslyckandena bevaras i [minnesunderlaget](preparation-memory-20261024/temporary-memory-current.json).

85 riktade parser-/katalog-/hållbarhetsprov och 16 uppstarts-/minnesprov
passerar (101 olika prov). Full [CI på `eeda184`](https://github.com/ossebosse/smako/actions/runs/40100110649)
passerar inklusive Chromium/WebKit. De nya testen jämför native-värden,
metadata och serialisering samt avvisar trasig JSON, Unicode, digest,
produktpris, index och proveniens. En giltig gammal läsare behålls fram till
atomiskt byte och en ogiltig kandidat ersätter inte den aktiva versionen.

Slutkodens första vanliga fyranropsprov är klart: **662,83 s** första anropet,
sedan **11,66 / 11,86 / 12,19 s**. Alla ger 988,32 kr, förväntad hash och
audit PASS. Slutlig cgroup-peak är **2 021 113 856 byte (1,882 GiB)** efter
alla anrop, rapportskrivning och städning, utan swap. Processens hela
körkommando tog 756,71 s; legacy-förberedelsen 61,63 s/3 041 utvärderingar.
Det andra och tredje kalla provet gav **649,49 / 664,50 s**; samtliga tre
ger 988,32 kr/hash/audit PASS. Medianen är **662,83 s**, spannet
**649,49–664,50 s** och högsta slutliga processpeak **1,882 GiB**.
Alla har slutkvitto efter rapportserialisering och städning, utan OOM/swap.
[Aktuellt cacheunderlag](preparation-memory-20261024/cache-modes-current.json).
Samma
förgrundssekvens fortsätter med två ytterligare kalla prov och alla cachelägen, pilot,
HTTP/historik, tre matchade basprov, ny fasprofil och full matris. Varje
steg stannar vid missad grind. Metodsignaturen är
`17568fe52f2f4da372b1263979673cb79f74f731fa8ada05acc6fe8058e0d6b6`;
kodändringen invaliderar äldre förberedelseartefakter. Äldre planresultat
räknas därför inte automatiskt som `eeda184`-celler. Inget standardbyte.

Matrisverktygets stoppgrind har också skärpts: en blockerad v1-cell mot
en levererad legacy-/bas-/föregångarmeny stoppar körningen direkt, liksom
ett oförklarat byte av blockeringskod/steg. Tre kontraktsprov passerar och
visar att motexemplet sparas före stopp. Likadana blockerade observationer
förblir separat evidens och blir aldrig ett bevis för global omöjlighet.

### Cachelägen på slutkoden, tretton processer klara

| Läge på eeda184 | Plananrop | Utfall |
| --- | --- | --- |
| Tom appcache/ny ägarstore, tre processer | 662,83 / 649,49 / 664,50 s | 988,32 kr/hash/audit PASS |
| Legacy med varm offentlig disk | 139,82 s; sedan 104,25–106,99 s | 988,32 kr/hash/audit PASS |
| 262-prefix | 11,21–11,77 s för tre varma anrop | 996,22 kr, audit PASS |
| Omstart med disk/certifikat, tre processer | 50,92–52,55 s | Elva certifikat laddade, noll publiceringar omsökta |
| Borttagen offentlig/härledd cache, tre processer | 132,47–134,38 s | Elva certifikat laddade, noll publiceringar omsökta |
| Varm offentlig disk/ny ägarstore, tre processer | 641,40 / 637,84 / 641,36 s | 988,32 kr/hash/audit PASS |

Samtliga tretton processer och deras 19 planer passerar; primärprovets
fyra planer redovisas separat. Högsta slutliga processpeak är 1,882 GiB, inklusive filcache,
rapportskrivning och städning, utan OOM/swap. Varm max(5 000)/min(262) är
**1,0873**, mediankvot 1,0521. V1:s tre varma 5 000-anrop är snabbare än
alla tre jämförbara varma legacy-anrop. Detta är en profil/stad/faktaarm,
inte hela standardgrinden. De sex omstarts-/cacheförlustproven gör aktuell
slutkontroll och audit; de återanvänder inte en gammal kassasumma.
Syntetiska lagren har noll vanliga sparade leveranser. HTTP-/historikproven
och resterande pilot/matris är ännu inte körda. De tre vanliga
versionsbytesproven har också passerat; faktaprojektionen inför piloten
har därför startat.

Faktaprojektionen är klar för båda städerna, med peak **1,867 GiB i Malmö**
och **1,348 GiB i Lund**. Priser, request och klocka är byteidentiska med
originalen. Armen använder den oförändrade, partiella releasen
`16410fb3d4e21746a75cb6c34072bb4bcc159c20ceefec2ba1187bb883ac233a`:
91 verifierade Willys-dokument och 12 Hemköp-dokument samt 18 negativa
svar. Produktmatchningar kan vara fler än dokumenten; de räknas inte som
ytterligare dokumenttäckning. [Exakta manifest, resurser och kommandon](preparation-memory-20261024/axfood-projection.json).
Detta är faktaprojektion, inte levererad meny-/auditkvalificering.

### Pilot, första gruppen klar

Malmö/originalfakta/262 är avslutad med sex celler och 24 anrop:

| Profil | Legacy, betalt | V1, betalt | Första v1-anrop | Tre varma v1-anrop |
| --- | --- | --- | --- | --- |
| Standard | 511,46 kr | 492,15 kr | 176,92 s | 10,93–11,33 s |
| Fördelning | 996,22 kr | 996,22 kr | 46,55 s | 11,46–11,71 s |
| Organic-share | 321,16 kr | 321,16 kr | 560,60 s | 10,72–10,95 s |

Alla 24 anrop klarar aktuell audit och gruppens slutliga cgroup-peak är
**1 626 034 176 byte (1,514 GiB)**, ingen OOM/swap. Prisgrinden mot legacy
passerar i dessa sex celler. Detta kvalificerar inte hela piloten: 42 celler
återstår och 5 000/262-tiderna måste jämföras för varje profil/stad/faktaarm.
Motsvarande Malmö/5 000-grupp körs nu. [Pilotens löpande maskinunderlag](preparation-memory-20261024/pilot-current.json).

## Föregående runtime: tre kalla prov och cachelägen godkända

På `b5c242d` passerar tre nya processer med tom appcache och ny ägarstore:
**674,71 / 641,28 / 665,08 s**, median **665,08 s**, högsta registrerade
cgroup-peak **2,115 GiB**. Alla ger 988,32 kr, förväntad hash och audit PASS.
OS-diskcachen är okontrollerad och har aldrig rensats. De tre observationerna
är vanliga plananrop; instrumenteringsmålet under 700 s och tre matchade
basprov är fortfarande inte verifierade.

Alla tretton cachelägesprocesser är avslutade med exit 0, utan OOM och inom
2,5 GiB vid de registrerade mätpunkterna. Tillsammans omfattar de 19 planer;
primärprovets fyra planer redovisas separat. Högsta peak över sekvensen är
**2 273 837 056 byte (2,118 GiB)**. Äldre anrop saknar avslutande processkvitto;
de senare har även peak efter rapportserialisering. Skillnaden redovisas per
process i [b5-seriens cacheunderlag](preparation-memory-20261024/cache-modes-b5c242d.json).

| Läge på `b5c242d` | Plananrop | Cgroup-peak |
| --- | --- | --- |
| Legacy, varm offentlig disk, ny process | 137,35 s; sedan 104,20–107,02 s | 1,650 GiB |
| 262-prefixvy | 21,28 s; sedan 11,12–12,98 s | 1,499 GiB |
| Omstart med disk/certifikat, tre processer | 50,91–51,28 s | högst 1,582 GiB |
| Borttagen härledd/offentlig cache, tre processer | 130,68–134,51 s | högst 1,583 GiB |
| Varm offentlig disk, tre nya ägarstore | 635,02 / 643,65 / 639,46 s | högst 2,118 GiB |

Samtliga sex omstarts-/cacheförlustprov laddade elva certifikat och sökte
om noll publiceringar. Dessa store har **noll vanliga sparade leveranser**;
de bevisar inte återhämtning med icke-tom menyhistorik. Varm kvot
max(5 000)/min(262) är **1,1116** (mediankvot 1,0662), med tre varma anrop
per storlek. Samtliga är snabbare än jämförbara varma legacy-anrop. Detta
gäller endast Malmö/fördelning/originalfakta.

Den efterföljande minnesgrinden på `b5c242d` var däremot **FAIL**. Ordinarie `write_artifact` gav
**2 736 246 784 byte (2,548 GiB)**. När nästa katalog laddats och bytts
atomiskt med gammal läsare samt fakta kvar nåddes **2 905 780 224 byte
(2,706 GiB)**. Båda katalogerna innehöll 89 458 produkter, med identisk
produktdigest och observationstid; 71 138 faktarader behölls. Den skrivna
filen var byteidentisk med fryst indata (191 730 753 byte). Exit 0, ingen
OOM eller swap gör inte minnesgrinden godkänd. Piloten och följande matris
startade därför **inte på denna runtime**. [Motexempel och kvitto](preparation-memory-20261024/temporary-memory-current.json).

Ett separat fryst ASGI-prov är förberett för ordinarie registrering,
kö/progress/avbrott och sparning, följt av tre processer med faktisk sparad
historik. Det är ännu inte kört och räknas inte som evidens. Kvarvarande
arbete var att rätta den tillfälliga minneskostnaden och därefter köra om berörd
slutkod samt passera pilot, matchad jämförelse och full matris.
Äldre tabeller nedan bevarar tidigare revisioners observationer.

## Ändringar

- Innehållscachen inventeras en gång per batch under ett icke-blockerande
  OS-skrivlås. Samma 4 096 poster och 32 MiB gäller. Antal och faktiska bytes
  uppdateras efter varje atomisk skrivning. Nästa batch inventerar igen.
  Låskonkurrens och skrivskydd ger beräkning utan cacheskrivning.
- Ett redan utfärdat recept jämförs fortfarande med hela det granskade
  registervärdet. Dess validerade frysta ingrediens-/designdelar återanvänds
  utan ytterligare dump/parsning. Listor och beredningsformer kopieras.
  Oregistrerade indata går genom tidigare normalisering och modellvalidering.
- Vid planstart, efter kvalificering och varje färdig publicering samlas
  oåtkomliga Pythoncykler i generation 2. Mellan sökspåren används generation 1.
  På glibc återlämnas oanvända heap-sidor med `malloc_trim(0)`. Aktiva värden
  och beständiga artefakter evikteras inte. Tillgänglighet och utfall räknas
  separat. En plattform utan funktionen påstås inte ha återlämnat sidor.
  [API-kontraktet](https://man7.org/linux/man-pages/man3/malloc_trim.3.html)
  beskriver återlämning av fria sidor och trådsäkerhet. Kostnaden ingår i anropet.
- Produktindexets prisavtal valideras fortfarande före publicering. Exakta
  fältvärden och supplied-field-flaggor lagras kompakt; modellobjekten
  återskapas när en produktrad läses. Rekursivt immutabla värden är ett krav.
  Avvikande modelltyper/nya mutabla former behåller ursprungliga objekt.
  Giltighet, medlemskap och erbjudandevillkor prövas vid läsning som tidigare.
  Detta ändrar representationen inom befintligt index; ingen ytterligare
  pris-/offertcache eller normaliseringsväg införs.

Referens, varje publicerad föregångare, oberoende legacy-spår, budgetar,
slutlig kassa/audit och ägar-/raderingsgränser är kvar. Legacy-sökningen
återupptas inte från en tidigare vinnare. Dess återstående prefixarbete är
en redovisad kostnad, inte ett borttaget korrekthetskrav.

## Fasprofil och matchat inledande prov

Samma frysta Malmö/fördelning/5 000 som i rättningsrapporten. En seriell,
nätspärrad Linuxworker, två CPU, 3 GiB minne inklusive swapgräns och en ny
syntetisk ägarstore. Varje arm startar en ny process med tom app-/offentlig
förberedelsecache. OS-diskcachen är okontrollerad och har inte rensats.

| Observation | Bas `9162f0f` | Recept/batch `81d5e6a` |
| --- | ---: | ---: |
| Första instrumenterade plananrop | 858,60 s | 759,31 s |
| Kvalificering | 207,00 s | 86,83 s |
| Singletonkorgförsök under kvalificering | 4 871 | 4 871 |
| Oberoende legacy-förberedelser | 200,30 s | 203,58 s |
| Verkliga legacy-utvärderingar | 9 517 | 9 517 |
| Betalt | 988,32 kr | 988,32 kr |
| Audit | PASS | PASS |
| Cgroup-peak | 3,000 GiB | cirka 2,911 GiB |

Menyerna har samma semantiska hash
`1c0ad484edda7e36bf026b83a6e4f171dddf9c8d4a2b3d5359d95fa90bc227b7`.
Detta är **ett kallt instrumenterat prov per arm**, inte tre oberoende
latensprov. Det visar 11,6 procent kortare första anrop och cirka 58 procent
kortare kvalificering i dessa observationer. Delmålet efter fasprofilen sattes
till under 700 s för första instrumenterade anropet och högst 2,5 GiB
cgroup-peak. Mellanversionen ovan uppnådde inget av dessa delmål.

Den lokala detaljprofilen på samma hashbundna 5 000-bibliotek visade över
åtta miljoner filkontroller medan innehållscachen fylldes. Windowsprofilens
499 s inklusive cProfile och filsystemkostnad är metoddiagnostik, inte
serverlatens. Den förklarar varför katalogarbetet åtgärdades först.

Basens inläsning tog 32,87 s, varav återställning/index 17,98 s. Separata
poster finns för plannerinitiering, publiceringshashning, kvalificering,
varje sökanrop och ägarartefakternas läs-/skrivning. Tider inuti större
faser överlappar och får inte summeras som oberoende faser. Profilens unika
korgsignaturer använder slot-ID och receptens objektidentitet; de bevisar
inte värdelikhet eller att återanvändning av hela söktillstånd är säker.

Det äldre provets 740,87 s hade legacy först i samma process. Det är ett
annat cacheläge och används inte som nämnare för den kalla jämförelsen.
Runnerns råfält `profiled=false` är hårdkodat; fasprofilens wrapperkörningar
är instrumenterade trots detta fält. Tomt användartillstånd per anrop
betyder inte tom ägarcache: den valda ägarstoren återanvänds vid varma
upprepningar. Hela processens tid och plananrop redovisas separat i maskinunderlaget.
HTTP-väntetid och admission-kötid är inte mätta av denna direkta plannerprobe.

## Minnesundersökning och senaste fulla planprov

Tidigare försök att internera frysta modellvärden och supplied-field-metadata
klarade värde-/serializerprov men gav inte tillräcklig resident minnesmarginal.
De togs bort före `193629f`. Provet på `fd15480` avbröts manuellt:
exit 137, `OOMKilled=false`. Det är ingen slutförd pris-/auditcell och ingen OOM.

Ett inläsningsprov på `81d5e6a`, med pris-/faktaobjekten kvar, gav efter
GC och trim RSS **2 093 703 168 → 1 624 489 984 byte**, cirka 447 MiB
återlämnat. Detta är bara diagnostik, inte hela planeringens minnesmål.
Det motiverade återlämning vid fasgränser; det ersätter inte minskad beräkning.

| Runtime/metod | Första plananrop | Efterföljande anrop | Cgroup-peak | 2,5 GiB |
| --- | ---: | --- | ---: | --- |
| `d44a64b`, instrumenterad, full GC/publicering | 773,75 s | 10,36/10,26/10,20 s | 2,520 GiB | FAIL |
| `0f626bd`, vanlig, full GC/sökspår | 839,06 s | se rårapport | 2,416 GiB | PASS, en process |
| `9fc82a6`, vanlig, GC generation 1/sökspår | 781,58 s | 10,31/9,97/10,05 s | 2,807 GiB | FAIL |
| `193629f`, vanlig, dessutom kompakta avtal | 778,95 s | 10,18/10,11/10,29 s | 2,327 GiB | PASS, en process |
| `ea4bb08`, vanlig, prefix + kompatibel metadata | 709,68 s | 12,31/11,88/11,80 s | 1,800 GiB | PASS, en process |
| `b5c242d`, vanlig, dessutom avbrott/progress | 674,71 s | 12,36/11,69/12,32 s | 1,848 GiB | PASS, en process |

Alla levererade menyer i tabellen ger 988,32 kr, samma hash och audit PASS.
Instrumenterade och vanliga tider är olika metoder och utgör inte en
matchad latensjämförelse med varandra. Varje rad startar med tom appcache
och ny ägarstore. Varma upprepningar är inte nya kalla processprov.
Senaste vanliga anropet är under 700 s i ett prov; delmålet för matchad
instrumentering har inte återkörts på senaste kod och är inte kvalificerat.
Inläsningen på `b5c242d` tog 49,52 s. Hela processen med första och tre varma
plananrop tog 772,42 s inklusive startkommandots overhead (containerns
livslängd 771,98 s). Dessa tider hålls skilda från varje plananrop och
från ännu omätt HTTP-/admissionväntan.

Full GC efter varje sökspår kostade 129,24 s i `0f626bd`; i `193629f`
kostade den valda kombinationen 33,23 s. Legacy-förberedelserna kostade
196,65 s i det provet och finns kvar över samtliga elva publiceringar.
Även den kvarstående beräkningskostnaden ingår i 778,95 s. `b5c242d` använder
61,35 s och 3 041 verkliga legacy-utvärderingar med samma elva publiceringar;
de övriga sökspåren och aktuell audit kvarstår.

Cgroup mäts inklusive filcache och kernelminne. En värdobservation på
`9fc82a6` visade cirka 332 MiB filcache i gruppen, mot mindre i andra prov.
Ett tidigare enstaka PASS gav alltså inte stabil marginal. Filcache får
inte subtraheras eller delad OS-cache rensas för att få PASS. Slutprovet
visar cirka 178 MiB marginal till 2,5 GiB i just den processen.

Cachecensus efter kvalificering höll 1 849 recept, 89 458 produkter och
71 138 faktarader vid liv. Sekventiell tömning av offert-, närings-,
resolution-, recept- och spårcacher frigjorde sammanlagt cirka 59 MiB RSS.
Det är ordningsberoende marginaler med delade referenser, inte exklusiva
objektstorlekar eller ett plan-/auditprov. Ett separat inläsningsprov med
kompakta avtal gav efter GC/trim RSS 1 376 272 384 byte, mot 1 624 489 984
för tidigare representation. Därför åtgärdades katalogens långlivade
avtalsmodeller. Diagnostikproven räknas inte som godkända matrisrader.

Cachelägessekvensen på `193629f` är avslutad efter elva lägen och **underkänd
minnesgrind**. Den vägrar fortsätta om föregående process inte klarar pris,
hash, audit och 2,5 GiB. Varje omstart
får en egen kopia av offentlig cache och SQLite-backup av syntetisk
ägarstore där läget kräver den. Cacheförlust tar bara bort klonens härledda
kvalificerings-/menyvyer och offentlig cache; certifikaten bevaras.
Historik räknas före/efter. Dessa benchmarkstore har noll vanliga sparade
leveranser. Ägarhistorik prövas separat i permanenta regressionstester och
påstås inte ha mätts mot verkliga ägarhistoriker.

Färdiga cachelägen på samma runtime och frysta fördelningsprofil:

| Läge | Plananrop | Cgroup-peak | Resultat |
| --- | --- | --- | --- |
| Legacy, varm offentlig disk, ny process | 131,92 s; sedan 103,37–107,15 s | 2,201 GiB | 988,32 kr, audit PASS |
| Förberedd 262-prefixvy | 16,56 s; sedan 9,07–9,15 s | 1,852 GiB | 996,22 kr, audit PASS |
| Ny process, varm disk + certifikat, tre processer | 35,61–36,14 s | 2,034–2,307 GiB | 988,32 kr, audit PASS |
| Ny process, borttagen offentlig/härledd cache, tre processer | 110,91–112,49 s | 2,126 GiB | 988,32 kr, audit PASS |
| Ny process, varm offentlig disk, tre nya ägarstore | 785,69/829,74/782,71 s | 2,315/2,329/**2,624 GiB** | Pris/audit PASS, sista minnesprovet **FAIL** |

De sex omstarts-/cacheförlustproven laddade elva certifikat och sökte om
noll publiceringar. De nya slutkontrollerna är fortfarande obligatoriska.
För varm planering ger max(5 000)/min(262) = **1,1344**, mediankvot 1,1159,
med tre varma anrop per storlek. Det klarar 1,25 i just denna profil/stad.
Varm 5 000-planering är också snabbare än de tre motsvarande upprepade
legacy-anropen. Första legacy-anropet ovan har varm offentlig disk och
jämförs inte som ett matchat kallt appcacheprov med 778,95 s.
Hela processens väggtid, inklusive inläsning, finns separat i
[cachelägesunderlaget](preparation-memory-20261024/cache-modes.json).

Samtliga 17 planer i sekvensen och primärprovets fyra planer klarade pris
och audit; alla elva cachelägesprocesser avslutades med exit 0 utan OOM.
Sista processens cgroup-peak var
**2 817 421 312 byte**, över målet 2 684 354 560. Processernas topp-RSS var
likartad (cirka 2,48–2,49 GB), men filcache vid just denna cgroup-topp
samplades inte. Orsaken får inte anges som bevisad filcachevariation.
Det separata provet för serialisering/överlappande syntetiskt versionsbyte
startade därför inte: `NOT_RUN_DUE_TO_MEMORY_GATE`. Ingen OOM eller
godkänd versionsbytesmarginal påstås. Råbuntens SHA-256 är
`2c62f8d3f94aff708ecd6c07b70ef1b5a18ba8111c9593d78c90b824ffcaeb32`.

## Nästa kandidat: prefix och modellmetadata

En objektcensus efter kvalificering på `193629f` fann 681 483 GC-spårade
set, tillsammans 659 674 440 byte i grundstorlek. Modellernas supplied-field-
metadata stod bland annat för 202 532 912 byte i 89 458 Product,
107 314 128 byte i 112 974 SourceProvenance och 88 219 040 byte i
121 180 RecipeIngredient. Dessa kolumner överlappar set-totalen och får
inte summeras till exklusiva allokeringar. Aktiva produkter/fakta/recept
behölls; provet levererade ingen meny och räknas inte som audit.

Kandidaten delar endast immutabla fältnamnsmönster i frysta modeller,
med högst 256 mönster/1 MiB. Publik `model_fields_set` materialiserar ett eget
muterbart native-set vid första läsningen. Kopiering, explicit konstruktions-
alias, pickle-state och `exclude_unset` behåller native-beteende. Anpassade
serializer-/copy-/computed-hooks behåller tidigare metadata. Validering av
domänvärden ändras inte; 19 modellers JSON-scheman är identiska med basen.
23 kompatibilitetsprov passerar. Inläsning med aktiva priser/fakta gav
RSS efter GC/trim **1 013 547 008 byte**, jämfört med 1 376 272 384 för
`193629f`, cirka 346 MiB mindre. Detta är diagnostik, inte full minnesgrind.

Legacy-spårets lokala checkpoint sparar tillståndet **före** terminal
förfining och återanvänder endast ett exakt oförändrat prefix inom samma
förberedelse. Varje publicering förfinas och slutkontrolleras fortfarande.
Ändrad kontext, recept, ordning, initialutvärdering eller okänd anpassning
ger en oberoende ombyggnad. En tidigare slutvinnare används aldrig som
ersättningsseed. 33 riktade prov innefattar ett motexempel där ett sådant
seed hade missat nästa vinnare. Se [bevis och avgränsningar](preparation-memory-20261024/prefix-checkpoint-proof.md).
Den frysta diagnostiska oraclen jämförde alla elva faktiska kandidater med
nya oberoende sökningar, inklusive hela korgen: **alla exakt lika**,
3 041 verkliga utvärderingar mot 9 517 oberoende. Slutplanen gav 988,32 kr,
förväntad hash och audit PASS. Dess dubbla arbete får inte användas för
latens- eller resurskvalificering.

Full [CI på `ea4bb08`](https://github.com/ossebosse/smako/actions/runs/40088977188)
passerar inklusive Chromium/WebKit. Vanliga resursprov pågår; de måste
slutföras innan kandidaten kan ersätta tidigare mätkod.

### Avgränsade jobb och avbrott

Runtime `b5c242d215b4655a5d8176fbe6f61c4822c64475` tillför kooperativt
avbrott inom befintlig admission. En permanent regression reproducerade
att en avbruten tråd fortsatte efter nästa fasgräns. Tråden får nu en egen
Event via kopierad ContextVar och kontrollerar den mellan recept, korgar,
kohorter och faser. Admission släpps först när tråden verkligen har slutat,
även vid upprepade avbrott. Pågående atomiska lagringsoperationer avbryts
inte mitt i en skrivning. Ingen ny worker eller kö införs.

Ägaren kan begära avbrott med `DELETE /api/plan-jobs/{id}`. Svaret är
`cancelling` tills arbetet har upphört; avslutade resultat tas inte bort.
Andra ägare får 404. Sidnavigation stoppar fortsatt bara statusläsaren och
avbryter inte automatiskt ett accepterat serverjobb. Jobbstatus ger faktisk
recept-/publiceringsprogress, inte en uppskattad total procent eller ETA.

Ett nytt weakref-prov fann också att det avbrutna jobbets traceback behöll
plannerobjekten under retention. Samma städning av avslutade traceback-
ramar som för misslyckade jobb används nu även för avbrott. 33 jobb-/admission-
och personliga prestandaprov samt 119 prefix-/certifikat-/metadatarelaterade
prov passerar. Ruff och compileall passerar. Full
[CI på `b5c242d`](https://github.com/ossebosse/smako/actions/runs/40091178789)
passerar inklusive Chromium/WebKit.

## Verifiering och återstående grindar

Tidigare 170 riktade offlineprov passerade. Efter senaste indexändringen
passerar 100 fokuserade prov för produktsökning, PriceUniverse och minne.
Den fulla sviten behåller cache-/ägare-/Axfood-regressionerna samt nya prov
för receptmutation efter eviction, batchgränser, låsstrid, GC, avtalsvärden,
serialisering och bevarat aktivt tillstånd. Ruff, compileall och diffkontroll
passerar. Full [CI på runtime `193629f`](https://github.com/ossebosse/smako/actions/runs/40077624097)
passerar inklusive Chromium/WebKit (progressmarkörer: 3 116 PASS,
10 XFAIL, 53 SKIP; saknat historiskt lokalt underlag redovisas som SKIP).
Äldre gröna interneringsrevisioner räknas inte som slutkodens CI.

[Maskinunderlag](preparation-memory-20261024/phase-evidence.json),
[kommandon och faktiska resurskvitton](preparation-memory-20261024/commands.json)
och [cellinventering](preparation-memory-20261024/cells.json).
Råfiler: `.local/preparation-memory-20261024/` och
`/opt/smako/evidence/preparation-memory-20261024/`. Ingen produktionsdatabas
är skrivbart monterad i proberna.

Inventeringen skiljer originalfakta från partiell Axfood-arm, sju profiler,
två städer, fyra storlekar, två sökpolicyer och v5 endast vid 262. Den räknar
**252 uttryckliga cellidentiteter, inte 252 godkända celler**. Malmö/fördelning/
5 000/v1 är uppmätt pilot, ännu inte standardkvalificerad. Äldre kods
matrisresultat räknas inte automatiskt som slutkodens resultat.

Kvar: tre kalla jämförbara prov på basarmen, matchad instrumenterad profil,
färdig evidens för alla slutkodens
cachelägen, aktuell legacy-jämförelse och 262-kvot, övriga pilotprofiler/
städer, versionsbyte/serialisering under minnestak och hela slutmatrisen.
Ingen generell total bytebudget för alla RAM-cacher har bevisats; marginalen
ovan gäller det enskilda frysta provet. Axfood-releasen omfattar fortsatt
103 verifierade dokument. Ingen full täckning, ny faktaaktivering eller
återfunnet historiskt Malmöarkiv påstås. Policyn förblir opt-in medan
någon grind återstår.
