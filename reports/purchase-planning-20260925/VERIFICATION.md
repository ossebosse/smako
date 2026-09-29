# Slutverifiering

## Riktig oförändrad 15/20-profil

Körningen använder den riktiga `PersonalPlanner` i privat Linux-kandidatmiljö med avsedd scheduler-image, icke-root, skrivskyddad kod/root och `network=none`. Ingen produktions-HTTP-endpoint eller aktiv användardatabas används. Förfrågan är den sparade riktiga 15/20-profilen: fem middagar à två portioner, fem frukostar och fem mellanmål; proteinminimum **40/30/20 g**, högst **två inköpsställen**. Det ordinarie recepturvalet och sökkraven är oförändrade (96 middagskandidater, 5 frukostar, 5 mellanmål). Näringsuppskattnings-opt-in kvarstår. Denna profil har inga medlemsprogram aktiverade i något jämförelseled.

Före/efter använder **samma kompletta bas, baskällornas snapshot-ID, källcache, köpdag 24 september och testklocka 2026-09-24 21:16:35.494010 UTC**. De gamla respektive nykvalificerade Willys-/Lidl-tillskotten körs genom slutkoden. Mellan exakt och uppskattat läge ändras endast `purchase_planning_mode`. Samtliga sex obligatoriska baskontexter finns i båda artefakterna; totalt 9 kontexter. Inget pris- eller observationstidfält har skrivits om.

| Underlag / läge | Varukostnad | Kvalitetsstatus | Måltider/portioner | Inköpsställen |
|---|---:|---|---:|---:|
| before / exact | 535.25 kr | VERIFIED | 15/20 | 2 |
| before / estimated | 535.25 kr | VERIFIED | 15/20 | 2 |
| after / exact | 535.25 kr | VERIFIED | 15/20 | 2 |
| after / estimated | 535.25 kr | VERIFIED | 15/20 | 2 |

Alla faktiskt valda köprader är exakta även när uppskattningsläget är tillåtet. Därför är `VERIFIED` korrekt för just dessa slutmenyer. De nya uppskattade/öppna erbjudandena måste inte väljas för att vara användbara; deras separata verkliga köp-/näringsprov redovisas i README och comparison.json. Ingen uppskattad besparing hävdas.

| Inköpsställe | Faktiskt vald produkt | Kostnad | Mängdunderlag |
|---|---|---:|---|
| Coop Online Syd | Knäckebröd Husman | 15.62 kr | exact |
| Coop Online Syd | Tomater Krossade | 15.68 kr | exact |
| Coop Online Syd | Kvarg Naturell 0,3% | 97.50 kr | exact |
| Coop Online Syd | Röda linser Hela | 29.29 kr | exact |
| Coop Online Syd | Gouda Skivor | 19.40 kr | exact |
| Coop Online Syd | Spaghetti | 13.95 kr | exact |
| Willys Lund | Torskfilé | 187.80 kr | exact |
| Willys Lund | Kycklingfilé 2-delad Frysta | 75.61 kr | exact |
| Willys Lund | Morötter Klass 1 | 14.90 kr | exact |
| Willys Lund | Äggnudlar | 17.80 kr | exact |
| Willys Lund | Långkornigt Ris | 19.90 kr | exact |
| Willys Lund | Vitkål Strimlad Klass 1 | 27.80 kr | exact |

Källfärskhet vid jämförelseklockan: **aging**, äldsta användbara pris **43.466 timmar**. Vid slutrapportens verkliga kontroll är den äldsta observationen 60.06 timmar gammal. Det historiska kompletta underlaget får alltså **inte** användas som ett påstående om aktuell publiceringsfärskhet. Ordinarie 36/48-timmarsgränser är bevarade.

Ett tidigare mellanprov hade bara åtta kontexter eftersom federerad källfiltrering fortfarande använde väggklockan. Det provet räknas inte som komplett bas. Den slutliga provklockan omfattar även federerad filtrering och innehåller en uttrycklig kontroll att samtliga obligatoriska baskontexter finns kvar. Produktionskoden och färskhetsgränserna ändrades inte för denna rättning.

Bevis: `profile-summary.json`, `profile/before-*-restored-original*.json`, `profile/after-*-restored-original*.json`, båda fulla PriceUniverse-artefakterna samt deras in-/utdata. Databas och extern cache är verifierat oförändrade; byggaren registrerar noll externa nätförsök.

## Kommun och ordinarie drift

Samma officiella inventering och kommunfunktion kördes för Lund 1281 och Malmö 1280, utan nya hårdkodade produktionsbutikslistor. `final/verification-1281.json` och `final/verification-1280.json` innehåller första och andra byggnaden med samtliga importerade kvalificerade butiksposter. Lund: **87**, Malmö: **467**. De byggnaderna är isolerade tilläggsprov, inte kompletta baskällsprov.

Slutkodens återkommande driftprov använder separat uvicorn-instans, ordinarie runner, verklig underprocess för rebuild och serving-reload mot isolerade filer. Bevarad City Gross-bas har 13 523 produkter, Willys 243 och Lidl 224. Ingen aktiv produktionskonfiguration ändras. Testklockan är **24 september 15:00 UTC**, så att kontrollen utan förfallet arbete faktiskt ligger före respektive källas förfallotid.

| Fas | Runner exit | Health/ready HTTP | Willys-poster bevarade |
|---|---:|---|---:|
| first | 0 | 200/200 | 243 |
| second | 0 | 200/200 | 243 |
| restart | 0 | 200/200 | 243 |
| not_due | 0 | 200/200 | 243 |
| fetch_fail | 0 | 200/200 | 243 |
| recovery | 0 | 200/200 | 243 |

Alla faser har samma slutkodshashar, produktsignaturer och källobservationer. Omstarten är en ny process med beständigt kommunval/status. `not_due` startar ingen prishämtning eller rebuild-underprocess. Vid injicerat hämtfel behålls giltiga LKG-priser och basen fungerar; återhämtningen kör ordinarie källväg med sparade faktiska svar. En framtida runtimeklocka +49 timmar utesluter för gamla kontexter och anger förfallet källarbete. Separata datumtester spärrar erbjudanden före start och efter kampanjslut.

Lidls separata jobbprov (`lidl-recovery-verification.json`) injicerar hämtfel, kontrollerar att godkända referenser behålls, kvalificerar därefter samma verkliga råsvar genom slutversionens collector och får åter **28 poster per Lundbutik**. Omstart utan nytt kommunvärde ger `not_due`. Prisobservationerna är oförändrade. Fullflödets varning om partiell kvalificering finns kvar; 28 av 380 är inte en komplett Lidl-katalog.

Nästa källkontroller i det **isolerade** beständiga läget ligger för Willys Malmö den **25 september 18:41 UTC** och för Lidl Lund den **26 september 01:35 UTC**, enligt redan befintlig 35-timmars behovsregel. Exakta tider per butik finns i `next-source-checks.json`. Detta är inte ändrade produktionsscheman eller ett löfte om att källor har hämtats vid dessa framtida tider.

## Tester och metodgränser

**768 unika testfall passerar**, deduplicerade på testnamn inklusive parametrar med senast verifierat resultat. Den breda slutkörningen hade 678 passerade tester; övriga riktade checkout-/cache-/kompatibilitetsprov ger det större unika antalet. Original-XML/loggar och tidigare misslyckade mellanprov finns kvar. `tests-verified.json` visar exakt vilket slutprov varje testresultat kommer från. Ruff, compileall och JavaScript-syntaxkontroll passerar (`quality-final.json`).

Regressionsgruppen omfattar kg-/cirka-/styckköp, hela paket och överskott, öppna och verifierade variantgrupper, blandade hela flerköp utan restpris, gemensamma hushållstak, pant, fel butik/variant/medlemskap/datum, pris-/textkonflikt, SLV-opt-in och enheter, deklarationsidentitet, allergi-/receptspärrar, API-läge, sparade val, uppmätt lagerbokning samt kedje-/providerbakåtkompatibilitet. Den nya generiska blandgruppsbryggan provas genom riktig collector/OWN/PU med **syntetisk källa**; detta ökar inte antalet verkliga kampanjer.

**Historisk Lidl-fixturelucka kvarstår öppen**, utanför dessa passerade fall. Den har inte dolts med skip eller fabricerad fixture. De tidigare verkliga dokumentrevisionerna är inte ett nytt oberoende holdout. Fullständig aktuell Malmö-publicering och färskt komplett produktionsbasunderlag kvarstår separat.

Nätinsamling hålls isär: **0 nya prisnätanrop**, **5 nya officiella närings-/produktnätanrop**. Driftens replay, testklocka och felinjektion utgör inte livehämtning. Ingen bildanalys, bildmodell eller betald modell-API användes.
