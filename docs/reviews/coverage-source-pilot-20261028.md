> **Avslutad 2026-10-28 på ägarens instruktion.** Externa nätbutiker ingår
> inte i fortsatt arbete. PR #34 stängdes utan merge. Ingen pilotkälla eller
> prisuppgift har aktiverats. Fysisk butik och nätpublicerade butikspriser för
> samma butik krävs för en ny handlare. Kontrollera befintliga alternativ och
> Smakos bortsortering först. Texten nedan är historiskt beslutsunderlag.

# Begränsad lokal källpilot för kvarvarande torra råvaror

Detta är ett beslutsunderlag, inte aktiverade källor eller nya verifierade
korgar. Senast verifierade lokala resultat är 1 864/2 200 i den frysta
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
  sökvägen har både äldre läsbart utdrag med 59 kr och ett senare 404-resultat.
  Vid omgranskning 2026-10-28 återfinns inte artikeln i den lästa
  [katalogsidan](https://www.extremefood.se/2-hem?page=19) eller kategorin
  [tortillas och mjöl](https://www.extremefood.se/39-tortillas-mjoel-mm).
  Detta bevisar inte marknadsfrånvaro; aktuell köpbar artikel återstår.
  Naturello med passerat kort datum ersätter inte denna artikel.
- [Med24s egen produktsida](https://www.med24.se/matvaror/mjoel-gryn-och-bakning/korn-och-gryn/paerlkorn-m-m/urtekram-food-paerlkorn-eko-400-g)
  anger 400 g och kornkärnor. Den visade EAN 5765228120453 skiljer sig från
  tidigare andra källors kod; inga GTIN-relationer kopieras över utan bevis.
  [Egen varumärkeslista](https://www.med24.se/urtekram) skilde tidigare 31 kr
  från 24 kr medlemspris. Senaste produktutdraget saknar läsbart pris.
  Piloten kräver en aktuell kvalificerad publik grundprisobservation.
- [Pong Markets egen bakningslista](https://pongmarket.se/bakning/) namnger
  de tre exakta artikelkoderna ovan. En annan språkversion visar exempelvis
  ett kartongantal vid pärlorna. De tre svenska produktsidorna har nu lästs
  separat; se den konkreta formgranskningen nedan.

Samtliga föreslagna kontexter är separata online-/leveranskontexter med
onlinepris. De är inte fysiska Malmö- eller Lundhyllor. Inget befintligt
Coop-ID eller någon produktidentitet får återanvändas för dem. Butikstaket
gäller även de nya kontexterna och användaren måste uttryckligen välja dem.

[Pong Markets leveransvillkor](https://pongmarket.se/v%C3%A5ra-leveranss%C3%A4tt/)
beskriver DHL-paket för torrvaror i övriga Sverige, vikt-/kolligränser och
plockavgift under 200 kr. Kyl/frys/färskt och Stockholmsbilar ingår inte i
piloten. Olika sidor visar olika fraktnivåer; en full leveranskostnad är
ännu inte kvalificerad. Den senaste läsningen anger 39 kr plockavgift under
200 kr, DHL endast för torrvaror, fri frakt över 1 200 kr upp till 20 kg
och 149 kr per extra kolli om högst 20 kg. De tre områdesblockens
99/129/139 kr får inte väljas utan rätt områdes- och kassabindning.

[Med24s leveranssida](https://www.med24.se/leverans) anger DHL Service Point
39 kr och fri frakt över 499 kr. Sidhuvudets ”från 499 kr” lämnar exakt
gränsbelopp oklart. Instabox 35 kr kräver egen områdeskvalificering.
[ExtremeFoods leveranssida](https://www.extremefood.se/content/1-delivery)
anger 59 kr med DHL Servicepoint inom Sverige. Dessa publika villkor
är forskningsunderlag, inte genomförda eller kvalificerade checkouter.

## Uppdaterad produktgranskning 2026-10-28

| Exakt produktlänk | Deklaration i primärkällan | Återstående kvalificering |
| --- | --- | --- |
| [BW0003](https://pongmarket.se/tapiokamj%C3%B6l-400g-cock-brand-kina/) | UPC 084909000798; 400 g; tapiokastärkelse 98 %, vatten 2 %; torr förvaring; utdrag 20 kr | Aktuell källbunden prisobservation, exakt receptform och obligatoriska avgifter |
| [PMSM0014](https://pongmarket.se/tapioka-p%C3%A4rlor-sm%C3%A5-400g-cock-brand/) | EAN 8858826308976; små torra pärlor 400 g; samma deklarerade proportioner; utdrag 25 kr | Aktuell källbunden prisobservation, receptform och avgifter; inget kartongpris antas |
| [PMSM0031](https://pongmarket.se/mj%C3%B6l-klibbigt-ris-500g-xin-liang-kina/) | EAN 6970603300064; glutinöst ris, 500 g; utdrag 33 kr | Energi 1 538 kJ och 542 kcal motsäger varandra. Ingen näringsimport; pris, form och avgifter återstår |

Befintlig arkitektur saknar ännu en deklarerad kostnad för paketleverans
i checkout. `StoreServiceArea.availability_basis` beskriver verifierad
hämtningskontext. En pilot behöver därför utöka befintliga kontext- och
checkoutkontrakt med verifierat leveransområde och obligatoriska avgifter,
så att butikstak och totalsumma fortsatt blir riktiga. Att bara lägga in
varupriser i Malmöreferensen är inte en färdig integration.

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
