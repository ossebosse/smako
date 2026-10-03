# Kontrollerad aktivering och återgång

Denna kandidat är en lokal funktionsleverans. Ingen Git-push eller
produktionsaktivering ingår. Aktuell produktionsinsamling, Windows-relä,
scheman, kommuntäckning, femkällorspolicy och 36/48-timmarsgränser ska inte
ändras vid installationen.

## Versionsbunden installation

1. Utgå från runtime-commit och serverpaket i denna releases `RESULTS.md` och
   det intilliggande `release.json`. Kontrollera SHA-256 före uppackning.
   Paketbyggaren läser enbart Git-blobbar. Använd rotens Dockerfile med
   serverpaketet som byggkontext; flytta inte in utvecklingsmiljön `.local`.
2. Ta en konsistent säkerhetskopia av befintlig plan- och personlagring enligt
   projektets driftordning. Bevara ägarsessionernas befintliga hemligheter,
   planrevisioner och skafferihistorik. Det krävs ingen radering eller
   återställning av gamla recept eller planer.
3. Starta den nya applikationsbilden med **`COMPLETE_RECIPES_ENABLED=false`**.
   Återanvänd ordinarie publicerat PriceUniverse och befintlig tillståndslagring.
   Kopiera aldrig replaymiljöns testklocka, prisfrysning, testsessioner eller
   `scripts/recipe_layer/serve.py` till produktionsstarten.
4. Verifiera readiness, gammalt publikt menyflöde, gamla personliga planer och
   åtkomstkontroll. Kör inga nya prisinsamlingar som del av detta prov.
5. Efter separat driftbeslut: sätt **`COMPLETE_RECIPES_ENABLED=true`** för
   applikationen och starta om enbart applikationsprocessen enligt ordinarie
   deployförfarande. Standardvärdet är av. Gränssnittets kapabiliteter läses
   från servern; flaggan skyddar också API:t.
6. Prova det publika och personliga läget med aktuellt publicerat underlag:
   fem middagar, två portioner, valda matkök, 10–15 ingredienser, högst två
   inköpsställen. Kontrollera synliga kvalitetsstatusar, kort start-/statusanrop,
   sparad plan, byte till annan grundrätt och uttrycklig omräkning. Priser och
   köpbarhet ska bedömas på dagens källor, inte mot replayrapportens belopp.

## Återgång utan förlust av planer

Sätt först `COMPLETE_RECIPES_ENABLED=false` och starta om samma nya
applikationsversion. Det stoppar ny komplett generering men behåller läsning
av redan sparade recept och samtliga revisioner. Gamla menyförfrågningar
fortsätter använda sitt befintliga läge. Radera inga receptarkiv, planrader,
revisioner eller skafferihändelser.

Att byta tillbaka till en äldre binär som saknar de nya läsmodellerna är inte
den rekommenderade funktionsåtergången. Om det ändå behövs av ett separat
driftskäl måste tillståndet först säkerhetskopieras och läskompatibiliteten
kontrolleras i isolering. Återställ inte en äldre databas över senare
användararbete.

## Källor och innehåll vid senare uppdateringar

Nya publicerade prisunderlag går genom befintlig PriceUniverse-aktivering och
kvalificering. En cachad lösning får inte förlänga en kampanj. Det frysta
acceptansunderlaget är endast historiskt bevismaterial.

Recepttexter, proportioner och tidsplaner är versionsbundet granskat innehåll.
En ändring kräver ny utgåva och bevarande av tidigare utgåvor för återläsning
och uttrycklig omräkning. Receptåterkoppling är knuten till användarens exakta
receptversion; den får inte skriva om andra användares planer. Planerade
rester blir aldrig automatiskt uppmätt skafferi.
