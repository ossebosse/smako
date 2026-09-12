# Smako – kostnadsanalys och uttryckligt ingen fisk, 12 september 2026

Den tidigare femmiddagsmilstolpen **förblir PASS**. Inga prisfel eller försvunna inköp har belagts. Samma meny kostar **677,43 → 677,43 kr**. Billigasts andra meny kostar **563,96 kr**. ”Ingen fisk” är **DATA_BLOCKED** med konkret ingrediens- och beredningsbrist. En bekräftad fiskklassningsbugg är rättad och driftsatt som `personal-v2-cost-fish-20260912`, appkod `e5a3787`.

## Fryst jämförelse

AGENTS.md, HANDOFF och [senaste fullrapporten](smako-five-dinners-20260912.md) lästes. Faktisk release före ändring verifierades via `/health`, current-symlink och Docker-image: `personal-v2-five-dinners-20260912c`, image `sha256:3b427220f5a6e589c43f840191bfb54086dcc4019be65c341595b7290b4e3193`. Arbetskopian utgår från dokumentationscommit `3e53363` med appkod `e626ac0`. De tre ändrade appfilernas bashashar kontrollerades mot serverkällan före staging.

Input hämtades direkt ur det sparade B5-fallet i `five-dinners-20260912/verified-frozen.json`, inklusive null/defaultfält. Fem middagar × fyra portioner, Balanserad, max två inköpsställen, uppskattningar uttryckligen på, protein minst 20 g och energi högst 800 kcal per portion. Tomt skafferi, inga extra inköp eller låsta produkter, inga medlemskap, inga likes/dislikes/allergier/uteslutningar, `surplus_mode=minimize`. Övriga sparade krav är oförändrade.

- Prisversion: `price-universe:9ab6c58a4934c0a253e037c724d58fdcc8c84b484d26a87d2027be087e17b929`; testtid `2026-09-11 07:15:56.668911+00:00`.
- Produktfaktaversion: `retained-catalog-facts-v2:a4283c8ba8ae5590d365808377efa00e2c6b2e2ae48d52f46d78fbddac756622`.
- Näringsreferens: `slv-component-input-v2:7d6f1acbb10e93269d534adedf5bde2e0a824811f5ed5b7e85c75644346d9a12`.
- Ursprunglig policy `personal-policy-v2-4`; A/B före ändring kördes med denna version. Efter fiskrättningen är cachepolicyn `personal-policy-v2-5`; samma A/B-resultat och övriga krav är regressionstestade. Variationspolicyn `structural-menu-v2` och alla dess gränser är oförändrade.
- [Fördeklarerade input](affordable-five-20260912/predeclared-inputs.json), [före ändring](affordable-five-20260912/baseline.json), [slutlig fryst acceptans](affordable-five-20260912/final.json). Fälthashar för prisfixture, produktfakta och båda näringsfilerna finns i acceptansfilerna.

**Alla jämförelsepriser är historiskt testunderlag, inte dagens prisutfästelser.** Ingen jämförelse med gamla menyer under andra krav används. Referensdata, paketmängder och konsumentens profil har inte ändrats för att få ett lägre resultat.

## Hela köpet 677,43 kr

M1–M5 nedan är originalmenyn i sparad ordning. Delning avser gemensam inköpsmängd över recepten; inga fysiska förpackningsindivider spåras. Köpt/ätbar insats/rest redovisas i gram.

- M1: Stekt torsk med äggnudlar och vitkål.
- M2: Torsk- och kålsoppa med äggnudlar.
- M3: Kokt kyckling med ris och morötter.
- M4: Couscoussallad med tofu och tomat.
- M5: Stekt lax med ris och morötter.

| Produkt | Inköpsställe | Hela förpackningar | Prisregel | Radsumma kr | Köpt g | Använt g | Planerat överskott g | Delas av |
|---|---|---:|---|---:|---:|---:|---:|---|
| Torskfilébitar i block | Coop Online Syd | 3 × 400 g | Ordinarie 64,31 kr/st | 192,93 | 1200 | 1200 | 0 | M1, M2 |
| Couscous Eko | Willys Lund | 1 × 500 g | Ordinarie 18,83 kr/st | 18,83 | 500 | 320 | 180 | M4 |
| Kycklingfilé 2-delad Frysta | Willys Lund | 1 × 800 g | Ordinarie 75,61 kr/st | 75,61 | 800 | 600 | 200 | M3 |
| Laxfilé i Bit Refreshed | Willys Lund | 2 × 400 g | Ordinarie 94,54 kr/st | 189,08 | 800 | 600 | 200 | M5 |
| Morötter Klass 1 | Willys Lund | 2 × 1000 g | Ordinarie 9,90 kr/st | 19,80 | 2000 | 1200 | 800 | M3, M5 |
| Äggnudlar | Willys Lund | 3 × 250 g | Ordinarie 9,36 kr/st | 28,08 | 750 | 640 | 110 | M1, M2 |
| Långkornigt Ris | Willys Lund | 1 × 1000 g | Ordinarie 19,90 kr/st | 19,90 | 1000 | 640 | 360 | M3, M5 |
| Naturell Tofu Fast Vegansk | Willys Lund | 3 × 200 g | Ordinarie 11,90 kr/st | 35,70 | 600 | 600 | 0 | M4 |
| Tomat Kumato Klass 1 | Willys Lund | 2 × 300 g | Ordinarie 27,90 kr/st | 55,80 | 600 | 600 | 0 | M4 |
| Vitkål Strimlad Klass 1 | Willys Lund | 3 × 400 g | Ordinarie 13,90 kr/st | 41,70 | 1200 | 1200 | 0 | M1, M2 |
| **Summa** | **Coop 192,93 + Willys 484,50** | **21 förpackningar** | **Inga medlemsvillkor/flerköp i denna korg** | **677,43** | | | | |

Fullständig produktidentitet, GTIN, förpackningsform, prisavtal, källsnapshot, köpbar mängd och receptens delade behov finns i `cases.same_menu.plan.optimized_basket` och `personal.needs` i [slutlig acceptans](affordable-five-20260912/final.json). Samtliga rader använder `regular`, `eligibility=public`, heltalspaket och inga kampanjgrupper.

Kostnadsdrivare: torsk **192,93 kr**, lax **189,08 kr**, kyckling **75,61 kr**, tomat **55,80 kr**. Fiskarna tillsammans är **382,01 kr (56,39 %)** av hela köpet. Laxens två 400-g-paket behövs för 600 g; dess 200 g rest motsvarar 47,27 kr proportionellt men dras inte från inköpet.

En separat analytisk fördelning är **585,28 kr för använd mängd** och **92,15 kr för rest**. Metod: varje rads fulla kostnad × använd ätbar mängd / köpt användbar mängd. Full precision summeras före avrundning (585,2763 + 92,1537 = 677,43). Denna förbrukningskostnad är ingen kassarabatt, ingen bokförd lagervärdering och ingen ändrad optimeringsfunktion. Inget skafferi används i originalet.

De tio valda produkterna har inga pantposter. Befintlig Basket-modell summerar produktrader; den har ingen separat modell för leverans-, plock- eller reseavgift. Sådana avgifter är därför **inte verifierade eller inkluderade** i 677,43 kr, och påstås inte vara noll. Ingen avgift har tagits bort i jämförelsen. Coop Online Syd är `ONLINE_FULFILLMENT/online_price`, inte ett fysiskt hyllpris; Willys Lund är `online_store`.

## A: samma recept och ingrediensmängder

Sparade fem recept låstes som explicita slots. Befintlig produktkvalificering, heltalspaket och BasketOptimizer prövade samtliga 6 enbutiks- och 15 tvåbutikskombinationer. **677,43 kr före och efter**. Alternativ: Coop + Willys Nova 678,27 kr, Coop + Hemköp 750,85 kr, Willys Lund ensamt 766,20 kr, Willys Nova ensamt 770,10 kr och Hemköp ensamt 879,14 kr. Coop ensamt saknar kvalificerad tofu. ICA-kontexterna ger inga kompletta kvalificerade alternativ för dessa behov i det frysta underlaget.

Billigaste isolerade kvalificerade tofu finns hos Hemköp: 35,20 kr mot Willys 35,70 kr. Den kräver ett tredje inköpsställe i originalkorgen, eller en dyrare tvåbutikskombination. Obegränsad summering av radminimum är 676,93 kr, men är inte en tillåten tvåbutikskorg. Detta är en verklig butikstakseffekt, inte för tidig gallring.

Produktkedjan utgår vid närings-/profilkrav från både ekonomipool, den bredare matchade poolen, det frysta kanoniska indexet och befintlig textsökning. Den kontrollerar hårda produktval före receptspecifikt näringsunderlag; sedan prissätts samtliga kvarvarande paket. Det finns ingen billig-poolgräns mellan dessa steg i `PersonalPlanner.resolve`. Samma-menyns billigaste kvalificerade korg klarar näringen direkt, så den begränsade alternativa näringssökningen behöver inte reparera den.

| Behov | Semantiskt lösta produkt-/butiksrader | Både närings- och prisgodkända |
|---|---:|---:|
| fisk | 21 | 10 |
| nudlar | 66 | 6 |
| vitkål | 11 | 3 |
| kyckling | 52 | 11 |
| ris | 137 | 29 |
| morot | 21 | 16 |
| tofu | 20 | 8 |
| couscous | 16 | 10 |
| tomat | 123 | 24 |
| lax | 20 | 9 |

[Alla produktrader, kvalificering, prisregler och butikskombinationer](affordable-five-20260912/candidate-audit.json). Saknat pris betyder att den strikta paketkontrollen inte accepterade en offert, inte noll kronor.

### Var billigare alternativ faller bort

| Alternativ för samma behov | Verklig offert kr | Avgörande steg och tolkning |
|---|---:|---|
| Coop Sejfilé i Block, 1 200 g behov | 138,99 | Annan fiskart; torskkopplingen SLV 1246/1337 får inte överföras. Sejrecept och granskad sejberedning saknas. Otillräcklig mappning, inte bevis för olämplig mat. |
| Willys Kycklingklubba Import, 600 g behov | 32,08 | Fel styckningsdel jämfört med rå skinnfri bröstfilé och annan ben-/ätbar mängd. Verklig oförenlighet med exakt meny/form. |
| Willys Lax Grytbitar, 600 g behov | 170,04 | Namn/underlag kvalificerar inte skinnfri odlad filé för den granskade kedjan; inte bevis att grytbitar i sig är oanvändbara. Datakvalificering saknas. |
| Willys Pinklaxfilé Solrosolja, 600 g behov | 117,80 | Annan art och oljekonserv; strider mot rå laxfilé och dess beredningskedja. |
| Willys passerad/skalad tomat, 600 g behov | 15,80 | Konserv kan inte ersätta rå färsk tomat i den granskade salladen. Verkligt formavslag. |
| Coop strimlad vitkål, 1 200 g behov | 48,12 | Konflikt i näringsbas (`nutrition_basis`); generisk mappning får inte skriva över konflikten. Dessutom dyrare än 41,70 kr. |
| Lös/variabel vitkål i sju butiksrader | Ej kvalificerad offert | Näringsreferens kan finnas, men paketmängden är `estimated/variable_weight_package`. Näringsopt-in tillåter inte uppskattade inköpsmängder. |
| Hemköp naturell fast tofu, 600 g behov | 35,20 | Kvalificerad och prövad; radvinsten 0,50 kr förloras med gemensamt butikstak. |
| Willys vanlig Couscous, 320 g behov | 28,29 | Kvalificerad och prövad, men dyrare hela paket än Couscous Eko 18,83 kr. Ingen prioritet för eko uppfanns. |
| Coop Cocktailtomater, 600 g behov | 56,64 | Kvalificerad och prövad, men dyrare än Kumato 55,80 kr. |

Vatten i deklarationen för vissa Coop-äggnudlar stoppar den snäva torrvarumappningen; den är inte belagd som en förlust av ett billigare kvalificerat alternativ i detta fall (lägsta berörda offert 28,26 kr mot vald 28,08 kr). Kvalificerad komplett produktnäring kontrolleras före menygrenar gallras. Vid verkliga näringskonflikter finns en befintlig begränsad sökning om högst 256 produktkombinationer; den är inte en generell optimalitetsgaranti. Ingen kostnadsrättelse eller utvidgning görs utan belagt fel.

## B: fria receptval under samma näringsprofil

Rå pool: 80 vanliga genererade recept + 10 granskade referensrecept. Alla 80 vanliga faller först på saknad beredningsgrund; de tio referensrecepten klarar individuellt både näring och köp. Relevanta vanliga kandidater omfattar äggrätter, kyckling, falukorv, tofu, kikärtor och kidneybönor; de är **skapade men datastoppade**, inte utkonkurrerade av dyr fisk. Sejkopplade granskade recept och fler kompletta fiskfria referensrätter **skapades aldrig** i befintlig referensgenerator.

Menysökningen använder beam 8. Originalets sökdjup behåller 8 grenar; 2/53/36/14/0 prissatta grenar gallras vid djup 1–5. Detta är **sökgallring**, inte ett hårt kravavslag. En separat uttömmande kontroll av alla 252 oordnade femkombinationer bland de tio individuellt kvalificerade recepten prövade befintliga variationsregler och därefter samma korgmotor. Balanserad: 245 variationavslag, 7 prissatta; två delade minimum på 677,43 kr, övriga 688,73–725,56 kr. Billigast: 252 prissatta, minimum 563,96 kr. Båda vanliga sökresultaten når dessa minimum. Slutsatsen gäller denna avgränsade kvalificerade pool och motor, inte alla tänkbara menyer eller produkter.

Balanserad behåller max två av samma proteinkärna, kolhydrat, familj, metod och serveringsform samt parvis kulinarisk likhet <0,85. Billigasts befintliga policy har inte dessa repetitionstak, men behåller fem skilda recept. Billigasts resultat följer alltså sin egen oförändrade policy.

### Balanserad och samma-menykontroll

| Middag | Protein g/portion | kcal/portion | Grund |
|---|---:|---:|---|
| Stekt torsk med äggnudlar och vitkål | 39,94 | 471,87 | ESTIMATED |
| Torsk- och kålsoppa med äggnudlar | 39,99 | 472,22 | ESTIMATED |
| Kokt kyckling med ris och morötter | 41,97 | 492,79 | ESTIMATED |
| Couscoussallad med tofu och tomat | 21,34 | 420,80 | ESTIMATED |
| Stekt lax med ris och morötter | 37,54 | 613,78 | ESTIMATED |

Full inköpskostnad **677,43 kr**. Inköpsställen: Coop Online Syd, Willys Lund.

### Billigast

| Middag | Protein g/portion | kcal/portion | Grund |
|---|---:|---:|---|
| Couscoussallad med tofu och tomat | 21,34 | 420,80 | ESTIMATED |
| Kokt kyckling med ris och morötter | 41,97 | 492,79 | ESTIMATED |
| Kycklingsoppa med äggnudlar och vitkål | 47,63 | 506,77 | ESTIMATED |
| Torskgryta med ris och morot | 34,33 | 458,24 | ESTIMATED |
| Stekt torsk med äggnudlar och vitkål | 39,94 | 471,87 | ESTIMATED |

Full inköpskostnad **563,96 kr**. Inköpsställen: Coop Online Syd, Willys Lund.

Skillnaden **113,47 kr** motsvarar att två laxpaket för 189,08 kr försvinner och ett extra kycklingpaket för 75,61 kr tillkommer. De andra ingrediensbehoven ger samma radkostnader. Det är en annan meny: kycklingsoppa/torskgryta ersätter torsk- och kålsoppa/stekt lax. Ingen portionsmängd ändras för att pressa pris.

## Ingen fisk: konkret DATA_BLOCKED

Före körningen kopierades exakt B5-input och endast `personal.profile.exclusions=["fisk"]` ändrades. Allergilistan är tom. Detta är matpreferens, inte fiskallergisäkerhet.

1. Befintliga kvarvarande referensrecept är kokt kyckling/ris/morot, kycklingsoppa/äggnudlar/vitkål och couscoussallad/tofu/tomat. Samtliga stoppas av befintligt krav på komplett ingrediensunderlag för hårda uteslutningar. **0 av 34 790 faktaposter** i fryst `FactsCollection` har `ingredients_complete=True`. Positiva deklarationer finns, men frånvaro av fisk är inte kvalificerad genom denna flagga. Samma stopp gäller de exakta valda, i övrigt näringskvalificerade produkterna; det beror inte på det första produktnamnet i feltexten.
2. Även om denna datalucka senare fylls finns bara **tre** granskade fiskfria referensrecept. Minst två ytterligare olika fiskfria middagskandidater och deras kvalificerade produkt-/beredningskedjor behövs. Med två befintliga simmer-rätter och en couscoussallad behövs också minst en tredje tillagningsmetod för fem inom Balanserads max två per metod. De 70 kvarvarande vanliga fiskfria kandidaterna saknar granskad beredningsgrund; enbart generiska råa näringsreferenser fyller inte detta hål.

Efter rättning: 90 råa kandidater → 17 verkliga fiskuteslutningar, 3 avslag på ingrediensunderlag (alla dessa 20 redovisas i policy/smak), 70 beredningsavslag, 0 individuellt godkända och 0 sökgrenar. Protein/kcal, butikstak och slutlig variation har därför inte ens prövats för en fiskfri femmeny. Inga nya recept eller näringsmappningar har lagts till: det skulle inte övervinna den första obligatoriska datagrinden. Minsta nästa dataarbete är kvalificerat ingrediensunderlag för en gemensam fiskfri råvarubas, följt av de saknade varierade beredningskedjorna. Detta är en konkret täckningsbrist, inte ett påstående om matematisk omöjlighet för fiskfri mat.

### Bekräftad bugg och rättning

Före ändring accepterade receptfiltret lax och tonfisk trots `exclusions=["fisk"]`; produktkontrollen accepterade också lax med komplett syntetiskt deklarationsunderlag. Sex nya negativa tester misslyckades före rättning. Explicit ordet fisk omfattar nu befintlig `food_family=fish` i recept och produktklassning samt positiva fiskartstermer i sammansatta produktdeklarationer. Namngiven art utvidgas inte automatiskt till alla fiskarter i produktkontrollen. Okänd ingrediensfullständighet/allergenfrånvaro förblir DATA_BLOCKED. Ingen allergisäkerhet påstås.

## Acceptans och skydd

### Befintligt skafferifall

| Middag | Protein g/portion | kcal/portion | Grund |
|---|---:|---:|---|
| Couscoussallad med tofu och tomat | 21,34 | 420,80 | ESTIMATED |
| Kokt kyckling med ris och morötter | 41,97 | 492,79 | ESTIMATED |
| Kycklingsoppa med äggnudlar och vitkål | 47,63 | 506,77 | ESTIMATED |
| Stekt torsk med äggnudlar och vitkål | 39,94 | 471,87 | ESTIMATED |
| Stekt lax med ris och morötter | 37,54 | 613,78 | ESTIMATED |

Full inköpskostnad **688,73 kr**. Inköpsställen: Coop Online Syd, Willys Lund.

500 g bekräftat torrt ris finns kvar i faktiskt lager före/efter generering och 500 g allokeras i planen. Annan meny än originalet; 688,73 kr är därför inte en samma-menybesparing. Planerad förpackningsrest räknas inte som redan befintligt skafferi eller uppäten näring.

Strikt produktläge utan uppskattningar: tidigare A2 ostsmörgås, två portioner, **30,38 kr**, `VERIFIED`. Ingen generisk referens aktiveras. Tillagad portionsvikt och fullständiga allergener förblir separat DATA_BLOCKED.

För alla lyckade femmenyer är näringsgrund **ESTIMATED**: SLV livsmedelsspecifika kopplingar för kokning/stekning per rå ätbar insats och separat granskad couscous-/tofu-/tomatsummering utan avrinning. Torsk använder kvalificerad produktdeklaration med dokumenterad tillagningsjustering; övriga valda komponenter i dessa frysta menyer använder generiska, explicit mappade referenser. Skafferiris har bekräftad `slv:2481:dry`. Inget antagande gör rå/torr/avrunnen mängd till verifierad tillagad vikt, och överskott ingår aldrig i uppäten näring. Alla fullständiga näringskällor och transformationskedjor följer planerna i JSON.

- **367 relevanta regressionstester PASS**: 218 pris-, flerköps-, medlems-, paket-, låsnings-, skafferi-, närings- och bokförda revisionsfall samt 149 befintliga konsumentplaneringstest. [JUnit](affordable-five-20260912/regression.xml), [konsumentregression](affordable-five-20260912/consumer-regression.xml). 47 fokuserade ingår i dessa 367 och räknas inte dubbelt.
- Python 3.12, Ruff, compileall och `git diff --check` passerar. Inga nya goldens.
- Fryst acceptans förbjuder socketanslutningar; samtliga fall har noll externa anrop. [Serverimageprov](affordable-five-20260912/runtime.json) körde Docker `--network none` med riktigt monterad pris-/rådatakälla och gav samma kostnader. Dess prisversion är dagens behållna `11e58c7c…`, redovisad separat från den äldre kostnadsfixturen.
- [HTTPS-acceptans](affordable-five-20260912/https.json): original, samma meny, Billigast, skafferi och strikt läge PASS, sparad återläsning PASS, ingen fisk 422/DATA_BLOCKED. Faktiskt lagersaldo oförändrat. Endast API-acceptans i denna release; ingen ny webbläsar-/iPhone-kvalificering.
- Två tidiga prov hade fel i provkoden (fel monteringsadress till rådata respektive `id` i stället för `plan_id` vid återläsning). De räknas inte som acceptans. Slutliga artefakter kommer från korrigerade prov.

## Drift och återställning

Endast tre appfiler ändrades. Release `personal-v2-cost-fish-20260912`, appkod `e5a3787`, image `sha256:4226869fc258d0ad96c1c4b1f79ce71b3d89749fbf89c01e2d815f7bf888e769`. Backup **20260912T145001Z** komplett före aktivering. Befintligt gemensamt driftlås användes; **140 tidigare planrevisioner bevarades**, 146 efter HTTPS-proven. Scheduler, prismanifest och databasens schema är oförändrade; integrity_check ok. [Driftevidens](affordable-five-20260912/deployment.json), [källhashar, health/ready](affordable-five-20260912/source-hashes.json), [rollbackprov](affordable-five-20260912/rollback.json).

Befintlig läskompatibel rollback `personal-v2-dinners-20260911c-rollback` är testad utan nätverk med de slutliga request-/planmodellerna och spärrar plan-/skafferiskrivning med 503. Aktivera med befintliga `personal_v2_cost_activate.py rollback` på servern; behåll databaser, historiska köp och revisioner. Ingen databasrestore.

Ready efter driftsättning var **AGING**, äldsta användbara pris cirka **36,8 timmar**, med 6 användbara kontexter och oförändrade 36/48-timmarsgränser. Ingen källa insamlades eller aktiverades av denna milstolpe. Ingen ändring av kallprestandaarkitektur, OIDC, ICA OWN, Willys-task/relay eller Coop-scope. Den tidigare femmiddagsmilstolpen och dess R1–R9-status bevaras.
