# Coops fysiska erbjudanden: uttryckligt partiellt kontrakt

Implementerat i `CoopRowApprovedOfferConnector` och befintlig `qualify_rows`,
policy `coop-physical-structured-v1`. Detta är ett frivilligt offers_only-tillskott.
Ingen produktion har aktiverats. Coop Online 730400 är en separat priskanal.

## Källa och identitet

Den befintliga Playwright-transporten läser butikens officiella sida och tar
tillvara dess publika DKE-svar från exakt butikens ledger-konto. Inga autentiserings-
headers, cookies eller sessionsidentiteter sparas. Inget direkt återanrop med
kopierade credentials och ingen ny transport. Officiell sididentitet, butikens
externa ID, ledger-konto, URL, hämtningstid och innehållshash måste stämma.

`alla.offerAmount`, gruppantal, DOM-kort och dubblerade kategorier kontrolleras.
Procentannonser räknas i strukturerad nämnare även när DOM:s penningprisselektor
inte hittar dem. Okänt schema, fel butik eller motstridiga kategorikopior stoppar
hela kandidaten. Nya okända annonsfält får inte tyst tappas.

Produktidentiteten är ett källbundet offer-ID + opakt variant-ID. `externalId`
blir **inte** GTIN. Verifierade barnvarianter ersätter gruppföräldern i importen;
allmänna priser kopieras inte till andra varianter eller butiker. Källa och
gruppavtal följer vidare i OWN och PriceUniverse. Gruppavtalet binder köpgränsen
över produktalias och varianter i samma fysiska butik.

## Prisroller och villkor

Annonserat köppris sparas i SourceOffer, aldrig automatiskt som ordinarie pris.
Även källans `Regular Price` är endast belagt inom annonsens datum. Ett tryckt
referenspris, jämförpris eller procenttal blir inte ett ordinarie restpris.
Ordinarie pris förblir null utan verifierad aktuell tillämplighet.

Källans exakta variantförpackning, enhet, publikt/medlemspris, kampanjdatum,
variantundantag, panttext och maxköp bevaras. Gemensamma föräldravillkor följer
med; motsägelser granskas. Datum tolkas i Europe/Stockholm. Inga gissade starter,
veckodatum eller paketvikter. Dags-/tidsvillkor som inte kan prissättas exakt
stoppar berörda rader. Framtida och utgångna priser får inte användas nu.

Grupper prissätts endast där befintlig checkout stöder hela erbjudandegruppen.
Restmängd utan belagt ordinarie pris och blandning mellan varianter utan ett
stödd kontrakt avvisas. Okänd pant, procent utan prisgrund, osäker förpackning,
personliga/aktiveringskrävande villkor och oförstådda källmarkeringar ligger kvar
i granskningsunderlaget. Den observerade `isPil`-flaggan bevaras men dess annonser
är tills vidare köpblockerade; flaggans innebörd har inte antagits.

## Kvalitet, ålder och drift

Alla lästa varianter finns kvar i full nämnare. Fullsnapshotens 95%-gräns ändras
inte. Varje isolerad rad måste klara alla tillämpliga kontroller. De godkända
raderna kan publiceras som en **partial-row-approved-offers-v1**-kandidat medan
fullsnapshot fortfarande visar `broken` och samtliga karantänorsaker.

Inget nytt schema eller produktionsberoende införs. Isoleringskommandot använder
befintlig collector, databas, lås och provider. Output måste vara en ny katalog.
Kandidatens observation är alltid råkällans verkliga hämtningstid; replay eller
ombyggnad föryngrar den inte. Basernas och Coops befintliga 36/48h-policy är
oförändrad; ICA:s separata kampanjpolicy har inte breddats här.

Korrekt pris, kvalificerat köp, ingrediensmatchning, näringsunderlag och vald
meny är olika steg. En importerad variant är inte automatiskt en näringsgodkänd
receptprodukt. Utöka inte fysisk kommuntäckning från denna butikstestning.

## Reproduktion

Se `reports/coop-physical-fix-20260921/README.md` för verklig begränsad insamling,
isolerad import och tester. Python 3.12 och redan befintlig Playwright/Chromium
användes på Windows. Inga nya bibliotek, bildmodeller eller betalda anrop.
