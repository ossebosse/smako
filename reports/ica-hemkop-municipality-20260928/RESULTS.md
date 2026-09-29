# ICA/Hemköps kommunuppkoppling – 28 september 2026

**Lund: PASS genom hela kedjan i isolering.** ICA/Hemköps ordinarie jobb, OWN-import, PriceUniverse och beständiga uppdateringsurval använder samma verifierade kommunval. Femkällorskandidaten och Coop-v4 bevaras. **Malmö: kommuninsamling och kandidatbygge PASS; publicering BLOCKERAD** av ofullständig kontrollkorg. Ingen full Malmö-publicering eller produktionsaktivering påstås.

## Före och efter

| Kommun / kedja | Upptäckta / innanför / utanför / okända | Insamlade butiker | Radgodkända OWN | Aktiverad serving |
|---|---|---:|---:|---:|
| Lund ICA | 12 / 12 / 0 / 0 | 12 | 277 | 211 → 275 |
| Lund Hemköp, fysisk erbjudandekanal | 205 / 3 / 202 / 0 | 3 | 18 | 0 → 18 |
| Malmö ICA | 69 / 24 / 0 / 45 | 23 | 560 | 0; kandidat 556 |
| Malmö Hemköp, fysisk erbjudandekanal | 205 / 4 / 201 / 0 | 4 | 24 | 0; kandidat 24 |

Lunds totala faktiska serving: **42,003 → 42,085 produkter**, 33 kontexter. De fem obligatoriska onlinebasernas innehåll, observationer och källsnapshots är identiska. Coop/Stora Coop behåller 254 fysiska erbjudanderader och X:-tra sex, med separata käll-/felstatusar. Antalen kommer från faktiskt observerade svar och serving, inte från hårdkodade förväntningar.

ICA Södra Sandby bidrar med 27 produkter, Genarp 16 och Veberöd 17. Hemköp Dalby saknar onlinekatalog men har sex kvalificerade fysiska erbjudanden. Hemköps Brunnshög och Karhögstorg får vardera sex separata fysiska erbjudanden; deras onlinebaser på totalt 11 263 produkter är oförändrade. Hemköps 205 är den rikstäckande registermängden. ICA:s lokatorsvar bevisar inte en fullständig kommuninventering.

[Alla butiksrader, källor, nollresultat, karantän och nästa tider](STORES.md). [Aktuella erbjudanden och representativa köp](OFFERS.md). [Kodväg, källbindning och rättade fel](ANALYSIS.md).

## Rättning och skydd

ICA:s redan befintliga kommunstöd var inte inkopplat i ordinarie jobb/källpekare och providern filtrerade fortfarande på adressort. Hemköps ortfilter och förvalda katalogkontexter ersätts i kommunläget av officiell inventering, verifierat kommunurval och befintligt kontextregister. Den fysiska strukturerade erbjudandevägen återanvänder Hemköp-transport, OWN-collector, radgodkännande och vanlig publicering. Endast entydiga, stödda produktrader tillåts.

Återkommande driftprov fångade och rättade även att ett ICA-inventeringsfel kunde tömma kommunurvalet, samt att en saknad länk i lokatorsvaret kunde orsaka onödig återhämtning av en ännu giltig butikskälla. Giltig källa och observationstid behålls nu vid inventeringsfel, med synlig felstatus och begränsat återförsök. Interna OWN-ID:n och officiella butiks-ID:n jämförs i rätt namnrymder; negativa felbutiks-/snapshotprov finns.

Lundspolicyn `lund-own-five-base-20260928-v1` är oförändrad, SHA-256 `684952daee28c71123e5c5b2cc43f7c3ba1e043bcd02cf0270bea9603208bce1`. Nya butiker är frivilliga tillskott. Samma användarparametrar, butiksval, priskanaler och butikstak gäller. Inga nya obligatoriska Malmö-baser har antagits.

## Drift och acceptans

- Ordinarie import → rebuild → normal atomisk publicering → faktisk reload PASS. Nästa ordinarie rebuild med injicerat frivilligt Hemköp-fel ger synlig `failed_optional_source/ConnectionError`, men behåller exakt samma serving, baser och källreferenser. Omstart före nästa rebuild och efter profilproven har samma produkthash `f765863a845b49993ecc087ac88e673f43a7f0885b3d623c9e0385582bca65ac`.
- Ingen prisinsamling när arbetet inte förfallit. En verkligt förfallen ICA-inventering kördes dessutom: samtliga tolv butiker behöll identiska godkännanden, prisobservationer och kampanjscheman, **0 prisanrop**. Nästa Lund-inventering är 1/10 17:56 svensk tid; nästa faktiska ICA-kampanjkontroll är 28/9 23:00. Hemköps nästa prisgräns ligger 30/9 cirka 04:02–04:05, beräknad från originalobservation +35 h. Obligatoriska baser blir tidigast förfallna 29/9 cirka 04:13. Inga observationer har föryngrats. Isoleringen har inget aktiverat schema; varje butiks beständiga tid finns i butiksrapporten.
- Fyra faktiska HTTP-profiler PASS: original-exact 445.29 kr, original-estimated 445.29 kr, plus-exact 445.29 kr, plus-estimated 445.29 kr. Alla har godkänd checkout/audit, identisk GET efter sparning och efter faktisk omstart. Konsumentplaneringen kördes utan externt nätverk. Ursprunglig femmiddagsmilstolpe och tidigare kvalificering påverkas inte.
- Fyra representativa köp från de nytillkomna butikerna passerar befintlig matchning, heltalsförpackningar och audit. Exempel: Genarps vetemjöl 2 kg för 16 kr, Södra Sandbys mango 325 g för 15 kr och Dalbys panko 200 g för 15 kr; officiella butikskällor, hela inköpskostnader och överskott finns i erbjudanderapporten.
- Slutparserreplay av sju separata Hemköp-svar ger samma 42 godkända rader. 98 nya källrefererade råfiler och 2 232 bevarade basråfiler verifieras mot hash. Coops verkliga kampanjbytesbevis återanvänds; Hemköps test av en ny utgåva är uttryckligen syntetiskt och får nytt käll-/godkännandebevis även vid återanvänt kampanj-ID.
- **217 unika relevanta tester PASS**, Ruff och Python 3.12 compileall PASS. Alla 592 appfiler i slutimagen stämmer med det verifierade paketet; `pip check` PASS. [Maskinell acceptans](acceptance.json), [profilunderlag](profile-summary.json), [råkällkontroll](results/source-audit-final.json).

## Kvarstående avgränsningar

Malmös 580 produkter är två identiska kvalificerade kandidater, **0 aktiverade produkter**: den ordinarie publiceringsgrinden kräver en fullständig kontrollkorg och har inte försvagats. Detta är fortsatt den separata uppgiften full Malmö-publicering och val av dess baspolicy.

ICA Bunkeflostrand är verifierat i Malmö och har en officiellt länkad folder, men ingen verifierad strukturerad erbjudandelänk. Det är inte samma sak som att butiken saknar erbjudanden. Nästa källuppgift för den här vägen är en strukturerad källa bunden till butik 1003660. För 45 ICA-träffar saknas verifierbar kommunuppgift. Ingen sådan extern uppgift blockerar de redovisade fungerande Lund-butikerna. Övriga spärrade rader kräver entydig variant-/villkorsinformation och ska ligga kvar i karantän.

Äldre PurchaseTerms-kopplingar, nya komplexa kampanjvillkor, Lidl/Willys-täckning, full Malmö-publicering och historisk Lidl-fixture är inte lösta av detta prov. Originalpolicyn/Primat, tidigare releaser och användarval bevaras. Ingen ICA-baskatalog, bildanalys eller betalt modell-API användes.

## Paket och återgång

Isolerad releasekandidat: `smako-ica-hemkop-municipality:20260928-v8`, image `sha256:0790b31f3d7a781c86993a3195d1069b2bc038008f67c0ca918d7dfa3d196bd0`. Föregående verifierade Coop-v4-image och dess data ligger kvar orörda. Slutpaketet har separat datarot `/var/tmp/smako-ica-hemkop-municipality-20260928/data`; före-filer finns i `before/`, kodskillnaden i [code.patch](code.patch). Återgång i isoleringen kan använda det orörda tidigare Coop-paketet och dess egen datarot; ingen återställning av användardata behövs.

Produktion kvar på `price-recovery-lund-20260914a` / image `54dde8382599…`. **Ingen produktionsaktivering, Windows-ändring eller ändring av aktiva scheman.**
