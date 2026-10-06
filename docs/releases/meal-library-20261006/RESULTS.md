# Gemensamt måltidsbibliotek – separat från betaaktiveringen

## A. Utfört appbyte

Beta kör den godkända dd12-imagen, BUILD_ID `status-reconnect-dd12cc80e98c`,
kompletta recept på. Endast appen ersattes; data, mounts, scheduler, relä och
proxy bevarades. Backup och fingeravtryck finns i den
[separata aktiveringsrapporten](../status-activation-20261006/RESULTS.md).
Riktiga publika/personliga mobilflöden passerade med faktiskt publicerade priser.
Kontoinloggning var avstängd; proven gäller gäster.

Den första WebKit-körningens statuslatensavvikelse är bevarad. Omkörningens
PASS bevisar inte orsaken. Senare diskbrist gjorde planlagringen otillgänglig.
Endast användarens godkända nya byggmappar arkiverades till D: med hashkontroll
och deras verifierade serverkopior togs bort. Planlagringen fungerar igen.
Driftkontroll 6 oktober 20:36:31 UTC: rätt image/JavaScript, `/health` 200, `/ready` 503 för
två för gamla Willys-underlag. Färskhetsgränser och insamling är oförändrade.
Etapp B har aldrig aktiverats. Rotdisken hade endast 172 077 056 byte ledigt; större städning är inte godkänd eller utförd.

## B. Implementerad måltidskandidat

Runtime **`fd2cfda5490ac93295e6a2cef6b6b8408497f89e`**, lokal gren
`feature/meal-library-20261006`. Gemensam befintlig produkt-, mängd-, närings-,
veckokorgs-, audit-, jobb- och revisionsväg för middag, frukost och mellanmål.
Antal, portioner, ingrediens-/tidsval, frivilliga näringsmål och upprepning
anges per måltidstyp. Middagens köks-/proteinfördelning behåller sin betydelse.

JSON-paket valideras, diffas, importeras atomiskt, förbereds och kvalificeras
genom [körbara kommandon](../../recipes/MEAL-LIBRARY.md). Utfärdade versioner
bevaras. Struktur, portionsskalning och offentliga faktaprojektioner
återanvänds med beroendeindex och hashkontroller; aktuell begäran och slutlig
audit prövas alltid. Ny tidigare saknad produkt kan upphäva ett negativt resultat.
Källinvalidering är konservativ och kan bygga om hela källindexet.

24 pilotrecept: åtta enkla middagar, åtta frukostar, åtta mellanmål.
Fullständiga definitioner finns i [pilotpaketet](../../../backend/app/data/recipes/pilot-20261006.json)
och [det andra sexreceptspaketet](../../../backend/app/data/recipes/extension-second-20261006.json).
Piloten är nytt författat innehåll; det befintliga bibliotekets 152 aktuella
recept registreras genom manifestet med oförändrade utfärdade definitioner.
Ett separat sexreceptspaket tillkom genom samma innehållsväg i en fryst
implementation: sex nya grundrätter, oförändrad omimport, ingen kodändring.
[Data-only-bevis](DATA-ONLY.json) skiljer 668 låsta Git-filer från 610
faktiskt jämförda imagefiler. P2→P3 ändrar endast tre recept-/manifestfiler.
Två tidigare felaktiga innehållsversioner är återkallade; deras numeriska PASS
och gamla sparade revisioner bevaras men räknas inte som godkänd leverans.

Inga nya produktfakta eller priser har importerats. Detta är
[berikad historisk replay](PRICE-BASIS.json), inte en aktuell prisoffert.
Innehållet är författat och strukturellt granskat, inte fysiskt provlagat.

## Verifiering och ekonomiska resultat

[Webbprov](BROWSER-EVIDENCE.json) använder verkliga jobb, den paketerade
imagen och riktiga revisions-GET i Chromium/WebKit med mobil layout.
Omladdning, kontrollerade avbrott, förlorat accepterat startsvar, dubbelstart,
byte, omräkning och faktisk appomstart ingår. En instrumenterad tung
beräkning per ursprunglig begäran; byte och omräkning är egna avsiktliga jobb.
Flagga av i samma image bevarar äldre och nya revisioner samt äldre menyflöde.
Det kvalificerar inte en äldre binäråtergång.

[Kompatibilitet](COMPATIBILITY.json): fyra äldre 15/20-profiler med oförändrade
40/30/20-krav, privat skafferi utan dubbelanvändning, ägarisolering samt 267
historiska revisionsrader lästa oförändrat. 97 relevanta Pythonprov och tio
transportprov passerade. Ett spontant statusanslutningsfel i API-testklienten
är bevarat; backendjobbet fortsatte och oförändrad omkörning passerade.
Exakt orsak är fortsatt obelagd. [Historik](HISTORY.json).

[Fullständiga menyer och inköpsrader](MENU.md), [maskinläsbara menyer](MENUS.json)
och [P0–P3-jämförelser](COMPARISONS.json) skiljer samma huvudmat från nya fria
menyval. Recept-/korg-/närings-/auditjämförelsen normaliserar bara uttrycklig
teknisk metadata; prisobservationer och köpavtal jämförs fortfarande.

| Samma begäran, oförändrade fakta | P2: 24 pilotrecept | P3: plus sex recept | Förändring |
| --- | --- | --- | --- |
| Befintligt huvudfall, 20 portioner | 741,15 kr | 741,15 kr | 0,00 kr, samma mat och korg |
| Fem enkla middagar för två | 328,16 kr | 262,28 kr | −65,88 kr, andra receptval |
| Fem frukostar för en | 40,70 kr | 40,70 kr | 0,00 kr, samma mat och korg |
| Fem mellanmål för en | 56,86 kr | 56,86 kr | 0,00 kr, samma mat och korg |
| 5×4 middag + 5×1 frukost + 5×1 mellanmål | 495,44 kr | 418,17 kr | −77,27 kr, andra receptval |

De nya biblioteksfallen har inga proteinmål; köp och separat näringsmedgivande
är uppskattat/tillåtet, tomt skafferi, högst tre inköpsställen. Nutrition
NOT_REQUESTED är inte ett 30/40-godkännande. Allergener NOT_REQUESTED är inte
allergenfrihet. De äldre 40/30/20-profilerna och det gamla huvudfallet provas
med sina uttryckliga mål. Lägsta hittade kostnad inom valen, inte bevisad
global optimalitet. Planerade rester räknas inte som skafferi eller framtida värde.

## Prestanda och kvarstående arbete

Två CPU, 3 GiB och en tung beräkning åt gången i isolering. Full tidsmatris,
råtider, medianer, spridning och minne redovisas i
[prestandarapporten](PERFORMANCE.md). Huvudklick utan navigationsinjektion 63,81/72,30 sekunder:
60-sekundersmålet är inte uppnått. Kall huvudstart blev långsammare än dd12;
minnestoppen minskade. Små nyplaneringar och förberedelsekostnad redovisas
separat. Ingen sökbudget eller kvalitetsgräns sänktes.

Alla slutliga prov är färdiga: [30 individuella kvalificeringar](QUALIFICATION.md),
1×/2×/5×-[skalprov](SCALE.md), kontrollerad invalidering och hela P0–P3-
tidsmatrisen. Vid 5× tar huvudfallet 919,89 s; minnestoppen är 1,62 GiB.
Relevant bibliotektillväxt är fortfarande dyr i söktid. Små kalla
frukostprov växer 55,59→78,29 s. Ingen snabb storbibliotekssökning påstås.
CLI-förberedelse 42,61 s med 42,57 CPU-s, andra körningen i samma process
22,92 s med giltiga artefakter. Cirka 8,55 MB lagring, återanvändning och
konservativ källinvalidering redovisas separat.

Ett autentiskt fast integrationsprov använder 150 + 150 g samma yoghurt
över middag och frukost, summerat till 300 g före köp av en 1 000-g-förpackning.
Oberoende audit passerar. Det är köpbarhet/samordning, ingen fri besparing.
[Uppdateringsoperander och korgar](INCREMENTAL.json) visar även att nya fakta
och tidigare saknad produkt ändrar utfallet, en ny receptversion ger en ny
strukturrad och att kampanjutgång slår igenom i faktisk checkout. Injektioner
är testoperander, inte publicerade fakta.

### Acceptans och återstående begränsningar

**Nästa vanliga receptpaket kan läggas till utan ny specialkod: verifierat.**
Sex nya recept importerades idempotent med fryst runtime, kvalificerades,
användes i fria planer och renderades/sparades/återlästes. Giltiga offentliga
förberedelser återanvänds mellan måltidstyper och nya begäranden. Varje
begäran prövar fortfarande privata villkor, aktuella köpavtal och slutlig audit.

**Snabbare planering för varje bibliotekstillväxt: inte uppnått.**
Huvudklick är över 60 s, kalla processer långsammare än dd12 och relevant
5×-sökning tar drygt 15 minuter. Minnesfelet är rättat; generell vidare
sökoptimering återstår. Full cachekapacitet ger säker beräkning i minnet
i stället för automatisk rullande generationsutrensning.

Inga nya faktarader behövdes för dessa 30 recept. Äldre öppna researchärenden
för paprika, chili, majs, pita, mjölk och ägg kvarstår; blandade SKU-storlekar
är fortsatt en separat funktionslucka. Inget av detta användes som genväg.

**FÄRDIG ISOLERAD APPKANDIDAT FÖR SEPARAT AKTIVERINGSBEDÖMNING.**
B är inte installerad. Driftförkontroller behöver åtgärdat källunderlag och
tillräckligt diskutrymme före ett framtida byte; inga sådana ändringar ingår här.

Paket `smako-server-fd2cfda5490a.zip`, SHA-256
`342b74f913ce0625ee78bcdf283f02937273e9b36b730d26216ec55ffd5014e3`;
image `sha256:b8541e165a2075c4c5657e1296c83e276f3aa8f59607292e32b653b60a7655fb`.
[Separat app-only-anvisning](ACTIVATION.md). Ingen B-aktivering eller Git-push.

## Två separata slutstatusar

| Etapp | Faktiskt utfall | Beslutsgräns |
| --- | --- | --- |
| A: dd12 | Aktiverad och publikt/personligt verifierad med aktuellt publicerade priser och gästägarsessioner. Senare planlagringsfel efter diskbrist avhjälpt genom exakt godkänd arkivering. | Beta är nu inte ready på grund av stale Willys-underlag, och diskutrymmet är litet. Första WebKit-latensens grundorsak är obelagd. |
| B: måltidsbibliotek | Implementerad, 24 + 6 kvalificerade recept, data-only-import, gemensamma korgar, fjorton strikta mobilflöden, gamla profiler/revisioner, paketerad slutimage och full prestandamatris. | Inte aktiverad. Under 60 s och snabb relevant 5×-sökning återstår. Kräver separat appbeslut och nya aktuella driftförkontroller. |

[Evidensindex med filhashar](EVIDENCE.json), [testomfattning](TESTS.md),
[bevarade fel](HISTORY.json). Senare dokumentationscommits ändrar inte
slutruntime eller paketet.
