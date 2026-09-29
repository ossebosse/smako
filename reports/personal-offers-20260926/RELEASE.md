# Inaktivt aktiveringsunderlag – PersonalPlanner, 26 september 2026

Ingen produktionsaktivering har skett. Ingen Windows-uppgift, aktivt schema,
kommuninventering, produktdatabas, prisobservation eller sparad användarprofil ändrades.

## Leverans

Fryst jämförelse: `baseline-code/baseline.json` och oförändrade rå-/artifactreferenser
från föregående leverans. Ändringar: `PlanRequest.allowed_store_ids`, gemensam
klassificeringsprojektion från entydigt bunden deklaration, prisupptäckt oberoende
av näringsfakta i uppskattningsläge, avgränsad verklig produkt-/receptsökdiagnostik,
förklaringar av rate-kontrakt samt sparad checkout/audit. Ingen ny prismotor.

`allowed_store_ids` är frivilligt, planbundet och endast tillåtet med PersonalPlanning.
Tomt/utelämnat bevarar tidigare område. Okända/inaktuella kontexter, tomma ID och
dubbletter avvisas. Valet ingår i sparad request/cacheidentitet och ändrar inte
kommuninsamling eller kontoprofil. Jämförda kontexter i svaret respekterar valet.

Matbröd-regeln är en dokumenterad livsmedelsklass från Dabas klassificeringsfält,
inte ett namn-, varumärkes- eller kampanjundantag. Identitetsadaptern återkontrollerar
GTIN/variant/förpackning och källdeklaration. Priser/villkor kommer fortfarande från
butikens erbjudande. Sammansatta/öppna varianter är inte automatiskt näringsgodkända.

## Verifierade bevis

Läs genererade `VERIFICATION.md`, `profile-summary.json` och råa JSON i `profile/`.
De fria profilerna använder samma kompletta bas, köpdag och receptpool; den separata
Plus-kopian ändrar bara medlemskap. HTTP-provet använder ett normalt kallt
bröd-/ostrecept, ett uttryckligt officiellt Lidl-butikskontextval och Lidl Plus
för brödet. Arla-osten är offentligt prissatt. Det är en måltid, inget extraköp.

Observera att HTTP-föreversionen saknar detta butiksväljarfält och ignorerar det.
Dess Coop-kostnad är därför inte en ekonomiskt jämförbar Lidl-baslinje. Det
avgränsade provet bevisar efterversionens faktiska måltids-/inköpskedja och
sparning/återläsning efter separat backendprocessomstart.

Pris-/näringsnätanrop: noll. Native körmiljö: befintlig kandidatimage,
uid 10001, privat arbetsdatabas, readonly kod, två CPU, fem GiB, nätverk avstängt,
HTTP bara på containerns loopback. Inga publicerade portar eller produktionsfiler skrivs.
Tidigare HTTP-livscykelprov och mellanresultat finns separat; slutbeviset kräver
`profile/http-after-integration.json` med `process_restarted: true`.

## Före eventuell senare aktivering

- Verifiera PACKAGE-hashar och tidigare kedjereleasers beroenden; använd denna
  arbetskopias fulla bevarade paket, inte en återställning till ren Git-bas.
- Skaffa färsk komplett godkänd bas via befintlig behovsstyrd drift. Historiska
  källor får inte föryngras eller publiceras som aktuella. 36/48 h är oförändrat.
- Det separata kompletta Malmö-publiceringsprovet återstår. Ingen ny inventerings-
  eller refreshmekanism behövs i detta steg.
- Den historiska Lidl-fixturen `lidl_offer_adapter.py` är fortfarande saknad;
  dess ursprungliga skydd räknas inte som verifierat av denna leverans.
- Ny tidigare ogranskad verklig kampanjutgåva ingår inte i detta replayprov.
- Behåll övriga deklarations-/berednings-/allergispärrar. Gouda saknar tillämpligt
  näringsunderlag; genererade varma recept behöver en dokumenterad beredningsmodell.

Fria sökningen är begränsad, inte ett globalt optimalitetsbevis. Avgränsad diagnostik
får inte översättas till ”dyrare” utan en godkänd komplett korgjämförelse.
Återgång sker till bevarat föregående paket; denna etapp kräver ingen databas-
eller schemamigrering och inga produktionssteg har genomförts.
