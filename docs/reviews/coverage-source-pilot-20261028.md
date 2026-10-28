# Begränsad lokal källpilot för kvarvarande torra råvaror

Detta är ett beslutsunderlag, inte aktiverade källor eller nya verifierade
korgar. Nuvarande integrerade resultat är 1 802/2 200 i den frysta
Malmöreferensen. Det underlaget och dess priser/tider ska bevaras.

## Föreslagen omfattning

Tillåt lokal implementation och kvalificering av exakt fem konsumentartiklar
hos tre nya handlare, genom befintliga provider-, snapshot-, GroceryContext-
och PriceUniverse-vägar. Inga fullständiga butikscrawlar ingår.

| Handlare | Artikel som får undersökas | Behov |
| --- | --- | --- |
| ExtremeFood | Maseca masa harina 1 kg, webb-ID 944 | Nixtamaliserat majsmjöl |
| Med24 | Urtekram Food Pärlkorn 400 g, varunummer 9576 | Polerade kornkärnor |
| Pong Market | Cock Brand tapiokamjöl 400 g, BW0003 | Ren tapiokastärkelse |
| Pong Market | Cock Brand små tapiokapärlor 400 g, PMSM0014 | Små torra pärlor |
| Pong Market | Xin Liang klibbrismjöl 500 g, PMSM0031 | Rent glutinöst rismjöl |

Pong-artiklarnas sammansättning och exakta form är ännu inte godkända.
Listningarna är kandidater för granskning, aldrig automatiska produktlänkar.
Grupperna har sammanlagt 88 varianter där respektive grupp ensam blockerade
insatsstödet i PR #27. Det är villkorad potential; nya källor, butikstak,
avgifter och fulla checkouter kan fortfarande stoppa korgarna.

## Källa och scope

Publika källor har lästs via webverktyget 2026-10-28. Verktygets angivna
crawlålder varierar mellan idag och äldre kopior; dessa utdrag är inte
nyinsamlade kvalificerade prisobservationer och får inte ge förnyade källtider.

- [ExtremeFoods historiska artikelsökväg](https://www.extremefood.se/mexikansk_mat/944-maseca-vitt-mexikanskt-majsmjol-1kg.html)
  måste återfinnas via dess aktuella officiella produktlänk. Den historiska
  sökvägen `/mexikansk_mat/944-maseca-vitt-mexikanskt-majsmjol-1kg.html`
  har både äldre läsbart utdrag och ett senare 404-resultat. Den aktuella
  [katalogen](https://www.extremefood.se/2-hem?page=19) visar Maseca 1 kg,
  59 kr, men är inte tillräcklig som kvalificerat nytt pris. Naturello med
  passerat kort datum ersätter inte denna artikel.
- [Med24s egen produktsida](https://www.med24.se/matvaror/mjoel-gryn-och-bakning/korn-och-gryn/paerlkorn-m-m/urtekram-food-paerlkorn-eko-400-g)
  anger 400 g och kornkärnor. Den visade EAN 5765228120453 skiljer sig från
  tidigare andra källors kod; inga GTIN-relationer kopieras över utan bevis.
  [Egen varumärkeslista](https://www.med24.se/urtekram) skiljer 31 kr från
  24 kr medlemspris. Piloten använder endast kvalificerat publikt grundpris.
- [Pong Markets egen bakningslista](https://pongmarket.se/bakning/) namnger
  de tre exakta artikelkoderna ovan. En annan språkversion visar exempelvis
  ett kartongantal vid pärlorna; konsumentförpackning och pris måste avgöras
  från den exakta artikeln och etiketten, inte kategorinamnet.

Samtliga föreslagna kontexter är separata online-/leveranskontexter med
onlinepris. De är inte fysiska Malmö- eller Lundhyllor. Inget befintligt
Coop-ID eller någon produktidentitet får återanvändas för dem. Butikstaket
gäller även de nya kontexterna och användaren måste uttryckligen välja dem.

[Pong Markets leveransvillkor](https://pongmarket.se/v%C3%A5ra-leveranss%C3%A4tt/)
beskriver DHL-paket för torrvaror i övriga Sverige, vikt-/kolligränser och
plockavgift under 200 kr. Kyl/frys/färskt och Stockholmsbilar ingår inte i
piloten. Olika sidor visar olika fraktnivåer; en full leveranskostnad är
ännu inte kvalificerad. [Med24](https://www.med24.se/matvaror) anger fri
DHL-frakt från 499 kr, men avgiften under gränsen återstår att verifiera.
ExtremeFoods aktuella leveransvillkor måste också kvalificeras.

## Vad ett ja innebär

Ett ja tillåter den avgränsade lokala piloten och dess nödvändiga källanrop,
exakta produkt-/mängdgranskning, tester och ett separat kandidatunderlag.
Kandidatpriser får inte räknas som levererade helkorgar förrän även rätt
leveransområde, faktiska obligatoriska avgifter och ordinarie checkout kan
verifieras. Avgifter ska följa befintlig arkitektur; okänd avgift blir ett
ärligt hinder. Individuella rabattkoder, medlemserbjudanden utan kvalificerat
villkorsstöd och personliga erbjudanden används inte.

Ingen beta-/produktionsaktivering, schedulerändring, breddad Coop-allowlist,
inloggningsautomation eller ändring av den frysta jämförelsen ingår.

Beslutet behövs eftersom det aktuella uppdragets punkt 5 säger: ”Först om
en ny handlare, källa eller allowlist behövs ska ett konkret separat
beslutsunderlag tas fram.” Arbetet med beredningar och befintliga källor
kan fortsätta oberoende av beslutet.
