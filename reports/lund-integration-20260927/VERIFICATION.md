# Lund 1281 – samlat aktuellt integrations- och driftprov

**Inte redo för separat aktiveringsbeslut. Ingen produktion eller aktiv schemaläggning har ändrats.**
Obligatoriska `primat:ica:1004409` (ICA Kvantum Malmborgs Clemenstorget) återvalideras nu av källan som `tier=offers_only`, `coverage=offers_only`, `selected=false`. Det tidigare verifierade kontraktet kräver `full_catalog`. Det saknas färsk komplett LKG. Den fullständiga federationen och dess atomiska publicering stoppas därför korrekt. [Aktuell identitetskontroll](results/primat-identity-check.json) visar det faktiska svaret, inte ett antaget nätfel. Gunnesbos identitet/täckning återvalideras fortfarande, men den obligatoriska bunten kan inte publiceras partiellt.

## Paket och bevarat arbete

- Git HEAD: `02ad73b8491f4b30679b3151b52686e27bedb8e6`; detta är **inte** en ren HEAD-byggning. Alla tidigare opublicerade ändringar ingår.
- Slutbild: `sha256:32e838155b0ef2b4b4eb9944cb7d1b31324b37e7ea56eb6d840fc70fc9e1ff87`. Full identitet: [final-image.json](final-image.json).
- Källträd SHA-256: `3e9cf6f3656bb20298560d44bbca079690834946ee3a773ddbe8126bd71b9899`. 589 paketerade filer verifierade mot bilden; `pip check` godkänd. App/collector/refresh ligger i samma bild.
- Föregående sökleverans: 9 kodhashar och 546 bevisfiler oförändrade. Inga recept, proteinmål, sökbudgetar, kampanjgodkännanden eller användarval har ändrats.
- Initial liveinsamling kördes före de smala integrationsrättningarna. Sparade verkliga svar återspelades därefter i slutlig kvalificeringsväg utan nät och utan nya observationer. Det första HTTP-provet använde den logiskt identiska bilden före Ruff-rättning av en blankrad i Coop-modulen; `http-results-final.json` verifierar det slutliga paketet på nytt. Detta får inte beskrivas som att hela liveinsamlingen upprepades i slutbilden.
- Testdata, databaser, manifest, sparade planer och rollback finns endast under `/var/tmp/smako-lund-integration-20260927`. Produktionsmanifest/data har inte skrivmonterats.

## Genomförda gemensamma integrationsrättningar

1. Coop-katalogen hade nya valfria `percentageDiscount`/`adjustedPercentageDiscount` samt beskrivande `localProduct`-fält. Den redan befintliga parsern hanterar procentfält tillsammans med uttryckligt absolut köppris. En snäv versionsbunden schemagranskare godkänner bara dessa specificerade tillägg, inte nya prisroller/villkor eller andra typbyten. Rå schemaavvikelse sparas.
2. Hemköps katalog hade valfria `energyDeclaration`-uppgifter för lampors EPREL-energimärkning, inte livsmedelsnäring. Granskaren tillåter dessa specificerade beskrivande fält och de verifierade array/null/objekt-differenserna. Sidornas antal/slutsentinel kontrolleras fortsatt. Inga generella godkännandeflaggor har införts.
3. Primat-refresh rapporterar nu första verkliga stoppet `exact_context_revalidation`. Om obligatorisk identitet/täckning fallerar utan giltig LKG stoppas körningen före de annars onödiga produktanropen. Befintligt stöd för giltig LKG och krav på komplett obligatorisk bas är oförändrat. Negativa tester för identitets- och täckningsdrift ingår.

Kod-/testlista: [integration-changes.json](integration-changes.json). **597 unika regressionstestfall godkända**, 676 testexekveringar inklusive riktade omkörningar. Ruff och compileall godkända. [Testresultat](test-summary.json).

## Faktiska aktuella källor

Ordinarie initial refresh tog 3894,82 s och avslutades med exit 1 på obligatorisk extern bas. Den lokala Willys-relayn tog 1482,83 s: 1254 faktiska HTTP-anrop, samtliga 200; 18 915 butiksposter, 10 486 unika Willys-produkt-ID. Primat gjorde 49 anrop i den ursprungliga körningen; två separata butikssvar hämtades sedan för diagnos (inga ytterligare produktanrop). Ett diagnostikskript behövde rättas efter serialiseringsfel; båda butikssvaren räknas som nätanrop. Inget spärrat fullprisflöde har upprepats utan ny grund.

Aktiva färska OWN-baskataloger: Coop Online Syd 11 481; Hemköp Karhögstorg 6188; Hemköp Brunnshög 5120; Willys Lund 10 242; Willys Nova 8673. Totalt 41 704 butiksposter före tillgänglighetsfilter. 192 markerades uttryckligen slut i lager; 41 512 återstår i PU. Coop och Karhögstorg importerades från samma dags sparade verkliga råsvar efter schemarättningen, med ursprungliga observationstider. Inga återspelningar räknas som nya hämtningar.

Första Willys-relayimporten avbröts med SQLite `OperationalError`; exakt underliggande SQLite-meddelande sparades inte. Oförändrad artefakt importerades sedan seriellt genom ordinarie inbox och godkändes, 18 915 rader/0 karantän/0 nya nätanrop. Grundorsaken till det första felet är inte bevisad. SHA-256 för relayartefakten finns i [relay-upload.json](relay-upload.json).

Kommuninventering: Coop/Stora Coop/X:-tra 10 av 778 innanför; Lidl 2 av 212; Willys 3 av 257 (två online och Hemma Stortorget som reklamblad); City Gross 0 av 38. Ingen okänd butik har tyst gjorts till Lundbutik. ICA-jobbet använder däremot befintligt ortsläge, 9 av 12 upptäckta; Hemköp befintliga godkända kontexter. Dessa är öppet redovisade kommunluckor, inte nyimplementerade funktioner.

Aktuella erbjudanden: Coop/X:-tra 503 butiksposter; ICA 219 godkända OWN → 217 PU; Lidl 28 per butik = **28 unika produkt-ID**, inte 56 nya erbjudanden; Willys Hemma 31 poster från 34 annonser/40 tolkade variant-/grupprader. Lidl: 387 kandidater per butik, 357 stoppade först vid obelagd butiksgiltighet/produkt–nationell kampanjbindning samt 2 parserkarantäner (oprövat rabattvillkor respektive icke-exakt jämförprisintervall). Det ger 28 + 359 = 387 utan dubbelräkning. Willys osäkra prisplaceringar, variant-/mängdgrupper och villkor kvarstår i karantän; gamla dokumentgodkännanden har inte flyttats till nya dokument.

[Butiksvis tabell med observationer, officiella länkar, OWN/PU, karantän och nästa uppdatering](STORE-RESULTS.md). [Fullständiga kvalificeringsuppgifter](results/source-coverage.json). Tal för prisimport betyder inte näringsgodkända produkter, och butikskopior räknas inte som ny unik täckning.

## Publicering och faktiskt serverat innehåll

Full Lund: ingen aktiv godkänd artefakt, inget serving-reload av ofullständig bas. De sex obligatoriska baskontexterna behölls. Felrapporten och manifestspärren är resultatet, inte en lyckad publicering.

Oberoende kontroll: **separat OWN-only-artefakt**, byggd med samma ordinarie PriceUniverse-byggare och aktiveringsvalidator; 42319 poster i 27 kontexter. Den är aldrig ersättning för den fullständiga Lund-kandidaten. HTTP begränsades ytterligare till verifierade `physical_store` + `offers`, vilket utesluter Coop Online Syd, Willys online, Hemköps nätpris och Primats legacy-default för fysisk kanal.

Byggning och andra byggning: 220.567 respektive 433.718 s väggtid. Samma produkt-/observationshash efter båda: `0e679adcfc58377666ecd7170d97adb3fd91ea0aae4d222c1e8f1a6411b461aa`. Första ordinarie builderdelen tog 136.425 s, andra 158.952 s; andra kördes med en laddad app och provprocess i samma begränsade container. Extra väggtid utanför builderns spann är inte fullständigt CPU-/I/O-profilerad och får inte tillskrivas en sökregression. Inga externa prisanrop, inga förändrade observationer. Läsning ur verklig serving-manager bekräftar identiskt innehåll. Dessa är två körningar av ordinarie byggare/atomisk aktivering, **inte** ett godkänt komplett federerat daily-refresh-prov.

## HTTP-planering – faktiska resultat

| Prov | HTTP/status | Varukorg kr | Sekunder | Köpstatus | Exakt/uppskattat/villkorat | Valda butiker |
|---|---|---:|---:|---|---|---|
| full-lund-original-exact | NOT_RUN_REQUIRED_BASE_MISSING | — | — | — | None/None/None | — |
| full-lund-original-estimated | NOT_RUN_REQUIRED_BASE_MISSING | — | — | — | None/None/None | — |
| full-lund-plus-exact | NOT_RUN_REQUIRED_BASE_MISSING | — | — | — | None/None/None | — |
| full-lund-plus-estimated | NOT_RUN_REQUIRED_BASE_MISSING | — | — | — | None/None/None | — |
| initial-physical/physical-exact | 422 | — | 19.865 | — | 0/0/0 | — |
| initial-physical/physical-estimated | 422 | — | 7.625 | — | 0/0/0 | — |
| initial-physical/representative-current-cheese | 201 | 171.68 | 5.521 | VERIFIED_WITH_ESTIMATES | 1/1/0 | Lidl Åkerlund och Rausings väg 1 |
| final-package/representative-current-cheese | 201 | 171.68 | 20.6 | VERIFIED_WITH_ESTIMATES | 1/1/0 | Lidl Åkerlund och Rausings väg 1 |
| final-package/representative-current-multibuy | 422 | — | 5.427 | — | 0/0/0 | — |

Originalprofilens fyra kompletta jämförelser kördes inte: ingen färsk komplett bas kunde publiceras. Kostnad och valda rader är därför okända, inte noll. Historiska 484,73 kr används inte som nytt resultat. Originalets 15/20, 40/30/20, max två butiker, receptversioner och användarprofil är bevarade.

Det separata fysiska 15/20-provet har Willys Plus/Lidl Plus i en testkopia. Både exact och estimated stoppar med 422 DATA_BLOCKED: 96/96 middagskandidater avvisas vid produkt-/faktakvalificering, 0 når singleton-/menysökning. Första stopp utan dubbelräkning: rapsolja 17, tofu 15, rödlök 12, vitkål 12, tortillas 8, ägg 7, kokosmjölk 4, sojasås 4, linser 4, crème fraiche 3, svarta bönor/kidneybönor/kikärtor/nötfärs 1 vardera samt 6 närings-/beredningsunderlag (ris; ett fall även kyckling). Detta är begränsat till det aktuella fysiska erbjudandeunderlaget, inte bevis för global omöjlighet eller högre pris. Produktdiagnostiken är avgränsad: 551 produkter utelämnades ur detaljloggen per fritt prov, medan de 96 första receptstoppen finns sparade. Ingen full ekonomisk jämförelse finns för alternativ som stoppats tidigare.

Separat aktuell varm ostsmörgås, en frukostportion, tillåten Lidl Åkerlund och Rausings väg: **171,68 kr**, 1 exakt + 1 uppskattad rad, 0 villkorade. Lingongrova 500 g/17,90 kr med Lidl Plus; Hushållsost cirka 2,2 kg × 69,90 kr/kg = 153,78 kr, offentlig kampanj, max 3 förpackningar/hushåll. Giltigt 21–27 september. Receptet använder 100 g av varje, inte hela köpvikten. Befintliga verifierade produktdeklarationer ger 33,8 g protein mot 30 g; måltiden är `ESTIMATED` enligt insatsbaserad beredningsmetod. Priset är `VERIFIED_WITH_ESTIMATES`, audit PASS; inga produktlås, extraköp eller kandidatpatchar. Källor och deklarationshashar finns i den sparade HTTP-responsen, [officiell butik](https://www.lidl.se/s/sv-SE/butiker/lund/akerlund-och-rausings-vaeg-1/). Korgkostnaden avser hela köpet och är inte exakt slutkvitto eller påstådd besparing.

Separat åttaportionsprov för aktuellt Coop-flerköp med vanlig varm ostsmörgås och tillåtet butiksval stoppar vid saknat näringsunderlag med rätt enhet för bröd. Mängden per portion är samma 100 g bröd + 100 g ost, mål 30 g. Det är **inte ett godkänt aktuellt flerköpsmåltidsprov**; ingen ändring av mål eller gissad referens används för att få det grönt. Befintliga komponentregressioner bevisar inte detta saknade liveintegrationsfall.

Tiderna jämför inte identisk uppvärmning: första exact är kallare, estimated följer samma process; första ostprovet följer två misslyckade profilprov och det slutliga paketets ostprov är kallt. De får inte användas som en ny före/efter-prestandajämförelse. [Maskinläsbara resultat och valda produkter](profile-summary.json), [ursprungliga HTTP-responser](results/physical-probe/http-results.json), [slutpaketets HTTP-responser](results/physical-probe/http-results-final.json).

## Drift, giltighet, sparning och återställning

- Ordinarie full refresh: faktiskt genomförd och korrekt spärrad. Efterföljande ordinarie rebuildförsök utan ny extern insamling spärrat; globalt not_due för komplett Lund, komplett andra publicering/omstart och fyra kompletta profilprov är **inte verifierade**.
- Separat fysisk yta: atomisk publicering, faktiskt reload, andra builderkörning med identiska källposter och reload samt processomstart verifierade. Sparad ostplan identisk före/efter; ingen tyst omräkning.
- Frivillig Willys-källa: kopierat isolerat källtillstånd läser beständigt kommunval 1281, returnerar verkligt `not_due` med 0 prisanrop. Injicerat ConnectionError behåller giltiga godkända referenser. Återhämtning med sparade verkliga råsvar och explicit testklocka +16 minuter godkänner 31 rader; observationerna är oförändrade. Det är replay, inte ny insamling. [Driftbevis](results/optional-lifecycle.json).
- Verkligt publicerad artefakt under explicit framtidsklocka och nätförbud:
- actual_now: 0 inaktiva kampanjposter, 0 kvar i äldre index, **0 godkända köp**; 3323 ordinarie priskandidater.
- tomorrow_test_clock: 784 inaktiva kampanjposter, 138 kvar i äldre index, **0 godkända köp**; 3323 ordinarie priskandidater.
- 49h_test_clock: 784 inaktiva kampanjposter, 0 kvar i äldre index, **0 godkända köp**; 0 ordinarie priskandidater.
- 8days_test_clock: 801 inaktiva kampanjposter, 0 kvar i äldre index, **0 godkända köp**; 0 ordinarie priskandidater.
  Äldre icke-ICA-index kan alltså fortfarande innehålla utgångna referenser tills färskhetsfiltret slår till; ordinarie användarprissättning avvisar dem före köp. ICA:s belagda kampanjundantag har separat slutdatum, inte ett generellt slopat 48-timmarskrav. Inga utgångna erbjudanden släpptes till köp i provet. [Giltighetsprov](results/physical-probe/expiry-admission.json).
- Klientprov: verklig Chromium-rendering, DOM-text och skärmbild sparade. Texten visar `ca 171,68 kr`, cirka-vikt, hel förpackning, minst 100 g användbar vikt, medlemskap och kampanjdatum. Ingen bildmodell/bildanalys. DOM-kontrollen är inte en pixelvis layoutgranskning. Allergenstatus är NOT_REQUESTED, inte verifierad allergisäkerhet.
- Isolerad rollback: gammal PersonalPlanner-modul från `/rollback`, separat kopierad plandatabas, GET 200 och identisk plan. Modulhash och faktisk planlagringssökväg finns i serving-beviset. Det bevisar **läskompatibilitet**, inte ny omräkning i äldre kod. Inga produktionsfiler har återställts eller ersatts.

## Kvarstående aktiveringsberoenden

1. Återställ/verifiera obligatorisk full bas för Clemenstorget hos Primat, eller fatta ett separat, uttryckligt beslut om annan belagd basstrategi. Denna körning tar inte bort kravet. Därefter måste komplett federering, andra ordinarie rebuild/restart/not_due och samtliga fyra fria profilprov köras med samma nya kompletta underlag.
2. Full kommuninventering i den befintliga ICA-/Hemköpsdriftkopplingen är inte visad här. En ny kedjeimplementation har inte påbörjats för att dölja detta.
3. Aktuellt fullständigt fysiskt 15/20-underlag saknas för angivna ingredienser/fakta. Aktuellt flerköpsmåltidsprov kvarstår vid brödets näringsunderlag. Öppna variantgrupper får fortsatt inte bli automatiska närings-/allergigodkända ingredienser.
4. Första relayimportens ursprungliga SQLite-fel har inte fullständig grundorsakslogg. Seriell återhämtning är visad, inte bevis att feltypen aldrig återkommer. Behåll operationslåset och undvik samtidiga tunga databasläsningar under import.
5. Malmö fullständiga aktuella publiceringsprov är separat och **olöst**. Det är inte orsaken till Lunds nuvarande Primat-stopp.
6. Historisk Lidl-fixture `reports/source-implementation-20260915/lidl_offer_adapter.py` saknas fortfarande. Dess gamla test kan inte samlas/köras: GTIN/variant/pack-/dokumentbindning, separat observationsgrund, kycklingberedning/avrunnen mängd, kolhydratgräns <0,5, korrupt deklaration och ost→recept→audit. Nyare tester och aktuellt ostprov täcker delar men ersätter inte exakt detta historiska skydd. Luckan är ett kvarstående releasebevis; den gör inte den aktuella källan automatiskt felaktig och förklarar inte Primat-felet.

Inför ett senare aktiveringsbeslut måste då förfallna källor uppdateras, 36/48-timmarsgränserna kontrolleras på verkliga observationer och kampanj-/medlems-/butiksgiltighet kontrolleras på nytt. Denna söndags flertalet erbjudanden går ut vid midnatt svensk tid; nästa befintliga kommunhämtning är 27 september 21:00 UTC (23:00 svensk tid), kampanjövergång 22:00 UTC. Det är sparad behovsplan, inte ett nyaktiverat schema. [Separat aktiveringsunderlag](ACTIVATION.md).
