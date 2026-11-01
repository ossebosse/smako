# Fortsatt hinderarbete och receptimport 2026-11-01

**170 ytterligare varianter och 70 nya grundrätter är innehållsgranskade och
importerade.** Biblioteket växer från **975/2 570 till 1 045/2 740**. Alla
170 har klarat ordinarie slutlig inköpskontroll med tillåtna uppskattningar
i den frysta referensen. **94 klarar även exakt inköp**; 76 är datablockerade
i det läget. Inget av dessa korgprov nådde tidsgränsen.

De fem faktiskt mottagna leveranserna innehåller **189 grundrätter / 501
varianter**. Totalt har **278 varianter i 111 grundrätter** importerats:
105 hela familjer och sex delvis importerade. **223 varianter återstår**.
Den senast mottagna ZIP-filen med 24 grundrätter / 62 varianter har 39
importerade varianter och 23 kvar i kön. Ett godkänt syskon gör inte hela
familjen godkänd.

Originalfilerna är bytebevarade. Först utfärdades 170 versioner 1.0.1.
Därefter utfärdades 67 efterföljare för 64 av varianterna: 50 för portionsinstruktioner,
satsstorlek eller fiskmetadata, nio för lammstek/upptining och åtta efter kontroll
av faktiskt valda frysta produkter. Tre pastavarianter har kedjan 1.0.1 → 1.0.2 → 1.0.3.
Alla 67 ersatta versioner är återkallade men bytebevarade. Samtliga recept är **inte provlagade**. Tider och nya kulinariska doser är granskade
författaruppskattningar. De 3 625 tidigare utgivna versionerna, samtliga
2 570 tidigare aktuella varianter och de 2 200 ursprungsreferenserna bevaras.
Ingen betaaktivering, insamling eller ändring av användarprofiler ingår.

## Åtgärder som öppnade recepten

39 ytterligare namn/form/enhetsidentiteter har **232 individuellt granskade
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
och `qualification-stageN.json` (N = 1–27). Granskningarna binder
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

Steg 23–27 gav ytterligare 13 av totalens 170 varianter: två pasqualina
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
uttryckliga återkallelser av just de 67 nyutgivna föregångarna, bundna till
efterföljare av samma bas/variant med strikt stigande versionsnummer.
Varje mellanversion och dess kvalificeringskvitto bevaras. Inga versioner som fanns före denna
omgång får återkallas eller ändras. Tidigare återkallelser och referens-ID:n
bevaras. Ingen
täckningsbaslinje regenereras för att göra testresultat gröna.

Den samlade riktade verifieringen gav **679 godkända tester** i två körningar:
128 för de nya produkt-/processgränserna och tidigare importkontrakt samt
551 för importkvitton, hela ingrediensregistret och bibliotekets kvalitetskrav.
Ruff på samtliga ändrade Pythonfiler, compileall och `git diff --check` passerade.
Full CI och täckningsöverblicken krävs därutöver före merge till main.

Efter de sista innehållsrättningarna passerade ytterligare **610 riktade tester**:
591 för importkvitton, ingrediens-/processgränser, gamla hashvärden och
bibliotekets kvalitetskrav samt 19 för portions-/versionskedjor, frysta
produktformer och kostkategorier. Alla slutliga nya versioner har egna
godkända korgprov; inget gammalt prov har skrivits om för att få ett godkännande.

## Kvarvarande kö och nästa leverans

[Variantkön](queue.json) redovisar samtliga 501 käll-ID:n. De 223 kvarvarande
består av **201 med register-/författarhinder** och **22 strukturellt giltiga
utkast med konkret saknat produktstöd**. De senare har omprovats i båda
inköpslägena, se [ingrediensprovet](remaining-native-inputs.json).

[Ingrediensliggaren](ingredient-blockers.json) rangordnar återstående
hinder med sökord, antal träffar, produktetiketter, berörda recept och nästa
åtgärd. Störst är makrutlimeblad (19), räkpasta (18), curryblad (16), epazote
och thaibasilika (10 vardera). Antalen överlappar. En tom sökning i den frysta
referensen bevisar inte att en vara saknas i handeln.

Thaibasilika i kruka har ingen verifierad bladmassa; ett framtida recept med
styckdos behöver ett eget inköpsbevis. Makrutlimeskal i currypasta är inte
limeblad. Surimi är inte krabbkött. Vanligt majsmjöl är inte verifierad masa
harina. Dessa skillnader har inte tagits bort för att öka antalet importer.
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
--native-probe .local/recipe-unblock-round2/pending-latest-inputs.json` med dess
hashbundna underlag. Ändra inte redan utgivna steg; skapa en ny version för
senare korrigeringar och en ny rapport för nästa granskningsomgång.
