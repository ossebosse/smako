# Oberoende granskning av energideklarationer, 2026-10-03

**Tidigare 94/104 är ett historiskt kvalificeringsresultat, inte ett slutligt näringsgodkännande.** Två hashbundna Coop-deklarationer innehåller grovt motstridiga kJ/kcal-par. De användes i 16 av de 94 recepten med näringsresultat, i tre av de sju menybevisen och i exakt tvåbutiksplan för HTTP-monotoniprovet. Ingen deklaration har korrigerats, bytts plats, dividerats eller ersatts med härledda makrovärden i denna granskning. Rätt åtgärd är konfliktspärr och ny vanlig kvalificering.

## Underlag och metod

- Bibliotekets innehållshash: `1c623aa7e4a8e8f9cde292807198c59d6f191f0dd3030462a254893995e7e90c`, bibliotek 1.4, 48 grundrätter och 56 variationer. Alla 104 har `cooking_test=not_cooked`; fysisk provlagning **0**.
- Granskad kvalificering: `qualification-release-final/qualification.json`, runtime `28bca2d057abed908436f2431eb45aeb0f0a90c0`, SHA-256 `2b6ffbd7da74359d38602ad7a663697dcbb64d8bcc273e35760dee83df46277d`.
- Alla 104 rader granskades: 94 hade kompletta näringsresultat, 10 stoppades tidigare och saknar komplett energisumma. Saknat resultat är okänt, inte noll eller godkänt.
- Avvikande måltidssummor undersöktes först med `4 × protein + 4 × kolhydrat + 9 × fett`. Detta är en grov sökhjälp, inte en full energiberäkning, ersättningsdeklaration eller godkännanderegel. Fiber och andra energigivande ämnen gör exakt likhet olämplig.
- Därefter följdes de valda ingrediensernas faktiska källreferenser till två exakta kvarhållna offentliga råfiler. Deras byteinnehåll verifierades mot det frysta manifestets SHA-256. Två små skrivskyddade filhämtningar omfattade totalt 207 201 byte. Ingen plannerberäkning, ny butikshämtning eller produktionsfil berördes. Hämtningarna överlappade pågående benchmark; de var fil-I/O, inte en jämförbar separat prestandakörning.
- De 78 övriga näringsresultaten använde ingen av dessa två produkter och hade kvot 1,0129–1,0936 mot sökhjälpen. Det bevisar inte att alla deras deklarationer är felfria. Samtliga 104 behöver därför köras om genom den nya generella källspärren.

De tidigare antalen var korrekt återgivna från rårapporten: **47/48 grundfamiljer hade minst en kvalificerad variant, 43/48 originalversioner och 94/104 versioner**. De tio första stoppen var två piccata-versioner på kaprisens köp-/mängdunderlag, två ursprungliga linschili-versioner på kidneybönornas köp-/mängdunderlag samt sex ursprungliga majsoppe-, färsbiffs- och ärtsoppeversioner på mjölkens oförenliga mängdenhet i näringsunderlaget. Dessa befintliga datastopp ska redovisas tillsammans med nya stopp efter energispärren; inga historiska antal är på förhand utlovade acceptansvärden.

## Exakta rådeklarationer

| Fält | Nötfärs 20% | Rostbröd |
| --- | --- | --- |
| Produkt-ID | `236d66dffc0f477cba9cb3d86c1e33df` | `ed6502c4a20a44c9a1aafd0eb2df997c` |
| GTIN, råpostens `id` | `7392055078800` | `7300156594488` |
| Ursprunglig mängdbas | 100 gram, `BY_MEASURE`, `GRM` | 100 gram, `BY_MEASURE`, `GRM` |
| `Energi` / `Kilokalori` / `amount` | `["1100"]` | `["1000"]` |
| `Energi` / `Kilojoule` / `amount` | `["250"]` | `["240"]` |
| Protein / kolhydrat / fett, gram | 17 / 0 / 20 | 8,2 / 47 / 1,7 |
| Råpost | `raw:3be0539e7859418c824adf8dd625d0cf#results.items[7]` | `raw:95396429272d4a62911d266a383d1157#results.items[38]` |
| Råfilens byteantal | 29 419 | 177 782 |
| Råfilens SHA-256 | `52605bf6b35206d202bac0084e4bd4146fb3dcd05af8aae901f93e94fdc88ef6` | `72f26a68f254ae53a5a01fe50586b26e6e4c4cd09950233d9b73afd3f7e17b97` |

Källreferensen i sparad plan är `coop:` följt av råposten och `:` följt av råfilens SHA-256. Båda posterna har ett enda deklarationshuvud; felet beror inte på portionsbas eller en felaktig gram-/milliliteromräkning i receptet. Kvarhållna filer ligger under det frysta underlagets `inputs/raw/coop/730400/512e0fab56674cce8498757944a8e119/`:

- `20261001T061226121181Z_0093_coop_product_category_page_deecaacd.json`
- `20261001T062433180626Z_0456_coop_product_category_page_523778e5.json`

Den tidigare adaptern, `retained-catalog-facts-v7-explicit-culinary-form`, valde det exakta fältnamnet `Energi/Kilokalori` men kontrollerade inte det andra energifältet. Det är ett källkvalificeringsfel. Etiketterna liknar omkastade enheter, men detta räcker **inte** för att fastställa eller automatiskt rätta den avsedda deklarationen.

## Berörda receptresultat

Beloppen nedan är **tidigare felgrundade kcal-resultat**, inte nya näringsvärden. Alla rader gäller två portioner. Prefixet `smako-` är utelämnat ur grundrecept-ID. Varianter utan `ribollita` eller `green-pea-soup` använder färsen; de fyra soppraderna använder brödet.

| Grundrecept | Variant | Berörd mängd i hela receptet, g | Tidigare kcal/portion | Berörd produkts tidigare kcalbidrag/portion |
| --- | --- | ---: | ---: | ---: |
| greek-keftedes | base | 340 | 2306,810 | 1870 |
| greek-keftedes | protein | 420 | 2746,810 | 2310 |
| italian-polpette | base | 340 | 2348,700 | 1870 |
| italian-polpette | protein | 420 | 2788,700 | 2310 |
| italian-ribollita | base | 120 | 1150,250 | 600 |
| italian-ribollita | protein | 120 | 1253,400 | 600 |
| mexican-beef-fajita | base | 320 | 2286,935 | 1760 |
| mexican-beef-fajita | protein | 400 | 2726,935 | 2200 |
| indian-keema | base | 340 | 2280,490 | 1870 |
| indian-keema | protein | 420 | 2720,490 | 2310 |
| thai-beef-broccoli | base | 340 | 2323,692 | 1870 |
| thai-beef-broccoli | protein | 420 | 2763,692 | 2310 |
| swedish-beef-patties | water-panade | 340 | 2447,760 | 1870 |
| swedish-beef-patties | water-panade-protein | 420 | 2887,760 | 2310 |
| swedish-green-pea-soup | creme-fraiche | 100 | 1197,290 | 500 |
| swedish-green-pea-soup | creme-fraiche-protein | 100 | 1311,140 | 500 |

Exempel: färsbiffarnas basversion använder 340 g färs för två personer. Den felgrundade deklarationen ger exakt `340 / 2 / 100 × 1100 = 1870` kcal/portion från färsen. Portionsdelningen fungerar; källan är orimlig. Detta fynd är inte ett belägg för orimlig råvarumängd eller dålig smakbalans i receptet.

## Påverkan på fulla meny- och HTTP-bevis

| Bevis | Direkt berört resultat | SHA-256 för full rårapport/plan |
| --- | --- | --- |
| `menus-release-final/indian-plan.json` | `dinner-4`, färs | `c942abb3aa835ca8bfdf59a7e9d8e05922655674bfc06c5d2d474fb7655997b8` |
| `menus-release-final/italian-plan.json` | `dinner-5`, bröd | `910fd0a1005b7312fb05daffc6e6826e23f1b6341002654d8991ed3945b707a3` |
| `menus-release-final/swedish-plan.json` | `dinner-5`, bröd | `1f68feda9b9dd6fda6ad558ac6c23dc062e39c4b054335055bd367e94a0e53f5` |
| `http-final-corrected/monotonic-scopes.json` | Exakt köp, två butiker, 777,15 kr: `dinner-5`, färs | `739503f588528c16a5644d5eaf550abd05ff262ef952108d9d00cb6d63007fa0` |
| Äldre `http-final/monotonic-scopes.json` | Samma exakta plan; redan ersatt av den korrigerade HTTP-körningen | `c1e917d6eec69287bc10153c190a04ecb975bd327a8053a5ce86cc3861d58618` |

Grekisk, mexikansk, thailändsk och blandad 40-g-proteinmeny använde ingen av produkterna i sina näringskällor. Den korrigerade monotonirapportens uppskattade tvåbutiksplan på 682,23 kr använde inte heller dessa produkter. Alla sju fria menyer bör ändå köras om utan låsta recept eller produkter: en källspärr kan ändra kandidatval och pris.

De övriga tio fulla positiva HTTP-planerna i `http-final` saknade båda produkterna i näringskällorna: `custom-ingredients`, `greek-pantry`, de fyra `legacy-1520-*`-fallen, `mixed-four`, `mixed-vegetarian`, `products-only` och `unrestricted-varied`. De stoppade fallen har inget fullständigt näringsresultat att godkänna. Resultat för korta statusanrop, åtkomstisolering, dubbelklick, validering och återläsning är separata funktionella observationer; de gör inte motstridig näring giltig.

De tre profilerade Varierad-planerna samt de kontrollerade kompletta kallplanerna från `packaged-complete-final` och `packaged-complete-ca57` använde inte dessa två produkter. Det bevarar deras historiska likhetsobservation, men en ny runtime behöver fortfarande egen versionsbunden verifiering. Den publika äldre planens avsaknad av personlig näringskvalificering ska inte räknas som ett nytt näringsgodkännande.

## Skilda kvalitetsnivåer och verifierat paketdelningsbevis

| Dimension | Vad granskningen visar | Vad den inte visar |
| --- | --- | --- |
| Receptkvalitet | 48 distinkta grundrätter; innehållsgranskning, portionsmängder, versionerade instruktioner, redskap och maskinella strukturprov | Ingen fysisk provlagning; faktisk smak, portionsupplevelse och uppmätt tid återstår |
| Källunderlag | Två exakta, reproducerbara deklarationskonflikter har identifierats; övrigt källunderlag måste prövas av samma nya regel | En korrekt GTIN-, pris- eller mängdmatchning bevisar inte korrekt näring |
| Köpbarhet | Tidigare 94 resultat hade godkänd korgaudit: 44 `VERIFIED`, 50 `VERIFIED_WITH_ESTIMATES` | Den nya källspärren kan ändra vilka kompletta recept och menyer som kvalificeras |
| Näring | Alla 94 tidigare resultat var `ESTIMATED`; 16 innehöll de felaktiga energikällorna | Historiska 94/104 får inte användas som slutligt näringsgodkännande; tio tidigare stopp saknar komplett resultat |
| Allergener | Samtliga 94 raders allergenkontroll var `NOT_REQUESTED`; separat negativt HTTP-prov finns | Ingen allmän allergensäkerhet bevisas av köp- eller näringsstatus |

Den blandade 40-g-proteinmenyn ger ett autentiskt delningsbevis som inte använder de två energikällorna. Fyra rätters risbehov `100 + 130 + 130 + 110 = 470 g` köps som **en 1 000-g-förpackning Långkornigt Ris för 21,95 kr**, hos Hemköp Lund Brunnshög. Två rätters citronjuicebehov `36 + 30 = 66 ml` köps som **en 200-ml-förpackning för 8,99 kr**, Coop Online Syd, GTIN `7340191116641`. Båda köprader är `VERIFIED`; 530 g ris och 134 ml juice är planerade rester, inte nytt uppmätt skafferi eller avdrag från betalningen. Full plan SHA-256: `efabd43bca38a88330461486f6af0c3b155f85ae01548147214d48bbc8e6d6d0`.

## Fortsatt verifiering

Konfliktspärren ska granska de ursprungliga energifälten och deras mängdbas, bevara råbeviset och inte tyst rätta enheterna eller tillåta generisk reservnäring genom en konflikt. En konservativ pargräns är en integritetskontroll, inte en juridisk tolerans eller ett bevis på exakt ekvivalens. Den separata massgränsen får inte appliceras på milliliter utan densitetsunderlag.

Oberoende kodgranskning av `d26983762bb0da6d0dab4842d4daf39493c97fea` fann ingen avvikelse från dessa krav. Den nya versionen `retained-catalog-facts-v8-qualified-energy-pairs` provades dessutom lokalt mot de **verkliga två hashbundna råposterna**: båda förlorade kvalificerbar kcal och fick `nutrition.kcal` plus `nutrition.energy` som konflikt; färsen träffade även massgränsen. Fem extra direkta gränsprov kontrollerade exakt 8 kJ och precis utanför på ursprunglig 10-g-bas, ett normalt 37-kJ/9-kcal-par samt separat gram-/milliliterhantering vid 1 001 kcal. Gränsproven bekräftade avsedd kontroll utan härledning eller korrigering. Kodens tester omfattar även konfliktbevarande genom exakt produktidentitet, leverantörskomplettering och generiska referenser. Denna granskning ersätter inte de återstående normala recept- och menykörningarna.

Efter rättningen krävs ny 104-kvalificering, sju fria menyer och påverkat HTTP-monotoniprov på ett nytt versionsbundet underlag. Historiska planer och rapporter ska bevaras med denna rättelse, inte skrivas om till gissade näringsvärden. Fulla råfiler, plansvar, sessionsuppgifter och arbetsanteckningar ligger utanför Git; denna rapport innehåller endast offentliga produktidentiteter, källhashar och sanerade resultat.
