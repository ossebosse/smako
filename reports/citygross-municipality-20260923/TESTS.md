# Tester och bevarande

Python 3.12. Sparade JUnit-resultat visar **255 olika tester godkända med
ordinarie testklocka**, plus **ett oförändrat historiskt Willys-test godkänt
med explicit fixture-klocka 19 september**. Räknaren deduplicerar överlappande
testkörningar; den är inte summan av varje omkörning.
[Maskinell sammanställning](tests-summary.json) listar samtliga sex XML-filer.

- 168 regressioner: befintlig City Gross-connector/full/partial,
  kommuninventering, source-job, kampanjsemantik, Coop-jobb/runner,
  Willys kommun/provider, OWN-kontrakt, deployment och behovsplan.
- 68 root-tester: managed-refresh, source-job, uttrycklig OWN-only/default
  federerad grind, legacy-handoff och befintlig OWN-provider.
- 22 fokuserade tester: City Gross-acceptans, full/partial-LKG,
  köptaksdominans och befintlig PriceUniverse.
- Slutlig omkörning av fyra rättade acceptans-/testfixturefall samt sju
  kommunprovidertester efter sökdelegationen: alla godkända.
- Därutöver körde deluppgifterna separata semantik-/köpgräns- och kommunsviter.
  Deras överlappande terminalresultat adderas inte till JUnit-räknaren.

Första felande försök ligger kvar. City Gross-acceptanstestets två föråldrade
GeographicArea-förväntningar fick redan införda `mode`/`municipality_code`.
En ny tests minimala Product-fixture saknade obligatorisk kategori och rättades.
Det historiska Willys-medlemstestet använder utgångna kampanjer men jämför
mot dagens datum. Det misslyckas fortfarande med dagens klocka, och är därför
inte inräknat i 255; [separat replay](verify_historical_member_fixture.py)
visar avsedd funktion på dess eget datum. Varken testfilen, källobservationer
eller runtimeklockan ändras av detta prov.

Ruff är godkänd för samtliga 28 Python-filer i inkrementet
([logg](ruff-final.log)); compileall är godkänd för samma filer
([filförteckning](compileall.json)). Dynamiska fullkatalogbyggen, faktisk
lokal publicering/reload och köpverifiering dokumenteras separat från dessa
fixturetester.

## Bevarande och paket

[Release-manifestet](release-manifest.json) beskriver 31 nya/ändrade
käll-/test-/dokumentfiler med före-/efterhash. **19 Willys-filer** – connector,
parser, transport, kommunstöd, relay, källartefakt, tester och tidigare
releaseunderlag – är bitidentiska med startläget. Inga Primat-, ICA-,
Coop-/X:-tra-connectorer, Lidl-connectorer, Windows-/schemafiler eller
skarp konfiguration ingår i inkrementet. Delad OWN-/bygg-/kvittokod ändras
inom den redovisade integrationen och omfattas av regressionerna.

[changes.patch](changes.patch) är ett läsbart inkrement mot den sparade
arbetskopian med radslutsbrus borttaget. [Källpaketet](citygross-source-increment.zip)
innehåller exakta slutfilbytes; inga testdatabaser, simulerade refresh-statusar
eller skarpa konfigurationer ingår. Kontrollera basens hash vid ett senare
införande; detta är inte en patch mot ren Git-HEAD och inte en aktivering.
