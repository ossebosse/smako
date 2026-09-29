# Willys kommunstöd och återkommande rebuild, 22 september 2026

Slutkontroll återupptagen **23 september 2026 cirka 08:08 Europe/Stockholm**.
Malmös båda sparade byggen var klara före avbrottet. Slutkodens 276 paketerade
Python-filer har jämförts på nytt utan skillnader. Lunds äldre testbas innehåller
nu en källa över 48 timmar; den spärras och får inte användas för ny aktivering.
Willys-källorna är fortfarande under 36 timmar vid denna kontroll.

Kommunstyrd Willys-insamling är implementerad som ett uttryckligt tillval i den befintliga vägen. Samma kod väljer Lund 1281 och Malmö 1280 från nationellt register och verifierad SCB-geometri. Inga manuella butikslistor styr det nya läget. ICA/Coop/X:-tra, Primat, användarprofiler och skarp drift är bevarade.

## Genomförd rättning

- Befintlig discovery och fullkatalogtransport har fått kommunurval. Källartefakten bevarar kommungräns, version/hash, alla butikskontexter och originalobservationer; mottagaren verifierar själv hela urvalet och sidföljden.
- Beständigt reläval (`source-scope.json`) och explicit serverkonfiguration (`WILLYS_MUNICIPAL_CONFIG`) styr vanlig insamling, import och byggare. Godkänt urval följer OWN-snapshotens metrics; nästa rebuild behöver inga handskrivna butiksargument.
- OWN-provider matchar exakt källbutik, fysisk identitet, kanal, adress och normaliserat **butikspostnummer**, även när adressorten är Limhamn. Kundens postnummer krävs inte vara identiskt. Ett faktiskt postnummerformatfel hittades i första privata provet och rättades; godkända men saknade butiker stoppar nu publicering.
- Befintligt operationslås, atomisk artefakthantering, snapshotvalidering, freshness, prisroller, medlemskap och checkout är kvar. Inga pris- eller näringskrav sänktes.

## Verifierade steg

| Prov | OWN Willys | PriceUniverse Willys | Coop-tillskott bevarat | Utfall |
|---|---:|---:|---:|---|
| Lund, första godkända rebuild | 18 824 | 18 642 | 493 | Privat publicering/reload, health/ready 200; 303,823 s |
| Lund, andra ordinarie rebuild | 18 824 | 18 642 | 493 | Samma PU-ID och full prispostsignatur; 269,263 s |
| Lund, ny process/container, samma beständiga data | 18 824 | 18 642 | 493 | Samma PU-ID, källtider och prispostsignatur; 281,028 s |
| Malmö, samma import och produktionsbyggare | 39 274 | 38 950 | Ej del av denna byggomfattning | OWN-only kandidat; bygge 143,161 s, föregående offlineimport 391,137 s |
| Malmö, ny process/container och ombyggnad | 39 274 | 38 950 | Ej del av denna byggomfattning | Samma prispostsignatur och inga nya importer; 140,058 s |

PU-ID i Lund: `price-universe:891df9ae8a1e2f84bac34a6d16c69c274cd4b00539f8451f9cd08637103bac92`.

PU-ID i Malmö: `price-universe:00584f824f3bdd111de0c048a368eb25e7a04bc0a617568fb5a23827d75b8b9f`.
Malmös fyra exakta butiker och prisvillkor är identiska mellan byggena.
Detta verifierar kommunurval → verklig insamling → validering → OWN → vanlig
produktionsbyggare, men **inte** en full federerad Malmö-publicering/reload med
färsk Primat-bas. Den kontrollen återstår inför en sådan driftaktivering.

Lunds prov använder kompletta sparade baskällor inklusive Primat; ingen begränsad lokal sökprojektion ersätter källorna. De andra körningarna gör lokala rebuilds, **inte** nya basprisinsamlingar. 18 642 är produktposter i PriceUniverse, inte antal näringsgodkända produkter eller valda menyingredienser. Ingen ny 15/20-besparing påstås.

Reläet kontrollerades i två separata processer med faktisk klocka och sparad kommun-/publiceringskvittens: 0 externa anrop när inget var förfallet. Kommunval och nästa uppdatering överlevde omstart. Vid explicit +49 timmar i testklockan spärrades båda Willys-kontexterna av oförändrad 48-timmarsregel. Befintliga kampanjtester verifierar dessutom att utgångna avtal inte fortsätter vara användbara.

Jobben gav korrekt exit 2/varningsläge eftersom en bevarad baskälla var äldre än 36 timmar, **inte** på grund av publiceringsfel. Underlaget låg ännu under 48-timmarsstoppet. Inga källobservationer föryngrades.

Vid återupptagandet 23/9 ger samma sparade Lund-artifakt `degraded`, med en
utgången kontext utesluten. Malmö-artifakten är `fresh`, fyra användbara kontexter.
Se `decision-current.json`. Den skarpa manifestreferensen har ändrats över natten
(`production-readonly-final.json`); uppgiften har endast läst den och har inte
aktiverat denna kandidat eller ändrat produktionens schema.

## Täckning och avgränsningar

- Lund: 3 verifierade kommunbutiker, 2 verifierade onlinekataloger. Hemma Stortorget kvarstår utan verifierad katalogtransport.
- Malmö: 10 verifierade kommunbutiker, 4 verifierade onlinekataloger. Limhamn omfattas via position; Oxie är också innanför, men saknar verifierad onlinekatalog i detta flöde.
- Nationellt register: 257 namngivna fysiska butiker och en oidentifierad rad 2002. Alla 258 rader finns kvar, inklusive utanför/okänd. Ingen oberoende total för hela kommunernas fysiska butiksutbud finns; full fysisk pristäckning påstås inte.
- Kanalen är butiksknuten **online_price**. Butiker utan `onlineStore=true` behöver en separat verifierad fysisk källa; deras priser kopieras inte från närliggande onlinebutiker.
- City Gross har redan full onlineinsamling och OWN/PriceUniverse-stöd; kommunurvalet återstår. Lidl har erbjudandeinsamling, men fysisk kommun-/regiongiltighet behöver kompletteras. Se kedjetabellen.

## Läs vidare

- [Butiksvis täckning](COVERAGE.md) och [alla 258 registerrader](ALL-STORES.md).
- [Kedjestatus och konkreta nästa steg](CHAIN-STATUS.md).
- [Tester, nätinsamling och reproduktion](VALIDATION.md).
- [Separat releaseunderlag](RELEASE.md).
- `decision-evidence.json`, `server-results/`, `malmo-resume-result.json`, `tests-final.xml` innehåller mätresultaten.

Inget produktionsunderlag, aktivt schema eller Windows-uppgift ändrades. Det förberedda kommunöverlägget är inte applicerat; väntande ICA-release har sitt separata aktiveringsbeslut.
