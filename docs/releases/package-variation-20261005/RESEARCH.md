# Riktade produktfakta och öppna ärenden

Exakta käll- och produktidentiteter, hashvärden, tider och öppna fält finns även i [RESEARCH.json](RESEARCH.json).

Tidigare [RESEARCH.md](../recipe-usability-20261005/RESEARCH.md) och [RESEARCH.json](../recipe-usability-20261005/RESEARCH.json) lästes före de nya källkontrollerna. Samma frysta priser från 4 oktober används i varje replay.

## Ärter, faktiskt korgbyte

Willys Lund har en fryst prisrad för Apetit *Nordiska Ärtor*, 1 kg, 34,92 kr, extern produkt `101698397_ST`. Den hashverifierade råposten från 2 oktober har en produktbild vars EAN-nyckel `06430104920418` klarar kontrollsiffra. En [leverantörslämnad Validoo-deklaration som visas hos Out of Home](https://outofhome.se/nordiska-artor-10x1kg) anger motsvarande konsument-EAN `6430104920418`, Apetit, 1 kg, ärtor 100 % och näring per 100 g: 75 kcal, fett 0,8 g, kolhydrat 9,5 g och protein 5,6 g. Den sidan hämtades 2026-10-05 20:47:02 UTC; råhash `2641afc5c30de71b8d51c97b8fa3738f8c328411cc4b7d0e222b89fe72145788`. Utgivaren är återförsäljaren; sidan tillskriver uttryckligen uppgifterna Apetit Ruoka Oy via Validoo. Påståendet om ursprung är därmed spårbart men inte en egen Apetit-värd publikation.

Kopplingen kräver dessutom exakt namn, varumärke och fast förpackning samt den hashverifierade frystmärkningen i samma råpost. Ingen GTIN har uppfunnits i den historiska prisraden. Den nya näringen används enbart för den identifierade produkten och är inte en generisk ärtreferens. I den fasta menyn ersätter den två 600 g-påsar från Coop (41,54 kr) med en 1 kg-påse från den redan valda Willys-kanalen (34,92 kr). Betalningen sjunker 6,62 kr; näringen prövas åter per recept och checkout/audit körs normalt. Se [RESULTS.md](RESULTS.md) och [MENUS.json](MENUS.json).

Tillverkarens tidigare indexerade produktsida `/produkt/arter/` visade en 1 kg-produkt i sökresultat men gav vid faktisk hämtning 2026-10-05 en annan produkt, *Ärter, majs och paprika 600 g*. Den användes därför inte som deklaration för 1 kg-påsen.

## Paprikapulver, konkret stopp

Samma frysta Coop Online Syd-snapshot innehåller Santa Maria 200 g (GTIN `7311311014499`) för 74,50 kr och 37 g (GTIN `7311311015182`) för 25,50 kr. Den fasta menyn behöver 14 g. Båda har egna kvalificerade makrovärden per 100 g. 200 g-varianten har ett exakt förpackningsbundet mildhetsintyg från tillverkaren. [Dabas produktblad för 37 g](https://www.dabas.com/productsheet/07311311015182) och [Santa Marias sida för 37 g](https://www.santamariaworld.com/se/produkter/kryddor/paprika-liten/) identifierar den mindre varan men ger inte samma entydiga uttalande om mildhet för just den förpackningen. E-handelsnyckelordet ”Mild” i Dabas-listan bland många söktermer har inte behandlats som ett variantbundet styrkebesked. 37 g stoppas därför före helkorgsjämförelse; 200 g-produktens uppgift har inte överförts. Ett exakt tillverkarintyg eller förpackningsfoto som binder mildhet till GTIN `7311311015182` är nästa researchärende.

Andra prisrader i snapshoten omfattar Vegeta *Söt* 100 g för 17,51 kr och Eldorado *Milt* 70 g för 14,90 kr i Willys-kanal. De får inte en positiv närings-/variantkvalificering genom namnlikhet. Behov, pris och hög restandel bevisar alltså inte en giltig billigare korg.

## Fortsatt prioritet

Den tidigare restlistan gäller fortfarande: torra chiliflingors näring och styrka, majsens avrunna mängd och näringsbasis, rökt paprikas hämtning/form, exakt färdigbakad pita, mjölkens massbasis och äggets ätbara gram. Varje ärende måste bindas till prissatt produkt/variant och kontrolleras mot övriga samtidiga stopp innan ett recept räknas som räddat. Inga nya kataloghämtningar eller betalda modell-API-anrop gjordes här.
