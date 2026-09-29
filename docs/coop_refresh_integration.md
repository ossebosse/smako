# Kommunala Coop-källor i ordinarie refresh

Avstängd som standard. Ingen scheduler installeras och inga användarområden
eller butikspreferenser ändras. Coop Online 730400, Primat och ICA har kvar
sina egna källor och regler. X:-tra är ett separat valfritt tillskott.

## Befintlig startväg

`deploy/scripts/run_daily_refresh.py` äger operationslåset och startar den
vanliga `python -m grocery_data daily-refresh`. Den kör det kommunala jobbet
före produktionsbyggaren. Varje senare build, även med enbart basuppdatering,
läser samma godkända beständiga källreferenser. Normal OWN-projektion,
PriceUniverse-validering, atomisk publicering och admin-reload återanvänds.
Inga särskilda Coop-byggargument behövs i jobbet.

## Inställningar vid ett separat aktiveringsbeslut

| Inställning | Betydelse |
|---|---|
| `COOP_MUNICIPAL_OFFERS_ENABLED=true` | Tillåt det kommunala tillägget; annars avstängt. |
| `COOP_MUNICIPALITY_CODE` | Officiell kommunkod, exempelvis `1281`. Inga inbyggda butikslistor. |
| `COOP_MUNICIPAL_BUILD_CITY` | Vilket befintligt city-build som får tillskottet. Följer annars `REFRESH_CITY` eller kommunnamnet. Ändrar inga användarval. |
| `COOP_MUNICIPAL_OFFERS_ROOT` | Beständig katalog; standard bredvid ordinarie SQLite-databas under `coop-municipal-offers`. |
| `COOP_XTRA_OFFERS_ENABLED=true` | Separat opt-in för verifierad PDF-text från respektive officiell butikssida. Ingen bildanalys. |
| `COOP_MUNICIPAL_INVENTORY` | Valfri initial verifierad inventering. Kopieras in i tillståndet och behövs inte efter bootstrap. Annars används befintlig discovery. |
| `DEMAND_REFRESH_ENABLED=true` | Befintlig lätt förfallokontroll, med samma befintliga startväg. Installation/ändring av dess tick är ett separat operatörsbeslut. |

Kommunval, aktiveringsinställningar och city-bindning sparas atomiskt i
`<root>/config.json`. Uttryckliga miljövärden har företräde och sparas vid
jobbkörning. Under `<root>/<kommunkod>/source-state.json` finns inventeringen,
samtliga butikars status, schemapolicy, godkända snapshotreferenser, senaste
byggkvitto och publicerings-/reloadstatus. `attempts/` innehåller oföränderliga
befintliga OWN-databaser och råbevis. Referenser är relativa till beständig root
och hashkontrolleras före import. Separata butiker kan peka på olika lyckade
insamlingar. Ingenting läses från en tillfällig utvecklardatabas i drift.

## Fel, utgång och återförsök

- Enbart lokal förfallokontroll gör inga externa prisanrop. Fortfarande giltiga
  godkända källor behöver inte hämtas om vid rebuild.
- Kampanjgränser och 35-timmarskontroll återanvänder befintlig policy. Varning
  vid 36 timmar och stopp vid 48 timmar behålls. Datum och medlems-/köpvillkor
  kontrolleras också i befintlig pris-/checkoutlogik.
- Misslyckad hämtning behåller referensen till tidigare godkänt underlag;
  den förlänger aldrig observation eller giltighet. Första källretry efter
  15 minuter, därefter begränsad exponentiell backoff till sex timmar.
- Ett validerat svar utan kvalificerade rader tar bort tidigare godkända
  referenser för just den butiken. Schemafel, saknad kritisk butikskoppling
  eller ofullständig PDF-layout är inte bekräftat tomma flöden.
- Inventering kontrolleras normalt efter 72 timmar; misslyckad inventering
  ger ny kontroll efter 15 minuter. Ändrad källidentitet förlorar sin gamla
  källreferens; osäkra kommunbutiker kan inte ärva ett tidigare pris.
- Hämtning, källgodkännande, diskpublicering och reload har olika tidsfält.
  Lyckad insamling kvitterar aldrig en misslyckad publicering. Reload måste
  ange byggkvittots exakta PU-ID. Ett misslyckat reload försöks igen efter
  15 minuter även om Coop-priserna inte ändrats vid en basrebuild.
- Korrupt eller otillgängligt frivilligt underlag utesluts med felstatus.
  Den giltiga basen används fortfarande. X:-tra-fel påverkar inte andra
  kommunbutikers godkända källreferenser.

## Operatörsgräns och rollback

Paketet kräver befintlig browsertransport med Playwright/Chromium och de
versionsbundna beroendena i `grocery_data/requirements-coop-candidate.txt`.
Körkontot behöver skrivåtkomst till den beständiga rooten och befintligt
operationslås. Appen behöver kunna läsa samma PriceUniverse-volym och ta
emot den befintliga skyddade reload-begäran.

Aktivering kräver ett separat beslut om image, flaggor, volymer och befintlig
tick. Denna leverans ändrar inga aktiva scheman eller Windows-uppgifter.
`deploy/coop-runtime.override.yaml` är ett separat, ännu inte tillämpat
Compose-tillägg. Det väljer den verifierade förbyggda imagen och tar bort
kandidatbildens insamlings-entrypoint så att de befintliga app-, scheduler-
och refresh-kommandona startar som avsett. Det ersätter inte den väntande
ICA-konfigurationen. Använd `--no-build` efter ett separat beslut; bygg inte
oavsiktligt om den gamla standardimagen från bas-Compose-filen.
Rollback ska använda befintlig kodkompatibel artefakt som fortfarande klarar
källfärskhet och köpdatum. En avstängning av X:-tra eller hela tillskottet
utlöser lokal rebuild; godkända källfiler bevaras för spårbarhet. Gammal
källa får inte återaktiveras genom att observationstider skrivs om.
