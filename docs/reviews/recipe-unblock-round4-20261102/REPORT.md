# Fler recepthinder, 2026-11-02

Denna omgång utgår från main `26d7d3de5212642ab3c38d06bfcbdb988ecd6b39`
och tredje omgångens 176 väntande varianter. Ingen ny ZIP tillkommer.
Originalutkast och tidigare utgivna versioner bevaras. De nya recepten är
innehållsgranskade, men inte provlagade.

## Granskade hinder och recept

| Hinder | Åtgärd | Varianter |
| --- | --- | ---: |
| Lammlever saknar stöd för utkastets insats | Magiritsa med uttryckligt namngiven ungnötslever, inköpsvikt före putsning och okänd förlust i bortkastat spad | 3 |
| Apelsinblomsvatten saknar registerkoppling; kanderat citronskal saknar stöd | Separat granskad Yamama-produkt i ml; utökad pastiera anger kanderat apelsinskal | 2 |
| Stracchino saknas; rucola saknar registerkoppling | Recco-inspirerat ostbröd med ricotta, färskost och avrunnen mozzarella; separat granskad rucola | 3 |
| Kasseri saknas | Bouyiourdi med uttryckligt namngiven gruyère och okänd eventuell kantförlust | 1 |

Detta är nio varianter i fyra familjer, varav tre nya grundrätter.
Bouyiourdi utökar en befintlig familj. Det finns inga alias som gör
ungnötslever till lammlever eller andra ostar till stracchino/kasseri.
Förändrade mängder är egna receptdoser, inte antagna utbytesfaktorer.

Kulinariskt stöd för anpassningarna finns hos receptförfattarna:
[Carolina Doritis magiritsa](https://cookout.skai.gr/articles/magiritsa-the-traditional-greek-easter-soup),
[ICA:s treostversion](https://www.ica.se/recept/focaccia-di-recco-729881/),
[GialloZafferanos pastiera](https://www.giallozafferano.com/recipes/pastiera-napoletana-Neapolitan-ricotta-cheese-Easter-pie.html)
och [bouyiourdi med gruyère](https://bwydbydbywyd.blogspot.com/2017/03/bouyiourdi.html).
De nya instruktionerna och doserna är granskade Smako-anpassningar.

## Produkt- och beredningskontroll

Två ingrediens/form/enhetsidentiteter får sammanlagt **15 exakta
produktkopplingar** i befintligt fryst butiksunderlag:

- Apelsinblomsvatten, `as_sold`, ml: sju poster för Yamama 300 ml,
  artikel `101553588_ST`. [Tillverkaren](https://www.yamama-lb.com/rose-blossom-water/)
  skiljer blossom water från rose water. Ingen densitet eller aromstyrka antas.
- Rucola, `raw_edible`, g: åtta poster för Ruccola Klass 1 125 g,
  artikel `101316310_ST`. [125 g-produktens uppgifter](https://www.garantskafferiet.se/vara-produkter/eko-frukt--gronsaker/sallad/ruccola---garant/)
  stöder rena rucolablad. Hela ätliga blad och stjälkar används.
  Den separata 65 g-sidan har motstridig text om småbladsmix och används inte.

Kopplingarna binder butik, produkt, artikel, källa, snapshot, sammansättning,
förpackning, form och enhet. Näring, allergier och ekologisk andel får ingen
ny attest. Byte av källa, innehåll, mängd eller identitet måste omprövas.
Se [produktsökningen](product-search.json) och
[registerunderlaget](../../../backend/app/data/ingredients/expansion-round4-20261102.json).
Sökresultatens antal är varken popularitet eller godkänd köpbarhet.

Leverns putsning och förvällningsspad, matvetets kokvatten och eventuell
ostkant redovisas som okända processförluster enligt V3. Serverad näring och
vikt förblir okända; hårda sådana gränser ska ge `DATA_BLOCKED`.
Ägg vägs utan skal. Frysta örter hettas upp; basilikan i utökat ostbröd
läggs i den gräddade fyllningen. Mozzarella anges som avrunnen insats,
ricotta och färskost används hela. Aktiva temperaturkontroller, formyta,
degtjocklek, processvatten och portionsfördelning granskas uttryckligen.

## Paketgränsen

Efter första delimporten nåddes den tidigare gränsen på 128 paketgenerationer.
Importen av nästa paket stoppades före skrivning. `MAX_PACKS` är nu 1 024,
samma ändliga storlek som cachen för validerade oföränderliga paket.
Det skapar inga paket i förväg och ändrar inte kontrollsummor, storleksgränsen
16 MiB per paket, receptvalidering eller konfliktskydd.
Regressionsprov täcker import nummer 129 med bevarad historik, idempotent
import vid den nya gränsen samt avvisning över gränsen före skrivning.

## Resultat och spårbarhet

Biblioteket är nu **1 083 grundrätter / 2 851 aktiva varianter**.
Av de 556 mottagna varianterna är **389 importerade och 167 väntande**,
fördelade på 146 hela och tre delvis importerade familjer. Senaste 21/55-ZIP
har nu 26 importerade och 29 väntande varianter. Alla sex leveransers
separata antal och korgutfall finns i [summary.json](summary.json).
Varje delpaket har `recipe-review-stageN.json`, `import-stageN.json` och
`qualification-stageN.json`, bundna till samma innehållshash. Alla nio
nya varianter har godkänd full korg i uppskattat läge; sex även i exakt läge.
De tre magiritsa-varianterna är `DATA_BLOCKED` i exakt läge eftersom
leverförpackningen och vissa grönsaksvikter är uppskattade. Inga timeoutfall.
Valda korgprodukter har också granskats mot tillagningen: fryst dill,
persilja och basilika hettas upp och mozzarella köps med granskad avrunnen vikt.

Referensen är oförändrad: 89 458 produkter, 52 butikskontexter, högst två
butiker, tomt skafferi, fyra middagsportioner eller en mellanmålsportion,
klocka `2026-10-23T06:00:02.869273+00:00`, utan hårda näringsgränser.
Varje full korg har 20 sekunders beräkningsgräns efter delad förberedelse.
Detta är ett avgränsat fryst prov, inte aktuella betapriser eller ett varmt menyprov.

[Manifestövergången](library-transition.json) bevarar alla 3 975 tidigare
utgivna versioner och 2 842 tidigare aktiva varianter. De 2 200 ursprungliga
referens-ID:na och CI-baslinjerna ändras inte. Den nya granskade övergången
läggs till i den befintliga verifieringen av additiva importer.

[Kön](queue.json) bevarar de 380 tidigare godkända variantbesluten.
[Den nya ingredienskontrollen](pending-known-inputs.json) omfattar varje
kvarvarande utkast och binder sig till köns hash. Den prövar kända insatser;
den utgör inte receptgodkännande eller full korgkontroll.
Av 167 väntande utkast har 81 även blockerade kända insatser; 86 har lösta
kända insatser men kvarvarande okända identiteter eller innehållsgranskning.

Lokal verifiering: **893 unika godkända offlinetester**, noll fel eller
skippar, samt godkända Ruff-, compileall- och diffkontroller. Återbyggnad
av samtliga tre författarpaket, native-paket och granskningar är byteidentisk.
Full CI med oförändrad täckningsbaslinje ska vara grön före main-merge.

## Nästa hinder

Börja nästa omgång i `ranked_combined_blocks` i den nya ingredienskontrollen.
Räkpasta, curryblad, masa och andra stora grupper behöver fortfarande
verifierat produkt-/formstöd. I den här omgångens bredare sökning hittades
ingen tapioka, skrädmjöl, stracchino, kasseri eller amarena i den frysta
referensen. Panerade bläckfiskringar, vattenkastanjer och rabarbersmaksatta
sammansatta produkter löser inte respektive rena råvaruinsats.
Kokossocker har kandidater, men är inte registrerat i denna omgång;
samtidiga hinder måste granskas innan ett helt recept kan släppas in.
Krukvikter för thaibasilika får inte användas som ätbara örtgram.

Nästa författarpaket är fortfarande 025 och beställningen återstår med
790 grundrätter / 2 194 varianter. De sex äldre dadelvarianternas dokumenterade
mängdproblem är oförändrat. Ingen betaaktivering ingår i denna omgång.

## Återskapa kontrollen

Kör från projektroten med `PYTHONPATH=backend;.` på Windows:

```powershell
.venv/Scripts/python.exe -X utf8 scripts/recipe_layer/finalize_expansion_round4_review.py
.venv/Scripts/python.exe -X utf8 scripts/recipe_layer/screen_pending_recipe_inputs.py --queue docs/reviews/recipe-unblock-round4-20261102/queue.json --universe .local/coverage-inputs/universe.json --facts .local/coverage-inputs/facts.json --clock 2026-10-23T06:00:02.869273+00:00 --output docs/reviews/recipe-unblock-round4-20261102/pending-known-inputs.json
```

Byggaren `admit_expansion_round4_20261102.py` vägrar skriva över ett utgivet
delpaket. För bytejämförelse byggs till en separat tillfällig katalog.
