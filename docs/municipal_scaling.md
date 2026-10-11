# Kommunvis utrullning: nästa åtgärder

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

## Redan genomfört och kvarvarande gränser

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
