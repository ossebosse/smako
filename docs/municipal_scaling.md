# Kommunvis utrullning och kapacitetskontroll

## Implementering 2026-10-11

Följande funktioner finns nu i koden. Aktivering och verifierad runtime redovisas
separat i HANDOFF; en kodändring är inte i sig bevis för produktionsdrift.

- **Willys återupptar hela färdiga butikskataloger.** En atomiskt sparad,
  komprimerad fil per butik innehåller råunderlag och kontrollhash. Vid återstart
  kontrolleras kommun, geometri, parser, butik, sidföljd och fullständighet igen.
  Material äldre än 24 timmar återanvänds inte. Alla ursprungliga observationstider
  bevaras och ordinarie kvalificering/import körs fortfarande. En avbruten butik
  hämtas om; detta är inte återupptagning mitt på en katalogsida. Kvalificerade
  Hemköpsbutiker hade redan separata snapshots; nu hämtas den äldsta väntande
  butiken per kommunvarv, utan att lägga backoff på ännu ostartade butiker.
- **Båda befintliga arbetarna prioriterar efter deadline och väntetid.** Journalen
  sparas före start, så även ett avbrutet försök lämnar tur åt andra kommuner.
  Uppmätt tid får 25 procent marginal; okänd tid har en uttrycklig startuppskattning.
  Efter ett dygn får en väntande kommun högre prioritet. Detta ändrar aldrig
  prisernas giltighetstid. Windows budgeterar 170 minuter inom uppgiftens befintliga
  tretimmarsgräns, med marginal för transport. Serverns totala körfönster är högst
  tre timmar och barnprocessens befintliga tvåtimmarsgräns består. En butik som
  inte bedöms rymmas skjuts upp. Överlast kan fortfarande ge färskhetsproblem;
  prioritering skapar ingen extra kapacitet.
- **Nya kommuner kräver ett kapacitetsunderlag genom registreringskommandot.**
  Saknade, negativa, icke ändliga eller mer än sju dagar gamla mätningar ger
  BLOCKED. Diskkontrollen använder faktiskt ledigt utrymme och inkluderar
  byggkopia, datatillväxt, kö, artefakter, backup och återställning med marginal.
  Minnesbehov och hela den delade uppdateringscykeln kontrolleras också. Befintliga
  Lund/Malmö och idempotent registrering påverkas inte. Inga nya kommuner aktiveras
  automatiskt. Underlaget ska komma från en komplett, avgränsad pilot i separat
  testmiljö; kommandot utför ingen dold fullinsamling och verifierar inte självt
  att operatörens mätfil motsvarar en utförd pilot.
- **Laddning återförsöks utan ombygge** när ett godkänt publicerat manifest väntar
  på appen och samma källfingeravtryck/tidsgränser fortfarande gäller. Hash, kommun,
  manifest-ID och färskhet kontrolleras. Nya källor, insamling som är förfallen
  eller erbjudandeövergångar går genom ordinarie uppdatering.
- **Driftöversikt:** `scripts/smako_ops.py municipalities` visar varje kommuns
  planering, käll-/butiksscheman, kvalificering, publicerat/laddat ID och väntande
  laddning. Okända kommunresultat isoleras och döljer inte andra kommuner.
  Det lokala kommandot fogar även in varje kommuns reläkvitto och leveransstatus.
  Reläets `store-checkpoints/progress.json` och `municipal-schedule.json` visar
  sparade/återanvända kataloger och uppskjutet arbete. En sparad traversal är inte
  en kvalificerad eller publicerad prislista. Kvitton läses från respektive lokal
  kommunmapp. Extern larmleverans är fortfarande inte konfigurerad.

### Kapacitetsunderlag för nästa kommun

Kör samma insamling och prisbygge i en avgränsad pilot med separat databas,
rålagring och artefaktrot. Använd rätt kommunregister och oförändrade källgränser.
Mät en hel cykel inklusive Windowsrelä, serverbygge och återställningsbehov.
Sammanställ en JSON-fil med `municipality_code`, `postal_code`, `sources`
(sorterad lista: citygross, coop, hemkop, ica, lidl, willys, xtra),
`pilot_complete: true`, `measured_at` (UTC med tidszon), samt följande mätningar:

| Fält | Enhet/innebörd |
| --- | --- |
| `store_count`, `requests` | Faktiskt antal butiker och HTTP-anrop |
| `collection_seconds`, `build_seconds` | Uppmätt insamling respektive prisbygge |
| `peak_memory_bytes`, `available_memory_bytes` | Toppbehov och tillgängligt minne efter övriga tjänster |
| `database_growth_bytes`, `build_copy_bytes` | Datatillväxt och hel tillfällig byggdatabas |
| `artifact_bytes`, `queue_growth_bytes` | Artefaktstorlek och maximal tillkommande kö |
| `backup_bytes`, `restore_bytes` | Tillkommande backup och utrymme för återställning |
| `existing_cycle_seconds`, `available_cycle_seconds` | Befintlig total arbetsmängd och faktiskt tillgänglig arbetstid inom färskhetsfönstret |

Okända fält lämnas saknade; sätt inte noll för att få godkänt. Noll är bara
tillåtet för faktiskt utebliven tillväxt/kö och befintlig arbetsmängd. I serverns
ordinarie driftmiljö används samma granskade fil först för kontroll, sedan för
registrering under operationslåset:

```text
python -m grocery_data.municipal_cli capacity --municipality 1480 --postal-code 41110 --capacity-evidence /reviewed/pilot.json
python -m grocery_data.municipal_cli add --municipality 1480 --postal-code 41110 --capacity-evidence /reviewed/pilot.json
```

Exemplet aktiveras inte av dokumentationen. En godkänd kapacitetsrapport ersätter
inte källornas kvalitetskontroller eller verifiering av butikstäckning och meny.

---

Beslutsunderlag 2026-10-11. Lund och Malmö är aktiverade. Göteborg har endast
torrkörts. Registreringen är generell, men godkänd registrering bevisar varken
butikstäckning eller att insamlingen ryms inom driftens kapacitet.

## Uppmätta begränsningar

- Malmö: fyra Willys-kataloger, 2 572 HTTP-anrop och cirka 86 minuter för
  insamling, parsning och paketering. 39 594 butik/produkt-rader motsvarar
  11 422 olika återförsäljarprodukter, inte lika många användbara menyvaror.
- Fyra Hemköp-kataloger tog omkring 71 minuter; efterföljande prisbygge cirka
  16 minuter. Ett avvisat butikssortiment får inte starta om redan färska butiker.
- Willys har två timmars gräns per insamling, högst 6 000 rådokument och
  `min(5900, 1000 * verifierade_onlinebutiker + 100)` anrop. Windowsuppgiften
  har tre timmars totalgräns och kommunerna körs i följd.
- Ett pågående prisbygge den 11 oktober använde 4,46 GB för sin tillfälliga
  databaskopia. Ledigt serverutrymme sjönk då till cirka 8,20 GB. Kopian är
  aktiv arbetsdata och ska inte raderas medan bygget pågår.
- Det större Malmöbygget observerades med cirka 3,07 GiB arbetsminne och en
  fullt utnyttjad CPU-kärna i en byggfas. Detta är en ögonblicksmätning,
  inte genomsnitt eller ett dimensioneringslöfte.
- Gemensamt operationslås skyddar insamling, publicering och aktivering.
  Fler kommuner innebär därför mer väntetid, även om deras källor är separata.

Underlag: föregående [Malmörelease](releases/municipal-rollout-20261011/ACTIVATED.json),
lokal driftevidens `.local/municipal-repair/` och skyddad serverevidens
`/opt/smako/evidence/municipal-repair-17a75cf60d5a/`. Tiderna är observationer
från konkreta körningar, inte garanterad genomströmning.

## Prioriterade utvecklingssteg

| Ordning | Åtgärd | Godkännandekrav före större utrullning |
| --- | --- | --- |
| 1 | Återupptagbar insamling per butik i befintlig snapshot- och reläkedja | Avbrott efter en färdig butik återanvänder hashverifierat material. Ursprungliga observationstider bevaras. Ofullständiga kataloger kan inte promoveras. |
| 2 | Planering utifrån färskhetsdeadline och uppmätt återstående tid | Samtliga kommuner får tur. Ett långsamt område får inte svälta ut senare områden. Starta inte en enhet som inte ryms i återstående körfönster; återuppta nästa gång. |
| 3 | Kapacitetsprov innan en ny kommun aktiveras | Redovisa butiksantal, förväntade anrop, tid, databasökning, byggkopia, artefakter, kö och återställningsmarginal. Saknade mätningar ska visas som okända, inte som godkänt. |
| 4 | Färre prisbyggen och separat återförsök av laddning | Återanvänd ett redan validerat bygge när endast laddning/kvittens återstår. Bygg om vid ändrat kvalificerat underlag eller tidsgräns för erbjudanden. Laddat ID måste matcha rätt kommuns publicerade ID. |
| 5 | Kontrollerad arkivering och dimensionerad lagring | Referenskontroll skyddar aktivt underlag, senaste giltiga reserv, väntande jobb och granskningsbevis. Återläsningsprov krävs före borttagning. Dimensionera mer disk efter verklig toppförbrukning. |
| 6 | Driftöversikt per kommun och butik | Visa upptäckt, hämtning, kvalificering, publicering, laddning och kvittens separat, med källålder och orsak för misslyckade/okända butiker. Prova larmets hela väg innan det betraktas som fungerande. |
| 7 | Verifierade större dataflöden från kedjorna | Utvärdera officiella bulk- eller förändringsflöden där sådana kan erhållas. Pris måste fortfarande knytas till rätt butik och villkor. Tillgång, avtal och kostnad är ännu inte utredda. |

Steg 1–3 bör föregå aktivering av flera stora kommuner. Registrera sedan en
kommun åt gången och verifiera minst en hel ordinarie uppdateringscykel,
butiksval, avståndsurval, verklig meny och beständig omladdning innan nästa.
Välj pilot efter verifierad källtäckning och kapacitet; kommunens storlek ensam
avgör inte hur lätt den är att samla in.

## Historiskt utgångsläge före denna implementation

Lagringsåtgärden 2026-10-11 frigjorde **106,49 GB** genom verifierade kalla
testarkiv och rensad byggcache. Servern hade därefter **118,39 GB ledigt**.
Ett ägarfel som hindrade backupkontots rotation är också rättat; nästa fulla
rotation återstår att observera. Detta ger marginal men ersätter inte mätning
per kommun eller referensstyrd retention av produktionshistorik.
Se [lagringsrapporten](storage-maintenance.md) för mätvärden och återställning.

Ordinarie återförsök godkände också de två tidigare avvisade Hemköp-katalogerna
i Malmö före lagringsunderhållet. Efter publicering har Malmö 2 607 produkter
och 63 pris-/butikskontexter, med Värnhem och Elinegård även som onlinekontexter.

Den befintliga registreringen, separata kommunjournalerna, oförändrade scheman,
butiksvisa Hemköp-återförsök och kommunvisa användarval är på plats.
Källrelease `17a75cf60d5a` rättar Coops parserversionskontroll och Hemköps
granskade schemakontrakt. Två mindre Malmö-sortiment har separata, belagda
fullständighetsgränser. Kedjans generella 8 000-varugräns och alla sid- och
kategorikontroller består. Historiska underlag behåller sin sparade gräns.

Samma release bekräftar rätt kommuns exakta laddade manifest via readiness om
laddningsanropets svar går förlorat. Det undanröjer en orsak till upprepade
byggen; en fullständig separat kö för laddningsåterförsök är ännu inte införd.
Återupptagbar insamling och deadlinebaserad fördelning ovan är också kvarstående
utveckling, inte redan driftsatta funktioner.

Uppföljningsrelease `0e2bacd95c03` avgränsar driftstatus till rätt kommuns
källjournal, stad och postnyckel. Pipelineincidenter kan endast återhämta sig
mot samma kommun. Den gemensamma diagnostiken saknar fortfarande läsning av
City Gross 3211:s separata kommunala källdatabas och visar detta som unknown;
den publicerade priskontexten och readiness har verifierats separat.

Coops fysiska erbjudanden ger inte automatiskt ett fullständigt bassortiment.
Tre Malmöbutikers offentliga sidor saknade erbjudandekort vid nya försök;
Centralens faktiska erbjudandesvar var HTTP 200 med `{}`. Detta bevisar ett
saknat kvalificerbart underlag vid kontrollen, inte att butiken saknar erbjudanden.
X:-tras saknade publikationer behöver giltiga butiksegna källor. Dessa luckor
ska följas upp genom ordinarie återförsök eller en verifierad ny källa.

Färskhetsgränserna 36/48 timmar, senaste giltiga reserv och exakta butiksidentiteter
ska bestå. Coop-fullinsamling är fortsatt begränsad till onlinekontext 730400.
Denna plan ändrar inga trafikgränser, köper ingen kapacitet och aktiverar inga
ytterligare kommuner.
