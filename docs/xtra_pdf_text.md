# X:-tra: avgränsad textimport från officiell PDF

Opt-in-policy `coop-xtra-pdf-text-v1`, parser `xtra-pdf-text-v1`. Ingen standard-
connector, serverkonfiguration eller aktiv källa växlas. Första verifierade
butiken är Skansvägen: Coop-ID 3658, X:-tra PDF-konto 216525.

## Körning och beroenden

Python 3.12 och projektets vanliga beroenden, samt befintliga **PyMuPDF 1.28.2**.
Det sistnämnda finns redan i `grocery_data/requirements-flyer-vision.txt`, men
denna adapter använder endast PDF-text, teckensnitt och koordinater. Ingen
bildmodell, OCR, modellserver, API-nyckel eller betalt anrop behövs. Inget paket
installerades under verifieringen. En miljö utan PyMuPDF behöver installera
det paketet i sin separata testmiljö; andra connectors importerar inte paketet.

Kör från den separata arbetskopians rot. Välj en **ny** utmatningskatalog:

```powershell
$env:PYTHONPATH='backend;.'
$env:PYTHONIOENCODING='utf-8'
py -3.12 -m grocery_data.scripts.import_xtra_pdf_text --inventory reports/coop-municipality-20260921/acceptance/inventory/inventory.json --source-metadata reports/coop-municipality-20260921/acceptance/xtra-3658/result.json --pdf reports/coop-municipality-20260921/acceptance/xtra-3658/source.pdf --output reports/xtra-text-20260922/new-isolated-run
```

Kommandot läser en redan officiellt hämtad PDF och dess observation. Det gör
inga externa nätanrop. Det skapar en egen SQLite/OWN, råbevis och PriceUniverse,
använder befintlig RefreshRunLock och vägrar skriva över tidigare körning.
Källobservation över 48 timmar eller i framtiden stoppar aktuell acceptans.
När dokumentet blir gammalt måste befintlig officiell hämtning ge nytt underlag;
ändra aldrig metadata för att kunna återköra detta kommando som aktuell acceptans.
Historiska regressioner använder separat uttrycklig testklocka.

## Bindning och extraktion

Kommuninventeringens godkända butik, adress, officiella X:-tra-butikssida och
dess faktiska dr.coop.se-konto måste stämma. PDF-titel, byteshash, råsvarets URL,
butiks-ID, observationstid, sidantal, tryckt vecka/datum och varje sidas
utgåve-ID kontrolleras. Årtalet kommer från dokumentets metadata och kontrolleras
mot tryckt vecka/utgåvekod; ingen gissad måndag eller ny observation skapas.

Parsern använder dokumentmallens typsnitt och koordinater för rubrikrader,
kolumner, brödtext, stora köppriser, separata decimaler och köp-/medlemsmärkning.
Detta är ett mallkontrakt, inte en lista med produkter eller närmaste-text-sökning.
En entydig köpprisplacering måste dessutom stämma med tryckt jämförpris och
belagd fast förpackning. Sparbelopp och jämförpris används inte som köppris.
Annonsen behåller råtext, textblock, koordinater, sida/ruta, dokumenthash,
referensetiketter och gemensamma villkor. Helgdatum begränsar veckoperioden.

`pdf:<sha256>:pN:adN` är en källbunden annonsidentitet, **inte ett GTIN**.
Inget fuzzy GTIN-/variantpris förs över. Samma dokument kan därför tolkas igen
utan att skapa en ny källobservation; ny dokumenthash kräver ny kvalificering.
Bevis om samma kampanj över olika dokument saknas och automatisk sådan
sammanslagning ingår inte i detta kontrakt.

## Importgräns

Samma SourceOffer → collector → OWN → provider → PriceUniverse → matcher →
checkout/audit som fysisk Coop. Separat opt-in-policy i befintligt partiellt
radkontrakt, ingen parallell prissättare. Inget ordinarie köppris skapas.
Alla prisannonser behålls som extraherade uppgifter även om konkret köp spärras.

Belagd fast g-förpackning och entydig annonsvariant kan godkännas. Generella
variantgrupper, ca-/intervallvikter, osäkra multipack, obelagd pant, okända
behörighetsvillkor och jämförpriskonflikter spärrar köp. Alla vätskor spärras
konservativt tills behållare/panttillämplighet är belagd; detta är inte ett
påstående om pantplikt för alla vätskor. Kilopriser bevaras utan fabricerad
fast paketvikt. Begränsade medlemsköp spärras tills gemensam kampanjidentitet
över butiker är belagd; PDF-hash räcker inte som delat hushållstak.

Oplacerat medlems-/kritiskt villkor spärrar berörd sida. Fel butik, källhash,
period/utgåva eller sidantal spärrar hela dokumentets kandidat. Fullständigt
snapshotkontrakt använder fortsatt 95 % och redovisas oberoende av partiell
radpublicering. Ingen butik får annonseras som komplett.

Bildinnehåll läses inte. Antalet okända ytterligare annonser är därför `null`,
inte noll. Ett fungerande textavtal verifierar inte alla framtida PDF-mallar.

## Tester och faktisk verifiering

```powershell
py -3.12 -m pytest grocery_data/tests/test_xtra_pdf_text.py grocery_data/tests/test_offer_rows.py -o addopts='' -q
```

Verklig sparad åttasidig PDF och separat textreferens ligger under
`grocery_data/tests/fixtures/xtra-text-20260921/`. Testerna täcker produkt/pris-
förväxling, källa/butik/hash, partiell import, förpackning, medlemskap, oplacerade
små villkor, gemensamma hushållstak, framtida/utgångna priser, flerköp utan
restpris och oförändrad observationsålder. Rapporter och slutkodens isolerade
resultat: `reports/xtra-text-20260922/`.
