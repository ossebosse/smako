# Verifiering av menyåtgärder 5–6, 2026-10-13

## 5. Återanvänd kampanjstruktur

Genomförd i kodcommit `334aeb2fa2a8` på `perf/menu-reuse-20261013`.
Driftsatt `ops-menu-reuse-334aeb2fa2a8` vid 2026-10-13T16:55:15.100387+00:00.

En begränsad strukturcache inom samma korgberäkning hittar kandidater som har
gruppkampanjer eller saknar ordinarie pris. Vanliga priskandidater behöver då
inte genomsökas på nytt. Endast oföränderliga kandidatfält återanvänds.
Aktuella erbjudanden och mängdtak läses vid varje kontroll; källvalidering,
gemensam kampanjberäkning, produktidentitet och medlemsvillkor går samma väg.
Föränderliga listor och andra kandidattyper beräknas direkt.

Cachen begränsas till 256 kandidatupler med sammanlagt 32 768 kandidatplatser
i indata. Den töms med den befintliga beräkningssessionen och vid dess vanliga
cachetömning.
Ingen sökgräns, kandidatpool, butiksmängd eller kvalitetsgräns har ändrats.
Exakt Decimal-aritmetik och skiljekriterier är oförändrade.

| Fryst fullständig meny | Före | Efter |
| --- | ---: | ---: |
| Kall | 395,434 s | 370,976 s |
| Varm | 2,989 s | 3,065 s |

Den kalla körningen var 6,2 % snabbare. Den varma körningen förbättrades inte.
Samma observationskod för möjlig återanvändning av butiksresultat ingår i
båda dessa mätningar; ingen profiler var påslagen. Detta är ett lokalt
före/efter-prov, inte en garanti om alla menyer eller en produktionsjämförelse.

Hela kallt respektive varmt PlanResponse är identiskt, undantaget enbart
`timings_seconds`, `timings_ms` och `span_statistics`. Alla operation_counters
är också separat jämförda. Det omfattar billigast, balanserad och varierad
meny, recept, inköpslistor, prisvillkor, kvalitet och sökning.

Provet använder fem middagar, två portioner och högst tre butiker, nätverk
avstängt, samma prisunderlag och klockan `2026-10-13T07:19:51+00:00`.
Prisartefaktens SHA-256:
`de54eafb81cf9bf47fd50a6a3e2a4d6929c88357b5e00b0c48009dbe98a0d2f6`.
Kall semantisk projektion:
`45e0bd4221027e741b12413ebb1f5e9e0d57431d93ad6c9a5dd3b52136bb8814`.

Uppmätt strukturindex: högst 246 poster och 8 733 kandidatplatser i indata;
samplad storlek för indexets egna behållare 57 664 byte (56,3 KiB).
Redan inlästa produkter är lånade referenser och ingår inte i detta tal.
Hela processens toppminne var cirka 1,62 GiB; indexmåttet är inte totalminnet.

202 unika riktade testfall är godkända: den samlade sviten med 201 fall,
därefter strukturtestens nio fall inklusive ett tillagt konfliktfall.
Tester omfattar ändrade mängdtak efter cacheträff, produkt-/butiks-/källidentitet,
snapshot och kampanjkonflikt, medlemspriser, prisrevision, exakta butikskorgar,
varierade menyer, personlig planering, minnesgränser och cachetömning.
Ruff, compileall och diff-kontroll är godkända.

## 6. Återanvänd delresultat för butikskombinationer

Verifierad genom en observerande cache som alltid kör originalberäkningen
och jämför resultat på varje möjlig träff. Ingen sådan cache har införts.

| Testad nyckel | Anrop | Träffar | Möjlig sparad beräkningstid |
| --- | ---: | ---: | ---: |
| Exakt identitet hos prisvektorer | 35 897 | 0 | 0 s |
| Exakt innehåll hos grupperade operander | 35 897 | 952 | 4,357 s |

Innehållsvarianten kostade 12,900 s för nycklar, uppslag och bokföring,
mer än den potentiellt sparade tiden. Den införs därför inte.
Resultaten på alla träffar var identiska. Hela menyresultatet och alla
sökräknare var också identiska med baslinjen, utom tidsstatistik.

Observern behöll additionsordning, butiksmängd, butiksgräns, vinnarmaskläge
och Decimal-kontext i jämförelsen. Innehållscachen hade högst 256 poster
och 363 464 byte räknad extra metadata, under gränsen 1 MiB.
Operandgrupper lånas från den befintliga sessionen och ingår inte i metadatatalet.
Identitetsvarianten nådde 100 poster under sin konservativt räknade gräns
på 1 MiB. Båda tömdes när beräkningssessionen eller dess cache byttes.

Detta avvisar de testade varianterna. Det bevisar inte att varje tänkbar
återanvändning av delresultat saknar värde. Den befintliga återanvändningen
av menyer och efterfrågeberäkningar är fortsatt aktiv.

## Drift och fler kommuner

Samma appkod används för befintliga och framtida kommuner. Punkt 5 kräver
ingen särskild kommunpatch och inga nya pris- eller insamlingsregler.
Den granskade produktionskandidaten innehåller endast
`backend/app/services/basket_optimizer.py` ovanpå den verifierade imagen
`sha256:3faff7284b503a940ec53c22f402422c45bc61a04bf7ebcbb5fe17b3e9970b64`.
Den separata ingrediensändringen `1518101` ingår inte.

Aktiveringen väntade på det befintliga operationslåset; appen ändrades först
när prisjobbet släppt låset. Lugn app, ny planbackup och byte av endast
appimage/BUILD_ID verifierades. Prismanifest, mounts, övrig miljö och
source/scheduler är bevarade. Samtliga tidigare 271 planrevisioner och
89 privata tillstånd är hashverifierat bevarade även efter slutproven.

| Liveprov | Tid | Resultat |
| --- | ---: | --- |
| Publik Malmö-meny, kall | 334.266 s | 17/17 kontroller, HTTP 201, identisk återläsning |
| Publik Malmö-meny, varm | 8.141 s | 17/17 kontroller, HTTP 201, identisk återläsning |
| Personlig meny | 62.6 s | Godkänd checkout-audit och identisk återläsning |

Kall och varm publik körning har samma prisversion och identiska recept,
korgar, butiksscenarier och kvalitetsresultat. Inga JavaScript-fel i proven.
Readiness för Lund och Malmö är HTTP 200 på rätt build.
Inga nya OOM-händelser under aktivering och slutprov. Den kalla menyn är
fortfarande långsam; liveprovet jämförs inte som ett prestandabevis med äldre
körningar på andra prisversioner.

## Evidens

Privata frysta menyer, loggar och observerkod finns i
`.local/menu-reuse-20261013/`. Sanerad maskinläsbar evidens finns i
[EVIDENCE.json](EVIDENCE.json). Produktionspaket och aktiveringsbevis hör
till `/opt/smako/evidence/ops-menu-reuse-334aeb2fa2a8/`.
Kör inte gamla aktiveringsskript på nytt.
