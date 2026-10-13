# Driftgranskning och prisåterhämtning, 13 oktober 2026

Uppdrag: granska driften, identifiera misslyckade prisuppdateringar och åtgärda
verifierade fel. Arbetet utgår från aktuell produktion, inte äldre releaseantaganden.
Gren: `fix/operations-20261013`. Privat körunderlag: `.local/ops-20261013/`.

## Verifierat före åtgärd, 08:32 svensk tid

- Lund: readiness 200, publicerat = laddat `a9c1b0fbe3b…`, fem obligatoriska
  baskontexter färska, senaste Willys-leverans kvitterad 02:46 svensk tid.
- Malmö: readiness 503. Fyra obligatoriska Willys-kataloger var 57–58 timmar
  gamla och spärrade enligt oförändrad 48-timmarsgräns. Publicerat = laddat
  `58f8f1798b1e…`, men nya Hemköp-data väntade på komplett publicering.
- Windowsuppgiften var aktiverad men senaste schemakörningen hade resultat 1.
  Lund lyckades; Malmö saknade leveranskvitto för det nya paketet.
- Willys-incident `source-162416ebcdaf0d2f9ba41a8e`: tre avvisade importer,
  senast snapshot `18dbbce61921492090342b14ffe386b7`. Malmös prisbygge hade
  fem registrerade fel i `pipeline-1483e13b4f7cc64016752fed`.
- City Gross Hyllie hade färskt godkänt underlag i kommunens separata OWN-databas.
  Driftkontrollens sökning enbart i huvuddatabasen gav felaktigt `unknown`.
- Serverns lagringsmarginal var tillräcklig: cirka 107 GB ledigt mot cirka
  11,1 GB uppskattat behov. D: hade cirka 637 GB; C: cirka 5,6 GB.

## Rättningar och belägg

1. Willys parser v5 granskar endast övergången number ↔ nullable number på
   katalogfältet `priceValue`. Andra typer, borttagna fält och all-null-övergång
   är fortsatt spärrade. Saknat pris blir varken noll eller ett antaget kampanjpris.
   Prisparsningen i övrigt är oförändrad. V4-reläpaket behåller kompatibilitet.
2. Sparat Malmö-paket `1e6defa470b5…` hashverifierades: 2 569 rådokument.
   Exakt en post per butik 2114/2144/2244/2253 saknade pris: rengöringsprodukten
   `101774905_ST`. Den är inte ens slutsåld i alla fyra butiker, så slutsåldhet
   används inte som antagande eller villkor för rättningen.
3. Isolerad full återspelning kvalificerade 39 576 produktposter, noll
   parserkarantän, healthy och promoverad. Nätåtkomst spärrad; samtliga
   ursprungliga råhashar och observationstider bevarade. Detta är produktposter
   per butik, inte antal unika varor. Standardverktygets 32 MB-reproduktion
   stoppade först enligt sin gräns; därefter användes avgränsat separat underlag.
4. Riktade Willys-/artefakt-/schema-/kvalitetstester, Ruff och compileall passerade.
   Första testomgångens två fel gällde gamla versionsförväntningar och ett
   felaktigt testantagande om redan stödd `salesPrice`; slutproven passerade.
5. City Gross-diagnostiken följer nu befintlig hashverifierad kommunreferens,
   exakt butik och godkända snapshot-ID:n. Saknat, felbundet eller oläsbart
   underlag kvarstår som unknown. 28 diagnostiktester inklusive negativa fall
   passerade; kontrollerna är läsande och gör inga butiksanrop.
6. Kärnloggen visar återkommande global minnesbrist som dödade den faktiska
   appcontainerns Python-process den 12 oktober; Docker visar sex omstarter.
   Två kvarlämnade verifieringscontainrar från 29 september/2 oktober använde
   cirka 3,5 GiB. De var inte proxyanslutna, hade separata testdatamontage,
   restart-policy `no` och ingen observerad trafik senaste tio minuterna.
   Båda stoppades 08:58:37 svensk tid, utan radering eller appomstart.
   Tillgängligt värdminne ökade från cirka 3,6 till 7,1 GiB. Detta undanröjer
   onödig belastning, men är inte ett flerdygnsbevis mot framtida minnesbrist.
7. Dagens ordinarie backup `20261013T004702Z` (02:47 svensk tid) verifierades
   mot samtliga filhashar: sex filer, 5 256 847 781 byte, PASS. Manifestet har
   databas-, plan- och prisintegritetssektioner. Det föregående bevarade
   dagsmanifestet är 10 oktober; 11–12 oktober saknas i listningen och orsaken
   är inte fastställd. Ingen full återställningsövning påstås genomförd här.

Prisrättningen aktiverades 08:45:51 svensk tid: commit `1a7f5098942c`,
source BUILD_ID `ops-price-recovery-1a7f5098942c`, image `c241eb79a8e9…`.
Fyra filer lades ovanpå den verifierade aktiva källimagen `1f10310fbccf…`.
Första aktiveringsförsöket avstod eftersom ordinarie jobb körde. Nästa försök
tog driftlåset; app/proxy, scheman, mounts, 259 äldre planrevisioner och 85
privata tillstånd verifierades bevarade. Ingen app-/UI-release ingår.

City Gross-diagnostiken aktiverades 09:18:14 svensk tid ovanpå denna version:
commit `0fa290342376`, source BUILD_ID `ops-price-recovery-0fa290342376`,
image `da1b2b2c7119…`. Samma bevarandekontroller passerade igen.
Appen är fortsatt `editable-sliders-7987bd5bc5d1`.

Kvittenssteget rättades därefter i commit `2f44f4e1b13b`: vid samma aktiva
snapshot och hashverifierade manifest kontrolleras redan laddad version via
befintlig kommunbunden readiness innan ett nytt reload-anrop görs. Exakt
manifest-ID och ready 200 krävs; saknat/felaktigt bevis ger fortsatt vanlig
omladdning eller fel, aldrig ett antaget kvitto. 13 artefakttester samt sju
befintliga prov för exakt kommun/version och timeout-återhämtning passerade.
Ruff och compileall passerade. Source-only aktivering 09:32:07 svensk tid:
BUILD_ID `ops-price-recovery-2f44f4e1b13b`, image `885790a82a04…`.
Alla 261 då existerande planrevisioner och 86 privata tillstånd bevarades.

## Slutverifiering

Den första återleveransen importerade och promoverade Willys-snapshot
`88f6115f68be4b5eb675121bee3225e1` med parser v5 och publicerade Malmös nya
prisuniversum. Den avstod dock kvitto 09:13 eftersom runtime-aktivering ännu
inte var bekräftad. Vid läsande kontroll 09:18–09:19 var Malmö readiness 200,
publicerat = laddat `13ad70e296a4e1fcfe68158314a050224bd66b12d3e428f0f0cbb90445306a38`,
och alla nio obligatoriska källkontexter godkända, färska, publicerade och laddade.
Även Hemköps tidigare väntande uppdatering hade då publicerats. Lund var fortsatt
200 med oförändrat manifest och fem färska obligatoriska källkontexter.

En andra återleverans 09:19–09:25 visade konkret `TimeoutError` från det
onödiga reload-anropet trots redan korrekt laddat prisuniversum. Därför infördes
den ovan beskrivna idempotenta kvittensrättningen. Nästa ordinarie
Windowskörning 09:30 slutförde serveraktiveringen 09:36:19 och kvitterade
exakt paket `1e6defa470b5adee0ac56d8fcbe0a91dba79bddf8523a7c425931508c02038b4`.
Aktiveringssvaret var `already_active`, snapshot `88f6115f68be4b5eb675121bee3225e1`
och samma publicerade/laddade Malmö-manifest. Windowsuppgiftens senaste
resultat är **0**; nästa ordinarie körning är 17:30 svensk tid. Inga väntande
leveranser finns i Lund eller Malmö. Källincidenten är `source_recovered` och
Malmös tidigare prisbyggnadsincident `recovered` i det ordinarie incidentindexet.

Verkliga Chromium-prov i separata gästsessionskontexter:
- Publik Malmö-meny: HTTP 201, fem middagar à två portioner, 17/17
  acceptanskontroller, basket-audit, näringskvalitet och identisk GET/omladdning;
  inga browserfel. Tog **512,3 sekunder**.
- Personlig Malmö-meny: en middag à två portioner med uttryckligt vald
  Willys-onlinekontext `context:willys:bbd37ea3cd468706`, godkänd checkout-audit
  och identisk GET/omladdning, inga browserfel. Tog **40,2 sekunder**.

Den publika menyns långsamhet är en kvarstående prestandabrist. Sparad faktisk
fasprofil visar 502,4 sekunders total planering, 360,2 sekunders huvudsökning,
130,3 sekunders efterföljande varierad sökning och 8,1 sekunders prisprojektion.
Tidsfälten för varied/store-tradeoff överlappar och ska inte summeras dubbelt.
Detta är inte ett misslyckat prisimportsteg. Inga kvalitetsgränser eller
sökparametrar har sänkts för att dölja svarstiden. Upprepat prov med samma
publika val lyckades också med samtliga kontroller, men tog **477,8 sekunder**.
Det var alltså inte bara en första kall körning. Optimeringen är inte reparerad
inom denna käll-/driftrelease; profilen är sparad som konkret kvarstående arbete.

Sista kommunvisa kontrollen efter menyproven: readiness **200 i båda kommunerna**,
publicerat = laddat och alla fem respektive nio obligatoriska baskontexter
FRESH, godkända, publicerade och laddade. Under ett pågående menyprov gav ett
separat statusanrop tillfälligt okänt laddnings-ID trots readiness 200 med rätt
version; efter avslutat prov verifierades även det fullständiga statusanropet.

Slutlig bevarandekontroll 09:38:57: samtliga ursprungliga **259 planrevisioner
och 85 privata tillstånd** är oförändrat kvar.
Totalt finns nu 262 planrevisioner och 86 privata tillstånd efter de tre
isolerade menyproven. Ingen ny OOM-händelse eller appomstart under granskningen;
appens omstartsantal är fortfarande sex från föregående dygn. De två gamla
testcontainrarna är stoppade och cirka 7,1 GiB värdminne är tillgängligt.
Maskinläsbar, avidentifierad verifiering: [EVIDENCE.json](EVIDENCE.json).

## Kvarstående källtäckning och återförsök

Följande är inte lösta av Willys-rättningen och räknas inte som lyckade uppdateringar:

- X:-tra Skansvägen 3658: ofullständig/blockerad publikation, senaste godkända
  hämtning 4 oktober; gammalt prisunderlag får inte föryngras.
- Malmö: Coop Malmö Central 3833, Kornettsgatan 3835 och Djupadal 3831 har
  misslyckade källförsök. Sparade körloggar visar browser-timeout.
- X:-tra Söderkulla 3646: officiell länk omdirigerar till `dr-saknas`.
  X:-tra Nydala 3829 saknar fungerande publiceringsunderlag.
- ICA 1003660 i Malmö: `missing_integration`, inget godkänt underlag.
- Coop Online Syd 730400 fick ett transportfel 06:10 svensk tid. Senaste giltiga
  katalog var fortfarande färsk. Ordinarie backoff angav nytt försök tidigast
  11:00:49 svensk tid, hårt stopp först 14 oktober 01:04. Källors återförsöksfrister
  och kvalitets-/färskhetsgränser kringgås inte.

Övriga listade butiksluckors automatiska återförsök ligger cirka 11:50–12:10
svensk tid enligt observationen. Externa källor kan inte ersättas med gissade
priser eller priser från en annan butik. Ingen ny notifieringstjänst infördes.

## Återgång och reproducerbarhet

Versionspaket och imageinformation sparas under
`/opt/smako/releases/ops-price-recovery-<commit>/`; aktiveringsbevis och tidigare
Compose-wrapper finns under motsvarande `/opt/smako/evidence/`.
Aktiveraren verifierar endast ändrad scheduler-image och BUILD_ID samt har
återgång till sin verifierade föregångare vid fel. Återgång hela vägen till
ursprungsversionen `municipal-source-7b7fe72472dd` återinför Willys-spärren. Återställ aldrig gamla databaser över senare användararbete.
Windowsreläets installerade version och schema lämnas oförändrade.
