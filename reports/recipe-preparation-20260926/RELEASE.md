# Aktiveringsunderlag – recept och beredning

Status: **inaktiv kandidat**. Ingen produktion, Windows-uppgift eller aktivt
schema är ändrat. Tidigare pris-/kedjereleaser gäller separat och är bevarade.

## Förändrat beteende

Nya recept från den deterministiska generatorn får versionerad, validerad
beredningsdefinition och uttrycklig oljemängd. Originalversioner finns kvar
genom `recipe_version="legacy"` och redan sparade recept omskrivs inte.
Externa anpassningar måste vara separata versioner.

Näringsuppskattning kräver fortfarande användarens opt-in. Ny varm
insatsberäkning märks ESTIMATED även när ingående produktdeklarationer är
verifierade. Köpprisets kvalitet är separat. Ätbar minimimängd ska vägas;
okänd färdigvikt eller okänd skal-/avrunnen mängd blir inte ett exakt utbyte.

API och PlanStore behåller `Recipe.preparation`; instruktioner, mängder,
formkrav och metodversion måste stämma. Receptidentitet/cacheunderlag omfattar
metoden. Gamla JSON-recept utan detta fält behåller sin tidigare form.

## Verifiering i denna etapp

Se VERIFICATION.md och summary.json för faktiskt uppmätta resultat från:

- Alla 84 ursprungliga avslag, med jämförelse av originalens exakta
  ingrediensmängder och instruktioner mot förra leveransen.
- Gamla och kompletterade recept i 15/20-profilen med 40/30/20 g protein,
  högst två butiker, originalmedlemskap och separat Plus-kopia.
- Ordinarie HTTP PersonalPlanner för den tidigare blockerade tofumackan
  och separat varm Lidl-/Arla-smörgås. Hela inköp, audit, sparning,
  återläsning och verklig backendprocessomstart.
- Riktade positiva/negativa regressioner, Ruff och compileall.

Alla priser är historisk replay vid 2026-09-24T21:16:35.494010Z. Inga nya
prisobservationer eller näringsvärden importeras. En separat officiell
webbkällkontroll av kikärtor ingår inte i pris-/näringsbasen.

## Kvarstående före framtida aktivering

1. Följ befintlig godkänd deploy-/aktiveringsväg; detta dokument aktiverar inget.
2. Använd aktuell komplett bas under oförändrade 36/48-timmarsgränser för ett
   aktuellt publiceringsprov. Återspelad bas är inte färsk produktion.
3. Kontrollera presentationen av receptversion, ätbar minimimängd och
   uppskattad näring i den avsedda klientreleasen. Denna etapp verifierar
   bevarandet i HTTP/API och sparad plan; ingen ny visuell UI-kontroll utförs.
4. Behåll kvarstående produkt-/mängdgränser: ägg behöver belagd ätbar
   inköpsmängd, avrunna baljväxter behöver båda mängd- och näringsgrunden,
   och g/ml-konvertering kräver belägg. Ett pris kan finnas trots att
   receptanvändningen fortfarande stoppas.
5. Behandla fullständig Malmö-publicering och historisk Lidl-fixture som
   separata öppna kontroller, inte som godkända genom dessa receptprov.

Ingen sökning har gjorts obegränsad. Avslag efter 256 näringskombinationer
är inte bevis för global omöjlighet eller ett ekonomiskt bortval.

Vid eventuell återgång återanvänds föregående applikationspaket enligt den
befintliga releaserutinen. Ny versionerad planinformation ska bevaras;
äldre kod kan sakna beräkningsstöd för sådana planer. Radera eller skriv
inte om användarnas recept som en del av återgången.
