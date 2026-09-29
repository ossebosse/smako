# Willys reklambladsbutiker – separat releaseunderlag

Kod och källbevis för ett frivilligt kommunstyrt `offers_only`-tillskott. Båda kommunernas isolerade driftprov är PASS; 118 unika riktade testfall har godkänt senaste utfall. Ingen produktionsaktivering eller ändring av Windows-uppgift/aktiva scheman ingår. Slutlig maskinläsbar verifiering finns i `RESULT.json`, respektive `runtime-final-1281/ACCEPTANCE.json` och `runtime-final-1280/ACCEPTANCE.json`. Kodpaketet och jämförelsen med tillståndet vid uppdragets start finns i `PACKAGE.json` och `package-code/`.

## Officiell inventering och faktisk insamling

Willys befintliga officiella `/axfood/rest/v1/store` hämtades på nytt. 258 registerrader bevaras, inklusive en olöst rad; de 257 parsade butikerna prövas med gemensam kommungeometri. SCB-bevisen återanvänds med ursprunglig observationstid. `inventory-1281/inventory.json` och `inventory-1280/inventory.json` redovisar urval, utanför kommun, okänd tillhörighet och orsaker. Ingen hårdkodad produktionslista eller ändring av användarprofiler/butiksval används.

Varje vald butiks egen aktuella officiella reklambladslänk hämtades. Källformatet är publik iPaper med dokumenttext och nedladdningsbar text-PDF; inget separat strukturerat produktflöde upptäcktes. Sex Hemma-butiker länkar självständigt till samma fyrsidiga publikation. Rosengård länkar till en annan tolvsidig publikation. Vi antar inte nationell giltighet från liknande produkter eller priser.

| Kommun | Butik / ID / officiell källa | Sidor | Textannonser → expanderade poster | OWN | Aktuell PriceUniverse | Karantän |
|---|---|---:|---:|---:|---:|---:|
| Lund 1281 | [Hemma Lund Stortorget 2863](https://reklamblad.willys.se/willys/2863/) | 4 | 34 → 39 | 21 | 21 | 18 |
| Malmö 1280 | [Hemma Malmö Lindängen 2843](https://reklamblad.willys.se/willys/2843/) | 4 | 34 → 39 | 21 | 21 | 18 |
| Malmö 1280 | [Hemma Malmö Lugnet 2851](https://reklamblad.willys.se/willys/2851/) | 4 | 34 → 39 | 21 | 21 | 18 |
| Malmö 1280 | [Hemma Malmö Möllevången 2870](https://reklamblad.willys.se/willys/2870/) | 4 | 34 → 39 | 21 | 21 | 18 |
| Malmö 1280 | [Hemma Malmö Söderkulla 2865](https://reklamblad.willys.se/willys/2865/) | 4 | 34 → 39 | 21 | 21 | 18 |
| Malmö 1280 | [Hemma Oxie Centrum 2879](https://reklamblad.willys.se/willys/2879/) | 4 | 34 → 39 | 21 | 21 | 18 |
| Malmö 1280 | [Willys Malmö Rosengård 2352](https://reklamblad.willys.se/willys/2352/) | 12 | 112 → 118 | 61 | 60 | 57 |

Samtliga sju är verifierat `inside`, `onlineStore=false` och lyckades med fysisk reklambladsinsamling. OWN-snapshotarna innehåller sammanlagt 187 kvalificerade variantposter. Efter verklig midnatt till 24 september finns 186 aktuella: Rosengårds Triumf Glass Leo's Djungelmix 15-pack gällde endast 21–23 september. `midnight-expiry.json` visar att exakt den posten försvann och att Malmös 165 övriga poster är oförändrade. Förfall är inte karantän eller förlorad observation.

Antal textannonser och produktvarianter är olika nämnare. Alla 34 respektive 112 identifierade textannonser granskades. Hemma har 16 köpbara annonser som ger 21 varianter; Rosengård 55 som ger 61. En upprepad gurkannons räknas som dubblett i varje utgåva. De fullständiga besluten finns i det versionsbundna bevisregistret och varje butiks `result.json`. Uppgifter som bara finns i bilder är inte bedömda; full bildannons-/sortimentstäckning påstås inte.

### En huvudorsak per bortfallen annons

| Orsak | Per Hemma-utgåva/butik | Rosengård |
|---|---:|---:|
| Viktvara utan verifierad fast köpförpackning i detta kontrakt | 6 | 11 |
| Ouppräknade varianter eller förpackningsintervall | 4 | 33 |
| Pantbelopp och variant otillräckligt belagda | 3 | 4 |
| Förpackningsmängd saknas | 1 | 2 |
| Netto-/avrunnen mängd inte uttryckligt åtskild | 0 | 2 |
| Styckeköp utan ordinarie pris stöds inte av befintligt köpavtal | 3 | 4 |
| Dubblett | 1 | 1 |
| Summa | 18 | 57 |

De sex identiska Hemma-utgåvorna ska inte räknas som sex olika nationella annonsmängder. Varje fysisk butik och dess egna prisrader räknas däremot separat. Kända köpbegränsningar delas över recept och tillämpliga butiker. Vi har inte infört en ny prissättare för vikt- eller styckeannonser.

## Tre källbelagda exempel per butik

Samtliga exempel gäller **21–27 september 2026**, i respektive fysisk butik, för **Willys Plus**, **max 3 köp/hushåll per erbjudande**. Reservation för slutförsäljning och tryckfel. Rosengårds dokument anger även möjliga lokala avvikelser; dess egen butikslänk bekräftar aktuell utgåva. Ingen pant är tillämplig på dessa tre förpackade livsmedel. Ordinarie köppris förblir okänt.

| Butik | Pågenlimpan, Pågen 900 g | Kycklingbröstfilé Sverige, Kronfågel 900 g | Pizzadeg, Monte Castello 400 g |
|---|---:|---:|---:|
| [Stortorget 2863](https://reklamblad.willys.se/willys/2863/) | 24,90 kr/förp | 99,90 kr/förp | 12,90 kr/förp |
| [Lindängen 2843](https://reklamblad.willys.se/willys/2843/) | 24,90 kr/förp | 99,90 kr/förp | 12,90 kr/förp |
| [Lugnet 2851](https://reklamblad.willys.se/willys/2851/) | 24,90 kr/förp | 99,90 kr/förp | 12,90 kr/förp |
| [Möllevången 2870](https://reklamblad.willys.se/willys/2870/) | 24,90 kr/förp | 99,90 kr/förp | 12,90 kr/förp |
| [Söderkulla 2865](https://reklamblad.willys.se/willys/2865/) | 24,90 kr/förp | 99,90 kr/förp | 12,90 kr/förp |
| [Oxie 2879](https://reklamblad.willys.se/willys/2879/) | 24,90 kr/förp | 99,90 kr/förp | 12,90 kr/förp |
| [Rosengård 2352](https://reklamblad.willys.se/willys/2352/) | 24,90 kr/förp | 99,90 kr/förp | **2 för 25 kr** |

Rosengårds pizzadeg kräver två förpackningar per köp; tre köp ger högst sex förpackningar. Ett udda överblivet paket får inte få ett gissat styckpris. Hemma har ett separat styrkt styckpris och högst tre förpackningar. Angivet lägsta 30-dagarspris (Hemma 16,90, Rosengård 13,90) bevaras i originalvillkoren men används inte som dagens ordinarie köppris.

`verify_purchases.py` prövar dessa tre produkter i varje butik på publicerade produkter genom riktig ingrediensmatchning, medlemskontext, checkout och audit: tre köp i Lund och arton i Malmö, sju verkliga butiker. Fjärde Pågenlimpan-paketet över recept/butiker blockeras; tre kostar 74,70 kr. Icke-medlemsköp och utgången kampanj saknar giltig fallback och blockeras. Inga besparingar har framtvingats.

Det ordinarie lagret för godkända produktfakta har kontrollerats. Dessa dokument-ID:n saknar belagd GTIN/online-SKU-koppling till en godkänd deklaration. Ingen sådan koppling eller näringsvärden gissas. Strikt näringsprövning för ett recept underkänns där deklaration saknas, även när köppriset är korrekt. Det är ett särskilt receptgodkännande, inte ett prisfel.

## Drift, nätverk och tester

Faktisk slutinsamling: `final-live-1281/collection` gjorde **3** publika erbjudandeanrop; `final-live-1280/collection` gjorde **10**. De omfattar varje butiks sida och respektive verifierad PDF-väg. Registerhämtningen är separat. Tidigare källundersökning/development-prober är inte inräknade i dessa 13. Rawbevis, verkliga observationstider, databaser och snapshots är bevarade. Lyckad källväg är densamma i slutpaketet; senare ändringar avser stopp efter åtkomstfel, blandade köp och faktacache.

De isolerade driftproven använder avsedd ordinarie runner → riktig CLI-process → build/validering → atomisk publicering → riktig HTTP-reload i en lokal applikation. Externa nätanrop är blockerade under driftproven. Hämtresultat där är uttryckligen oförändrad replay av de verkligt hämtade OWN-databaserna, och felprovet är injicerat. Eventuellt förfallet City Gross-arbete använder också markerad replay. Det är inte en ny faktisk insamling av andra kedjor.

Bevisen skiljer första publicering, andra uttryckliga ordinarie rebuild, ny applikationsprocess med beständigt kommunval, behovskontroll utan arbete/anrop, hämtfel med giltig LKG och återhämtning. Testklocka +49 timmar visar att gamla observationer spärras och arbete blir förfallet. Den korta glasskampanjen verifierades dessutom över verklig midnatt. Första kontroll efter datumbyte kan ha faktiskt förfallet publiceringsarbete; först en efterföljande `not_due` utan barnprocess räknas som provet utan arbete.

Lunds giltiga bas innehåller 18 642 Willys onlineprodukter och sex Lidl-priser; reklambladet tillför 21. Basen är åldrande, och dess väntan på befintlig LOCAL_RELAY ger **degraded/exit 2**, öppet redovisat trots godkänd publicering och `/ready=200`. Malmös isolerade bas har 13 523 City Gross-produkter och 24 Lidl-priser; efter kampanjutgång tillkommer 165 Willys-priser. Detta är inte fullständig federerad Malmöbas. Övriga giltiga produktposter och observationstider bevaras mellan relevanta rebuilds.

Riktade tester täcker inventeringsurval/tamper, samtliga granskade poster, pris-/identitetsbevis, medlemskap, flerköp, hushållsgränser, utgång, åtkomststopp, beständig status, validering/publiceringskvitto och befintliga pris-/faktaavtal. Sammanräkning utan dubbelräkning och senaste utfall finns i `RESULT.json`. Ruff och compileall passerar. Mellanliggande misslyckade prov har sparats och räknas inte som godkända: fel i första testfixturen, blandad köpberäkning, flyttalsassertion, förväxling av förfallet/icke-förfallet testläge samt två befintliga cacheidentitetsassertioner. Inga acceptansgränser eller färskhetsregler sänktes.

Två små gemensamma korrigeringar behövdes: blandade korgar bevarar redan beräknade vikt-/styckeköp när ett fastförpackat erbjudande saknar ordinarie pris; faktalagret behåller sitt befintliga cacheobjekt när ingen Lidl-deklaration ska läggas till. Willys publiceringsgrind skiljer dessutom onlinekontexter från nya fysiska reklambladskontexter utan att bredda onlineurvalet.

## Automatik, nästa uppdatering och kvarstående releasekontroller

Automatiskt: officiellt kommunurval, butikens källkoppling, hämtning av granskad utgåva, validering, OWN/PriceUniverse, kampanj-/behovsstyrning, LKG/felbackoff och publiceringsstatus. Manuellt: textgranskning och nytt versionsbundet bevisregister när publikationen/PDF-hashen ändras. Okänd utgåva stannar säkert; bildberoende eller oklara annonser stannar utanför köpimport.

Nästa kontroll per butik och 48-timmarsstopp anges med exakta tider i `RESULT.json`. Efter återhämtningsprovet har alla sju butiker ordinarie 35-timmarskontroll cirka **25 september 10:37 svensk tid**. Rosengårds tidigare kampanjövergång har passerat och behandlats i rebuild och markerad replay efter midnatt; nästa kontroll beräknas fortfarande från den verkliga observationen den 23 september. Ingen observation föryngras i replay. Detta är status i den privata körmiljön, ingen bokad/aktiverad produktionskörning.

Lunds befintliga onlinebas behöver en verklig godkänd uppdatering före sitt 48-timmarsstopp, tidigast **24 september 01:31:28 svensk tid**. Befintlig Lidl-källkontroll är **25 september 04:28 svensk tid**. Ny Willys- eller Lidl-kampanj kräver granskning. Det fullständiga Malmö-publiceringsprovet med aktuell komplett bas kvarstår som separat releasekontroll.

Lidl-pilotens avgränsning och det saknade historiska näringstestets exakta skydd/lucka finns i [LIDL-AVGRANSNING.md](LIDL-AVGRANSNING.md). De tre godkända av 380 har exakt granskad produkt–kampanjbindning. Övriga 377: 348 saknar sådan granskning, 27 har oprövat prisfält, en oprövat rabattvillkor, en intervall/approximation. Ingen teknisk gräns på tre finns; den manuella bevismängden är däremot begränsad. Det historiska testet kan fortfarande inte samlas in och räknas inte som passerat. Tidigare ICA-, Coop/X:-tra-, City Gross-, Willys online-, Lidl- och Primat-arbete samt releaseunderlag bevaras.
