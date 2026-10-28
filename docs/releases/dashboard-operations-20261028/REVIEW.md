# Dashboard och driftkontroll 2026-10-28

Ägaren frågade varför de nya ICA-baspriserna inte framgår och bad om
driftkontroll av Coop och Willys. Alla observationer nedan är skilda från
en ny prisinsamling eller ett påstående om aktivering av denna rättning.

## Bekräftat läge före rättning

Det autentiserade befintliga admin-API:t lästes utan att lämna ut dess
behörighetsuppgifter. Aktiv app är `app-f596e1102fd7-09770600`, scheduler
`beta-scheduler-2b65533af00d-contracts1`. Båda kommunernas prisversioner är
laddade. API:t har redan `available_base_prices` men JavaScript visar inte
fältet. Faktiska ICA-basposter: Gunnesbo 1 926, Clemenstorget 38, Caroli
1 213 och Västra Hamnen 1 432. Clemenstorgets priser är äldre kvalificerad
LKG, inte en ny fullständig Primat-hämtning.

Dashboardens text anger fortfarande spärr efter 48 timmar och enbart ICA-
undantag för kampanjer. Detta motsäger den aktiva prispolicyn: kvalificerade
baspriser behålls tills ersatta och kampanjer följer sina verkliga datum.
Sparade gamla återförsökstider visas utan den nya tvånattspolicyn. Den
gemensamma statusens schemaformat med `Mon,Thu` ger dessutom ingen nästa
tid, eftersom läsaren enbart accepterar det tidigare dagliga formatet.

## Avgränsad rättning

- Visa befintligt antal baspriser per underlag och rätt prispolicy.
- Behåll ålders- och insamlingsvarningar, men beskriv inte äldre baspriser
  som oanvändbara på grund av åldern.
- Projektera nästa erbjudandehämtning genom samma befintliga körpolicy
  som sourcejobbet. Ingen journal eller observationstid skrivs om.
- Läs måndag/torsdag i nästa schematid, med svensk sommar-/vintertid.
- Läs också Willys reklamblads befintliga kommunala körjournal, med exakt
  butik/kommun. Dess giltiga priser visades redan, men senaste insamling
  visades som okänd eftersom endast ICA/Coop ingick i journalläsaren.

De tre tidigare driftspecifika dashboardmodulerna registrerades först som
oförändrad källbas från aktiv image (`b4acc7f`). Detta ger exakt granskbar
filbas för patchverktyget; det är inte en installation av nya adminrättigheter.
Autentisering, användardata, priskvalificering och insamling ändras inte.

## Coop och Willys

Tio fysiska Coop-underlag (fyra Lund, sex Malmö) har vardera 14 efterföljande
avvisade försök. Senaste försöken 28 oktober stoppas före kvalificering av
det nytillkomna fältet `row.environmentalCode` i offentliga butikssvaret.
Tidigare godkända, fortfarande giltiga kampanjer finns kvar. Malmö Central,
Kornettsgatan, Djupadal och X:-tra Nydala saknar dessutom godkänd källa och
har separata återkommande fel; de får inte beskrivas som uppdaterade.
Malmö Central, Kornettsgatan och Djupadal har verifierade timeoutkedjor i
`public_offer_fetch`, vid väntan på erbjudandekorten på butikssidan. X:-tra
Nydalas aktuella fel ska fortfarande hållas separat från dessa tre.

Coop Online Syd `730400` är en separat online-/leveranskontext. Den använder
17 oktobers kvalificerade baspriser. Det senaste kompletta avvisade försöket
19 oktober har schemaförändring i kampanjernas maxantal. Reproduktion
verifierade 821 originalfiler och 42 722 655 byte utan nätanrop. Dessa gamla
data ska inte omdateras eller promoveras genom en försvagad grind.

Lund-Willys senaste kvitterade källa är från 27 oktober, med cirka 37 timmars
ålder vid granskning. Malmö-Willys fyra kataloger observerades 28 oktober
16:33–17:36 UTC och är redan publicerade och laddade. Windows saknar dock
slutkvitto efter ett tidigare transportfel. Ett avgränsat återupptagande
använder befintligt verifierat paket och normala import-/kvittensvägen;
ny källinsamling är uttryckligen spärrad i den körningen.
Återupptagandet avslutades **21:35:49 UTC** med `already_active` för exakt
`bbba3548e426de8f7a191f3abe3d92c8597bd233ea69ab554d6306271ce378da`.
Det beständiga kvittot motsvarar nu samma laddade Malmöversion; efterföljande
driftkontroll visar `pending_delivery=false`. Ingen ny prisinsamling startades.

Alla sju fysiska Willys-reklambladskontexter har lyckade befintliga
kommunjournaler från 27 oktober. Den granskade journalläsaren hittade exakt
deras källidentiteter och projekterade nästa hämtning till 29 oktober
03:17 svensk tid. Dessa saknade visad historik, inte tillgängliga kampanjer.

## Verifiering av rättningen

PR42 kod `fac3a7e021a06038c76c2a281bc8c7623f026a34` är integrerad som
`c965426254bfab0e3ac1058216215534a588de7f`.
[Alla CI-delar passerade](https://github.com/ossebosse/smako/actions/runs/40773482626).
Riktade offlineprov, Ruff och compileall passerade. Schemafallen omfattar
sommar-/vintertid, exakt startgräns och nästa måndag efter torsdag.
Journalläsarens prov bevarar gamla källtider, felräknare och filinnehåll för
ICA, Coop och Willys. Browserprovet visar alla fyra ICA-basantal från fångat
admin-API. Ingen ny publik meny används som prestandabevis för denna rättning.

Exakt slutkandidat `app-fac3a7e021a0-9fcadbe1` passerade normal lifespan-
uppstart och automatisk förberedelse för båda kommunerna: 189,66 s,
minnestopp 2 474 385 408 byte, 2 CPU/3 GiB och inget nätverk. Alla 2 462
varianter för portioner 1–4 förbereddes med noll persistensfel och inga
syntetiska sparade planer/profiler. Metodsignaturen är
`c3a22c355cab23ac192976cbdfa4545f81e9c270bd54e9d040893cc051f6ad58`.
Detta skiljs från den faktiska aktiveringen och kontrollen av den publika appen.

Windowsuppgiften använder fortfarande det tidigare paketet och dagliga
starttider. Byte till nytt paket och veckoschema kräver fortfarande
administratör. Denna granskning får inte påstå att registreringen är klar.

Skyddat operatörsunderlag finns i `.local/ops-dashboard-20261028/`.
Inga hemligheter, cookies, användarprofiler eller full miljökonfiguration ingår.
