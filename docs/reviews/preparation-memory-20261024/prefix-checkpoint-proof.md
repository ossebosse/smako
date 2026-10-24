# Checkpoint för legacy-prefix: villkor och likvärdighet

Kandidat på `perf/legacy-prefix-checkpoints-20261024`, efter den integrerade
förberedelseoptimeringen i PR #9. Fryst fullbiblioteksjämförelse passerar;
resurskvalificering pågår. Ingen standardväxling.

`LibraryPrefixCheckpoint` ägs av ett enda `_search_verified_reference`-anrop.
Den kopplas bara till legacy-spåret. Referens, förbättring, certifikat och
ägarhistorik använder sina tidigare vägar. Standardklasser för planner,
service, korgoptimerare, kalkylator och normalizer krävs; injicerade vägar
behåller oberoende anrop.

Induktionsvillkoret är ett fast snapshotsammanhang och samma rena callbacks.
Det gäller de ordinarie callbacks som skapas en gång i `_create`; de får inte
ändra kvalificeringsresultaten eller de privata beräkningsindata under batchen.
Ny kontext/callback, nya initiala resultatobjekt eller ett ändrat ordnat
slot-/receptprefix ger ett vanligt fullständigt anrop. Ny förfrågan får alltid
en ny checkpoint. Nyckeln omfattar slot-ID, dag, måltidstyp och receptets
exakta värdesnapshot, inklusive mängder, instruktioner och beredningsformer.

Efter varje gemensam kohort är substitueringens incumbent, föregående pool,
sekundär incumbent och 256-posters LRU samma som i en oberoende körning från
början. Nästa övergång har därför samma indata och samma förslagsordning.
Checkpointen tas **före terminal förfining**. Den nya publiceringen återställer
även LRU-ordningen från denna punkt; tidigare terminala cacheträffar får inte
ändra vilka förslag som ryms i de fasta utvärderingsgränserna. Rena receptnycklar
kan beräknas om, och träffräknarens offset påverkar bara diagnostik.

Varje begärd publicering gör fortfarande sin egen terminala förfining.
Den färdiga kandidaten konkurrerar sedan genom aktuell checkout/audit.
Färdiga publiceringar hoppas inte över. Föregående publicerings vinnare används
inte som ny seed. Checkpointen innehåller ingen ny approval och sparas inte.
Exhaustiv sökning, arkiverade prefix och checkpoint-prober använder sin tidigare
oberoende väg. En enda checkpoint behåller högst det befintliga LRU-innehållet;
övergående kopiering av LRU och prefixsignatur ska mätas under resursgränsen.

Permanenta syntetiska prov jämför varje avslutat prefix mot en oberoende körning
för fasta slumpade, icke-additiva pristabeller, sekundärt mål, par-/joint-gränser
och begränsad substitutionsordning. Ändrade mängder, instruktioner, slotvärden,
ordning, kontext, initiala kvalificeringsobjekt och kortare prefix måste bygga om.

Ett separat motexempel skiljer metoden från en vinnarseed: AAA kostar 10,
terminal förfining ger ABB för 4. Vid nästa utökning når den ursprungliga
substitutionsbanan CCC för 1, medan ABB som seed blir kvar på 4. Checkpointen
behåller AAA före förfining och måste ge samma CCC som det oberoende anropet.
Detta är algoritmevidens; först en fryst oraclejämförelse per publicering samt
nya latens-/minnesprov kan kvalificera den verkliga körningen.

Den frysta oraclen på `ea4bb08f1ace5a854901a81d08ce7facfa11b383` jämförde
alla elva publiceringar i Malmö/fördelning/5 000 mot nystartade legacy-
söktillstånd, med exakt samma initialresultat och callbacks. Samtliga
ordnade slot-/receptvärden och hela serialiserade korgar var identiska.
Slutplanen gav 988,32 kr, förväntad semantisk hash och audit PASS.
Den återupptagna vägen utförde **3 041** utvärderingar jämfört med
**9 517** oberoende, och återupptog sammanlagt 165 tidigare kohorter.
Det dubbla oraclearbetets tid/minne kvalificerar ingen resurscell.
Se [alla jämförelser](prefix-oracle.json) och wrappern `prefix_oracle_entry.py`.
