# Prestanda, träffsäkerhet och gemensam receptförberedelse

Detta är arbetskontraktet för prioritet 1–2. Tid, giltighet och inköpskostnad
bedöms tillsammans. En snabbare beräkning som ändrar hårda krav, tappar
kandidater eller ger en dyrare korg är inte automatiskt en förbättring.

[Verifierade mätvärden och begränsningar, 2026-10-16](../reports/planner-preparation-20261016.md).

## Befintliga delar som återanvänds

| Behov | Befintlig komponent | Ändring i denna etapp |
| --- | --- | --- |
| Offlineprov och profilering | `backend/scripts/combined_performance_probe.py` | Nytt `--matrix`-läge för dagens extraval, samma frysta pris-/faktaformat |
| CPU-/tidsmätning | `services/performance_trace.py` | Befintliga spans används; separat ekosökning och köväntan tillkommer |
| Minnesmätning | `backend/scripts/benchmark_beta_capacity.py` | Samma Windows/Linux-samplare används i matrisen |
| Persistenta förberedelser | `services/meal_prepared_artifacts.py` | Ingredienssökning läggs till befintliga innehålls-/deklarationsartefakter |
| Cache med begränsad storlek | `price_universe_runtime.MenuSearchResultCache` | Återanvänds inom rätt PreparedPriceUniverse för ingredienssökning |
| Näring och mängdunderlag | Befintliga källfakta, deklarationsartefakter och `RecipeComputationCache` | Återanvänds; ingen extra gemensam näringscache införs |
| Uppstart och omladdning | `pricing_projection_prewarm.py` | Förbereder ingrediensindex via befintligt anrop när kompletta recept är aktiverade |
| Förberedelsekommando | `meal_library_cli prepare/build --universe` | Förbereder också samma ingrediensindex |
| Prissättning och godkännande | PersonalPlanner/BasketOptimizer/audit | Oförändrade sökbudgetar, användarkrav och slutkontroller |

Ingen separat prismotor, ny datakälla, jobbkö eller produktionsinstallation
införs i denna etapp. Den befintliga HTTP-kapacitetsmätaren används när
samtidighet ska provas i en separat testmiljö.

## Mål och hur de mäts

- Föreslaget interaktivt mål: vanliga profiler inom 30 sekunder, med ambition
  15–30 sekunder. Föreslaget mål för en överenskommen representativ testmix:
  95:e percentilen inom 60 sekunder. Dessa är mål, inte uppmätt serverkapacitet.
- Beräkningstid, kötid, uppstart/inläsning och verifiering redovisas separat.
  Offlineanropet går direkt till planeraren: kötid är därför **okänd**, aldrig
  uppmätt noll. `planner_queue_wait` mäts när den befintliga admission-vägen
  körs under en PerformanceTrace.
- Varje profil körs i egen process, först processkall och sedan processvarm.
  En ny PersonalPlanner skapas varje gång. Färdiga menyer återanvänds inte.
  Cachekatalogen ska vara ny för ett helt kallt diskprov; återanvänd katalog
  endast om provet uttryckligen avser persistenta förberedelser.
- Enstaka prov och tio syntetiska användarprofiler kan inte belägga verklig
  p95 för användartrafik. Rapporten märker percentilen som en provpercentil.
- Profilerade cProfile-tider räknas inte som acceptanstider. Befintliga
  PerformanceTrace-spans används även utan cProfile; de är nästlade och
  deras tider får inte summeras som om de vore exklusiva.
- Minnets maxvärde är processens observerade högvattenmärke, inte en separat
  topp för varje iteration. Det används för att upptäcka tillväxt och för
  senare dimensionering av parallell körning.

Matrisen innehåller standardmeny, protein 40 g, samtidiga makro-/energigränser,
veganskt, proteinfördelning, 20 % ekoandel, frukost/mellanmål med viktgräns,
mjölkallergi, ekologiska animalier och en avsiktlig 300-gramsproteingräns.
De sista profilerna skiljer dataluckor och ej uppnådda mål från lyckade
planer. Ett förväntat avslag räknas inte som en levererad meny.

## Reproducerbar körning

Kör från projektroten med Python 3.12 och `PYTHONPATH=backend;.` på Windows.
Använd offentliga sparade produktuppgifter och syntetiskt tomt skafferi.
Ingången ska innehålla:

- `combined-prices.json`: befintlig `PreparedPriceUniverseArtifact`.
- `combined-facts.json`: befintligt format `facts` som par av produktnyckel
  och ProductFacts, samt verifierbar `facts_version`.
- `combined-request.json`: basval inklusive exakta tillåtna butiker och
  pris-/uppskattningspolicy. Matrisen byter endast dokumenterade måltidsval.
- `matrix-inputs.json`: tidszonsatt fryst `now` och `sha256` för de tre filerna.

Pris-/faktaunderlaget och klockan ska vara identiska före och efter.
Äldre underlag märks historisk replay; inga observationstider förnyas.
Nätverksanslutningar blockeras under beräkningen. Ingen privat databas öppnas.

```powershell
$env:PYTHONPATH='backend;.'
.venv\Scripts\python.exe -X utf8 backend/scripts/combined_performance_probe.py --matrix --inputs .local/planner-preparation/inputs --output .local/planner-preparation/example --label reference --matrix-case protein40 --repeat 2 --reference-preparation
.venv\Scripts\python.exe -X utf8 backend/scripts/combined_performance_probe.py --matrix --inputs .local/planner-preparation/inputs --output .local/planner-preparation/example --label optimized --matrix-case protein40 --repeat 2 --baseline .local/planner-preparation/example/reference-protein40.json
```

`--reference-preparation` kopplar endast förbi den nya gemensamma
ingredienssökningen. Befintliga
lokala cacher, planerare, kandidater, prissättning och audit används i båda
armarna. Detta är ett kontrollerat jämförelseprov, inte en annan serverversion.
En faktisk föregående kodversion kan också användas med samma frysta indata.

`--prepared-startup` kör samma nya gemensamma ingrediensförberedelse som
serving-processens uppstart före första menyanropet. Tiden sparas separat i
`startup_preparation_seconds`. Jämför både menyns svarstid och summan av
inläsning, uppstart och beräkning; förberedelse är flyttat arbete. Flaggan är
inte ett test av full webbserveruppstart eller parallell användartrafik.

Använd `--matrix-case organic-share --profile --repeat 1` för cProfile.
Rapporten sparar både kumulativ och exklusiv funktionsprofil samt räknaren
`ecological_subsets_evaluated`. Att sökbudgeten är 256 för en enskild
ekodelsökning betyder inte 256 utvärderingar för hela veckomenyn.

## Godkännandekrav

Vid lyckat resultat kontrolleras inköpsaudit, avstämda summor, noll okända
mängder, butikstak, tillåtna butiker, antal måltider/portioner, näringsgränser
och ekoandel. Kostval, hårda uteslutningar och begärd proteinfördelning
kontrolleras också; begärda allergi-/ekointyg måste vara verifierade.
En jämförelsehash omfattar hela recept, inköpskorg,
näringskällor, audit och skafferifördelning. Profilvalens variation visas
separat. Samma resultat måste överleva cacheträffar och en ny användarplanerare.
Avslag jämförs med kod och steg och redovisas med orsak.
Sökningens utfall och budget redovisas när planeraren lämnar dem. Identisk
korg före/efter visar att denna ändring bevarar resultatet; det bevisar inte
att den begränsade sökningen hittat den globalt billigaste möjliga menyn.

## Gränser för återanvändningen

Ingrediensindexet återanvänder exakt samma befintliga textsökning och
granskade stavningsalias. Det är kandidatåtervinning, inte godkännande av en
pris- eller livsmedelsidentitet. Persistensen binds till hela inventeringen,
butikskontexterna, frågorna och kodsignaturen. Saknade produkter får därför
inte ärva gamla negativa sökresultat när underlaget byts.

Näringsberäkningen använder redan förberedda offentliga källfakta,
deklarationsklasser, näringsreferenser och förfrågans egna cacher. Ett försök
med ytterligare gemensam cache för näringsunderlag gav ingen tydlig tidsvinst
i matrisen. Exakta cachenycklar och skyddskopiering tillförde eget arbete;
försöket togs därför bort ur den slutliga implementationen.

Varje recept valideras fortfarande. Portioner, användarens näringsmål,
allergier, medlemskap, skafferi, butikstillåtelse, giltighetsdatum, mängdbehov
och slutlig inköpsaudit är förfrågans egna beslut. Den befintliga
`meal_library_cli prepare/build --universe` förbereder käll-/deklarationsdata
och nu även ingrediensindexet. Ingen ny närings- eller mängddatabas införs.
Kodsignaturen binder också näringsreferensernas och produktdeklarationernas
JSON-filer, så en ny release inte återanvänder artefakter för äldre data.
Trasiga eller fulla diskartefakter faller tillbaka till ordinarie beräkning.
När en minnespost kastas ut beräknas den om vid nästa behov.
