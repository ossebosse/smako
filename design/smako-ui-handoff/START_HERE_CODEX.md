# Uppdrag: implementera godkänt Smako-UI, alternativ 3

Arbeta i befintligt Smako-repo. Underlaget ligger i `design/smako-ui-handoff/`.
Implementera det nya gränssnittet i den verkliga applikationen. Leverera inte bara en plan, en bild eller en separat demo.

## 1. Läs och kartlägg utan att ändra drift
- Läs gällande projektinstruktioner och relevanta `AGENTS.md` utan att ersätta dem.
- Kontrollera arbetskopia, branch och befintliga lokala ändringar. Arbeta på separat UI-branch eller säker isolering enligt projektets arbetssätt. Kör aldrig reset/clean/stash av användarens ändringar utan tillåtelse.
- Läs `README.md`, `UI_SPEC.md`, `FUNCTIONAL_PARITY.md`, `API_MAPPING.md` och `ACCEPTANCE.md` i paketet.
- Öppna `references/approved/approved-board.png` och detaljutsnitten. Läs originalbilderna av befintliga inställningar vid behov.
- Granska prototypen i `prototype/` eller `smako-ui-preview.html`. Dess testdata, enums och fältnamn är INTE backendens API.
- Identifiera verklig frontendstack, komponentstruktur, routes, API-klient, state/persistens, formulärhantering, autentisering och tester. Återanvänd dem.
- Fyll `API_MAPPING.md` med verkliga symboler/filvägar, fält, defaults, enumvärden och anropsflöden. Förteckna även existerande fält som inte syns i bilderna. Märk osäkerheter och integrationsluckor.

## 2. Implementera i befintliga frontendfiler
- Bevara designriktningen: varm cremevit bakgrund, skogsgrön färg, vita rundade kort, serifrubriker, kompakta tydliga kontroller och samma formspråk i dialoger.
- Bevara backend, routing, inloggning, insamlare, scheduler, prisdata, pris-/köpregler, optimering och existerande sparade användarval.
- Frukost och mellanmål aktiveras oberoende i Extraval. Aktivering visar ett fullständigt eget inställningskort under Middag. Ordningen är Middag, Frukost, Mellanmål.
- Alla aktiva måltider har Antal, Portioner, Fördelning, Portionsvikt och Näringsvärden. Återanvänd samma måltidskomponent och dialogkomponenter utan att dela inställningsstate mellan måltiderna.
- Näringsvärden och portionsvikt ska ha två reglagehandtag OCH numeriska min/max-fält, enheter, validering samt återställning. Positionerna måste motsvara värdena; kopiera inte de felplacerade reglagehandtagen i AI-bilden.
- Standard/tomt får inte omvandlas till 0 eller till ändpunkterna på skalan. Mappa mot befintligt kontrakts exakta null/utelämnat/sentinel-semantik.
- Fördelning använder befintliga kostval och samtliga kategorier. Visa fördelade antal och kvarvarande antal korrekt. 0 och Standard är olika. Ändra inte explicit valda fördelningar tyst när måltidsantalet minskas.
- Klart tillämpar dialogens giltiga utkast för rätt måltid. Avbryt/kryss/Escape lämnar föregående värden kvar. Bakgrunden är låst och fokus återställs korrekt.
- Behåll geografiskt urval, egna butiksval, max inköpsställen för hela korgen, extra måltider, smak-/uteslutnings-/allergifält, granskningssteg, receptlägen, ekologiskt, överskottsstrategi, tidigare planering/feedback, integritetslänkar och alla ytterligare befintliga inställningar.
- Koppla inte bildens påhittade snabbval till nya hårdkodade närings-/optimeringsregler. Använd befintliga dokumenterade presets om sådana finns. Annars använd genvägar till befintliga inställningar enligt prototypen.
- Låt befintliga scheman/kod styra fältens fullständiga uppsättning, gränser och defaults. Prototypens Fett/Energi-gränser och listor är illustrationsdata, inte beslutade backendregler.
- Ta inte bort funktioner bara för att de saknas i designbilden. Flytta dem till ett logiskt ställe i samma stil.

## 3. Koppla och verifiera
- Använd befintliga anrop för postnummer/butiker, tolkning, inläsning/sparning av val och skapande av plan/inköpslista. Skapa inte nya endpoints för att efterlikna prototypens objekt.
- Håll presentation, UI-state, validering och API-adapter åtskilda. Återanvänd existerande affärslogik. Mappa bara de fält UI:t äger och behåll övriga stödda befintliga värden.
- Ingen tyst fallback till exempeldata när ett backendanrop misslyckas. Inga exempelbutiker, demo-ID:n eller demoval i produktionsflödet.
- Bevara laddning, fel, tomma svar, okänd datastatus, utgången session och användarens val efter fel. Hindra dubbelsubmit och sena svar som skriver över nyare val.
- Verifiera UI mot verkligt API i utvecklings-/testmiljö utan att initiera produktionsprisinsamling. Testa request-paritet före/efter för representativa befintliga inställningar.
- Kör byggkontroll, lint/typkontroll och relevanta enhets-, integrations- och UI-tester enligt projektets verktyg.
- Granska faktisk rendering på 390 px mobil och 1440 px desktop. Testa även 320/375/430 px, låg viewport, modal-scroll, tangentbord och iOS Safari/safe areas när den testmiljön finns.
- Lämna nya skärmbilder av det verkliga Smako-UI:t. Visa middag + aktiverad frukost + aktiverat mellanmål, extraval och respektive dialog.

## 4. Slutrapport
Redovisa ändrade filer, återanvända anrop, bevarade funktioner, körda kommandon/resultat, skärmbilder och kvarvarande verifieringsluckor. Rapportera blockeringar ärligt. Påstå inte att en backendkoppling eller Safari-testning är verifierad om den inte har körts.

Slutför all icke-blockerad implementation i samma uppdrag. Om en nödvändig backendändring verkligen krävs: gör inte den obemärkt, dokumentera varför och föreslå den minsta ändringen. Stoppa inte hela UI-arbetet för att någon fristående tilläggsfunktion saknar stöd.

**Ingen push. Ingen deployment. Inga ändringar av prisinsamling, scheman, produktionsdata eller hemligheter.**
