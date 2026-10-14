# API-/state-kartläggning från faktisk kod, 2026-10-14

Bas: ad23943, ren arbetskopia i D:/Projects/Smako, ursprunglig branch perf/prepared-pricing-20261013. UI-branch ui/approved-option-3. Projektregler: AGENTS.md, docs/HANDOFF.md, CONSOLIDATION.md, DEVELOPMENT.md.

## Stack och komponenter
FastAPI/Pydantic, Python 3.12; vanlig HTML/CSS/JavaScript utan frontendramverk. /personal i backend/app/main.py serverar static/personal.html. personal.js äger show(), DOM-komponenter, sliders, readMeals(), requestPayload(), putChoices(), API-fel och resultat. complete-recipes.js äger recept-/ingrediens-/köksval och jobblivscykel. shopping-location.js äger geografi. Befintliga styles.css/personal.css/complete-recipes.css återanvänds. Streckkodsläsarens separata pnpm-bygge påverkas inte.

Befintlig same-origin fetch, gästcookie och privata revisioner i api/personal.py/services/personal_store.py behålls. Sessionslagring via SmakoRecipes.storage: smako.personal.requestDraft, smako.personal.location, smako.recipeChoices.personal. localStorage smako.personal.lastPlan innehåller plan-ID, inte privat API-svar. Inga nya auth-/CSRF-/routingflöden.

## Verkliga flöden
| Handling | Befintlig symbol/API | Data |
|---|---|---|
| Läs val | init/refreshState/putChoices i personal.js; GET /api/personal/state, /api/recipe-library | Profil, revision, lager, extravaror, biblioteksflagga. Sessionutkast och privat plan återställs. |
| Postnummer/butiker | SmakoLocation.lookup; GET /api/shopping-location?postal_code=... | Fem siffror efter mellanslagsnormalisering. eligible/unknown_postcode/ambiguous_postcode/unavailable/outside_coverage. Ingen demo-fallback. |
| Urval | updateSelection/renderStores/values i shopping-location.js | area_postal_code -> postal_code; context_id -> allowed_store_ids. Radie 1–5 km, kommun, egna val. Nullavstånd förblir okänt. Onlinepris märks. Epoch skyddar mot sena svar. |
| Smaktolkning | POST /api/personal/interpret-profile | {text} -> {profile, unresolved}; granskning före tillämpning. |
| Profil | PUT /api/personal/profile | {revision, profile, save_explicitly:true}; uttrycklig knapp. |
| Plan | requestPayload/api/SmakoRecipes.jobRequest; POST /api/plans | Befintlig PlanRequest och jobbidempotens. GET /api/plan-jobs/{id} eller /api/plan-job-requests/{requestId} för återanslutning. |
| Resultat | accept/renderPlan/renderShopping; GET /api/plans/{id} | Privat revision, #plan=..., gemensam korg. |
| Extravaror | PUT /api/personal/shopping-list, befintliga change-anrop | extras och pantry_revision bevaras. |

## Komplett konfiguration för berörd vy
Källor: models/personal.py (PortionLimits, MealSettings, MealRecipeChoices, PersonalPlanning), models/plan.py, static/personal.js och static/complete-recipes.js.

| UI/scope | Verklig representation, standard/gränser |
|---|---|
| Måltid | personal.meals[], meal_type dinner/breakfast/snack, separata objekt |
| Antal | count heltal 0–7. UI middag=5, extra inaktiva med utkast=5. Inaktiv skickas count=0/distribution={}/limits={}; receptadapter tömmer recipe_choices/max_same_base_meals. |
| Portioner | servings schema 1–8, tidigare UI 1–6. Middag=4, extra=1. Sparade 7/8 får inte klippas. |
| Kost | diet mixed/vegetarian/vegan, default mixed; vegetariskt tillåter ägg/mejeri |
| Fördelning | distribution vegetarian/chicken/fish/meat -> heltal. Utelämnad=Standard, 0=noll. Summa <= count. Vegetarian/vegan får inte ha positiva animalier; explicit vegetarian måste vara count. Ingen tyst trimning. |
| Tillagad ätbar portionsvikt | limits.min_weight_g/max_weight_g null eller 0–3000 g |
| Protein | limits.min_protein_g/max_protein_g null eller 0–300 g; tidigare UI-skala 0–100 |
| Kolhydrater | limits.min_carbs_g/max_carbs_g null eller 0–500 g; tidigare UI-skala 0–400 |
| Fett | limits.min_fat_g/max_fat_g null eller 0–300 g |
| Energi | Endast limits.max_kcal null eller 0–4000 kcal. min_kcal finns INTE. |
| Precision/standard | limits är ändliga float utan heltalssteg. Tomt=null, explicit 0 bevaras; min<=max. Sparade bråk och värden utanför gamla visningsskalor bevaras. |
| Smak | personal.profile likes/dislikes/exclusions/allergies separata listor, max 30x100 tecken. Befintlig migration sammanför gamla måltidsprofiler med synlig notis. |
| Eko | personal.organic_percent 0–100, default 0, kostnadsandel efter rabatt. organic_animals globalt och per måltid, false. |
| Överskott | personal.surplus_mode minimize/allow_larger, default minimize |
| Butikstak | max_stores UI 1–3, default 2, hela korgen; skilt från kandidater |
| Medlemskap | Befintliga medlemsprogram bevaras (redan dolda kontroller); membership_price_policy=all_advertised |
| Planeringsläge | Befintlig personlig serializer: diversity_mode=balanced, varied_budget_percent=25, strategy=optimized, purchase_planning_mode=estimated, allow_nutrition_estimates=true. Publika lägen oförändrade. |
| Recept | Personligt biblioteksläge; personlig receptstil ersattes redan 12 oktober med ingrediensantal. Återinför inte prototypens stilpresets. Publika receptlägen kvar på /. |
| Ytterligare per måltid | recipe_choices min/max_ingredients 1–40, max_active_minutes 1–180, max_total_minutes 1–2880, max_waiting_minutes 0–1440; alla nullable. max_same_base_meals 1–7 nullable. |
| Middagskök | Befintliga cuisines, cuisine_distribution free/each_selected/minimum, min_distinct_cuisines, max_same_main_protein_dinners samt tidigare uttryckliga gränser hydreras av receptadaptern. |
| Övrigt | extras, pantry_revision, sparade planer, lager/reservationer, feedback, bokföring, pris-/köpvillkor behåller befintliga ägare och flöden. |

Dialoger får avbrytbart utkast; Klart applicerar endast lokalt. Öppning/Avbryt/Escape ska inte skriva API eller session. Smaktolkning får inte tyst ersätta hårda krav. Serializern återanvänds; inga godtyckliga inkommande JSON-nycklar masskopieras.

## Luckor och verifiering
- Backend saknar min energi: behåll maxfältet, inget påhittat API-fält. Ett energiminimum skulle kräva separat backendändring.
- Högre giltiga protein-/kolhydrat-/portionsvärden ska bevaras. Visningsskala utökas vid behov.
- Personlig receptstil är redan ersatt; aktuella ingrediens-/tidsfält bevaras.
- node --check, Python 3.12 pytest (Chromium/WebKit och API-kontrakt), Ruff, compileall, git diff --check. Faktiska resultat, request-paritet, backendmiljö och skärmbilder redovisas efter körning i IMPLEMENTATION_REPORT.md. Prototyptester räknas inte som backendverifiering.
