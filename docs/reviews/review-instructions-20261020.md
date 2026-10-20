# Granskningsinstruktion till Codex: receptskalning, 2026-10-20

Skriven av Claude på ägarens begäran. Kompletterar commitmeddelandena och
[rapporten](recipe-scaling-20261019.md); upprepar dem inte. Ingenting är aktiverat
i produktion. Granskningen beställer inte heller aktivering, prisinsamling eller
nya produktionsrecept.

## 0. Grenar och ursprung

| Gren | Bas | Commits | Innehåll |
| --- | --- | ---: | --- |
| `fix/full-library-reference-contract` | `00123b7` | 1 (`9e6b7a9`) | Kvarvarande P2 från 2026-10-18: `--uncapped-reference` kräver explicita sökinställningar |
| `perf/recipe-scaling-20261019` | `00123b7` | 12 | Skalningsuppgiften steg 1–4 och denna instruktion |

Claude arbetade i en molnmiljö utan pushbehörighet. Commitarna överfördes som
`git am`-patchar till ägarens klon `C:\Users\ossia\projects\smako` och pushades
därifrån. Committern är därför ”Claude” men SHA:erna skiljer sig från Claudes
egna kopior; trädhasharna verifierades lika. SHA:er i rapporten avser de pushade
commitarna. Klonen på laptopen är inte den permanenta roten `D:\Projects\Smako`.

Laptopklonens arbetsträd har CRLF och Windows-git med `core.autocrlf=true`.
Linux-git utan den inställningen visar alla filer som ändrade; det är inte
innehållsändringar. Där finns även en stash `crlf-noise-before-pull-20261019`
som bara innehåller sådana radslut och kan tas bort.

## 1. Sammanslagning: kontraktet måste även kräva `substitution=0`

Grenarna rör samma fil, `backend/scripts/planner_acceptance_matrix.py`:

- fix-grenen lägger till `FULL_LIBRARY_SEARCH_LIMITS = {"seed": 0, "refinement": 0,
  "seed_variant_shortlist": False}` och `validate_full_library_reference`;
- perf-grenen lägger till `--substitution-limit`, låter `--uncapped` sätta
  `library_substitution_pool_limit=0` och skriver `search_limits["substitution"]`.

Vid sammanslagning ska `FULL_LIBRARY_SEARCH_LIMITS` även innehålla
`"substitution": 0` och kontraktet versionsmärkas `-v2`. En referens utan
nyckeln ska avvisas med samma regel som en saknad `seed_variant_shortlist`:
den skapades när substitutionen var obegränsad, men det framgår inte av
rapporten. Lägg till ett test för detta och kontrollera att `--uncapped` och
`--substitution-limit` inte kan kombineras (perf-grenen avvisar redan det).
`docs/HANDOFF.md` får en enkel textkonflikt överst.

## 2. Granska koden

Läs commitarna i ordning. Utöver det som står i dem, kontrollera särskilt:

1. **Parlikhet vid behov** (`9653e29`). `LazyPairwiseSimilarities.__iter__`
   och `values()` beräknar alla par; finns någon anropare utanför testerna som
   itererar? `DiversityConstraints.__post_init__` hoppar nu över
   intervallkontrollen för den lata typen. Är det rätt att ett värde utanför
   [0, 1] upptäcks först vid uppslag?
2. **Behovsradsmallar** (`c638ee6`). Mallarna är grunda kopior. Muterar
   `basket()` eller `_check_final` något *inuti* en rad (listor, profilobjekt)
   och inte bara toppnivånycklar? `_model_json` och `_merged_profile`
   memoiserar per objekt-id med stark referens; muteras `meal`,
   `spec.profile` eller `recipe_preferences` någonstans under ett anrop?
3. **Delad produktupplösning** (`c638ee6`). Detta bryter avsiktligt mot den
   tidigare principen ”ingenting överlever till ett annat anrop”, för ren
   produktupplösning. Pröva att scope-nyckeln i
   `planner_shared_cache.scope_key` täcker *allt* `resolve` läser: gå igenom
   `resolve` rad för rad (`self.view`, `self.store_ids`, `self.facts`,
   `self.declared_*`, `self.index`, `self.queries`, `self.user`,
   `self.pricing_date`, `self.request.purchase_planning_mode`,
   `self.complete`, `self.service.matcher`). Bedöm också
   - integritet: nyckeln innehåller allergiprofilens JSON; posten används bara
     av exakt samma nyckel, men lever i processens minne mellan konton;
   - trådsäkerhet med flera samtidiga planerare i samma process;
   - om `facts_version` alltid är en innehållshash i produktion
     (`FactsCollection.version` sätts utifrån);
   - minne i drift: 4 scope × 32 768 poster; uppmätt +20 MB vid 1 000 recept.
   Avstängning: `SMAKO_PLANNER_SHARED_RESOLUTION=0`. Om principen inte ska
   brytas: behåll endast den anropslokala delen och mät om.
4. **Substitutionstaket** (`99e2d62`, `1d2e620`, `f88dfd6`). Det är en heuristik
   som ägaren godkände 2026-10-20. Rangordningen återanvänder
   `library_seed_cap` men *utan* variantlistan, så att en generation inom taket
   prövas helt. Kontrollera att `_select_library_options` med tomma grupper
   inte ändrar seed-vägen. Notera att taket är ett absolut antal per
   måltidstyp och inte skalar med generationens storlek.
5. **Importgränsen** (`ed76088`). Verifiera att inget redan utfärdat paket
   i produktionsbiblioteket ligger nära 16 MiB och att `author --import`
   rapporterar felet begripligt.

## 3. Upprepa mätningarna i referensmiljön

Claudes miljö: 2 CPU, 7 GiB minne, utan cgroup-gräns, cirka 15–20 % långsammare
än serverns referens. Spridningen mellan körtillfällen var upp till 20 % (Malmö
222 recept: 40,5 s ena kvällen, 33,1 s nästa morgon, samma kodväg, samma korgar).
Tiderna i rapporten är därför vägledande; priser och hashar är det som ska
stämma exakt.

Indata: `smako-followup-public-data-20261018.zip` (SHA-256 `d3a93b88…c774`) från
din egen leverans, uppackad under `.local/followup-review-20261018/server-data/`.
Klocka `2026-10-18T05:12:49.467392+00:00`.

Testbibliotek, alltid i en isolerad worktree, aldrig i main-checkouten:

```bash
export PYTHONPATH=backend:. PYTHON_DOTENV_DISABLED=1
git worktree add --detach ../lib-1000 HEAD && cd ../lib-1000
python reports/recipe-scaling-20261019/generate_library.py --recipes 778 --output d1000.json
python -m app.services.meal_library_cli author d1000.json --output p1000.json --report a1000.json --import --prepare 4
# 2 000 recept: generera 1778, dela i recept 0–777 och 778–1777 (två pack_id),
# importera i den ordningen. Ett enda paket överstiger 16 MiB.
```

Jämför manifest-, utkast- och pakethashar med
[library-manifest.json](recipe-scaling-20261019/library-manifest.json).

Mät i serverns 2 CPU / 3 GiB-container, en process per rad, båda körordningarna:

- standard, 222/1 000/2 000 recept, Lund och Malmö, standardinställning (tak 160)
  och `--substitution-limit 0`;
- alla sju profiler vid 1 000 recept med `reports/recipe-scaling-20261019/limit_sweep.py`
  (`160,0`) och jämför med
  [substitution-limit-sweep.json](recipe-scaling-20261019/substitution-limit-sweep.json);
- full offline-svit och GitHub-CI med webbläsartester. Claudes miljö kunde inte
  starta Playwrights webbläsare; 41 webbläsartester är alltså inte körda.

## 4. Tre öppna frågor att utreda

### 4.1 Större bibliotek ger dyrare meny (Lund 2 000: 518,55 kr; 1 000: 497,19 kr)

Gäller även med `--substitution-limit 0`, så det är inte taket. 2 000-biblioteket
innehåller samma 778 syntetiska recept som 1 000-biblioteket (samma innehåll,
annat `pack_id`) plus 1 000 till, importerade som generation 12 och 13.

Gör så här:

1. Ta 1 000-vinnarens fem recept (rapportens `measurements.json`, raden
   `lund/s160_1000`) och prissätt exakt den menyn i 2 000-biblioteket med
   `PersonalPlanner.basket(slots, final=True)` och samma indata. Blir det
   497,19 kr och klarar audit, har sökningen bevisligen missat en giltig och
   billigare meny.
2. Ta reda på var vinnaren försvinner. `search_phases.py` visar korgar per fas.
   Troliga orsaker: förfiningens tak 90 väljer andra recept ur en pool på 1 967,
   variantlistan, eller att substitutionen går generation för generation och
   lämnar en annan startpunkt. Kör samma prov med `--uncapped` (se 4.3).
3. `PersonalPlanner.create` har redan `retain_library_comparison`, som
   omplanerar med föregående biblioteksgeneration och behåller den billigare.
   Den hoppas över när den inkrementella sökningen har hanterat biblioteket
   (`_library_search_handled`). Avgör om det är avsiktligt och om
   uppgiftens krav (”behåll en tidigare giltig kandidat … under samma aktuella
   priser”) ska uppfyllas där, och till vilken kostnad. En full extra planering
   per anrop fördubblar tiden; ett billigare alternativ är att i sökningen
   behålla föregående generations vinnare som kandidat och kvalificera om den.
   Kräver ägarbeslut om tidskostnaden.

### 4.2 Minne: Malmö 2 000 recept 2,96 GB peak RSS

Gränsen är 3 GiB (3,22 GB). Utan cgroup-gräns i Claudes miljö är det okänt om
processen hade klarat sig eller dödats.

1. Kör Malmö standard vid 2 000 i 3 GiB-containern. Notera OOM, swap och tid.
2. Mät vad som växer med biblioteket med `tracemalloc` (topp 30 per fil/rad)
   vid 1 000 och 2 000 recept, efter kvalificering och efter veckosökningen.
   Misstänkta: `qualified_results` och den lokala korgcachen (256 poster med
   hela korgar), `variant_search_evidence` (nu obegränsad per anrop, se
   `5468645`), `RecipeComputationCache` (1 024), `normalized_recipe_rows`
   (512), behovsradsmallarna (4 096), förberedelsecachen (`recipe_prepared`),
   produktspåret och den delade upplösningen.
3. Jämför peak RSS med `SMAKO_PLANNER_SHARED_RESOLUTION=0` och med
   `--substitution-limit 0`. Taket minskar antalet korgar, men peak RSS var
   nästan lika (2 964 mot 2 983 MB); toppen sätts alltså troligen av
   kvalificering och förberedelse, inte av sökningen.
4. Föreslå begränsning som inte ändrar resultatet, och mät att hashen består.

### 4.3 Fullbiblioteksreferens vid 1 000 och 2 000 recept saknas

Jämförelserna gäller hittills endast substitutionstaket mot hela
substitutionssvepet; seed 40, förfining 90 och variantlistan var påslagna i båda
armarna.

1. Slå först ihop grenarna enligt avsnitt 1, så att `--uncapped` även sätter
   `substitution=0` och referensen kan valideras.
2. Kör `--uncapped --repeat 1` för standard och fördelning, Lund och Malmö,
   1 000 och 2 000 recept. Seed-sökningen över hela poolen är dyr: räkna med
   tiotals minuter per körning och peak RSS över 3 GiB i Malmö 2 000 (kör den
   i en större container och redovisa det).
3. Kör ordinarie inställningar med `--uncapped-reference` mot varje referens.
   Varje profil där standard betalar mer ska redovisas med orsak; höj då det
   otillräckliga taket enligt uppgiften (”ett otillräckligt tak höjs”).
4. Notera att 80 i Claudes prov gav en *billigare* meny än hela svepet
   (485,87 mot 497,19 kr i Lund standard). Sökningen är inte monoton i taken;
   en referens utan tak är därför inte heller garanterat optimal.

## 5. Övrigt att bekräfta eller avvisa

- Delad enreceptskvalificering prövades och förkastades (ingen nettovinst,
  +110 MB). Patchen finns i
  [rejected-shared-qualification.patch](recipe-scaling-20261019/rejected-shared-qualification.patch)
  om du vill pröva den i referensmiljön.
- En konservativ bevisad kostnadsgräns (enpaketsgolv per sammanslagen
  ingrediensgrupp, kampanj- och viktvaror som 0) nådde högst 51 % av
  veckobeloppet och kunde inte beskära någon vecka
  ([bound-tightness-lund-1000.json](recipe-scaling-20261019/bound-tightness-lund-1000.json)).
  Granska om golvet faktiskt är tillåtligt för alla erbjudandetyper.
- Lund fördelning vid 1 000 och 2 000: samma pris men annan meny med tak 160
  än med hela svepet. Bedöm om lika-pris-regeln ska kräva samma meny.
- 5 000 recept är inte mätt. Kvalificeringen (cirka 60 s kallt vid 2 000)
  växer linjärt och blir då den dominerande kostnaden.

## 6. Leverans

Rapportera som tidigare: beslut, PASS/XFAIL/SKIP, råvärden med spridning,
priser och hashar per stad/profil/storlek, peak RSS, samt vad som inte kunde
köras. Inga prov får skriva i produktionsdatabaser eller produktionsbiblioteket.
