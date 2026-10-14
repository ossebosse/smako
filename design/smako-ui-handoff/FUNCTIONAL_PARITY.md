# Funktionsparitet: inget ska försvinna vid UI-bytet
Codex ska fylla i sista kolumnen med verklig kodreferens och test. Tabellen är miniminivå; den är inte en uttömmande API-inventering. Screenshots under `references/current` är källa för visat beteende, inte schema för backendfält.

| ID | Funktion/betydelse att bevara | Visuellt underlag | Verifierad kod och test (fyll i) |
|---|---|---|---|
| F01 | Postnummer, hitta butiker, ungefärligt närhets-/täckningskrav | IMG_2302/2311 | shopping-location.js lookup; test_postal_locations + browser location-fall; verkligt Malmö-API |
| F02 | Radie från referenspunkt; inte exakt adress eller körsträcka | IMG_2303/2304 | shopping-location.js updateSelection; test_location_radius_municipality_manual_and_invalidation |
| F03 | Kommunurval, radieurval och egna butiksval | IMG_2302–2304 | shopping-location.js values/renderStores; browser location-fall och actual API |
| F04 | Butiker utan position endast där stödet medger det; aldrig 0 km som ersättning | IMG_2302/2304 | shopping-location.js nullkontroll; browser location-fall, test_postal_locations |
| F05 | Onlinepriser separat från fysiska butikspriser | IMG_2302/2304 | shopping-location.js price_scope_label; befintlig renderShopping bevarad |
| F06 | Verkliga butiks-ID:n, antal kandidater, valda/ej valda butiker | IMG_2303/2304 | shopping-location.js context_id/allowed_store_ids; request-paritet och Malmö-API |
| F07 | Middagsantal; bild visar 0–7 och exemplet 5 | IMG_2305/2313 | personal.js måltidsloop; choice-controls.js slider; primary/default-request + oberoende måltidstest |
| F08 | Portioner per rätt; bild visar 1–6 och exemplet 4 | IMG_2305/2313 | MealSettings.servings 1–8; högre sparade värden bevaras; test_saved_limits_above_old_scale_and_servings_are_preserved |
| F09 | Max inköpsställen för HELA korgen; bild 1–3 | IMG_2305 | requestPayload max_stores; faktisk gemensam korg med två butiker |
| F10 | Frukost/mellanmål oberoende aktivering i Extraval | IMG_2307/2312 + användarens krav | syncMeal/enable-breakfast/enable-snack; primary/default-request + nio dialoger |
| F11 | Frukost/mellanmål har egna antal/portioner och samma tre dialoger som middag | IMG_2313 + användarens krav | Gemensam måltidsloop och SmakoChoiceUI.dialog; test_all_nine_dialogs_are_independent_transactional_and_accessible |
| F12 | Näringsfält per måltid; egna min/max; standard; full fältlista | IMG_2314 | PortionLimits + interval; test_ranges_validation_positions_precision_zero_and_reset; energi har bara max enligt befintligt schema |
| F13 | Protein 0–100 g och kolhydrater 0–400 g synliga; övriga fält kräver kodinventering | IMG_2314 | Visningsskalor protein100/kolhydrater400; schema300/500 bevarat och testat |
| F14 | Portionsvikt avser tillagad, ätbar uppskattad vikt per portion | IMG_2315 | PortionLimits vikt0–3000; vikttext bevarad; drag/fokus-test |
| F15 | Fördelningens kostval och samtliga kategorier; Standard är inte 0 | IMG_2317 | proteinNames/diet/readMeals; test_distribution_conflict_preserves_explicit_values |
| F16 | Antalsbudget: summa egna kategorier och återstående platser | IMG_2317 | distributionSync utan trimning; test_distribution_conflict_preserves_explicit_values |
| F17 | Smaktext + Tolka och granska + manuella strukturerade fält | IMG_2307/2308/2312 | interpret-profile, granskningsdialog, profileFields; test_profile_review_does_not_replace_confirmed_hard_requirements |
| F18 | Gillar/föredrar, ogillar som mjukt önskemål, uteslutningar och allergier som separata hårda krav | IMG_2308 + skärmbildens rubriker | profile()/putProfile(); gransknings- och migreringstester |
| F19 | Befintliga receptlägen; visad receptstil gäller middagar | IMG_2309 | complete-recipes.js oförändrad; aktuell personlig ingrediensmodell och äldre publika lägen; ingredient_interval/old_recipe_styles-tester |
| F20 | Planeringsmål Billigast/Balanserad/Varierad där de redan finns | Text i IMG_2309 | personlig balanced-policy oförändrad, publika mål orörda; request-paritet |
| F21 | Minsta verifierade ekologiska KOSTNADSandel efter rabatt, 0–100 % | IMG_2309 | organic-percent; request-paritet; PersonalPlanning/Pydantic och befintlig planner-testsvit |
| F22 | Eko: mat-extravaror ingår; skafferi, avgifter, icke-livsmedel exkluderas; okänt räknas inte positivt | IMG_2309/2310 | Befintlig eko-definition i personal.html och renderPlan oförändrad; personal_planning_v2-tester |
| F23 | Ekologiskt för alla animalier inklusive ägg och mejeri, separat krav | IMG_2309 | organic-animals globalt och per måltid; request-paritet |
| F24 | Överskottsstrategi och förklaringar om hela förpackningar, extra mängd/merkostnad, okänd hållbarhet | IMG_2310 | surplus-mode och befintliga resultattexter; request-paritet, booked_revisions |
| F25 | Skapa plan OCH inköpslista med gemensam korg för samtliga aktiva måltider | IMG_2310 + användarens krav | POST /api/plans och befintlig jobblivscykel; verklig tre-måltidsplan/korg och godkänd checkout-audit |
| F26 | Tidigare planering, feedback, integritet och radera mina data | IMG_2304/2310/2311 | Footer/navigation oförändrade destinationer; befintligt resultat- och bokföringsflöde kvar |
| F27 | Inläsning och befintlig persistens av användarval, validering/fel/timeout/auth | Aktuell kod krävs | requestDraft/putChoices, same-origin cookie/API; browser migrering/paritet/401/403/500 och identisk verklig GET |
| F28 | Exakta vs uppskattade köppriser, köp-/kampanjvillkor och befintliga pris-/köpregler nedströms | Aktuell kod krävs; inte nytt UI-beteende | Backend/optimizer/prisinsamling helt orörda; 84 backendtester och verklig checkout-audit |
| F29 | Ytterligare fält/enumvärden/länkar som saknas i bilderna | Inventera aktuell kod | API_MAPPING.md full inventering; ingrediens/tid/kök, skafferi, extravaror, medlemsprogram, jobbåteranslutning kvar; request-paritet |

## Krav på diff
Inga oannonserade ändringar i backendkontrakt, defaultvärden, begränsningar, optimeringsmål, prisinsamling eller schemaläggning. Befintliga extra fält får inte tappas genom att det nya UI:t bygger en mindre payload från noll.

En ofullständig skiss motiverar inte att fungerande inställningar tas bort. Dokumentera placering och test för varje existerande fält före slutförande.

Testnamn utan filprefix avser `backend/tests/test_personal_choices_browser.py`. Faktiskt körda kommandon och begränsningar finns i `IMPLEMENTATION_REPORT.md`. Originalbilderna bevisar inte integration.
