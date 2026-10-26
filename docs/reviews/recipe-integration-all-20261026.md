# Samtliga 2 200 levererade receptvarianter integrerade

Fortsättning efter ägarens uttryckliga instruktion att integrera **alla** recept.
Första delmängden på 45 är historik, inte slutresultatet. Den här leveransen
för in återstående **2 155 varianter** genom befintlig author → validate → diff →
import → prepare. Alla 800 källkandidater är representerade. Utvecklingsbiblioteket
har **2 462 aktiva varianter på 934 registrerade grundrätter**; de ursprungliga
262 varianterna/165 baserna är innehållsmässigt oförändrade.

Import är inte samma sak som verifierad köpbarhet. Alla varianter har granskad
receptstruktur; faktisk produkt, mängd, pris, diet, näring, allergener och eko
prövas för respektive användarval. Recepten är AI-författade och inte provlagade.
Ingen beta, produktion, insamling, schemaläggning eller användarprofil aktiveras.
Legacy-default och `merge=False` består.

## Hela källan och vanlig publicering

- [Alla 2 200 käll-ID:n → aktiva ID:n, rad, SHA och ändringsbeslut](recipe-integration-all-20261026/all-recipes.json).
- [Strukturellt slutkvitto](recipe-integration-all-20261026/structural-summary.json):
  166 manifestbundna originalfiler byteidentiska, idempotent återimport,
  **33 aktuella + sju historiska generationer**, långt under 128.
  Största publicerade paketet är 2 882 571 byte, under 16 MiB.
- [Granskade författar-/standardfiler](../../backend/app/data/recipes/reviewed-all-20261026/)
  har 15 grundpaket och en separat tolv-raders versionsrättning. Publicerade
  hashfiler och äldre versioners bytes bevaras. De tolv äldre versionerna med
  för grova styckdetaljkrav är uttryckligen återkallade.
- [Native audit av det oförändrade originalet](recipe-integration-all-20261026/original-audit.json)
  ger fortfarande 2 140 kompatibla, 19 ingrediensblockerade och 41 native avslag.
  Originalets två fröidentiteter är inte globala alias: granskade varianter anger
  uttryckligen skalade ätliga kärnor. Korrigerade och importerade versioner har
  **noll** kvarvarande författar-/innehållsavslag.

Samlingen omfattar 1 800 middagar, 200 frukostar och 200 mellanmål. Köken:
grekiskt 341, indiskt 341, italienskt 342, mexikanskt 262, svenskt 589,
thailändskt 325 varianter. Varje korrigerad variant valideras och rundtrippas
vid **1, 2, 4 och 12 portioner**, med bevarade mängdformer, krav, familj och
grundrätt. Större omgångars faktiska aktiva tid får överstiga 180 minuter i
receptmodellen; användarens 180-minutersfilter fortsätter avvisa sådana fall.

## Innehållsbeslut

Samtliga komponentmängder, användningar, stegberoenden, tidskedjor, råvaruformer,
titlars namngivna ingredienser och dietklassificering omfattas av systematiska
kontroller och uttryckliga redaktionella regler. Detta ersätter inte provlagning
eller en oberoende global unikhetsgranskning.

De 13 kvarvarande namngivna processgrupperna är genomlästa. Deras 41 basanspråk
samlas på 13 gemensamma baser/familjer: samma deg/bindning, formning och
slutberedning med olika fyllningar. Tillsammans med tre tidigare avvisade
ny-basanspråk blir det **769 nya registrerade baser**, inte 800 nya unika
kulinariska konstruktioner. Ingen källvariant försvinner; `max_same_base_meals`
kan inte kringgås genom variantnamn.

Rå animalisk insats behålls som rå insats när den faktiskt tillagas före kall
slutmontering. Kaffedoppad sockerkaka bakar ägget före kylning; ostkrämen har
inget rått ägg. Blandade aktiva/passiva moment delas utan att kapa blötläggning,
jäsning eller kylning. Frysta frukt-/örtvarianter anges uttryckligen, med
upptining där det behövs och bevarad fruktsaft. Frysta hallon får ett fullständigt
uppkok och, för kalla rätter, en separat kylkedja enligt
[Livsmedelsverkets råd](https://fragor.livsmedelsverket.se/org/livsmedelsverket/d/varfor-finns-det-virus-pa-importerade-frysta-bar/).
Fyra nötköttskonstruktioner kräver i version 1.0.1 specifikt innanlår, hel oxfilé,
nötstek respektive mager remsdetalj; en grov tidsregel får inte ersätta detta.

De **294** avvikelserna från variantintervallen kvarstår som dokumenterade
kulinariska undantag utan utfyllnad. Efter samgruppering saknar fyra aktiva
middagsbaser fortfarande variant inom 10–15: selleripaket med bönor,
kyckling-/dillgryta, linsfylld rotselleri och tofu-/ananasspett. De exakta ID:na
finns i strukturkvittot. Standardfilter och `dinner_level` ändras inte.

## Ingredienser och konkreta köphinder

[Det nya ingrediensregistret](../../backend/app/data/ingredients/intake-all-20261026.json)
har **92** ytterligare identiteter med **381** granskade produktreferensrader.
Bindningen kräver exakt GTIN eller exakt produkt/butik/snapshot, hela namnet,
varumärke, förpackning, enhet och mängdstatus. Tio referenser har källans
uppskattade vikt och kan bara prövas med uttryckligt `estimated`-val.
184 referenser har matchande bevarad faktarad; ingen av dessa faktarader har
fullständig ingrediensdeklaration. Det är inte positiva närings-/allergen-/ekointyg.
Första leveransens tolv identiteter/23 referensrader är fortsatt bevarade.

Ytterligare **89** giltiga ingrediensdefinitioner kan nu författas och importeras
utan låtsasrecept eller tomma krav. De kräver en verklig källbunden
tillverkardeklaration av identitet, form och användbar mängd. Definitionernas
källrader är granskningsunderlag för receptet, **inte godkända produktbevis**.
Nuvarande data uppfyller inte dessa krav. Ingen fri densitet, torr/kokt-faktor,
skal-/ben-/baljandel eller avrunnen mängd antas. Bruttomassa av kalvben,
musselskal, majskolv och edamamebaljor får inte ge ätlig näringsmassa.

Den gemensamma inventeringen använder samma behöriga Malmöunderlag från
**23 oktober**, 89 458 produkter och 71 138 faktarader. Den förnyar inga
tidsstämplar och är inte ett påstående om dagens butiksläge. Den skiljer
individuellt lösbara insatser från en gemensam godkänd inköpslista.

Slutlig runtime `d181416` ger **1 812 gemensamma inputscope** över hela
samlingen. I exakt köpläge har **704/2 200** varianter alla insatser lösta,
**1 496** är produktblockerade. Efter det separata uttryckliga valet
`estimated` blir motsvarande antal **888** respektive **1 312**. Detta
är ingen automatisk kravändring eller ett intyg om 888 giltiga veckomenyer.
Det återstår **104** ingrediens-/formluckor i exakt läge: 89 nya definitioner
med saknade produktbevis och 15 redan kända identiteter med andra köp-/faktahinder.

- [Prioriterad konkret hinderlista](recipe-integration-all-20261026/HINDER.md).
- [Exakta recept-ID:n, mängd-/formkrav, avslag, produkt-/butiks-/snapshotförslag och nästa komplettering](recipe-integration-all-20261026/purchase-blockers.json).
- [Gemensam inventering i exakt köpläge](recipe-integration-all-20261026/product-inputs.json).

Största överlappande luckorna är limejuice med obelagd ren sammansättning,
rå ätlig ingefära, ansad salladslök, färsk mynta och frysta majskorn.
Listan skiljer verkligt saknade produktbevis från köpform, avrinning,
fetthalt, sammansättning och matchning som behöver kompletteras. En varas
närvaro bland källförslagen gör den inte automatiskt godkänd.

## Funktionella prov och mätgränser

[Åtta låsta funktionella fall](recipe-integration-all-20261026/functional-probes.json)
på runtime `ce0b7e9` har full checkout/audit, privat save och ägarbunden
återläsning: sex kök, tre måltidstyper, ny ingrediensväg, gemensam pajbas,
fryst bärberedning och en variant av befintlig frukostbas. Samtliga åtta
sparades och återlästes oförändrade. Rouladkontrollen kostar fortfarande
270,36 kr; de sju nya fallen 148,00 / 87,15 / 131,20 / 93,98 / 123,35 /
126,51 / 161,95 kr med de exakt sparade villkoren. Tolv senare styckdetalj-
rättningar berör andra recept; dessa kvitton avser sin angivna runtime.
Näring var `NOT_REQUESTED`; detta är ingen full näringskvalificering.

[Ett nionde, separat estimated-fall](recipe-integration-all-20261026/estimated-functional-probe.json)
på slutlig runtime sparar och återläser lammsoppa med uppskattat pris
**317,90 kr** och godkänd checkout/audit. [Estimated-inventeringen](recipe-integration-all-20261026/product-inputs-estimated.json)
behåller också det första misslyckade kontrollfallet: nötköttsgrytan
avvisas på rotselleri och räknas inte som ett lyckat prov.

[Förberedelsekvittot](recipe-integration-all-20261026/preparation.json) anger
den slutliga bibliotekshashen och gemensamma innehållsartefakter. Den gamla
lokala cachen var full vid 4 096 poster och behöll säker beräkning i minnet;
slutlig förberedelse använder en ny, uttrycklig cachekatalog med oförändrade
gränser. Portionsstrukturer förbereds i minnet genom befintlig väg.
Slutligt innehåll: **2 816** beständiga poster/1 796 286 byte. Alla fyra
portionsstorlekar omfattar **2 838** aktuella/historiska versionsreferenser.
Slutlig förberedelse tog 132,2954 s inklusive budgetwrapper; exakt inventering
67,5097 s. Största verifierade private-commitpeak är 1 277 063 168 byte
(cirka 1,19 GiB). Två CPU och hårt 3 GiB commit är verkställda för den riktiga
Windows-interpretern; detta är inte ett Linux-cgroup-/RSS-latensprov.

Alla dyra starter, förberedelser, omtag och funktionella prov debiteras samma
[120-minutersjournal](recipe-integration-800-20261025/budget.json). En av misstag
överlappad inventering stoppades; båda arbetenas tid är fullt debiterad och
överlappet används inte som prestandabevis. En OS-låsning förhindrar nu en andra
aktiv budgetarbetare. Vanliga implementationstester/CI hålls separat enligt
uppdraget. Det finns ingen ny extra budget.

**Slutlig förbrukning: 2 125,9999 s = 35,43 minuter. Kvar: 5 074,0001 s =
84,57 minuter av samma 120 minuter.** Journalens summa och samtliga starter,
avbrutna arbeten och omtag är bevarade. Inga budgetarbetare kör vidare.

Detta styrker inte 30–60-sekundersmålet, p95, generell veckosöklatens eller
global optimalitet. V2:s fortsatta arkitektur-/sökuppdrag är fortfarande separat
återstående arbete inom samma kvarvarande budget. Inga mätarbetare lämnas igång.
