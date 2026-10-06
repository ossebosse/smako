# Versionshanterat måltidsinnehåll

JSON är enda importformatet: `smako-meal-pack-v1`, `pack_id` och `recipes`.
Varje post följer `Recipe`/`RecipeDesign`: stabil `base_id`, innehållsversion,
variant, portionsgrund, fullständiga ingredienser och instruktioner.
`meal_types` använder dinner/breakfast/snack; `dinner_level` använder
simple/crafted. Blandning är ett användarval, inte en egen måltidstyp.
Matkök får vara tomt. Aktiv tid, total tid och väntetid är separata minuter.

Ingredienser anger kanonisk identitet, g/ml/st, mängd, komponent, roll,
råvaruform och eventuella stödda produktkrav. Komponenternas mängder måste
överensstämma med ingredienslistan. Steg har stabilt ID, ingrediensreferenser,
beroenden och uppskattad tid. Alla ingredienser ska användas. Ingen aktuell
butik, pris, näringsdeklaration eller exekverbar kod finns i innehållet.

Importeraren läser aldrig receptstyrda sökvägar eller dynamiska moduler.
Den beräknar innehållshash och knyter befintlig insatsmetod till exakt innehåll.
`content_source` binder författarunderlagets hash och granskningsstatus.
Maskinell strukturgodkänning är inte provlagning, produktspecifik näringsfakta
eller ett permanent köp-/allergengodkännande.

## Körbara kommandon

Kör från repositoryroten med Python 3.12 och `PYTHONPATH=backend;.` på Windows
(`backend:.` på Linux). Gemensam CLI (även `python -m app.services.meal_library_cli` i appimagen):

```powershell
$env:PYTHONPATH='backend;.'
python scripts/recipe_layer/library.py validate paket.json --output validation.json
python scripts/recipe_layer/library.py diff paket.json --output diff.json
python scripts/recipe_layer/library.py import paket.json --output import.json
python scripts/recipe_layer/library.py prepare --output preparation.json
python scripts/recipe_layer/library.py qualify --pack paket.json --universe universe.json --clock 2026-10-05T10:00:00+00:00 --allow-nutrition-estimates --output qualification.json
python scripts/recipe_layer/library.py build --output bibliotekskandidat
```

Importera före kvalificering så att exakt utfärdad version finns i registret.
Kvalificering kör PersonalPlanner, mängder, köpvillkor och oberoende audit.
Utan `--protein` anges inget uppfyllt proteinmål; en numerisk makrokontroll
med noll minima ger näringsunderlag separat från 30/40-godkännande.
Äldre prisdatum ska uttryckligen kallas berikad historisk replay.

Konflikt: samma ID/version/variant med olika innehåll stoppas. Oändrade
objekt och identiska dubbletter redovisas; omimport förändrar inte manifestet.
Ny version behåller tidigare utfärdade versioner för sparade planer.
Den högsta numeriska innehållsversionen används för samma grundrätt/variant.
Ett paket med en oförändrad äldre version återaktiverar den inte.
Avvisningar sparas med fil, fält, ID och orsak. Vid avvisningar publiceras
bara en uttrycklig `--accept-id grundrätt:version:variant`-delmängd.
Hashnamnat paket skrivs före atomiskt manifestbyte; ingen halvimport exponeras.

## Beroenden och återanvändning

Receptstruktur förbereds per exakt innehåll. Portionsskalning förbereds per
innehålls- och metodversion. Ingrediensindexet i preparation.json anger vilka
recept som berörs av en råvaruändring. Produktdeklarationer förbereds per hela
inventariet och faktaversionen. Katalogprojektioner återanvänds först efter
kontroll av varje refererad råfils hash och de exakta databaskopplingarna.
Nya tidigare saknade produkter ändrar nyckeln även när ett gammalt resultat
var negativt. Pris, kampanj, datum, kanal, medlemskap, skafferi och aktuella
måltidskrav prövas fortfarande i den gemensamma veckovägen och slutliga audit.

Beständig lagring följer PlanStore-mappens `recipe_prepared`, eller en
operatörsvald `RECIPE_PREPARATION_CACHE_ROOT`. JSON-kuvert verifierar schema,
nyckel och payloadhash. Fel/partiella filer återberäknas säkert. Kapacitet:
32 MiB per typ, högst åtta käll-/skalningsgenerationer och 4096 strukturrader.
Vid fullt eller skrivskyddat utrymme fortsätter vanlig kontroll i minnet;
äldre bevis raderas inte. Ingen bakgrundstjänst eller produktionsinsamling.

Gamla anrop utan `recipe_choices` behåller tidigare middags-/profilsemantik.
Nya måltidsval använder samma enums, slots och gemensamma veckokorg.
`max_same_base_meals` räknar måltidstillfällen per stabil grundrätt.
Middagens köks- och huvudproteinkrav gäller fortsatt middagar. Proteinmål är
frivilliga och tillämpas per måltidstyp. Noll tillfällen skapar inga behov.
