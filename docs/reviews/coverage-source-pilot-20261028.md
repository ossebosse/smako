# Begränsad lokal källpilot för kvarvarande torra råvaror

Ägaren godkände 2026-10-28 uttryckligen: ”Ja, genomför den lokala piloten”.
Godkännandet omfattar de fem artiklarna nedan, lokal implementation,
källanrop och kvalificering inklusive leveransavgifter och butikstak.
Ingen produktionsaktivering ingår. Detta är ännu inte nya verifierade
korgar. Senast verifierade lokala resultat är 1 864/2 200 i den frysta
Malmöreferensen. Det underlaget och dess priser/tider ska bevaras.

## Godkänd omfattning

Lokal implementation och kvalificering av exakt fem konsumentartiklar
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
  En färsk manuell webbläsarkontroll skiljer 31 kr vanligt pris från
  24 kr medlemspris. Gästkorgen bekräftar 31 kr. Medlemspriset används inte.
  GTIN visas inte i den färska synliga sidan; den äldre koden får därför
  inte ensam etablera en aktuell relation till en annan källas artikel.
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

## Genomförd manuell käll- och kassagranskning

Alla fem godkända artiklar har granskats i publik webbläsare 2026-10-28.
De fyra Med24-/Pong-artiklarna är köpbara kandidater. ExtremeFoods
historiska URL visar inga tillgängliga produkter. En offentlig sökning
efter Maseca ger sex andra resultat, ingen godkänd artikel 944.
Andra märken har inte ersatt den. Ingen marknadsfrånvaro påstås.

[Strukturerade observationer](specialist-pilot-20261028/observations.json)
skiljer artikelidentitet, synligt listpris, gästers kassapris och avgifter.
De är manuella forskningsobservationer, inte ett aktiverat prissnapshot.

| Pong-artikel | Produktsidans belopp | Specificerad gästkassa |
| --- | ---: | ---: |
| BW0003, tapiokastärkelse 400 g | 20 kr | 20,47 kr |
| PMSM0014, små torra pärlor 400 g | 25 kr | 25,14 kr |
| PMSM0031, klibbrismjöl 500 g | 33 kr | 32,63 kr |

Pongs postnummerkontroll för referensområdet 21120 erbjuder torrvaror
med DHL till ombud. Kyl-/frysleverans är inte tillgänglig där.
En av varje artikel ger 78,24 kr varusumma, 69 kr DHL, 38,16 kr
tilläggsavgift och två kassajusteringar på −0,01 respektive −0,39 kr:
**185 kr totalt**. En ensam BW0003 kostade **128 kr inklusive avgifter**.
Kassan visar alltså andra exakta belopp än produktsidorna och den allmänna
texten om 39 kr plockavgift. Ingen automatisk moms- eller avrundningsregel
härleds från detta fåtal korgar. Ett generellt vikt-/beloppsbundet
leveransavtal och exakt maskinläsbar prisbindning återstår.

Med24s gästkorg bekräftar 31 kr för artikel 9576. Slutligt leveransval
kräver e-post före nästa steg; inga personuppgifter har fyllts i.
Publicerad DHL-frakt 39 kr, korgens annons om frakt från 35 kr och
fri-frakt-gränsen kvalificerar inte samma geografiskt bundna leveransval.
Samtliga tillfälliga testartiklar har tagits bort. Inga köp gjordes.

Butikstaket gäller oförändrat: en vanlig matbutik plus Pong använder två
kontexter; en matbutik plus Pong och Med24 använder tre och är inte en
tillåten tvåbutikskorg. Ingen sådan korg har räknats som godkänd.

**Noll nya verifierade Smako-korgar från piloten hittills.** De återfunna
fyra artiklarnas grupper hade 57 ensamblockerade varianter i arbetsmatrisen;
det är fortfarande villkorad potential. Hela pilotens ursprungliga 88
inkluderade även 31 masa-varianter vars godkända artikel inte återfanns.
De 1 864 tidigare hela korgarna och nämnaren 2 200 består.

## Lokal implementation och fortsatta kvalificeringsvillkor

Godkännandet tillåter den avgränsade lokala piloten och dess nödvändiga källanrop,
exakta produkt-/mängdgranskning, tester och ett separat kandidatunderlag.
Kandidatpriser får inte räknas som levererade helkorgar förrän även rätt
leveransområde, faktiska obligatoriska avgifter och ordinarie checkout kan
verifieras. Avgifter ska följa befintlig arkitektur; okänd avgift blir ett
ärligt hinder. Individuella rabattkoder, medlemserbjudanden utan kvalificerat
villkorsstöd och personliga erbjudanden används inte.

Den begränsade insamlaren använder befintlig `RawFetch`, `RawBatch`,
oföränderliga råsnapshot och operationslås. Bara tio explicit listade
produkt-/villkorssidor ingår, fem av dem produkter. Separat opt-in krävs,
omdirigeringar följs inte, åtkomststopp avbryter källan och nya misslyckade
försök skriver inte över tidigare underlag. Insamlaren rapporterar
ofullständiga försök som sådana och aktiverar aldrig priser.

Tre handlaridentiteter är tillagda utan nya ordinarie källstrategier.
`DEFAULT_SOURCE_CHAINS` bevarar exakt de tidigare sex standardkedjorna
i insamling, upptäckt, status, byggare och benchmark. Pilotens nya
identiteter är inte tillåtelse till automatisk insamling eller aktivering.

Den automatiska råinsamlingen har stannat före handlaranrop eftersom
serverns ordinarie `run_daily_refresh.py` höll operationslåset från
08:30 UTC. Läskontrollen 09:27 UTC visade en levande CPU-arbetande process,
inte en övergiven låsfil. Ingen process har avbrutits och inget lås tagits
över. Den manuella webbläsargranskningen hålls separat från råinsamling
och kvalificering. En ny ordinarie refresh tog låset 09:45 UTC. Ett köat
pilotförsök väntar högst 45 minuter med normala låsförsök och noll
handlaranrop före erhållen lease. Aktuell lokal försöksstatus finns i
`.local/specialist-pilot-20261028/collection-status.json` och dess attempts.

## Verifiering av oförändrat huvudunderlag

[Kvittoverifieringen](specialist-pilot-20261028/verification.json) bevarar
alla 2 200 original, 2 462 aktiva recept och 2 932 kvittofiler på aktuell
metod. Fortsatt 1 066 exakt hela och 1 864 inklusive uppskattningar, inga
förluster. A kostar 278,76 kr två gånger, API/spara/läs 52,16/52,11 s.
B2:s hela korg är identisk med tidigare, 731,20 kr.

Ett exakt fall nådde den korta genomgångens sökdeadline. Det isolerade
omprovet använde samma källor, recept, mängd- och butikskrav, en sökram
på 20 s och ordinarie slutlig audit: 2,34 s checkout efter 7,83 s
kandidatuppbyggnad. De andra 2 931 kvittona hashkontrollerades och
bevarades. Ingen pris-, fräschhets- eller kvalitetsgrind ändrades.

92 riktade tester samt Ruff och compileall passerar.
[CI-inventeringen](specialist-pilot-20261028/ci-partitions.json) bevarar
alla tidigare 4 201 noder exakt en gång och lägger till 11, totalt 4 212.
Hosted CI måste passera på leveransens exakta head före integration.
[Separat teststatus](specialist-pilot-20261028/test-status.json) redovisar
att den bredare grocery-sviten inte blev färdig inom 600 s. Dess fem
observerade fel gäller äldre ICA-förväntningar och återkommer med main:s
oförändrade moduler; de har varken dolts, hoppats över eller räknats gröna.

Ingen beta-/produktionsaktivering, schedulerändring, breddad Coop-allowlist,
inloggningsautomation eller ändring av den frysta jämförelsen ingår.

Det tidigare beslutskravet kom från uppdragets punkt 5: ”Först om
en ny handlare, källa eller allowlist behövs ska ett konkret separat
beslutsunderlag tas fram.” Ägarens ja gäller denna pilot och ska inte
efterfrågas igen. Kvalificering inom de fem artiklarna får fortsätta;
en annan artikel eller produktionsaktivering ingår inte i beslutet.
