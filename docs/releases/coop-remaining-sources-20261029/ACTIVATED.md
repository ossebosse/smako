# Återstående Coop-källfel rättade och verifierade

Appen kör `source-ops-2600390d3943` (bild `sha256:11068cd153f6dc7aed4b4cea2cc9630aa05912993f89584b074302b309c3b29c`), aktiverad 2026-10-29T08:54:44.133202+00:00.
Insamlingsprocessen kör `source-ops-47b1f0fdb717` (bild `sha256:5e2684e49176e27fc077fa7021b9fb81da4bcdbd167f78e7587c2bd5ef0cae55`),
aktiverad 2026-10-29T10:18:36.341802+00:00. Appens container och bild förblev oförändrade vid det sista bytet.
PR [44](https://github.com/ossebosse/smako/pull/44),
[45](https://github.com/ossebosse/smako/pull/45) och
[46](https://github.com/ossebosse/smako/pull/46) är integrerade i main.
Slutlig kod är `47b1f0fdb7178deaed266fcb29660c2a92f870dc`, main-merge `2e0b87a7c6d55fbabdf225920630a78136c9da27`.
Slutlig [PR-CI](https://github.com/ossebosse/smako/actions/runs/40854141065)
och [main-CI](https://github.com/ossebosse/smako/actions/runs/40855326236) är gröna.
Se [kontrollunderlaget](EVIDENCE.json) och [fält-/gränsgranskningen](ONLINE-REVIEW.md).

## Fyra verifierade tomma Malmö-källor

Butikernas officiella identitet och rubrik stämmer. Malmö Central, Kornettsgatan
och Djupadal svarar HTTP 200 med exakt `{}` från den butikskopplade offentliga
API-källan och har inga produktkort. X:-tra Nydala har uttryckligen tom aktuell
publikationslänk och inga alternativa aktuella publikationer.

| Butik | Officiellt ID | Verklig observation UTC |
| --- | --- | --- |
| Coop Malmö Central | 3833 | 2026-10-29T08:31:30.228591Z |
| Coop Kornettsgatan | 3835 | 2026-10-29T08:32:03.326486Z |
| Coop Djupadal | 3831 | 2026-10-29T08:32:36.521576Z |
| X:-Tra Nydala | 3829 | 2026-10-29T08:41:36.678467Z |

Parser v8 kräver exakt butik, källa, lyckad status och tom DOM. Avstängda
reklamblad får bara passera importsteget för en verifierad tom källa. Null,
okända svar, fel status/butik och okända PDF-layouter är fortsatt blockerade.
De tre fysiska svaren återverifierades utan nät med samma bytes och tider;
X:-tra kontrollerades färskt. Tomma snapshots har inte promoverats som priser.

Dashboarden visar alla fyra med lyckad kontroll, noll felräknare och noll
priskontexter. Nästa hämtning är 2 november 03:17 svensk tid. Inga priser
eller GTIN har hittats på. Det publicerade dashboard-scriptets SHA matchar
kandidaten exakt. Admin utan autentisering ger fortsatt 401.

## Coop Online Syd

En normal fullhämtning gav 816 sidor/748 kategorier, 12381 råposter,
11237 unika produkter och 1144 identiska dubbletter mellan kategorier.
Inga transportfel, konflikter eller karantänposter. Första kandidaten
`4ce8bec702854547882efb58acdb3fc2` avvisades korrekt för tre nya fält.
Alla 818 rådatafiler hashverifierades och återanvändes utan ytterligare nättraversering.

Den kvalificerade aktiva återspelningen är `335b406f160a49c7bf351ceece8fcf6e` med
11237 produkter. Produktobservationer: 2026-10-29T08:56:22.714511+00:00
till 2026-10-29T09:23:30.978844+00:00. Observationerna har inte flyttats till
återspelningens körtid. 1328 produkter
har kampanjer som undanhålls vid okänd köpgräns; tre motstridiga typsammanfattningar
undanhåller också kampanjer. Verifierade B2C-baspriser behålls.

Parser v5 granskar bara de exakta nya typ-/bildsökvägarna för 730400. Typlistan
måste vara känd, unik och stämma med faktiska kampanjrader. Bildlänken används
inte för prisfakta. Nya fält och typbyten förblir blockerade. En typetikett ger
aldrig pris eller obegränsad köpgräns. Coops styckgräns räknas om till hela
rabatterade köpgrupper för flerpack. Checkout-test: sex förpackningar à 10,90,
två för 15 och högst fem styck ger 51,80, inte 45. Gränser, datum och medlemskap
behålls. Lagrat pris och lagrade kampanjvillkor kontrollerades efter import.

Lunds befintliga kanoniska onlinekontext är `context:coop:23eaae11c9661e68`.
Malmö har ingen sådan onlinekontext i sitt valda scope och behåller sina
butikskopplade källor. Inga användarval eller butiksområden har utökats.
Online Syd är ONLINE_FULFILLMENT/online_price, aldrig fysiskt butiksbaspris.

## Publicerat och bevarat

- Lund: `price-universe:0f311e3d5107ad4480721d9ab3d16cf480eaab293367b26e3dc98e1300aa7082`, bekräftat laddad, normalt returvärde 0.
- Malmö: `price-universe:e8ed718b6d66124375aac4b7ec42b70ec6f80f7f32cca86f1f65a22b960d0289`, bekräftat laddad, normalt returvärde 0.

Dashboarden verifierar den nya online-snapshoten i Lund och oförändrat Malmö-scope.
De tio tidigare rättade Coop-butikerna har kvar exakt samma 2925 kampanjpriser
och observationstider. ICA-baspriserna består. Åldersvarningar är separata från
källfel; kvalificerade baspriser behålls tills de ersätts.

Första releasen ändrade 13 appfiler och 10 schedulerfiler, med 993/991 övriga
runtimefiler byteidentiska. Slutlig komplettering ändrade bara tre schedulerfiler;
998 övriga schedulerfiler och hela appbilden är oförändrade. Recept-/beräkningskod
består. Två adminfiler i första releasen ändrade den konservativa förberedelsehashen
från c3a22c... till 588016...; den vanliga cacheinvalideringen behölls.

Verifierade backuper: 20261029T084441Z inför appändringen och `20261029T100721Z` inför
slutligt källbyte. Kandidat cb5b510fca04 stoppades före aktivering; dess verifierade
backup 20261029T095005Z ändrade inga aktiva bilder eller priser. Samtliga tidigare
314 planrevisioner, 123 privata tillstånd, två konton, en session och fyra authförsök
bevarades. Mountar, miljö utöver BUILD_ID och övriga containrar kontrollerades.
Det gemensamma driftlåset användes genom bygg, backup, byte, återspelning och publicering.

Driftens reservkrav sänktes inte när återspelningen först stoppades av diskgränsen.
Oanvänd byggcache och två äldre schedulerbilder före den omedelbara återställningsbilden
rensades under låset. Aktiva bilder, omedelbara återställningsbilder, datavolymer och
verifierade backuper behölls. Retention och kapacitet kontrollerades före fortsättning.

Slutlig driftstatus bekräftar tillräckligt diskutrymme med oförändrad reservgräns.
Båda Online Syd-incidenterna `source-5bee65424ddcdca6ed78c16d` och
`source-c861b36e7feaec4e533683b5` är markerade `source_recovered`.

Serverhämtning sker fortsatt måndag/torsdag 03:17 svensk tid. Windowsreläets äldre
uppgiftsregistrering kräver fortfarande administratör och ändrades inte här.
