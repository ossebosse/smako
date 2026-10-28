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
`-Apply`, sparar föregående uppgift och bevarar konto, åtgärd och inställningar.
Windows befintliga återhämtning efter missad start bevaras. Reläet och servern
använder fortfarande sina befintliga arbetslås och publiceringskvitton.

`ICA_PRIMAT_BASE_ENABLED=true` låter det befintliga Primat-flödet planera en
redan verifierad baskontext även innan den ingår i det aktiva prisunderlaget.
Endast kommuner med exakt verifierade, fullständiga Primat-kontexter lämnar
OWN-only för det avgränsade bygget. Samma identiteter återkontrolleras mot
aktuell butiksupplösning innan produkter godkänns. Det befintliga kontraktet
är 49 anrop per kommun: en butiksupplösning och 48 ingredienssökningar, inte en
ny fullständig produktkatalog. Butiker med enbart erbjudandekontext räknas inte
som baspriskällor. Inga nya butikskopplingar eller källfakta fabriceras.

Kvalificerade baspriser behålls tills en validerad ersättning finns. Varningar
vid 36/48 timmar består, även när åldern är väntad mellan körningarna. Kampanjer
gäller enbart inom sina verkliga källdatum; en lokal datumövergång får byggas
och publiceras mellan insamlingsnätterna. Backup fortsätter dagligen. Separat
dagligt Coop-återförsök stängs av i denna konfiguration.

Se aktuell aktiveringsjournal i `docs/releases/ica-twice-weekly-20261028/`.
Versionshanterade standarder ändrar inte i sig en installerad beta.
