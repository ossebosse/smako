# Tidseffekt av receptcheckpointen i uppvärmt läge

2026-11-01. **Liten uppmätt tidsskillnad för den tekniskt testbara delen:**
en middag 21,24 → 21,61 sekunder (+0,38 s, cirka 1,8 %); tre middagar
49,03 → 49,03 sekunder. Två körningar per bibliotek och middagsfall ger
en begränsad jämförelse, inte en statistiskt säkerställd liten regression.

Det aktiva biblioteket och betan har inte ändrats. Provet jämför isolerat
**2 462 befintliga varianter med 2 512**, alltså de 50 strukturellt kompatibla
utkasten som tillägg (+2,03 %). Dessa representerar 21 grundrätter, fördelade
på 28 middags-, 4 frukost- och 18 mellanmålsvarianter över alla sex matkök.
De 149 registerblockerade varianterna ingår inte. Resultatet får inte räknas
upp linjärt till alla 199 varianter eller beställningens 1 000 grundrätter.

## Menytid och resultat

Tiden börjar före planerarens insläpp och inkluderar beräkning, korgkontroll,
sparning och ägd återläsning i separat syntetisk databas. Den inkluderar
inte HTTP, webbläsare eller verklig köbelastning. Samma 60-sekundersgräns
och användarval gäller på båda sidor.

| Varmt menyprov | Befintligt bibliotek | Med 50 extra | Skillnad | Fullständiga mätningar per sida |
| --- | ---: | ---: | ---: | ---: |
| En italiensk middag, 2 portioner, högst 1 butik | 21,236 s | 21,612 s | +0,376 s | 2 |
| Tre middagar, fria matkök, 2 portioner, högst 3 butiker | 49,028 s | 49,028 s | <0,001 s | 2 |
| Middag + frukost + mellanmål, högst 3 butiker | 49,044 s | 49,010 s | −0,035 s | 1 |

Två observationer sammanfattas med medelvärde; det sammanfaller här med
medianen. Enmiddagsintervallen överlappar: **21,020–21,452 s** respektive
**21,391–21,833 s**. Primningsjobbet efter gemensam uppvärmning redovisas
separat: 24,502 → 24,144 s i medel. Det ingår inte i tabellens upprepade
enmiddagsprov. De två större valkombinationerna är nya i varje process.

Alla 14 fullständiga mätposter klarade audit, sparning och ägd återläsning.
Fyra är primning och tio är tabellens jämförelseunderlag. Motsvarande korgar
har identiska hashvärden, receptval och priser: **110,55 kr**, **182,39 kr**
respektive **112,64 kr**. Inget nytt utkast valdes i dessa slutmenyer.
Detta visar ingen prisvinst i just proven och bevisar inte att nya recept
aldrig kan ge billigare menyer.

## Var tiden ligger

| Steg, medel av två körningar per sida | Befintligt | Med 50 extra |
| --- | ---: | ---: |
| Faktaladdning, en middag | 6,744 s | 6,654 s |
| Kandidatgenerering/kvalificering, en middag | 4,219 s | 4,308 s |
| Planerarens minnesstädning, en middag | 2,330 s | 2,438 s |
| Kandidatgenerering/kvalificering, tre middagar | 16,219 s | 16,476 s |
| Menysökning, tre middagar | 14,898 s | 14,773 s |

Stegmåtten kan innehålla arbete som mäts även på andra nivåer; summera inte
alla interna mätfält till väggtid. Ingen profilerare eller ändrad sökalgoritm
användes. Samma lätta loggning av explicita GC-anrop användes på båda sidor.

Den råa middagsmängden ökade 339 → 343 i det italienska fallet och
2 021 → 2 049 med fria matkök. Det större fallet hade 836 → 841 kvalificerade
alternativ per plats. De nya recepten laddades alltså och påverkade kandidaterna.
Det större jobbets slutorsak var på båda sidor att reservera tid för slutlig
korgkontroll och sparning. Därför betyder oförändrad sluttid inte att all
extra beräkning är gratis. Kandidatkontrollen ökade cirka 0,26 s i medel.
Antalet prövade hela menyer varierade mellan körningarna; ingen säker
förändring i sökkapacitet eller optimalitet fastställs.

## Uppvärmning och minne

Alla fyra processer passerade explicit gemensam uppvärmning: rätt antal
aktuella recept och portionsvyer 1–4, både Lund och Malmö redo, noll
persistensfel och samma 54 515 respektive 95 998 fakta. Vanlig HTTP-readiness
användes inte som ersättning för denna grind.

Recept-/faktauppvärmning: **85,884 → 86,324 s** i medel, med intervall
85,782–85,987 respektive 84,284–88,363 s. Föregående prisinläsning tog
92,6–94,1 s och prisprojektion 12,8–13,7 s. Detta är startförberedelser i
nya processer med kvarvarande OS-cache, inte menytid eller prov av kall disk.

Högsta kernelmätta process-RSS, inklusive uppvärmningen:
**2 737,3 → 2 741,1 MiB**, cirka +3,8 MiB. Högsta samplade RSS under
menyjobben: **2 486,9 → 2 517,6 MiB**, cirka +30,7 MiB. Värdena är maxima
över respektive två processer. Värden under jobb samplades från värddatorn
var 50 ms, oberoende av Pythons GIL; korta toppar kan missas. Kernelns
processövergripande högvattenmärke ger ett separat totalmått.

## Metod och avgränsningar

- Körordning **A1–B1–B2–A2**, fyra separata processer med tomma processcacher
  och egna temporära förberedelse-/plankataloger. Samma oförändrade appbild
  `app-b7c8d0506e23-c18e4ba9`, samma källvolymer skrivskyddade och gemensamt
  driftlås genom hela serien. Inget nätverk i testcontainrarna, 4 GiB minnesgräns.
- Fryst prisklocka `2026-11-01T12:19:40.625053+00:00`; samma Lund-PriceUniverse
  och faktaversion i samtliga fullständiga menyresultat. Exakta ID:n, miljö,
  hashvärden, tider och sökräknare finns i [EVIDENCE.json](EVIDENCE.json).
- Samma syntetiska underlag med 17 valda Lundbutiker, högst 1/3 inköpsbutiker,
  middagar för 2 personer, tillåtna näringsestimat och oförändrade övriga val.
  [CASES.json](CASES.json) innehåller hela indata. Varje jobb fick en ny
  syntetisk profil/databas och beräknades, kontrollerades och sparades på nytt.
  Ett färdigt tidigare menysvar återanvändes inte.
- I blandprovet är `recipe_choices=null` för frukost/mellanmål. Ordinarie
  beteende söker då enkla basalternativ: fem kandidater för vardera måltidstypen,
  och resultaten blev kvarg med bröd respektive kvarg. Provet mäter den blandade
  användarkombinationen, **inte utökad sökning bland de nya 22 författade
  frukost-/mellanmålsvarianterna**. En framtida sådan jämförelse behöver ett
  separat deklarerat fall med receptval för dessa måltidstyper på båda sidor.
- De 50 utkasten är tillfälligt utgivna genom ordinarie importfunktion i en
  isolerad katalog och monterade endast i testcontainrarna. Strukturkontroll
  och lyckade korgar ersätter inte den kvarstående
  [innehållsgranskningen](../recipe-checkpoint-72-20261101/REPORT.md).
  Inga ingredienskrav, källkontroller eller receptoriginal ändrades.
- Delad server, få repetitioner och en plats innebär att små skillnader kan
  bero på körvariation. Detta är inte p95 eller en garanti för alla val,
  samtidighetslägen, hela checkpointen eller den kommande större leveransen.

## Mätfel och efterkontroll

De två första blandproven nådde godkänd korg, sparning och ägd återläsning,
men resultatloggningen antog sedan att även basalternativen hade ett utgivet
recept-ID. Den kastade `AttributeError` efter kontrollerna. Dessa två poster
är bevarade som mätfel och **uteslutna** ur tabellen. Korrigeringen kontrollerar
om `recipe.design` finns; ingen appkod ändrades. B2/A2 ger det fullständiga
blandparet. [Ursprunglig mätkod](PROBE-ORIGINAL.py.txt),
[korrigerad mätkod](PROBE-CORRECTED.py.txt) och
[isolerad körning](REMOTE-RUNNER.py.txt) är arkiverade som text; hash-/körkoppling
finns i evidensen. Två inledande startförsök nådde inga menyprov: filåtkomst
och formatkontrollen av portionsrapporten rättades i mätverktyget.

Efter serien: testcontainrar borttagna, driftlåset släppt, ordinarie
driftkontroll genomförd. Aktiv appbild, BUILD_ID, kontrollerad kod, receptmanifest
och planeringsmiljö matchar före provet. Alla 12 bevarade leveranskällor har
oförändrade storlekar/hashvärden. Lokala råresultat och minnessampling finns i
`.local/recipe-checkpoint-72-timing-20261101/`. **Ingen betaaktivering eller
import i det riktiga biblioteket har gjorts.**
