# Nästa receptlager – testad lokal kandidat

Funktionen är integrerad i Smako på `feature/complete-recipe-layer`, byggd
från den fungerande kodbasen `402a5c9` ovanpå publika rättningen `74c9077`.
Slutruntime är **`17a9c1330dcc72ff9750a3fa680fa6982f7ed99b`**. Den är aktiverad
i isolerad testmiljö, inte i produktion. Ingen Git-push har gjorts.

## Vad användaren kan göra

Både det publika menyflödet och personlig planering har läget för genomarbetade
middagar. Det omfattar **Matkök och inspiration** (ett, flera eller alla sex
matkök), ingrediensförval inklusive 10–15 eller eget min/max, högsta uppskattade
tid, kost, fisk, uteslutningar, valfritt proteinmål och val mellan lämpliga
produktbyten och godkända receptvariationer. API:s stödda ingrediensgränser
är 3–20; bibliotekets nuvarande rätter har 12–14. Ett intervall utan lämpliga
recept ger ett uttryckligt stopp, inte automatiskt ändrade val.

Billigast, Balanserad och Varierad behåller sin ekonomiska betydelse. Portioner,
skafferi, butikstak, medlemskap, priskanaler och exakt/uppskattat köp följer
ordinarie PersonalPlanner, PriceUniverse, korgmotor och audit. Valen sparas
med planen och används även vid byte och uttrycklig omräkning.

Mobilanpassade kort visar komponentindelade mängder, numrerade steg med
beroenden, uppskattade tider, redskap, portioner, matkök, näring och separata
kvalitetsstatusar. Salt, peppar och vatten särredovisas. Unika ingredienser
räknas över hela rätten; skafferiet ändrar inköpsbehovet, inte receptantalet.
Inköpslistan visar produkt, verklig butik/kanal, hela paket, medlemsvillkor,
pant, uppskattningar och planerade rester. Betalning skiljs från använd mängd.

Byte väljer en kvalificerad annan grundrätt; byte och omräkning ger nya
oföränderliga revisioner. Smak, svårighetsgrad, portionsstorlek och faktisk
tid kan lämnas via befintlig feedbackväg, bundet till rätt receptversion.
Ingen betald modellgenerering sker när användaren trycker på menyknappen.

## Bibliotek, källor och kvalificering

**48 distinkta grundrätter, åtta per matkök, och 56 godkända variationer:**
104 konkreta receptversioner. 23 grundrätter är vegetariska och sex innehåller
fisk. Tidsuppskattningarna är 35–50 minuter för två personer. Bibliotekets
aktuella utgåva är 1.4.0, hash
`1c623aa7e4a8e8f9cde292807198c59d6f191f0dd3030462a254893995e7e90c`.
Oförändrade objekt behåller sina äldre versioner; tidigare bibliotek finns kvar.

Alla 104 prövades på slutimagen genom normal produkt-, mängd-, närings-,
inköps- och auditkontroll, utan handpatchade produkter eller tvingade kampanjer.
Provet tillät uppskattade köp och gav uttryckligt medgivande till uppskattad
näring. Resultaten är villkorade av detta pris- och källunderlag:

| Matkök | Grundrätter | Variationer | Kvalificerade versioner | Fungerande grundrätter | Fungerande original |
|---|---:|---:|---:|---:|---:|
| Grekiskt | 8 | 8 | 16/16 | 8/8 | 8/8 |
| Italienskt | 8 | 8 | 14/16 | 7/8 | 7/8 |
| Mexikanskt | 8 | 12 | 16/20 | 8/8 | 6/8 |
| Indiskt | 8 | 8 | 16/16 | 8/8 | 8/8 |
| Thailändskt | 8 | 8 | 16/16 | 8/8 | 8/8 |
| Svenskt | 8 | 12 | 16/20 | 8/8 | 6/8 |
| **Totalt** | **48** | **56** | **94/104** | **47/48** | **43/48** |

De tio första stoppen gäller kapris, kidneybönors mängdunderlag och mjölkens
näring på rätt mängdbasis. Godkända vita bön-, crème-fraîche- och vattenpanad-
variationer gör berörda grundrätter användbara, utom piccata. Exakta första
stopp och produktbyten finns i [FINAL-QUALIFICATION.md](FINAL-QUALIFICATION.md).
Ingen negativ kvalificering omtolkas som bevis för en för dyr eller omöjlig rätt.

Slutgranskningen hittade motstridiga energipar i en Coop-färs och ett rostbröd.
De är nu spärrade med bibehållen råproveniens; enheter rättas inte genom gissning.
Tolv receptversioner hittar en annan lämplig färs och fyra soppor hittar
källstyrkt färdigt matbröd. Receptmängderna är oförändrade. Tidigare 94/104 är
historik och ersätts av den nya körningen. Se [energiutredningen](ENERGY-DECLARATION-REVIEW.md).

| Dimension | Vad som faktiskt är verifierat |
|---|---|
| Receptkvalitet | Modellassisterad innehållsgranskning och maskinell kontroll av mängder, ingrediensräkning, stegberoenden och utrustning. **Ingen fysisk provlagning.** |
| Källtäckning | Hashbundna produktuppgifter; snäva referensmatchningar med käll-ID, version och hämtningstid. Saknade och motstridiga uppgifter behålls som stopp. |
| Köpbarhet | 94 receptkorgar med godkänd audit: 44 `VERIFIED`, 50 `VERIFIED_WITH_ESTIMATES`. |
| Näring | Samtliga 94 har `ESTIMATED`, med uttryckligt medgivande och godkänd beredningsmetod. Verifierat köp innebär inte verifierad näring. |
| Allergener | `NOT_REQUESTED` i de fria recepten. Separata negativa allergenprov visar spärrar; inget generellt allergensäkerhetsintyg lämnas. |
| Ekonomiskt val | Fullständigt kvalificerade hittade lösningar. Global optimalitet är inte bevisad; sökbudget och giltig lösning redovisas separat. |

Generiska SLV-referenser aktiveras inte av köpvalet uppskattat. Näring gäller
använd mängd per portion, med orundad proteinjämförelse. Inköpt, använd,
ätbar/avrunnen mängd och enhetsbasis hålls isär. Nya underlag kvalificeras på
nytt; cache förlänger inte kampanjer eller delar privata villkor mellan ägare.

## Sju kompletta menyer och samordnade inköp

Alla sju menyer kördes på exakt slutimage, sekventiellt utan annan
acceptansplanering. Fem middagar för två, 10–15 ingredienser, högst två
inköpsställen, Balanserad, uppskattat köp och uttrycklig näringsuppskattning.
De sex fria köksproven saknar extra protein-/tidsgräns; det blandade kräver
högst 40 minuter och minst 40 g protein. Alla valda produkter, mängder,
förpackningar, källreferenser och näringsvärden finns i [MENUS.md](MENUS.md)
och [evidence.json](evidence.json).

| Meny | Betala för inköp | Beräknad kostnad för använd mängd |
|---|---:|---:|
| Grekiskt | 682,23 kr | 418,77 kr |
| Italienskt | 651,94 kr | 360,42 kr |
| Mexikanskt | 673,87 kr | 390,82 kr |
| Indiskt | 647,95 kr | 346,42 kr |
| Thailändskt | 638,99 kr | 371,48 kr |
| Svenskt | 734,05 kr | 355,61 kr |
| Grekiskt/mexikanskt, 40 g/40 min | 738,17 kr | 444,93 kr |

Den blandade menyn använder 470 g ris i fyra rätter och köper en enda
kiloförpackning Långkornigt Ris för 21,95 kr hos Hemköp Lund Brunnshög.
Två rätters 66 ml citronjuice delar en 200-ml-förpackning för 8,99 kr hos
Coop Online Syd. Båda raderna är VERIFIED. Det är faktisk samordning av
inköp, inte summan av fem separat avrundade receptkorgar.

Den grekiska menyn valde Kycklinglårfilé, 450 g för 46,90 kr hos Coop Online
Syd, giltig offentlig kampanj 27 september–4 oktober på replaydatumet.
Blandmenyns gröna paprika, 200 g för cirka 11,79 kr, är ett uppskattat köp
hos Hemköp Lund Brunnshög och behåller VERIFIED_WITH_ESTIMATES. Ingen
kampanj eller uppskattad vara tvingades in som ett separat extraköp.

Planerade rester bokförs inte som faktiskt skafferi och något hypotetiskt
framtida restvärde dras inte av från det belopp användaren behöver betala.

## Prestanda på jämförbara villkor

Samma autentiska frysta underlag, 2 CPU och 3 GiB. Separata kalla processer,
ingen annan acceptansplanering under slutmätningen, inga appkällkodsmounts.
Python och alla 47 installerade beroendeversioner matchar baslinjen. Kall
betyder ny process; varm betyder ny beräkning i samma process, inte ett
redan färdigt jobb. Artefaktinläsning redovisas separat.

| Mått | Baslinje, äldre publikt | Slutimage, äldre publikt | Slutimage, komplett 40 g/40 min |
|---|---:|---:|---:|
| Kall generering, s | 328,424 | 161,047 | 105,721 |
| Varm generering, s | 2,166 | 2,264 | 95,976 |
| CPU kall, s | 328,147 | 160,922 | 105,622 |
| CPU varm, s | 2,164 | 2,263 | 95,892 |
| Processens högsta RSS, KiB | 1 281 328 | 1 195 272 | 1 595 548 |
| Artefaktinläsning, s (separat) | 14,584 | 14,445 | 14,294 |

Det äldre publika flödets kalla tid minskar med **50,96 procent**, så målet
om minst halvering nås i den jämförbara slutmätningen. Recept, ingredienser
och hela korgen är identiska med baslinjen, inklusive betalning 168,55 kr.
Varm tid är i praktiken oförändrad. Det nya lägets mätning gäller Billigast,
fem middagar för två, grekiskt/mexikanskt, 10–15 ingredienser, max 40 minuter,
minst 40 g protein och max två inköpsställen. Båda körningar ger samma
recept, ingredienser och korg på 738,17 kr. Den nya beräkningen tar alltså
fortfarande cirka 1,5–2 minuter även varm; korta jobb-/statusanrop behövs.

Kandidatgenerering, produktfakta, näring, förpackningar, veckosökning och
audit är separat instrumenterade. Spann kan överlappa och ska inte summeras
som oberoende delsteg. Exakta tider, räknare, CPU, RSS, råhashar och
baselinejämförelse finns i [PACKAGED-FINAL-PERFORMANCE.json](PACKAGED-FINAL-PERFORMANCE.json).
Profileringen styrde återanvändning av rena delberäkningar, förberedelsekontroll
och exakta jämförelsenycklar; tidigare A/B-rapporter visar samma fullständiga
plan vid oförändrade val. Kvalitetskrav, sökgränser och testunderlag sänktes inte.

## Verkliga HTTP- och webbläsarprov

Fem nya HTTP-slutprov kördes på runtime `17a9c133`, image `99bf3bfc…`,
2 CPU/3 GiB, utan annan tung acceptanslast. Alla slutfördes med väntat
resultat. Tiderna nedan är funktionella HTTP-tider, inte kalla benchmark:

| Fall | Resultat | Tid | Längsta start-POST / status-GET |
|---|---|---:|---:|
| Gammalt publikt anrop utan nya fält | Samma giltiga meny, 168,55 kr | 161,76 s | 5,322 / 0,762 s |
| Komplett 15/20-profil | 850,17 kr; 15 måltidsplatser, 20 portioner; ursprungliga 40/30/20-krav uppfyllda | 114,86 s | 0,151 / 1,596 s |
| Varierad, alla matkök | Fem olika grundrätter, 583,70 kr | 359,68 s | 0,105 / 2,199 s |
| Utvidgade köpval och butikstak | Tre giltiga prisjämförelser, ingen dyrare ersättning | 152,04 s totalt | 0,126 / 2,363 s |
| Tre samtidiga användare | Tre egna sparade planer, 682,23 kr vardera | 24,66 / 48,29 / 70,82 s | 0,221 / 1,085 s |

Det breda Varierad-valet tar alltså fortfarande **cirka sex minuter** och är
en konkret prestandabegränsning. Dess befintliga kostnadspåslag på högst
25 procent är oförändrat. Menyn innehöll palak tofu, röd linsdal,
svamp- och linsrisotto, majs- och bönsoppa med quesadilla samt kycklingbowl.

Med identiska övriga val kostade exakt köp med två butiker **796,15 kr**,
uppskattat köp med två **682,23 kr** och uppskattat köp med tre **665,62 kr**.
Exakt köp med en butik avslutades med HTTP 422 och svarskoden `CONFLICT`;
det är ett konkret rapporterat stopp, inte bevis för global omöjlighet.
Den äldre jämförelsen 777,15 kr använde en senare spärrad energideklaration
och är uttryckligen ersatt av slutprovet.

Dubbelstart återanvände samma ägares jobb. Annan ägares jobb/plan nekades,
sparad återläsning stämde och inga sessioner blandades. Tre samtidiga klienter
använde den befintliga kön med en aktiv beräkning; det påstås inte vara tre
parallella CPU-beräkningar. Högsta samplade minne var **2,073 GiB** och CPU
100,98 procent. Komplettprofilens minsta orundade protein var
40,17199999999999 / 35,5 / 22 g för middag/frukost/mellanmål.
Fulla val, produkter, korgar, stegövergångar, sökbudgetar och råfilhashar
finns i [HTTP-ACCEPTANCE.json](HTTP-ACCEPTANCE.json).

Tidigare breda autentiska HTTP-prov omfattar fyra personer, en/flera/alla
matkök, 12–13 ingredienser, produkter utan receptändring, vegetarisk kost,
angivet skafferi, medlemskap samt de fyra ursprungliga 15/20-profilerna med
oförändrade 40/30/20-krav. Protein och kostnad blandas inte ihop med köpstatus.
Negativa prov gäller för snäv tid, för få vegetariska grundrätter, motstridigt
fiskval, saknat allergen-/uteslutningsunderlag och fel kanal. Valen sänks inte
tyst. Fallen och deras exakta runtimeversioner finns i [HTTP-ACCEPTANCE.json](HTTP-ACCEPTANCE.json).

På exakt slutimage kördes också två nya verkliga knappflöden:

| Webbläsare och flöde | Generering | Receptbyte | Uttrycklig omräkning |
|---|---:|---:|---:|
| Chromium, mobil, personlig planering | 95,328 s | 17,719 s | 11,937 s |
| WebKit, desktop, publikt menyflöde | 86,593 s | 19,688 s | 12,265 s |

Båda skapade den kvalificerade blandmenyn för 738,17 kr, återanslöt efter
omladdning under generering och bevarade revision 1–3. Varje kort kontrollerades
i verklig DOM för sin egen receptversion och utrustning. Inga JavaScriptfel,
nätfel eller horisontella layoutöverskridanden observerades i dessa slutfall.
Mobilens verkliga budgettext matchade sparade sökresultat; den publika
budgettexten fångades inte av denna runner och redovisas inte som direkt
DOM-verifierad där.

Efter kontrollerad omstart på samma image återlästes revisionerna i samma
webbläsarsession. Samtliga **34 sparade testrevisioner** hade identiska
innehållshashar före/efter omstart; de omfattade även alla 28 äldre revisioner
från före imagebytet. Se [FINAL-PERSISTENCE.json](FINAL-PERSISTENCE.json).
Båda återkopplingsraderna verifierades dessutom genom skrivskyddad databasläsning
mot exakt sparad revision, recept-ID, version 1.4.0, innehållshash och betyg.
[UI-FEEDBACK-BINDING.json](UI-FEEDBACK-BINDING.json) dokumenterar två matchningar,
noll skrivningar och noll nya planjobb.

Fyra tidigare verkliga knappflöden täcker Chromium och WebKit på mobil och
desktop. De körde 99–151 sekunders generering, korta start-/statusanrop,
omladdning, nätavbrott, byte, omräkning och sparning. Ägarisolering provades
med nekad åtkomst från annan session. Flagga-av-omstart bevarade revisioner
med identiska innehållshashar. Dessa versioner och senare prov blandas inte
samman; [UI-ACCEPTANCE.json](UI-ACCEPTANCE.json) binder varje resultat till sin build.
DOM och verklig layout är kontrollerade. **Ingen fysisk iPhone har provats.**
Feedbackinmatningen är syntetisk acceptansdata, inte faktiska smakbetyg.

Den fullständiga nätspärrade sviten på exakt slutruntime passerade **3887 tester,
0 fel och 0 överhoppade**, på 2042.099 sekunder. Runtimefilerna hölls fasta
under körningen. Inga spärrade externa nätförsök eller äldre källkopieåtkomster
registrerades. [TESTS.json](TESTS.json) binder XML- och åtkomstloggar till
exakta hashvärden; tidigare kontrollversioner redovisas som historik.

Ruff på alla ändrade Python-filer, compileall och pip check passerar.
Utgångna kampanjer, fel butik/kanal, okänd pant, oklar variant, oförenlig
råvaruform, saknad/motstridig näring samt cache- och privat revisionsisolering
har separata reproducerbara regressioner. [NEGATIVE-CACHE-PERSISTENCE.json](NEGATIVE-CACHE-PERSISTENCE.json)
skiljer dessa kontrollerade tester från autentiska marknadsresultat.

## Underlag, driftgräns och kvarvarande begränsningar

Publicerat underlag fryst **2026-10-02 15:09:36 UTC**: 44 185 produkter,
fyra katalogsnapshots, 2 232 hashverifierade råfiler. Universe
`price-universe:8ecd0659a7e69b8eb007e383ae4f9686a3d1a4f24570b0dd9b72c9c875653bad`,
artefakt-SHA `1335cbb6680237f5826912f19a1d5c348476089ec3091126cb073c4cc5a643e0`.
Beloppen är **historiska replayresultat**, inga prisutfästelser för nya köp.
Isolerad testlagring innehåller nya testsessioner; privat produktionsdata
kopierades inte. Råfiler och stora testartefakter ligger utanför Git.

Separat skrivskyddad kontroll **2026-10-03 10:12:15 UTC**: produktionens
`/ready` svarade 200/ready med build `74c9077001b3084317f36630fd38ce48e4663473`.
Ingen källinsamling startades. Aktiva prisinsamlingar, Windows-relä, scheman,
femkällorspolicy, kommunomfattning och 36/48-timmarsgränser är orörda.
[PACKAGE-BOUNDARIES.md](PACKAGE-BOUNDARIES.md) redovisar den oberoende
kontrollen av paketmanifest, driftgränser och standardlägets avstängda flagga.

Konkreta begränsningar är de tio dokumenterade källstoppen, saknad fysisk
provlagning och verkligt uppmätta tillagningstider, samt de redovisade
söktiderna. Hårda allergen-/uteslutningskrav kan kräva mer fullständigt
källunderlag. En avslutad sökbudget bevisar inte omöjlighet eller globalt
optimum. Oberoende fungerande rätter och användarflöden är tillgängliga.

## Exakt kandidat och kontrollerad aktivering

- Runtime: `17a9c1330dcc72ff9750a3fa680fa6982f7ed99b`.
- Paket: `smako-server-17a9c1330dcc.zip`, 2 739 005 byte,
  SHA-256 `d3327b9137d4310707118b5272bc826ed0403ebd6d0c0ab935bb1196efee060a`.
- Image-ID: `sha256:99bf3bfcb4f395ec1a06df23649e0241903d52bb5bba40ca4336abbd2bbecc35`.
- Paketet ligger i `.local/releases/complete-recipes-20261002/`.
  [Manifest](release.json) och [imageverifiering](IMAGE-17A-VERIFICATION.md).

[ACTIVATION.md](ACTIVATION.md) beskriver hashkontroll, app-only-konfigjämförelse,
flagga av först, explicit aktivering och återgång genom flagga av i samma
nya version. Planrevisioner och databaser ska bevaras, aldrig ersättas med
äldre kopior. `COMPLETE_RECIPES_ENABLED=false` är standard. Testlaunchern,
replayklockan och reläarkivet ska inte användas för denna produktionsaktivering.
Efterföljande dokumentations- och testskriptcommits ändrar inte den låsta
runtimen. Ingen produktionsaktivering eller Git-push ingår i leveransen.
