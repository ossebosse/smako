# Acceptans för det verkliga Smako-UI:t
Detta är testkrav för Codex integration, inte en rapport om redan utförd backendverifiering. Dokumentera körda fall separat. Nuvarande prototypkontroller finns i `verification/TEST_REPORT.md`.

## A. Måltider och oberoende inställningar
A01. Befintligt sparade middagsvärden visas korrekt; inte prototypens exempel-defaults.
A02. Aktivera endast frukost: fullt kort under Middag, ingen ändring av middag.
A03. Aktivera endast mellanmål: fullt kort under Middag, utan att frukost måste aktiveras.
A04. Aktivera båda: ordning Middag → Frukost → Mellanmål; alla har tre dialoger.
A05. Ändra antal, portioner, kostfördelning, vikt och protein på varje måltid; övriga måltider är oförändrade.
A06. Avaktivera en måltid: inga krav från den påverkar optimeringen. Av/på under samma session ger inte oavsiktlig radering av utkast.
A07. Kontrollera tillåtna min/max/step från verklig kod. Antalet portioner är per rätt, inte hela veckan.
A08. Noll middagar med aktiv frukost/mellanmål följer befintlig möjlighet. Noll aktiva tillfällen får ett begripligt fel enligt backendkontraktet.

## B. Näringsvärden och vikt
B01. Öppna alla nio kombinationer av måltid × dialog. Rubrik och state hör till rätt måltid.
B02. Min/max kan både skrivas och dras med två handtag; värden och positioner följs åt.
B03. 10–30 g på 0–100-skala visas vid 10/30 %, inte vid 0/100 %.
B04. Explicit 0 serialiseras som ett explicit värde; tomt/Standard behåller backendens standardsemantik.
B05. Endast Min, endast Max, båda och inga gränser fungerar.
B06. Min > Max, felaktig inmatning och gränsöverskridande ger fältnära fel och blockerat Klart; aldrig tyst nytt krav.
B07. Återställ ett näringsfält: bara det fältet återställs; andra näringsvärden/måltider är kvar.
B08. Återställ följt av Avbryt ändrar inte tidigare sparade värden.
B09. Samtliga befintliga näringsfält/precisioner/enheter finns kvar även om prototypen inte visar dem.
B10. Portionsvikt förblir tillagad, ätbar uppskattad vikt per portion i både label och data.

## C. Fördelning
C01. Samtliga befintliga kostval och kategorier finns kvar.
C02. Vid 5 tillfällen: 3 vegetariska + 2 kyckling ger 5 fördelade, 0 kvar.
C03. Vid 5 tillfällen: 1 + 2 + 1 ger 4 fördelade, 1 kvar.
C04. Summa 6 vid 5 tillfällen blockeras med förklaring; ingen dold trimning.
C05. 0 skiljer sig från Standard i både UI och request.
C06. Minska antalet tillfällen under befintlig fördelning: visa konflikt, låt användaren korrigera.
C07. Kostvals-/kategorikonflikter hanteras enligt existerande logik. Inga hårda uteslutningar lättas automatiskt.

## D. Butiker, preferenser och övriga val
D01. Postnummer med/utan mellanslag; ogiltigt format; okänd täckning; timeout; serverfel.
D02. Radius, kommun och egna butiker ger rätt kandidatunderlag enligt aktuell kod. Okänd position blir inte 0 km och hamnar inte i radieurval utan stöd.
D03. Antal kandidater och max besökta inköpsställen är separata begrepp. Max gäller hela korgen inklusive extra måltider.
D04. Egna val sparas med verkliga butiks-ID:n, inte kedjenamn eller index. Visade logotyper är inte en hårdkodad geografisk inventering.
D05. Onlinepriser/uppskattningar/okänt underlag märks korrekt; inga falska pris- eller besparingslöften.
D06. Ändrat postnummer medan tidigare sökning pågår: sent svar får inte ersätta nyare val.
D07. Tolkning av smaktext går genom befintligt flöde. Visad tolkning måste granskas före tillämpning; manuella korrigeringar fungerar.
D08. Gillar, ogillar, uteslutningar och allergier hålls åtskilda; hårda krav får inte försvinna när ett mjukt önskemål ändras.
D09. Receptstil/mål/övriga presets bevarar deras faktiska definition. Inga nya optimeringsregler från designbildens chips.
D10. Eko-andelen räknas enligt befintlig kostnadsdefinition efter rabatt, inte antal/vikt; separat animaliekrav och okänd datastatus fungerar.
D11. Överskottsstrategi, förpackningshantering och befintliga kompletterande fält bevaras.
D12. Historik, feedback, integritet/radering och befintlig toppnavigation går till rätt befintliga destinationer.

## E. Data, integration och regression
E01. Kartlägg fullständig konfigurationsmodell och ta representativa avidentifierade request-fixtures före UI-bytet.
E02. Oförändrade val ger semantiskt likvärdigt requestunderlag efter bytet; även extra fält som inte syns på bilden bevaras.
E03. Skapa plan anropar rätt befintliga flöde, exakt en gång per bekräftad handling; aktiv laddning förhindrar dubbelsubmit.
E04. Riktig backend i utvecklings-/testmiljö får rätt tre måltidskonfigurationer och ger resultat/inköpslista med gemensam korg.
E05. 401/403/5xx/timeout/ingen möjlig plan: begripligt fel, val behålls, ingen tyst fallback till mockdata eller lättade krav.
E06. Inga nya backend-endpoints, authflöden, collectors, scheman eller produktionsdriftändringar utan separat motiverat beslut.
E07. Inga demo-ID:n, förifyllda exempelpostnummer, demo-priser eller fasta exempelbutiker läcker till produktion.
E08. Befintliga bygg-, typ-, lint- och regressionstester passerar, eller faktiska fel/blockeringar redovisas.

## F. Visuellt och tillgänglighet
F01. Skärmbilder från verklig app: initial vy, vald geografi, frukost + mellanmål, öppna extraval, alla tre dialogtyper.
F02. Bredder 320, 375, 390, 430, 768 och 1440 px: ingen horisontell sidscroll, klippt text eller täckt primärknapp.
F03. Normal mobiltext och inmatning läsbara; primära touchkontroller ungefär 44 px eller större. Små återställningar får tillräcklig klickyta.
F04. Modal med långt innehåll: sidfot/rubrik åtkomliga, bakgrund låst, intern scroll fungerar.
F05. Tangentbord: etiketter, synlig fokusmarkering, fokus inom modal, Escape och tillbaka till öppningsknappen.
F06. Nummerfält och sliders kan användas utan draggest. Status/fel inte enbart genom färg. Namn på respektive handtag inkluderar näringsfält och Min/Max.
F07. iOS Safari med visat tangentbord och safe areas testas faktiskt där miljö finns; browseremulering rapporteras som emulering, inte fysisk iPhone-verifiering.
F08. 200 % textzoom, låg viewport och reducerad rörelse kontrolleras. Inga onödiga svep-, parallax- eller obligatoriska animationer.
F09. Färgkontrast/fokus/rubrikhierarki kontrolleras i den riktiga appen, även när befintliga globala stilar laddats.
