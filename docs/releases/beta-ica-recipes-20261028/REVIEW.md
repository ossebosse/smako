# Samlad betarelease, 2026-10-28

Ägaren har beställt Malmö ICA-baspriser och aktivering av tvånattsschemat
tillsammans med allt integrerat recept- och beräkningsarbete. Tidigare
begränsningar mot betaaktivering i receptuppdragen är därmed ersatta för
denna release. Aktivering måste fortfarande verifieras separat.

## Malmö, verifierat inför releasen

ICA:s befintliga kommununderlag från 2026-10-28 ger 24 godkända fysiska
butiker. Deras verkliga orter bevaras. Primats upplösning av prisområdet
21120 gav 11 ICA-kontexter; samtliga matchades med exakt officiellt butiks-ID,
inga fuzzy-kopplingar. Av dessa är två fullständiga baskontexter:

- ICA Kvantum Malmborgs Caroli, 1004490.
- Maxi ICA Stormarknad Västra Hamnen, 1003569.

Ett separat avgränsat produktprov gav 49 respektive 51 prissatta mjölkprodukter
med verifierad proveniens. Båda kopplingarna kvalificerades genom befintlig
`ProviderContextSmokeActivationService`, först i databaskopia och därefter
under driftlåset i det gemensamma registret. Övriga träffar är offers-only.
24 kommunbutiker innebär inte 24 baspriskällor; andra orter byter inte namn.
Slutlig insamling och publicering återstår vid denna granskningspunkt.

Provet hittade att den gamla Primatläsarens `immutable=1` ignorerar nya
WAL-commits. Läsaren använder nu vanlig skrivskyddad SQLite och `query_only`.
Ett regressionstest håller WAL-skrivaren öppen och verifierar både återkallad
och återgodkänd kontext utan checkpoint och utan ändring av huvudfilen.

## Releasens omfattning

Appen ska innehålla hela integrerade biblioteket: 2 462 aktiva varianter,
inklusive alla 2 200 importerade referenser och deras granskade nya versioner.
Mängd-, berednings-, närings-, korg- och offertberäkningar tas från samma
granskade main-träd. `LIBRARY_SEARCH_POLICY=smako-current-library-v2` aktiverar
den verifierade sökningen; experimentell sammanslagning av generationer
förblir avstängd. Befintliga verkliga användarprofiler och planer bevaras.

[Senaste frysta verifiering](../../reviews/top-five-ingredients-20261028.md):
2 024/2 200 hela korgar inklusive uppskattningar och 1 140 exakt hela.
Detta är historiskt verifierad täckning i ett specificerat prisunderlag,
inte en garanti för varje ny insamling eller alla personliga val.

App- och schedulerbilder ska byggas på respektive verklig pinnad driftimage.
Git-ändringar och redan integrerade källrättningar granskas mot faktiska
filhashar. Tidigare dokumenterat stöd för adminlösenord i aktiv appkonfiguration
bevaras uttryckligen. Hemligheter och produktionsdata ingår inte i paketen.
Ordinarie driftlås, backup, kandidatkontroll, återställningsväg och efterkontroll
gäller. Windowsreläets befintliga uppgift ska bindas till verifierat paket och
måndag/torsdag 03:17 svensk tid. Ingen genomförd aktivering påstås i denna fil.

## Granskade ingrediensfakta i vanlig faktaladdning

Inför aktiveringen hittades en verklig integrationslucka: 66 redan granskade
produktdeklarationer var med i det frysta faktaunderlaget men saknades i den
vanliga faktaladdningen. De finns nu i en liten versionshanterad projektion
under `backend/app/data/ingredients/issued-compositions-20261028.json`.
Varje post måste finnas exakt i befintlig utgiven ingrediensregistry och
ge samma tidigare godkända sammansättningshash. En oregistrerad äldre
pektinkoppling uteslöts. Exporten binder faktaunderlagets hash ovan.

Befintlig `reviewed_ingredients` kompletterar endast saknad sammansättning.
Den återanvänder samma exakta produkt-, förpacknings-, käll- och butiksgate
som receptkvalificeringen. Ny prisgeneration kräver fortfarande samma
verifierade livsmedelsidentitet; originalkällans observationstid och tidigare
bindning bevaras i evidensen. Avvikande aktuell deklaration eller konflikt
skrivs aldrig över. Priser, mängder, näring, allergenkontroller, personliga
godkännanden och övriga befintliga fakta ändras inte av denna komplettering.
76 riktade nya tester inklusive vanlig faktaladdning, identitetsgränser och
ny prisgeneration passerar. Befintliga faktaladdnings-/Axfood-/offertfaktatester
passerar separat. Ny metodhash måste användas för härledda cacheartefakter;
de historiska täckningssiffrorna ovan skrivs inte om till nya mätningar.

Det senaste granskade Axfood-detaljarkivet är
`b11ed75863be1547755ee78be5143ba737d5ea3564acc1cadaa0feb6b4ebf0a8`:
111 verifierade Willys- och 12 Hemköpsdokument samt 18 negativa svar.
Det installeras med hashkontroll och skyddade filer i befintlig datavolym;
`AXFOOD_PRODUCT_DETAIL_ROOT` binder den exakta releasen. Detta aktiverar
faktaläsaren och startar ingen ny produktdetaljinsamling.

## Bounded återkörning av underhåll inför bytet

Första förkontrollen avbröts med SIGINT i vår egen underhållsprocess;
ingen extern insamling avbröts. Den hade fastnat i upprepade relationsprober
för pensionerad råmetadata vars kroppar redan saknas. Ett läsande prov gav
1 000 pensionerade råreferenser och noll befintliga filer. Ingen image hade
byggts eller aktiverats. Tidigare slutförda snapshottransaktioner består.

`snapshot_retention` filtrerar nu säkert redan saknade kroppar före dessa
prober. Alla befintliga kroppar går fortfarande genom färsk relationskontroll,
sökvägs-, hash- och ändringskontroll före borttagning. Råmetadata behålls.
Ett regressionstest med 200 extra saknade kroppar verifierar både preview
och apply utan upprepade relationsprober och att otillåtna sökvägar stoppas.
Befintliga skydds-, avbrotts-/återförsöks- och underhållstester passerar.
Det korrigerade, granskade underhållet används också i det avgränsade
förkontroll-/backupförloppet innan den nya schedulern är aktiverad.

Skyddat operatörsunderlag: `.local/beta-all-20261028/` och serverns
`/srv/app/var/reports/beta-all-20261028/`. Dessa innehåller inga källnycklar
i publicerade rapporter och checkas inte in.

## Slutlig kandidatverifiering

Kodreferens `2b65533af00d6355bd9370a18b9f613337c7ed2d`, integrerad via PR40
som `2f033b8`, har grön hosted CI även på main. De slutliga bilderna har
BUILD_ID `beta-all-2b65533af00d`. 373 appfiler och 429 schedulerfiler
verifierades mot deklarerade filhashar; övriga runtimefiler och befintliga
admininställningar bevarades. Git-blobbarna för receptdata används exakt,
inklusive deras deklarerade radslut. Inga beroenden eller databasscheman ändras.

Exakt appimage klarar import, alla 2 462 aktiva varianter och samtliga
66 utgivna kompositionskopplingar. Nätverkslös förberedelse av båda verkliga
prisunderlagen, portioner 1/4, klarade 186,81 s med 2 CPU och 3 GiB-gräns;
uppmätt minnestopp var 2 980 331 520 byte. Detta mäter förberedelse,
inte konsumentens menyberäkning. Båda kommunernas körplaner var utan
källanrop på onsdagen och källor förföll på torsdagen enligt veckopolicyn.

Den slutliga insamlingen gav 2 645 produktposter för Malmös två godkända
ICA-kontexter. Lund gav 1 964 poster: aktuell hämtning från Maxi Gunnesbo
och kvalificerad tidigare data för Clemenstorget. Primat anger numera
Clemenstorget som offers-only; dess tidigare baspriser behålls enligt
ordinarie LKG-policy med ursprunglig observationstid. Ingen erbjudandekontext
uppgraderas. Varje lyckad kommunhämtning använde 49 anrop; en separat
rate-limit-händelse bevaras i operatörsunderlaget och följdes av väntan.

Windows fullpaket `2b65533af00d` är installerat och verifierat, men den
befintliga S4U-uppgiften kräver administratörsrättighet för registreringsbytet.
Den hade återgått till Ready när försöket gjordes. Ingen ändring registrerades;
det äldre schemat kan därför inte beskrivas som aktiverad tvånattspolicy.
Faktisk serveraktivering och publika slutprov journalförs separat.

## Modellavvikelse hittad vid första prispubliceringen

Första fullständiga prisbygget efter imagebytet behöll korrekt de gamla
prismanifesten när ett `AttributeError` uppstod. Aktuell incident är
`pipeline-bb0aba4c93d836fce99a07bc`, Lund 18:56:50 UTC, med samma fel även
i Malmö. Stacken går genom ekonomiskt urval och `BasketCalculator.quote_item`
till saknat `ProductCandidate.purchase_units`.

Den första schedulerpaketeringen hade bevarat fyra äldre runtimeavvikelser
genom exakt kommuterande patchning. Dessa var saknade redan granskade
funktioner i förhållande till main, inte nödvändiga driftutökningar. Att
patchningen kommuterar bevisar inte modellkompatibilitet. Appens motsvarande
filer var redan identiska med main; dess image behöver inte ändras.

Ett korrigerat schedulerpaket installerar exakt main-versionen av
`models/product.py`, `services/beta_observability.py`,
`services/price_universe_runtime.py` och `services/product_search.py`.
Det återställer bland annat köpantalsfältet, räknad viktgräns med validering,
kommunval, befintlig feldiagnostik och publicerings-/cachekontrakt. Alla
övriga runtimefiler och all konfiguration jämförs med den då faktiskt aktiva
schedulerbilden. Ingen pris- eller mängdgräns kringgås.

Den misslyckade Malmöbyggarens färdigställda, integritetskontrollerade
slutna SQLite-underlag behölls som en avgränsad diagnostikfil före dess
temporärkatalog togs bort. Det används skrivskyddat med oförändringskontroll
för båda kommunernas fullständiga kandidatbyggen och samma slutna ICA-cacher.
De faktiska byggena, med nätverket avstängt, måste passera före schedulerbytet.
Ordinarie managed refresh validerar sedan kandidaterna och snapshotlinjerna
igen före atomisk publicering. Laddning måste bekräftas med exakt pris-ID
per kommun; ett återladdningssvar med oförändrat gammalt ID räcker inte.

## Gemensam receptförberedelse i det vanliga körflödet

Det första publika Malmöprovet för tre recept/två portioner nådde 60-sekunders-
gränsen innan sökningen hann börja. Det fanns 455 individuellt kvalificerade
recept, noll prissatta kombinationer och inget omöjlighetsbevis. Samma krav
gav en helt reviderad meny på 53,02 s efter gemensam förberedelse 1–4.
Den tidigare förberedelsen 1/4 täckte inte hela den vanliga gästvägen.

Den befintliga `schedule_source_facts_prewarm` förbereder nu även aktuellt
bibliotek, portionsvyer, deklarationer och ingredienspositioner med samma
verifierade universe/faktamappning. Detta gäller endast uttrycklig
`smako-current-library-v2`; legacy/V1 behåller sitt tidigare faktaladdningsflöde.
Den körs efter uppstart och varje ny godkänd runtimeaktivering. En upprepad
leverans av samma pris-ID behåller sina cacher. Bakgrundsarbeten serialiseras,
tar ingen plannerplats och skapar inga menyer eller köpbeslut. Cachefel blir
synlig partial/failed-status och ändrar aldrig en godkänd prisaktivering.

Riktade tester täcker exakt scope/faktabindning och portioner 1–4, avstängd
funktion, legacy, cachefel, högst en tung förberedelse samt validering/atomiskt
byte före schemaläggning. Fel i den valfria schemaläggningen behåller giltiga
priser; samma pris-ID startar inte om förberedelsen. Ruff och compileall passerar.
