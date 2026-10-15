# Receptingredienser och verifierade matvaror – 2026-10-15

## Status och avgränsning

Lokal rättning på `fix/recipe-product-links`, bas `37cd882`.
Ingen produktionsaktivering, prisinsamling, schedulerändring eller ändring av
användarens profil har gjorts. Produktionsdiagnostiken var skrivskyddad.

Användaren tillät alla butiker inom 3 km från 22225. Den publika
butiksupplösningen gav 19 priskontexter inom denna radie. Willys Lund
(`context:willys:383650ec6ff5a636`) ligger 2,62 km bort. Coop Online Syd
saknar fysisk distans och ingår inte i radieurvalet. Befintliga godkända
Coop-alternativ räckte därför inte för användarens urval.

Skärmbildens referens `5c8a5ed8-ca74-45cd-adf8-86d8f71984f1` motsvarar
HTTP 422 den 15 oktober 11:39:18 UTC, app `base-price-retention-app-0f54e51`.
Underlaget var
`price-universe:5539233425d7b341ad9e0785adad69e461893356e71eedd3b5a9bb6ab3642aed`
med 43 798 produkter och 42 265 faktaposter. Felet är ett avslag i
planeringen; separat undantagsbevis saknades.

## Orsak och rättning

- Sparade Willys-/Hemköpsrader hade verifierbara GTIN i officiella bildnycklar,
  men dessa användes inte för de befintliga Dabasdeklarationerna om mängd.
  Nu binds dessa till samma produkt, butik, källversion, varumärke och
  förpackning. GTIN måste ha korrekt kontrollsiffra.
- Märkningen `380/230g` hade redan projicerats till 230 g i produktunderlaget,
  medan leverantörens förpackningsuppgift var 380 g. Både nettovikt och
  avrunnen vikt måste nu överensstämma med den exakta leverantörsdeklarationen
  innan den användbara mängden godtas. Snedstrecket ensamt är inget bevis.
- Crème fraiches volym kan kopplas till receptets gram genom leverantörens
  uttryckliga massuppgift. Ingen allmän regel om att ml motsvarar g införs.
- Salt, crème fraiche, kalamataoliver och vissa färska tomatsorter saknade
  fullständiga namnregler. `Lök Röd i Påse Klass 1` hade dessutom felaktig
  gul-lök-klassning. Reglerna känner nu igen dessa hela produktnamn och
  avvisar fortfarande såser, smaksatta blandningar och andra livsmedel.
- Zeinas citronjuice saknade ingrediensunderlag. En exakt deklaration för
  namnet, varumärket och 200 ml-förpackningen har tillförts från
  [tillverkarens produktsida](https://zeinas.se/produkter/citronjuice/).
  Deklarationens citrusolja från den egna fruktens skal godtas endast vid
  uttrycklig juicehalt minst 99 procent. Andra oljor/socker godtas inte.

Faktaprojektionen versionshöjs till
`retained-catalog-facts-v10-supplier-package-link` så att gammal projektion
inte återanvänds som den nya. Priser, prisomfattning, originaltidsstämplar och
användarens butiksurval ändras inte.

Tillverkarkällan hämtades 2026-10-15T11:52:04.036679+00:00, HTTP 200,
SHA-256 `42f7adb908a13e24c930022eb74a24e8c6dd91d9391e461e92fa96405219d26f`.
Parsern verifierar käll-URL, dokumenthash, unik produkt, förpackning och
uttrycklig näringsbas. Full HTML ligger endast lokalt; registret innehåller
de relevanta produktfakta och källreferensen.

## Verifierat resultat

Autentiska sparade rader från Willys Lund löser samtliga sex ingredienser
som syns i skärmbilderna, med receptens egna form- och mängdkrav:

| Ingrediens | Verifierad produkt | Användbar mängd |
| --- | --- | --- |
| Citronjuice | Zeinas Citronjuice | 200 ml |
| Crème fraiche | Skånemejerier Crème Fraiche 32% | 200 g |
| Salt | Jozo Salt med Jod | 1 000 g |
| Bönor | Zeta Vita Bönor Stora Ekologiska | 230 g avrunnet |
| Kikärtor | Zeta Kikärtor Ekologiska | 230 g avrunnet |
| Oliver | Zeta Kalamata Oliver Urkärnade Ekologiska | 170 g avrunnet |

En lokal återspelning av hela **Färsbiffar med citronpotatis, tzatziki och
tomatsallad**, två portioner och en middag, passerade med endast Willys Lund
tillåtet. Alla 14 ingredienser hittades. Kassakontrollen gav `PASS`, inga
mängdbrister, noll okända mängder och avstämda totalsummor. Inköp av hela
förpackningar kostade 301,20 kr i det sparade prisunderlaget; detta är inte
portionskostnaden. Sparning och återläsning återgav identiskt recept.

Detta verifierar ett komplett av de visade recepten och de sex felande
ingredienserna, inte användarens exakta hela veckoplan. Övriga profilval är
inte kända. Återspelningen hade inga näringsgränser. Citronjuicens näring
anges av tillverkaren per 100 g medan förpackningen anges i ml. Ingen densitet
eller näring per ml har hittats på. Krav som behöver denna omräkning kan
fortfarande kräva mer verifierat underlag. Allergenkontroll intygas inte av
enbart ingredienskopplingen.

## Kontroller

500 olika riktade testfall passerade över tre överlappande körningar:
263 utökade, 232 fokuserade och 65 i slutkörningen. Den sista omfattade den
nya regressionen samt befintliga leverantörs- och bildidentitetstester efter
rättningen av hanteringen av ogiltigt GTIN. Ruff, compileall och
`git diff --check` passerade.

Testområden: semantik, mängdupplösning, officiella deklarationer, GoGreen,
hela recept, receptkällor, faktaprojektion, användbarhet, bild-GTIN och
receptpaket. Negativa fall täcker fel butik, produkt, källversion, varumärke,
förpackning, GTIN, mängdpar, tillagade produkter och näringskonflikter.
Tester kördes genom `scripts/verify_offline.py` med extern trafik spärrad.

Den beständiga regressionen finns i
`backend/tests/test_recipe_product_links.py` och åtta reducerade autentiska
produkt-/råfältsposter i `backend/tests/fixtures/recipe_product_links.json`.
Lokala diagnostik-, XML- och återspelningsfiler finns i den ignorerade
`.local/recipe-product-links/`. Dessa innehåller inga användarprofiler.

Vid en separat auktoriserad aktivering måste den nya faktaprojektionen laddas
och samma butiksurval verifieras i den verkliga appen. Lokal verifiering är
inte ett kvitto på produktionsaktivering.
