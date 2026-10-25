# Slutrapport: förberedelsekostnad, minne och avgränsad verifiering

Leveransen avslutades den 25 oktober 2026 på beställarens begäran:
”Skippa 5000 testen. Vi har tillräckligt med underlag”. Den pågående
5 000-körningen och återstående matrissekvens är stoppade. Inga ytterligare
benchmarkkörningar eller automatiska återstarter är planerade.

Kodförbättringarna är integrerade i main genom PR #9 och #10. Appfilerna är
identiska med uppmätt runtime `eeda184926f02e73ab76e71e50c740e9dcb01b02`.
Denna slutleverans samlar evidens och avgränsningar i
[PR #11](https://github.com/ossebosse/smako/pull/11).
**Hela standardgrinden är inte verifierad.** Standarderna är fortsatt
`library_search_policy=legacy` och `library_merge_generations=False`.
Ingen produktionsaktivering, insamling, aktiv fakta-/prisversion eller
driftuppgift ändrades.

## Vad som förbättrades

Exakt nycklade delberäkningar och verifierad återanvändning av legacy-prefix
minskar upprepad sökning mellan publiceringar. Oberoende slutkontroll och
aktuell audit behålls. Kompaktare immutabla produkt-/modellvärden, avgränsade
cacher och radvis native-validerad kataloginläsning minskar samtidiga grafer
och stora JSON-buffertar. Giltig referens, diskcertifikat och ägarhistorik
behålls; en tidigare kassasumma blir inte ett nytt godkännande.

| Matchat Malmö/fördelning/5 000 | Före | Efter | Utfall |
| --- | --- | --- | --- |
| Första plananrop, median av tre tomma appcache-/ägarprocesser | 881,31 s | 662,83 s | 24,79 % kortare |
| Högsta slutliga cgroup-peak i dessa kalla processer | 2,818 GiB | 1,882 GiB | 33,20 % lägre |
| Instrumenterat plananrop | 858,60 s | 666,03 s | Delmålet under 700 s uppnått |
| Legacy-förberedelse i fasprofilen | 200,30 s / 9 517 utvärderingar | 61,16 s / 3 041 utvärderingar | Alla elva kandidatpriser identiska |

Alla dessa planresultat ger 988,32 kr med samma semantiska menyhash och
godkänd aktuell audit. Mätningarna använder samma frysta indata och seriell
två-CPU-/3-GiB-gräns. OS-diskcache är okontrollerad. Vanliga och instrumenterade
tider jämförs var för sig; processernas olika antal anrop blandas inte till
en processmedian.

Kostnader återstår: budgeterad förbättring tar 437,33 s i fasprofilen, och
inläsningsmedianen ökar från 33,12 till 47,70 s. Det högsta slutminnet bland
redovisade aktuella acceptansprov är HTTP-provets 2,467 GiB, bara cirka
34,15 MiB under 2,5-GiB-målet. Uppmätta marginaler gäller de frysta proven;
ingen generell total bytebudget för alla möjliga RAM-cacher har bevisats.

## Vad som verifierades

- Hela 48-cellspiloten: båda städerna och faktaarmarna, 262/5 000,
  standard/fördelning/organic-share, 192 auditgodkända anrop. Alla pilotens
  pris-, minnes- och varmgrindar passerar. Högsta varmkvot är 1,24054.
- Totalt **91 av 252** fullständiga cellmätningar, inklusive piloten:
  **84 levererade menyceller / 336 auditgodkända anrop**, samt **sju separat
  blockerade veganceller / 28 observationer** med bevarad `SEARCH_BLOCKED`-kod
  och steg. De blockerade observationerna bevisar ingen global omöjlighet.
- Alla 84 levererade cellers fyra priser och menyhashar är stabila.
  De 224 tillgängliga kontrollerna av upprepning, kontext, prisgränser,
  blockeringssignatur och varm tid passerar utan registrerade avvikelser.
- Tretton cachelägesprocesser, matchade före-/efterprov och fasprofil,
  tre ordinarie överlappande katalog-/serialiseringsprov, HTTP/Save/GET,
  ägargränser, köat/aktivt avbrott och tre historikåterhämtningar passerar.
  Alla tolv ankomstprov för nya sparade menyidentiteter passerar utan
  omsökning av de elva färdiga publiceringarna.
- Axfoods godkända partiella 103-dokumentsrelease är projicerad och provad
  för båda städerna: 91 Willys, tolv Hemköp och 18 negativa svar. Priser,
  begäran och testklocka bevaras. Full källtäckning eller ett återfunnet
  historiskt Malmöarkiv påstås inte.
- Relevanta regressionstester, Ruff och compileall passerar. Full
  [CI på `2dc5020`](https://github.com/ossebosse/smako/actions/runs/40183481276)
  passerar inklusive Chromium/WebKit före avslutande dokumentation.
  Slutleveransens checkar finns i [PR #11](https://github.com/ossebosse/smako/pull/11/checks).

## Varför hela uppdraget inte genomfördes

Fullmatrisen kräver 252 uttryckliga cellidentiteter med fyra observationer
vardera: 1 008 anrop över sju profiler, båda städerna, två faktaarmar,
biblioteksstorlekar och policyer. Varje ny personlig kontext måste fortfarande
förbereda och kontrollera de publicerade föregångarna för att bevara
prisgarantin. Biblioteksdelar eller legacy-spår får därför inte hoppas över
för att korta mätningen. Flera tidigare uppmätta minnesfel behövde också
rättas och omprovas innan den godkända piloten kunde köras.

Den kvarvarande kalla kostnaden är hög trots förbättringarna. Organic-share
vid Malmö/original tar 21,10 minuter vid 1 000 och 33,13 minuter vid 2 000;
pilotens första 5 000-anrop tar 66,54 minuter. Protein40 vid 2 000 tar
14,60 minuter första gången. Oförändrad seriell två-CPU-/3-GiB-körning ger
därför en omfattande total körtid. Beställaren valde att avsluta ytterligare
mätningar och leverera på befintligt underlag.

**161 cellidentiteter saknar fullständig mätning**, även i återstående
stads-/faktaarmar vid mindre storlekar. **299 korsjämförelser saknar ännu
underlag.** De återstående profilernas 5 000-varmgrindar och den fullständiga
standardkvalificeringen kan därför inte godkännas. Ingen ny pris-, utfalls-
eller minnesregression har registrerats i de stängda grupperna.

Den avbrutna 5 000-gruppen hann ge fyra protein40/legacy-observationer för
912,72 kr med audit PASS. V1 avbröts under första anropet. Gruppen saknar
ordinarie slutligt process-/resurskvitto och tillför **noll** fullständigt
uppmätta celler. Docker-exit 137 följer det beställda stoppet efter 20 sekunder;
`OOMKilled=false`. Den observerade minnespeaken före stopp är ingen ersättning
för ett slutkvitto. [Stoppkvittot](preparation-memory-20261024/user-requested-stop.json)
och [avslutsstatusen](preparation-memory-20261024/completion-status.json) bevarar detta.

## Bevarat underlag

[Detaljrapporten](preparation-memory-20261024.md) innehåller ändringar,
fasresultat, cachelägen, exakta kommandon och begränsningar.
[Cellinventeringen](preparation-memory-20261024/cells.json),
[fullmatrisstatusen](preparation-memory-20261024/full-matrix-current.json) och
[den separata korsgranskningen](preparation-memory-20261024/cross-cell-review-current.json)
markerar leveransen avslutad på begäran, med full kvalificering falsk och
inga fortsatta körningar planerade.

Det sista slutna arkivet innehåller 259 verifierade metadatafiler, SHA-256
`3aeaa7292c6759602b50862b4c0e009b41505db5e1e56ef1dd1dee160a6af640`.
Ett separat fyrfilersarkiv bevarar den avbrutna gruppens uttryckliga metadata,
SHA-256 `bedc75ebda50bd359fe4a508ccf9c6f9815f5de04afe70076dcb4867d78c1f02`.
Båda finns hashverifierade lokalt och på evidensvärden. Ägarstore, privata
cacher och databaser ingår inte i de exporterade metadataarkiven.
