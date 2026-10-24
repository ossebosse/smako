# Förberedelsekostnad och minne, 2026-10-24

Arbete enligt [nästa uppdrag](../CODEX-SOL-NEXT-20261024.md), på
`perf/preparation-memory-20261024`, [PR #9](https://github.com/ossebosse/smako/pull/9).
Senast mätt runtime: `193629fbd0a0360955726f7a28bc30700ed8fc87`.
**Etappen är ännu inte standardkvalificerad.** `legacy` och
`library_merge_generations=False` är oförändrade standarder. Ingen aktivering,
insamling, faktarelease, Windowsuppgift eller ökad samtidighet ingår.

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

Försök att internera frysta modellvärden och supplied-field-metadata klarade
värde-/serializerprov men gav inte tillräcklig resident minnesmarginal.
De har tagits bort från slutdiffen. Provet på `fd15480` avbröts manuellt:
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

Alla levererade menyer i tabellen ger 988,32 kr, samma hash och audit PASS.
Instrumenterade och vanliga tider är olika metoder och utgör inte en
matchad latensjämförelse med varandra. Varje rad startar med tom appcache
och ny ägarstore. Varma upprepningar är inte nya kalla processprov.
Delmålet under 700 s har ännu inte uppnåtts.

Full GC efter varje sökspår kostade 129,24 s i `0f626bd`; i `193629f`
kostade den valda kombinationen 33,23 s. Legacy-förberedelserna kostade
196,65 s i slutprovet och finns kvar över samtliga elva publiceringar.
Även den kvarstående beräkningskostnaden ingår i 778,95 s.

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

Cachelägessekvensen på `193629f` pågår seriellt. Den vägrar starta om
föregående process inte klarar pris, hash, audit och 2,5 GiB. Varje omstart
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

De sex omstarts-/cacheförlustproven laddade elva certifikat och sökte om
noll publiceringar. De nya slutkontrollerna är fortfarande obligatoriska.
För varm planering ger max(5 000)/min(262) = **1,1344**, mediankvot 1,1159,
med tre varma anrop per storlek. Det klarar 1,25 i just denna profil/stad.
Varm 5 000-planering är också snabbare än de tre motsvarande upprepade
legacy-anropen. Första legacy-anropet ovan har varm offentlig disk och
jämförs inte som ett matchat kallt appcacheprov med 778,95 s.
Hela processens väggtid, inklusive inläsning, finns separat i
[cachelägesunderlaget](preparation-memory-20261024/cache-modes.json).

Tre nya ägarstore med varm offentlig disk återstår i den pågående
sekvensen. Därefter ligger ett separat resursprov för ordinarie
serialisering och överlappande syntetiskt PriceUniverse-versionsbyte.
Det mäter ingen meny/audit och ersätter inga matrisfall.

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

Kvar: minst tre kalla jämförbara prov per arm, färdig evidens för alla
cachelägen, aktuell legacy-jämförelse och 262-kvot, övriga pilotprofiler/
städer, versionsbyte/serialisering under minnestak och hela slutmatrisen.
Ingen generell total bytebudget för alla RAM-cacher har bevisats; marginalen
ovan gäller det enskilda frysta provet. Axfood-releasen omfattar fortsatt
103 verifierade dokument. Ingen full täckning, ny faktaaktivering eller
återfunnet historiskt Malmöarkiv påstås. Policyn förblir opt-in medan
någon grind återstår.
