# Versionerade recept och beredningsberäkning

`smako-edible-input-v1` är receptutformning. Det är inte hämtade produktfakta,
uppmätt oljeupptag, densitet, ätbar andel eller tillagningsutbyte.

Den deterministiska kandidatgeneratorn skapar nya definitioner. Originalen kan
fortfarande genereras med `recipe_version="legacy"`; redan sparade recept utan
`preparation` ändras inte. Varje ny definition har ursprung, metodversion,
mallfamilj, ingrediensformer och innehållshash för originalet. API, PlanStore
och återläsning använder samma Recipe-kontrakt. Externa anpassningar märks
`explicit_adaptation` och ersätter inte sitt original.

## Receptutformning

De 15 varma mallarna anger nu rapsolja i ingredienslistan:

| Mall | ml per portion | Utformningsskäl |
|---|---:|---|
| Gryta, pasta, chili, curry, gratäng, soppa, bowl, wrap | 5 | Liten uppmätt fräsbas; vatten och rättens vätska används under tillagningen. |
| Ugn | 7,5 | Fördelas över råvarorna i täckt form; all sky serveras. |
| Wok, panna, risrätt, nudelrätt, potatisrätt, husman | 10 | Uppmätt fett för stekpannans större kontaktyta; ingen ytterligare fri tillsats. |

Mängderna valdes som kulinariska portioner innan pris-/menyjämförelsen, inte
för att nå proteinmål. All uppmätt olja räknas som använd och ska serveras.
Det är en explicit uppskattningsförutsättning, inte ett uppmätt upptag.

Äggversionerna använder 100 g rå ätbar äggmassa per huvudmåltidsportion och
50 g i äggmellanmålet. Äggen tillagas som äggröra i stället för att kokas och
skalas. Tortillaversionerna använder 100 g per portion. Dessa är nya
receptmängder, **inte** styckvikter eller omräkningsfaktorer. Crème fraiche
vägs i gram med samma numeriska receptmängd som tidigare angavs i ml;
det är en separat massbaserad receptutformning, ingen antagen densitet.

Torkade gryn/pasta/linser anges som torra; de tillagas med vatten som behålls
eller avdunstar. Vätska med livsmedel hälls inte bort. Kikärtor/bönor anges
separat som kokta och avrunna. Där krävs belagd användbar avrunnen
förpackningsmängd och motsvarande näringsgrund; en nettoburkvikt räcker inte.

Tofumackans nya version anger 5 ml rapsolja per portion. Varm ostsmörgås har
en separat metod utan extra olja; all ost och det fett som hamnar i formen
ska serveras. Den senare är ett separat integrationsrecept och räknas inte
som ett av de 84 ursprungliga fallen.

## Beräkningsmetod och skydd

För efterfrågade makron/energi per portion används:

`summa(källvärde per 100 g eller ml × använd ätbar mängd / 100) / portioner`

Enheten måste stämma direkt. Metoden tillverkar ingen g/ml-, styck/g- eller
torr/kokt-omräkning. Inköpskostnad kommer från befintlig helförpacknings- och
kampanjberäkning. Förpackningsrest ingår inte i måltidsnäringen.

Receptets gram är nödvändig ätbar insats. Efter putsning måste denna mängd
kontrollvägas; en exakt andel av en inköpt lök, fisk eller frukt påstås inte.
Denna reservation sparas i beräkningsgrunden. Metoden intygar inte att en
okänd bruttovikt räcker till en viss ätbar mängd.

All varm insatsberäkning får näringsstatus `ESTIMATED`, även med verifierad
produktdeklaration. Den kräver befintligt `allow_nutrition_estimates`.
Detta är oberoende av exakt/uppskattat **köppris**. Per 100 g färdig rätt och
färdig portionsvikt förblir okända utan separat belagd slutvikt. Befintliga
viktkrav stoppar sådana planer. Inga vitaminretentionsfaktorer tillkommer.

Kontrollen validerar ingrediensoperander, enheter, former, oljemängd och de
faktiska instruktionerna för metoden. En flagga eller ändrat instruktionsfält
kan inte godkänna en annan tillagning. Valideringen körs vid generering och
vid näringsprövning. Receptets metod ingår i identitets-/cacheunderlaget.

Verifierade deklarationer prioriteras. Befintliga SLV-referenser kan användas
via samma opt-in och produktidentitetskontroll; deras källor och versioner
bevaras. Bekräftade skafferireferenser måste också ha rätt rå/torr/avrunnen
form. Referensvärden blir inte produktdeklarationer eller allergibevis.

Kommunval, erbjudandegiltighet, observationstider, prisimport, refresh och
användarprofiler ändras inte av denna metod.
