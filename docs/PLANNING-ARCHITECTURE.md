# Planeringsarkitektur för Smakos produktmål

## Deklarerat antal hela varor i befintlig mängdväg

Ett exakt granskat tillverkarantal får projicera användbar mängd i `st`
för samma källprodukt och förpackning. Receptets form måste vara `as_sold`;
gramvikten för inköpta förpackningar bevaras och får inte användas som
ätlig styckevikt eller näringsgrund. När inköpsenheten är gram kräver den
befintliga skafferijournalen uppmätt antal före förbrukning i stycken.
Två explicita frysta majskolvsrecept använder denna väg. Se
[granskningen](reviews/whole-corn-20261028.md).

## Versionerad bladplockning i befintlig beredning

Samma metodval, inköpsgruppering och uppmätta PersonalStore-journal stödjer
myntablad från tio redan exakt granskade råmyntakontexter. Exakt utgivet
recept och uppskattningsval krävs. Den befintliga produktrelationen används
även vid råvarans kandidatsökning; ingen fuzzy auktorisering eller separat
prisväg. Bladgram × 0,85 / 0,5464 är en uttrycklig brygga mellan två oberoende
begränsade referenser. Faktiska insats-/bladgram och svinn bokförs; kort utbyte
stoppar förbrukning. Bladpartier har egen identitet, okänd näring/hållbarhet
och omprövas mot aktuell källprodukt och personliga krav. Äggstödet består.
Se [granskningen](reviews/mint-leaf-preparation-20261028.md).


## Oförändrat paketantal i befintlig offertcache

En anropsägd, begränsad metadataoffert får återanvändas för samma frysta
exakta fasta kandidatobjekt, användbara enhet och antal hela paket. Den
ordinarie mängdresolvern och källans köpgräns gäller varje gång; namn,
aktuellt behov och rest kommer från den aktuella upplösningen. Erbjudanden,
kampanjgrupper, PurchaseTerms, uppskattningar och egna kalkylatorer/resolvers
behåller ordinarie vägar. Ingen separat pris- eller lagerberäkning införs.
Se [likhets- och prisgrindarna](reviews/plain-food-facts-20261028.md).

## Versionerad gemensam äggberedning

Exakt utgivet receptinnehåll kan ange hen_egg_separation_estimate_v1 via en
metodoperand i befintliga ingredienskrav. Endast uttryckligt uppskattningsläge
får planera insatsen: helt ägg + max(3 × gula, 1,5 × vita), i kvalificerade
ätbara gram. Inga komponentpaket eller nya prisvägar skapas. Befintlig
resolve, gemensam inköpsgruppering, mängdresolver, checkout och audit består.

PersonalStore bokför uppmätt köp, reserverad rå insats och faktiskt uppmätta
separata utfall i samma transaktion/journal. Beredda partier har egen
komponentidentitet och metod-/produktursprung. De kvalificeras på nytt för
aktuell kost, allergi, eko och separat tillåten komponentnäringsuppskattning.
Kort utbyte sparas sanningsenligt men blockerar förbrukning. Delvis förbrukning,
omplanering och frigivning bevarar verkligt lager och historik. Båda utfallen
delar köp; komponentöverskott och paketrest redovisas separat. Inget framtida
restvärde krediteras i checkout. Se [granskningen](reviews/egg-preparation-20261028.md).

## Exakt granskad torr form och ren textklassning

Vatten i en innehållsdeklaration är en konservativ våtformsheuristik. Den
kan nu övervinnas enbart av befintlig exakt granskad torr produktrelation,
med samma källidentitet, sammansättning och mängd; kokt/färdig vara blockeras.
Två rena namn-/kategorifunktioner använder begränsad memoization av enbart
oföränderliga textresultat. Produktfakta, priser och personliga beslut cachas
inte av detta. Fulla klassningssvar för alla 89 458 produkter är identiska.
Se [granskningen](reviews/product-facts-20261028.md).

## Granskad avrunnen massa även för färdigkokta räkor

Samma befintliga exakta mängdprojektion accepterar cooked_drained och
preserved_drained. Den kräver en full granskad relation för samma produkt,
butik, snapshot, nettovikt och sammansättning, deklarerade avrunna gram
samt oförändrad konfliktspärr. Det konverterar inte rå vara till tillagad
vikt. Nettoinköp, förpackningsavrundning och separata personliga krav består.
Se [produktgranskningen](reviews/reviewed-drained-foods-20261027.md).

## Deklarerad avrunnen massa och statisk spärrfrasscope

Exakt granskade fasta förpackningar kan projicera deklarerad avrunnen massa
genom befintlig mängdväg även utan uppskattningsval. Nettoinköp, källidentitet,
konfliktspärrar och personlig kvalificering består. Hela sammansättningen
granskas separat och godkänner inte allergen-/ekokrav. Fasta regelord och
spärrfrasers namn-/kategoriscope beräknas vid inläsning, med identiska fulla
klassningssvar; priser eller användarbeslut cachas inte av detta.
Se [fortsättningsrapporten](reviews/coverage-continuation-20261027.md).

## Ät inte och allergier utan fullständig deklaration (ägarbeslut 2026-11-14)

Endast 351 av 71 169 produktfakta (frusen data 2026-10-23) hade fullständig
ingrediensförteckning, så varje allergi och varje Ät inte gav ingen plan.

- *Ät inte* kontrolleras mot receptets ingredienser och varans namn, även i
  sammansatta ord (`mentions`: "lök" träffar rödlök och lökpulver, "fläsk"
  fläskfilé; "glutenfri", "utan ägg" och ord där den andra delen är kortare än
  tre bokstäver räknas inte), och mot deklarationen när den finns. Utan
  fullständig deklaration godtas en vara som inte är sammansatt
  (`is_composite`: sås, buljong, krydd- och smakblandningar, färdigmat, bröd,
  godis med flera, på namn eller källkategori). Sammansatta varor kräver
  fortfarande deklaration.
- *Allergi* kräver fortfarande fullständig deklaration och kontrollerad
  allergen. Undantaget är färsk frukt, grönt, svamp och örter
  (`single_ingredient_by_rule`): de behöver ingen ingrediensförteckning enligt
  EU 1169/2011 artikel 19 och är sin enda ingrediens. Torkat, inlagt, blandat
  och allt vars namn pekar på en stor allergen (nötter, sesam, senap, soja,
  selleri, lupin, vete) omfattas inte. Inga produktfakta skapas; regeln
  tillämpas vid kontrollen.
- Allergier begränsar därför fortfarande planerna kraftigt tills fler
  deklarationer hämtas in, styrt av receptbibliotekets efterfrågan.

## Näring som går snabbt och alltid syns (steg 3, 2026-11-15)

- **Delad näringsevidens.** `PersonalPlanner.nutrition_evidence` läser per
  100 g-evidens för en vara och receptingrediens. Den beräknas nu för alla fyra
  makron (energi, protein, kolhydrater, fett) på en gång och delas mellan
  förfrågningar i `planner_shared_cache.SHARED_NUTRITION`, med scope = exakt
  förberett prisunivers (svag referens), `facts_version`, näringsreferensens
  version och inställningar. En fråga om en del av makrona återanvänder
  evidensen; en deklaration med bara några av de fyra behåller sin deklaration
  för de fält den har. Saknas evidens för alla fyra saknas den också för en
  del (alla evidenskällor bär alla fyra). Inga portionskontroller, korgar eller
  priser delas. Gränsen är 400 000 poster (`SMAKO_SHARED_NUTRITION_ENTRIES`),
  `SMAKO_PLANNER_SHARED_RESOLUTION=0` stänger av. På frusen data
  2026-10-23 (Malmö): första näringsbegränsade planen 105 s lokalt, därefter
  36–42 s för nya gränser (tidigare 77–94 s).
- **Uppvärmning.** Vid start och efter varje aktiverat prisunivers schemalägger
  appen `nutrition_prewarm` (oberoende av den vanliga planuppvärmningen, som är
  avstängd på beta): en vanlig planförfrågan med gränser som alltid uppfylls
  (protein/kolhydrater/fett ≥ 0, energi ≤ 4000 kcal) för middag, frukost och
  mellanmål. Den körs bara när planeraren är ledig (`only_if_idle`), med 45 s
  egen tidsgräns, och sparar ingen plan. `SMAKO_NUTRITION_PREWARM=0` stänger av.
- **Näring alltid.** Den slutliga planen visar näring per portion även utan
  gränser, när varje ingrediens har värden (alla fyra, annars de som går).
  Det stoppar aldrig en plan och ändrar inget val. Antal portioner påverkar
  inte värdet per portion; portionsvikt är fortsatt ett filter.

## Planer som känns rimliga (steg 4, ägarbeslut 2026-11-15)

Menysökningen rangordnar nu veckor efter **betalt belopp + butikskostnad +
smakkostnad** (`PersonalPlanner._week_purchase_key`, `score`). Samma värde
används i biblioteksökningens kvarhållning och förfining, vid jämförelse med
lösningar från lägre butikstak och i den nedre gränsen
(`bounded_evaluate`). Priser, produkter och kontroller ändras inte.

- **En extra butik måste spara minst 10 kr** (`EXTRA_STORE_MIN_SAVING`).
  Varje butik utöver den första kostar 10 kr i rangordningen. För den valda
  menyn jämför `_fewer_stores` dessutom den exakta billigaste korgen för varje
  lägre butikstak och behåller den med lägst summa + 10 kr per extra butik;
  lika betyder färre butiker. Verifieringsstatus får inte bli sämre. Med
  ekologisk andel, näringsgränser eller "Större köp går bra" söker de stegen
  egna butiksuppsättningar upp till taket; där gäller regeln bara i
  rangordningen. Användarens butikstak är fortfarande ett tak.
- **"Gillar": minst en rätt, med pris och billigare alternativ.** Varje
  gillad term (receptnamn eller ingrediens, även i sammansatta ord:
  "kycklingfilé" nämner kyckling) som någon middag som passar de övriga valen
  nämner finns i minst en middag i en ny vecka. En vecka utan den räknas som
  `LIKE_MISSING_KR` = 1000 kr dyrare i rangordningen, så sökningen alltid hittar
  en plan; går det inte står det i `checks.likes` (`not_included`), och saknas
  sådana recept helt står `not_available`. Utöver det väger varje recept med
  en gillad term 15 kr (`TASTE_WEIGHT_KR`), så fler gillade rätter kommer med
  när de nästan inte kostar något. Ett recept med något som inte gillas räknas
  15 kr dyrare. Tidigare räknades en gillad term högst en gång per vecka och
  bara som 2 kr, och bibliotekssökningen rangordnade efter enbart pris.
  **Sökordning (2026-11-16):** med gillningar söker planeraren först veckan
  som om inget vore gillat (ogillat räknas fortfarande), och lägger sedan in
  varje gillning som saknas genom att byta en middag: för varje middagsplats
  prövas de åtta billigaste gillade recepten (inköp för receptet ensamt) och
  veckan med lägst rangordning som klarar alla regler behålls
  (`_add_likes`). Startpoolen får dessutom de fyra billigaste recepten per
  gillning och, för en blandad vecka, per slag (`_seed_wanted`). Gillningar
  tar därmed ungefär lika lång tid som en vanlig vecka (lokalt 57 s mot 53 s,
  tidigare 62–68 s), och veckan utan gillningarna är känd exakt utan en ny
  planering: `checks.likes[].without` har vad den kostar, hur mycket mindre
  det blir och vilka middagar som byts (med recepten). Den gillade veckan kan
  bli några kronor dyrare än en full sökning med gillningen hade gett (frusen
  data: kyckling 176,23 mot 172,26 kr). Provgränssnitten visar priset på
  receptkortet ("Du gillar kyckling · 32,06 kr dyrare än billigaste
  alternativet", "Visa billigare recept") när bara den gillade middagen byts,
  annars en rad för veckan ("utan kyckling hade veckan kostat X kr mindre",
  "Visa veckan utan kyckling"). Bytet sparar de redan prissatta recepten med
  `change` (`action: replace`, `recipe_ids`) utan ny sökning. Förhandsvisningen
  `preview_without_like` finns kvar i API:t men används inte av gränssnitten. Byte av ett recept kräver inte gillningen
  igen. På frusen data (Lund, 3 middagar) ger "gillar kyckling" en kycklingrätt
  (176,96 kr i stället för 144,17 kr) och billigaste alternativet är
  falukorv (162,17 kr); förhandsvisningen tog 52 s lokalt.
- **"Allt" betyder blandat** (`mixed_week_ok`). Med kostvalet Allt, två eller
  fler middagar och ingen egen fördelning har minst en middag kött, kyckling,
  fisk eller skaldjur och minst en är vegetarisk. Regeln gäller nya veckor och
  byte av ett recept, men bara när de övriga valen (vid byte: den platsens
  recept) gör den möjlig. Delveckor godtas så länge de
  återstående platserna kan uppfylla den. På frusen data blir veckan 144 kr
  med falukorv i stället för tre tofu- och kikärtsrätter för 134 kr.
- **Omväxling som standard i provgränssnitten.** Med tre eller fler middagar
  skickar `/ui/a` och `/ui/b` `max_same_main_protein_dinners: 2`
  (`recipe_week_variation`): högst två middagar med samma huvudprotein.
- **"Har du hemma?"** (`personal.staples_at_home`, `app/services/staples.py`).
  Personen kan bocka för salt, svartpeppar, rapsolja, olivolja, socker,
  vetemjöl och torkade kryddor. Salt, svartpeppar och rapsolja är förbockade
  från början (ägarbeslut 2026-11-15). En förbockad basvara köps inte till
  recepten och redovisas i `personal.at_home`. Det är ett påstående från
  personen, inte en skafferimängd: inget reserveras eller dras av, och raden
  ingår inte i `remaining_demands`. Basvaran köps ändå när måltiden har
  näringsgränser (värdena måste vara deklarerade), när raden har allergier
  (deklaration krävs) och för egna varor eller låsta produkter. Den visade
  näringen använder den granskade generiska referensen i samma enhet
  (salt, vetemjöl, kanel, spiskummin, gurkmeja per gram); annars, som för
  olja i milliliter, visas ingen näring för det receptet. Inget värde hittas
  på. På frusen data blir veckan 87 kr i stället för 144 kr när alla
  basvaror är förbockade.

## Fart (steg 6, 2026-11-16)

Mätt på beta 2026-11-16 (3 middagar, salt/peppar/rapsolja hemma): Lund 51 s
(kö-steget 8 s, varufakta 11 s, kvalificering 15 s, veckosökning 16 s), Malmö
81 s (34 butiker, alltså 90 s-gränsen: kö-steget 7 s, varufakta 15 s,
kvalificering 15 s, veckosökning 40 s). Planerarens egna tider för Lund:
varufakta 7,4 s och minnesrensning 7,0 s.

- **Minnesrensningen efter jobbet** (`planner_memory.reclaim_and_freeze`):
  den fulla skräpsamlingen före varje jobb (7–8 s i "kö") och före sökningen
  (7 s) gick igenom alla långlivade delade cacher. Nu körs den fulla
  samlingen efter att jobbets resultat är ute, innan nästa jobb släpps in, och
  fryser det som överlever (`gc.freeze`), så att samlingarna under nästa jobb
  bara går igenom jobbets egna objekt. Före jobbet samlas bara unga objekt.
  Inget levande tillstånd släpps; cykliskt skräp bland frysta objekt samlas
  efter nästa jobb.
- **Varufakta delas mellan förfrågningar** (`cached_retained_facts`): samma
  aktiverade prisunivers och oförändrade källfiler (databas, råfiler,
  Axfood-detaljer: storlek och ändringstid) ger samma faktaobjekt i högst
  `SMAKO_RETAINED_FACTS_TTL` sekunder (600, 0 stänger av). Versionen räknas
  inte om när faktan laddades av planeraren själv och inte ändrats.
- **Veckosökningen slutar när den inte hittar något billigare**
  (`SMAKO_MENU_SEARCH_STALL_SECONDS`, 10 s; 0 som förut). Tidigare letade den
  tills 12 s återstod av tidsgränsen. På frusen Malmödata kom alla sex
  förbättringar inom 0,6 s och resten av en 90 s-gräns ändrade inget: 78 s
  blev 52 s med samma vecka (153,00 kr). Planen redovisar
  `improvement_search_seconds` och `stop_reason`
  `no_improvement_for_stall_seconds`, och meddelandet säger att vi slutade leta
  när vi en stund inte hittat något billigare. Globalt lägsta pris är som
  förut inte bevisat.
- **Näringsuppvärmningen** körs i upp till tre rundor om en runda når sin
  gräns på 45 s; varje runda väntar på en ledig planerare.
- **Gillningar** kostar ingen extra planering (se steg 4).

## Förpackningsvikt när avrunnen vikt saknas (ägarbeslut 2026-11-13)

Vill ett recept ha en vara avrunnen (`cooked_drained`, `preserved_drained`)
och produkten anger ingen avrunnen vikt, räknar planeraren med förpackningens
vikt och säger att vikten utan spad kan bli lägre. Det gäller överallt:
matplanen, inköpslistan, "Jag har handlat" och skafferiets valda varor.

- Deklarerad avrunnen vikt går först (`complete_recipes.declared_drained`):
  ägargodkänd förpackningsidentitet, granskningsregistret, faktabevis med
  `basis: drained`, eller källans egen brutto/avrunnet-vikt som normaliseringen
  lagrar som användbar mängd med `DERIVED` (City Gross "400/240 g", Lidl).
- Annars godtas förpackningsvikten bara för en fast förpackning i gram som
  ligger i vätska (`package_weight_drained`): ingrediensförteckningen nämner
  vatten, lake, olja, ättika eller vinäger, eller namn/hylla säger konserv,
  "naturell", "i vatten" o.d. Torkade, smaksatta varor och varor i sås godtas
  inte; torkade bönor väger mer kokta och vore fel åt andra hållet.
- Receptets identitets- och kravkontroller körs före regeln och ändras inte.
- Köpraden får `drained_weight_from_package`; gränssnitten visar notisen.
  `GET /api/personal/pantry-product?name=…` svarar med `drained_from_package`.
- Mätt mot den frysta Malmö-referensen: kikärtor, vita/svarta/kidneybönor,
  kapris och tonfisk får 8–22 nya godkända butiksrader var (Willys, Hemköp).

## Statisk prioritet i den kompletta menysökningen

Den befintliga kompletta V2-sökningen räknar singletonprioriteten en gång
per måltidsplats och anrop. Värdet beror på fast kvalificerat prisunderlag
och fasta preferenser. Återanvändning vid ankarnas sortering behåller
ordning, dagsspecifika värden och alla kandidater; den frigör tid för fler
fullständiga checkouter inom oförändrad deadline. Tolv sekunders
slutreserv, audit och sparning består. Detta ger inget globalt optimumbevis.
Se [fyravarugranskningen](reviews/recipe-four-staples-20261027.md).

## Ordinarie viktpris när en äldre rabattgräns saknar enhet

En äldre katalograd kan ha ett separat ordinarie kilopris och ett kg-erbjudande
vars rabattgräns saknar verifierad enhet. I uppskattat läge får `user_pricing`
använda det ordinarie priset genom befintlig prisresolver, när försäljningsform,
kilopris och mängdunderlag är belagda. `PurchaseQuantityResolver` beräknar
sedan faktisk inköpsmängd och avrundar hela variabla paket. Erbjudandet finns
kvar som källmetadata men tillämpas inte. Varken erbjudandets identifierare
eller förpackningsvikten skapar nya `PurchaseTerms` eller en rabattgränsenhet.
Den befintliga vägen för uttryckligen belagda paketgränser behåller sina rabatter.
Exakt läge, separata inköpsgränser och identitets-/näringsvillkor består.
Se [kontrollpunkten](reviews/recipe-weight-coverage-20261027.md).

## Konkret mängd- och sökkomplettering 2026-10-27

`official_product_facts` använder samma produkt-/butiks-/snapshotbundna
leverantörsbevis för deklarerad gramvikt i en styckförpackning och deklarerad
volym i en gramförpackning. Förpackningens inköpsidentitet behålls, medan
`project_usable_quantity` bara projicerar den uttryckligen begärda användbara
enheten. Näringsomräkning kräver förpackningens belagda mass-/volympar och
oförändrade konfliktspärrar. Ett gramvärde ensamt innebär aldrig en densitet.
Den här vägen används för exakt 12-blads/20-g gelatin och ett källbelagt
1000-g/1000-ml kefirpaket. Nya bevis ingår i befintlig metod-/faktaversion;
inga priser eller observeringstider byts i den frysta jämförelsen.

Den kompletta menysökningen återstartar de prisordnade enstaka receptbytena
när en bättre gemensam korg hittas. Ett tidigare olönsamt byte kan bli
lönsamt efter ett annat byte genom delade förpackningar. Den ordinarie
strömmen av fulla menyförslag fortsätter parallellt i samma seriella sökning.
Det är en ändrad förslagsordning; deadline, slut-audit, sparning och alla
hårda användarvillkor gäller fortfarande. Ingen global optimalitet påstås.

**Den tidigare spärren är löst för versionerad äggseparering enligt ovan.**
Enbart en ny mängdfaktor i `resolve` räcker inte: före äggstödet bokförde
`personal_store` samma mängdenhet för inköp, reservation och förbrukning. Gula och vita från samma
ägg behöver en gemensam inköpsgrupp och separata uppmätta utfall, även vid
delvis förbrukning, omplanering och återstående skafferi. Receptens
insatsnäring och aktiva/vänt-/totaltider måste följa den granskade versionen.
Fler beredningsmetoder ska utöka dessa befintliga vägar och deras förberedda
beroenden, inte lägga till en fristående berednings- eller prisdatabas.
Se [källgranskningen och acceptansfallen](reviews/recipe-coverage-full-20261027/preparation-review.md).

## Tillägg 2026-10-27: full recepttäckning före mer generell optimering

Ägarens mål är att alla 2 200 importerade varianter blir användbara.
Nästa uppdrag är [COVERAGE-FOLLOWUP](CODEX-SOL-NEXT-20261027-COVERAGE-FOLLOWUP.md).
Den gemensamt förberedda produkt-/faktanivån ska därför kompletteras;
fler recept eller mer cache löser inte en saknad ingredienskoppling.

Separera bevis för **produktidentitet och kulinarisk form**, **köpbar
mängd**, **pris i rätt butik** och **personliga egenskapskrav**. Återanvänd
befintliga produktfakta, register, `PersonalPlanner.resolve` och checkout.
En importerad `definition_only` beskriver ett behov, inte en fungerande
produktrelation. Nuvarande `intake_product_links.declared_definition`
kräver både en särskild tillverkardeklaration och exakt mängd. Det är en
gräns i den nuvarande vägen, inte ett permanent krav att varje vanlig
grönsak måste ha just denna maskinella deklaration från tillverkaren.

Godkänd källinformation får efter granskning bindas till rätt produkt och
användas i samma register: exakt identifierad butik-/tillverkarprodukt,
belagd form och sammansättning där den behövs samt korrekt mängdunderlag.
Fuzzy namnträffar räcker inte. Full ingrediensdeklaration krävs när den
behövs för exempelvis en sammansatt produkts renhet; den ska inte krävas
slentrianmässigt för att identifiera en entydigt belagd hel färsk råvara.
Kräv inte att källan redan publicerar Smakos interna klassificeringsfält.

**Skilj också osäker mängd från osäker identitet.** Utveckla vid behov den
befintliga uppskattningsvägen för källbelagda inköpsvikter/ätliga utbyten,
med explicit `estimated`-val. Spara källa, metodversion, råvaruform och
tillämpningsvillkor; kontrollera beräknad inköpsmängd, förpackningsavrundning,
kostnad och förbrukad näringsmängd separat. Generella utbyten är uppskattningar,
inte nya deklarerade fakta om en enskild förpackning. Krukvikt, skal/ben,
avrunnen vara och tillagad vikt är inte utbytbara. Saknat underlag för en
sådan beräkning förblir ett hinder. Ingen uppskattning får kringgå okänd
identitet, allergenrisk, ekologiskt bevis eller ändra användarens mängdpolicy.

Förtydligande efter PR #19: samtliga mängdprojektioner ska följa samma
befintliga mängdkonfliktspolicy, inklusive den nya vägen för granskade
utbyten. Bara kända rena näringskonflikter får undantas från mängdspärren;
ett prefix som `nutrition.` får inte i sig godkänna en okänd mängdkonflikt.
Kontrollen ska ske innan en mängdberäkning accepteras och bevaras genom
efterföljande produktkvalificering. En godkänd mängd gör inte omstridd
näring användbar för ett personligt näringskrav.

Förbered och återanvänd dessa relationer per exakt beroendeversion och
butiksscope. En prisuppdatering ska kunna återanvända oförändrade faktabevis;
en ändrad produkt/form/deklaration ska invalidera berörda relationer.
Bevara originalrecepten och alla aktuella hårda krav. Nya faktaversioner
får inte tyst skrivas in i gamla mätningar eller sparade planer.

Redovisa separat import, individuellt lösta ingredienser och fullständigt
verifierade receptkorgar, med fast nämnare och referensscope. Täckning i
en region/ett mängdläge bevisar inte stöd för alla butiks-/personval.
Hela bibliotekets ökande användbara pool ska senare ingå i tidsproven;
tidigare 55,12 s med en mindre kvalificerad pool är ingen ny tidsutfästelse.

## Tillägg 2026-10-26: hel meny före bred prefixprissättning

För genererade aktuella V2-urval med fler än 64 alternativ i någon slot
föreslår befintlig MenuOptimizer kompletta menyer före gemensam checkout.
Detta väljer algoritm, begränsar inte biblioteket. Alla hårda acceptans-
och produkt-/pris-/närings-/ekoregler samt slutlig aktuell audit/save består.
Kvalificeringens privata singletonpriser och paketidentiteter prioriterar
förslag; de är inga giltighetsintyg eller undre gränser för hela veckan.
Prioriterade och ursprungliga ankare varvas och redan giltiga hela korgar
förbättras inom kvarvarande tid. Oprövade alternativ redovisas som uppskjutna,
inte globalt omöjliga eller dyrare. Resultatet saknar globalt optimumbevis.

Förbättringscheckouter får en nästlad kooperativ deadline som reserverar
tolv sekunder av samma absoluta begäransbudget för aktuell slutkontroll,
lagring och svar. Ett avbrutet förbättringsförsök får inte kasta en tidigare
giltig kandidat eller förlänga den yttre deadlinen. Fulla resultat begränsas
till bästa och pågående utvärdering; högst 4 096 kompakta menyidentiteter
används för att undvika identiska utvärderingar. Privat allokering/lås
behåller ordning. Varje nytt anrop/ägare får egen sökstatus.

I den ordinarie slot-beamen reserveras överlämnade förstamåltidsresultat
tills de konsumeras i samma ordning. Reserverade resultat och fortsatt cache
delar fortfarande totalt 256 poster. Detta ändrar arbete, inte ranking,
tie-break, kandidatgiltighet eller finalkontroller. Äldre återställda UI-val
utan intentmetadata förblir utan metadata tills användaren väljer nytt intent.

[Mätningen](reviews/broad-week-search-20261026.md) visar oförändrat A med
53,37 s API/save/GET och 55,12 s verklig browser, 297,18 kr; B2 behåller exakt
731,20-kronorskorgen. Det är singelprov med förberett underlag, inte p95,
samtidighet, verklig veckouppdatering eller hela valkatalogens kvalificering.
Legacy är fortfarande standard och den nya vägen opt-in.

## Tillägg 2026-10-26: uttryckliga val och känd standardvariation

För nya opt-in-anrop med `smako-current-library-v2` och
`variation_intent.version=explicit-over-default-v2` sparas varje variationsfälts
ursprung: `default`, `explicit` eller `unknown`. UI skickar inte förifyllda
standarder som skenbart uttryckliga begränsningar. Råa tidigare värden och
ursprung bevaras vid återläsning. Utan metadata gäller tidigare tolkning;
legacy/V1 och gamla sparade revisioner omtolkas inte. UI kräver ett nytt val
för att ersätta en äldre okänd standardtolkning. En uttrycklig hård gräns
behålls tills användaren ändrar själva gränsen.
Sparat nytt intent får heller inte tappas när en miljö återgår till legacy:
ägd GET fortsätter fungera, men ny beräkning med de reglerna avvisas om
sökpolicyn inte stöder dem. En redan committad identisk ändring kan återläsas.

Tre klassificeringar förblir separata: måltidsfördelningen använder en enda
kost-/proteinkategori per recept, den kulinariska huvudråvarugränsen använder
profilens enda `primary_protein`, och veckans huvudproteingräns räknar alla
författade substantiella proteinkällor, även båda delarna av en blandrätt.
Varianter delar samtidigt grundrättens `base_id`; ingen av dessa regler
ersätter basupprepningskontrollen.

Innan menyförsök beräknas en konservativ kapacitet ur de faktiskt
kvalificerade aktuella recepten: per vald kategori grupperas distinkta
baser efter den kulinariska primärklass som samma acceptanspredikat använder.
Summan av `min(tak, antal baser)` är en övre kapacitetsgräns. Okänd klass
ger inget omöjlighetsbevis. Om en uttrycklig måltidsfördelning kräver mer än
denna kapacitet får en **känd ärvd** huvudråvarustandard höjas endast till
minsta tillräckliga tak. Övriga variationsregler och samtliga egna hårda
val består. En explicit eller okänd gräns anpassas inte automatiskt.
Två motstridiga hårda val ger ett konkret konfliktbesked inom denna
kvalificerade pool, inte ett globalt bevis om alla tänkbara livsmedel.

Rå begäran, ursprung och normaliserade värden sparas med planen; faktisk
effektiv policy och motiverad standardanpassning sparas i planens checks
och visas för användaren. Original-B behålls som negativt underlag. B2
behåller dess 52 butiks-ID:n och övriga val men markerar bara den tidigare
huvudråvarustandarden som känd standard. Det är ett nytt acceptansfall.

**Ägarbeslut 2026-11-14: tidsgränsen räknas från att motorn börjar.** Tiden i
planerarens kö (admission) räknas inte in i planerarens 60 s. När en begäran
väntar på en ledig plats pausas dess timers (`pause_engine_clock`), och när den
släpps in flyttas alla omslutande deadlines och asyncio-timers fram med kötiden
(`start_engine_clock`). Arbetet efter insläppet, inklusive checkout, audit och
sparning, har fortfarande sina 60 s. Jobbstatus visar `engine.elapsed_seconds`
och `engine.limit_seconds` efter insläppet. Klientens klocka från knapptrycket
visas separat och ändras inte. Mätningar av latens ska därför redovisa kötid och
motortid var för sig.

Samma serverdeadline (räknad från insläppet enligt ovan) följer nya och
personliga ändringsanrop genom async-jobb, tråd, inre loopar och transaktion. Timeout före commit rullar
tillbaka revision, reservationer och mutationskvitto. En full revision som
redan committat kan identifieras i timeoutstatus och återläsas genom ägd GET
eller identiskt återförsök utan dubbel revision. Ett sent färdigt resultat
räknas inte som levererat inom 60 s. Kompletterande samma-meny-jämförelser
och produktkontrafaktiska förklaringar är inte obligatoriska före den
aktuella V2-vinnarens checkout/audit/save; inga oprövade prisomdömen visas.

Beslutad riktning 2026-10-25 efter PR #12, main `d27e0cf`. Utgår från
[produktmålet](PRODUCT-GOAL.md). Implementation och mätning återstår;
`legacy` är fortsatt standard och V1:s befintliga beteende ändras inte av
detta dokument. Nästa etapp finns i
[Sols aktuella uppdrag](CODEX-SOL-NEXT-20261027-COVERAGE-FOLLOWUP.md).

## Varför riktningen ändras

[Senaste rapporten](reviews/personal-choice-latency-20261025.md) visar att
V1:s första A-median går 200,72 → 187,50 s, matkök B 138,69 → 128,74 s och
protein C 66,87 → 62,79 s. D når femminutersgränsen. E får `SEARCH_BLOCKED`,
två av 66 recept kvalificeras; ingen färdig lista. Legacy-kontrollen av A
tar 76,86 s. Detta är olika sökpolicyer, inte en generell produktlatens.
Veckouppdateringens verkliga latens är omätt. De nio nya riktade proven har
även omkörts oberoende på PR #12:s main och passerar.

Dyra gemensamma korgberäkningar och V1:s upprepade förberedelse per
publicering kvarstår. Två försök med numerisk memoisation återställdes utan
visad vinst. Att bara lägga till en cache eller värma kompletta personliga
kombinationer är därför inte den fortsatta huvudarkitekturen.

## 1. Gemensamt förberett underlag med tre skilda beroenden

Utöka befintliga `PriceUniverse`, `PreparedPriceUniverse`, recept-/faktakedja
och förberedelsemoduler. En versionsbunden artefakt beskriver exakt recept-,
produkt-, fakta-, käll-, metod- och prisidentitet. Förbered per recept,
ingrediens och butik, inte varje möjlig meny eller varje butiksdelmängd.

- **Receptstruktur:** kompakta immutabla mängder/enheter, klassificering,
  matkök, huvudproteiner, ingrediensantal, tider, grundrätt och variation.
  Indexera alla aktuella recept. Prisbundna värden ska inte ligga i denna nivå.
- **Produkt- och faktakoppling:** exakta tillåtna ingrediens–produktrelationer
  per butik och källscope, enhets-/råformsomvandling, spårbar näring,
  ingredienser/allergener och ekologisk status. Bevara flera produkter när
  näring, form, förpackning eller villkor skiljer sig. Okänt är inte godkänt.
- **Pris- och inköpsvillkor:** förbered den befintliga kalkylatorns rena
  offertdelar, produktfingeravtryck och exakta förpacknings-/kampanjfunktioner
  där det lönar sig. Bind mängd, enhet, datum, butik, metod och samtliga lästa
  villkor. Gemensamma kampanjer över flera rader är fortsatt gemensamma.

Använd befintlig `PackageCostCache` där dess beroenden passar. Ingen ny
prismotor eller produktmatchning införs. Cachevärden är inte köp-/närings-
godkännanden. Dela inte användarens medlemskap, skafferi, allergiprofil eller
historik som offentliga förberedelsevärden. Personliga prispåslag/avdrag och
behörigheter prövas i rätt ägarscope. Behåll full kontext för personliga
resultat; smalare delnycklar kräver dokumenterade läsberoenden och regressioner.

Index får ge snabb exakt filtrering och säkra närings-/kapacitetsgränser.
Ett nominellt receptvärde får inte utesluta ett recept om ett tillåtet
produktbyte kan uppfylla kravet. Gränser måste vara konservativa för alla
aktuella kandidater. Okända fakta får inte bli optimistiska intyg.

## 2. Förberedelse vid uppdatering, inte efter varje nytt personligt val

Bygg och validera förändrade delar när nytt recept-/fakta-/prisunderlag
förbereds i befintlig livscykel. Publicera en sammanhängande version atomiskt
enligt befintliga lås och LKG-regler. Gamla oförändrade strukturer får delas
endast om deras beroenden fortfarande matchar; inga nya tidsstämplar på gammal
data. Kampanjer ska löpa ut även om inget nytt snapshot har publicerats.

En begäran binds till en sammanhängande version. Före leverans kontrolleras
aktuell giltighet enligt befintligt kontrakt; ett prisbyte får inte blandas
med tidigare närings-/priskorg eller publicera ett gammalt resultat som nytt.
Om det behövs omprövning räknas den in i väntetiden. Visa ändrat underlag
ärligt om en kontrollerad lista inte kan slutföras inom budgeten.

Arbetet ska vara deduplicerat, avbrytbart och återupptagbart inom befintlig
admission. Ingen ny scheduler/kö. Ett valt butiksområde blir en vy över
förberedda butiksdata; bygg inte alla geografiska urval i förväg. Användarjobb
får inte vänta bakom obegränsad förvärmning. Även kall miss måste vara korrekt.
Total bytebudget ska omfatta nycklar, referenser och överlappande versioner,
inte bara antalet poster i var och en av flera cacher.

## 3. En gemensam personlig sökning över aktuellt bibliotek

Inför som separat opt-in-utvecklingspolicy **`smako-prepared-personal-v2`**
en sökväg som använder hela aktuella bibliotekets förberedda underlag.
Använd befintliga kravmodeller, prisberäkning och slutlig audit.

1. Normalisera användarens plats/butiker, måltider, portioner och samtliga
   hårda/mjuka val. Filtrera säkert via index och bygg ett kompakt personligt
   beslutsunderlag; behåll produktalternativ som behövs för näring och eko.
2. Sök efter en fullständig giltig meny tidigt och förbättra dess faktiska
   gemensamma korgkostnad inom kvarvarande budget. Återanvänd inkrementella
   mängder och beräkna om ändrade delar, inte identiska hela korgar i varje steg.
3. Receptval, produktval, inköpsmängder, butiksgräns, näringskrav, ekologisk
   kostnadsandel och variation måste kunna påverka varandra. Välj inte först
   billigaste produkt per recept och lås sedan bort de alternativ som gör
   hela menyn giltig eller billigare. Ekokravet gäller faktisk rabatterad
   matkostnad; antal ekologiska produkter är ingen ersättning.
4. Använd bevisat giltiga undre gränser för säker gallring och en verifierad
   bästa kandidat. Heuristik får prioritera men inte påstå fullständighet
   eller globalt optimum efter en begränsad sökning. Rangordning och pengar
   använder befintlig exakthet, inte avrundade jämförpriser.
5. Gör aktuell gemensam checkout/audit, spara och återläs den fullständiga
   listan innan leveransen räknas klar. Deadlinekontroller behövs även inne
   i dyra korg-/butiks-/näringssteg, inte bara mellan två plananrop.

Detta är en gemensam begränsningsstyrd sökning med befintlig checkout som
auktoritet. Val av algoritm/bibliotek ska motiveras med ett litet likvärdighets-
och tidsprov; inget nytt solverberoende antas redan finnas. Om ett verktyg
använder heltal eller relaxerade kostnader måste avrundning, giltighet och
kopplade erbjudanden visas korrekta. En ny solver är inte en ny priskälla.

Reservera i ett första försök cirka 5 s för begäran/filter, upp till 40 s för
sökning och cirka 10 s för slutkontroll/save, med marginal till 60 s för kö/
transport/UI. Detta är en mätbar budgetfördelning, inte bevisade fasgränser.
En timeout utan färdig giltig lista är ett missat produktmål, inte PASS.
Resultatstatus ska skilja optimum bevisat, giltig bästa hittad, data blockerar,
bevisad omöjlighet och ofullständig sökning. Ingen ny prisregressionstolerans
eller automatisk lättnad av användarkrav beslutas här.

## 4. Butikstak upp till alla valda

Låt `S` vara det normaliserade valda butiksunderlaget och `K` användarens
tak: `1 <= K <= |S|`. ”Alla valda” betyder att taket inte begränsar urvalet
utöver S; det betyder inte obligatoriska inköp i varje butik. Vid tomt eller
otillgängligt underlag lämnas rätt besked, aldrig köp utanför S.

UI har i dag tak tre (`personal.js`), requestmodellen tak fyra (`plan.py`).
Att enbart höja dessa är otillräckligt: `_eligible_store_subsets` materialiserar
delmängder och personliga närings-/ekospår har ytterligare kombinationsloopar.
Den nya sökvägen får inte skapa alla delmängder upp till K. Modellera använda
butiker i samma begränsade sökning, med säker täcknings-/kostnadsgallring.
Specialfall utan kopplade villkor kan förenklas endast med visad ekvivalens.

Räkna inte separat om hela korgen för varje lägre butikstak före huvudsvaret.
Nuvarande `same_menu_comparisons` är kompletterande presentation och kan bli
ett separat, uttryckligt anrop efter färdig lista. Detsamma gäller bevisat
fristående förklaringar. Detta får inte skjuta upp obligatorisk audit,
verklig prissättning eller inköpslistans färdigställande.

Val, intent och den upplösta butiksmängden ska sparas och återläsas utan
tyst klippning. Befintliga sparade planer med heltalstak behåller betydelsen.
Butiksidentitet och priskanal får inte slås ihop bara för att namnen liknar
varandra. Visa datatäckning separat från användarens avsedda urval.

## 5. Ändring av tidigare arkitekturkrav

Detta avsnitt ersätter för **V2** kravet i 2026-10-23 års arkitekturbeslut
att en ny personlig kontext måste återspela alla historiska publiceringar
och köra oberoende legacy-spår per publicering före svar. V1 och dess tester
behåller sina kontrakt. V2 ska inte maskeras som en kvalificerad V1.

Publiceringshistorik används för proveniens, återkallelser, inkrementell
förberedelse och releasejämförelser. Den får inte multiplicera användarens
sökning med antalet historiska generationer. Den aktiva sökningen arbetar
mot ett aktuellt manifest, med tidigare fortfarande giltiga ägarvinnare som
kandidater efter ny checkout. Använd aldrig deras gamla kassasumma som intyg.

Pris-/kvalitetsskyddet är fortsatt noll oförklarade regressioner i jämförbara
acceptansfall mot legacy, V1 och tidigare giltig vinnare. Jämförelsen med
fulla äldre sökningar görs utanför det tidskritiska användaranropet.
Ett högre pris vid identiskt underlag och identiska krav förblir ett
releasehinder även om en kortare sökbudget förklarar skillnaden. Ändrade
priser eller krav är däremot inte en likvärdig regressionsjämförelse.
Små uttömmande orakelprov ska kontrollera exakt optimum och säkra gränser.
Samma prisgaranti för alla kalla körningar på alla biblioteksstorlekar följer
inte automatiskt av detta; påstå inte det. En tidsbegränsad ny sökning kan
missa en äldre billig vinnare, vilket är en risk att mäta och stoppa release
på, inte ett godkännande att höja priset.

Källproveniens, exakt artikel-/butiksscope, näring, allergier, ekobevis,
användarägarskap, LKG, aktuella kampanjer, revisionsregler och gemensam audit
är oförändrade krav. Ingen default eller produktionsversion ändras innan
en konkret avgränsad release har granskats; äldre ofullständig fullmatris
blir inte godkänd genom ett nytt policynamn.
