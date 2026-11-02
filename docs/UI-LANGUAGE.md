# Språk i Smakos användartexter

Gäller allt som syns för användaren: texter i `/personal`, felmeddelanden från
API:t och meddelanden som planeraren skickar till planen. Receptens språk styrs
av [författarinstruktionen](recipes/AUTHORING.md).

## Grundregler

- **Skriv till användaren, inte om systemet.** ”Vi har inga priser för det här
  postnumret än”, inte ”Prisunderlag saknas för valt postnummer”.
- **Säg vad som hände och vad man kan göra.** Ett fel slutar med en handling:
  ”Välj fler matkök eller längre tid.” Inte ”Se blockeringsfördelningen”.
- **En mening räcker oftast.** Hjälptexter är högst två korta meningar.
  Regler och detaljer hör hemma under ”Läs mer” eller i Tekniska detaljer.
- **Ett förbehåll på ett ställe.** Skriv inte samma reservation på varje rad
  (”inte ett verifierat kvitto”, ”ingen garanti …”). Det som verkligen påverkar
  användaren ska stå kvar: uppskattade mängder, okända allergener, att ett
  nätpris kan skilja sig från hyllpriset.
- **Ingen reklamton.** Inga slogans i tretakt (”Goda måltider. Lägre kostnad.
  Enklare vardag.”), inga utropstecken och inget ”sömlöst” eller ”smidigt”.
- **Undvik ”X, inte Y”.** Skriv det som gäller: ”Tiden är uppskattad”, inte
  ”Tiden är en uppskattning, inte ett provlagningsresultat”.
- **Lova inte mer än beräkningen visar.** Skriv ”det billigaste vi hittade”,
  inte ”billigast”, när global optimalitet inte är bevisad.
- **Ändra aldrig betydelsen.** Gränser, varningar om uppskattningar och
  allergier, prisernas omfattning och AI-ursprung ska finnas kvar, bara
  enklare formulerade.

## Ord att byta ut

| Skriv inte | Skriv i stället |
| --- | --- |
| underlag, prisunderlag, produktunderlag | uppgifter, priser, varor |
| verifierad, verifierat | kontrollerad, bekräftad, eller inget alls |
| priskontext, kontext, inköpsställe (i rubriker) | butik, nätbutik |
| korg, korgen | inköpslista, inköp |
| tillfälle, måltidstillfälle | måltid |
| planeraren | Smako |
| spårbar uppskattning | uppskattat |
| produktidentitet | produkt, vara |
| bokföra | registrera |
| hårt krav, hårda val | det du har valt bort |
| giltig, ogiltig | fungerar, stämmer, oväntat svar |
| sökbudget, delsteg, delberäkning | beskriv vad användaren kan göra |
| kvalificera, disponibel, tillämpa | kontrollera, finns kvar, använd |
| revision, planrevision | version |
| session (i felmeddelanden) | webbläsaren, ladda om sidan |

`backend/tests/test_ui_language.py` stoppar orden i tabellen i texterna som
`/personal` laddar. Lägg till ett ord i testet och i tabellen samtidigt. Interna
namn i kod, loggar, adminvyn och dokumentation påverkas inte.

## Exempel

| Före | Efter |
| --- | --- |
| Matkassen är ogiltig | Inköpslistan gick inte att räkna ut |
| Sparade priser visas. Prisunderlaget har ändrats; räkna om för aktuell korg. | Priserna är från när planen sparades. Räkna om planen för att se dagens priser. |
| Sökningen hittade ingen komplett meny med dina krav. Se blockeringsfördelningen. Inga krav har sänkts. | Vi hittade ingen meny som uppfyller alla dina krav. Se vad som stoppade recepten nedan. |
| Planeringsförsöket finns inte i din session. | Vi hittar inte beräkningen. Starta en ny. |
