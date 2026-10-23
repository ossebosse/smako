# Verifierad referens och separat Axfood-release

Genomförande av [arkitekturbeslutet](../CODEX-SOL-ARCHITECTURE-20261023.md).
Runtime integrerad och pushad till main: `c981d757b081f79f3926d9bcb6349c9918fcfb4d`.
De frysta profilparen kördes på `4b3f91a`; slutkodens 5 000-motexempel och
reader-image verifierades separat på `c981d75`. Katalogkö ingår sedan `f15b529`. Ingen produktionsaktivering eller ny timer.
Standarderna är fortsatt `legacy` och `library_merge_generations=False`.

## Sökning och förberedelse

`library_search_policy=smako-verified-reference-v1` använder den pinnade
262-receptsreferensens exakta värden och ursprungliga paketordning, separat från
förbättringsspåret. Referensmanifestets innehållshash är
`8a1188dfa0079aa79535afbc5e12cb8f6840fa30ee0e189b5d42e610905f0481`.

Förbättringen börjar med hela poolen, därefter befintliga geometriska försök inom
samma fasta budget: 4 096 utvärderingar, 32 768 förslag, 900 sekunders säkerhets-
avbrott per publicering (`full-pool-first-4096-v1`). Pilotens 1 024-budget lämnade
inte seedbanan; den bevaras som prototyp. Budgeten växer inte med receptantalet.

Arkivet har åtta platser. Referens och billigaste fortfarande giltiga tidigare
vinnare skyddas. Tidigare kandidater slutkontrolleras innan en vinnare skyddas;
en billig ogiltig kandidat kan inte tränga undan den. Alla möjliga vinnare går
genom accepts, aktuell gemensam korg och checkout-audit. Ny exakt kassasumma och
befintliga skiljeregler avgör. Budgetslut utan verifierad meny ger
`SEARCH_INCOMPLETE`. Inget globalt optimum utlovas; negativa kapacitetsbevis
avser bara den undersökta kvalificerade poolen.

Append-only-kedjan binder receptvärden, ordning, föregångare, kontext, vinnare,
audit och pengar. Kall miss återskapar varje saknat publicerat steg. Ändrat/
återkallat innehåll blir experiment. Förlorad härledd cache kan även återhämta
ägarens sparade levererade menyidentiteter från befintliga planrevisioner.
Gamla menyer återkvalificeras, utan återanvändning av gamla godkännanden/priser.

Små kvalificeringsposter, kompletta vyer och certifikat ligger i ägarens PlanStore.
Kontexten binder request, faktiskt lästa inställningar, PriceUniverse, faktavärden,
Axfood-manifest/parser/kod, prisdatum, butiksvy, medlemskap, portioner, lås och
effektivt skafferi/planledger. Optimistisk revisionskontroll är separat. Slutlig
gemensam audit körs också vid förberedd träff. Befintliga planjobb/admission används;
avbruten HTTP-väntan frigör inte en fortfarande tung worker.

PlanStore: totalt 64 MiB/4 096 artefakter, högst 8 MiB per post. Full budget
avvisar tillväxt och bevarar evidens. Sparad menyhistorik läses högst åtta rader
à 8 MiB; bara identiteter förs vidare. Rena receptuppslag: fyra vyer, vardera
högst 16 384 referenser/2 MiB. Privat data följer radering, återställningsspärr
och kontoflytt; gamla workers kan inte återskapa rader efter radering. Detta är
inte ett verifierat kapacitetslöfte för flera samtidiga ASGI-workers.

## Kontrollerat Axfood-underlag

Kända lokala, server- och arbetskopiearkiv inventerades utan fynd. Malmöfallet
361,81/340,64 är **inte reproducerat**. En deterministisk fixtur provar samma
sökmisstyp, utan anspråk på historiskt bevis.

Frysta kataloger gav 11 775 Willys-koder, SHA
`6bdc937ae11469405b8e3ecc3cf5a80700faa2d80aab8474aa191d7e4ca67f72`,
och 11 179 Hemköp-koder, SHA
`0b57b9fc85c5c857eb7671c37b07ff13171a1cca3f7adfe25ca9bb5485a6a3ed`.
Befintliga klienter/butiker användes under lokalt relälås och gemensamt serverlås,
högst 1/s respektive 0,1/s. Resultat: **103 verifierade dokument** (91 Willys,
12 Hemköp) och 18 negativa 404/410-svar. Täckningen är partiell.

Immutable v3-release:
`16410fb3d4e21746a75cb6c34072bb4bcc159c20ceefec2ba1187bb883ac233a`.
Den finns under `D:/smako-data/axfood-product-details/releases/` och, efter
hashkontroll i kandidatimage och atomisk publicering under driftlåset, under
`/srv/smako/data/axfood-product-details/releases/`. Ingen aktiv katalog eller
runtimevariabel skrevs. Råarkivets ZIP-SHA är
`4233658523507abe87cb2f5dbef6d15c9d5f45e3d53eb56a81b4d873933d1dac`.

Läsaren kräver status 200, exakt kod/kedja/URL/tid/payloadhash och säker sökväg.
Checksummevaliderad GTIN-8/12/13/14 nollfylls till 14 siffror för exakt jämförelse.
Saknad detalj-GTIN när katalogen har GTIN avvisas. Delning Hemköp→Willys kräver
samma kod och godkänd GTIN-bindning; egna avvisningar döljs inte. Deklarationer
skrivs inte över. Konflikter/återkallelser spärrar kvalificering. Näringsgränser
behålls som gränser och motsägande punktvärden spärras. Priser och katalogtid
ändras aldrig. Per projektion cachas högst 32 MiB/32 768 rådokumentsvar; nästa
projektion validerar filerna igen.

En verklig felklass hittades: linsprodukt `100046442_ST`, GTIN `7312787710182`,
hade identiska 349 kcal/1,8 g fett/51 g kolhydrat/26 g protein per 100 g men
olika källtexter för näringsbasen. Detta gav en falsk konflikt. Endast de två
befintliga projektorernas kända per-100-format jämställs nu; enhet, beredning,
överlappande värden och okända format kontrolleras fortfarande. Körningar med
den falska konflikten är förkastade och bevarade som mellanunderlag.

Lund: 175 egna + 106 delade katalogträffar, 4 verkliga konfliktprodukter,
30 195 utan dokument. Malmö: 366 + 255 träffar, 7 konflikter, 70 465 utan dokument.
Träffarna räknar butiksprodukter, inte unika rådokument.

`--approved-snapshot` läser kön direkt från aktuell godkänd komplett katalogs
exakta koder för vald kedja/butik. En ny publicering gör nya koder tillgängliga
utan parallell ködatabas; avlistade koder faller bort. Vyn begränsas till
100 000 säkra koder. Befintlig journal skiljer verifierat, 30-dygnsomprövning,
404/410 efter sju dygn, retry högst tre gånger, permanenta fel och åtkomststopp.
429/challenge stoppar körningen. Fel förnyar inte LKG:s observationstid.
Inget automatiskt insamlingsschema har installerats.

## Verifiering och standardbeslut

**Standardbyte stoppat:** slutkoden `c981d75` ger 992,22 kr i Malmö/fördelning
vid 5 000 recept, mot gamla sökningens 988,32 kr. Alla tre körningar per policy
har samma utfall och godkänd checkout-audit. Skillnaden är **+3,90 kr**.
Referensen vid 262 är 996,22 kr; publiceringskedjan förbättras först vid 4 000
till 992,22 och behåller sedan vinnaren. Referens-/föregångarkontraktet räcker
således inte för empirisk dominans över gamla sökningen på hela biblioteket.

[Motexemplet](verified-reference-axfood-20261023/failed-gate.json) binder kod,
bibliotek, priser, fakta, request, klocka, utfall, audit, minne och kommandokvitto.
Två CPU, 3 GiB inklusive swapgräns, nät av, en isolerad worker:

| Policy | Kr, alla tre | Tid, tre anrop (s) | Högsta observerade RSS |
| --- | ---: | --- | ---: |
| Legacy | 988,32 | 249,481 / 101,766 / 101,605 | 2 918 944 768 byte |
| Verifierad referens | 992,22 | 533,606 / 8,422 / 8,341 | 3 043 659 776 byte |

Cgroup-peak nådde gränsen **3 221 225 472 byte**, OOMKilled=false och exit 0.
Önskad marginal på 2,5 GiB saknas. Ingen ökad samtidighet är motiverad.
Första nya anropet har privat cachemiss men redan varm offentlig process från
legacy; det är inte ett separat kallprocess-/kall-diskprov. Två upprepningar
är förberedda menyträffar. Kö är inte uppmätt i detta ensamma workerprov.

Fullmatrisens [252 celler](verified-reference-axfood-20261023/status.json) har
explicit status: **30 mätta, 222 ej körda**. De ej körda cellerna, inklusive
v5 och resterande storlekar/faktaarmar, har inte godkänts. Standardkvalificeringen
stoppades vid det konkreta prisfelet. Separat kall disk, ny process med varm disk
och återhämtning efter RAM-eviction återstår. Inga fulla skalnings-, latens- eller
godtyckliga kallstarts-/cachetillståndsgarantier är empiriskt verifierade.
`legacy` och `library_merge_generations=False` förblir standard; v1 är opt-in.

### Frysta faktapar och separat algoritmjämförelse

`4b3f91a`, metodhash
`dc01edcf7446d958c33f6f114db41843a7f8f3cbd5a63b81311740852540a87b`:
två städer × sju profiler × tre upprepningar. Priser, request och klocka är
byteidentiska mellan kontroll och berikning. Varje arm kör samma plannerkod.
Gamla menyidentiteter återauditeras mot nya fakta och kan konkurrera; inget gammalt
pris kopieras. Alla 14 faktapar behöll kassasumma och utfall: 78 giltiga menyer
och sex oförändrat blockerade Malmö/vegan-anrop. Det blockerade utfallet är inte
ett bevis på global omöjlighet.

Samma berikade fakta jämfördes därefter mellan legacy och v1. Tabellen visar
identiskt resultat i alla tre upprepningar per cell. Totalt kördes 126 anrop
över kontroll/legacy och berikad/legacy/v1: 117 PASS och nio BLOCKED.

| Stad/profil | Legacy på berikade fakta (kr) | V1 på samma fakta (kr) |
| --- | ---: | ---: |
| Lund/Standard | 487,85 | 487,85 |
| Lund/Protein40 | 775,32 | 775,32 |
| Lund/Alla makron | 802,68 | 796,28 |
| Lund/Vegan | 347,90 | 335,35 |
| Lund/Fördelning | 761,45 | 761,45 |
| Lund/Organic-share | 314,24 | 314,24 |
| Lund/Frukost/mellanmål/vikt | 64,06 | 64,06 |
| Malmö/Standard | 511,46 | 492,15 |
| Malmö/Protein40 | 1000,86 | 1000,86 |
| Malmö/Alla makron | 1000,86 | 1000,86 |
| Malmö/Vegan | BLOCKED | BLOCKED |
| Malmö/Fördelning | 996,22 | 996,22 |
| Malmö/Organic-share | 321,16 | 321,16 |
| Malmö/Frukost/mellanmål/vikt | 53,16 | 53,16 |

Slutkodens senare ändringar gäller katalogkön, källans `<`/`>`-representation,
felaktig precision och korrupt cache-JSON. Sökalgoritmen/budgeten är oförändrad
sedan profilprovet. Färska projektioner i den exakta slutimagen gav identiska
faktavärden/faktaversioner i båda städerna. Profilparen ovan är Windowsprov,
inte bevis för serverlatens eller cgroup-minne.

### CI och tidigare pilot

[Full app-CI 40019613139](https://github.com/ossebosse/smako/actions/runs/40019613139)
på `c981d75`: **3 094 PASS, 10 XFAIL, 53 SKIP**, inklusive Chromium/WebKit.
Riktade source-/arkiv-/kö-/integritetsprov, Ruff och compileall passerar.
Tidigare full Windows-CI på `4531729`: 3 116 PASS, 10 XFAIL, 4 SKIP,
47 browserrelaterade fall. SKIP för datakrävande historiska prov innebär inte
att deras acceptansgrind passerat.

Pilot `4531729` på originalfakta, Malmö 262, tre upprepningar per policy:
standard 511,46→492,15, fördelning 996,22→996,22, organic-share 321,16→321,16.
Varm v1 tog cirka 7,3–8,1 s. Vid 5 000 gav standard 511,46→492,15 och samma
fördelningsfel som slutkoden. Dessa pilotfiler/kommandon bevaras separat.
Organic-share/preparation vid 5 000 avbröts manuellt efter tre av elva hållbara
certifikat för att prioritera faktareleaseprovet: exit 137, OOMKilled=false.
Det är varken en slutförd kall mätning eller en OOM. Tid/delresultat bevaras.

## Separat, ännu inaktiv Axfood-release

[Konkret releaseförslag](../releases/axfood-reader-20261023/PROPOSED.md), med
[manifest](../releases/axfood-reader-20261023/manifest.json), pinnad Compose-fil
och rollback, är färdigt. Image:

`sha256:92be15f2efa053f7c85bc398782d10618e9e1d06dbef24625528862753e6ffbf`

BUILD_ID `source-ops-c981d757b081`, paket
`smako-source-ops-c981d757b081.zip`, SHA
`d31850a6df5862a45ca8b5566d821406875408465ea13ac2b5574370381cdd6a`.
Exakt tre runtimefiler ändras ovanpå aktiv `c253cbd9ef93`; konfigurationen
verifierades. Planner, bibliotek, schema, ICA och scheduler ingår inte.

[Native jämförelsen](verified-reference-axfood-20261023/native-reader.json)
använder bildens **222 recept**, inte en överlagrad 262-planner: 14 profilpar,
tre upprepningar, 78 PASS och sex oförändrat BLOCKED. Alla kassasummor/utfall
behölls. De 13 giltiga gamla menyidentiteterna var stabila över upprepningarna
och klarade varsin separat ny audit. Den auditen ändrade inte native-resultatet.
Återanvändning från reader-image `2f2f8b8` binds till byteidentisk native planner,
modeller/bibliotek och exakt lika färsk faktaprojektion i slutimagen; endast
reader/projektor skiljer mellan dessa två images.

Production-klon bas→kandidat→rollback gav readiness 200 för båda städerna i
alla tre steg och identiska prispekare före/efter. Tillfälliga databaser och
syntetiska nycklar användes; inga produktionsdatabaser monterades. Källfaktas
bakgrundspreparering var avstängd i readiness-klonen och verifierades som färsk
projektion separat. Fullt produktions-prewarm/total cachekapacitet är därmed
inte bevisad. Befintliga aging/degraded-varningar behölls; inga krav sänktes.

Befintlig lagringsretention kördes under driftlåset före imagebygget och
bevarade återställningsgolvet. Axfood-retention har kodstöd; register/env/timer
har inte installerats. Releaseförslaget beskriver skydd av aktiv/rollback/evidens.
Produktionens image, schema och Axfood-miljövärde är oförändrade.

Rådata, full checkout, kommandon, privata miljöinventarier och körloggar ligger
utanför Git i `.local/sol-architecture-20261023` och serverns
`/opt/smako/evidence/sol-architecture-20261023`. Kodarkiv `c981d75` har SHA
`fcc83416e966bba0b1c9087d1cfa871bac8a9b02986a6305831c9ac847e75017`.
Originaldata och förkastade mellanunderlag är bevarade. Den första metadata-
kopieringen från privat serverkatalog nekades; kvittot hämtades därefter med
skrivskyddad sudo-läsning. Imagen byggdes inte om och provutfallet ändrades inte.

Ett produktionsbyte eller nytt insamlingsschema kräver separat driftbeslut
enligt BETA.md. Principgodkännandet av berikningen efterfrågas inte igen.
