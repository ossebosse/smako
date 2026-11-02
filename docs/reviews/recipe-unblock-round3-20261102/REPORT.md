# Leverans 21/55 och fortsatt hinderarbete, 2026-11-02

**20 av den nya leveransens 55 varianter är granskade och importerade, från
åtta grundrätter.** 14 gick in efter beredningsgranskning. Därefter öppnades
ytterligare sex genom tre uttryckliga råvaruanpassningar. Biblioteket växer
från **1 072/2 822 till 1 080 grundrätter / 2 842 aktuella varianter**.

Alla 20 har godkända fullständiga inköpskorgar i referensens uppskattade läge,
14 även i exakt läge. Sex har mängd-/produktblockering i exakt läge;
inga korgprov nådde tidsgränsen. Recepten är inte provlagade.
Ingen betaaktivering, insamling, profiländring eller varm menytidsmätning ingår.

## Mottagning och beställningsräkning

35 originalfiler från `Smako-21-nya-grundratter-55-varianter.zip` är bevarade
byte för byte. Alla levererade filhashar stämmer. Tre författarpaket,
022–024, innehåller 21 baser / 55 varianter: 13 middagar, en frukost och sju
mellanmål. [Mottagningskontrollen](intake-audit.json) fann 21 native-kompatibla
och 34 registerblockerade utkast före innehållsgranskningen. Kompatibilitet
är inte importgodkännande.

Faktiskt mottagna sex ZIP innehåller **210 grundrätts-ID:n / 556 varianter**.
Leveransens egna högre historiska antal inkluderar fortfarande hänvisningar
till arkiv som ägaren uppgett inte finns. Dessa räknas inte. Nästa nyskrivna
paket är **025**. Beställningen har 790 baser / 2 194 varianter kvar att leverera:
614 middagar, 107 frukostar och 69 mellanmål. Det är mottagningsräkning,
inte en slutlig kulinarisk nyhetsattest för alla återstående utkast.

Totalt från beställningen är nu **380 varianter i 146 grundrätter** importerade:
142 hela familjer och fyra delvis. **176 varianter återstår**, varav 35 från
den senaste leveransen och de tidigare 141. Se [sammanställningen](summary.json)
och [variantkön](queue.json); äldre rapporter behåller sina historiska scope.

## Import och åtgärdade hinder

| Steg | Varianter | Genomförd granskning |
|---|---:|---|
| 1 | 14 | Enkel söt pumpafilo, tre ängamat, tre fiskpuddingar, enkel bouyiourdi, tre äggfria scammaro-pastakakor och tre jota-surkålssoppor. Portionsantal, processvatten, aktiv tid och faktiskt valda produktformer är kontrollerade. |
| 2 | 3 | Pallotte får uttryckligen lagrad pecorino i stället för obelagd Romano-identitet. 140 g avser köpt ost före eventuell kantputsning; kantförlusten förblir okänd. Allt stekfett följer med i såsen. |
| 3 | 3 | Utökad pumpafilo får 5 g kanderat apelsinskal i stället för 1 g färskt skal. Två coyotas får 18 g mörkt muscovadosocker per portion i stället för piloncillo. Namn, råvaror, mängder och metoder ändras tillsammans. |

Pecorinoalternativet stöds av [GialloZafferanos egna pallotte](https://www.giallozafferano.com/recipes/Pallotte-Cacio-e-Ova-Cheese-and-Egg-Balls.html).
Sötat apelsinskal förekommer i [Angela Nicolettous pumpapaj](https://www.sbs.com.au/language/greek/en/podcast-episode/sweet-pumpkin-pie-with-ricotta/g5xzo5yrq).
Brunt socker och smör som coyotasalternativ stöds av
[Maricruz Avalos eget recept](https://www.maricruzavalos.com/coyotas/).
Källorna stödjer alternativen; våra doser och övriga instruktioner är egna
granskade författarbedömningar, inte omräkningsfaktorer eller smaklikhetsbevis.
Pumpapajens ursprungliga 10 g socker behålls; det kanderade skalet tillför
ytterligare sötma. Inga nya identitetsalias, produktfakta eller densiteter införs.

Fiskpuddingen planerar kylupptining, kylning före äggblandning och aktiv
temperaturkontroll. Bortkastat fisk-/ärtspad redovisas som okänd processförlust.
Frysta örter genomhettas. Scammaro får samma saltdos i den serverade pastan
och osaltat kokvatten; stärkelseförlusten vid avrinning förblir okänd.
Jotas lagerblad plockas bort med okänd överföring. Dessa V3-versioner kan
köpas men godkänns inte för hårda gränser för näring eller serverad vikt.

Faktiska korgval omfattar bland annat sejfilé, fryst blomkål och hackade örter,
färsk filodeg, lagrad Pecorino 8mån, avrunna sardeller och surkål. Granskningen
använder de redan godkända produktkopplingarna. Referensen är fryst Malmödata
från 2026-10-23: högst två butiker, fyra middagsportioner eller en mellanmålsportion,
tomt skafferi och inga extra kost-, allergi-, eko- eller näringsgränser.

Alla varianter har version 1.0.1. Tre separata `recipe-review-stageN.json`,
`import-stageN.json` och `qualification-stageN.json` binder originalfil,
ändringar, innehållshash och slutlig korg. Samtliga 3 955 tidigare utgivna
versioner, 2 822 tidigare aktiva varianter och 2 200 ursprungsreferenser bevaras.
[Manifestövergången](library-transition.json) är additiv och kontrollerad;
ingen jämförelsebaslinje regenereras.

## Återstående hinder och nästa agent

De största återstående grupperna kontrollerades först i befintliga butikers
frysta underlag. Räkpasta, curryblad och masa harina gav inga verifierade
rena produkter. Breda namnträffar som kycklingpastej är inte räkpasta.
Tamarind finns som Chua Hah Seng-koncentrat i ml, redan separat granskat;
det löser inte gramdoser, andra saknade råvaror eller receptberedningen automatiskt.
[Produktsökningens kvitto](product-search.json) dokumenterar scope och träffar.
Noll träffar i denna referens är inte bevis för frånvaro i handeln.

[Kontrollen av väntande utkast](pending-known-inputs.json) håller kvar både
okända registeridentiteter och produktblockeringar bakom dessa. Börja nästa
omgång med `ranked_combined_blocks`. Av 176 väntande varianter har 81 ett
konkret produktstopp bland redan kända ingredienser. De övriga 95 är fortfarande
inte innehålls- eller korggodkända. Särskilda nya hinder är bland annat
lammlever, fänkålsgrönt, kasseri, apelsinblomsvatten, nopales, fermenterad
bambu/tofu, kolostrumprodukt och rätt urvattnad saltsill. Mysore paks mycket
lilla heta sockersats behöver praktisk metod-/utrustningsgranskning även om
ingredienserna går att köpa. Detta kringgås inte med ett produktgodkännande.

Det tidigare upptäckta mängdbasisproblemet i sex äldre dadelvarianter kvarstår;
se föregående omgångs rapport. Det har inte rättats genom denna additiva import.

Återskapa kön med `finalize_expansion_round3_review.py` och kontrollera därefter
väntande ingredienser med `screen_pending_recipe_inputs.py --queue
docs/reviews/recipe-unblock-round3-20261102/queue.json`, samma universum/fakta
och klockan `2026-10-23T06:00:02.869273+00:00`. Skriptet godkänner inga recept.
Nya ZIP ska fortsätta räknas utifrån verkliga originalfiler.

## Verifiering

Riktade tester kontrollerar originalbytes, varje import- och korgkvitto,
portionsskalning 1/4/12, temperaturer, mängdbasis, processförlusternas steg
efter upptining och hela kedjan av manifestövergångar. Efter rättning av två
fel i de nya testernas modellåtkomst passerar samtliga **108 unika riktade
tester** (99 befintliga och nio nya). Ruff, compileall och diffkontroll passerar.
Alla 20 utgivna versioner återskapas byteidentiskt av granskningsskriptet.
Full CI krävs före merge; körningslänk och resultat redovisas i PR.
