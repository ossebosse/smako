# Åtta nya recept i alla fyra klasser – innehållsprovet passerar

**Två enkla middagar, två genomarbetade middagar, två frukostar och två
mellanmål har lagts till utan ändrad programkod.** Det aktuella biblioteket
växer från 182 till 190 receptposter. Befintliga versioner och återkallelser
bevaras. Ingen aktivering eller annan produktionsåtgärd har utförts.

| Klass | Nya recept |
| --- | --- |
| Enkel middag | Ärtpasta med keso och citron; Tomat- och couscoussoppa med kikärtor |
| Genomarbetad middag | Linsfyllda kåldolmar med tomatsås och gurkyoghurt; Tofu- och couscousfyllda tomater med rostad morot och citronkräm |
| Frukost | Ugnsbakad havre med äpple och keso; Varm morotsgröt med yoghurt |
| Mellanmål | Ugnsvarm tomat med ost och oregano; Ärtdipp med yoghurt och morotsstavar |

[Fullständiga mängder, instruktioner och provkorg](RECIPES.md).
[Importpaket](../../../backend/app/data/recipes/all-meal-classes-20261008.json).

Grundrätterna skiljer sig i huvudråvara, sammansättning och/eller beredning från
tidigare innehåll; detta är inte omdöpta portioner. Exempelvis skiljer varm
morotsgröt och ugnsbakad havre sig från tidigare kall yoghurtgröt, och kåldolmar
från tidigare kålgryta. Innehållet är författat och granskat mot mängdbasis och
stegreferenser, **inte fysiskt provlagat**. Tiderna är uppskattningar.

## Verifierad innehållsväg

Basimage `sha256:8a537fc4d333d9fc17fd06916061ed481ba433951126688df51b6b4da19766f3`,
runtime `54cb2e8159a126de26fa11cb1d393dc275238fd3`.
Ny isolerad innehållsimage:
`sha256:9784eb872990039ffb547203c7f4b45f424fa5c58c0c275bcfe564be189d8fc6`.

Den befintliga CLI:n körde **validera → diff → import → omimport → förbered →
kvalificera → bygg bibliotekskandidat**. Åtta nya identiteter, noll avvisningar.
Omimport: åtta oförändrade identiteter och identiskt manifest. Samma import
kördes med den oförändrade importören inne i 54cb-imagen. Alla **610 programfiler**
är byteidentiska mellan bas- och innehållsimage; alla **20 tidigare receptfiler**
är oförändrade. I appträdet tillkom endast ett hashbundet receptpaket och ändrat
innehållsmanifest. Inga nya specialregister, produktfakta eller metoder.
Repositoryts 1 589 låsta filer utanför innehåll och dokumentation är oförändrade,
inklusive befintliga testhjälpare. Den nya privata provorkestreringen är testkod.

Förberedelse i Windows: 40,226 s första gången, 3,942 s i nästa process.
Andra körningen: 973 träffar, 0 missar, 0 skrivningar. Förberedelsen omfattar
även bevarade historiska versioner och portionsskalningar; dess 496 registrerade
versioner får inte räknas som 496 aktuella distinkta maträtter. Detta är ett
återanvändningsprov, ingen ny 1×/2×/5×-prestandamatris.

## Faktisk kvalificering och appflöden

- **8/8** individuella recept passerade ordinarie PersonalPlanner, produktval,
  mängder, näringsberäkning och oberoende korgaudit. Både lokalt och i imagen;
  bildens sammanlagda kvalificering tog 82,093 s.
- Villkor: tomt skafferi, max tre butiker, uppskattat köp tillåtet och separat
  näringsmedgivande. Inget proteinminimum och inget allergenkrav i individprovet.
  Näringsstatus är `ESTIMATED`, allergenstatus `NOT_REQUESTED`.
  Ett PASS betyder alltså **inte** automatiskt 30/40 g protein eller allergenfrihet.
  Protein per portion i provet varierar från 9,32 till 31,85 g.
- **17 befintliga bibliotekstester** passerade, bland annat importkonflikter,
  återkallelser och förberedelsekontroller.
- Alla åtta nya recept i en uttryckligt vald plan: **Chromium och WebKit PASS**,
  mobil layout, åtta tillfällen/tolv portioner, audit PASS, recept och inköpslista
  renderade, samma idempotenta jobb, sparad GET och annan ägare nekad.
  WebKit återläste samma plan efter faktisk omstart av den isolerade appen.
  Samtliga nio framgångsrika provrevisioners kompletta request-/planinnehåll
  jämfördes dessutom efter omstart och var identiskt.

Fria knappflöden använde hela biblioteket, inte en låst lista med nya recept:

| Fri plan | Webbläsare/vy | Tillfällen/portioner | Klick till resultat | Utfall |
| --- | --- | --- | --- | --- |
| Enkla middagar | Chromium/publik | 5/10 | 40,328 s | PASS |
| Genomarbetade, minst 3 kök, proteintak 2 och minst 30 g protein | WebKit/personlig | 5/20 | 111,281 s | PASS |
| Frukostar, upprepning tillåten | Chromium/publik | 5/5 | 31,563 s | PASS |
| Mellanmål, separat upprepningsgräns | WebKit/personlig | 5/5 | 28,687 s | PASS |
| Kombinerad vecka | Chromium/personlig | 15/30 | 74,953 s | PASS |

Alla fem omfattar dubbelklick, omladdning under jobb, sparning, identisk GET och
ägarskydd. Kombinationsprovet omfattar också receptbyte, uttrycklig omräkning
och revisionerna 1/2/3. Ingen oväntad pageerror eller nätavvikelse observerades.
Mobil emulering är inte fysisk iPhone-testning. Två CPU, 3 GiB, en tung planerare.
Tiderna är enstaka funktionsprov, inte jämförbara före/efter-medianer eller bevis
för under 60 sekunder i alla profiler. Ingen sådan förbättring påstås.
Den befintliga mätningen registrerade tio beräkningsförsök för tio jobb,
inklusive det korrekt avvisade provet: högst en beräkning per jobb.
Processens observerade högsta RSS var 1 645 508 KiB; det är inte ett separat
minnesmått per begäran. Ingen extra tung planerare eller större resursgräns.

Fri sökning valde den nya couscoussoppan i den enkla middagsveckan, morotsgröten
i frukostveckan och ärtpastan i kombinationsveckan. Alla nya recept behöver inte
bli billigast i ett fritt val. De två nya genomarbetade middagarna når inte
30 g i individprovet och räknas inte som räddade 30-g-recept.

### Gemensam förpackning över måltidstyper

I den uttryckligt valda åttareceptsplanen används samma kvalificerade yoghurt
till middagar, frukostar och mellanmål. Totalt 620 g samordnas till **en
1 000-gramsförpackning**, 380 g planerad rest, 15,55 kr. Hela korgen: 468,87 kr
över tre butiker, audit PASS i båda webbläsarna. Ingen hypotetisk framtida
restnytta dras av. Ingen besparing gentemot separat planering har mätts.

Alla belopp avser **berikad historisk replay**, köpdatum 4 oktober, bevarade
priser/fakta och artefakt `f82d6610…`. Det är inga aktuella prisofferter och
inga nya källhämtningar har gjorts. Detaljer: [EVIDENCE.json](EVIDENCE.json).

## Bevarade misslyckade försök

Första genomarbetade webbprovet skickade `dinner_level=simple`: den äldre
provbegäran saknade det uttryckliga fältet och testverktygets formulärval blev
enkelt. Appen avvisade korrekt de motstridiga kraven med
`RECIPE_CHOICES_CONFLICT`. Den felaktiga provkörningen är fortfarande FAIL.
Nytt prov satte uttryckligen `crafted` och passerade; ingen appkod eller
skyddsregel ändrades. Rapporthash och rålogg bevaras.

Docker Desktop behövde startas om efter ett lokalt `dockerInference`-startfel.
Första innehållsbygget angav image-ID i FROM, vilket BuildKit försökte slå upp
som ett registry-namn. Nytt bygge använde den befintliga taggen efter kontroll
av dess exakta image-ID. Båda byggloggarna är bevarade. Ingen fabriksåterställning.

## Leverans och nästa användning

Gren: `content/all-meal-classes-20261008`, lokalt committad. Innehållspaket och
manifest ligger i Git; privata råresultat ligger på D: i
`.local/all-meal-classes-20261008/`. [PACKAGE.json](PACKAGE.json) binder det
körda innehållet och det återläsningskontrollerade biblioteksarkivet.

Se [REPRODUCE.md](REPRODUCE.md) för körvägen. Den isolerade appen är stoppad efter
proven; image, lokal planvolym och underlag bevaras. Dockerdata finns på
`D:\docker\DockerDesktopWSL\disk\docker_data.vhdx`.

**Det går att lägga till detta receptpaket utan ny programkod.** Författande,
semantisk granskning och kvalificering behövs fortfarande. Inga nya
skalbarhetsgarantier eller globala optimalitetsbevis görs.
Beta är oförändrad. Innehållsimagen är ett prov ovanpå 54cb och innehåller inte
betans senare selektiva incidentfix; den ska inte användas som en genväg till
produktionsaktivering. En framtida sammanhängande apprelease måste bevara den
fixen och gå genom sitt separata aktiveringsbeslut.
