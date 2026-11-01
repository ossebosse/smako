# Tre receptfortsättningar mottagna 2026-11-01

> Ägarens rättelse senare 2026-11-01: något separat 72/194-arkiv finns inte.
> Rapportens slutsats nedan att begära det är återkallad. Författarens
> arkivhänvisningar och konflikter mot det är obestyrkta metadata; de ska
> inte stoppa arbetet med faktiskt mottagna 165 baser / 439 varianter.
> Fortsatta leveranser kommer med cirka 10–40 rätter per ZIP.


**93 grundrätter / 240 varianter mottagna som utkast. Ingen import eller
betaaktivering.** Tillsammans med den tidigare checkpointen finns faktiskt
165 grundrätts-ID:n / 439 variant-ID:n i mottagningen. Detta är inte ett
slutligt antal kulinariskt unika och godkända rätter.

Kontrollerna använder main `ac4d4811f5cbd5edd93ca03286dca1664def34ab`,
2 462 aktuella varianter och 3 517 aktuella/historiskt utgivna variant-ID:n.
Bibliotekets manifest är byteoförändrat, SHA-256
`68a142625914bdeae7d03d1d41d76f7a440ae2ab1239d2f31e2e4ebc435f3516`.

## Mottagning och strukturkontroll

| Leverans | Grundrätter | Varianter | Middag / frukost / mellanmål | Native-kompatibla | Ingrediensblockerade |
| --- | ---: | ---: | --- | ---: | ---: |
| [22](../../../backend/app/data/recipes/incoming/authoring-1000-20261101/continuation-22/README.md) | 22 | 54 | 10 / 2 / 10 | 14 | 40 |
| [41](../../../backend/app/data/recipes/incoming/authoring-1000-20261101/continuation-41/README.md) | 41 | 108 | 26 / 3 / 12 | 15 | 93 |
| [30](../../../backend/app/data/recipes/incoming/authoring-1000-20261101/continuation-30/README.md) | 30 | 78 | 18 / 5 / 7 | 19 | 59 |
| Nya totalt | 93 | 240 | 54 / 10 / 29 | 48 | 192 |

Alla 108 ZIP-medlemmar klarar CRC, säkra relativa sökvägar och författarens
filhashar. JSON-filerna saknar dubbla objektnycklar. 49 originalfiler är
bytebevarade i Git, med tre separata `SOURCE-MANIFEST.json` som även
inventerar övriga arkivmedlemmar. Stora härledda kontrollfiler, duplicerade
referenser och medföljande program ligger kvar i ZIP/lokal uppackning.
Inga medföljande program har körts och inga originalrecept har ändrats.

Alla 240 varianter klarar leveransschemat. Variantfamiljer, portionsantal,
ingrediensträknare och rapporterade okända identiteter stämmer med receptfilerna.
Tidsaritmetiken för samtliga 1 732 steg stämmer, inklusive beroenden och väntetid.
Detta verifierar beräkningen, inte författarens uppskattade tillagningstider.

48 varianter klarar befintlig `standardize` och `validate_pack_bytes`,
diff som nya recept, isolerad strukturförberedelse och 144 skalningskontroller
(1, 4 och 12 portioner). De omfattar 18 hela familjer med 38 varianter samt
10 varianter från åtta ofullständigt kompatibla familjer. Ingen familj har
delimporterats. Produktfakta, näring, slutlig köpbarhet och fullständig checkout
är inte kvalificerade här. De diagnostiska granskningsdatumen är inte attest.

Kvitton: [samlad validering](VALIDATION.json), [22](NATIVE-AUDIT-22.json),
[41](NATIVE-AUDIT-41.json), [30](NATIVE-AUDIT-30.json).

## En äldre fortsättning saknas och förklarar olika totalsiffror

De senare leveranserna hänvisar till **ett annat 72-receptspaket** än den
redan mottagna checkpointen med 199 varianter:

`smako-fortsattning-72-nya-grundratter-194-varianter-20261101.zip`

Författarens referens anger 6 570 948 byte och SHA-256
`f86c1d7e03f965a65a434d7a4b02c255a4cba18477798e77b151573a21019b74`.
Originalarkivet finns inte i denna mottagning. Referensen kommer från
[indatakontrollsummorna](../../../backend/app/data/recipes/incoming/authoring-1000-20261101/continuation-30/source/kontroll/indata-kontrollsummor.json)
och [författarens konfliktregister](../../../backend/app/data/recipes/incoming/authoring-1000-20261101/continuation-41/source/tidigare-leveranskonflikter.json).

Författarens senare totalsiffra **235 baser / 629 variant-ID:n** inkluderar
den saknade leveransen. Jämförelsen med mottagna filer ger **70 bas-ID:n /
190 variant-ID:n som ännu inte är mottagna**; fullständiga listor finns i
VALIDATION. Två baser/fyra variant-ID:n anges även i den mottagna 22-leveransen.

Konfliktregistret uppger olika innehåll för samma version/variant av
`smako-thai-miang-kham` och `smako-thai-kluai-buat-chi`, båda simple/extended.
Det uppger också konceptöverlapp för Testaroli, Pad pak bung/boong, Chicken 65
och Gubbröra. Dessa uppgifter är författarens; båda originalversionerna behövs
för egen innehållsjämförelse. Välj ingen vinnare och skriv inte över original.

Det saknade arkivet har paket **007–011**, medan 22-leveransen återanvänder
paket-ID **007–008 med andra filhashar**. Det saknas alltså mer än bara 009–011.
Identifiera en källa med leveransmapp + filhash, inte enbart paket-ID. Behåll
original-ID:n. Nästa nyskrivna paket ska börja på **019**; konfliktlösning
av gamla leveranser ska redovisas separat.

## Nyhet och innehåll som återstår att granska

Ingen ny bas eller variant krockar på exakt ID med aktuell/historisk utgivning,
den tidigare mottagna checkpointen eller inom de tre nya leveranserna.
[Likhetsscreeningen](DUPLICATE-TRIAGE.json) jämför alla 93 nya baser med
aktuellt bibliotek, checkpointen och varandra; den ger tre namn-/ingrediens-
kandidater per bas för manuell granskning. Inget exakt normaliserat namn före
variantbeskrivningen hittades. Likhetsmått kan missa samma rätt med olika namn
och är varken automatiska avslag eller ett godkännande av kulinarisk nyhet.
Den saknade leveransen ingår inte i denna innehållsjämförelse.

Konkreta innehållshinder före import:

- 192 varianter stoppas av okända ingredienser. Unionen är 105 ursprungliga
  namn/form-förslag, 103 efter nuvarande normalisering. Bevara originalen och
  granska exakta råvaror/former; skapa inga alias enbart för att passera.
  Exempel som behöver kontroll är färska majskorn → majs, grönsaksbuljong →
  buljong, hel kyckling/kycklinglårfilé → kyckling och svartögda bönor → bönor.
  Alla berörda varianter är redan blockerade; inga sådana alias godkänns här.
- Kosha mangshos tre varianter har **192, 192 respektive 197 aktiva minuter**,
  över Smakos 180-minutersgräns. Totalerna är 335/335/340 minuter. De ingår
  redan bland de 192 ingrediensblockerade; lägg inte till tre i totalsumman.
  Granska arbetsmomenten utan att godtyckligt korta tider eller kalla aktivt
  arbete passivt.
- 12 av de 48 kompatibla varianterna ärver frysta insatser: hallon (3),
  jordgubbar (2), koriander (3), lingon (3) och mango (1). Exakta krav och ID:n
  finns i VALIDATION. Exempelvis beskriver äggost färska jordgubbar och
  mandelmusslor sköljda hallon. Recepttext och verklig insats behöver förenas
  med granskad beredning; kompatibilitet intygar inte den överensstämmelsen.
- Loukoumades anger 180 ml frityrolja per portion och Mangalore buns 300 ml.
  Författaren markerar uttryckligen processinsats och att rester inte äts.
  Inköpsbehov, processmängd och konsumerad mängd behöver separat hantering
  före närings-/kostnadsbedömning. Gissa inte oljeupptag.
- Äggost och shrikhand beskriver avrinning av vassle från angivna insatser.
  Författaren anger själv att utbytet inte är uppmätt. Validera hur processrest,
  färdig portion och näring ska representeras; rå insats är inte verifierat
  konsumerat utbyte.

Olivolja berör 63 nya varianter, grön chili 18 och parmesan 14. Dessa tal
visar beroenden i utkasten, **inte popularitet, styrkt produktstöd eller ny
produkttäckning**. Prioritera fortsatta ingrediensgranskningar med befintligt
produktunderlag enligt [beställningsrutinen](../../recipes/REQUESTING-RECIPES.md).
Källsidor, klassikeranspråk och all recepttext är inte slutligt sakgranskade.

## Fortsättning och reproducerbarhet

Faktiskt mottaget hittills är 109 middagar, 13 frukostar och 43 mellanmål.
Mot beställningen återstår **835 baser / 2 311 varianter** räknat mot dessa
utkast: 641 middagar, 112 frukostar och 82 mellanmål. Antalen ska räknas om
efter att saknat original och konceptkonflikter har retts ut.

| Kök | Mottagna middagar | Frukostar | Mellanmål | Baser |
| --- | ---: | ---: | ---: | ---: |
| greek | 12 | 2 | 9 | 23 |
| italian | 27 | 1 | 4 | 32 |
| mexican | 17 | 4 | 7 | 28 |
| indian | 16 | 4 | 7 | 27 |
| thai | 20 | 1 | 9 | 30 |
| swedish | 17 | 1 | 7 | 25 |
| Totalt | 109 | 13 | 43 | 165 |

Be först om det namngivna saknade originalarkivet. Granska därefter
konflikter, innehåll, ingrediensidentiteter och produktstöd. Spara eventuella
godkända rättningar som separata granskade versioner enligt AUTHORING.
De tre leveransernas effekt på varm planeringstid är **inte uppmätt**.
Tidigare mätning av checkpointens 50 varianter får inte extrapoleras hit.

Varje mottagningsmapps README har kommandot för befintligt native-auditverktyg.
Exitkod 1 betyder slutförd kontroll med dokumenterade hinder. Ytterligare
offlinekontroller finns som [körd kontrollkod](validate.py.txt) och
[likhetsscreening](duplicate_triage.py.txt); filerna är dokumentationskopior,
inte program från leveransen. Kör från repo med `PYTHONPATH=backend;.`.
Valideringen använder samma oförändrade leveransschema och befintlig lokal
jsonschema-miljö från checkpointens kontroll. Hashbundna resultat bevaras här;
lokala förberedelsecacher och det tillfälliga native-paketet publiceras inte.
