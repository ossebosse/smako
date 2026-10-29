# Online Syd kopplad till Stora Coop och verifierad i betan

Ägarbeslut 29 oktober: Coop Online Syds ordinarie baspriser används för
Stora Coop Lund, Coop Forum/Stora Coop Jägersro och Stora Coop Stadion.
De fysiska köpkontexterna och butikernas egna kampanjer består. Butiksvalen
visar `Baspris från Coop Online Syd`. Mindre Coop och X:-tra omfattas inte.

| Butik | Officiellt ID | Baspriser | Egna kampanjposter |
| --- | --- | ---: | ---: |
| Stora Coop Lund | 2696 | 11237 | 454 |
| Coop Forum Jägersro | 3850 | 11237 | 454 |
| Stora Coop Stadion | 3853 | 11237 | 454 |

Dashboard, butiksval och publik scoped readiness är verifierade. Verklig
varusökning ger Coop Mellanmjölk 1,5 liter, GTIN 7300156578167, för 15,50 kr
hos samtliga tre. Inga privata profiler eller sparade planer skapades för provet.

## Aktiv kod och bevarande

App och scheduler använder `source-ops-8a53beb80e43`, kod `8a53beb80e437633e9fd945dcde3e1ca84bd529d`.
Appimage: `sha256:c81c507598a418dc5378492ec678cf9f32c1e2cde21e168e2b2634ffefb6fbd4`.
Schedulerimage: `sha256:35b377c863c183c93167df2d1ab1766319cd11efbfc5252d2d247f3d93e38c23`.

PR [47](https://github.com/ossebosse/smako/pull/47),
[48](https://github.com/ossebosse/smako/pull/48) och
[49](https://github.com/ossebosse/smako/pull/49) är integrerade i main.
Slutlig kodmerge `178a323adbd4e20d175cdc96d9adc284475024b2` har grön PR- och main-CI.
68 riktade fakta-/provider-/paketeringstester och samtliga 51 runtimeprov
passerade, liksom Ruff och compileall. Tidigare policyprov/regressioner
är dokumenterade i [kodgranskningen](../../reviews/stora-coop-syd-base-20261029.md).

Slutsteget ändrade en appfil (exakt faktabindning) och två schedulerfiler
(befintlig byggversionsparameter och dess anrop). Övriga körfiler hashjämfördes
mot respektive faktiskt aktiv bas: app 2600390d3943 och scheduler 9172815e60f9.
Tidigare fyra schedulerfiler i 9172815 tillförde själva butikskopplingen ovanpå
47b1f0fdb717. Äldre separata runtimeanpassningar bevarades; hela main kopierades
inte över bilderna. Receptbiblioteket, personliga krav, mängdregler och checkout
består. Faktaläsarens versionsbyte ger normal invalidering av förberett underlag.

Aktiverad 2026-10-29T21:24:52.509976+00:00, med fullständigt verifierad backup `/srv/smako/backups/20261029T211156Z`.
Tidigare plan-/profil-/konto-/sessionsrader, mountar och prismanifest kontrollerades
före/efter. Scheduler, app och proxy kontrollerades mot de förväntade bilderna.
315 planrevisioner, 124 privata tillstånd, två konton och en session bevarades.
Befintligt gemensamt driftlås användes; ordinarie prisjobb fick slutföras.
Lagringsretention är complete efter aktiveringen. Se [underlaget](EVIDENCE.json).

## Källa, priser och produktfakta

Online Syd-snapshoten är `335b406f160a49c7bf351ceece8fcf6e`.
Produktobservationer: 2026-10-29 08:56:22.714511–09:23:30.978844 UTC.
Ingen ny källhämtning eller förnyad observationstid gjordes för kopplingen.
Ordinarie paket-, vikt- och styckpris används. Onlinekampanjer/medlemspriser
överförs inte. Varje destinations egna kampanjobjekt var byteidentiska i
kandidatkontrollen; deras faktiska datum, medlemskap och köpgränser gäller.

Exakta kommun-, butiks- och ledger-ID:n styr kopplingen. Jägersro heter Coop
Forum i den officiella locatorn. OWN:s interna källbutik binds till verifierade
730400 i samma snapshot. Främmande eller tvetydig produkt-/butikskälla stoppar
bygget. Förpackning, GTIN och källans köpbegränsningar bevaras.

Faktaläsaren löser enbart det explicita produkt-ID:t
`<käll-UUID>:stora-syd:<destinations-ID>` med rätt ägarroll, katalogkanal,
onlineursprung och fysisk destination. Samma snapshot, råprodukt-ID och
dokumenthash krävs. Ingredienser och näring följer därmed med även till
Malmö utan en separat onlinekontext som faktadonator. Saknade fakta antas inte.
Exakt kandidatbild verifierade 11237 tilldelade källposter i
Lunds verkliga prisunderlag: 7816 hade ingredienser och
6830 hade näringsuppgifter. Mjölkens båda fältgrupper provades
särskilt; saknat deklarationsunderlag fylldes inte i.

## Publicering och laddning

Ordinarie fullständiga lokala byggen färdigställde båda kommunernas prislistor
med den nya tilldelningen. Lundkontrollen upptäckte att oförändrade råsnapshots
gav samma universe-ID som före tilldelningen. Den rättade byggaren inkluderar nu
`stora-coop-syd-base-v1` i befintlig source_strategy_version och båda cachekeys.

De färdiga listorna återanvändes efter hashkontroll. Endast versionssträngen
och dess härledda universe-ID ändrades: omvänd byteersättning återskapade
hela originalfilen exakt. Samtliga pris-, produkt-, index-, kandidat- och
tidsbytes består. Ordinarie slutmodell, snapshot-/kontext-/färskhetsgrindar,
representativ varukorg, kontroll av lagrade bytes och atomisk aktivering
användes. Därefter verifierades faktisk laddning och normal Coop-kvittens.
Detta är ingen ny prisberäkning eller insamling.

- Lund: `price-universe:91e1e624c0139abdbc7a2dc1004e7a389d20a502d0cf9c303e73bf9274c8db3b`.
- Malmö: `price-universe:1557275410a993563d7f095725c949ee25a050dd7090110371425a79a4e90c02`.

Serverns schema är fortsatt måndag/torsdag 03:17 svensk tid, med en gemensam
Syd-källa. Malmös publiceringsfingeravtryck följer också källans aktiva snapshot.
Den tidigare dokumenterade Windowsregistreringen ändrades inte i detta uppdrag.

Slutlig driftkontroll gav ready 200, noll okända obligatoriska kontexter och
noll aktuella HTTP-fel i mätunderlaget. Lagringsunderhållet efter publicering
är complete. Den befintliga konservativa kapacitetsindikatorn är fortfarande
under sin uppskattning: cirka 10,8 GB ledigt mot 16,6 GB beräknat utrymme
för två databaskopior och artefakter. Ingen återställningskopia under den
verifierade tvåkopiegränsen togs bort för att ändra indikatorn. Detta är en
separat kapacitetsfråga; genomförd backup, publicering och laddning är verifierade.
