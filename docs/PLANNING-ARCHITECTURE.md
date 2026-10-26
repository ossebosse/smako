# Planeringsarkitektur för Smakos produktmål

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

Samma absoluta serverdeadline följer nya och personliga ändringsanrop genom
kö, async-jobb, tråd, inre loopar och transaktion. Timeout före commit rullar
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
[Sols aktuella uppdrag](CODEX-SOL-NEXT-20261026-BROAD-WEEK.md).

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
