# Konkreta källstopp – 8 oktober 2026

Diskbristen och Windowsregistreringen är åtgärdade. Befintliga kvalitetskontroller
stoppar två nya Hemköp-underlag. Inga kontroller har kringgåtts.

## Karhögstorg, extern butik 4123

Snapshot `b662192bf600405e9b70476f8d44f667`, hämtning 12:02:42–12:18:10 UTC.
6 304 produkter; 20/20 kategorier, 82 sidor; 87 anrop, inga HTTP-fel,
rate limits eller karantänposter. Effektiv schemadiff:

- `4123:store_context:$[].hasPickingBaseStore` tillagt, boolean.
- `stores:$[][].hasPickingBaseStore` tillagt, boolean.

Rådiffen innehåller även redan stödda variationer i lampors energyDeclaration.
De två fälten ovan återstår efter oförändrad befintlig granskning.
Snapshot är rejected; den har inte manuellt promoverats.

Nästa åtgärd: separat avgränsad granskning av de nya fältens påverkan på
butik/kanal, följd av versionerad typstrikt källrättning om motiverad och
isolerad replay av hela underlaget. Behåll negativprov för andra fält,
fel typer och ändrade kommersiella villkor. Därefter krävs separat konkret
aktiveringsbeslut för eventuell källruntime; dd12-appen ska bevaras.
Spara och återpröva dagens kompletta råunderlag med autentiska observationstider
genom befintlig väg där kontraktet tillåter det; ingen direkt statusändring i DB.

## Brunnshög, extern butik 4224

Snapshot `927a801e126847a184f0515cffc36283`, hämtning 12:18:10–12:26:22 UTC.
`ConnectorFetchError`; 15/20 kategorier färdiga, 45 sidor och en konflikt.
50 anrop, inga rapporterade HTTP-fel eller rate limits. Ofullständigt underlag
får inte promoveras. 45 kvarhållna katalogsidors hashvärden kontrollerade.

Produkt `101293703_ST` (Gyros Kebab Sverige) hade olika `potentialPromotions`
i svar 12:22:01 och 12:26:21 UTC. Det senare innehåller klubbpris 39,95 kr
(`LOYALTY`, kod `2500325088`) utöver det generella 2-för-89-avtalet
(`GENERAL`, kod `10010495716`); det tidigare saknar klubbavtalet. Detta är
fångad källevidens från butik 4224, ingen aktuell prisoffert eller
användarspecifik rabatt. Exakt orsak till källans olika svar är inte belagd.

Nästa åtgärd: bevara konfliktspärren och använd ordinarie behovsstyrt återförsök
för att få ett komplett sammanhängande underlag. Slå inte samman motstridiga
köpvillkor och kalla inte den partiella hämtningen komplett. En schemafix
ensam bevisar inte att denna separata kampanjkonflikt är löst.

Se de två maskinläsbara HEMKOP-*-BLOCKER.json för snapshot, schema,
fullständighetsmått, råreferenser och hashvärden.
