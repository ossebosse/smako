# City Gross: representativa produkt- och receptköp

Verifiering den 23 september 2026, helt utan nätanrop. Slutparser v4 och ordinarie kommunprovider → OWN → full PriceUniverse-byggare → ProductMatcher → befintlig användarprisning → BasketCalculator → BasketAuditor. Inga priser har kopierats mellan butiker. Båda butikernas källor läses separat.

| Butik | Käll-ID / fysisk site | OWN / PriceUniverse | Penne Rigate 4 × 500 g | Receptets varukorg |
|---|---|---:|---:|---:|
| Malmö Hyllie | 3211 / 169 | 13523 / 13523 | 50.00 kr | 67.35 kr |
| Staffanstorp | 3229 / 11 | 13780 / 13780 | 50.00 kr | 67.35 kr |

Alla redovisade produkt- och receptkorgar passerar normal matcher, checkout och oberoende audit. Byggarna har noll externa nätförsök och oförändrade indata. Hyllie använder immutabel artefakt från runtimeprovets andra ordinarie rebuild; Staffanstorp har en separat full OWN-only-byggning. Artefaktens källa, SHA-256 och universe-ID finns i `purchases.json` och `purchases-*/used-artifact.json`.

## Exakta produktköp

### Malmö Hyllie (3211)

- [Penne Rigate](https://www.citygross.se/matvaror/skafferiet/pasta-ris-och-mos/garant-penne-rigate-p101548709_ST), variant `101548709_ST`, 500 g: fyra paket kostar 50.00 kr. Ordinarie enpaketspris 14.10 kr. Originalens kampanjdatum och villkor finns bevarade i JSON.
- [Pasta Carbonar](https://www.citygross.se/matvaror/fryst/fryst-fardigmat/findus-pasta-carbonar-p101548097_ST), 1100 g: utan medlemskap 70.90 kr; med City Gross Prio 54.95 kr. Samma delade produktdata, endast begärans medlemskontext ändras. Detta är ett uttryckligt köp av den namngivna varan, inte ett ingrediensutbyte i recept.
- Separat butiks-/produktbundet köptak: 25 paket Penne godkänns för 314.10 kr; 26 paket avvisas. Taket är 25 köpta förpackningar och hålls separat från kampanjens antal per rabattgrupp. [Officiell UI-källa](https://www.citygross.se/static/js/main.07a64bf6.js).

### Staffanstorp (3229)

- [Penne Rigate](https://www.citygross.se/matvaror/skafferiet/pasta-ris-och-mos/garant-penne-rigate-p101548709_ST), variant `101548709_ST`, 500 g: fyra paket kostar 50.00 kr. Ordinarie enpaketspris 14.10 kr. Originalens kampanjdatum och villkor finns bevarade i JSON.
- [Tekaka Ljus](https://www.citygross.se/matvaror/brod-och-bageri/brod/city-gross-tekaka-ljus-p101827449_ST), 70 g: utan medlemskap 5.60 kr; med City Gross Prio 3.95 kr. Samma delade produktdata, endast begärans medlemskontext ändras. Detta är ett uttryckligt köp av den namngivna varan, inte ett ingrediensutbyte i recept.
- Separat butiks-/produktbundet köptak: 25 paket Penne godkänns för 314.10 kr; 26 paket avvisas. Taket är 25 köpta förpackningar och hålls separat från kampanjens antal per rabattgrupp. [Officiell UI-källa](https://www.citygross.se/static/js/main.07a64bf6.js).

## Befintligt recept: Tomatpasta med ägg och gul lök

Oförändrat sparat recept, två portioner, från den befintliga receptpoolen. Ingen receptgenerator eller näringsuppskattning användes. Detta verifierar varuköp och prisavtal, inte en ny näringskvalificerad 15/20-meny eller en besparing.

| Ingrediensbehov | Köpt produkt | Förpackningar | Hyllie / Staffanstorp |
|---|---|---:|---:|
| ägg 4 st | Ägg 6P Frigående Inomhus | 1 | 16.50 / 16.50 kr |
| pasta 200 g | Penne Rigate | 1 | 8.50 / 8.50 kr |
| gul lök 150 g | Lök Gul i Påse | 1 | 11.95 / 11.95 kr |
| krossade tomater 300 g | Tomater Krossade | 1 | 8.45 / 8.45 kr |
| tomat 200 g | Tomater Babyplommon | 1 | 21.95 / 21.95 kr |

Färsk tomat är uttryckligt vald ur City Gross källkategori `Frukt & grönt > Grönsaker > Tomater`, och passerar fortfarande samma matcher och audit. Det befintliga generella tomaturvalet tillåter även passerade tomater; därför får det fria lägsta-prisresultatet 53,85 kr inte användas som receptbevis här. Det korrekta avgränsade provet ovan kostar 67,35 kr per butik. Den allmänna matcherluckan redovisas och har inte byggts om som sidouppgift.

Receptets instruktioner nämner redan basvarorna vatten, salt, peppar och neutral olja. Provet omfattar exakt receptets fem registrerade inköpsingredienser; inga nya näringsfakta eller basvarupriser har fabricerats.

## Tester

`backend/tests/test_citygross_municipality_provider.py`: sju fokuserade regressioner passerar, inklusive två tester av ordinarie OWN-sökning och helkatalogens bevarande: riktig OWN-intern butiks-UUID → officiellt storeNumber; förlustfri PriceUniverse-rundtur med cap25 och officiell URL; fel butik på en rad; fel snapshot; grannkommunsurval samt bevarad annan kedja vid nollurval. Fixtures är verkliga rader i ett uttryckligt begränsat replaykuvert och en fast testklocka, inte nya nätobservationer. Kommun-/collector-/fallbacksvit: 18 tester PASS. Ruff och compileall PASS för berörda egna filer.
