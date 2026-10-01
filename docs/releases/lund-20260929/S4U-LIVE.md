# Avslutad obevakad livekörning 2026-10-01

**Obevakad verklig Willys-hämtning och leverans: PASS** för exakt körning
`20261001T074423Z`. Operatören startade den registrerade isolerade uppgiften.
Denna granskning läste befintliga loggar, artefakter, SQLite och serving-status;
ingen uppgift, insamling, import, publicering eller omstart utfördes igen.
[Maskinläsbara bevis och filhashar](S4U-LIVE-EVIDENCE.json) hör till denna
körning och dess nya artefakt, inte tidigare replayresultat.

## Körkontext och startgräns

- Task Scheduler: `Smako Lund bdc9 S4U isolated verification`, start
  **09:44:23**, slut enligt observatören **10:33:32 svensk tid** (07:44:23–08:33:32 UTC).
  Återläst `Ready`, LastTaskResult **0 / 0x00000000**, samma LastRunTime.
- Observatörens faktiska identitet är det lokala kontot `ossia`,
  **session 0**, `interactive=false`. Principalens serialiserade
  `CimInstanceProperties` visar UserId `ossia`, LogonType 2 (**S4U**) och
  RunLevel 0 (**Limited**); samma värden finns i den registrerade uppgiften.
  CIM-klassens null-defaultvärden är inte körningens principalvärden.
- Operational-eventloggen var avstängd och har inte aktiverats. Bedömningen
  bygger på körningens identitetsfil, uppgiftsdefinition och Scheduler-resultat,
  inte på påstådda eventloggposter som saknas.
- Observatörens SHA-256 `66551d59…` och startkvittots SHA-256 `2f50da3c…`
  är oförändrade mot förkontrollen. Kvitto kontrollerat 07:25:03 UTC, giltigt
  till 09:25:03 UTC. Den oförändrade observatören kontrollerar giltigheten
  **före** att skriva startkontexten 07:44:23 UTC. Även slutförandet inträffade
  före utgången. Ingen ny giltighet har skrivits vid denna granskning.
- Verkligt versionsbundet paket: `D:\smako-local-relay\releases\bdc9f7df4170`,
  commit `bdc9f7df417084641d0a712e3dad188dad1ad7d4`. Samtliga **624 filer**
  kontrollerades åter med rena hash-läsningar och matchar paketmanifestet.
  Ingen policyöverstyrning eller ändring av säkerhetspolicy gjordes.

## Samma källa genom hela kedjan

| Steg | UTC 2026-10-01 | Bevis och utfall |
| --- | --- | --- |
| Reläets start | 07:44:27 | `task_start`, sedan `collection_start`; ingen not_due/replay-gren |
| Insamling | 07:44:35–08:21:47 | Ny snapshot `049d1ce3a2e546f3922cbadd89e3d73f`, healthy |
| Lokal validering | 08:23:20 | Ny artefakt, komplett originalkälla, hash/tider/butik/schema verifierade |
| SSH-leverans | klar 08:23:58 | BatchMode, separat testinbox, `upload_pass`; exakt samma bytes/hash på mottagaren |
| Mottagarimport | 08:24:32–08:27:46 | Ny snapshot `293e153376ae45bbbf114c0cbb5790d3`, succeeded; validerad 08:27:46 |
| Promotion | 08:28:17 | `promoted`, aktiv snapshot, exakt en import med artefakthashen |
| Ordinarie publicering/reload | 08:28:17–08:33:29 | Operationslås, `source_relay_import`, refresh exit 0, runner exit 0; reload `changed=true` |
| Beständigt kvitto | 08:33:30 | Atomiskt `last-success.json` med samma hash, import-ID och universe-ID |
| Slutförande | 08:33:31–08:33:32 | `task_success`, `task_end`, observatör exit 0, Scheduler exit 0 |

Artefakt: `049d1ce3a2e546f3922cbadd89e3d73f.smako-source`, **3 948 272 byte**,
SHA-256 **`5b1a2b6b01ba65338f224cdd6af432c8178f214b1612d5d54ec400ffe8f9362a`**.
Kontrakt `smako-source-snapshot-v1`, verklig kommunbindning 1281,
`willys-parser-v3`, `product-normalizer-v3-recipe-taxonomy`.
De två onlinekontexterna är **2176 Willys Lund** och **2354 Willys Lund Nova**.
Ingen fysisk hyllpristäckning påstås genom dessa onlinebaser.

**1 255 verkliga Willys-anrop**, varav **1 253 HTTP 200 och 2 HTTP 500**;
0 challenges. Collectorns snävare mätning 1 254 utelämnar den inledande
kommunala butikshämtningen. De 1 250 sparade råsvaren består av 1 243
katalogsidor, två kategoriträd, två butiksaktiveringar, två kontextkontroller
och en butikslista. Två lyckade CSRF-anrop används endast i minnet; tillsammans
med den inledande butikshämtningen och två misslyckade försök förklarar detta
skillnaden mellan 1 250 rådokument och 1 255 nätanrop. Inga token/cookies
har kopierats till rapporten. Insamlingen använder HTTP-klienten; ingen
webbläsare krävs eller har verifierats genom detta prov.

De två HTTP 500-svaren är redovisade övergående transportfel, inte dolda
slutfel: ordinarie retryflöde återhämtade hämtningen. Båda katalogerna är
fullständiga enligt råmaterialets oberoende completion-kontroll
(447/447 respektive 432/432 kategorier, 658 respektive 585 sidor).
0 parserfel och 0 karantänsatta produktposter. Exakta URL:er/tider för de
två misslyckade försöken finns inte i det beständiga detaljunderlaget;
ingen sådan precision påstås här.

**18 939 butiksspecifika produktposter**: 10 266 + 8 673; manifestets
`product_count` är **10 496 distinkta produktidentiteter** över butikerna.
Alla 1 250 råpayloaders hash, hämtningstid, butik och dokumenttyp matchar
artefakten och mottagarens import. Observationer **07:44:37.057437–08:15:10.740536 UTC**
är bevarade; import-/byggtid har inte ersatt källtid. Mottagarens normala
artefaktvaliderare kördes läsande igen, utan import eller nätanrop.
Kedjans PASS är inte ett generellt närings-/mängdgodkännande: importmetrics
redovisar 663 poster med okänd försäljningsmodell och 18 264 med
förpackningsmängd. Ingen kvalificering eller planacceptans har mildrats.

## Faktisk serving och resultatkoder

Runnerns kvitto visar reload från förkontrollens `a69651bd…` till:

- Universe: **`price-universe:19cd1da8ee3880e446d447c2141f9675f13afc5a26705709e67789e58c4e2671`**.
- Aktivt manifests SHA-256: `330a446eb382e2845c1270fbe8be6379ce64331e002a54a5cb655efd5beef2cc`.
- Förberedd artefakts SHA-256: `2912262e77e83f7e33356cf6ae5f2f5b900fc6e0f2064404fad8495e21e0f0bb`.
- Faktiskt HTTP-serving: **44 066 råproduktposter**, 2 246 efter pruning,
  samma universe-ID och snapshotlista som den hashverifierade aktiva filen.
- **18 760 serverade poster från just denna import** (10 170 + 8 590).
  Deras provenance anger OWN/catalog/online_store/LOCAL_RELAY och import-ID;
  varje observationstid finns i butikens ursprungliga råsvar. Återstående
  Willys-poster från frivilliga erbjudandekanaler räknas inte som denna import.

Detta nya manifest är skilt från **42 491** (profilprov), **44 132**
(tidigare driftprov) och **44 080** (förkontroll). De gamla resultaten har
inte räknats om som nya prov.

Resultatkodskedjan har granskats: installerat startskript vidarebefordrar
Python-reläets kod, observatören vidarebefordrar startskriptets `$LASTEXITCODE`.
Reläet kräver lyckad SSH-process och mottagarens aktiveringsbekräftelse innan
framgångskvitto och `task_success` skrivs. **I denna körning** är även mottagarens
refresh/runner-koder 0, med fullbordad reload verifierad genom ordinarie HTTP.
Så observatörens 0 återger denna körnings verkliga framgång. Generellt kan
mottagaren acceptera även degraded=2 och reläet har not_due/replay-grenar;
därför är en godtycklig framtida exit 0 fortfarande inte ensam tillräckligt bevis.
Den kvarliggande `progress.json` är bara senaste periodiska checkpoint
(1 200 anrop), inte slutresultat; slutmetrics/logg/kvittot ovan är auktoritativa.

## Avgränsning

Serverbilden är fortsatt `sha256:2f81344208e05cbc57d16fa74a73c97b26bc729859936ca5d96ab150579fe221`
i `smako-lund-ops-s4u`, endast separat `s4u-data:/work`, ingen produktionsinbox.
Produktionsuppgiftens XML SHA-256 är fortsatt
`c781d10ce504aa172d8006f365f7ad167ac2ca23688fcf629d1b0851c5ff6755`.
Ingen uppgift, policy, säkerhetsinställning eller produktion ändrades.

| Kontroll | Status |
| --- | --- |
| Obemannad livehämtning och leverans i S4U/Limited | **PASS**, denna körning |
| Ny återleverans/not_due efter denna körning | **EJ PRÖVAD**, inget nytt jobb startat |
| Samordnat versionsbyte och köövergång | **BLOCKERAD**, tidigare blockerare kvar |
| Säker planläsning efter återgång till faktisk produktionsbild | **BLOCKERAD**, tidigare kompatibilitetsfel kvar |

**Samlad release: INTE REDO.** S4U-spärren är stängd för den verifierade
konfigurationen; versionsövergång och säker återgång är separata kontroller.
Femkällorspolicy, serveraktivering och byte av aktiv Windows-uppgift är
fortfarande tre separata, ej fattade produktionsbeslut.
