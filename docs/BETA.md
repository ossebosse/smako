# 2026-11-24: Willys-reläet turas om mellan Lund och Malmö

Main `5aaad70`. Malmö Willys har inte levererats sedan 2026-11-05: reläet på
ägarens dator körde alltid Lund först (≈1 h), Malmö hann bara 2 av 3 butiker
(`insufficient_collection_window` 12/11, 19/11), och full serverdisk stoppade
9/11 och 23/11 (även Lund). En kommun som får vänta på tid går nu först nästa
körning. Relärelease `5aaad700832f` (sha256 `914c56ce…`) och adminskript ligger i
`D:\Projects\Smako\.local\relay-fair-window-20261124`; ägaren kör skriptet
(installerar bredvid `2b65533af00d`, pekar om uppgiften, sparar före/efter-XML).
`scopes/municipal-schedule.json`: Malmö (`1280`) markerad `squeezed` så att den
går först 2026-11-26 03:17 (kopia `municipal-schedule.before-20261124.json`).

---

# 2026-11-24 morgon: Coop Online Syd hämtas igen

Main `0292f98`. Scheduler **source-ops-0292f98cfcaf**. En Coop-vara med
säljenhet "0" kastade hela Coop-katalogen sedan 5/11; rättat, nattens
sparade hämtning ompersad och promoverad (11 456 varor).
[Aktiveringsjournal](releases/coop-placeholder-unit-20261124/ACTIVATED.md).

---

# 2026-11-23 kväll: Primat-varor klassas som insamlade varor

Main `25cbf48`. Scheduler **source-ops-25cbf488ca83**. Primat-varor får samma
livsmedelsklassning som Smakos egna källor; ca en tredjedel av ICA-varorna blir
användbara i recept. Effekt efter Primat-uppdateringen 2026-11-24 01:10.
[Aktiveringsjournal](releases/primat-classify-20261123/ACTIVATED.md).

---

# 2026-11-23 kväll: Prisåldern för Primat-butiker; Mobilia och Maxi Malmö

Main `17302fa`. Scheduler **source-ops-17302fa4f4ff**. Clemenstorgets två
månader gamla Primat-priser lämnas ute (orsak till `degraded`); Mobilia och
Maxi Malmö verifierade och korgkvalificerade (kontextprov 46/54 prissatta).
Primat-uppdatering Lund + Malmö schemalagd 2026-11-24 01:10 efter kvotåterställning.
[Aktiveringsjournal](releases/primat-age-and-malmo-20261123/ACTIVATED.md).

---

# 2026-11-23: Hela ICA-katalogen från Primat, 14 dygns prisålder

Main `ca08017`. Scheduler **source-ops-ca08017afde0** (`sha256:7dd64e6dccd3…`),
app samma bild med override `price-age-14d-20261123.json`. Dagligt katalogjobb
07:37 för alla fem ICA-butiker med full katalog hos Primat (gratisnivån, en
runda ≈ 10–14 dygn); ICA-priser tas ur katalogen när rundan är klar.
`MAX_PRICE_AGE_HOURS=336`, `PRICE_AGE_WARNING_HOURS=240` för alla kedjor.
Första steget 9 851 rader. [Aktiveringsjournal](releases/ica-full-catalog-20261123/ACTIVATED.md).

---

# 2026-11-22 kväll: Fler Primat-sökningar för ICA (scheduler)

Main `7ec9a6767a22`. Scheduler **source-ops-7ec9a6767a22**
(`sha256:192cf3ae7f4a…`), app orörd (`app-d3bad43b756e-ccf6ce69`). Nattens
Primat-uppdatering gör 48 + 100 receptsökningar (149 anrop per stad, 1,1 s
mellanrum) inom gratisnivån, för ICA Gunnesbo, Västra Hamnen och Caroli.
Liveprov: 13 av 15 saknade ingredienser i ägarens plan fick pris med
förpackning. Aktiverad 21:07 UTC; config före/efter skiljer bara i image och
BUILD_ID. [Aktiveringsjournal](releases/ica-primat-recipe-queries-20261122/ACTIVATED.md).

---

# 2026-11-22 kväll: Kvitton med vägda varor

Main `d3bad43b756e` (fast-forward av `receipt-matching-2-20261122`). App
**app-d3bad43b756e-ccf6ce69**, bas `9ba01ad64d7c`. Ändrat:
`member_rewards.py`, `api/member.py`. Ägarens tredje Hemköp-kvitto (PDF):
vägda varors namnrad saknar pris och följs av viktraden; namnet väntar nu på
sin viktrad, och en vikt-/antalsrad går till den vara vars pris den
förklarar. Vägda varor jämförs med Smakos kilopris. Sammansatta ord,
varumärke och numrerade storlekar (S6, 13-19 kg) tolkas bättre. Kvittotexten
(utan kort-, medlems- och terminalnummer) är testdata. Importprov i
nätverkslös container godkänt. Aktiverad 19:24 UTC; befintligt tillstånd och
prismanifest bevarade, lagringsretention körd efteråt. `/ready` Lund och
Malmö: ready.

# 2026-11-22 kväll: Kvitton jämförs med alla Smako-priser

Main `9ba01ad64d7c` (fast-forward av `receipt-matching-20261122`). App
**app-9ba01ad64d7c-314931cd**, bas `ff812c8a875f`. Ändrat:
`member_rewards.py`, `api/member.py`. Ägarens andra Hemköp-kvitto gav tre
"andra priser" som var Smakos egna: klubbpris (Minutfilé, Jordnötssmör) och
en mindre förpackning (Småbladsmix). Kvitton jämförs nu med ordinarie,
kampanj-, medlems- och klubbpris samt "2 för"-erbjudanden per förpackning;
radens första ord (varan) måste matcha, gram matchar aldrig ml, EKO föredrar
ekologiska varor, kassar och pant räknas inte. Underlaget saknade bara "2 för
28" på Lätt Crème Fraiche Bearnaise. Importprov i nätverkslös container
godkänt. Aktiverad 16:48 UTC; befintligt tillstånd och prismanifest
bevarade, lagringsretention körd efteråt. `/ready` Lund och Malmö: ready.

# 2026-11-22 eftermiddag: Kvittopoäng för alla varor

Main `ff812c8a875f` (fast-forward av `receipt-points-any-item`). App
**app-ff812c8a875f-f7b35815**, bas `a6eac85e678a`. Ändrat:
`member_rewards.py`, `api/member.py`, `planning_rules.py`, `admin-rules.js`,
`admin.html`, `next/mine.js`, `next/a.html`, `next/b.html`. Ägarbeslut
2026-11-22: varorna behöver inte finnas på handlingslistan; +5 per vara som
Smako saknar i butiken (eller varje vara i en butik utan Smako-priser), +2 per
vara med annat pris än Smakos, 10 per kvitto med minst 3 lästa varor, högst
100 poäng per kvitto. Osäkra matchningar ger inga poäng förrän streckkoden är
skannad. Importprov i nätverkslös container godkänt. Aktiverad 14:10 UTC;
befintligt tillstånd och prismanifest bevarade, lagringsretention körd
efteråt. `/ready` Lund och Malmö: ready.

# 2026-11-22 middag: Näring för alla middagar, gilla recept och poäng för kvitton

Main `a6eac85e678a` (fast-forward av `nutrition-fallback-20261122` och
`member-points-20261122`). App **app-a6eac85e678a-0c8e22c0**, bas
`3f82b06919d8`.

Näring (ägarrapport 2026-11-22, 4 av 5 middagar utan näringsvärden): en vara
utan användbar tabell får Livsmedelsverkets allmänna värde för samma livsmedel
i receptets form, bara för visade värden (`nutrition_fallback.py`); nya
SLV-referenser i `slv-20261122.json` (lammkött, tonfisk, sardiner, mozzarella,
parmesan, bakpulver, körsbärstomat); olivolja hemma räknas med; salladslök och
kapris räknas inte med och visas med namn.

Medlemskap (ägarbeslut 2026-11-22): medlemmar gillar/ogillar rätter, alla ser
antalet; gillade rätter föreslås oftare och ogillade aldrig för medlemmen.
Poäng för kvitton (foto läst i telefonen med tesseract.js, eller PDF): 10 per
kvitto med minst 3 varor från listan, +2 per vara med annat pris än Smakos,
+5 per vara köpt där Smako saknar priser; värdena och senaste kvitton på
admin-fliken Matplanering. Nya tabeller i plans-databasen
(`member_recipe_ratings`, `member_receipts`, `member_points`).

Caddy (ägarens ja 2026-11-22): `script-src` fick `'wasm-unsafe-eval'` i
`/opt/smako/overrides/Caddyfile.geolocation-1fc4b6c` (kopia före ändringen:
`...-1fc4b6c.before-wasm-20261122`); Caddy omstartad 11:38 UTC eftersom
admin-API:t är avstängt. `deploy/Caddyfile` i repot ändras vid nästa
fullständiga release.

Importprov i nätverkslös container godkänt. Aktiverad 11:43 UTC;
befintligt tillstånd och prismanifest bevarade, lagringsretention körd
efteråt. `/ready` Lund och Malmö: ready.

# 2026-11-22 förmiddag: Fliken Matplanering på adminsidan

Main `3f82b06919d8` (fast-forward av `planning-rules-admin`). App
**app-3f82b06919d8-e8abbbe9**, bas `78eb7f6d0442`. Ändrat: `planning_rules.py`
(nytt), `personal_policy.py`, `personal_planner.py`, `plan_variation.py`,
`api/beta_ops.py`, `admin.html`, `admin.css`, `admin-rules.js` (nytt).
Ägarbegäran 2026-11-22: alla regler för matplaneringen går att finjustera
under /admin, fliken "Matplanering": kostfördelningen för 1–7 middagar (Allt:
kött, fisk, vegetariskt; Fisk och vegetariskt: fisk), högsta andel av ett
köttslag och ett matkök, minsta besparing för en butik till, vikterna för
gillar/ogillar och saknad gillad råvara, slumpvariationen och standarden för
"undvik rätter från senaste planer". Reglerna sparas i
`/srv/app/var/plans/planning-rules.json` och gäller nya planer; saknas filen
gäller standardvärdena (ägarbesluten hittills). Importprov i nätverkslös
container godkänt. Aktiverad 08:45 UTC; befintligt tillstånd och prismanifest
bevarade, lagringsretention körd efteråt. `/ready` Lund och Malmö: ready.

# 2026-11-22 morgon: Kostandelar och matkök i veckan

Main `78eb7f6d0442` (fast-forward av `diet-shares-20261122`). App
**app-78eb7f6d0442-6b93e73a**, bas `370df63cd371`. Ändrat:
`personal_policy.py`, `personal_planner.py`, `next/core.js`, `next/a.html`,
`next/b.html`. Ägarbeslut 2026-11-22: "Allt" har kött eller kyckling i minst
1 av 1–3, 2 av 4–5, 3 av 6–7 middagar, en vegetarisk vid 2+ och minst en
fiskrätt vid 4–7; "Fisk och vegetariskt" har fisk enligt samma tabell; ett
köttslag i högst hälften av kötträtterna; ett matkök i högst hälften av
middagarna (avrundat uppåt) om man inte valt ett enda kök; allt så långt
övriga val tillåter. "Torkade kryddor" borttaget ur "Har du hemma?".
Importprov i nätverkslös container godkänt. Aktiverad 08:07 UTC; befintligt
tillstånd och prismanifest bevarade, lagringsretention körd efteråt.
`/ready` Lund och Malmö: ready.

# 2026-11-21 kväll: Variation i planerna, 100 nya middagar, blockerande ingredienser

Main `370df63cd371` (fast-forward av `plan-variation`, merge av
`more-dinners-20261121`). App **app-370df63cd371-98dbcac1**, bas
`0e556758891a` (image `a6c7279f5134`). Ändrat: `plan_variation.py` (nytt),
`personal_planner.py`, `personal_store.py`, `api/personal.py`, `api/plan.py`,
`models/personal.py`, `intake_product_links.py`, `complete_recipes.py`, ett nytt
receptpaket och bibliotekmanifest (`smako-variation-bases-20261121`, 100
grundrätter, 300 varianter), samt `next/mine.js`, `next/a.html`, `next/b.html`.
Ägarbeslut 2026-11-21: nya planer väljer ibland en vecka inom cirka 10 % av den
billigaste; medlemmar undviker rätter från sina senaste planer (inställning,
standard 2 planer). 28 ingredienser fick granskade etikettregler; ägaren har
noterat förslagen för de som inte finns i butik. Importprov i nätverkslös
container godkänt. Aktiverad 22:45 UTC; befintligt tillstånd och prismanifest
bevarade, lagringsretention körd efteråt. `/ready` Lund och Malmö: ready.

# 2026-11-21: Kärnbibliotekets namn, fler näringsvärden

Main `0e556758891a` (branch `core-names-and-nutrition`, fast-forward). App
**app-0e556758891a-1ef84515**, bas `434cad1f7e70` (image `70f21b986fd9`).
Ändrat: ett nytt receptpaket och bibliotekmanifest (95 kärnvarianter med
riktiga namn, steg och mängder oförändrade), `recipe_library.py`
(kärngenerationens skalning följer släktledet), `nutrition_reference.py`,
`recipe_preparation.py`, `recipe_volume_nutrition.py`, `nordic_nutrition.py`,
`staples.py`, nya referensdata `slv-20261121.json` och
`matvaretabellen-20261121.json`, samt `next/core.js`, `next/a.html`,
`next/b.html`. Ägarbeslut 2026-11-21: torkade kryddor och färsk mynta räknas
aldrig i visade näringsvärden; vätskor i ml använder Matvaretabellens vikt per
dl; ägg 88 % ätbar andel; butternut från Matvaretabellen. Importprov i
nätverkslös container godkänt. Aktiverad 08:57 UTC; befintligt tillstånd och
prismanifest bevarade, lagringsretention körd efteråt. `/ready` Lund och
Malmö: ready.

# 2026-11-20 sen kväll: Riktiga rättnamn, fler näringsvärden, kampanjer i listan

Main `434cad1f7e70` (merge av `campaign-marks`, `dinner-names` och
`nutrition-gaps`). App **app-434cad1f7e70-4f6f4fb5**, image `70f21b986fd9`, bas
`94f39e9de168` (image `014781c7375d`). Ändrat: tio nya receptpaket och
bibliotekmanifest (911 middagsnamn i 1999 varianter, steg och mängder
oförändrade; 59 namn i kärnbiblioteket väntar på ny biblioteksversion),
`nutrition_reference.py`, `personal_planner.py`, `staples.py` (torkade kryddor
på högst 2 g räknas som noll och visas vid näringsvärdet) och `next/a.html`,
`next/b.html`, `next/base.css`, `next/core.js` (kampanjvaror märks i
inköpslistan). Importprov i nätverkslös container godkänt. Aktiverad 22:07 UTC;
befintligt tillstånd och prismanifest bevarade, lagringsretention körd efteråt.
`/ready` Lund och Malmö: ready (prisunderlaget `degraded` av äldre basprisrader
som behålls tills de ersätts, som före aktiveringen).

# 2026-11-20 kväll: Medlemmar får fler middagar och portioner

Main `94f39e9de168`. App **app-94f39e9de168-622d7ec3**, image `014781c7375d`,
bas `02c9da2819f9` (image `2b9db89e5670`). Tre ändrade filer: `next/core.js`,
`next/a.html`, `next/b.html`. De nya gränssnitten använde gästgränserna (3
middagar, 2 portioner) även för inloggade medlemmar. Aktiverad 17:57:34 UTC,
lagringsretention complete före och efter. `/ready` Lund och Malmö: ready
(prisunderlaget `degraded` av äldre basprisrader som behålls tills de ersätts,
som före aktiveringen).

# 2026-11-20 eftermiddag: Alternativ A som standard, 49 billiga grundrätter

Main `02c9da2819f9` (merge av `ui-a-default`, `variation-and-diet-fixes` och
`cheap-base-recipes-resolved`). App **app-02c9da2819f9-dcc1560d**, image
`2b9db89e5670`, bas `343946e59054`. 17 ändrade filer: receptpaket och
bibliotekmanifest, granskningsregister (`composition-rereviews-20261120.json`,
`recipe-shapes-20261026.json`), `intake_product_links.py`, `diet_policy.py`,
`personal_policy.py`, `personal_planner.py` och de statiska filerna för
Alternativ A/B, admin och `/personal`. Aktiverad 14:27:26 UTC. Prov: /personal
öppnar /ui/a; Lund, 3 middagar, "Många ingredienser" gav tre recept med 14
ingredienser, 278,11 kr, cirka 20 s.

Bygge och aktivering kördes med arbetarkoden från `beta_release.py` startad med
nohup på servern, eftersom klientens skal stoppar långa processer. Kvittona
skrevs till arbetsmappen efteråt. Ett första bygge (`app-02c9da2819f9-6b766034`)
avbröts på klientsidan efter bildbygget och användes inte.

# 2026-11-18 morgon: Uppvärmning med lägsta prioritet, tre planer samtidigt

Main `daa6a40bd821` (PR #99). App **app-daa6a40bd821-c51d81c5**, image
`dee5a1076ec1`, bas `a94018b1f7c3` (image `03e2197ffe05`). Två ändrade filer:
`nutrition_prewarm.py` och `planner_processes.py`. Inga lokala undantag.
Bygget väntade på den dagliga prisuppdateringen (driftlåset, klar 06:04 UTC),
som själv skrev nya ögonblicksbilder för de nya prisunderlagen. Aktiverad
06:24:17 UTC, säkerhetskopia `20261118T061150Z`, lagringsretention complete
före och efter.

Efter aktiveringen satte ägaren `PLANNER_MAX_CONCURRENT_REQUESTS=3` i
`multicore-snapshots-a94018b1f7c3.json`, med driftlås, lugn plantrafik, kopia
i `/opt/smako/evidence/concurrency-3-*` och automatisk återställning. Omstart
till ready: 52–53 s (ögonblicksbilder).

Mätt på betan (Malmö, 54 butiker, nya kombinationer per gäst):
- **Direkt efter omstarten, allt kallt och uppvärmning igång:** tre samtidiga
  (lax, bönor, svamp) hann alla inte bli klara (95–170 s, "Vi hann inte...").
- **Några minuter senare, fyra samtidiga** (nötfärs, pasta, tofu, ris): alla
  klara. Tofu efter 83 s, pasta och ris efter ca 105 s, nötfärs efter 147 s
  (fick vänta).
- **Därefter tre samtidiga** (kyckling, potatis, lax): alla klara efter 62, 91
  och 125 s.
- Uppvärmningen startar bara när planeraren är ledig, men upptar sedan en av
  platserna i ca 2 minuter per varv.

Kvarstående risk: tre helt nya Malmöplaner samtidigt direkt efter en omstart
eller ett byte av prisunderlag hinner inte bli klara inom 90 s.

# 2026-11-17 kväll: Två planer samtidigt, flera kärnor och snabb start aktiverat

Main `a94018b1f7c3` (PR #95, #97, #98). App **app-a94018b1f7c3-301421b6**,
image `03e2197ffe05`, bas `7c59f6290822` (image `ac59196cc756`). Scheduler
orörd. Aktiverad 2026-11-17 21:08:03 UTC, säkerhetskopia `20261117T205907Z`.
Lagringsretention complete före och efter. `/ready` 200 för 22350 och 21120.

Förberedelsen krävde ett lokalt, granskat undantag i `beta_release.py` (inte
incheckat): `deploy/compose.yaml` ändrades i intervallet. Serverns compose
får samma inställningar genom en egen override i stället:
`/opt/smako/overrides/multicore-snapshots-a94018b1f7c3.json` med
`PLANNER_MAX_CONCURRENT_REQUESTS=2`, `SMAKO_PREPARED_SNAPSHOT_ROOT` och
volymen `/srv/smako/data/prepared_snapshots` (10001:10001, 700).

Overriden lades in under driftlåset med samma kontroller som en aktivering:
lugn plantrafik, wrapperkopia, konfigkontroll, `/ready` för båda städerna,
oförändrad image och miljö utöver de två variablerna. Underlag finns i
`/opt/smako/evidence/multicore-snapshots-a94018b1f7c3/`. Två planer i stället
för tre, eftersom tre nya Malmöplaner samtidigt tog 87–93 s mot gränsen 90 s.

Importkontroll av kandidaten var ok. I kandidatbilden utan nätverk tog Lunds
prisunderlag 38,6 s från JSON och 3,2 s från ögonblicksbild, fakta 37,2 s
mot 0,9 s, med samma plan (114,18 kr).

Mätt på betan:
- **Start:** den första starten skrev ögonblicksbilderna (174 s). En omstart
  efter det: appen startade på 27 s och svarade ready efter 56 s, inklusive
  nedstängning.
- **Tre nya Malmöplaner samtidigt:** alla lyckades. Två räknades sida vid sida
  på ca 62 s, den tredje väntade på en ledig plats och var klar efter 101 s.
- **Malmö, sedan uppvärmningen var klar:** 3 middagar 35 s, gillar kyckling
  60 s, eko 25 % 49 s, mjölkallergi 70 s. Lund fisk och vegetariskt 47 s.
- **Flöde A (Lund):** plan 40 s, byte av recept 24 s, handlingslista, köp
  sparat i skafferiet. Inga sid- eller API-fel.

Fel som hittades: medan uppvärmningen efter starten pågick (ca 10 minuter)
hann de första planerna i Malmö (95,7 s) och Lund (67,9 s) inte bli klara.
Uppvärmningen tog alla provare. Rättningen är PR #99 (lägsta CPU-prioritet och
högst en provare för bakgrundsarbete). Den är inte aktiverad, eftersom PR:en
väntar på ägarens godkännande.

# 2026-11-17: Testrapportens fel, Stora Coop, butikernas allergener, fisk, fart

Main `7c59f6290822` (PR #94). App **app-7c59f6290822-8fc198af**, scheduler
orörd, Axfood-detaljer fortfarande `f87b8df135a7…`. 24 appfiler, importkontroll
ok (`FACTS_VERSION` v14). Bas `b0190e160084` (image `e9b120ae65db`), ny image
`ac59196cc756`. Aktiverad 2026-11-17 09:52:01 UTC, säkerhetskopia
`20261117T094118Z`; lagringsretention complete; `/ready` 200 för 22350 och 21120.

Förberedelsen krävde två lokala, granskade undantag i `beta_release.py` (inte
incheckade): `providers/coop_syd_base.py` finns inte i appens image (används av
schedulern; appen visar redan "Ordinarie pris" via `meal_plan_optimizer`), och
appens `price_universe_runtime.py` saknade bara 8a53bebs parameter
`source_strategy_version` med samma standardvärde, så Gits fil skickades.

Mätt på betan efter aktivering (alla butiker i området, högst 2): Malmö 54
butiker 3 middagar 94 s första gången, 33 s nästa gång och 45 s med andra
gillar; gillar kyckling 98 s, eko 25 % 136 s, mjölkallergi 39 s. Lund 25
butiker 3 middagar 43 s, fisk och vegetariskt 32 s (en fiskrätt). Coop Online
Syd listas inte i någon av städerna.

# 2026-11-16: Steg 5–7 och näringsdeklarationer aktiverat

Main `b0190e160084` (PR #89, #92, #90, #91). App **app-b0190e160084-b72e8023**,
scheduler orörd. Steg 5 (sökning, skafferi med äggstorlek och sorter), steg 6
(minnesrensning efter jobbet, delade varufakta, veckosökningen slutar när den
inte hittar billigare), gillar utan extra planering, steg 7 del 1 och City
Gross-deklarationer (`FACTS_VERSION` v13). 23 appfiler, importkontroll ok. Bas
`745bf535233b` (image `6f61eea792dd`), ny image `e9b120ae65db`. Aktiverad
2026-11-16 21:02:28 UTC, säkerhetskopia `20261116T205317Z`; lagringsretention
complete; `/ready` 200 för 22350 och 21120.

Därefter, under samma driftlås, pekades appens `AXFOOD_PRODUCT_DETAIL_ROOT` om
till release `f87b8df135a7…` (2 822 Willys- och 505 Hemköp-dokument, tidigare
111 och 12) via `overrides/axfood-details-f87b8df135a7.json`; schedulern läser
inte detaljerna och är orörd. Återgång: ta bort den override-filen ur
compose-omslaget (kopia i `evidence/axfood-details-f87b8df135a7/`) och starta
om appen. Se `docs/DECLARATIONS.md`.

# 2026-11-15: Gillar i flera middagar aktiverat

Main `745bf535233b` (PR #87). App **app-745bf535233b-7a0d5db0**, scheduler
orörd. Bara provgränssnitten ändras (core.js, a.html, b.html, `?v=20261115f`):
en gillning i flera middagar prissätts mot den billigaste veckan utan den.
Bas `d611d09080e4` (image `f17d26119fa0`), ny image `6f61eea792dd`,
importkontroll ok. Aktiverad 2026-11-15 12:27:45 UTC, säkerhetskopia
`20261115T121850Z`; lagringsretention complete; `/ready` 200 för 22350 och 21120.

Prov 2026-11-16 i /ui/a (Lund, 3 middagar, gillar kyckling): första försöket
tog slut på tid efter 56 s ("Vi hann inte hitta en fungerande lista"), andra
gav två kycklingrätter på 56 s. Raden "Du gillar kyckling i 2 middagar · utan
kyckling hade veckan kostat 23,90 kr mindre" kom efter 51 s till, och popupen
visade veckan utan kyckling. Inga sidfel eller API-fel utöver tidsgränsen.

# 2026-11-15: Steg 4 – blandat, extra butik ≥ 10 kr, Gillar och Har du hemma aktiverat

Main `d611d09080e4` (PR #85). App **app-d611d09080e4-e17fc969**, scheduler
orörd. Ägarbeslut 2026-11-15: en extra butik måste spara minst 10 kr; "Allt"
betyder blandat (även vid byte av ett recept); varje "Gillar" finns i minst en
middag och provgränssnitten visar vad den kostar och ett billigare recept
(`preview_without_like`, inget sparas); "Har du hemma?" med salt, svartpeppar
och rapsolja förbockade. 10 appfiler, importkontroll ok, bas `1062559d7b3b`
(image `53145185976c`), ny image `f17d26119fa0`. Aktiverad 2026-11-15
11:17:51 UTC, säkerhetskopia `20261115T110838Z`; lagringsretention efter
aktivering complete; `/ready` 200 för 22350 och 21120.

Prov på beta (Lund, 3 middagar × 2 portioner, salt och rapsolja hemma):
Allt 51,8 s, 116,21 kr i 2 butiker (sparar 22,90 kr), två vegetariska och
falukorv; gillar kyckling 51,0 s, två kycklingrätter, 139,50 kr i 1 butik;
förhandsvisning av billigare recept 40,7 s per plats; gillar oxfilé och linser
ger två linsrätter och beskedet att oxfilé saknas; alla basvaror hemma 96,87 kr;
Malmö 81,6 s (fortfarande över målet); testkonto 5 middagar × 4 portioner
51,6 s. /ui/a i mobilstorlek: förbockade basvaror, märkningen på receptkorten
och raden "Har du hemma" i handlingslistan, inga sidfel eller API-fel. Med två
kycklingrätter visar båda "kostar inget extra", eftersom ett byte av en av dem
ensam inte gör inköpet billigare (de delar förpackning).

# 2026-11-15: Ät inte, tidsgräns från motorstart, förlopp 0–100 % och snabb näring aktiverat

Main `1062559d7b3b` (PR #81, #82, #83). App **app-1062559d7b3b-80314879**,
scheduler orörd. Ät inte kontrolleras på namn och deklaration (ägarbeslut
2026-11-14); allergier kräver deklaration utom färsk frukt och grönt.
Planerarens tidsgräns räknas från insläppet, inte från kön. Provgränssnitten
visar påsen, 0–100 % och tiden sedan knapptrycket, och alternativ A visar hur
mycket av inköpet som går till recepten. Sökning använder områdets postnummer.
Delad näringsevidens, näringsuppvärmning (oberoende av den avstängda
planuppvärmningen) och näring per portion även utan gränser. 18 appfiler,
importkontroll ok, bas `c2de0d344288` (image `9560994abaee`), ny image
`53145185976c`. Aktiverad 2026-11-15 cirka 07:45 UTC, säkerhetskopia
`20261115T073313Z`; `/ready` ready för 22350 och 21120. Näringsuppvärmningen för
Lund nådde sin 45 s-gräns (delvis uppvärmd).

Prov på beta (testkonto, Lund, 3 middagar): koriander 51 s och lök+vitlök 37 s
ger planer; glutenallergi ger klarspråksbeskedet; högst 700 kcal 52 s; minst
25 g protein tog slut på tid första gången (65 s) och gick på 42 s därefter;
protein+fett 46 s; 5 middagar × 4 portioner 51 s.

# 2026-11-14: Småfixar efter betatest aktiverade

Main `c2de0d344288`. App **app-c2de0d344288-55a9c6d4**, scheduler orörd.
Klarspråk när Smako saknar uppgifter för allergier, Ät inte, portionsvikt och
näring; batterier, tändstickor, våtservetter, bindor, deodorant, rakblad,
disktabletter, djurmat och kattsand räknas som inte mat; rätt singularformer
(1 vara, 1 portion); /personal säger att butikerna ska bekräftas; provgränssnitten
skickar högst två likadana rätter per måltidstyp och lägger till frukost och
mellanmål med små knappar under Middag. Nya ?v= och skalcache v45 så att
installerade kopior hämtar de ändrade filerna. 11 appfiler, importkontroll ok,
bas `09b7740076c1` (image `2432685ec7a8`), ny image `9560994abaee`. Aktiverad
2026-11-14 11:54 UTC, säkerhetskopia `20261114T114313Z`; `/ready` ready för
22350 och 21120. Bygge och aktivering fristående på servern som tidigare i dag.
Se testrapporten i projektet (testrapport-beta-20261114).

# 2026-11-14: Måltidskort med fördelning, portionsvikt och näring i provgränssnitten aktiverat

Main `09b7740076c1`. App **app-09b7740076c1-a3b5499c**, scheduler orörd.
/ui/a och /ui/b har nu måltidskort som /personal: Middag med antal, portioner
och knapparna Fördelning, Portionsvikt och Näringsvärden; frukost och mellanmål
läggs till under Fler måltider och får egna kort. Receptkorten visar näring per
portion. 5 appfiler (statiska), importkontroll av kandidaten ok, bas
`ac78802c4281` (image `dc594821923f`), ny image `2432685ec7a8`. Aktiverad
2026-11-14 07:53 UTC, säkerhetskopia `20261114T074502Z`; `/ready` ready för
22350 och 21120 med nya BUILD_ID. Bygge och aktivering kördes fristående på
servern (kod från `beta_release.py`, startad med `setsid nohup`), eftersom
enhetens skal avbryter bakgrundsprocesser när anropet slutar. Första
byggförsöket väntade på driftlåset under den dagliga insamlingen.

# 2026-11-13: Konto, skafferi och köp i provgränssnitten, Kött och förpackningsvikt aktiverat

Main `ac78802c4281`. App **app-ac78802c4281-02c83b8d**, scheduler orörd.
Provgränssnitten /ui/a och /ui/b har konto, skafferi och köp; frågeguiden har
valet Kött (middagar med kött, övriga måltider som vanligt); typade skafferirader
kraschar inte längre; när en vara saknar avrunnen vikt räknar Smako med
förpackningens vikt och visar notisen "vikten är med spad" (ägarbeslut
2026-11-13, se PLANNING-ARCHITECTURE.md). 22 appfiler, importkontroll av
kandidaten ok, bas `3e490544632a` (image `47d0bee21857`), ny image `dc594821923f`.
Aktiverad 2026-11-13 17:41 UTC, säkerhetskopia `20261113T173006Z`; `/ready`
ready för 22350 och 21120 med nya BUILD_ID, tidigare rader bevarade.
Första aktiveringsförsöket 17:04 UTC avbröts när klientanslutningen föll och
rullades automatiskt tillbaka; andra försöket kördes fristående på servern.
Lärdom: kör `activate` från en anslutning som överlever hela steget (cirka
10 minuter), annars rullas bytet tillbaka.

# 2026-11-12: Egna varor, provgränssnitt och lösvikt i matplanen aktiverat

Main `3e490544632a`. App **app-3e490544632a-749e98be**, scheduler orörd.
Generiska egna varor köps som de varor de namnger, billigaste vinner även med
lösvikt; samma vara i andra kedjor kan läggas till; två provgränssnitt väljs på
/admin. Matplanen tar nu också lösvikt när den är billigare än en exakt
förpackning (ägarbeslut 2026-11-12). Rättat: `/api/plan` kraschade på den nya
frozenset-policyn i urvalscachen. 24 appfiler, importkontroll av kandidaten ok,
retention före/efter complete, båda /ready svarar med nytt BUILD_ID.
Bygge och aktivering kördes losskopplade på servern med samma workerkod som
`beta_release.py` (laptopens skal tillåter högst 180 s per anrop).
Aktiverad 2026-11-12 07:04 UTC.

---

# 2026-11-10: Snabbare menysökning aktiverat

Main `82b9ce411660`. App **app-82b9ce411660-7332b1f6**, scheduler orörd.
Exakt samma menyer, snabbare: Malmö 2 portioner/3 butiker 117 s (avbrott) → 38 s,
2/4 270 → 46 s, Lund 2/3 22 → 15 s. Publikt prov Malmö 2/3: 39,8 s, VERIFIED.
Backup `/srv/smako/backups/20261110T194041Z`.
[Aktiveringsjournal](releases/planner-speed-20261110/ACTIVATED.md).

---

# 2026-11-09: Mina val Frågor aktiverat

Main `78c2649a2bf2`. App **app-78c2649a2bf2-083247bf**, scheduler orörd.
Fjärde mobilvisningen av Mina val (åtta frågor). Daglig rensning av gamla
Docker-images på servern (`smako-image-retention.timer`).
[Aktiveringsjournal](releases/choice-guide-20261109/ACTIVATED.md).
Föregående: 2026-11-08 snabbare sökning vid tre butiker,
[journal](releases/cap3-store-search-20261108/ACTIVATED.md).
Malmö 1 portion/3 butiker 64 s (avbrott) → 40 s; Lund 1/3 fungerar (medlemsbesparingsfixen).
Kvar: Malmö 2 portioner/3 butiker och 4+ butiker hinner inte inom 60 s.

---

# 2026-11-07 kväll: Kedjeövergripande produktgodkännanden aktiverat

Main `e02a2ef7f0db`. App **app-e02a2ef7f0db-1d6fdb43**, scheduler orörd.
Granskade varor med GTIN/artikelnummer gäller i alla butiker i kedjan: Lund 1 741 → 659
blockerade receptvarianter. Kvarvarande fel: Lund 1 portion/3 butiker ger HTTP 500 i
medlemsbesparingen (fanns före). [Aktiveringsjournal](releases/chain-wide-approvals-20261107/ACTIVATED.md).

---

# 2026-11-07: Fler köpbara råvaror och Malmö-ersättningar aktiverat

Main `bdd956c7351d`. App **app-bdd956c7351d-f0f775c9**, scheduler orörd.
Godkännanden knutna till artikelnummer (nötkött, lamm, tempeh m.fl. planerbara
igen), bredare råvaruidentiteter, förpackningsvikt för listade varor och
134 receptversioner med köpbara ersättningar för råvaror som Malmö inte säljer.
Publikt prov i Malmö: meny skapad, sparad och återläst, VERIFIED.
Bevarat: 337 planversioner, 151 privata tillstånd. Backup
`/srv/smako/backups/20261107T140021Z`.
[Aktiveringsjournal](releases/produce-coverage-20261107/ACTIVATED.md).

---

# 2026-11-07: Snabbare planering, "alla valda butiker" och City Gross-namn aktiverat

Main `e63953efb720`. App **app-e63953efb720-6d2ce025**, scheduler orörd.
Butikstak upp till alla valda butiker; exakt snabbare prissättning och
menysökning (identiska korgar i 34/34 prov, Malmö hela kommunen ca 2–3 gånger
snabbare); återanvänd receptkvalificering; 90 s för planer med fler än 30
butiker. City Gross-namnet slår igenom först när schedulern uppdateras.
Publikt prov i Lund: Stora Coop Lund och Willys Lund, 168,37 kr, VERIFIED.
Bevarat: 336 planversioner, 150 privata tillstånd. Backup
`/srv/smako/backups/20261107T081316Z`.
[Aktiveringsjournal](releases/speed-storecap-20261107/ACTIVATED.md).

---

# 2026-11-06: Stora Coop i stället för nätbutiken och butiksadresser aktiverat

Main `191f173f1e19`. App **app-191f173f1e19-e452c67c**, scheduler orörd.
Med alla butiker i kommunen jämförs Stora Coop Lund i stället för Coop Online
Syd, vars baspriser butiken redan har. Plan och inköpslista visar adress, t.ex.
"Willys Lund, Magistratsvägen 22". Publikt prov i Lund: Stora Coop Lund och
Willys Lund, 168,37 kr, VERIFIED. Bevarat: 335 planversioner, 149 privata
tillstånd. Backup `/srv/smako/backups/20261106T074611Z`.
[Aktiveringsjournal](releases/stores-stora-coop-20261106/ACTIVATED.md).

---

# 2026-11-05: Mina val (Din mat, Inköp), Pescetariskt och omväxling aktiverat

Main `431ddb3ac0f2`. App **app-431ddb3ac0f2-28522b51**, scheduler orörd
(source-ops-e6d4ceaca5bc). Hela main sedan 2026-11-01 följde med: textgenomgång,
receptvarianter och adminfiler. Mina val har sex steg; Gillar/Undvik med
allergimarkering; Pescetariskt som kostval; omväxling Lite/Lagom/Mer.
Grocery-ändringar som redan fanns i schedulern lämnades på appbildens version
(`--keep-app-grocery`). Publikt prov: tre pescetariska middagar, en fisk, tre
matkök, VERIFIED, 278,70 kr, återläst. Bevarat: 333 planversioner,
147 privata tillstånd. Backup `/srv/smako/backups/20261105T203020Z`.
[Aktiveringsjournal](releases/mina-val-dinmat-20261105/ACTIVATED.md).

---

# 2026-11-01: Uppvärmda prov och samordnad faktaläsning/GC aktiverat

[PR 59](https://github.com/ossebosse/smako/pull/59), main `b47e07febe6e`.
App **app-b7c8d0506e23-c18e4ba9**, scheduler source-ops-8a53beb80e43.
[Mätning](reviews/warm-facts-gc-20261101/REPORT.md) och
[aktiveringsjournal](releases/warm-facts-gc-20261101/ACTIVATED.md).

Varma prov kräver nu `/ready/preparation`: färdigt bibliotek och båda aktuella
kommunerna, rätt bygge och pris-ID:n. Gemensam uppvärmning är fortsatt på.
Normaljobb efter primning: median 24,226 → 21,694 s; faktaladdning
7,112 → 6,682 s; planerarens städning 4,722 → 2,401 s. Tre fulla GC blir två
plus generation 1. Minnestoppar i praktiken oförändrade; alla 20 menyprov godkända,
med identiska motsvarande korgar och samtliga 150 513 fakta över Lund/Malmö.
Det större fallet kvar på 51,3 s; uppvärmningen tog 85,0 → 92,6 s, ingen starttidsvinst.
Publikt efter uttrycklig uppvärmningsgrind: **28.469 och 25.203 s**,
båda verifierade/sparade, 110,55 kr. PR-/main-CI gröna (4 442 pass, 63 skip).
Full backup `/srv/smako/backups/20261101T064110Z`; tidigare användarrader, miljö, mountar och
prismanifest bevarade. Retention complete. Se rapportens omfattning och begränsningar.

---

# 2026-11-01: Varma menyprov kontrollerade; uppvärmning kvar på

Betan ligger kvar på `app-327fa573eb3f-0541cf49`. Ingen runtimeaktivering.
`SOURCE_FACTS_PREWARM_ENABLED=true` och V2:s begränsade uppvärmning behålls:
varm upprepning 22,358 → 21,648 s; första efter färdig uppvärmning
27,334 → 24,629 s. Tre nya val hade 0,145–1,016 s högre medeltid;
ingen generell tidsvinst påstås. 20/20 audit/sparning/ägd återläsning godkända,
identiska motsvarande recept, varukorgar och faktaversioner.
Det tidigare publika 53,500 s-provet överlappade förberedelsen; vanlig
`/ready` intygar inte att denna är färdig. Dagens publika prov: 32,391 och 28,359 s,
båda verifierade, 110,55 kr. Skäl till på/av, mätgränser och alla observationer:
[uppföljning](reviews/warm-prewarm-20261101/REPORT.md).

---

# Aktivera från main på den befintliga betan

Källa: `main` i `https://github.com/ossebosse/smako.git`.
Mål: https://beta.smako.nu. Det finns ingen automatisk deployment vid push.
En aktivering väljer alltid en bestämd commit och image, så senare commits
på `main` inte ändrar en pågående release.

## Förutsättningar

- Installera utvecklingsmiljön enligt [DEVELOPMENT.md](DEVELOPMENT.md).
- Behörig operatör behöver SSH-alias `smako` till befintlig server samt
  rättighet att köra `sudo -n python3` och hantera Docker. SSH-nycklar och
  serveradress tillhandahålls av projektets förvaltare, aldrig genom Git.
- Befintlig installation använder `/opt/smako/compose`, containrarna
  `smako-app-1`, `smako-scheduler-1`, `smako-caddy-1`, data i `/srv/smako/data`
  och det gemensamma driftlåset. Detta flöde installerar inte en ny server.
- Läs aktuell [HANDOFF.md](HANDOFF.md), [OPERATIONS.md](OPERATIONS.md) och
  senaste aktiveringsrapport. Appens BUILD_ID är `app-daa6a40bd821-c51d81c5`;
  schedulern är `source-ops-0292f98cfcaf`.
  [Uppvärmda prov och samordnad faktaläsning/GC](releases/warm-facts-gc-20261101/ACTIVATED.md)
  är senaste appaktiveringen. Sex Pythonfiler från kod `b7c8d0506e23`;
  verifierade varma jämförelser och minnesmaxima. Se journalens publika prov.
  [Föregående faktarättning](releases/menu-work-reduction-20261031/ACTIVATED.md)
  och övrig runtime består.
  [Stora Coop-kopplingen](releases/stora-coop-syd-base-20261029/ACTIVATED.md)
  dokumenterar de separata faktiska baserna och den exakta slutpatchen.
  [Senaste Coop-källrättning](releases/coop-remaining-sources-20261029/ACTIVATED.md)
  dokumenterar de skilda faktiska baserna: första app-/källrättningen 2600390d3943
  följdes av tre schedulerfiler 47b1f0fdb717. Appens äldre Coop-baser/collector
  kräver den dokumenterade exakta backporteringen; kopiera inte hela main över runtime.
  Recept-/beräkningskod består. Två adminfiler i första releasen gav normal cacheinvalidering.
  Den tidigare [Coop-fälträttningen](releases/coop-environmental-code-20261029/ACTIVATED.md)
  uppdaterade tio butiker med en fyrfils-patch ovanpå appbas `fac3a7e021a0`
  och schedulerbas `2b65533af00d`.
  Använd faktiskt aktiv fil/image som bas vid nästa exakt granskade release.
  [Samlad aktivering](releases/beta-ica-recipes-20261028/ACTIVATED.md) innehåller
  ICA/tvånattspolicy och hela det integrerade recept-/beräkningsarbetet.
  Windowsuppgiftens registreringsbyte återstår med administratörsrättighet.
  [Senaste dashboardrättning och driftkontroll](releases/dashboard-operations-20261028/ACTIVATED.md)
  visar ICA-baspriser, Willys körjournaler och de då kvarvarande Coop-källfelen.
  Tidigare runtimefunktioner för admin bevarades med granskad exakt patchning;
  config.py är därför inte en ren kopia av main. Historiskt
  [medlemskap](releases/membership-20261021/ACTIVATED.md) och dess tre additiva
  kontotabeller består. Se även
  [basbildens granskning](releases/planner-startup-20261018/ACTIVATED.md)
  innan en ny ändring av config.py paketeras.

## Vanlig appändring

Hjälparen `scripts/beta_release.py` gör appbytet enligt samma förfarande som
den verifierade aktiveringen 2026-10-16. Den paketerar bara ändrade filer under
`backend/app/`, ovanpå den **faktiskt aktiva** appbilden. Den använder befintlig
exakt patchmatchning i `build_source_patch.py`; filerna måste bli identiska
med den valda Git-versionen. Ingen dold `.local`-katalog från en annan dator
behövs. `.local` nedan är bara nya utdata i din klon.

### 1. Hämta main, kontrollera drift och skapa paket

```powershell
git switch main
git pull --ff-only
git status --short
.venv/Scripts/python.exe -X utf8 scripts/smako_ops.py status

# Använd den granskade Git-bas som motsvarar faktiskt aktiva filer enligt senaste journalen.
.venv/Scripts/python.exe scripts/beta_release.py prepare --from-commit d3bad43b756e --commit main --workdir .local/beta-release
```

`d3bad43b756e` är appen som aktiverades 2026-11-22 19:24 UTC. Appbildens egen
grocery-kopia är äldre än Git; använd `--keep-app-grocery` om intervallet
bara innehåller grocery-Python som redan levererats till schedulern. De äldre
Coop-filerna i runtime (`price_universe_runtime.py`,
`production_price_universe_build.py`, saknad `coop_syd_base.py`) är medvetet
kvar på Git-versionen i basen och ändras inte av ett appflöde. Byt bas efter
nästa aktivering till den commit som då körs.

Arbetskopian ska vara ren; paketet läser enbart committade Git-blobbar.
`prepare` läser aktuell app via SSH, men ändrar inget på servern. Granska
`.local/beta-release/review.json`, Git-diffen och berörda testresultat.
Enbart dokumentationsändringar kräver ingen apprelease; verktyget säger då
att det saknas appändringar. Använd en ny utdatamapp för varje nytt paket.

Om aktiv fil har andra ändringar än Git-basen, om en fil tas bort eller om
beroenden, databasstruktur, grocery-kod eller körbara deploy-filer har ändrats i
intervallet, avbryts detta begränsade appflöde. Leverera då förändringen med
schedulerpatch eller full release nedan; kopiera inte hela main över den aktiva
bilden på chans.
Appbilden har en egen, äldre kopia av grocery-koden; schedulern får sina
grocery-ändringar genom schedulerpatchar. Om intervallet bara innehåller sådana
redan levererade grocery-Pythonfiler kan `prepare --keep-app-grocery` användas.
De paketeras då inte, utan listas i granskningen som kvar på appbildens version.
En ändrad appfil vars importrader mot en sådan modul har ändrats stoppar
fortfarande, liksom grocery-beroenden, data och andra filer än `.py`.
`deploy/.env.production.example` är dokumentation och paketeras aldrig.
Ändringar där ändrar inte serverns miljöfil. Appmoduler vars namn innehåller
`requirements` är vanlig appkod och ingår i den exakta filgranskningen.

### 2. Bygg och verifiera kandidatbilden

```powershell
.venv/Scripts/python.exe scripts/beta_release.py build --workdir .local/beta-release
Get-Content .local/beta-release/build.json
```

Bygget använder den pinnade aktiva basbilden och kör utan nätverk. Det verifierar
filhashar före/efter patchen, compileall och att inga andra runtimefiler ändrats.
Ingen container byts. Resultatet har exakt kandidat-image och BUILD_ID.
Serverunderlaget finns under `/opt/smako/evidence/<release-id>/`.

Bygge och aktivering kör först den gemensamma
[lagringsretentionen](storage-maintenance.md) under driftlåset. Blockerad
retention stoppar releasen med ett lokalt kvitto. Slutbilden återställer
basbildens runtimekonfiguration från ett nytt filsystemlager; upprepade
patchreleaser bygger därför inte en allt längre kedja av gamla lager.
Konfiguration och filhashar jämförs med förväntat resultat. Efter lyckat bygge
roteras egna avslutade images och oanvänd byggcache. Aktiva, rollback-,
väntande och okända images skyddas.

Verifiera dessutom kandidatens ändrade funktioner med relevanta offlineprov
och vid behov isolerad HTTP-/browsermiljö med separata data. Exempel på
importkontroll av exakt kandidatbild, med image-ID från `build.json`:

```powershell
ssh smako 'sudo -n docker run --rm --network none --read-only --entrypoint python sha256:<kandidatens-image-id> -c "from app.main import app; print(app.title)"'
```

Importkontroll ersätter inte funktionstester. Kör aldrig kandidatprov mot
produktionens skrivbara användardatabas. Ett byggfel lämnar bild/loggar på
servern för diagnos; försök inte tyst återanvända ett ofärdigt release-id.

### 3. Aktivera den verifierade kandidaten

```powershell
.venv/Scripts/python.exe scripts/beta_release.py activate --workdir .local/beta-release --checks-passed
```

Detta är det uttryckliga skrivande steget. Hjälparen kontrollerar att samma
basbild fortfarande kör och att kandidatkvittot är oförändrat, tar befintligt
driftlås, kräver lugn menytrafik, säkerhetskopierar båda SQLite-databaserna
och kontrollerar kopiorna. Den ändrar endast appens image och BUILD_ID via
ett nytt compose-override. Scheduler, proxy, volymer och övrig miljö bevaras.

Releasebackupen använder samma kompletta, roterande backupkatalog som den
dagliga backupen. Inga nya databasdubletter läggs i releaseunderlaget.
Efter aktiveringen körs underhållet igen. Ett fel där rapporteras uttryckligen
som **aktiverad app men blockerad retention**, inte som ett uteblivet appbyte.

Om låset är upptaget görs inget appbyte. Låt det ordinarie jobbet bli klart
och kör samma aktiveringskommando igen. Avbryt inte prisinsamlingen och
kringgå inte låset. Vid annan felorsak: läs fel och serverunderlag först.
Skriptet återställer föregående wrapper/appbild vid fel efter bytet och
återställer aldrig produktionsdatabaserna. Om transporten bryts är utfallet
okänt tills driftstatus och serverns `activation-success.json` har lästs;
starta inte en konkurrerande aktivering.

### 4. Verifiera och journalför

```powershell
.venv/Scripts/python.exe -X utf8 scripts/smako_ops.py status
curl.exe -fsS 'https://beta.smako.nu/ready?postal_code=22350'
curl.exe -fsS 'https://beta.smako.nu/ready?postal_code=21120'
```

På Linux/macOS används `curl`. Båda ska svara ready med kandidatens BUILD_ID.
Aktiveringssteget kontrollerar också detta och att tidigare plan-/profilrader
är bevarade. Kontrollera publicerat/laddat prismanifest och gör ett relevant
publikt användarprov: skapa meny, granska köp-/kravkontroller, återläs sparad
meny. Mät första anropet separat från uppvärmda anrop.

För uppvärmt prov krävs HTTP 200 från `/ready/preparation` med färdigt bibliotek,
rätt BUILD_ID och samtliga aktuella pris-ID:n. Väntan ligger utanför menyklockan.
Webbläsarverktyget `scripts/release_verification/complete_recipe_browser.py`
stöder `--warm-build-id <BUILD_ID>` och en `--warm-universe-id <ID>` per aktiv
kommun; båda krävs tillsammans. Hämta förväntade ID:n från den granskade
driftstatusen. Partiell/saknad rapport eller avvikande bygge får inte räknas som varmt.
Den första menyn efter gemensam förberedelse särredovisas från upprepade och nya val.

Spara en sanerad rapport under `docs/releases/<release>/`, uppdatera
`docs/HANDOFF.md` och committa/pusha till `main`. Ange kodcommit, image,
BUILD_ID, tid, tester, databevarande och kvarvarande begränsningar.
Spara aldrig full compose-miljö, cookies, privata profiler eller backupfiler i Git.

## Andra releasetyper

Ny server, databasmigrering och Windowsrelä kräver en egen plan.
Scheduler- och grocery-kodändringar får aktiveras direkt, utan separat
granskningsrelease, när relevanta tester är gröna: paketera med
`build_source_patch.py` enligt nedan, ta backup och byt schedulerbild.
Verifiera första körningen efteråt i driftstatus och journalföra som vanligt.

En samlad release måste prova faktisk schedulerbild mot ett helt inaktivt
prisbygge i berörda kommuner. Kommuterande filpatchar bevisar inte kompatibla
produktmodeller: jämför också konsumentens och byggarens fält-/köpkontrakt.
Schedulerns cronfil skapas under uppstart; invänta och verifiera färdiga jobb
innan en saknad fil betraktas som startfel. Se
[incident och korrigering](releases/beta-ica-recipes-20261028/REVIEW.md).

Befintlig paketerare är:

```powershell
.venv/Scripts/python.exe scripts/build_release.py --commit main --output .local/full-release
```

Den skapar källpaket och aktiverar inget. Utgå från aktuell drift och relevanta
delar av `deploy/compose.yaml`, `deploy/compose.release.yaml` och
`deploy/scripts/install_relay_release.ps1`. Historiska driftsättningsguider
beskriver sina dåvarande miljöer; kör inte deras daterade kommandon blint.

En avgränsad schedulerpatch kan paketeras med `scripts/build_source_patch.py`.
Den kräver nu även `--base-config <privat-inspect.json>`: exakt
`docker image inspect` för den pinnade `--base-image`. Filen ska ligga
utanför Git. Slutbilden plattas på samma sätt som appreleasen.
Om den äldre runtimefilen har CRLF men Git har LF kan `--base-files` ange
ett privat `{image, files}`-inventarium med base64-kodade originalfiler.
Endast bevisat identiskt Pythoninnehåll efter radslutsnormalisering tillåts;
byggkontrollen kräver fortfarande originalets exakta bytehash. Andra
runtimeavvikelser avvisas.
Jämför dess `Config` med paketets `IMAGE-CONFIG.json`, verifiera granskade
filhashar och kör relevanta offlineprov före aktivering.
En ny installation eller uppdaterad scheduler kör städningen vid start och
via befintliga backup-/refreshjobb; ingen extra timer installeras.

Den versionshanterade apphjälparens paketeringsspärrar och klonstart verifieras
separat vid införandet. En ny liveaktivering körs först när det finns en
faktisk granskad appändring att leverera; dokumentationsreleasen byter inte betan.
