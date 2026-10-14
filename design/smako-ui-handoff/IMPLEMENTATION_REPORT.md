> Uppdatering 2026-10-14: efter separat användarbeslut är UI:t nu aktiverat på betan. Se [aktiveringsrapport och liveverifiering](../../docs/releases/ui-option3-20261014/ACTIVATED.md). Ursprunglig lokal leverans nedan beskriver läget före aktiveringen.

# Implementerat Smako-UI · alternativ 3

2026-10-14. Implementation i befintliga `/personal` i `D:/Projects/Smako`.
Branch: `ui/approved-option-3`, bas `ad23943`, implementation `ff24180`. Arbetskopian var ren vid start.
Inga andra lokala ändringar återställdes, städades eller stashades.
Ingen push, deployment, produktionsprisinsamling eller schemaändring i drift.

## Vad som ändrats

| Fil | Ändring |
|---|---|
| `backend/app/static/personal.html` | Befintlig konfiguration får arbetsyta, sammanfattning, genvägar och tydligare Extraval. Samma route/navigation/länkar. |
| `backend/app/static/personal.js` | Gemensamma måltidskontroller, egna dialogutkast, konflikt utan trimning, sammanfattning, explicit granskning av smakförslag med bibehållna hårda krav. Befintlig request-/resultatadapter återanvänds. |
| `backend/app/static/choice-controls.js` | Återanvändbara stegare, numeriska intervall med två handtag, validering, Standard/null, dialoger med Klart/Avbryt/Escape/kryss, fokusfälla/återfokus och scrollås. Inga API-anrop. |
| `backend/app/static/choices.css` | Cremevit/grön design, serifrubriker, rundade vita kort, kompakt mobilvy och desktopkolumn. Scope till personlig konfiguration/dialoger; befintliga resultatstilar kvar. |
| `backend/app/static/service-worker.js` | Versionerat statiskt skal uppdaterat till aktuella filreferenser inklusive nya UI-filer. API, priser och privata svar cachelagras fortsatt inte. |
| `backend/tests/test_personal_choices_browser.py` | Chromium/WebKit-regressioner och faktisk före/efter-requestjämförelse. Äldre testförväntningar om tyst klippning och direkt sparad Escape ersatta med de godkända kraven. |
| `docs/HANDOFF.md` | Kort lokal överlämning, uttryckligen inte produktionsrelease. |
| `design/smako-ui-handoff/` | Originalpaket, ifylld API_MAPPING/FUNCTIONAL_PARITY, denna rapport och nya integrationsbilder. |

Originalpaketets `MANIFEST.sha256` beskriver den mottagna ZIP-filen. Det är inte
ett nytt hashmanifest för de kompletterade kartläggningsfilerna.

## Bevarad funktionalitet och API

Frukost och mellanmål aktiveras oberoende och har samma fullständiga kontroller
som middag, i ordningen Middag–Frukost–Mellanmål. Av/på behåller sessionens utkast.
Alla nio måltid/dialog-kombinationer provas. Egna fördelningar ändras inte när
antalet minskas. Tomma gränser och explicit noll har olika requestvärden.
Bråk och giltiga äldre protein-/kolhydrat-/portionsvärden bevaras.

Befintligt postnummer-/kommun-/radie-/butiksurval, verkliga context-ID:n,
onlineprismärkning, butikstak för hela korgen, smakfält, ingrediens-/tids-/köksval,
eko-definition, överskott, skafferi, extravaror, historik, feedback och
integritetslänkar finns kvar. Komplett inventering: `API_MAPPING.md` och
`FUNCTIONAL_PARITY.md`.

Återanvända anrop: GET `/api/personal/state`, `/api/recipe-library`,
`/api/shopping-location`, POST `/api/personal/interpret-profile`, PUT
`/api/personal/profile`, POST `/api/plans`, befintliga jobbstatusanrop och GET
`/api/plans/{id}`. Befintlig same-origin gästcookie, revisionskontroll och
jobbidempotens behålls. Inga nya endpoints eller backendändringar.

Personlig receptstil hade redan ersatts av ingrediensantal i aktuell kod;
den funktionen behålls. Äldre publika receptlägen och planeringsmål på `/`
är orörda. Snabbknapparna är endast genvägar till befintliga inställningar.

## Körda kontroller

Alla Pythonkommandon använder `.venv/Scripts/python.exe` (Python 3.12) och
`PYTHON_DOTENV_DISABLED=1`. Browserproven använder uttryckliga API-fixtures;
de är separata från det verkliga backendprovet nedan.

- `-m pytest backend/tests/test_personal_choices_browser.py backend/tests/test_pwa_readiness.py backend/tests/test_consumer_static_ui.py -q`: **57 godkända** i slutkörningen, varav 40 personliga browser-/kontraktsfall. Tillsammans med de två tillagda nollmiddags-/mellanmålsfallen: **59 godkända UI/static-fall**.
- `-m pytest backend/tests/test_personal_choices_browser.py -k snack_without -q`: 2 godkända fall i Chromium/WebKit.
- `-m pytest backend/tests/test_personal_planning_v2.py backend/tests/test_personal_booked_revisions.py backend/tests/test_postal_locations.py backend/tests/test_recipe_library.py backend/tests/test_plan_jobs.py -q`: **84 godkända**.
- `-m ruff check backend/tests/test_personal_choices_browser.py`: godkänd.
- `-m compileall -q backend/app backend/tests/test_personal_choices_browser.py`: godkänd.
- `node --check` på personal.js, choice-controls.js och service-worker.js: godkända.
- `git diff --check`: godkänd. Endast information om Git-konfigurerad LF/CRLF-konvertering.

Request-paritet kör den tidigare riktiga personal.html/personal.js från `ad23943`
och det nya UI:t mot samma testdata, och jämför **hela payloaden**. Standardval
och en konfiguration med alla tre måltider, fördelning, decimalgräns, eko,
medlemsprogram, allergi, ingrediens-/tidsgränser och köksval är identiska.
Fyra jämförelser (två konfigurationer × två browsermotorer) passerar.

Browserfallen täcker även 401/403/500 utan mockreserv, bevarade val efter fel,
postnummersvar i fel ordning, radius/kommun/egna butiker, alla nio dialoger,
Avbryt/kryss/Escape, återställning, noll kontra Standard, intervallfel, exakta
10/30-procentpositioner, drag/keyboard, fokusrundgång och återfokus.
En upptäckt WebKit-klickförlust vid textnodsuppdatering samt fokus ut till
browserramen är rättade och omtestade.

Utökad kontroll av `test_public_beta_ui.py` visar två **befintliga basfel**:
`test_beta_geography_and_online_scope_are_explicit` förväntar äldre Lundtext,
och `test_planner_fails_closed_with_swedish_readiness_copy` förväntar ett äldre
literal för `/ready`. Båda reproducerades mot oförändrade index.html/app.js från
`ad23943`. Dessa filer är inte ändrade. Fullständig repository-testsvit har inte körts.

## Verklig backend i isolerad utvecklingsmiljö

Faktiska FastAPI-appen serverade den implementerade frontendkoden på loopback.
En kvarhållen verklig Malmö-PriceUniverse lästes från
`.local/ops-followup-20261013/inputs/universe.json`. Se artifact-hash i
`implementation/backend-verification.json`. Pris-/färskhetsprov använde uttrycklig
testklocka **2026-10-13 07:19:51 UTC**, utan ändrade kvalitetsgränser. Separata
privata testdatabaser under `.local/ui-option3/`; inga användarprofiler kopierades.
Utgående nätverksanslutningar spärrades. Inga mockproviders eller HTTP-intercept
användes i detta prov. Levererade granskade/official produktfakta och det verkliga
prisunderlaget användes; hela produktionskälldatabasen kopierades inte.

Första försöket identifierade saknat schema i den nya testdatabasen. Befintlig
`create_schema` initierade den isolerade databasen, utan backendkodändring.
Därefter lyckades UI-flödet:

- Verklig postnummersökning/kommunurval för Malmö.
- **Exakt en** POST för en middag, en frukost och ett mellanmål, en portion vardera.
- Färdig plan efter cirka **71,6 s**, gemensam korg i två butiker.
- Checkout-audit **PASS**, mängder och totaler avstämda; sju ingrediensbehov,
  inga okända köpantal i den valda korgen.
- GET av den sparade planen två gånger gav identisk plan.
- Inga JavaScript-fel. Request och avgränsad resultatrapport finns i `implementation/`.

Lokala verifieringsskript och testlagring ligger i `.local/ui-option3/`.
Detta är ett historiskt återspelningsprov, inte en verifiering av dagens
produktionspriser eller samtliga kombinationer av hårda krav.

## Skärmbilder och visuell kontroll

Nya bilder från **implementerad Smako**, inte från prototypen:

- `implementation/desktop-initial.png`, `mobile-initial.png`
- `implementation/desktop-three-meals.png`, `mobile-three-meals.png`
- `implementation/desktop-extras.png`, `mobile-extras.png`
- `implementation/desktop-distribution.png`, `mobile-distribution.png`
- `implementation/desktop-weight.png`, `mobile-weight.png`
- `implementation/desktop-nutrition.png`, `mobile-nutrition.png`
- `implementation/backend-result-mobile.png`

Chromium-layout verifierad vid **320, 375, 390, 430, 768 och 1440 px** utan
horisontell sidscroll. Dialoger även vid 320×500 och 390×420, med åtkomlig
sidfot, intern scroll och låst bakgrund. CSS-textförstoring 200 % och reducerad
rörelse kontrollerades; bilder på mobil och desktop granskades visuellt.

## Kvarvarande verifieringsgränser

- Fysisk iPhone/iOS Safari med skärmtangentbord och verkliga safe areas är inte
  testad. Playwright WebKit är browsermotortestning, inte fysisk iPhone-verifiering.
- Ingen automatiserad full WCAG-audit eller manuell skärmläsarsession har körts.
  Etiketter, synlig fokusram, tangentbord och dialogfokus är testade.
- Backend har endast `max_kcal`; ett energiminimum kräver separat kontrakts- och
  affärslogikändring. Det nya UI:t behåller max energi, utan fiktivt minfält.
- Liveproduktionsbackend och full källa-/allergimatris är inte omtestade.
  Sparade produktionsval eller pris-/schemaläggnings-/optimeringskod har inte ändrats.
