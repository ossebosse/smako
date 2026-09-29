# City Gross kommunstöd – separat releaseunderlag

Datum: 23 september 2026. Kod och isolerade verifieringsartefakter, ingen
produktionsaktivering. Utgångspunkt är arbetskopian på
`areas/municipality-audit-20260920`, HEAD
`02ad73b8491f4b30679b3151b52686e27bedb8e6`, inklusive redan pågående
ICA-/Coop-/X:-tra-/Willys-/Primat-arbete. HEAD ensamt beskriver inte basen.
[initial-state.json](initial-state.json) och säkerhetskopior anger faktisk bas.

## Problem och levererad kod

Kommunvalet styr City Gross från officiell helinventering till återkommande
insamling, bevarat uppdateringsstate, OWN, vanlig PriceUniverse-byggare,
atomisk publicering och administrativ reload. Samma gemensamma SCB-funktion
som övriga kedjor används; lokala ortnamn eller handskrivna butikslistor väljer
inga butiker. Lunds tomma urval undertrycker även den gamla ortsbaserade
City Gross-källan. Utanför, okänd och misslyckad butik behåller synlig status.

Parser v4 bevarar redan hämtade ItemsTotal-kampanjer för en vara.
Ordinarie pris, kampanjpris och medlemspris förblir olika roller. Köp med
ej stödda minimibelopp/kupongvillkor får inte rabatten. Köptak per varukorg
följer befintlig provenance till checkout/audit och kan inte tappas genom
ekonomisk dominanspruning. Kampanjens rabattak behåller sin egen betydelse.
Ofullständiga katalogsvar kan ge radgodkända onlineerbjudanden som
`offers_only`; giltig full katalog behålls tills dess egna färskhetsgräns nås.

Fullkatalogsökning återanvänder OWN:s befintliga queryfunktion med exakt
butiks-UUID och återger endast redan validerade produktprojektioner.
Slutmaterialiseringen behåller hela den godkända katalogen.
Ingen ny matchare, prissättare eller scheduler har införts.

## Kodgräns

- Ny officiell inventering och kommuncollector/replay under
  `grocery_data/app/connectors/citygross` och `grocery_data/scripts`.
- Ny `citygross_municipal_job.py`: beständig konfiguration, källreferenser,
  behov, felstatus, färskhet och återhämtning.
- Ny `citygross_municipality.py` i backend binder exakt källa till OWN.
- Befintlig `daily-refresh`, produktionsbyggare och refresh-runner ansluter
  den frivilliga källan; default förblir avstängt och kräver normal extern bas.
- Gemensamma bygg-/publiceringskvitton extraheras från Coops befintliga väg.
  Coops funktion och wrappergränssnitt behålls och regressionstestas.
- Befintliga prisavtal/radvalidering återanvänds; SourceProvenance får
  valfria villkors-/URL-fält som inte skrivs för äldre poster där de saknas.
- Den redan befintliga uttryckliga inställningen `OWN_SOURCES_ONLY` respekteras
  även av daily-refresh. Saknad Primat-bas slår aldrig automatiskt på läget.

För exakt inkrement, före-/efterhashar och nya filer se release-manifest och
`changes.patch`. Patchen avser den sparade arbetskopian, inte en ren HEAD.
Kopiera inte hela denna arbetskopia över andra pågående releaser.

[Tester/bevarande](TESTS.md) redovisar 255 godkända olika tester med ordinarie
klocka och ett separat historiskt fixtureprov. Ruff/compileall är godkända.
[Produkt-/receptköpen](PURCHASES.md) passerar matcher, checkout och audit i
båda butikerna. Den generella färsk-tomat/passata-luckan är synlig i rapporten;
receptprovet använder en uttryckligt verifierad färsk produkt.

## Verifieringsunderlag

[Inventering/insamling](INVENTORY-COLLECTION.md) skiljer 274 verkliga
kataloganrop från nollnät-replay med parser v4. Hyllie har 13 523 och
Staffanstorp 13 780 godkända katalograder, noll produktkarantän. Elva
rabattavtal per butik har synligt ej stött minimiköpsvillkor och spärras.
[Semantikrapporten](PRICE-SEMANTICS.md) och [exempeldata](offer-examples.json)
har tre aktuella egna källbevis per butik, inklusive butik, kanal, GTIN,
förpackning, prisroll, giltighet, antal och officiell produktlänk.

Isolerad drift använder den riktiga runnern, dess daily-refresh-subprocess,
vanlig builder, faktisk lokal publicering och lokal HTTP-reload. Detaljer,
fasvisa kodhashar, processomstarter och nätmätning finns i driftprovet.
Första utvecklingsbyggena har mellanversioner och räknas inte som bevis för
identisk slutkod. Märkt replay återanvänder originalens observationstider;
fel injiceras separat. Testkonfiguration eller simulerat state är inte skarpt
releaseinnehåll.

Slutresultatet är [PASS](runtime-final/ACCEPTANCE.json). Nollbehov,
injicerat hämtfel och återhämtning använder identiska slutkodhashar. Fel- och
återhämtningsfaserna gör var sin vanlig full rebuild, publicering och reload:
13 523 City Gross-poster har samma pris-/provenienssignatur och originaltider.
Varje fas startar ny appprocess med beständigt kommunval och status.
Health/ready är 200. Förfallsprov med uttrycklig framtida testtid utesluter
källan utan att skriva om observationer. Inga externa nätförsök sker i
driftprovet. Se [full driftredovisning](RUNTIME.md).

Riktade tester täcker kommunurval/identitetsfel, nollurval, offers-only,
fel/retry/LKG, källintegritet, omstart, två rebuilds, kvitto/reloadfel,
behovskontroll utan externa prisanrop, prisroller och köpbegränsningar.
JUnit/loggar bevaras inklusive första felande försök. Två äldre
City Gross-assertioner uppdaterades för redan införda GeographicArea-fält.
Ett oförändrat historiskt Willys-medlemspristest använder utgångna kampanjdatum
och misslyckas med dagens testklocka; det passerar separat märkt replay på
fixture-datum 19 september. Inga sparade prisdatum eller Willys-testfiler ändras.

## Beständig drift och framtida aktivering

Konfiguration, kommandon och datakatalog anges i
[docs/citygross_municipality.md](../../docs/citygross_municipality.md).
`CITYGROSS_MUNICIPAL_ENABLED` förblir avstängt i skarp miljö.
En framtida installation behöver aktuell verifierad bas för vald kommun,
beständig kommunrot, normalt operationslås, befintligt schema och vanlig
publicerings-/reloadväg. Bekräfta health/ready och manifest efter aktivering;
ett rent fetch-resultat är inte ett reloadkvitto.

Vid återställning används tidigare kod och ett fortfarande färskt verifierat
underlag. Ingen gammal snapshot får föryngras. Stängd frivillig City Gross-väg
tar inte bort dess granskningsunderlag. Gamla lokala testmanifest och utgången
federerad bas är inte giltigt rollbackunderlag.

## Avgränsningar och nästa arbete

Drift- och köpproven är uttryckligen isolerade OWN-only-prov. Full federerad
Malmö-publicering med aktuell komplett Primat-/övrig bas återstår; befintliga
färskhetsregler har inte lättats för att få ett grönt prov. Den aktuella
[basinspektionen](base-current.json) saknar verifierad Malmö-Primat-kontext
och har utgången Coop-onlineobservation. Detta är inget aktiveringsbesked.

[Willys sju butiksluckor](WILLYS-GAPS.md) beror på officiell
`onlineStore=false`. Varje butik har en egen verifierad publik reklambladslänk;
oförändrad connector kan ännu inte importera dessa blad. Inga priser kopieras.
Willys implementation, tester och tidigare releaseunderlag behålls.

Lidls nästa avgränsade steg är samma officiella kommuninventering samt
verifierad butiksgiltighet för aktuella regionala/nationella erbjudanderader
genom befintlig offers-only-väg. Inget Lidl-arbete har påbörjats.
Ingen Windows-/schemaändring, produktionsaktivering, bildanalys eller
betalt modell-API ingår.
