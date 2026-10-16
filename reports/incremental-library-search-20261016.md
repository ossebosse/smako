# Bibliotekssökning med återanvändning och riktade byten

Lokalt arbete i `D:\Projects\Smako`, gren `perf/incremental-library-search`,
bas `6614ac9`. Beställning: genomför punkt 1 och 2 i prestandaprioriteringen.
Ingen aktivering på betan, källinsamling eller ändring av användarkrav.

## Ändring

Vanlig nyplanering använder en `PersonalPlanner` för bibliotekets generationer.
Det aktuella recepturvalet kvalificeras en gång per måltidstyp; samma privata
produkt-, närings- och receptcacher används under hela sökningen. En extra
cache med högst 256 exakta del-/helkorgar återanvänder lyckade beräkningar mellan
försöken. Nyckeln innehåller ordnade måltids-ID:n, dagar, typer, hela receptvärden
och om kontrollen gäller en delmeny eller slutmeny. Cachen lämnar aldrig anropet.

Första giltiga menyn hittas med befintlig beam, bredd 8 och befintligt villkorat
omförsök med bredd 64. Saknas kandidater för en måltidstyp eller hittas ingen
giltig meny prövas nästa större urval. Bara nu aktuella receptversioner får
ingå i starturvalet; äldre ersatta eller återkallade versioner återinförs inte.

Senare publicerade recept prövas som enskilda byten i den giltiga menyn, högst
två genomgångar per tillkommande urval. Två avslutande genomgångar med hela
urvalet kan också förbättra kombinationen med äldre recept. En andra genomgång
görs endast efter en förbättring. Slutligen prövas högst 128 parvisa byten ur
högst åtta rankade alternativ per måltid. Förslagen måste klara samma kompletta
kravkontroll och gemensamma checkout. Dyrare förslag ersätter aldrig den giltiga
menyn. Vid lika pris används befintlig smak-/namnordning.

Förpacknings- och ekokopplingarna motiverar båda förbättringsstegen: en första
prototyp utan omprövning av äldre recept gav 691,46 i stället för 674,16 kr i
standardfallet. Enskilda byten räckte inte heller för eko: 447,61 i stället för
434,13 kr. Dessa prisregressioner stoppade verifieringen och är inte slutresultat.

Slutlig audit och fördelnings-/variationskontroll körs oberoende av sökcachen.
Ändrade butikstak/köpval och den balanserade referensen för Varierad får egna
planerare. Redigeringar och injicerade egna sökare behåller sin tidigare väg.
Sökspåret skiljer på startförsök, enskilda byten och parvisa byten; försök har
separata nummer för korrekta avslagsräkningar. Policyidentiteten har uppdaterats.

## Mätning och reproduktion

Befintlig `combined_performance_probe.py --matrix` använder det frysta
22225-underlaget med 19 tillåtna butikskontexter, explicit faktasamling och
klockan `2026-10-15T13:00:00+00:00`. Nätverk är blockerat. Ingen färdig menycache.
Priser/fakta/begäran hashkontrolleras mot `.local/planner-preparation/inputs/matrix-inputs.json`.
Kalla och varma körningar avser samma process per profil, separat förberedelsecache
för varje profil. Laddning av prisartefakten och oberoende resultatkontroll
redovisas separat från nedanstående planeringstid.

Slutliga råmätningar: `.local/incremental-library/final/after-<profil>.json`.
Jämförelse: `.local/flexible-recipes/matrix/after-<profil>.json` för fyra huvudfall,
och `.local/ecological-week-search/verified/verified-<profil>.json` för övriga.
Körhjälpare och sammanställning finns i `.local/incremental-library/`.

| Profil | Före kall / varm, s | Efter kall / varm, s | Inköpssumma före → efter, kr |
| --- | ---: | ---: | ---: |
| Standard | 85,78 / 58,46 | 49,97 / 25,94 | 674,16 → 674,16 |
| Minst 40 g protein | 32,59 / 8,79 | 33,44 / 8,30 | 1 216,11 → 1 184,12 |
| Frukost + mellanmål + vikt | 29,06 / 4,31 | 24,54 / 2,06 | 85,55 → 85,55 |
| Ekoandel minst 20 % | 316,28 / ej mätt | 144,09 / ej mätt | 434,13 → 434,13 |

Standard varm är 55,6 % snabbare än efter receptutökningen och också snabbare
än de tidigare 37,74 sekunderna. Ekofallet är 54,4 % snabbare än 316,28 s och
snabbare än tiden före receptutökningen, 216,52 s. Det ligger fortfarande över
målet 30–60 s. Små skillnader kring någon sekund är inte säkra prestandavinster.

Standard väljer samma fem recept i annan dagsordning; dess fulla semantiska
hash ändras därför. Proteinmenyn ändras och blir 31,99 kr billigare. Ekofallet
behåller samma meny och ekoandel 23,4953 %. Frukostfallet behåller extra yoghurt
och kikärtsröra med gurkstavar. Kravuppfyllelse jämförs oberoende av receptnamn;
ingen gammal semantisk hash har framtvingats genom att ändra kraven.

Sökspåret visar en kvalificeringsomgång och en veckosökning i stället för tre
i både standard- och ekofallet. Standard varm: korgberäkningar 4 428 → 1 841,
produktmatchningar 6 064 → 2 171 och förpackningsberäkningar 116 571 → 58 989.
Eko: korgberäkningar 142 946 → 50 467 och ekosökningar 2 648 → 1 108.
Ekosökarens pris-/källlogik är oförändrad i denna etapp; den anropas färre gånger.

Övriga positiva kontrollfall (jämförda med föregående tioprofilsserie):

| Profil | Efter kall / varm, s | Inköpssumma före → efter, kr |
| --- | ---: | ---: |
| Alla fyra makronäringskrav | 33,76 / 8,40 | 1 216,11 → 1 184,12 |
| Veganskt | 27,73 / 3,57 | 478,17 → 478,17 |
| Angiven måltidsfördelning | 33,77 / 10,10 | 1 119,68 → 1 107,34 |

Mjölkallergi, ekologiska animalier och omöjligt proteinmål ger fortsatt samma
avslag i det frysta underlaget. Kall/varm tid: 25,75/1,14, 26,10/1,45 respektive
27,66/3,39 s. Sju positiva och tre blockerade profiler ger totalt 19 mätningar.
Alla har samma indataidentiteter som respektive jämförelse. Högsta observerade
processminne i serien: 825,27 MiB; detta är inte en per-användare- eller serverdimensionering.

Mätserien föregår en sista kompatibilitetsvakt för äldre frukostrecept utan
biblioteksdesign. Dessa ska ingå oförändrade i alla urval och saknar biblioteks-ID.
Matrisens kandidater kommer från biblioteket och berörs inte av vakten; den
prövas i ett separat integrationstest. Rårapporterna bevarar mätkodens signatur.

```powershell
$env:PYTHONPATH='backend;.'
$env:PYTHON_DOTENV_DISABLED='1'
.venv\Scripts\python.exe -X utf8 backend/scripts/combined_performance_probe.py --matrix --inputs .local/planner-preparation/inputs --output .local/incremental-library/recheck --label recheck --matrix-case standard --repeat 2
```

## Begränsningar

Detta är en begränsad sökmetod. Rankningen av par är en heuristik, ingen
matematisk prisgräns. Alla par eller större samtidiga byten provas inte, och
oförändrat/lägre pris i testmatrisen garanterar inte det för varje framtida
begäran eller bibliotek. Nya recept kvalificeras fortfarande och kan öka tiden.
Ingen global kostnadsoptimalitet eller kapacitet för hundratals samtidiga
användare är bevisad. Mätningarna är lokala enstaka kall-/varmprov, inte en
serverbelastningstest eller en uppskattning av kötider.

## Kodverifiering

375 offlineprov i 18 moduler passerade, följt av det separata kompatibilitetsprovet
för äldre frukost: totalt 376 passerade prov. Den nya modulen täcker framtida
paket, dyrare/ogiltiga tillägg, misslyckat starturval, återanvända exakta prefix,
ändrade recept och måltidsfält, separata anrop, äldre recept efter råvarubyten,
parvisa vinster, fast parbudget, begränsat cacheminne, återkallade/ersatta
versioner och en oberoende slutkontroll som också kan avvisa sökresultatet.
Befintliga prov täcker privata uppgifter, skafferi, medlemspriser, ändrade krav,
butikstak, näring, eko, kampanjer, variationsregler och sparade menyer.

Ruff, compileall och `git diff --check` passerar. Isoleringsloggarna
`.local/verification/incremental-library-final-access.json` och
`incremental-library-legacy-access.json` har inga rapportläsningar eller
blockerade anrop. Den breda serien hade 18 befintliga serializer-varningar
från syntetiska testdata i `test_personal_performance`, inga testfel.
