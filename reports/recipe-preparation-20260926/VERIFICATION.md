# Recept och beredning – mätt resultat, 26 september 2026

Historisk replay med samma kompletta bas, köpdag och medlemskontext inom varje jämförelse. Prisobservationer har inte ändrats. Inga produktlås, extraköp eller handpatchade kandidater.

| De ursprungligen blockerade recepten | Gamla versioner | Nya versioner |
|---|---:|---:|
| Nämnare | 84 | 84 |
| Beredningsgodkända med opt-in | 0 | 84 |
| Samtliga ingredienser når produkt-/köpmatchning | 0 efter beredningsgrinden | 48 |
| Når näringsprövning i varukorgen | 0 | 48 |
| Minst en korg får numeriskt näringsresultat | 0 | 39 |
| Näringsmål + varukorg + audit passerar separat | 0 | 19 |

Godkänd beredning är inte produkt-, närings- eller menyselektion. Samtliga original och nya definitioner, exakta mängdändringar, källor, avslag och godkända korgar finns i `profile/all-84.json`. Originalen jämfördes mot den tidigare rapportens ingrediensmängder och instruktioner, inte bara mot namn.

| 15/20: medlemskap / köpläge | Gamla recept: kr / s | Nya recept: kr / s | Valda av de 84, unika |
|---|---:|---:|---:|
| public / exact | 535.25 / 64.853 | 484.73 / 117.569 | 2 |
| public / estimated | 535.25 / 67.292 | 484.73 / 125.991 | 2 |
| plus / exact | 535.25 / 62.948 | 484.73 / 114.802 | 2 |
| plus / estimated | 535.25 / 65.372 | 484.73 / 125.724 | 2 |

40/30/20 g protein, 15 måltider/20 portioner, högst två inköpsställen är oförändrade. Gamla recept är en kodregression; de nya versionerna ändrar receptinnehåll och tillagning. En kostnadsskillnad mellan dessa pooler är inte en besparing för identisk mat. Körningstider är enstaka uppmätta körningar, inte ett statistiskt prestandatest. Butiker, kanaler, kvalitetsstatus, köprader, näringsstatus och valda produkter finns fullt ut i `summary.json`.

| HTTP-fall | Köpläge | Status | Kostnad | Sekunder | Korgkvalitet |
|---|---|---:|---:|---:|---|
| Varm Lidl-ostsmörgås | exact | 422 | – | 9.765 | spärrat |
| Varm Lidl-ostsmörgås | estimated | 201 | 171.68 | 4.015 | VERIFIED_WITH_ESTIMATES |
| Genererad tofumacka | exact | 201 | 107.64 | 13.598 | VERIFIED |
| Genererad tofumacka | estimated | 201 | 107.64 | 7.728 | VERIFIED |

Båda HTTP-proven använder ordinarie POST/GET och verklig backendprocessomstart med identisk återläst plan. Tofumackan är ett av de 84 tidigare spärrade recepten, med oförändrat 30 g proteinmål och ordinarie område/max två butiker. Varm ostsmörgås är ett separat nytt tillagningsfall: explicit Lidl-butik, Lidl Plus för brödet och det offentliga Arla-erbjudandet. Den räknas inte som ett 85:e återvunnet recept.

Arla köps som helt cirka 2,2 kg-paket för cirka 153,78 kr; 100 g används. Bröd 17,90 kr ger totalt cirka 171,68 kr. Näringsberäkningen använder 100 g ost och 100 g bröd, 33,8 g protein. Varm insatsberäkning är ESTIMATED även med verifierade deklarationer. Allergisäkerhet är inte begärd/bevisad. Exakt köpplanering spärrar cirka-osten.

## Vad som ändrats

- Versionerade definitioner för generatorns 15 varma mallar samt de fyra särskilda beredningsfallen. Originalen finns kvar som legacy och i varje fallrapport.
- Explicit rapsolja 5/7,5/10 ml per portion efter tillagningsmall; hela mängden räknas. Ägg och tortillas har nya massbaserade receptportioner, inte påhittade styckvikter. Crème fraiche vägs i de nya versionerna; ml har inte behandlats som gram i näringsräkningen.
- Gemensam operand-/instruktionsvaliderad insatsberäkning per portion. Ingen färdig rättvikt, retention, oljeupptag, densitet eller ätbar andel tillverkas.
- Verifierade deklarationer prioriteras; generiska SLV-referenser och skafferiformer behåller opt-in, källa och version. Ursprunglig evidenstyp följer den uppskattade tillagningsberäkningen.
- Komplett konservdeklaration får inte bli rå tomat. Äggkartongens vikt får inte bli ätbar äggmassa utan belägg. Köppris och näringsgodkännande hålls isär.
- Metodmetadata överlever API/PlanStore och ingår i receptidentitet/cacheunderlag.

## Kvarstående hinder

Exakta första stopp per recept finns i `all-84.json`. Ett sökavslag efter högst 256 näringskombinationer är en sökbegränsning, inte ett bevis om global omöjlighet eller högre pris. Sökning, produktdiagnostik och hela förpackningspriser är bevarade.

Ägg behöver belagd ätbar inköpsmängd eller direkt mätbar hel äggmassa; inga skal-/styckfaktorer har hittats på. Kikärtor behöver rätt produktbindning, avrunnen användbar inköpsmängd och avrunnen näringsgrund. Metoden stöder sådana belagda fält och SLV 3815 med rätt råvara; frysta källrader med bara nettovikt kvalificeras inte.

En separat officiell webbkällkontroll av Zeta visar 230 g avrunnen vikt; direkt dokumentarkivering gav HTTP 403. Inga nya värden eller produktkopplingar från denna kontroll har importerats i jämförelsen. Se `sources/zeta-check.json` och [officiell sida](https://www.zeta.nu/produkter/kikartor-ekologiska/).

Övriga stopp omfattar saknad köpbar ingrediens i basen, saknad passande enhet/deklaration och sökningar utan funnen målkompatibel korg. Inget fall har tagits bort ur nämnaren.

Färsk produktionsbas, fullständig Malmö-publicering och historisk Lidl-fixture är separata öppna uppgifter. Prisimporter, providers, PurchaseTerms, kommunfunktion, observationstider, scheman och sparade användarprofiler har inte ändrats. Ingen produktionsaktivering.

## Första stopp, utan dubbelräkning

| Orsak | Recept |
|---|---:|
| Köp/matchning: rödlök | 22 |
| Närings-/mängdbas: ägg | 5 |
| Ingen målgodkänd kombination funnen i begränsad sökning | 20 |
| Köp/matchning: svarta bönor | 3 |
| Köp/matchning: crème fraiche | 10 |
| Godkänd korg och näringsmål | 19 |
| Närings-/mängdbas: kidneybönor | 1 |
| Närings-/mängdbas: kikärtor | 2 |
| Närings-/mängdbas: blandfärs | 1 |
| Köp/matchning: bönor | 1 |

De fyra fria körningarna använder Coop Online Syd (online_fulfillment) och Willys Lund (online_store). Korgarna är VERIFIED: 12 exakta rader före, 16 efter, inga uppskattade eller villkorade köprader. Näring redovisas separat: 5 ESTIMATED och 10 VERIFIED måltider både före och efter.

De två nytillgängliga valda recepten är Tomatpasta med lax och gul lök samt Gryta med lax, nudlar och vitkål. Tofumackans HTTP-korg använder Coop Online Syd och fyra exakta rader; 36,4 g protein mot 30 g krav. Lidl-provet har en exakt och en uppskattad köprad.

Riktade regressioner: 179 godkända, inga fel eller överhoppade prov. Ruff och compileall passerar. Historisk Lidl-fixture ingick inte och kvarstår separat. För ägg, avrunna baljväxter och g/ml-varor återstår kvalificerade mängd-/faktakopplingar; de beskrivs inte som färdigställda genom metodstödet.
