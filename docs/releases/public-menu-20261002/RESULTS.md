# Publikt veckomenyflöde efter Lund-aktiveringen

Status: rättat och driftsatt. Publik knappacceptans godkänd för Balanserad, Billigast och ren session; fyra separata 15/20-regressioner godkända. Slutlig kontroll 2 oktober 2026 cirka 09:41 svensk tid.

## Utgångspunkt och bevis

Arbetet utgår från [aktiveringsprotokollet](../lund-20260929/ACTIVATION-LIVE-20261001.md), faktisk `/opt/smako/current` och den körande bilden, inte en ny Lund-aktivering. Vid reproduktion var webbapp och scheduler byggda från `08c137475d9ca96a6ef7673245a639c8c5c9e922`, bild `sha256:d8a166fa7ee162cd0570f9d8089ff800e00d9c949ac3c674e387c5fff1538dd7`.

Publicerade index.html, app.js och personal.js matchade Git-blobbarna i den driftsatta releasen. Skillnader mot Windows arbetsfiler berodde på CRLF. Service worker v10 använder nätverksprioritet för skalet och cachar inte meny-API:t. Samma ursprung, `https://beta.smako.nu`, användes för API-anropet. Ingen belagd cache- eller autentiseringsorsak.

`/health` och `/ready` gav 200. Aktivt prisunderlag var `price-universe:fb61c78432a4e80a32129d1cf188a5b2a1a20fc7294687ba533d6bced7bf185a`, byggt 2026-10-01 22:37:18 UTC, med 33 användbara kontexter och 44 092 råprodukter. Äldsta **användbara** underlag var 23,91 h, status fresh, alla fem obligatoriska källkontexter användbara. Det äldre historiska underlaget i statusfältet `oldest_price_age_hours` (65,215 h) är inte samma sak som aktuellt användbart underlag. Åldersgränserna 36/48 h har inte ändrats.

Readiness redovisade samtidigt `requires_attention: true`. Den flaggan tar även hänsyn till äldre kontextåldrar; den ska inte döljas eller likställas med att alla användbara priser är inaktuella. Den befintliga varningen och åldersgränserna bevarades.

## Verklig knappreproduktion före ändring

Separata Chromium-sessioner med egen lagring och identitet; användarens sparade profil ändrades inte. Desktop 1280×900 och mobilvy 390×844. Mobilvy är en webbläsarviewport, **inte ett faktiskt iPhone-prov**. Även publika sidan i appens riktiga webbläsare reproducerade felet. Inga JavaScript-undantag registrerades; begäran skickades.

Knappen skickade `POST https://beta.smako.nu/api/plans`. Typiskt sanerat anrop med sidans sex faktiskt tillgängliga medlemsprogram:

```json
{
  "postal_code": "22350",
  "recipes": 5,
  "servings": 2,
  "max_stores": 3,
  "purchase_planning_mode": "exact",
  "diet_preference": "mixed",
  "availability_mode": "normal",
  "avoid_ingredients": [],
  "diversity_mode": "balanced",
  "varied_budget_percent": 25,
  "use_member_prices": true,
  "memberships": ["CITY_GROSS_PRIO", "COOP_MEMBER", "HEMKOP_MEMBER", "ICA_STAMMIS", "LIDL_PLUS", "WILLYS_PLUS"],
  "optimization_iterations": 1,
  "strategy": "optimized",
  "candidate_recipe_count": 80,
  "beam_width": 30,
  "debug": false
}
```

Billigast skickade `diversity_mode: "cheapest"`. Ren session hade inga förvalda medlemskap: `memberships: []`, `use_member_prices: false`. De sex ID:na verifierades i formulärets checkboxvärden och nätverksanropet. Skärmbildernas antal räcker inte för att identifiera innehållet i ett äldre försök; det tillskrivs därför inte användaren som historiskt bevis.

”Fler val” hade normal/rådgivande tillgänglighet, tom undviklista och variationsbudget 25 %. Grundstandard var fem middagar, fyra portioner och två inköpsställen; provet ändrade till två portioner och tre inköpsställen. Exakt köpplanering, blandad kost och valt variationsläge behölls.

Alla tre första knappförsök gav **HTTP 422**, utan fältplats eller separat felkod i svaret:

```json
{"detail":"OWN_SOURCES_ONLY=true requires OWN_GROCERY_BASE_URL"}
```

| Session | UTC 2026-10-02 | Request-ID | Backendtid |
|---|---|---|---:|
| Ren, Balanserad | 06:00:55 | `4f363c813de649f384b20d86a693f491` | 14,784 ms |
| Mobil, sex medlemskap, Balanserad | 06:00:58 | `61721907c2cb4401a6554207e13be720` | 13,285 ms |
| Mobil, sex medlemskap, Billigast | 06:01:01 | `03548dcd1ee04ccaadb49d91f3c77015` | 13,362 ms |

Browserns tider var 0,312 / 0,110 / 0,125 sekunder. Kompletta formulärvärden, svar och skärmbilder finns i lokal evidens `.local/public-menu-20261002/before`. `diagnostics-before.json` innehåller motsvarande allowlistade backendposter ur `beta_request_metrics`: endpoint, metod, status, `http_422`, tid och build-ID överensstämmer. Inga sessionsidentifierare, cookies eller token ingår i rapporten.

Historikens datum verifierades i databasen: **2 oktober 2026**, svensk sommartid UTC+2:

| Svensk tid | Request-ID | Status | Backendtid |
|---|---|---:|---:|
| 07:20:54,5198 | `35bf26a12d6943e98ef24ee623eeb5a7` | 422 | 16,694 ms |
| 07:21:19,7363 | `8714965f2018473a944f59f468e8c351` | 422 | 14,029 ms |
| 07:26:28,7796 | `1a1c159eacab4935bf0f525e861fcdc3` | 422 | 17,532 ms |

Dessa poster använder `/api/plans` och samma release. Historiska request/response-bodyer sparades inte, så de kan inte rekonstrueras exakt. Caddy hade ingen accesslogg aktiverad och inga motsvarande proxyfel i stdout. Därför finns ingen ärlig möjlighet att ange en historisk proxyloggrad för varje request-ID. Den faktiska proxykonfigurationen verifierades: 540 s svarstimeout för `/api/plans`. Ingen proxy- eller loggkonfiguration ändrades för felsökningen.

## Fastställda fel och riktad rättning

1. Femmiddagsformuläret gick via `_run_admitted_plan` → `MealPlanService.create_plan`, inte PersonalPlanner. Det skapade en liveprovider **innan** den redan förberedda lokala PriceUniverse-vägen kunde väljas. Normaldriften använder egna källor utan `OWN_GROCERY_BASE_URL`, vilket gav det reproducerade 422-felet. Rättningen väljer den befintliga `LocalPriceUniverseProvider` när matchande förberett underlag finns. Ordinarie kontroll av område, medlemskap och färskhet körs fortfarande.
2. När första felet var passerat kastade medlemsprisernas deltaoptimering `Weight-dependent checkout requires estimated planning mode`. Två delvägar saknade fullprojektionens befintliga bortfiltrering av otillåtna viktuppskattningar. De använder nu samma `_project_rows` och samma exakta policy. Uppskattningar aktiveras inte.
3. Den frivilliga jämförelsen ”Obegränsat” försökte skapa 8 589 934 591 butiksdelmängder för 33 kontexter, trots användarens tak tre. Instrumentering fångade `stores=33 limit=33`; isolerade containrar träffade minnesgränsen. Endast den frivilliga obegränsade jämförelsen utelämnas med tydlig förklaring över tolv kontexter. Användarens trebutikskorg och jämförelserna 1/2/3 behålls.
4. Verkliga browserprov visade klientavbrott efter 90 s. Klientens väntetid är nu 600 s, samma som den befintliga personliga planeraren och längre än proxyns 540 s. Timeout förklaras som timeout med fel-ID; det utgör inte i sig ett lyckat menyprov.
5. Ett fortsatt isolerat knappförsök översteg även 600 s. Profilering visade att orelaterade erbjudandealias i hela kommunens pool skickade råvarukorgar genom kartesisk kampanjberäkning. Kontrollen av gemensamma produktköptak avgränsas nu till faktiskt efterfrågade råvarurader. Kampanjgruppskontrollen behålls. Nested 1/2/3-gränser delar en exakt genomgång, och den befintliga verifierade basprisvägen behåller oföränderliga kandidatsekvenser i den befintliga request-lokala cachen. Ingen ny approximativ prisberäkning eller sänkt kampanjgräns införs.

Alla dessa fel belades före respektive rättning. Mellanprov som avbröts för att ersättas av en senare kandidat räknas inte som acceptans. Ett instrumenterat prov avslutades dessutom med signal 11 utan OOM; detta har inte tillskrivits användarfelet eller räknats som ett godkänt prov.

## Skillnaden mot releaseprovet

| Egenskap | Publik femmiddagsknapp | Befintligt 15/20-releaseprov |
|---|---|---|
| Endpoint | POST `/api/plans` | POST `/api/plans` |
| Kodväg | MealPlanService, `personal` saknas | PersonalPlanner, `personal` finns |
| Omfattning | 5 recept × 2 portioner | 15 måltider, sammanlagt 20 portioner |
| Butikstak i prov | heltal 3 | heltal 2 |
| Medlemskap | array av faktiska program-ID i `memberships` | inga medlemskap i original; Willys Plus och Lidl Plus i plusprofilen |
| Köpplanering | `exact` | separata `exact`/`estimated` |
| Näringsmodell | befintlig canonical-estimatmodell med tydlig uppskattningsmärkning | separat `personal.allow_nutrition_estimates` i releaseprofilen |
| Näringsmedgivande ändrat | inget nytt fält/medgivande skickas | releaseprofilens redan uttryckliga `true` bevaras |
| Kanaler | områdets tillåtna källkontexter; inget separat kanalfält | samma grundområde, personlig modell kan ange explicita kontexter |

PlanRequest tar emot numeriska 5/2/3, enumvärdena exact/mixed/balanced eller cheapest, och normaliserar medlems-ID till både programlista och kedjeflaggor. Generell modell tillåter upp till fyra inköpsställen; konsumentvägen tillåter tre. Ingen dold tvåbutiksgräns konstaterades. Cacheförberedelse för ett och två inköpsställen är inte ett formulärtak. Ingen ändring av användarens butikstak gjordes.

## Felpresentation och tester

Verklig fältvalidering får strukturerad fältplats, svensk fältetikett, fokus och `aria-invalid`. DATA_BLOCKED, ofullständig möjlig korg, inaktuellt prisunderlag, timeout, kapacitetsfel, autentisering och internt serverfel får olika förklaringar. Interna konfigurationsdetaljer skickas inte till användaren. Ett genererat/ekat `X-Request-ID` visas som Fel-ID, även vid klienttimeout. Formulärvärden behålls. ”Kontrollera dina val” är inte längre generell felorsak.

Regressioner visar providerfelet, exakt medlemsprojektion, obegränsad delmängdsexplosion, orelaterade erbjudandealias, upprepad nested-sökning och förlorad cache före respektive rättning. Separata UI-feltester använder syntetiska HTTP-fel för att kontrollera presentationen; de används aldrig som publik acceptans. Exakta grupppriser, gemensamma köptak, offertidentitet, kvantitetspolicy, konsumentgränser, PWA och optimerare kontrolleras med relevanta befintliga tester.

## Driftsättning och offentlig acceptans

App-hotfixen driftsattes 2026-10-02 cirka 09:14 svensk tid från Git-commit `14cc716ae54e2bb09ceaed5c4e3c2159e3a9c97d`, paket SHA-256 `aac48416d4902b4984c439eca92074a0ecae8fde117cc9ff69b723206efe5f37`, image `sha256:7dcc2c5c9b35a0f0ab68e1e1b180eada790c3f0a045d8f6a63c883ee7461ebef`. Tidigare rättningscommits är `443f947` och `c365444`.

621 runtimefiler matchade Git-paketet; beroendekontroll och Chromium-start utan nät PASS. De sista fokuserade sviterna gav 268 respektive 155 godkända tester (delvis överlappande), Ruff och compileall PASS. Elva befintliga Pydantic-varningar om enum i combined-profile-testfixturer kvarstår; inga testfel.

Bytet följde befintlig app-only-procedur och delat refresh/backup-lås, med SQLite-onlinebackup av plandatabasen. 179 tidigare revisioner verifierades oförändrade, databasens integritet var OK, och prismanifesten var identiska under bytet. Scheduler och proxy har samma container-ID som före, och alla miljövariabler utom appens BUILD_ID är identiska. Driftkonfigurationens enda semantiska skillnader är app-image och appens BUILD_ID. Källjobb ligger kvar på 08c1374. Ingen migration, prisrestore eller omaktivering av Lund genomfördes.

Aktiv källa: `/opt/smako/releases/public-menu-14cc716ae54e`. Skyddad återgångsinformation och plandatabackup: `/opt/smako/evidence/public-menu-20261002`. Återgångsverktyget återställer föregående appbild och Compose-koppling under driftlåset, **inte databaser eller priser**. Äldre källor, containrar och bevis har bevarats.

Efter bytet verifierades de faktiskt serverade HTML/JS/service-worker-filerna mot Git utan avvikelse. Service worker v11, nätverksprioritet och oförändrad säkerhetspolicy. Ett första testverktygsförsök avbröts när Playwrights strängbaserade väntan stred mot CSP; testet ändrades till DOM-locator-väntan. Det räknas inte som publik acceptans. Kandidatens kalla Balanserad-prov tog 333,359 s. Det slutliga publika Balanserad-provet kan ha delat uppvärmning med det avbrutna testförsöket och anges därför inte som ett oberoende kallprov.

Offentlig knappacceptans körs i Chromium, separata rena browser contexts, utan API-mockar eller handändrade requests:

| Publik väg | HTTP | Browsertid | Kostnad | Inköpsställen | Request-ID |
|---|---:|---:|---:|---:|---|
| Mobil, sex medlemskap, Balanserad | 201 | 286,000 s | 168,55 kr | 3 | `425b5f58-59cb-4538-8abf-ccb8fab22aa6` |
| Mobil, sex medlemskap, Billigast | 201 | 2,953 s (varm cache) | 125,10 kr | 3 | `830f6b2f-2fc4-42ca-9a27-74d20848e017` |
| Ren desktop, inga medlemskap, Balanserad | 201 | 313,984 s | 168,55 kr | 3 | `ada8b011-e714-4455-a4a0-0d2f5d94f0ef` |

Samtliga tre har fem middagar, två portioner/recept, tio portioner totalt, ingrediensmängder, fullständiga instruktioner, inköpsrader och avstämda summor. Korg VERIFIED, näringskontroll PASS och planens kvalitet PASS. Befintliga näringsuppskattningar är märkta som uppskattningar; köpläget är fortfarande exact. Begärda medlemskap bevaras; City Gross Prio och Lidl Plus utan verifierade kontrakt redovisas uttryckligen som sådana. Den rena sessionen skickar inga medlemskap och aktiverar inte medlemspriser. Separat GET efter omladdning gav identiska sparade planer och requests. Inga JavaScript-fel. En annan sessions läsning nekades med 403.

Alla sju slutliga anrop (tre knappvägar och fyra separata profiler) har matchande backendposter med samma request-ID, `/api/plans`, POST, 201 och nya build-ID:t. Se [knappresultat](public-acceptance.json), [backend och färskhet](after-runtime.json), [frontendhashar](frontend-after.json) och [kontrollerat appbyte](deployment.json). Proxyn har fortsatt ingen accesslogg; framgång via den publika HTTPS-domänen plus backendkorrelationen är det tillgängliga transitbeviset.

[Recept i publik mobilvy](mobile-six-balanced-recipes.png) och [inköpslista i publik mobilvy](mobile-six-balanced-shopping.png). Fullständiga sanerade request/response-bodyer, skärmbilder, återläsningar och tidsmått finns under `.local/public-menu-20261002/public-after`; ingen cookie eller token sparas av browserprovet.

Aktiveringsprotokollets fyra PersonalPlanner-profiler gav redan 440,72 kr med 08c1374; samma profiler och summa bekräftades här. De fyra separata PersonalPlanner-regressionerna gav HTTP 201 med identisk sparning/GET: original-exact 178,015 s, original-estimated 193,969 s, plus-exact 169,234 s och plus-estimated 191,343 s. Samtliga: 15 måltider/20 portioner enligt oförändrade profiler, 440,72 kr över två inköpsställen, köpgranskning PASS, avstämda totalsummor och uppfyllda proteinminima. Endast den separata testsessionens aktuella pantry_revision hämtades på nytt. Detta är API-regressioner, inte ersättning för knappacceptansen. [Sanerade regressionsresultat](personal-regressions.json).

Kvarvarande praktisk begränsning: en kall femmiddagsberäkning tar fortfarande flera minuter. Den obegränsade frivilliga butiksjämförelsen utelämnas tydligt för stora prisområden. Inget faktiskt iPhone-prov har gjorts.

Ingen Git-push, städning, Malmö-aktivering eller ändring av relä, scheman eller femkällorspolicy ingår.
