# Smako – verifierat femmiddagsfall, 12 september 2026

Femmiddagsmålet **PASSERAR** i fryst prov, serverimage utan nätverk och verklig HTTPS i Chromium/WebKit. Release `personal-v2-five-dinners-20260912c`, appkod `e626ac0`. Live: https://beta.smako.nu/personal.

Före ändring lästes AGENTS.md, docs/HANDOFF.md, föregående fullrapport och R1–R9-matris. Aktiv release `personal-v2-dinners-20260911c` och appkod `7b15c05` bekräftades; de 13 ändrade appfilernas basversioner kontrollerades dessutom före staging. Ändringen följer befintlig generator, MenuOptimizer, produktkvalificering och gemensam korg.

## Primärt acceptansfall B5

5 middagar × 4 portioner, Balanserad, högst 2 butiker, explicit ”Tillåt spårbara näringsuppskattningar” på, minst 20 g protein och högst 800 kcal per portion. Verkliga paket kostar **677,43 kr**. Samtliga fem middagar är `ESTIMATED`; inga uppmätta produktvärden eller tillagade vikter påstås.

| Middag | Protein g/portion | kcal/portion | Grund |
|---|---:|---:|---|
| Stekt torsk med äggnudlar och vitkål | 39,94 | 471,87 | ESTIMATED |
| Torsk- och kålsoppa med äggnudlar | 39,99 | 472,22 | ESTIMATED |
| Kokt kyckling med ris och morötter | 41,97 | 492,79 | ESTIMATED |
| Couscoussallad med tofu och tomat | 21,34 | 420,80 | ESTIMATED |
| Stekt lax med ris och morötter | 37,54 | 613,78 | ESTIMATED |

Full precision, produkt-ID:n, pris- och näringskällor, instruktioner, fälthashar och begäran finns i [Chromium HTTPS](five-dinners-20260912/https/chromium.json), [WebKit HTTPS](five-dinners-20260912/https/webkit.json) och [fryst acceptans](five-dinners-20260912/verified-frozen.json).

| Vara | Butik | Hela paket | Köpt g | Använt g | Rest g | Full kostnad kr |
|---|---|---:|---:|---:|---:|---:|
| Torskfilébitar i block | Coop Online Syd | 3 × 400 g | 1200 | 1200 | 0 | 192,93 |
| Couscous Eko | Willys Lund | 1 × 500 g | 500 | 320 | 180 | 18,83 |
| Kycklingfilé 2-delad Frysta | Willys Lund | 1 × 800 g | 800 | 600 | 200 | 75,61 |
| Laxfilé i Bit Refreshed | Willys Lund | 2 × 400 g | 800 | 600 | 200 | 189,08 |
| Morötter Klass 1 | Willys Lund | 2 × 1000 g | 2000 | 1200 | 800 | 19,80 |
| Äggnudlar | Willys Lund | 3 × 250 g | 750 | 640 | 110 | 28,08 |
| Långkornigt Ris | Willys Lund | 1 × 1000 g | 1000 | 640 | 360 | 19,90 |
| Naturell Tofu Fast Vegansk | Willys Lund | 3 × 200 g | 600 | 600 | 0 | 35,70 |
| Tomat Kumato Klass 1 | Willys Lund | 2 × 300 g | 600 | 600 | 0 | 55,80 |
| Vitkål Strimlad Klass 1 | Willys Lund | 3 × 400 g | 1200 | 1200 | 0 | 41,70 |

Coop Online Syd är `ONLINE_FULFILLMENT`/`online_price` (`own:coop:730400`), inte fysisk Lund-hyllprisdata. Willys Lund är `online_store`. Korgen består av verkliga ordinarie paketpriser utan medlemskrav. Ingen rest räknas som uppäten näring. Näring utgår från varje recepts använda ätbara mängd, inte köpt förpackningsmängd.

## Två nya kandidater och deras beredning

1. **Stekt torsk med äggnudlar och vitkål:** 150 g rå ätbar torsk, 80 g torra äggnudlar och 150 g ätbar vitkål per portion. Torsken steks varsamt i belagd panna utan extra fett och utan kvarvarande steksky; den kokas inte först. Nudlar och vitkål kokas som i befintlig dokumenterad kedja. Torskpannan ger en annan proteinkärna än den befintliga laxpannan.
2. **Couscoussallad med tofu och tomat:** 150 g naturell fast tofu, 80 g torr vanlig durumcouscous och 150 g färsk rå tomat per portion. Couscous får svälla under lock i kokande vatten enligt förpackningen; allt livsmedel och absorberat vatten serveras. Tofu och tomat vänds i utan stekning, pressning eller avrinning. Detta öppnar tredje kolhydraten couscous, familjen grynsallad och metoden `rehydrate_and_assemble`.

Familjerna utgår från råvaror och verkliga instruktioner. Balanserads högst två av samma kolhydrat/tillagningsmetod och parvis kulinarisk likhet <0,85 är oförändrade. Strukturellt test visar att ingen kombination av fem bland de tidigare åtta granskade kandidaterna är giltig. De båda gamla laxpannorna är fortfarande för lika trots ris/nudel-byte. Två tillägg räcker för den verifierade femmenyn; sökbredden är oförändrad.

### Källstöd och mängdkedja

30 explicita SLV-mappningar behålls. Dokumenterade tillagningskopplingar ökar från 9 till 10 genom [SLV 1337 Torsk stekt](https://dataportal.livsmedelsverket.se/livsmedel/api/v1/livsmedel/1337). Underlaget kopplar 550 g rå torsk (1246) till dokumenterad slutbatch 396,875 g inklusive 2,8 g salt. För protein/fett/kolhydrater/kcal har salt noll bidrag. Omräkning är `cooked_per100g × final_batch_g / raw_input_g`; källans vattenfaktor multipliceras inte med totalvikten. Kvalificerad produktdeklaration prioriteras och justeras med dokumenterad rå/tillagad relation där sådan behövs. Det är en spårbar uppskattning, inte mätning av användarens fisk.

Couscous använder en separat snävt granskad summering av ätbar insats, märkt `REVIEWED_ESTIMATE_NOT_MEASURED_RETENTION`. [Sevan](https://sevan.se/foretag/produkter/skafferi/bulgur-gryn/couscous-eko-5kg) stöder förångbehandlad vanlig durumcouscous; [Tipiak](https://www.tipiak.com/node/3338) stöder svällning under lock; [Yipin](https://yipin.se/produkter/naturell-tofu/) stöder naturell fast tofu kall i sallad. [Livsmedelsverket](https://www.livsmedelsverket.se/livsmedel-och-innehall/tillagning-forvaring-hallbarhet/tillagning/hur-paverkas-maten-vid-tillagning/) ger kvalitativt stöd om makron och vattenkoncentration. Inga märkesspecifika näringsvärden, priser, ekoegenskaper, vattenkvoter eller exakta retentionsfaktorer överförs. Exakt omfattning och begränsningar finns i [granskningsunderlaget](../backend/app/data/nutrition/couscous-assembly-20260912.json).

Köpt mängd, receptets använda ätbara mängd och förpackningsrest redovisas separat. `used_edible_quantity` är uppmätt insats; `cooked_quantity_g` är null. Krav på faktisk tillagad portionsvikt förblir **DATA_BLOCKED**. Potatis/pasta/hasselback granskades men fick inga nya aktiverade kopplingar eftersom full kedja saknades. Ingen generell recept- eller insamlingsmotor byggdes.

## Produktidentitet och datatäckning

Vanlig durumcouscous, naturell fast tofu och rå tomat kräver uttrycklig formkvalificering även om en produkt har full deklaration. Pärlcouscous, fullkorn/glutenfri/smaksatt couscous, silkes-/lagtofu, konserverade/skalade/hela/krossade/passerade/torkade tomater blockeras för denna kedja. Tester inkluderar billiga felprodukter med avsiktligt bättre metadata. Mjölk-/ostavgränsning och det strikta produktläget behålls.

Vald färsk Tomat Kumato Klass 1 kostar 2 × 300 g = 55,80 kr för 600 g behov. Vanliga kvalificerade alternativ finns med samma generiska beredningsgrund: Coop cocktailtomater 3 × 250 g = 56,64 kr, Willys cocktail 3 × 250 g = 59,70 kr och Willys plommon 2 × 500 g = 59,80 kr. Valet beror på hela paketkostnaden, inte ett undantag för bättre metadata. [Produktgranskningen](five-dinners-20260912/tomato-qualification.json) visar accepterade och avvisade alternativ.

Ingen ny accepterad Coop-produktfakta eller retailerinsamling ingår. På den tidigare fasta 449-poolen är underlaget oförändrat **83/46/78** deklarationer/eko/full näring. Referensuppskattningar är inga nya produktdeklarationer. Den oberoende ordinarie refreshen har gett dagens universum 36 535 produkter (Coop 11 404, Hemköp 4 985, ICA 1 885, Willys 18 261); detta ska inte blandas ihop med fasta 449-poolen eller API:ts befintliga urvalsantal 2 091.

## Blockeringsfördelning

UI och API visar rå pool, första kandidatavslag per steg, godkända enskilda kandidater och separata menygrenar per sökdjup. Detta undviker dubbelräkning. Noll avslag betyder inte att ett senare otestat steg har passerat. Sökningen är begränsad och ett sökfel är inte ett bevis för global omöjlighet.

| Kandidatsteg | Gammal pool, fem misslyckas | Ny pool, B5 passerar |
|---|---:|---:|
| Rå receptpool | 88 | 90 |
| Policy/smak – första avslag | 0 | 0 |
| Näringskrav – första avslag | 0 | 0 |
| Eko – första avslag | 0 | 0 |
| Butikstak – första avslag | 0 | 0 |
| Variationskrav – första avslag | 0 | 0 |
| Tillagning/beredning – första avslag | 80 | 80 |
| Produktkvalificering – första avslag | 0 | 0 |
| Pris/korg – första avslag | 0 | 0 |
| Godkända enskilt | 8 | 10 |
| Ej enskilt utvärderade | 0 | 0 |

Alltså: 80 vanliga genererade kandidater saknar granskad beredning. De åtta gamla granskade kandidaterna har användbart data men räcker inte till fem med oförändrad variation. Det är både beredningstäckning i den större poolen och otillräcklig faktisk variation bland de kvalificerade kandidaterna.

| Fall | Djup | Menyförslag | Variation avvisar | Övriga utvärderingsavslag | Prissatta | Behållna | Sökbredd sållar |
|---|---:|---:|---:|---:|---:|---:|---:|
| Gammal pool | 1 | 8 | 0 | 0 | 8 | 8 | 0 |
| Gammal pool | 2 | 64 | 20 | 0 | 44 | 8 | 36 |
| Gammal pool | 3 | 64 | 48 | 0 | 16 | 8 | 8 |
| Gammal pool | 4 | 64 | 64 | 0 | 0 | 0 | 0 |
| Ny pool B5 | 1 | 10 | 0 | 0 | 10 | 8 | 2 |
| Ny pool B5 | 2 | 80 | 19 | 0 | 61 | 8 | 53 |
| Ny pool B5 | 3 | 80 | 36 | 0 | 44 | 8 | 36 |
| Ny pool B5 | 4 | 80 | 58 | 0 | 22 | 8 | 14 |
| Ny pool B5 | 5 | 80 | 72 | 0 | 8 | 8 | 0 |
| Max en rätt/metod | 1 | 10 | 0 | 0 | 10 | 8 | 2 |
| Max en rätt/metod | 2 | 80 | 37 | 0 | 43 | 8 | 35 |
| Max en rätt/metod | 3 | 80 | 60 | 0 | 20 | 8 | 12 |
| Max en rätt/metod | 4 | 80 | 80 | 0 | 0 | 0 | 0 |

Samtliga övriga avvisningssteg är 0 i ovanstående sökgrenar; JSON visar varje steg separat. För hårdare max en rätt/metod blir fem fortfarande SEARCH_BLOCKED, med full fördelning. HTTPS-provet med minsta tillagad vikt 100 g blir DATA_BLOCKED: rå pool 90, beredning 90 avvisade, övriga steg 0, inga godkända enskilda kandidater. Felpanelen visar samma fördelning i båda webbläsarna.

## Acceptans och regression

| Test | Verifierat resultat |
|---|---|
| A Tre middagar | Exakt tidigare meny: kokt kyckling/ris/morot, kycklingsoppa/äggnudlar/vitkål, stekt lax/ris/morot. 426,52 kr, samma ≥20 g/≤800 kcal/max 2. Fryst, image utan nätverk och HTTPS i båda motorerna. |
| B Fem middagar | Menyn ovan 677,43 kr. Fryst, aktuell serverdata utan nätverk och Chromium/WebKit HTTPS. |
| C Skafferi | 500 g bekräftat torrt ris, 500 g allokerat över femmenyn, faktiskt saldo 500 g före och efter generering. Fryst och båda HTTPS-motorerna. Annan meny 688,73 kr; kostnadsskillnaden är inte en jämförelse med samma meny. |
| D Strikt produktbaserat | Explicit uppskattningsval av. Tidigare A2, två portioner ostsmörgås, 30,38 kr, VERIFIED. Inga generiska uppskattningar. Fryst, image och båda HTTPS-motorerna. |
| E Semantisk produktmatchning | 11 negativa formfall med bättre metadata samt vanlig färsk tomat mot billig felaktig konserv. Kvalificerade vardagsalternativ i riktiga korgen; ost/getmjölksregression ingår. |
| F Inga externa konsumentanrop | Socketanslutningar förbjudna i fryst acceptans/test. Imageprovet kör med Docker --network none och verkliga monterade källdata. Planresultat live_chain_requests = 0 i alla HTTPS-fall. |
| Eko-regression | Samma tidigare tre middagar med eko ≥25 %: 480,05 kr, faktisk källstödd andel 50,54 %. Fryst, image och båda HTTPS-motorerna. |

250 distinkta berörda testfall: full körning 249 godkända, sista fokuserade körningen 89 godkända efter ytterligare ett negativt produktformfall (union 250, inte 338). Ruff, Python 3.12 compileall, JavaScript syntax och git diff --check passerar. Ingen ny golden. [regression.xml](five-dinners-20260912/regression.xml), [final-focused.xml](five-dinners-20260912/final-focused.xml).

Chromium/WebKit: riktiga mobilformulär 390 px, standardavstängt opt-in och sparad inställning, näringsvisning, blockeringspanel, skafferi, strikt/eko/tremiddag via separata gäst-API:n, inga JS-fel, inget horisontellt överflöd med 24 px grundtext. [Resultat](five-dinners-20260912/https/results.json) och skärmbilder i samma katalog. Fysisk iPhone är inte testad.

Oförändrad äldre basmeny kostar 244,49 kr; uppmätt kall 14,791 s/varm 0,722 s mot föregående 14,477/0,717 s. Enskilda mätningar, ingen påstådd prestandavinst. [benchmark.json](five-dinners-20260912/benchmark.json).

## Drift och återställning

Aktiv prisversion `price-universe:11e58c7ce1ae5efaf8da60d87c3f67e29adc43bde8b1fb321f7351d450715a46`, byggd 2026-09-12 02:07:35 UTC. Det frysta regressionsexemplet använder `price-universe:9ab6c58a4934c0a253e037c724d58fdcc8c84b484d26a87d2027be087e17b929`. Båda ger B5 677,43 kr. Driftens freshnessgränser är oförändrade; postdeploy visade FRESH och cirka 33,5 timmar äldsta användbara pris.

Näringsreferensversion `slv-component-input-v2:7d6f1acbb10e93269d534adedf5bde2e0a824811f5ed5b7e85c75644346d9a12`; policy `personal-policy-v2-4`. Releasearkiv SHA-256 `8b99b8952dfcb7c6e5189104ae3a0f6756bab596e523cf2abe367a158960942d`. Aktiv image `sha256:3b427220f5a6e589c43f840191bfb54086dcc4019be65c341595b7290b4e3193`. [Källhashar](five-dinners-20260912/source-hashes.json) bekräftar att samtliga 13 ändrade appfiler matchar både releasekatalog och körande container.

Backup `20260912T053012Z` klar före aktivering. Gemensamt driftlås användes vid appbyte; 130 äldre revisioner hashbevarade, 140 revisioner efter HTTPS-proven. Scheduler och prismanifest oförändrade under operationen, databasens integrity_check ok. [Driftevidens](five-dinners-20260912/deployment.json).
Rollbackimage `personal-v2-dinners-20260911c-rollback` läser de nya sparade modellerna och returnerar 503 för skrivning. Offlineprov passerade utan nätverk; ingen databasrestore eller radering av användardata. [Rollbackprov](five-dinners-20260912/rollback.json).

## Kvarstående avgränsningar

Femmiddagsmålet är uppfyllt för det verifierade fallet; det innebär inte obegränsad variationspool. R3/R6/R7/R8 förblir IMPLEMENTED_AND_VERIFIED och R1/R2/R4/R5/R9 PARTIAL. Tillagad vikt och fullständiga allergener är fortsatt DATA_BLOCKED. Ingen förändring av Willys-task/relay, OIDC, kallprestandaarkitektur, ICA OWN, källinsamling, Coop-scope eller freshness-/kvalitetsgrindar. Nästa datasteg är ytterligare komplett beredningskedja och godkänt Coop-detaljschema.

Tidiga utforskande resultat och lokalwebbläsarprov före sista tomatformskorrigeringen är uttryckligen markerade som underkända/ersatta. De utgör ingen acceptans. Första runtime-provet saknade testmiljöns GROCERY_DATABASE_URL/GROCERY_RAW_SNAPSHOT_ROOT och är markerat INVALID_HARNESS; det korrigerade runtime.json använder verkliga sparade produktfakta utan nätverk.
