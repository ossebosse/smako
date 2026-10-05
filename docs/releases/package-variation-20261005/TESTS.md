# Slutprov och prestandabevis

Testimagen `sha256:30de1272e6d2896714f9e815f7d6537019fc43548c4a55767a812c379ebb1b0a` är byggd från paketet för runtime `82de80e1ae898e2ab005c16c8d95e6670898be93`. Alla här kallade nya runtimeprov kördes i isolerad miljö med fryst PriceUniverse, två CPU, 3 GiB, samma beroenden och separat planlagring. Betan och dess användardata har inte skrivits.

## Kod- och beräkningsprov

Hela `backend/tests` passerade lokalt på slutlig runtime med exitkod 0. Ett äldre test för intern cacheträffsstatistik förväntade den tidigare delvägen; efter kontroll av identiskt korgresultat ändrades bara dess diagnosförväntan för den nu använda exakta delmängdsvektorn. Det riktade provet och därefter hela sviten passerade. Ruff på de modifierade test-/webbprovfilerna, Python-kompilering och tidigare riktade variations-/faktaprov passerade. Den oberoende slutliga närings- och checkout/audit-vägen kördes i varje R0–R3-plan; alla redovisade planer har `PASS` i audit.

Namngivna regressioner täcker heltalsavrundning och paketgräns (`test_basket_calculator`), delat veckobehov (`test_basket_auditor`, `test_menu_optimizer`), medlems- och köpgränser (`test_membership_candidate_generation`, `test_basket_calculator`), produktidentitet och butikskanal (`test_supplier_image_gtin_facts`, `test_complete_recipe_supplier_facts`), oberoende näringskontroll (`test_complete_recipe_integration`) samt uttryckliga köks- och proteinkrav (`test_recipe_week_variation`). Blandade storlekar av **olika** SKU är fortfarande en öppen funktionspunkt och kallas därför inte godkänd i denna testmatris.

Den fasta R0-, R1- och R2-menyn kördes var för sig, liksom fri R1/R2 och de två R3-valen. **Fri R0** är den sparade HTTP-replayen från föregående receptleverans, återanvänd därför att dess kod och begäran är utgångspunkten; den kallas inte en ny körning. `MENUS.json` jämför varje recept-ID, version, portionsantal och råmängd; de är identiska i R0–R2. Priskällans SHA-256 och alla 2 233 råfiler verifierades före ändring. Den felmärkta första fasta R2-resultatkatalogen avvisades efter att körningen gett `FileExistsError`; ett nytt unikt `R2-82de-fixed`-prov kördes och är det enda som används i rapporten. [COMPARISON.json](COMPARISON.json) redovisar exakt produktbyte och separata variationsmenyer. [PERFORMANCE.json](PERFORMANCE.json) behåller kalla/varma CPU-, väggtids- och minnesmätningar.

Tre kalla R2-fria processer: 80,92, 80,72, 81,83 s; median **80,92 s**. Tre varma **nyberäkningar**, inte återhämtade sparade planer: 52,95, 54,55, 54,49 s; median **54,49 s**. Högsta RSS 2 186 776 KiB under dessa sex prov. Föregående jämförbara kandidat hade 79,25 s kall och 54,80 s varm median. R1 med gamla fakta på slutimagen gav 79,91 s kall och 54,03 s varm i ett enstaka par, inte tre mätningar.

## Hela webbresan

Webbläsarproven startade vanliga HTTP-jobb i Chromium eller WebKit med mobil vy. Varje prov dubbelklickade, krävde exakt ett dyrt POST-jobb, laddade om under pågående generering, kontrollerade sparad GET, ägarisolering och återrendering. Fullproven gjorde dessutom receptbyte, uttrycklig omräkning, alla revisions-GET och appomstart. Klicktid mäts från klick till renderat resultat; den är inte samma sak som kall backendprocess eller varm nyberäkning. [BROWSER-EVIDENCE.json](BROWSER-EVIDENCE.json) har kompakt maskinbevis och pekar på bevarade rårapporter.

| Fall | Klick till resultat | Utfall | Revisioner och återstart |
| --- | ---: | --- | --- |
| Chromium, publikt, fritt | 70,72 s | PASS | Sparad GET och ägarisolering |
| WebKit, personligt, fritt | 61,56 s | PASS | Sparad GET och ägarisolering |
| Chromium, publikt, ”Mer omväxling” | 58,55 s | PASS | Tre revisioner, receptbyte, omräkning och identisk läsning efter appomstart |
| WebKit, personligt, ett av varje kök, funktionsåtergång | 54,49 s | **FAIL i strikt webbläsarprov** | Alla tre revisioner kunde läsas efter omstart och med skapandekontroller avstängda; se fel nedan |

WebKit-felet är bevarat. Vid avsiktlig omladdning 2026-10-05 21:44:26.364396 UTC rapporterade WebKit ett `Fetch API cannot load ... /api/plan-jobs/... due to access control checks` från status-`fetch` i `complete-recipes.js:331`, tidsstämplat 21:44:26.338773 UTC, cirka 26 ms före navigationen. Det är **förenligt med ett avbrutet statusanrop vid navigation**, men detta är en orsakshypotes och ingen bevisad fix. Jobbet slutade med HTTP 201, omräkning och revisioner lyckades, och funktionsåtergångens sparade recept var läsbara. Det strikta provet markerades ändå FAIL eftersom ett sidfel inträffade. Ingen omkörning har använts för att dölja detta. Det tidigare intermittenta WebKit-felet kvarstår som öppet ärende.

Den testade funktionsåtergången är feature-flag-off på **samma** runtimeimage, följt av GET för flera revisioner av den nya planen. Läsning av nya variationsplaner med den föregående **binären** är inte bevisad; ett faktiskt imagebyte till äldre runtime kräver separat kompatibilitetsprov med kopia av aktuell planlagring. [ACTIVATION.md](ACTIVATION.md) ställer det villkoret.

Slutimagen läste dessutom **11 planrevisioner från föregående runtime** via deras ursprungliga ägarsessioner, från en kopia av dess isolerade planlagring. Alla GET gav 200 och SHA-256 för begäran, recept, korg, personlig plan och revision var identisk med den tidigare sparade kontrollen. Ingen av de äldre begärandena fick nya variationsfält vid läsning. [OLD-PLAN-READBACK.json](OLD-PLAN-READBACK.json) har varje utfall utan privata sessionstoken. Detta provar ny binär som läser gamla planer; motsatt riktning kvarstår okvalificerad.

## Representativa HTTP-profiler och kötid

Nio slutliga individuella profiler kördes via ordinarie HTTP-flöde. Det här är enstaka förfrågningstider, skilda från backendmedianer och webbläsarklick. [HTTP-MATRIX.json](HTTP-MATRIX.json) behåller begäran, utfall, tider och sparad rårapportreferens. Äldre 15/20-profiler kördes med oförändrade 40/30/20 g-krav.

| Profil | Status | Hela inköpet | HTTP-tid |
| --- | --- | ---: | ---: |
| Ett grekiskt kök, två portioner | complete | 682,23 kr | 30,75 s |
| Grekiskt med faktiskt skafferi | complete | 665,33 kr | 21,51 s |
| Indiskt, vegetarisk kost | stopped inom begränsad sökning | — | 18,34 s |
| Blandad kost, 40 g protein | complete | 738,17 kr | 60,03 s |
| Bred Varierad | complete | 590,08 kr | 122,96 s |
| Äldre 15/20 original, exakt köp | complete | 430,26 kr | 60,49 s |
| Äldre 15/20 original, uppskattat köp | complete | 430,26 kr | 67,96 s |
| Äldre 15/20 plus, exakt köp | complete | 430,26 kr | 59,20 s |
| Äldre 15/20 plus, uppskattat köp | complete | 430,26 kr | 62,48 s |

Den indiska vegetariska profilen stannar som tidigare inom begränsad sökning; det är inte ett bevis på global omöjlighet. Ett separat vanligt HTTP-POST med tre middagar och uttryckligt krav på alla fem valda kök gav 422 och svenskt fel om köksfördelning före jobbskapande. Samma kombination får fältfel direkt i formuläret.

Första samtidighetsförsöket accepterade tre separata jobb och återanvände varderas jobb-ID vid dubbelstart, men testklientens status-GET gav `socket hang up`; dess klientkötid kan inte användas. Containern var fortfarande igång, `OOMKilled=false`, och arbetade vidare. Felet är bevarat i [CONCURRENCY.json](CONCURRENCY.json). Dessa jobb avslutades före omkörningen.

Omkörningen med tre nya oberoende ägare **PASS**. Samtliga dubbelstarter återanvände samma jobb, främmande jobb gav 404, främmande plan gav 403 och varje ägare kunde läsa sin egen färdiga plan. Ingen statuspoll i omkörningen behövde transportåterhämtning. Klickfri generering inklusive kö blev 64,87, 126,18 och 185,65 s; färdig GET tog 1,91, 1,90 respektive 1,31 s och är inte en nyberäkning. Serverns uppmätta kötid var 0,00, 59,75 och 120,87 s; varje klient fick samma 741,15-kronorsmeny. Högsta serverrapporterade RSS var 2 662 308 KiB inom 3 GiB-gränsen. Det första transportfelet är fortfarande öppet som anmärkning, inte bortförklarat av omkörningen.
