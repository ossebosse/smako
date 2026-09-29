# Ordinarie Lidl-driftkedja i isolering

Python 3.12, egna datamappar, operationslås och loopback-servrar på portar 18780/18781. Ordinarie `run_daily_refresh.main` → riktig CLI-child → källjobb/OWN-referenser → produktionsbyggare → artefaktvalidering/publicering → faktisk HTTP-reload. Varje fas startar en ny app-process. Inga produktionsvolymer eller användarval används.

Malmö har oförändrad City Gross Hyllie-bas (13 523 produktposter); Lund har den normalt omvaliderade/importerade befintliga Willys-artefakten (18 642 poster i PriceUniverse, 18 824 i OWN). Ingen kommun lånar grannkommunens Lidl-butik. Detta är isolerade OWN-instansprov, inte fullständiga federerade kommunreleaseprov.

| Kommun | Fas | Lidl i PU | Exit | health/ready | Tid s |
|---|---|---:|---:|---|---:|
| Lund | first | 6 | 2 | 200/200 | 408.094 |
| Lund | second | 6 | 2 | 200/200 | 94.468 |
| Lund | restart | 6 | 2 | 200/200 | 105.375 |
| Lund | not_due | 6 | 0 | 200/200 | 14.641 |
| Lund | fetch_fail | 6 | 2 | 200/200 | 122.687 |
| Lund | recovery | 6 | 2 | 200/200 | 112.406 |
| Malmö | first | 24 | 0 | 200/200 | 99.875 |
| Malmö | second | 24 | 0 | 200/200 | 94.938 |
| Malmö | restart | 24 | 0 | 200/200 | 134.406 |
| Malmö | not_due | 24 | 0 | 200/200 | 16.500 |
| Malmö | fetch_fail | 24 | 0 | 200/200 | 133.000 |
| Malmö | recovery | 24 | 0 | 200/200 | 132.047 |

Malmös första/andra/omstart provade versionen före den sista skärpningen som förbjuder olika byggstad och kommunkod. `not_due`, `fetch_fail` och `recovery` kördes om med slutkoden; tidigare kvittenser ligger kvar i `before-scope-validation`. Lunds första publicering föregick samma konfigurationsskärpning; följande faser har slutkoden. Pris-/produkt-/observationssignaturerna är identiska även mellan dessa versioner. Slutkvittensernas 17 berörda kodhashar jämförs med leveransen. Detta är inte ett påstående att alla historiska körningar hade identisk kod.

## Verifierade egenskaper

- Kommunval och enabled-läge läses från beständig konfiguration efter första fasen; de explicita miljövariablerna tas bort vid följande processstarter.
- Andra rebuilden och omstarten bevarar alla sex respektive 24 Lidl-poster, giltiga erbjudanden, snapshotreferenser, medlemskap, förpackningar och originalobservationer. Baskällornas fulla produkt-/prissignaturer är också identiska mellan faserna.
- I `fetch_fail` injiceras ett dokumenterat insamlingsfel för valda Lidl-butiker. Status/felräknare/återförsök syns per butik. Giltig LKG går ändå genom ordinarie rebuild/publicering/reload och fungerande baskällor blockeras inte.
- `recovery` återspelar samma godkända oförändrade OWN-underlag. Det återställer källstatus utan att påstå en ny nätobservation.
- `not_due` startar ingen CLI-child, ingen prisinsamling och ingen rebuild/reload. Nätspärren registrerar noll externa försök. I Lund är det separata befintliga Willys-reläets 35-timmarstimer samtidigt förfallen (`relay_due=true`); detta döljs inte eller omvandlas till ett nytt Lidl-jobb. Den lokala serverrunnern har inget eget förfallet arbete.
- +49 timmar är en uttrycklig injicerad testklocka: samtliga pris-kontexter blir oanvändbara/stale och källplanen blir förfallen. Ingen maskinklocka eller observation skrivs om. Kampanjutgång och kortare dagsvillkor provas dessutom separat i sluttesterna.

Lund ger exit 2 i rebuildfaserna eftersom original-Willyspriserna är äldre än 36 timmar men ännu yngre än 48. Det är en korrekt färskhetsvarning, inte ett Lidl-importfel. Willys-observationerna är fortfarande 21 september cirka 23:31–23:59Z. Ingen ny Willys-nätinsamling gjordes.

## Faktiska nätanrop och replay

Verklig begränsad Lidl-insamling från slutpaketet: [paketkvittens](package-live-verification/verification.json), 10 externa anrop totalt, 7 produktflödessidor. Driftproven använder separat verklig insamling från 23 september cirka 15:28Z som hashkontrollerad replay. Varje app/child/harness tillåter endast loopback; externa försök är noll. Collector-dokumenträknare är inte ett mått på nya nätanrop.

Den första Lund-harnesskonfigurationen gav otillräcklig receptbas med bara Lidl/Coop-erbjudanden. Ordinarie publicering stoppade den korrekt. Ett senare harnessfel hade fel filnamn i Willys-inboxen: den kräver SHA256-filnamn. Det rättades i verifieraren och normal källimport kördes. Inga pris-, färskhets- eller publiceringskrav sänktes. Misslyckade försök finns kvar i separata provmappar/kvittenser och räknas inte som acceptans.

## Nästa uppdateringar i de verifierade privata instanserna

| Källa | Nästa steg/tid (Europe/Stockholm) |
|---|---|
| Lidl aktuella kampanjprodukter, båda kommunerna | 25 september cirka 04:28:27, gemensam 35-timmarskontroll. |
| Lidl butiksinventering | 26 september, cirka 17:30 i Malmö / 17:31 i Lund; exakt privat tid finns i `selection.next_inventory_check`. |
| Nationellt Lidl-blad | Produktkontrollen hämtar aktuell listning/metadata. Nytt/ändrat blad kräver ny textgranskning; nuvarande kampanj slutar 27 september. |
| Bevarad City Gross Hyllie-bas | 23 september 23:00 enligt bevarat kampanjstyrt tillstånd. |
| Bevarad Willys Lund-bas | Reläets 35-timmarskontroll är redan förfallen; originaltid och 48-timmarsstopp står kvar. Ingen basinsamling påbörjades i Lidl-uppdraget. |

Den separata slutpaketshämtningen runt 17:45 Stockholm har sina egna verkliga observationstider och OWN-databaser. Den ersätter inte i efterhand driftprovens källreferenser eller uppdateringskvittenser. Inga scheman har aktiverats i produktion.

Maskinkvittenser: [Lund](runtime-final-lund/ACCEPTANCE.json), [Malmö](runtime-final-1280/ACCEPTANCE.json), respektive `result-*.json`, `purchases.json` och nätloggar.
