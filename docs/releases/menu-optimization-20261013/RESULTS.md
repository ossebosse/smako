# Menyberäkning: exakta optimeringar 2026-10-13

Driftsatt `ops-menu-7eab60a36fae` vid 2026-10-13T14:55:21.022696+00:00. Gren
`perf/menu-exact-20261013`. Endast tre granskade appfiler har lagts ovanpå den
verifierade produktionsimagen. Source/scheduler och prisunderlag är bevarade.
Den separata ingrediensändringen `1518101` är fortfarande inte driftsatt.

## Genomförda åtgärder

| Åtgärd | Varför resultatet bevaras |
| --- | --- |
| Återanvänd textnormalisering | Samma rena strängfunktion; högst 4 096 poster och 2 048 tecken per indata. Längre text beräknas direkt. Recept-ID beräknas från aktuellt innehåll. |
| Återanvänd innehålls-ID och profilegenskaper inom recepturvalet | Undviker upprepad hashning och profiluppslagning under samma anrop. Urvalsregler, stabil bas, dubblettkontroll, ordning och skiljekriterier är identiska. Mellan anrop läses innehållet på nytt. |
| Minska arbete i den innersta butiksjämförelsen | Gemensam följd av återstående operander skapas en gång per steg; direkt heltalsjämförelse ersätter upprepade max-anrop. Exakta butiksmasker, Decimal-priser och additionsordning bevaras. |
| Hantera tomma butikskombinationer | En saknad komplett korg ger ordinarie fel för ofullständig korg. Den tidigare singletonvägen kunde indexera en tom vektor och krascha. |

Samma appkod används för Lund, Malmö och framtida kommuner. Det finns inga
kommunvillkor i ändringarna och inget separat äldre menyflöde för nya kommuner.

## Mätning med frysta priser

| Körning | Före | Efter |
| --- | ---: | ---: |
| Kall menyberäkning | 440.016 s | 384.693 s |
| Samma begäran med varm cache | 3.204 s | 2.962 s |

Kall beräkning blev **12.6 % snabbare** i detta test, cirka
55.3 sekunder kortare. Det är ett lokalt
före/efter-prov med samma underlag, inte en garanti för alla menyer eller en
jämförelse av olika produktionsprisversioner. Tidsraderna har ingen profiler påslagen.
Baslinjens innehåll har dessutom reproducerats mot aktuell kod före ändringen.

Provet använder fem middagar, två portioner, högst tre butiker, samma fasta
klocka och nätverk avstängt. Prisartefaktens SHA-256:
`de54eafb81cf9bf47fd50a6a3e2a4d6929c88357b5e00b0c48009dbe98a0d2f6`.

**Hela planobjektet är identiskt** i kallt och varmt prov, med undantag enbart
för tids-/spanstatistik. Det omfattar billigast, balanserad och varierad meny,
recept, inköpslistor, prisvillkor, kvalitetskontroller och sökräknare.
Alla sökräknare är också separat jämförda. Kall semantisk projektion:
`45e0bd4221027e741b12413ebb1f5e9e0d57431d93ad6c9a5dd3b52136bb8814`.

Provet behåller 200 genererade recept, 179 i sökpoolen och beam width 30.
Ingen kandidatgräns, butiksmängd, prisregel eller kvalitetsgräns har sänkts.

## Verifiering

- 193 riktade tester godkända: bland annat uttömmande butiksjämförelser, saknade
  priser, vinnande butiksmasker, kampanjer, medlemspriser, prisrevision, varierade
  menyer och personlig planering. Ruff, compileall och diff-kontroll är gröna.
- 80 ytterligare direkta jämförelser med föregående recepturval ger samma hela
  resultat eller samma valideringsfel. Båda urvalslägen, dubbletter, gränser och
  ändrat nästlat receptinnehåll mellan anrop täcks.
- Separat jämförelse av butiksberäkningen: 1 350 kombinationer och 20 ingredienser,
  2 100 körningar med identiska svar, omväxlande före/efter. Medianerna var
  1,804 respektive 1,468 sekunder per 150 körningar. Detta är ett delprov,
  inte en ytterligare vinst att addera till helhetsmätningen.

## Verifierat i drift

| Prov | Tid | Utfall |
| --- | ---: | --- |
| Publik Malmö-meny, kall | 370.813 s | HTTP 201, 17/17 kontroller, identisk återläsning |
| Publik Malmö-meny, varm | 8.171 s | HTTP 201, 17/17 kontroller, identisk återläsning |
| Personlig meny, en middag/två portioner | 56.9 s | Godkänd checkout-audit och identisk återläsning |

Kall och varm publik körning har också identiska recept, inköpskorgar,
butiksscenarier och kvalitetsresultat på samma aktuella prisversion.
Inga JavaScript-fel i proven. Båda kommunerna har readiness HTTP 200 på rätt
build. Aktiveringen använde det befintliga operationslåset, verifierad lugn app,
ny planbackup och kontrollerat byte av endast appimage/BUILD_ID.
Alla 268 tidigare planrevisioner och 88 privata tillstånd är hashverifierat
bevarade även efter slutproven. Prismanifest, mounts och övrig miljö bevarades.
Inga nya OOM-händelser under denna driftsättning och verifiering.

## Åtgärder för fortsatt optimering

1. Undersök återanvändning av exakt kampanjstruktur inom en beräkning.
   Den gemensamma kampanjsökningen är fortfarande en betydande kostnad.
   Delade mängdtak, produktidentitet och medlemsvillkor måste verifieras innan
   en sådan cache kan tas i drift.
2. Undersök återanvändning av delresultat för återkommande butikskombinationer.
   Kräver både identiska prisresultat och en mätt minnesgräns; inför ingen
   obegränsad cache när fler kommuner tillkommer.

Dessa två är utredningspunkter, inte driftsatta ändringar. Den befintliga
återanvändningen av menyer för samma validerade prisversion är redan aktiv.
Första menyn är fortfarande långsam och mer arbete behövs för interaktiv svarstid.

## Spårbarhet

Kodcommits `7aa77aab2361` och `7eab60a36fae`. Aktiv image:
`sha256:3faff7284b503a940ec53c22f402422c45bc61a04bf7ebcbb5fe17b3e9970b64`. Maskinläsbar, sanerad evidens finns i
[EVIDENCE.json](EVIDENCE.json). Privata underlag ligger i
`.local/menu-optimization-20261013/`; fryst artefakt och äldre baslinje finns i
`.local/ops-followup-20261013/`. Serverns backup och aktiveringsbevis finns under
`/opt/smako/evidence/ops-menu-7eab60a36fae/`. Kör inte aktiveringsskript på nytt.
