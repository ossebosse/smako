# Separat Lidl-releaseunderlag

Status: verifierat frivilligt `offers_only`-tillägg för aktuell granskad kampanj. **Inte produktionsaktiverat.** Framtida ogranskade kampanjer blockeras; detta är inte en full Lidl-katalog eller en generell automatisk produktjoin från alla reklamblad.

## Leverans

- `lidl-review-package.tar.gz`: 422 applikations-/datafiler från den bevarade arbetskopian, inklusive de nya Lidl-modulerna och deklarationen. SHA256: `5e4b3db62ebffb70f58c9530821e8ef5030e65551ef498052af4b7b39bc443e5`.
- `release-manifest.json`: individuella filhashar. Arkivet extraherades till `package-code`, alla hashar jämfördes och faktisk begränsad nätinsamling kördes från denna kod. [Kvittens](package-live-verification/verification.json).
- `incremental-existing-files.patch` och `backups/`: skillnaden i de åtta gemensamma filer som ändrats sedan uppdragets start. De ska bedömas mot arbetskopians befintliga ocommittade kedjearbete, inte appliceras blint på ren HEAD.
- Nya Lidl-filer och tester finns i `lidl-incremental-review.tar.gz` med separat manifest; dokument och reproducerbara verifierare ingår där.
- Python 3.12 och `grocery_data/requirements-lidl-candidate.txt`. Den etablerade Smako-miljön behövs; detta är ett granskningspaket, ingen körd produktionsinstallation eller ny schema-konfiguration.

## Avgränsade kodändringar

Lidls nya inventering/produktbindning/källadapter återanvänder befintlig transport, parser, kommungeometri, collector och OWN. Den gemensamma radpubliceringen känner igen Lidls uttryckliga partial-policy. OWN:s befintliga offer-API släpper igenom dess validerade kontrakts-ID. Befintlig gruppcheckout tillämpar samma hushållsgräns för Lidls kontraktsnamnrymd. Den vanliga byggaren/CLI/runnern läser beständigt Lidl-val och godkända referenser, och kvitterar faktiskt publicerad/reloadad artefakt. Leverantörsfakta läggs till i den befintliga faktaladdningen med exakt identitet och separat näringsprövning.

Ingen ny prissättare, prisdatabasarkitektur, refreshmekanism, butikslista, kommunhårdkodning eller produktionsaktivering har lagts till. Varje kommun använder separat beständig källmapp. Datainsamlingen skriver inte användarnas val.

## Verifiering

[Butik/köp](STORES.md), [drift](RUNTIME.md), [tester](VALIDATION.md). Driftproven använder ordinarie lokal Python 3.12-runner, riktig app-process och HTTP-reload. Detta är inte ett påstående om en nybyggd eller installerad produktionscontainer. Befintliga aktiverings-/färskhetskontroller är kvar.

232 körbara regressionstester passerade. 16 fokuserade slutprov och åtta slutliga driftkopplingsprov passerade, med överlapp redovisad. Ett äldre saknat fixtureberoende hindrade ett separat historiskt näringstest från att starta; se VALIDATION.md. Ruff och compileall passerade.

`preserved-chain-results.json`: 60 City Gross-, 51 Willys-, 78 ICA-, 68 Coop/X:-tra- och 18 Primat-relaterade startfiler kontrollerade utan innehållsändring. `preservation-check.json` visar de åtta avsiktligt ändrade gemensamma filerna. Befintliga releaseunderlag är bevarade.

## Verkliga hinder för vidare release

- Ny kampanj/dokumenthash kräver ny säker produktbindning. Utan den får inga nya produkter importeras som nationellt giltiga.
- Saknade produktdeklarationer begränsar recept-/näringsanvändning även för prisgodkända produkter.
- Produktionsaktivering kräver aktuell bas, normala driftskontroller och separat releasebeslut. Lunds äldre Willys-bas har en synlig färskhetsvarning och förfallen relätimer. Den används inte som ny observation.
- Fullständig federerad Malmö-publicering med aktuell komplett bas är fortsatt en separat öppen uppgift. Detta arbete bevisar Lidl-tillägget med befintlig kommunriktig City Gross-bas i en privat OWN-instans.

Willys sju reklambladsbutiker utan onlinekatalog återstår separat. Deras offentliga erbjudanden är inte liktydiga med avsaknad av erbjudanden, och inga priser har kopierats från andra Willys-butiker.
