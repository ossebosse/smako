# Statusflöde och återanslutning – lokal appkandidat

**REDO FÖR SEPARAT APP-AKTIVERINGSBESLUT.** Betan är oförändrad. Ingen produktionsaktivering, push, prisinsamling, proxy-/säkerhetsändring, relä- eller schemaändring har utförts.

Gren `feature/status-reconnect-20261006`, runtime **dd12cc80e98c79aa32c159223c8bc1ceeaaa7580**. Utgångspunkt f5deaef ovanpå 82de; senare relevanta ändringar bevarades. Serverpaket `smako-server-dd12cc80e98c.zip` (2 839 700 byte), SHA-256 **bc1ec3f2b03c228348bb63bcf3bba0f84f300b56aa375cdbe877f0dc8838484c**. Verifierad image **sha256:c8362751b13a6e649beadad2a3c27b9b5df8bfd1e2fa177ff68e01e1d7b8b2c7**. Efterföljande commits för testverktyg/dokumentation ändrar inte den paketerade runtimekoden.

## Beslutsmatris

| Område | Utfall och begränsning |
| --- | --- |
| 1. WebKit-händelsen | Exakt historisk orsak är fortsatt obelagd. Ett nytt strikt FAIL visade ett pollanrop före pagehide under navigation. beforeunload stoppar nu timern tidigare; regressionen fallerar före/passerar efter, och slutimagen klarar omladdning, fördröjt statusanrop och återkomst utan oväntade sidfel. Råa misslyckanden bevaras. |
| 2. Samtidighetens anslutningsfel | Historiskt socket hang up har ingen belagd exakt orsak och kopplas inte till WebKit. Ett separat senare test-API-GET bröts efter visat resultat; tillgänglig serverlogg förklarar inte det. Nya ostörda och kontrollerat avbrutna treägarkörningar passerade. Ingen testklientomkörning kallas appfix. |
| 3. Återanslutning | 11 riktiga paketerade webbresor, två treägarkörningar och negativa session-/omstartsprov passerade. Samma ägare/jobb/begäran återfinns; en POST och exakt en instrumenterad huvudberäkning per återhämtningsprov. Begränsade återförsök och manuell återupptagning skapar ingen ny meny. |
| 4. Resultat och revisioner | Fullt mat-/köpinnehåll matchar 82de även efter byte och omräkning. Historiska totaler kvarstår: 741,15 / 787,56 / 910,39 kr. 11 äldre HTTP-revisioner, 22 revisioner i lagringskopian och nya fullresors revisioner läses oförändrat. Flagga-av och äldre menyflöde passerar på samma image. |
| 5. Prestanda/resurser | Enskilt ostört huvudklick 67,81 s; under 60 s återstår. Kö, beräkning, klienttid och minne redovisas separat. Två CPU, 3 GiB och en tung plats behölls. Ingen kausalt isolerad merkostnad för statuskod påstås. |
| 6. Leverans och prov | Identifierad runtime, nytt hashverifierat paket/image, laddad JavaScript-hash, 10 transport-, 41 backend- och 8 syntetiska frontendprov; strikta riktiga Chromium/WebKit-resor. Se [TESTS.md](TESTS.md) och [PACKAGE.json](PACKAGE.json). |
| 7. Aktiveringsbeslut | App-only-kandidaten är förberedd enligt [ACTIVATION.md](ACTIVATION.md). Ofärdiga processminnesjobb överlever inte backendomstart. Signerad kontosessionsexpiry, fysisk iPhone och äldre binäråtergång är inte kvalificerade här. Historiska intermittenta orsaker är fortsatt osäkra. |

## Vad ändrades?

Publikt/personligt flöde använder samma sekventiella statusläsare med generation, egna avbrott och sena svar spärrade även efter JSON-konsumtion. Timers/fetch stoppas vid ersatt läsare, beforeunload och pagehide. Återkomst läser tillgängligt sessionstillstånd; lösningen kräver inte att en viss avslutshändelse alltid har körts. Transportfel ger återanslutningsläge, tidsgräns/backoff och därefter separat manuell statusåterupptagning. Ett förlorat accepterat startsvar återfinns genom ägarbunden GET med samma begäransreferens. HTTP-, schema-, autentiserings- och riktiga jobbfel bevaras. Serverjobb avbryts inte för att sidan lämnas. [TRANSPORT.md](TRANSPORT.md) beskriver budget, diagnostik och processminnesretention.

Recept, fakta, pris-/kampanjkontrakt, sökbudget, näring och oberoende audit har inte ändrats. Beloppen är **berikad historisk replay med priser från 4 oktober**, inte dagens prisoffert eller en ny besparing. Kompletta menyer/inköpsrader finns i de oförändrade [tidigare leveransmenyerna](../package-variation-20261005/MENU.md); fulla nya råresultat och hashbundna jämförelser finns i [COMPATIBILITY.json](COMPATIBILITY.json).

## Bevis

[Webbläsare](BROWSER-EVIDENCE.json) · [Samtidighet](CONCURRENCY.json) · [Negativa prov](RECOVERY.json) · [Bevarade fel](HISTORY.json) · [Kompatibilitet](COMPATIBILITY.json). Rårapporter, skärmbilder, testloggar och isolerade serverloggar är bevarade under `.local/status-reconnect-20261006/` och den ägarmärkta teststagen. Ingen cookie, token eller privat produktionsplan finns i den committade evidensen.
