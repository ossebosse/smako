# Uppstartsväntan på betan

Undersökning 2026-10-16 av kodcommit `e041451`, aktiv som
`joint-week-refinement-app-e041451`. Rapporten bygger på det redan utförda
betaprovet, tidsstämplade containerloggar, exakt matchad startmetrik,
runtimehashar och lokal reproduktion. Ingen omstart, ny liveberäkning,
konfigurationsändring eller insamling gjordes i undersökningen.

## Slutsats

Huvudorsaken är att bakgrundsuppvärmningen för **Malmö** upptar appens enda
gemensamma beräkningsplats när användarens **Lundmeny** kommer in. Den väntar
bakom ett redan startat bakgrundsjobb. Kontroll av konsumentprioritet sker
bara innan uppvärmningen startar; en senare anländ användare kan inte ta över.

Uppvärmningen använder dessutom den äldre receptvägen: fem middagar, två
portioner, tre butiker och balanserat läge. Den saknar `recipe_preferences`
och `personal`, även när `complete_recipes_enabled=True`. Användarprovet
använde det nya receptbiblioteket, fyra portioner och högst två butiker.
Det är därför inte en uppvärmning av samma menyväg. Vissa gemensamma
priscacher kan fortfarande få nytta; det bevisar inte att hela körningen behövs.

## Tidslinje från den verkliga körningen

Alla tider nedan är UTC, svensk tid är två timmar senare.

| Händelse | Tid |
| --- | --- |
| Appcontainern startade | 13:21:04.080 |
| Applikationens uppstart färdig | 13:22:07.754 |
| Lunds bakgrundsuppvärmning färdig | 13:23:46.732 |
| Proteinprovets startmetrik lagrad, POST svarade 202 | 13:24:24.932 |
| Malmös bakgrundsuppvärmning färdig | 13:32:04.378 |
| Proteinplanen skapad och sparad | 13:33:12.788 |

Startanropet tog 672,631 ms på servern. Slutresultatet kom efter 533,72 s
(8 min 54 s) i klientmätningen. Det var alltså inte ett enda HTTP-anrop
som tog nio minuter; det asynkrona jobbet väntade och klienten pollade.

Mellan den lagrade startmetriken och Malmös färdiglogg gick 459,45 s,
ungefär **7 min 40 s**. Det är ett starkt tidsmässigt stöd för köförklaringen,
inte en exakt uppmätt köspan: metriken lagras asynkront och den historiska
kötiden finns inte sparad. Koden och reproduktionen nedan visar mekanismen.
Ingen exakt historisk starttid för Malmöuppvärmningen finns i loggen.

Från Malmös färdiglogg till den sparade proteinplanen gick 68,41 s.
Produktfakta tog 21,04 s och `PersonalPlanner.create()` tog 43,79 s, tillsammans
64,83 s. Dessa tider är förenliga med att användarjobbet körde efter
Malmöuppvärmningen. Övrig initiering, minnesstädning, sparning, transport
och pollning är inte individuellt tidsatta i det sparade resultatet.

De cirka 44 sekunderna som tidigare redovisades som intern planerartid börjar
**efter konstruktorn**. De inkluderar inte de 21 sekunderna produktfakta från
konstruktorn. Sökningens underposter överlappar dess total och ska inte adderas
ovanpå den. Appens uppstart före readiness är också separat från de 533,72 s.

Efterföljande API-prov tog 26,98 s (makrokrav), 15,77 s (frukost/vikt) och
16,28 s (vegan). Alla passerade köp-, närings-/vikt- och återläsningskontroller.
Det är olika profiler och inget kontrollerat kall/varm-lasttest.

## Bekräftad kodväg och reproduktion

Åtta berörda runtimefiler är SHA-256-identiska med granskad lokal kod:
uppstart, uppvärmning, admission, HTTP-planering, båda planerartjänsterna,
receptöversättning och begäransmodellen. Aktiv inställning är en samtidig
beräkning, fyra köplatser och menyuppvärmning aktiverad.

- `backend/app/main.py:115` schemalägger uppvärmning för alla laddade kommuner.
- `backend/app/services/plan_prewarm.py:233` har 15 s väntan mellan kommunerna.
- `plan_prewarm.py:290` använder samma admission som konsumenterna, med
  `only_if_idle=True`. Detta förhindrar start när konsumentjobb redan finns,
  men avbryter inte ett pågående bakgrundsjobb.
- `backend/app/services/planner_admission.py:127` väntar på samma semafor.
- `plan_prewarm.py:133` konstruerar standardbegäran utan nytt receptläge.
- `backend/app/services/personal_planner.py:2333` startar create-timern först
  när konstruktorn redan har slutförts.

Det lokala provet använder verklig `BackgroundPlanPrewarm` och
`PlannerAdmissionController`, med ett eventstyrt arbete i stället för faktisk
prissökning. Malmö startar först; Lund hamnar i kö och kan inte börja innan
Malmö släpps. En 200 ms avsiktlig spärr gav 210,174 ms uppmätt kötid. Utan
bakgrundsjobbet blev kötiden 0,008 ms. Detta bevisar ordningen, inte serverns
prestanda eller exakt historisk kötid.

Samma reproduktion fångar begäran från verklig `BackendStandardPlanPrewarmRunner`
och bekräftar `complete_recipes=False`, `personal=False`, 5 recept, 2 portioner,
3 butiker. Befintliga **17 tester** för bakgrundsuppvärmning och admission
passerar. De täcker bland annat det omvända fallet: bakgrunden väntar när en
användare redan beräknar. Inget beteende i applikationen har ändrats.

Reproduktion från projektroten:

```powershell
$env:PYTHONPATH='backend;.'
$env:PYTHON_DOTENV_DISABLED='1'
.venv/Scripts/python.exe -X utf8 reports/startup-wait-20261016/reproduce.py
.venv/Scripts/python.exe -m pytest backend/tests/test_background_plan_prewarm.py backend/tests/test_planner_admission.py -q
```

Sanerade mätvärden och runtimehashar finns i
[EVIDENCE.json](startup-wait-20261016/EVIDENCE.json).

## Rekommenderade nästa åtgärder

1. **Stäng av den fullständiga menyuppvärmningen via befintlig inställning**
   `PRICE_UNIVERSE_PREWARM_ENABLED=false`. Behåll separata
   `precompute_pricing_semantics` och dess förberedda ingredienssökning;
   de ligger utanför denna flagga. Då tas den identifierade bakgrundskön bort.
   Det första riktiga användarjobbet kan fortfarande behöva läsa produktfakta.
   Ingen ny svarstid utlovas innan detta har verifierats.
2. **Mät hela användarjobbet.** Återanvänd `PerformanceTrace` och befintlig
   `planner_queue_wait`, men bevara separata tider för kö, minnesstädning,
   konstruktor/fakta, sökning och sparning. Redovisa även start/slut och
   varaktighet för uppvärmningen utan användar- eller sessionsuppgifter.
3. **Förbered bara återanvändbara data vid behov.** Använd befintliga
   versionsbundna artefakter och faktacacher för det nya receptflödet, i
   begränsade steg som inte kör en hel hypotetisk veckomeny framför användaren.
   Att enbart byta bakgrundsbegäran till nytt receptläge lämnar köfelet kvar.

Behåll begränsningen av samtidiga beräkningar tills faktisk CPU- och
minnesbelastning har verifierats. Att släppa semaforen medan en Pythontråd
fortfarande arbetar är inte ett säkert sätt att ge användaren företräde.

Den första åtgärden ovan är ett förslag, inte utförd i denna undersökning.
Betan kör fortsatt samma verifierade version och inställningar.
