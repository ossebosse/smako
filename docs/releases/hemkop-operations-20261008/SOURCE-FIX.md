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

## Exakta autentiska belägg

Karhögstorg 4123, online_store:

| Endpoint | Verklig JSON-sökväg | Typ/värde | Hämtning UTC | Råhash |
| --- | --- | --- | --- | --- |
| GET /axfood/rest/store | `$[i].hasPickingBaseStore` | boolean false i samtliga 205 butiker | 2026-10-08 12:02:43.283497 | `83ec8f0a41256c00269bdd7711d636e4fc0435933ca68ce40f38d57b99cddce3` |
| GET /axfood/rest/store/active | `$.hasPickingBaseStore` | boolean false, storeId 4123 | 2026-10-08 12:03:13.122752 | `186c1ae7bc050f3bd24ccbc9b99c678f3a6679119cb37e70878b6a3d8907e2f8` |

Tidigare förväntat kontrakt saknade fältet; collector.py `_review_schema_diff`
och snapshot_manager.py:s oberoende promotion stoppade tillägget. Granskad
allowlist finns nu i hemkop/schema_review.py; mängd-/butikssemantik bevakas i
models.py `validated_store_context`, parser.py och client.py:s aktiveringsreadback.
Full reducerad fixture: grocery_data/tests/fixtures/hemkop-picking-store-20261008.json.

Brunnshög 4224, online_store, samma produkt 101293703_ST och samma snapshot:

| Uppgift | Färdigmat, sida 0 | Kött/fågel/chark, sida 0 |
| --- | --- | --- |
| Hämtad UTC | 12:22:01.121507 | 12:26:21.346470 |
| Offentlig kampanj | GENERAL 10010495716, 2 för 89 kr | Samma |
| Medlemskampanj | Saknas | LOYALTY 2500325088, 1 för 39,95 kr |
| Ordinarie produktpris | 55,79 kr | 55,79 kr |
| Offentlig period | null/saknat datum, ingen ny period antagen | Samma |
| Medlemsperiod | Ingen post | slut 2026-10-11 21:59:59 UTC, start saknas |
| Köptak | maxOrderQuantity/promotionRedeemLimit null | Samma |
| Råhash | bcf18bc61c30039b2cca7ff96b86607580ffc292c3fdac61e131aa3c1e0c3793 | 35596ebcaab89f2586a3bb971bc2dfc4c438ef3cb1e6ad99453f27f1eb7848f7 |

Offentligt `price.value=44.5` är källans styckvärde inom tvåköpet; rewardLabel
anger 89 kr. Det ger inget antaget restpris. Fulla produktposter, request-URL,
query och sidreferens finns i hemkop-promotion-conflict-20261008.json. Råfiler
under respektive snapshot finns även via gemensamma `reproduce`-kommandot.
Inget bevis för blandade försök, sammanblandade kampanj-ID:n eller medlemspris.
Detta var faktisk varierande källinformation; exakt extern orsak är okänd.

Aktiveringsbevis och lyckad vanlig replay/nytt sammanhängande försök finns nu
i [RESULTS.md](RESULTS.md), [ACTIVATION.md](ACTIVATION.md) och FINAL.json.
