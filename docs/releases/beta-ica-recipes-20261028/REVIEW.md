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

Skyddat operatörsunderlag: `.local/beta-all-20261028/` och serverns
`/srv/app/var/reports/beta-all-20261028/`. Dessa innehåller inga källnycklar
i publicerade rapporter och checkas inte in.
