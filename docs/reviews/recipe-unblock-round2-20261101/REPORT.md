# Fortsatt hinderarbete och receptimport 2026-11-01

**224 ytterligare varianter och 89 nya grundrätter är innehållsgranskade och
importerade.** Biblioteket växer från **975/2 570 till 1 064/2 794**. Alla
224 har klarat ordinarie slutlig inköpskontroll med tillåtna uppskattningar
i den frysta referensen. **127 klarar även exakt inköp**; 95 är datablockerade
och två stoppas i checkout i det läget. Inget av dessa korgprov nådde tidsgränsen.

De fem faktiskt mottagna leveranserna innehåller **189 grundrätter / 501
varianter**. Totalt har **332 varianter i 130 grundrätter** importerats:
124 hela familjer och sex delvis importerade. **169 varianter återstår**.
Den senast mottagna ZIP-filen med 24 grundrätter / 62 varianter har 44
importerade varianter och 18 kvar i kön. Ett godkänt syskon gör inte hela
familjen godkänd.

Originalfilerna är bytebevarade. 224 godkända varianter fick först version 1.0.1.
Därefter utfärdades 76 efterföljare för 73 av varianterna: 50 för portionsinstruktioner,
satsstorlek eller fiskmetadata, nio för lammstek/upptining, åtta efter kontroll
av faktiskt valda frysta produkter, tre för skalbart kokvatten, tre för kort pasta och tre för Pindi choles blötläggningsvatten. Tre pastavarianter har kedjan 1.0.1 → 1.0.2 → 1.0.3.
Alla 76 ersatta versioner är återkallade men bytebevarade. En ytterligare lokalt
utgiven version underkändes i korgprovet och återkallades; den räknas inte som import. Recepten är **inte provlagade**. Tider och nya kulinariska doser är granskade
författaruppskattningar. De 3 625 tidigare utgivna versionerna, samtliga
2 570 tidigare aktuella varianter och de 2 200 ursprungsreferenserna bevaras.
Ingen betaaktivering, insamling eller ändring av användarprofiler ingår.

## Åtgärder som öppnade recepten

43 ytterligare namn/form/enhetsidentiteter har **258 individuellt granskade
produktkopplingar** i befintliga butikskontexter. Registret finns i
[`expansion-round2-20261101.json`](../../../backend/app/data/ingredients/expansion-round2-20261101.json).
Varje koppling behåller artikel/GTIN, butik, hela produktnamnet, märke,
förpackning, källsnapshot, mängdbasis och sammansättningssignatur.
Ingen ny närings-, allergen- eller ekologisk deklaration har lagts till.

| Hinder | Genomförd åtgärd |
|---|---|
| Saknad rätt form eller enhet | Bland annat fryst grön jalapeño, mald ancho, torr salvia, kryddnejlika och mejram, ml matlagningsvin/fond/Worcestershire samt gram filmjölk. Befintliga ml-recept får ingen påhittad densitet. |
| Frityrolja, vassle och kasserat kokspad | Nytt uttryckligt kontrakt för okända processförluster, utan antagen upptagnings- eller utbytesandel. |
| Skal, ben och putsning | Hela ägg köps i antal; hel kyckling, oxsvans, lägg, lever, kokbanan och ost får rätt inköpsbasis och synlig beredning. Ätlig slutvikt antas inte. |
| Avrunna konserver | Grebbestads ansjovis, Abba ätklar sill och Felix saltgurka binds till deklarerad avrunnen mängd. Källans redan avrunna jämförmängd reduceras inte en gång till. |
| Produkt finns men butikskoppling saknas | Sex exakta kardemummakopplingar samt elva kopplingar för samma frysta koriander/avokadoprodukter. Det löste verkliga hinder vid högst två butiker. |
| Kulinariska alternativ | Bland annat svensk surdegsfralla, lagrad pecorino, ungnötslever, färdig tomatillosalsa, musselkött utan skal och corned beef. Nytt namn, ny uttrycklig dos/metod där det behövs; inga falska råvarualias. |

Varje steg har separat `recipe-review-stageN.json`, `import-stageN.json`
och `qualification-stageN.json` (N = 1–48, där steg 34 är underkänt och återkallat). Granskningarna binder
original-ID, originalfilens hash, nytt versions-ID, innehållshash, samtliga
mängdändringar och kulinarisk jämförelse. Receptens ingrediensantal,
arbetssteg och synliga instruktioner följer samma innehåll.

Exempel på avsiktliga mängdändringar är 158 g avrunnen ansjovis i stället för
220 g med spad, fyra råa hela ägg i stället för en angiven kokt äggvikt,
600 g hel mogen kokbanan i stället för 300 g skalat fruktkött och 680 g
färdigkokt corned beef i stället för 700 g rå bringa. Dessa är nya receptdoser,
**inte uppmätta omräkningsfaktorer**. Originalen skrivs inte över.

Kokbananens mognad måste kontrolleras före matlagningen. Katalogen bevisar
inte mognadsgrad och eventuell mognadstid ingår inte i tillagningstiden.
Frysta råvaror får uttrycklig upptining/genomhettning där det behövs;
upptiningssaft, stekfett och dressing behålls när den granskade metoden säger det.
Aktiv tillsyn, avrinning, temperaturkontroller och kylöverföring skiljs från
passiv kokning, ugnstid och väntan.

## Senare granskning av fem ytterligare hinder

Steg 23–27 gav ytterligare 13 av totalens 224 varianter: två pasqualina
med uttryckligen 600 g spenat och kvarvarande mejram/muskot, två frijoles
puercos med svensk färsk chorizo, tre rogan josh med paprika/cayenne samt
sex patatato/tsigariasto med lamm. Tillbehör och kryddskillnader bevarar
meningsfulla variantnivåer. Get, mangold, mexikansk chorizo och kashmirichili
har inte fått falska identitetsalias.

[Garants färska chorizo](https://www.garantskafferiet.se/vara-produkter/chark/korv/chorizo/)
är en rå fläsk-/nötkorv, inte färdig grillkorv. Ny dos är 35 g med fjälster,
vars borttagning förblir en okänd förlust. Fläsk- och nötköttsundantag samt
vegetarisk/vegansk kost spärrar den. Paprika/cayenne är en separat
författad dos, 8/0,6 g, med stöd för själva kombinationen i
[Ainsley Harriotts rogan josh](https://www.ainsley-harriott.com/recipe/lamb-rogan-josh/).
Ingen likvärdig hetta påstås. Lammalternativen har stöd i
[Visit Greece om patatato](https://www.visitgreece.gr/el/experiences/architecture/local-architecture/amorgos-gastronomy)
och [restaurangens tsigariasto hos Gastronomos](https://www.gastronomos.gr/syntagh/tsigariasto/50594/).
Receptens egna mängder och tillbehör är fortfarande separat granskade.

Korgarna visade fryst lammstek. Därför fick de nio lammvarianterna nya
1.0.2-versioner med sju specifika produktkopplingar för **benfri lammstek**,
planerad kylupptining i 24 timmar och okänd putsförlust. Lammytterfilé,
rostbiff och benbärande stek får inte fylla denna insats. Gramdosen avser nu
hela uppvägda produkten före putsning, med tillhörande upptiningsvätska;
ingen likvärdig ätlig mängd antas. All sådan vätska genomkokas i grytan.
[Granskning](lamb-corrections.json) och [korgprov](qualification-lamb-corrections.json)
binder nio av nio godkända korgar i uppskattat läge.

Ytterligare åtta efterföljare beskriver de valda produktformerna:
Sopa de lima har planerad kycklingupptining och aktiv temperaturkontroll;
melitzanosalata har uttryckligen genomhettad vitlök; aglio e olio har
hackad färsk/fryst vitlök, persilja genomhettad före pastan och okända
förluster vid avrinning. Ingrediensmängderna är oförändrade. Se
[granskningen](selected-product-corrections.json) och
[korgprovet](qualification-selected-product-corrections.json).

Summerad väntetid kan nu vara upp till samma 48-timmarsgräns som total tid,
så 24 timmars upptining plus passiv kokning ryms i innehållsmodellen.
Ett enskilt steg är fortfarande högst 24 timmar. Användarens tidsfilter
respekteras: exempelvis högst 24 timmars väntan utesluter dessa längre recept.
Redan kylförvarat kött behöver ingen upptining; beräknad total tid är försiktigt
planerad för det frysta alternativet. Inget av detta är en uppmätt provlagning.

## Ytterligare prövningar av enskilda rätter

Steg 28–38 gav ytterligare **28 godkända varianter**. Varje alternativ har
synligt ändrat namn, egna doser och granskad beredning. Underlagen styrker
valet av alternativ; de bevisar inte likvärdig smak, näring eller vikt.

| Rätt / antal | Granskat alternativ och metodstöd |
|---|---|
| Spetsofai / 3 | Färsk salsiccia med ätligt fjälster, kvarvarande stekfett och temperaturkontroll. [Receptförfattarens korvalternativ](https://www.mygreekdish.com/recipe/spetsofai-sausages-with-peppers-and-tomato-sauce/) och [Garants produkt](https://production.garantskafferiet.se/vara-produkter/chark/korv/salsiccia/). |
| Pasta alla Norma / 3 | 75 g pecorino med okänd kantputsning i stället för ricotta salata. [Jamie Olivers alternativ](https://www.jamieoliver.com/recipes/pasta/sicilian-spaghetti-alla-norma/). Skalbart kokvatten rättades i version 1.0.2. |
| Pitarakia / 2 | Feta och pecorino i en tunn ostpaj, med okänd putsning och frityroljeupptagning. [My Greek Dish](https://www.mygreekdish.com/recipe/greek-cheese-pies-milos-pitarakia-milou/). |
| Rajas con crema / 3 | Grillad paprika och jalapeño, färdiga majstortillas och avrunnen mozzarella. Okänd förlust vid skalning; fryst koriander genomhettas i såsen. [Maricruz Avalos](https://www.maricruzavalos.com/rajas-con-crema/). |
| Nam prik ong / 3 | Uttrycklig fisksåsversion av fläskfärsdippen utan räkpasta. Alla varianter spärras vid fiskundantag men räknas som kött i menyfördelningen. [Thai Foodie](https://thai-foodie.com/thaifood/thai-style-lettuce-wraps-nam-prik-ong-น้ำพริกอ่อง/). |
| Patishapta / 2 | Mörkt muscovadosocker i kokosfyllningen, med bevarade skillnader mellan variantnivåerna. [Receptförfattarens sockerbruksalternativ hos Culture](https://culturecheesemag.com/recipes/indian-sweet-crepes-patishapta/). |
| Pasta ’ncasciata / 3 | Avrunnen mozzarella i stället för caciocavallo; faktiskt köp måste ge kort pasta. [Galbanis version](https://www.galbani.it/ricette/pasta-ncasciata). |
| Tod man pla / 3 | Färskt citrongräs i stället för limeblad, finfördelad fisk och ägg, temperaturkontroll samt okända puts-, upptinings- och oljeförluster. [Ateliers & Saveurs recept](https://www.ateliersetsaveurs.com/uploads/recipes/culinary/pdf/thai-fish-cakes-with-sweet-and-sour-chili-sauce-en-751-v1.pdf). |
| Tsouxti / 3 | Smöret bryns separat; feta tillsätts efter pastan och behandlas inte som torr myzithra. Fryst persilja genomhettas. [Greek Cooking Made Easy](https://www.greekcookingmadeeasy.com/allrecipes/greek-sizzling-tsouhti-pasta-with-charred-butter-grated-cheese-and-fried-eggs-from-mani). |
| Pasta e patate / 3 | Uttryckligen orökt, avrunnen mozzarella och kort pasta. Stärkelsevattnet stannar i grytan och vattenmängderna skalas. [Gennarinos metod](https://www.gennarino.org/wordpress2/ricetta-della-pasta-e-patate/). |

Granskningen av faktiskt köpt pasta hittade spaghetti till pasta ’ncasciata.
Tre nya versioner kräver därför befintliga `pack:pasta` för kort pasta;
[korgprovet](qualification-pasta-shape-corrections.json) verifierar 3/3 med
uppskattningar och 2/3 exakt. Separat rättades kokvattnets portionsskalning
för Norma; [dess korgprov](qualification-alternative-portion-corrections.json)
verifierar 3/3 med uppskattningar. Föregångarna är bevarade och återkallade.

Khao tom mat prövades med bakpapper i stället för bananblad med stöd från
[Charinyas egen metod](https://charinyaskitchen.wordpress.com/2018/06/22/khow-tom-mud/).
Det fullständiga korgprovet visade därefter att **glutinöst ris saknar verifierat
köp**. Vanligt sushiris ersätter inte den rissorten. Den lokala versionen
återkallades före main och räknas varken som importerad eller godkänd.
[Avslagskvittot](rejected-stage34.json), [provet](qualification-stage34.json)
och de utgivna originalfilerna är bevarade. Efter detta används ingrediensprov
före lokal utgivning och alltid ett fullständigt korgprov före godkänd import.

## Okända processförluster förblir okända

`smako-authored-losses-v3` binder en okänd processförlust till ett faktiskt
steg och dess ingredienser. Det kan exempelvis vara fritering följd av
avrinning, silad vassle, bortplockade lagerblad eller skalning efter kokning.
Inga procentsatser eller näringsvärden räknas fram ur metadata.

Inköpsbehovet kan fortfarande beräknas från den uttryckliga insatsen.
Serverad vikt och näring blir däremot okända. Om användaren kräver en hård
närings- eller portionsviktsgräns stoppas receptet med `DATA_BLOCKED`.
Utan sådana gränser redovisas näringen som `UNKNOWN`, utan värden. Detta är
inte ett näringsgodkännande. Befintliga V2-versioner och deras hashar ändras
inte och alla äldre recept påstås inte vara omgranskade.

Regressionerna använder både syntetiska processfall och verkligt utgivna
Gulab jamun, Bohuslänsk äggost, blodpalt, Murgh musallam och Cacio e pepe.
De kontrollerar bland annat min/max portionsvikt, protein och energi.

Även kostfiltren kontrollerar de nya kulinariska namnen. Ätklar sill och svensk
ansjovis omfattas av ”ingen fisk” även om en äldre förseglad innehållsflagga
saknade namnet. Hel kyckling räknas som kyckling i menyfördelningen; råa
vannameiräkor och musselkött räknas som skaldjur och kan inte fylla en fiskkvot.
Detta är kategorisering för användarval, ingen produktidentitetsalias.
Äldre innehållshashar skrivs inte om. Framtida författande använder samma
fisknamn när metadata skapas.

En separat portionsgranskning rättar fasta livsmedelsmängder i text,
konservantal och processvatten som tidigare skrevs exempelvis ”85 ml hett
vatten” eller ”300 ml kokvatten”. Ingrediensmängder, enheter, former och
produktkrav är identiska i de 50 efterföljarna. Processvattnet skalas nu
uttryckligt; temperaturer och mått ändras inte. Murgh musallam och fläsklägg
har sex varianter med `servings_multiple=4`: endast 4, 8 eller 12 portioner,
med flera hela stycken vid större satser. Övriga portionsval finns kvar men
väljer andra recept. [Granskningen](portion-corrections.json) och
[det nya korgprovet](qualification-portion-corrections.json) binder samtliga
50 efterföljare; 50/50 passerar uppskattat inköp och 19/50 exakt inköp.
Totalen ovan räknar varje aktuell variant en gång.

Exporten till nästa receptförfrågan tar nu med separat granskade
enhetsalternativ och processförluster. Den nya gramfilen för filmjölk tappas
alltså inte bort när ml fortfarande är standardenheten. En riktad kontroll
av export, kostgränser och befintliga författarkontrakt gav 117 godkända tester.

## Fortsatt genomgång av produkt- och örtblockeringar

Steg 39–48 öppnade ytterligare **26 varianter**. Samtliga har fullständiga
korgprov och synligt namngivna anpassningar. Den enkla vada pav-varianten
släpps in separat; dess två syskon med curryblad kvarstår i kön.

| Rätt / antal | Granskat alternativ och metodstöd |
|---|---|
| Chicken 65 / 3 | Uttrycklig version utan curryblad och med egen paprika/cayenne-dos. [Misty Ricardo](https://mistyricardo.com/chicken-65-recipe/) gör bladen valfria; [Genevieve Taylor](https://curryforchange.org.uk/recipes/chicken-65) använder paprika/chili. Kycklingens upptining och okända oljeupptag är uttryckliga. |
| Pad prik king tofu / 3 | Egen infusion av 1 g torkade makrutblad. [Importören A Chau Lien](https://achaulien.se/products/dried-lime-leaves-12-x-25g-krua) bekräftar KRUA-produktens bladidentitet. Alla blad silas bort; ingen färsk-torr-faktor eller näringsöverföring antas. |
| Paprika en nogada / 3 | Mild paprika med fruktig fläskfärs, valnötssås och granatäpple. [Receptförfattaren](https://stefangourmet.com/2019/12/20/chile-relleno-en-nogada-stuffed-chile-with-walnut-sauce-and-pomegranate/) anger paprika som alternativ. Råvaran vägs efter urkärning men före rostning; skalförlust är okänd. |
| Pölsa / 3 | Högrev och gross ungnötslever med korngryn; ingen identitetsalias för hjärta eller fläsklever. Kött-/levermetoden stöds av [ICA](https://www.ica.se/recept/polsa-729947/) och [Coop](https://www.coop.se/recept/polsa/). Leverputsning och bortkastade kokspad är okända förluster. |
| Pindi chole / 3 | Egen kryddblandning enligt metodstödet från [Padhuskitchen](https://www.padhuskitchen.com/2015/02/pindi-chole-recipe-how-to-make-pindi.html), med citronalternativ från [Spicing Your Life](https://www.spicingyourlife.com/how-to-make-pindi-chole/). Teet, kikärtsmetoden och handgräddat bröd bevaras. Version 1.0.2 rättar blötläggningsvattnets skalning; tre nya korgprov. |
| Cornflakes-chivda / 2 | Naturella färdigrostade frukostflingor, rostade osaltade jordnötter och kvarvarande kryddolja. [Manali Singh](https://www.cookwithmanali.com/cornflakes-chivda/) skiljer färdiga cornflakes från rå makai poha; [Coles kök](https://www.coles.com.au/recipes-inspiration/recipes/chivda) gör curryblad valfria. |
| Khua kling / 3 | Röd currypasta, silad torr limebladsinfusion och citrongräs vägt före ansning. [Praews recept](https://hungryinthailand.com/khua-kling/) anger röd pasta som alternativ. Allt köttfett behålls medan vattnet kokas bort; syskonens ägg köps råa i antal. |
| Arroz a la tumbada / 2 | Korianderversionerna behåller skalade skaldjur, all upptiningsvätska och den soppiga risformen. [Irenes eget recept](https://mysliceofmexico.ca/2025/02/06/arroz-a-la-tumbada-a-rice-and-seafood-mish-mash/) använder koriander och valfri epazote. |
| Papadzules / 3 | Pumpakärnssås med koriander, räknade råa ägg och färdiga mjuka majstortillas. [Barilla Foundations recept](https://fondazionebarilla.com/en/recipes-archive/papadzules/) anger koriander som örtalternativ. All sås serveras; fryst avokado får egen upptining. |
| Vada pav / 1 | Enkelvarianten får 416 g mjukt svenskt hamburgerbröd. [Dan Toombs](https://greatcurryrecipes.net/2018/04/30/vada-pav/) använder mjuka hamburgerbröd. All kikärtssmet serveras, fryst vitlök genomkokas och frityroljeupptaget förblir okänt. |

Den manuella produktsökningen missade tidigare särskrivningen **Lime Blad
Torkade**. Den hittar nu även sådana etiketter, men ger fortfarande bara
kandidater för sakgranskning. De två verifierade KRUA-kopplingarna gäller
endast den separata torra identiteten. Inga automatiska produkt-/prisalias
eller färsk-torr-omräkningar införs.

De två andra tillkommande produktformerna är [Garants färdiga cornflakes](https://www.garantskafferiet.se/vara-produkter/skafferi/flingor--musli/corn-flakes/)
och [Pågens mjuka hamburgerbröd](https://www.pagen.se/produkter/korvbrod-hamburgerbrod/hamburgerbrod/),
med åtta exakta butikskopplingar vardera. Befintlig deklaration för socker,
salt, kornmalt eller sesam raderas inte; ingen ny närings- eller allergenfakta
kopieras från webbsidorna.

Nya steg stoppas före lokal utgivning om en uttrycklig vattenmängd inte
följer portionsantalet. Granskade ingrediensrader kan återskapas selektivt
med `review_expansion_round2.py --only 'namn|form|enhet' --inventory ...`.
Kommandot kräver samma frysta referens och bevarar andra registerrader.

## Källor och kvalificeringsscope

Mängdbevis och korta källutdrag ligger vid respektive produktkoppling.
Utdragens SHA-256 avser den angivna UTF-8-texten, inte hela webbsidan.
Några centrala primärkällor:

- [Grebbestads/Orkla via Dabas](https://www.dabas.com/productsheet/07311170022116): 125 g burk, 79 g avrunnen skarpsill.
- [Abba](https://www.abba.se/produkt/5-minuterssill-hela-fileer/) bekräftar ätklar 5-minuterssill; [Orklas leverantörsuppgifter hos Mathem](https://www.mathem.se/se/products/10375-abba-sill-hela-fileer-5-minuter/) anger 430/210 g.
- [Orklas leverantörsuppgifter om Felix saltgurka](https://www.mathem.se/se/products/9544-felix-saltgurka-hel/) anger 700/340 g och den saltare gurktypen.
- [Miramar via Dabas](https://www.dabas.com/productsheet/07350001292809) avser rätt råa skalade räkor i 400 g-förpackning; ingrediensprocent blir ingen avrunnen andel.
- [Garant pistaschkärnor](https://www.garantskafferiet.se/vara-produkter/choklad--snacks/notter--torkad-frukt/pistaschkarnor/), [Garant blåmusslor utan skal](https://www.garantskafferiet.se/vara-produkter/fisk--skaldjur/kott-fagel--fisk/blamusslor-utan-skal/), [Yora/Clemente Jacques via Dabas](https://www.dabas.com/productsheet/07501052473505) och [Al Madinas produktkatalog](https://www.almadina.se/products) fastställer de uttryckliga produktformerna.

Inköpsproven använder 89 458 frysta produktposter i 52 butikskontexter,
prisklocka **2026-10-23 06:00:02.869273 UTC**, högst två butiker, fyra
middagsportioner eller en frukost-/mellanmålsportion och tomt skafferi.
Inga extra kost-, allergi-, närings- eller ekologiska begränsningar har lagts
på just dessa prov; näringsuppskattningar tillåts. Ordinarie slutlig audit
måste vara godkänd. Gränsen är 20 sekunder per korg, timeout skulle vara okänt.

Universumhash `06cbf0b12e619f09dd3709b808916d1c74676859d246ad72f74d52d0e6d91857`
och faktahash `23c45ae2e4f27222833028277b3b9ca9426a232408baa4971c9e8114b766abca`
är oförändrade. Varje kvitto behåller sin faktiska metod- och manifesthash;
importerna gjordes successivt och har inte samma manifest. Det här är
enskilda fullständiga korgprov, **ingen ny mätning av varm menyplaneringstid**.

[Sammanställningen](summary.json) och [manifestövergången](library-transition.json)
är maskinläsbara. Övergången tillåter nya disjunkta, hashbundna paket och
uttryckliga återkallelser av just de 76 nyutgivna föregångarna, bundna till
efterföljare av samma bas/variant med strikt stigande versionsnummer.
Den underkända lokala versionen binds dessutom till sitt fullständiga misslyckade
korgprov, ursprungspaketets hash och återkallelseskäl. Den kan inte väljas som
aktuellt recept. Varje mellanversion och dess kvalificeringskvitto bevaras.
Inga versioner som fanns före denna
omgång får återkallas eller ändras. Tidigare återkallelser och referens-ID:n
bevaras. Ingen
täckningsbaslinje regenereras för att göra testresultat gröna.

Den samlade riktade verifieringen gav **679 godkända tester** i två körningar:
128 för de nya produkt-/processgränserna och tidigare importkontrakt samt
551 för importkvitton, hela ingrediensregistret och bibliotekets kvalitetskrav.
Ruff på samtliga ändrade Pythonfiler, compileall och `git diff --check` passerade.
Full CI och täckningsöverblicken krävs därutöver före merge till main.

Efter de tidigare innehållsrättningarna i steg 23–27 passerade ytterligare **610 riktade tester**:
591 för importkvitton, ingrediens-/processgränser, gamla hashvärden och
bibliotekets kvalitetskrav samt 19 för portions-/versionskedjor, frysta
produktformer och kostkategorier. Alla slutliga nya versioner har egna
godkända korgprov; inget gammalt prov har skrivits om för att få ett godkännande.

Slutkontrollen av samtliga 224 varianter gav **825 godkända offline-tester**,
utan fel eller överhoppade testfall. Den omfattar alla importkvitton,
versionskedjor, ingrediensgränser, portionsskalning, kostfilter och hela
bibliotekets innehållskrav. Ruff, compileall och diffkontroll passerade.
De tidigare testkörningarnas antal överlappar och ska inte summeras.

## Kvarvarande kö och nästa leverans

[Variantkön](queue.json) redovisar samtliga 501 käll-ID:n. De 169 kvarvarande
består av **149 med register-/författarhinder** och **20 strukturellt giltiga
utkast med konkret saknat produktstöd**. De senare har omprovats i båda
inköpslägena, se [ingrediensprovet](remaining-native-inputs.json).

[Ingrediensliggaren](ingredient-blockers.json) rangordnar återstående
hinder med sökord, antal träffar, produktetiketter, berörda recept och nästa
åtgärd. Störst är räkpasta (15), curryblad (13), makrutlimeblad och thaibasilika
(10 vardera), guajillochili (9) och palmsocker i inköpt form (8). Antalen överlappar. En tom sökning i den frysta
referensen bevisar inte att en vara saknas i handeln.

Thaibasilika i kruka har ingen verifierad bladmassa; ett framtida recept med
styckdos behöver ett eget inköpsbevis. Makrutlimeskal i currypasta är inte
limeblad. Surimi är inte krabbkött. Vanligt majsmjöl är inte verifierad masa
harina. Dessa skillnader har inte tagits bort för att öka antalet importer.
Grön papaya behövs som enzymatiskt mörningsmedel i Galouti kebab; gurka eller
äpple fyller inte den funktionen. Färsk majs i uchepos behöver rå stärkelse;
förkokta majskolvar är inte samma insats. Den påträffade misopastan saknar
tillräcklig ingrediensdeklaration och är inte automatiskt thailändsk Tao Jiao.
Andra kvarvarande hinder är bland annat tapiokastärkelse/pärlor, risflingor,
mangold, rensad bläckfisk, vissa bönformer, specialostar och fermenterade
smaksättare. Befintliga råvarualternativ i liggaren behöver separat
receptgranskning och kan fortfarande ha blockerade syskon.

Fortsätt ta emot ZIP med 10–40 rätter utan att vänta på ett större arkiv.
Det felaktigt refererade 72/194-arkivet finns inte och ska inte efterfrågas.
Nästa nyskrivna paket är **022**. Mot beställningen återstår **811
grundrätter / 2 249 varianter**, med 627 middagar, 108 frukostar och
76 mellanmål. Det räknas mot mottagna utkast, inte bara importerade recept.
Använd [beställningsjournalen](../../recipes/REQUESTING-RECIPES.md) och inkludera
alla mottagna utkast i nästa dubblettunderlag.

Efter ny leverans: kör `audit_expansion_queue.py` till en ny lokal katalog.
För att återskapa denna avslutade rapports beslut används
`finalize_expansion_round2_review.py --universe .local/coverage-inputs/universe.json
--native-probe .local/recipe-unblock-round2/pending-final20-inputs.json` med dess
hashbundna underlag. Ändra inte redan utgivna steg; skapa en ny version för
senare korrigeringar och en ny rapport för nästa granskningsomgång.
