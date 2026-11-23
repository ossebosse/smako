# Prisinsamling två nätter per vecka

Ägarbeslut 2026-10-28: alla aktiverade bas- och kampanjkällor hämtas natten
mot måndag och natten mot torsdag, med start **03:17 Europe/Stockholm**.
Sommar-/vintertid följer svensk civil tid. `PRICE_COLLECTION_CADENCE=mon_thu`
väljer denna policy; `legacy` bevarar äldre drift vid separata installationer.

Den befintliga behovsstyrda arbetaren kör fortfarande lokala kontroller varje
kvart (`DEMAND_REFRESH_CRON=2,17,32,47 * * * *`). Källhämtningar och befintliga
begränsade felåterförsök får starta 03:17–06:17 dessa två morgnar. En lyckad
källobservation sedan nattens start gör källan färdig för den natten. Senare
körningar gäller lokal publicering, laddningskvitton, kampanjutgång och backup,
inte nya prishämtningar. Ett jobb som redan har startat får avslutas normalt.
Om en källa inte kan hämtas under fönstret behålls kvalificerad LKG; nästa
ordinarie hämtningsfönster visas utan att gamla källtider förnyas.

Samma policy används för ICA, Hemköp, Coop/X:-tra, City Gross, Lidl och Willys
reklamblad i aktiverade kommuner. Schemalagda Willys-kataloger kommer via
befintligt Windowsrelä med en veckotrigger måndag/torsdag 03:17, utan tidigare
åttatimmarsrepetition. `set_price_collection_schedule.ps1` visar ändringen före
`-Apply`, sparar föregående uppgift och bevarar konto, transport och inställningar.
Åtgärden binds till den verifierade reläversionen med `-CollectionCadence mon_thu`.
Windows befintliga återhämtning efter missad start bevaras, men reläets egen
policy väntar till nästa insamlingsnatt om en sådan start sker under dagen.
En observation före torsdagens start får inte skjuta upp torsdagshämtningen.
Reläet och servern
använder fortfarande sina befintliga arbetslås och publiceringskvitton.

`ICA_PRIMAT_BASE_ENABLED=true` låter det befintliga Primat-flödet planera en
redan verifierad baskontext även innan den ingår i det aktiva prisunderlaget.
Endast kommuner med exakt verifierade, fullständiga Primat-kontexter lämnar
OWN-only för det avgränsade bygget. Samma identiteter återkontrolleras mot
aktuell butiksupplösning innan produkter godkänns. Det befintliga kontraktet
är 149 anrop per kommun: en butiksupplösning, de 48 ingredienssökningarna
(100 rader var) och 100 sökningar på receptbibliotekets vanligaste övriga
ingredienser (50 rader var, ägarbeslut 2026-11-22), inte en ny fullständig
produktkatalog. Sökningarna går med 1,1 s mellanrum (Primats gratisnivå: 60
anrop/min, 200 rader/anrop, 20 000 rader/dygn). Butiker med enbart erbjudandekontext räknas inte
som baspriskällor. Inga nya butikskopplingar eller källfakta fabriceras.

Hela ICA-katalogen (ägarbeslut 2026-11-23): med `PRIMAT_ICA_CATALOG_ENABLED=true`
kör schedulern `deploy/scripts/run_primat_ica_catalog.py` dagligen kl. 07:37
(`PRIMAT_ICA_CATALOG_CRON`), efter nattens insamling. Jobbet läser kvoten
(`/me`) och butikerna (`/stores`, räknas inte mot kvoten) och tar alla
ICA-butiker med `tier=full` i Smakos kommuner. Därefter: dagens erbjudanden
(`/prices?offers=1`), förpackningsstorlek en gång per matvara (`/batch`) och
nästa del av hela katalogen (`/prices` med sparad markör), inom
`min(PRIMAT_ICA_CATALOG_MAX_ROWS, kvar idag − PRIMAT_ICA_CATALOG_RESERVE_ROWS)`.
En hel runda tar ungefär en vecka; när den är klar tas varor bort som butiken
inte längre har. Raderna sparas med hämtningstid i
`<PRICE_UNIVERSE_CACHE_ROOT>/primat-ica-catalog/catalog.sqlite`; status i
`reports/operations/primat-ica-catalog.json`. Jobbet rör inte grocery-databasen,
prisunderlagen eller planeraren.

Med `PRIMAT_ICA_CATALOG_SOURCE=true` hämtar nattens Primat-steg ICA-varorna ur
den sparade katalogen i stället för de 148 sökningarna, när en hel runda är
klar och varje butik har minst `PRIMAT_ICA_CATALOG_MIN_PRODUCTS` (1 000)
matvaror med förpackning. Då görs bara butiksupplösningen (1 anrop). Varje vara
behåller sin egen hämtningstid och får vara högst prisåldersgränsen gammal;
erbjudanden som senaste dagliga erbjudandepasset inte längre visade tas bort.

Prisåldersgräns (ägarbeslut 2026-11-23): en inställning för alla kedjor,
`MAX_PRICE_AGE_HOURS` (kodens standard 48 h; produktion 336 h = 14 dygn), och
`PRICE_AGE_WARNING_HOURS` för när ett pris räknas som åldrande. Kampanjers
giltighetsdatum påverkas inte.

Primats verifierade register läses med SQLite `mode=ro` och `query_only`.
En levande databas får ha sparade ändringar i WAL; `immutable=1` används
inte här eftersom det kan dölja både nya kopplingar och återkallade godkännanden.

Kvalificerade baspriser behålls tills en validerad ersättning finns. Varningar
vid 36/48 timmar består, även när åldern är väntad mellan körningarna. Kampanjer
gäller enbart inom sina verkliga källdatum; en lokal datumövergång får byggas
och publiceras mellan insamlingsnätterna. Backup fortsätter dagligen. Separat
dagligt Coop-återförsök stängs av i denna konfiguration.

Se [aktuell serveraktivering och kvarvarande Windowsregistrering](releases/beta-ica-recipes-20261028/ACTIVATED.md).
Versionshanterade standarder ändrar inte i sig en installerad beta eller Windowsuppgift.
