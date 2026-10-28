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

Windowsuppgiften använder fortfarande det tidigare paketet och dagliga
starttider. Byte till nytt paket och veckoschema kräver fortfarande
administratör. Denna granskning får inte påstå att registreringen är klar.

Skyddat operatörsunderlag finns i `.local/ops-dashboard-20261028/`.
Inga hemligheter, cookies, användarprofiler eller full miljökonfiguration ingår.
