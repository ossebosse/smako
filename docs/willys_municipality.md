# Willys kommunstyrda källrelä (ej aktiverat)

Kommunläget är ett uttryckligt tillval. Det ändrar inte användarprofiler,
ICA-/Coop-/X:-tra-inställningar eller standardreläets två verifierade Lundskontexter.

## Insamling och källbevis

`python -m grocery_data.source_cli collect willys --municipality 1281 --workspace <separat-beständig-katalog>`

Använd en separat beständig reläkatalog per kommun. `source-scope.json` bevarar
kommunen; nästa ordinarie `python -m grocery_data.local_relay --workspace <katalog>`
använder den utan butikslista. Använd aldrig testkatalogen med skarp `push`/`import`.
De befintliga push-/importkommandona har produktionsdestination och får köras först
efter separat aktiveringsbeslut.

Hela officiella Willys-registret jämförs med SCB RegSO 2025-kommungränser genom
befintlig geometri-/områdesfunktion. Adressort och kundpostnummer är inte gränsen.
Alla registerrader bevaras i inventeringen, inklusive okända/utanför/ej insamlingsbara.
Endast verifierade kommunbutiker med källans `onlineStore=true` kan använda den
befintliga fullkatalogtransporten. Det är butiksknuten **online_price**, inte
belägg för fysiskt hyllpris. Övriga butiker saknar verifierad transport i denna väg;
det är inte bevis för att de saknar erbjudanden.

Källartefakten innehåller register, sidföljder, exakt aktiverad/återläst butik,
kommungränsens version/hash samt riktiga observationer. Mottagaren räknar själv
om kommunurvalet och fullständigheten. En avbruten eller underkänd fullkatalog
exporteras inte. Katalogen kan innehålla både ordinarie priser, publika kampanjer
och allmänna medlemsavtal; dessa använder oförändrade befintliga kontrakt.

## Beständig serverkonfiguration

`WILLYS_MUNICIPAL_CONFIG` pekar på en beständig JSON-fil:

```json
{"schema":"willys-municipal-build-v1","build_scopes":{"22350":"1281","21120":"1280"}}
```

Postnumren identifierar befintliga **byggomfattningar**, inte butikspostnummer
eller en ny användargräns. Inga profiler skrivs om. Kommun-ID avgör inventeringen.
Filen ska finnas för avsedd driftanvändare och ingå i vanlig backup. Utan filen
accepteras inga kommunartefakter; det gamla reläkontraktet fungerar oförändrat.

`deploy/willys-municipality.override.yaml` är ett **ej applicerat** tillägg som
förmedlar denna enda variabel till app, scheduler och refresh-once. Lägg filen
under redan beständigt monterad datakatalog, exempelvis
`/srv/app/var/grocery/willys-municipal-config.json`. Tillägget väljer ingen
release-image, byter inga källor eller scheman och ersätter inte ICA-/Coop-paketen.

Ordinarie `run_daily_refresh` importerar inkommande artefakter under befintligt
operationslås, validerar och promoverar via SnapshotManager. Den vanliga
`_build_production_price_universe` läser godkända kommunbevis från aktiv OWN-snapshot.
OWN-provider hämtar endast motsvarande exakta butiks-ID/adress/kanal, även när
adressorten skiljer sig. Samma källa används vid efterföljande lokala rebuilds.
Publicering, reload och rollback använder befintliga rutiner.

En övergång från adressort får återanvända exakt samma råobservationer endast om
samtliga payloadhashar, tidsstämplar och källidentiteter samt parser/faktaversion
överensstämmer. Detta är omkvalificering, inte ny prisinsamling. Ändrade råpriser
med gamla tider avvisas. Ett äldre adressortsrelä får inte tyst ersätta ett
redan kommunstyrt aktivt underlag.

## Behovsstyrning och fel

Reläet kontrollerar prisålder lokalt: nästa hämtning efter 35 timmar, varning vid
36 och hårt stopp vid 48. `last-qualified-source.json` visar kvalificerad källa;
`last-success.json` visar separat bekräftad publicering och nästa hämtning.
Loggen behåller aktuell felstatus. Vid överföringsfel återanvänds giltig färdig
artefakt, utan nya observationstider. Dubbletter importeras idempotent.

Kommuninsamling förblir sekventiell vid 1 anrop/sekund. Anropsbudgeten är
`min(5900, 1000 * verifierade_onlinebutiker + 100)`, högst två timmars insamling
samt befintlig 256 MiB-gräns för källartefakten. Resursstopp är ofullständig
insamling, aldrig komplett kommunprisunderlag. Ingen daglig fullhämtning eller
ny schemaläggare införs. En lokal rebuild behöver inte hämta källorna igen.

Varken kommunregistret eller en lyckad insamling aktiverar priser i sig.
Före en skarp övergång behövs giltiga källor, rätt persistent konfiguration,
verifierat driftpaket och separat operatörsbeslut. Den väntande ICA-releasen
ska behålla sitt separata administratörs-/aktiveringssteg.
