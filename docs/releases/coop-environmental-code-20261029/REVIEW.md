# Coop environmentalCode, 29 oktober 2026

Begäran: rätta Coops insamlingsfält och återställ den blockerade insamlingen.

Färska ordinarie offentliga butikssvar från Värpinge Lund (3659/216526,
05:30:51 UTC) och Bulltofta Malmö (3815/106410, 05:30:55 UTC) avvisas av
`coop-parser-v6` med `row.environmentalCode`. Båda visar strängen `A` på
erbjudandet Ekologiska ägg 6-pack, 24,90 kr. Reducerade autentiska affärsfält
finns i `grocery_data/tests/fixtures/coop-environmental-code-20261029.json`.
Inga förfrågningshuvuden, cookies eller sessionsuppgifter har lästs/sparats.

`coop-parser-v7` accepterar och bevarar just den observerade strängen som
opak källmetadata, även i barnposter. Koden härleder inga ekologiska fakta,
produktidentiteter, priser eller köpvillkor från den. Andra värden, typer och
nya okända fält kräver fortfarande källgranskning. Pris-, kampanj-, kommun-,
butiks- och radkvalificering är oförändrade.

Avsedd release ändrar endast `grocery_data/app/connectors/coop/parser.py`
och `structured_offers.py` ovanpå de faktiska aktiva app- och schedulerbilderna.
Runtimekonfiguration, recept, konton, scheman och övriga filer bevaras.
Lagringsretention, befintligt driftlås, verifierad backup, kandidatkontroll och
normal kvalificering/publicering gäller som tidigare. Inget aktivt jobb avbryts.

De tio berörda fysiska butikerna är Värpinge, Veberöd, Klostergården,
Mårtenstorget, Värnhem, Norra Parkgatan, Kirseberg, Bulltofta, Oxie och Limhamn.
Separata hämtningsfel för Malmö Central, Kornettsgatan, Djupadal och X:-tra
Nydala samt Coop Online Syds katalogkontrakt omfattas inte av detta fältstöd.
Deras tidigare underlag och felhistorik ska bevaras. Coop Online Syd är fortsatt
en onlinekontext, inte baspriser för fysiska Coop-butiker.

Aktivering och färska butiksresultat dokumenteras först när de är verifierade.

Lokal verifiering: 101 test godkända (52,93 s): miljöfält, schemaövergång,
fysisk strukturerad insamling, connector, offer acceptance, kommunjobb,
kommunkontrakt, routning och browserintegritet. Ruff, compileall och
`git diff --check` godkända. Negativa prov täcker okända värden/typer och
nya villkor; fulla historiska Lund-/Malmöunderlag ger identiska prisbeslut.
