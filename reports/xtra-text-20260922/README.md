# X:-tra textimport – faktisk isolerad verifiering 22 september 2026

**Genomfört, inte produktionsaktiverat.** Arbetskopian är fortsatt
`municipality-coverage-20260920`, gren `areas/municipality-audit-20260920`,
HEAD `02ad73b8491f4b30679b3151b52686e27bedb8e6`. Ärvt ocommittat arbete bevaras.

Slutkodens körning: **07:46:32 Europe/Stockholm**. Original-PDF:en hämtades
**21 september 19:56:02 Europe/Stockholm** och var **11,842 timmar** gammal.
Detta är en ny texttolkning/import av faktiskt källmaterial, **ingen ny
nätinsamling eller föryngring av observationen**. Noll externa anrop, modeller,
OCR eller betalda API-tjänster. Källan var både färsk och kampanjgiltig vid provet.

## Resultat

| Underlag | Extraherade | Isolerat OWN | PU för 22 september | Blockerade/avgränsning |
|---|---:|---:|---:|---|
| X:-tra Skansvägen, åtta PDF-sidor | 57 identifierade textannonser | 10 | 9 | 47 köpblockerade; 1 framtida i OWN; ytterligare annonsantal okänt |
| Nio Coop/Stora Coop, bevarade svar | 2 436 butik–varianter | 499 | 493 | 1 937 karantän; 6 Stora-erbjudanden utgångna efter 21 september |

X:-tra-kedjan kördes på **1,892 s** inklusive collector, OWN, PriceUniverse och
fyra matchningsprov. Couscous 500 g/15 kr, tomatpuré 2 × 200 g/30 kr och gul lök
3 kg nät/19,90 kr passerade matchning, checkout och audit. Honung 350 g/30 kr
nådde PU men matchningen till ingrediensen honung avvisades. Inga matchnings-
eller näringsregler har ändrats för provet. Toalettpapper finns som korrekt
prispost, inte som verifierad receptprodukt.

Källan är [X:-tra Skansvägen](https://x-tra.se/butiker/skansvaegen), fysisk
butik 3658, konto 216525: [officiell PDF](https://dr.coop.se/Butik/?store=216525).
Tryckt period 21–27 september; sida 8 först 24–27 september. Referenspriser
är bevarade som referenser, ordinarie köppris och GTIN förblir null.

**[Alla sidor och annonser, exempel och exakta hinder](COVERAGE.md)**.
Maskinläsbar sammanfattning: `coverage-final.json`. Varje annons med textblock,
koordinater, källa, period, prisroller och OWN/PU-koppling finns i
`final-acceptance/result.json`; normaliserade SourceOffer i `source-products.json`.
Den sparade original-PDF:en finns i föregående rapports `acceptance/xtra-3658/`
och som byteidentisk regressionstestfixtur.

## Implementerat och testat

- Ny återanvändbar adapter för den belagda textmallen; inga handskrivna
  produkt-/prislistor i extraktion/import. Endast verifieringsproven väljer titlar.
- Befintlig collector/partiellt radkontrakt och OWN-provider. Samma backend-
  matcher, PriceUniverse, checkout och audit; inga nya parallella datamodeller.
- Full snapshot förblir BROKEN, **10/57 = 17,54 %**, 95 %-gräns oförändrad.
  Endast tio självständigt godkända rader publiceras i isolerad databas.
- Gemensamma butik/hash/datum/sidfel blockerar dokumentet. Oplacerat kritiskt
  villkor blockerar sidan. Ändrat pris/förpackning/medlemskap får inte återanvända
  gammal annonsbindning. Framtida/utgångna köp, fiktiva restpriser och osäkra
  gemensamma hushållstak stoppas.
- 125 berörda tester PASS på 49,55 s. Efter sista tillägget: 20 berörda
  X:-tra/radkontraktstester PASS på 16,58 s, inklusive ett nytt test; totalt
  126 unika testfall. Ruff och compileall PASS. Verklig PDF används i regressioner;
  historiska testklockor skiljs från ovanstående faktiska körning.
- Coop återimporterad med 499 godkända, 1 937 karantän och 25 audit-PASS på
  21,077 s. Ursprungliga 27 köpbevis bevarade; två ytterligare Stora-köp återanvänds
  som tidigare hashstabil verifiering. Exakta sex utgångna poster listas i
  `coop-regression/expired-difference.json`.

## Reproduktion

Se [körbar adapter, beroenden och kontrakt](../../docs/xtra_pdf_text.md).
Använd ny outputkatalog och originalets riktiga observation. Kommandot vägrar
aktuell acceptans efter 48 timmar; historiska tester kan köras senare.

```powershell
$env:PYTHONPATH='backend;.'
$env:PYTHONIOENCODING='utf-8'
py -3.12 -m grocery_data.scripts.import_xtra_pdf_text --inventory reports/coop-municipality-20260921/acceptance/inventory/inventory.json --source-metadata reports/coop-municipality-20260921/acceptance/xtra-3658/result.json --pdf reports/coop-municipality-20260921/acceptance/xtra-3658/source.pdf --output reports/xtra-text-20260922/new-isolated-run
py -3.12 -m pytest grocery_data/tests/test_xtra_pdf_text.py grocery_data/tests/test_offer_rows.py -o addopts='' -q
```

Coop-regressionen kördes med befintliga `reports/coop-municipality-20260921/verify_isolated.py`,
`--input reports/coop-municipality-20260921/final-sources` och
`--output reports/xtra-text-20260922/coop-regression`. Detta är replay med verkligt
aktuellt inköpsdatum, inte nya prisobservationer. Collector-måttet `request_count`
räknar de återspelade råbatcherna; faktisk nättrafik i denna etapp är noll.

`pilot`, `full-check`, `acceptance` och `parse-*` är bevarade mellanresultat.
Endast **`final-acceptance`** är X:-tra-slutkodens acceptans. Summera inte
förkörningarnas tio poster som nya priser; det är samma källannonser och observation.

## Separata releaseunderlag

- **[Coop – nio butiker, 499 bevarade godkända källposter](RELEASE-COOP.md)**:
  behöver inte vänta på X:-tra/karantän. Exakta återstående 15/20-steg anges.
- **[X:-tra – separat partiell textkandidat](RELEASE-XTRA.md)**:
  tio källprisposter; full reklambladstäckning och näringsgodkänd meny ej belagda.

Ingen helmeny eller besparing påstås. Ingen aktivering, Windows-/schema-/server-
ändring, ändring av Primat, Coop Online, ICA-baspaus eller väntande ICA-release.
Tilläggspatchen är mot sparad smutsig bas, inte ren HEAD; den har endast kontrollerats.
