# UI-specifikation · Smako alternativ 3
Version 1.0. Underlag: användarens bilder och godkänd utbyggd design. Alla värden i skisser/prototyp är exempel om inte befintlig kod verifierar dem.

## 1. Målsättning och avgränsning
En kompakt, varm och tydlig konfiguration för en gemensam matplan och inköpslista. Byt presentation, inte affärsbeteende. Layouten ska kunna utökas med befintliga inställningar som ligger utanför skärmbilderna.

Detta är inte en ny receptgenerator, optimerare, backend eller nylansering. Befintligt resultatflöde efter planering ska fortsätta fungera.

## 2. Designreferenser och preciseringar
`references/approved/approved-board.png` är användarens godkända design. Den visar en stilriktning, inte en fullständig funktions- eller dataförteckning. Den lilla AI-bilden innehåller illustrativa fel som INTE ska implementeras:
- I fördelningsbilden visas 1 + 2 + 1 men en summering på 5. Korrekt summering är 4 av 5, 1 kvar. Ursprungsskärmens 3 + 2 är 5 av 5, 0 kvar.
- Reglagen har ritats vid ändpunkterna trots egna min/max-värden. Verklig position ska vara proportionell mot skalan. Exempel: 10–30 på 0–100 placeras vid 10 % och 30 %.
- Telefon 5 visar två dialoger samtidigt för presentation. Produkten får bara ha en aktiv modal åt gången.
- Frukost får INTE ersätta middag med ett annat, förenklat kort. Båda ska ha samma inställningar. Mellanmål fungerar likadant.
- Max inköpsställen och flera avancerade val saknas i bilden men ska finnas kvar.
- Fotografier, logotyper, ikoner för favoriter/profil och handskrivna dekortexter är inte nya funktionella krav. Återanvänd rena godkända resurser där de finns; lägg inte en bild på hela UI:t.
- Snabbvalens exakta effekter har inte definierats. Prototypen använder därför genvägar till befintliga inställningar, inte nya dolda optimeringsregler.

## 3. Visuellt system
Förslagna exakta implementationstokens finns i `prototype/tokens.css`. Dessa är ett genomarbetat kodförslag, inte färgmätningar från bilden.

| Egenskap | Förslag |
|---|---|
| Bakgrund | `#f7f6f0` |
| Kort | `#ffffff` |
| Ljusgrön yta | `#edf3e9` |
| Huvudtext | `#143f35` |
| Primär handling | `#164b3e`, vit text |
| Sekundär text | `#586a60` |
| Kant | `#d7dfd7` |
| Radii | Kontroller 10 px, kort 18 px, modal 26 px |
| Avstånd | 4/8/12/16/20/24/32/40 px |
| Brödtext | Systemfont, normal läsbar storlek; inmatning 16 px |
| Rubriker/ordmärke | Befintlig serif om tillgänglig; Georgia är referensens fallback |
| Interaktion | Synlig fokusram; inte enbart färg som status |

Anpassa tokens till projektets befintliga stylingmekanism: CSS-variabler, befintliga komponenttokens eller motsvarande. Inget tvingande nytt stylingpaket. Lägg inte in global CSS-reset som oavsiktligt ändrar andra Smako-vyer; använd lämplig scope/layout i riktiga appen.

## 4. Informationsstruktur
Huvudflöde i samma konfiguration: **Butiksområde → Måltider → Max inköpsställen → Extraval → Skapa plan och inköpslista**. Flytta inte obligatoriska fält bakom otydliga menyknappar.

Mobil: en kolumn, minst 14–20 px sidmarginal vid vanliga telefonbredder. Sammanfattning och huvudknapp under formuläret. Ingen obligatorisk wizard; bildens stegindikator är dekorativ riktning, inte ett krav att införa ny routing.

Desktop: arbetsyta max ungefär 1100 px, huvudformulär och mindre sammanfattningskolumn. Sammanfattningen kan vara sticky så länge den får plats. Dialog max ungefär 560 px. Låt inte fälten bli godtyckligt breda.

Ingen horisontell sidscroll vid 320 px. Låt etiketter radbrytas utan att knappar eller värden försvinner. Textzoom och tangentbord ska inte gömma Klart/Avbryt. Använd `dvh`/safe areas eller projektets motsvarighet.

## 5. Butiksområde
Postnummerfält med beständig label, numeriskt tangentbord och uttrycklig Hitta butiker-handling. Acceptera visningsmellanslag enligt befintlig normalisering. Visa laddning, valideringsfel, saknad täckning och serverfel skilt åt.

När svar finns: områdessammanfattning, urvalssätt, radie när relevant, val av specifika butiker och antal butiker i kandidatunderlaget. Logotyper representerar inte val av en viss fysisk butik utan en verifierad koppling. Välj enskilda butiker med verkliga ID:n, namn, tillgängliga avstånd, kanal och markering.

Antalet kandidatbutiker är INTE max antal inköpsställen. UI får exempelvis jämföra 20 butiker men optimera korgen till max 2. Behåll nuvarande radius-/kommun-/egna-val-beteende inklusive vad som händer vid växling. Prototypens kommunresultat är en fixture och gör ingen gränsberäkning.

Förklarande text kan ligga under Om avstånd och prisunderlag. Gating, varningar och kritiska begränsningar får inte döljas på ett vilseledande sätt. Okänd position visas som okänd, aldrig som 0 km. Online-/butikspris hålls isär. Kommun betyder inte samma sak som adressort.

## 6. Återanvändbart måltidskort
En komponent per aktiv måltid, exempelvis `MealSettingsCard` med motsvarande egenskaper i aktuell stack:
- Identitet: middag, frukost eller mellanmål; stabil nyckel.
- Antal måltider/tillfällen och portioner per rätt, med minus/plus och direkt inmatning.
- Tre likadana handlingar: Fördelning, Portionsvikt, Näringsvärden.
- Kort sammanfattning: Standard eller antal egna val/intervall.
- Komponentspecifika fel, inte bara ett generiskt fel längst ned.

I Extraval finns två oberoende aktiveringskontroller. Vid aktivering läggs kortet till i ordningen Middag → Frukost → Mellanmål. Ingen automatisk helsidesnavigation eller jump som tar bort fokus från kontrollen. Meddela förändringen till hjälpmedel och erbjud Gå till måltider.

Varje måltid äger eget state: ändringar i Frukost får aldrig ändra Middag/Mellanmål. Även fördelning, vikt och näring är separata. Receptstil är däremot middagsspecifik enligt befintlig text; flytta inte globala fält till alla kort utan stöd i kod.

Avaktiverad måltid ska inte påverka planeringen. Behåll gärna dess utkast under pågående session för av/på utan dataförlust, men bevara befintlig persistensmodell. Koppla payloadens exkludering/avaktivering enligt verkligt API, inte genom att anta att alla fält ska serialiseras som 0.

## 7. Gemensam dialog
Rubrik visar måltid + inställning, t.ex. **Frukost · Näringsvärden**. Samma dialogram för alla måltider.

Scroll endast i modalens innehåll vid behov. Rubrik/stängning och sidfot med Avbryt/Klart förblir åtkomliga. Bakgrundens scroll och fokus är låsta. Tangentbord, Escape, fokusfälla och återfokus fungerar. Bara en modal åt gången.

Dialogen arbetar på ett utkast. Klart validerar och tillämpar lokalt för rätt måltid. Avbryt/kryss/Escape/backdrop avbryter utan ändring. Återställ påverkar utkastet och blir bestående först med Klart. Lokal Klart ska inte på egen hand införa ett nytt nätverksanrop om befintligt UI inte har det.

## 8. Näringsvärden
Visa samtliga fält som redan finns, inte en fast ny fyrfältslista. Varje fält: namn, enhet, Min, Max, två reglagehandtag, skala, Standard-status, återställning och fältnära fel.

Tomt Min och/eller Max betyder ingen användarspecificerad gräns på den sidan; befintlig standardberäkning gäller. Explicit 0 är ett eget värde. Fullt visat reglageintervall betyder inte att båda ändpunkterna ska skickas som krav. Återställ båda till standard utan att ändra andra näringsfält.

Min ≤ Max när båda är satta. Validera siffror, finita tal, tillåtna steg och gränser från befintliga scheman. Förhindra korsande handtag och synka dragning/inmatning. Behåll separat möjlighet att tömma båda fälten.

I aktuella screenshots är Protein-skalan 0–100 g och Kolhydrater 0–400 g. Fett/Energi i designbilden är en illustration; deras verkliga förekomst, skala, steg och enheter måste läsas ur kod. Ändra inte giltiga sparade värden till bildens gränser. Näringsvärdena gäller per portion, inte hela veckans mängd. Paketet anger inga rekommenderade näringsmål.

## 9. Portionsvikt
Samma RangeField-komponent som näring. Viktdefinitionen ska vara **uppskattad tillagad, ätbar vikt per portion**. Inte råvarornas inköpsvikt, inte veckokorgens vikt och inte förpackningsvikt. Aktuell bild visar skala 0–3000 g; verifiera gränser/steg i kod. Tomt/Standard ska bevaras.

## 10. Fördelning
Kostval samt samtliga befintliga matkategorier. Visa egna antal med kompakt stegkontroll och direkt inmatning. Behåll Standard som separat tillstånd från 0.

Summa egna antal får inte överstiga den aktuella måltidstypens antal tillfällen. Återstående antal fylls av planeraren enligt befintliga regler. Sammanfattningen räknas från faktiska värden. Vid minskat antal tillfällen: visa konflikt och väg att justera, ändra inte explicit fördelning tyst.

Kostval som vegetariskt/veganskt ska bevara befintliga exkluderingar. UI får förvarna om uppenbara konflikter, men ska inte införa en ny optimerare eller ny kategoritaxonomi. Den fullständiga kategorilistan och kombinationsreglerna måste läsas ur kod.

## 11. Extraval utöver måltider
Smak: fri text, befintlig Tolka och granska-funktion, granskning av strukturerade fält, möjlighet att redigera manuellt. Gillar, ogillar, hårda uteslutningar och allergier är olika fält. Tillåt inte att en fri text/tolkning tyst ersätter bekräftade hårda krav. Gör ingen ny allergitolkning via frontendheuristik.

Receptstil: alla befintliga lägen. Planeringsmål Billigast/Balanserad/Varierad ska fortsätta ha sin befintliga betydelse där de finns. Inga nya gränser för Högprotein eller Familjevänligt hämtas från skissen.

Ekologiskt: procent av verifierad ekologisk kostnadsandel efter rabatt, samt separat krav på ekologiskt för animalier inklusive ägg och mejeri. Behåll full kostnadsdefinition, datastatus, fel/konflikter och okända märkningar. Ingen förändring till procent av antal varor eller vikt.

Överskott: befintliga strategier, förpackningsavrundning, extra mängd/merkostnad, beräknade rester och okänd hållbarhet ska behållas. Alla dolda ytterligare inställningar måste inventeras och få en plats.

## 12. Slutlig huvudhandling
**Skapa plan och inköpslista** använder befintlig validering/serialization/resultatrouting. Ingen automatisk planberäkning medan användaren drar reglage om det inte redan är avsiktligt beteende.

Bevara data vid timeout/fel. Visa riktig status utan påhittad procentprogress. Ingen tyst mock-fallback, och inga hårda krav får lättas utan uttrycklig användarhandling när planen saknar lösning.
