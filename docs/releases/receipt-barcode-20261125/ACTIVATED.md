# Streckkodsskanning i kvittodialogen fungerar (2026-11-25)

Aktiverad 2026-11-25 18:53 UTC. App **app-10a3567c2499-130792a7**
(`sha256:6f3f6fa78931…`), bas `app-868cb9b93f81-bffcde1f`. Scheduler orörd.

Main `ba42a3f`, releasegren `release/receipt-barcode-20261125` (`10a3567`).

## Fel och rättning

Ägarens rapport: streckkodsläsaren efter kvittoskanning fungerade inte.
`mine.js` anropade `.then` på `createBarcodeScanner(...)`, som returnerar
läsaren och inte ett löfte. Varje skanning föll därför direkt med
”...then is not a function”. Nu:

- läsaren startas med `start()`; träff ger streckkoden till raden som förut;
- kan kameran inte starta eller läsa avslutas väntan med ett tydligt besked och
  ett fält för siffrorna under streckkoden (kontrollsiffran valideras);
- knappen ”Avbryt skanningen”; stängd dialog stoppar kameran;
- versionsparametern i `a.html`/`b.html` är `20261125b` så att telefoner hämtar
  nya skript.

## Prov

- Nytt webbläsarprov `test_receipt_barcode_browser.py` (skannad kod skickas med
  raden; skriven kod när kameran inte läser). Båda faller med gamla `mine.js`
  med exakt felet ovan och går igenom med rättningen.
  `test_trial_interfaces_browser.py`: 33 passerade.
- Kandidatbild: rättade filer på plats, `from app.main import app` ok.
- Efter aktivering: `/ready` Lund och Malmö ready med nytt BUILD_ID; beta
  serverar nya `mine.js` och `a.html`; inga fel i apploggen.
