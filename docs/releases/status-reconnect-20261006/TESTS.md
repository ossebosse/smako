# Slutprov för status och återanslutning

Runtime **dd12cc80e98c79aa32c159223c8bc1ceeaaa7580**, image **sha256:c8362751b13a6e649beadad2a3c27b9b5df8bfd1e2fa177ff68e01e1d7b8b2c7**. Alla nedanstående riktiga menyprov körde paketerad appkod, ordinarie planner, audit och PlanStore. Inga källkodsmounts användes. Isolerad historisk replay: samma frysta PriceUniverse med SHA-256 `f82d66103e830b82b7d919fe847fd5b3ef85c5e323e0a2133c338f064dfb8768`, tidigare faktaunderlag och prisklocka 4 oktober. Den tidigare kontrollen av artefakten och dess 2 233 råfiler återanvänds eftersom filerna är oförändrade och inputs monteras skrivskyddat. Testernas verkliga UTC-tid och monotona durationer är separata från prisklockan.

## Kodregressioner och testbedömning

**10/10** syntetiska transportregressioner, **41/41** berörda backendprov och **8/8** syntetiska frontendkombinationer (Chromium/WebKit, publik/personlig, mobil/desktop) passerade. Ruff, compileall och JavaScript-syntaxkontroll passerade. [RECOVERY.json](RECOVERY.json) binder råloggarna till runtime. Syntetiska svar används för transport-/schema-/layoutregressioner och räknas inte som faktiska menykvalificeringar.

Samma beforeunload-regression fallerar på cdc2809 och passerar på dd12cc8: den tidigare läsaren fortsatte till ett nytt pollanrop, den nya avbryter timern och behåller samma jobb. Startkapplöpningsprovet fallerar på klienten före 15f2883 och passerar efter dess begränsade återfinningsfrist. Ett separat verkligt backendfel reproducerades i den berörda sviten: återkastning av ett behållet task-HTTPException kunde få dess traceback-rensning att påverka en aktiv läsare. Pollningen undersöker nu task.exception och skapar ett nytt HTTPException; upprepade slutliga fel-GET bevarar status, body och felkod. Detta fel gäller misslyckade backendjobb och är inte en belagd förklaring till de historiska framgångsrika jobben A/B.

Fellyssnare för pageerror/unhandledrejection finns kvar. Inga breda undantag för WebKit, statusadresser, feltext eller socketfel har lagts till. **Alla oväntade sidfel ger FAIL.** Råa navigations- och injicerade nätavbrott finns i rapporterna och betyder inte att inga nätfel inträffade. [HISTORY.json](HISTORY.json) bevarar sju tidigare underkända försök, inklusive det nya cdc2809-felet; de har inte omklassificerats till PASS.

## Riktiga knappflöden på slutimagen

Alla 11 resor dubbelklickar riktiga knappar, kräver en POST, samma ägarbundna jobb, exakt en instrumenterad plannerberäkning, korrekt DOM och full sparad GET. Den faktiska laddade complete-recipes.js matchar manifestets SHA-256 `17311d27a3a50ec9e75415316ca8cc90d10c94ac85380b36a75a3541d1b7114e`. Minst tre riktade navigations-/återanslutningsresor per webbläsare passerade, med både publikt och personligt flöde och mobil vy 390 × 844.

| Fall (mobil vy) | Klick till resultat | Utfall |
| --- | ---: | --- |
| chromium-personal-free-skip-invalid-body-offline0-reload3 | 67,14 s | PASS |
| chromium-personal-free-skip-timeout-offline0-reload3 | 65,17 s | PASS |
| chromium-public-free-skip-long-outage-offline0-reload3 | 128,44 s | PASS |
| chromium-public-free-skip-none-offline0-reload999 | 67,81 s | PASS |
| chromium-public-free-skip-none-offline10-reload3 | 66,98 s | PASS |
| chromium-public-more-rollback-reset-offline0-reload3 | 67,95 s | PASS |
| webkit-personal-each-full-delayed-reload-offline0-reload3 | 46,11 s | PASS |
| webkit-personal-free-skip-away-offline0-reload3 | 69,77 s | PASS |
| webkit-personal-free-skip-hidden-offline0-reload3 | 71,30 s | PASS |
| webkit-public-free-skip-lost-start-race-offline0-reload3 | 77,50 s | PASS |
| webkit-public-free-skip-none-offline20-reload45 | 86,95 s | PASS |

WebKit each/full och Chromium more/rollback omfattar uttryckliga variationskrav, receptbyte, omräkning, tre revisions-GET och faktisk appomstart. Samma nya image med flaggan av läste alla nya revisioner, och **11 äldre** revisioner lästes med ursprungliga testägare och identiska kritiska hashvärden. Dessutom läste paketerad ny image, både flagga på och av, **22 revisioner från 82de** från en konsistent separat kopia. Det är ett modell-/lagringsprov; HTTP-ägarisolering prövas separat. Det äldre menyflödet passerade genom riktig publik knapp, omladdning och sparad GET med flaggan av. Dess första försök föll i testverktygets summering av `personal=null`; appen hade redan lämnat ett riktigt resultat. Verktyget rättades utan appändring.

Kontrollerade fel påverkar endast transport/livscykel: accepterad POST följd av förlorat startsvar; en uttryckligt injicerad tidig återfinnings-404; anslutningsreset; fördröjt statusanrop vid omladdning; 20 s timeout; kort offline före/efter slutförande; åtta statusavbrott följda av manuell återupptagning; HTML-svar som gav schemafel och sedan manuell läsning av samma jobb. HTML-provet vidarebefordrar det riktiga serveranropet; det ersätter inte en meny. Native goto/back/forward/back prövas. Hidden-provet ändrar document.hidden och skickar visibilitychange: **simulering, inte ett operativsystemsombyte**. Mobil WebKit är **inte fysisk iPhone-testning**.

Sena svar efter ersatt läsare eller sidavslut och sena konsumtionssvar prövas i de syntetiska transportregressionerna; de är inte två parallellt färdigmockade menyer i end-to-end-provet. Verkliga fördröjda statusanrop, dubbelklick och navigationsåterkomst prövas mot riktiga jobb. Negativa transportprov täcker 401/403/404/422, 429/Retry-After, tillfälliga 502/503/504, slutlig jobb-503, JSON/HTML/schemafel och bevarad referens efter retrygräns. Riktiga separata ägare får 404/403. Både gästcookieborttagning och webbläsarverkställd utgång av gästcookies gav korrekt terminalt besked; återställning av den ursprungliga testcookien i testminnet hämtade samma färdiga jobb. Det senare provet satte cookieutgång i det förflutna och lät webbläsaren sluta skicka cookien. Det är inte ett prov av utgången signerad kontoinloggning. Faktisk omstart under pågående jobb gav saknat processminnesjobb och begripligt slutläge utan ny POST; färdiga revisioners överlevnad prövades i fullresorna.

Det kompletterande cookieutgångsprovets första verktygsförsök stoppades av ett syntaxfel före någon startbegäran (be73f21). Verktyget rättades i 6e045b6, Ruff/compileall passerade och det riktiga provet kördes därefter mot oförändrad dd12cc8-image. Detta är en testverktygsrättning, inte en appfix. Slutimagen bevarade serverloggar saknar ERROR/Traceback/ASGI-exception i den kontrollerade omfattningen; hashreferenser finns i RECOVERY.json.

## Tre ägare, kö och resurser

Två separata körningar: ostörd och ett kontrollerat statusavbrott för ägare 1. Alla formulär förbereddes, ägare 1 accepterades först, sedan klickade två andra ägare medan första jobbet beräknades. I avbrottsprovet laddade båda köande klienter om, med ändrad dokumentreferens. Varje ägare behöll ett jobb, en beräkning och rätt fullständigt slutresultat. Främmande jobb gav 404 och främmande planer 403.

| Körning/ägare | Serverkö | Beräkning | Klick till visat resultat |
| --- | ---: | ---: | ---: |
| Ostört · ägare 1 | 0,00 s | 57,90 s | 63,67 s |
| Ostört · ägare 2 | 58,08 s | 59,30 s | 124,36 s |
| Ostört · ägare 3 | 118,63 s | 59,11 s | 183,89 s |
| Avbrott · ägare 1 | 0,00 s | 62,77 s | 70,08 s |
| Avbrott · ägare 2 | 62,84 s | 59,44 s | 129,09 s |
| Avbrott · ägare 3 | 123,74 s | 56,96 s | 188,80 s |

[CONCURRENCY.json](CONCURRENCY.json) innehåller statuslatens, råa klienthändelser och separata Docker-minnessampel. Högsta registrerade serverprocess-RSS i dessa beräkningsposter var **2,467,048 KiB** (ru_maxrss, processens topp sedan start). Docker-sampel är intervallobservationer, inte en garanterad fångst av varje momentan topp. Två CPU, 3 GiB och en tung admissionplats med fyra köplatser behölls; ingen extra plannerprocess infördes. [PACKAGE.json](PACKAGE.json) verifierar image, alla kopierade runtimefiler, mounts, resursgränser och identiska Python-, biblioteks- och OS-paketversioner mot 82de.

Den ostörda enskilda huvudresan tog **67,81 s** från klick; serverkö **0,00 s**, faktisk beräkning **60,11 s** och minnesrensning **1,07 s**. Det är ett enstaka prov, inte en ny kall/varm median eller en kausalt isolerad statusoverheadmätning. **60-sekundersmålet är inte uppnått.** Avbrottsfallens extra tid redovisas och räknas inte som långsammare matsökning. Statusbudgeten och merkostnaden i extra begränsade GET finns i [TRANSPORT.md](TRANSPORT.md); matmotorn är oförändrad.

## Resultatkompatibilitet och återanvända bevis

[COMPATIBILITY.json](COMPATIBILITY.json) jämför hela begäran och allt mat-/köpinnehåll, även efter byte och omräkning, med 82de. Recept, versioner, råmängder, inköpsrader, kanaler, användningskostnad, näring, allergenstatus, audit och variation är identiska. Nya plan-ID, build-ID, skapandetider, intern timing och ordning i en medlemsmängd normaliseras. Efter sparning skiljer privat cacheidentitet eftersom den inkluderar nya privata state-ID/reservationsnycklar; båda hashvärdena finns kvar i jämförelsen. Första menyernas cacheidentitet är identisk.

Den föregående kandidatens fulla mat-/förpacknings-/variationssvit, äldre 15/20-profiler med 40/30/20-krav och kalla/varma mätningar återanvänds endast för oförändrade kod-/dataområden. De kallas inte nykörda. Ny binär som läser gamla data och flagga-av på samma image är kvalificerade här. **Äldre binär som läser nya revisioner är inte kvalificerad**; ingen äldre databas har återställts över senare arbete.
