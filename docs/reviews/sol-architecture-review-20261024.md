# Oberoende granskning av Sols implementation, 2026-10-24

Granskat intervall: arkitekturbeslut `e527a3c` till main `ac0bbfe`.
Runtime är `c981d75`; efterföljande commit är dokumentation.

Bedömning: bra grund med separat referensspår, slutlig kassakontroll,
ägarbundna artefakter, oförändrat standardläge och spårbar Axfood-evidens.
**Ändringarna är inte färdiga för standardbyte.** Två ytterligare kodfel
reproducerades i denna granskning. Sols redan rapporterade pris- och
resursproblem kvarstår. Ingen appkod eller driftkonfiguration har ändrats
av granskningen.

## Nya fynd som Sol ska rätta

### P1: Förberedd meny ignorerar en nytillkommen billigare levererad meny

`backend/app/services/personal_planner.py:3013–3015` binder den snabba
cachevägen till `self.previous_menus`, men inte till ägarens sparade
menyhistorik. Vanliga API-anrop lämnar `previous_menus` tom. När en billigare
meny därefter sparats kan samma kontext därför fortsätta returnera sin gamla,
dyrare cachevinnare. Den ordinarie certifikatvägen har samma lucka vid
2789–2804: den läser `recent_menu_records(context)` men hoppar över dessa
kandidater när certifikatet redan finns och inget explicit argument skickats.

Offline-reproduktion med repoets riktiga recept-/korg-/auditkod och
syntetiska produktfakta:

1. Låt första sökningen föreslå en giltig meny för 323,80 kr och spara dess
   normala certifikat. Endast sökförslaget är adversariellt i fixturen.
2. Spara en annan färdig meny för 283,90 kr i samma ägares PlanStore.
   Båda planerna har exakt samma `verified_reference.context`. Den billigare
   menyn klarar dessutom en ny oberoende checkout med samma pris.
3. Nästa vanliga anrop ger `prepared_menu_hit=True` och **323,80 kr**.

Detta är en ny reproducerad felklass, inte en uppmätt prisregression i en
verklig stadsprofil. Den bryter ändå arkitekturens kontrakt om att behålla
en tidigare levererad, fortfarande giltig billigare meny.

Rättning: bind cachevalet till den relevanta ägarbundna historiken eller
en beständig version av mängden konkurrerande menyer. Samla och reauditera
nya identiteter även vid förberedd träff och full certifikatträff; uppdatera
vinnaren först efter kassakontroll. Försök inte lösa det genom att bara
ta bort `menu_view`: den andra cachevägen måste också korrigeras. Bevara
nuvarande ägar-/raderingsgränser och låt inte en obehörig historik bli en
kandidat. Lägg regressionsprov för båda träffvägarna och en ogiltig ny meny.

### P2: Godkänd katalog och föregående Axfood-release går inte att kombinera

`scripts/fetch_axfood_product_details.py:106–107` skriver katalogbeviset med
`atomic_bytes` under den nya stagingkatalogen. Det skapar katalogen. Vid
`--base-release` kontrollerar samma körning sedan på 121–122 att staging
**inte** finns och avbryter alltid med exit 2.

Reproducerat med en verkligt validerad lokal syntetisk basrelease, ny run-id,
`--approved-snapshot` och `--base-release`. DB-köläsning och driftlås är
isolerade testdubblar; ingen nätförfrågan behövs för att nå felet.

Konsekvens: den avsedda uppdateringen från nästa godkända katalog kan inte
behålla tidigare verifierade dokument och retryjournal genom CLI-flödet.
Att utelämna basen skulle ge ett tomt stagingunderlag och onödiga omhämtningar.

Rättning: verifiera att staging är ny före den första skrivningen, läs
katalogbeviset till minnet, kopiera validerad bas och skriv sedan den nya
katalogens bevis. Behåll spärren mot en orelaterad befintlig stagingkatalog.
Testa initial körning, godkänd katalog + bas, avbrott/återupptagning och att
LKG samt negativa svar följer med till nästa release.

## Kända återstående leveransgrindar

Detta är Sols redan dokumenterade resultat, kontrollerade mot det committade
[maskinunderlaget](verified-reference-axfood-20261023/failed-gate.json), inte
nya fullskaliga mätningar i denna granskning:

- Malmö/fördelning/5 000: legacy **988,32 kr**, v1 **992,22 kr**, tre lika
  utfall per arm och godkända korgkontroller. Basreferens och föregångare
  garanterar inte dominans över gamla sökningen på samma fulla bibliotek.
- Första v1-anropet tog **533,61 s**; efterföljande menyträffar cirka **8,4 s**.
  Det visar nyttan av återanvändning, men inte att ny sökning eller kallstart
  skalar tillräckligt. Första provet var inte en separat kall process.
- Cgroup nådde **3 GiB**; inget OOM, men den önskade marginalen saknas.
  Bara **30 av 252 celler** är mätta. Kall disk, varm disk i ny process och
  evictionprov återstår. Det var rätt att stoppa standardkvalificeringen
  vid ett konkret prisfel och att inte märka resten som godkänt.
- Axfood omfattar **103 verifierade dokument** av katalogköer med över
  11 000 koder per kedja. Delvis berikning är tillåten, men denna täckning
  verifierar inte nyttan eller beteendet med ett fullständigt arkiv.
  Historiska Malmö 361,81/340,64 är fortfarande inte återskapat.

Rekommenderad fortsättning: rätta de två nya felen först. För de stödda
profilerna ska förberedelsen också låta gamla fullbibliotekssökningens
vinnare konkurrera, enligt arkitekturbeslutets avsnitt 2. Kör det en gång
per exakt kontext/publicering och bevara dess verifierade resultat; kör
inte om hela referensen vid varje varm träff. Detta tar bort just den
kända dominansluckan, men kostnaden måste budgeteras och redovisas som
förberedelse. En höjning av K är inte ett generellt korrekthetsbevis.

Separera därefter minnes- och kallstartsarbetet från vinsten på rena
menyträffar. Verifiera först den misslyckade cellen och cacheeviction,
sedan återstående matris. Låt Axfoods insamlings-/readerarbete fortsätta
separat efter rättat basreleaseflöde, med oförändrade identitetskrav.
Principgodkännandet från ägaren gäller fortsatt.

## Verifiering och reproduktion

**89 befintliga riktade tester passerade**: verified-menu-search,
owned-planner-artifacts, library-publications, Axfood-detail-archive,
Axfood-product-details och approved-catalogue-queue. De nya fallen täcktes
inte av dessa tester. Sols fulla CI har inte körts om för denna dokument-
och granskningsleverans; resultatet 3 094 PASS avser Sols rapporterade CI.

[Två offlineprober](sol-architecture-review-20261024/reproduce_findings.py)
reproducerar båda fynden på `ac0bbfe`. De ligger utanför standardsviten och
asserterar **att buggen finns**: passerade prober är bevis för fynden,
inte ett godkännande av implementationen. Vid rättning ska Sol skriva
permanenta regressionstester som i stället kräver korrekt utfall.

```powershell
.venv/Scripts/python.exe scripts/verify_offline.py docs/reviews/sol-architecture-review-20261024/reproduce_findings.py -s -q
```

Granskningen omfattar kodläsning av sökning, kontext/cache, historik,
Axfood-läsare/arkiv/insamling samt rapporterad releaseevidens. Den innebär
ingen ny liveinsamling, produktionsaktivering eller full kapacitetsmätning.
