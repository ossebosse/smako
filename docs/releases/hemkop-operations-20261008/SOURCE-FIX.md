# Avgränsad Hemköp-källrättning

Bas: oförändrade sju källfiler i 08c137475d9c och 0d4c1d7.
Ingen konsumentapp eller måltidskod ingår i källpatchen.

Samma fältnamn hasPickingBaseStore finns i GET /axfood/rest/store
(`stores:$[][].hasPickingBaseStore`, verklig payload `$[i].hasPickingBaseStore`)
och GET /axfood/rest/store/active
(`4123:store_context:$[].hasPickingBaseStore`, verklig payload `$.hasPickingBaseStore`).
De extra listnivåerna är fingerprintets aggregat över rådokument.
Full råhash/tid och reducerade oförändrade fält finns i testfixturen.
Alla 205 katalogbutiker och aktiv butik 4123 hade boolean false.
Tidigare kontrakt saknade fältet; _review_schema_diff → assess_run_health
stoppade tillägget. Inga priser eller butiksmappningar härleds från flaggan.

Semantik: namnet kan signalera koppling till annan plockbas. Ingen sådan
mappning är belagd. Därför tillåts endast explicit false för ny data; true,
null, tal och sträng stoppar berörd bindning. Saknat fält behåller äldre
kontrakt utan att skrivas om till false. Befintlig exakt butiksaktivering,
readback och sidornas butiksfacet kvarstår. Godtycklig rekursiv storeId-sökning
ersätts av kända direkta/store/pickingStore-former; motstridiga former stoppas.
Parserversion hemkop-parser-v1.1-picking-contract. Schemaanpassningen kräver
boolean i den faktiskt beräknade fingerprinten vid insamling/replay/slutpromotion.
Andra tillägg, borttagning och typändring behåller spärren.

Brunnshögs råposter tillhör samma snapshot och butik men olika kategorisidor.
Produkt 101293703_ST har GENERAL 10010495716 i båda och LOYALTY 2500325088
endast i den senare. Offentlig flerköps- och medlemskampanj har redan skilda
identiteter; ingen sammanblandning belagd. Konfliktkontrollen ändras inte.
Ett begränsat nytt ordinarie försök behövs; ingen atomisk källgaranti påstås.

Lokala prov: 127 riktade regressioner PASS, Ruff och compileall PASS.
Första tio nya kontraktprov fallerade före implementation; rå schemaändring
fortsatt blockerad av äldre parserversion även efter patchen.
En första integration hittade äldre store-wrapper; den bevarades uttryckligt
före slutprovet. Misslyckade försök finns kvar i privat evidens.
Full ordinarie isolerad replay: 6304 produkter, 0 karantän, healthy/promoted,
0 nätanrop. Ofullständigt Brunnshög-underlag fortsatt blockerat.
Stora rådata och testdatabas finns på D: under .local/hemkop-operations-20261008.
Produktfixturen visar två legitima skilda erbjudanden samt verklig frånvarokonflikt.

Aktiveringsbevis tillkommer separat efter paketering och förkontroller.
