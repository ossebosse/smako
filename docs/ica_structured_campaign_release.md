# Strukturerade ICA-kampanjer och behovsstyrd uppdatering

Två explicita aktiveringsinställningar, båda normalt false:
`ICA_STRUCTURED_OFFERS_ENABLED` och `DEMAND_REFRESH_ENABLED`.
`ICA_STRUCTURED_OFFERS_ROOT` är befintlig OWN-lagring i separata, slutna SQLite-källversioner under grocery-volymen; inte en alternativ prissättare.
`structured-source.json` pekar på godkänd partiell radimport och inventeringsgodkända ICA-konton. Den normala PriceUniverse-byggaren läser denna via befintlig OWN API/provider.
Alla 95-procentsutfall och karantänposter bevaras. Butikskonton hämtas ur inventeringen, inte ur en konfigurerad lista.

`verified-current-campaign-v1` kräver källbunden butik, erbjudande-ID, råreferens, verklig observation och kontrolltid. Saknat startdatum förblir null. Den officiella aktuella erbjudandesidan styrker tillämplighet från observationsdagen i Europe/Stockholm; uttryckliga framtida startdatum går före. Slutdatum krävs för köp. Datumvillkor kontrolleras även i checkout. Kampanjavtal från denna kanal undantas från basprisernas åldersstopp; verifierade datum förlängs aldrig av rebuild eller replay. Publicerade referenspriser skapar inget ordinarie köppris.

Befintlig cron/runner/lås används. En 15-minuters lokal kontroll gör inga externa prisanrop om inget har förfallit. Nästa hämtning sparas per butik: normalt en timme före nästa kända start/slutgräns (slutdagens efterföljande midnatt), sedan 15 minuter efter bytet om samma period fortfarande publiceras. Reservkontroll högst 72 timmar för lång kampanj, 12 timmar för tomt/obundet/utgånget flöde. Nätfel återförsöks efter 15 minuter och exponentiellt upp till 6 timmar. Nya butiker upptäcks vid insamling och senast vid inventeringsförfall efter 72 timmar. Lokal datumväxling är separat från nätinsamling.

Baskällor förfaller vid 35 timmar, med varning 36 och köpstopp 48 timmar oförändrade. Kampanjarbete kan tidigarelägga en basuppdatering när basen är minst 24 timmar gammal. Samma kedja/Primat hämtas bara en gång per körning. Källpromotion utan publicering upptäcks genom snapshot-identiteter. Schemastatus/omstarter använder `DEMAND_REFRESH_STATE_PATH`. Willys lokala relay kan använda samma 35-timmarsprincip via filen `demand-refresh-enabled` i sin befintliga arbetskatalog; dess Windows-trigger måste då vara en lätt periodisk kontroll.

Frivilligt ICA-fel stoppar inte en giltig bas. Tidigare kvalificerade kampanjer kan behållas endast inom verifierad giltighet. Tomt eller gemensamt underkänt underlag tar bort berört tillägg. Felaktig butik, flera obestyrkta varianter, obelagd pant, okänt personligt villkor och okänt fast förpackningskontrakt ligger kvar utanför köp.

Ingen bildmodell anropas av denna väg; `collect_flyers=false`, `discover_flyers=false`, kandidatjobbet av och bildkommandot null. Primat och ICA-baspriskatalogens paus ändras inte.

Körning: `python deploy/scripts/run_daily_refresh.py` i befintlig scheduler och dess miljö. Rollback får bara återaktivera kodkompatibel, fortfarande giltig bas. Den tidigare manifestpekaren avvisas vid >=48 timmars basålder. Releasens faktiska driftutfall finns i reports/ica-structured-release-20260920.
