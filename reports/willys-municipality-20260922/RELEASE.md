# Separat releaseunderlag: Willys kommunläge

**Ingen aktivering i denna körning.** Tillägget är explicit och återanvänder befintlig Willys-transport, OWN, prisavtal, PriceUniverse och ordinarie publicering/reload. Ingen ny schemaläggare eller prissättare.

**Beslutsstatus 23 september cirka 08:08:** kod och dokumenterade tester är
verifierade, men det sparade federerade Lund-testunderlaget är inte färdigt att
återaktiveras: en baskälla har passerat stoppet 03:17:55 samma dag.
Willys-underlagen är fortfarande giltiga vid kontrollen. Uppdatera/validera förfallen
bas och rollbackunderlag inför ett separat aktiveringsbeslut; återanvänd inte
gårdagens gröna källålder. Malmö har verifierad Willys-import/ombyggnad men saknar
ett komplett federerat publicerings-/reloadprov med aktuell Malmö-bas.

## Verifierat innehåll

- Kommunbaserat urval från hela officiella registret och SCB RegSO 2025, samma kod för 1281/1280; inga fasta butikslistor i kommunläget.
- Fullständighets- och identitetskontroll i källartefaktens mottagare. Alla verifierade onlinebutiker måste ingå; partiell katalog marknadsförs inte som komplett.
- Persistenta kommuninställningar och godkända källreferenser, scope-säker och idempotent import, oförändrade observationstider och separat publiceringskvittens.
- Ordinarie privata Lund-rebuilds/publicering/reload och omstart med identiska 18 642 Willys-poster, oförändrade villkor och bevarade 493 Coop-tillägg. `health`/`ready` 200.
- Färsk verklig Malmöinsamling av fyra kompletta onlinekataloger, 39 274 butik–produktposter. Resultaten av import/ombyggnad efter omstart finns i README och `server-results/`.
- Noll prisanrop vid ej förfallet arbete, 35-timmarsbehovsstyrning, 36-timmarsvarning och 48-timmarsstopp. Förfallna avtal behåller befintligt checkoutskydd.
- 180 berörda regressioner godkända; Ruff/compileall. Paketerad appkod hashjämförd, inga monterade utvecklarbibliotek.

## Avgränsningar och kvarvarande kontroller

1. **Priskanal:** enbart butiksknuten online_price för källans verifierade onlinebutiker. Sju andra verifierade kommunbutiker saknar fysisk priskälla i denna väg. De tas inte bort ur täckningsrapporten och får inte kopierade priser.
2. **Malmös federerade driftprov:** kommuninventering, faktisk Willys-insamling, OWN och den vanliga produktionsbyggaren provas med samma kod. En aktuell komplett Malmö-Primatbas och ett fullständigt ordinarie Malmö-publicerings-/reloadprov är inte levererade i denna etapp. Ingen Lund-bas eller begränsad sökprojektion ersätter dem.
3. **Färskhet inför beslut:** källunderlaget måste fortfarande valideras vid faktisk aktivering. Lunds Willys-observation börjar 21 september 23:31:24Z; Malmö 22 september 16:18:30Z. De har olika förfallotider. Äldsta bevarade federerade Lund-basobservation är 21 september 01:17:55Z, med hårt stopp **23 september 03:17:55 Europe/Stockholm**. Den behöver förfallen normal uppdatering före en senare aktivering; ingen tillåtelse att förlänga gränsen ges.
4. **Rollback:** bevara skarp databas, konfiguration, kompatibel image och manifest före separat aktivering. Verifiera artefakthash, scope, prisålder och kampanjgiltighet vid rollback. Ett gammalt adressortsrelä får inte ersätta aktivt kommununderlag tyst. Föredra kompatibel föregående kommunartefakt; återgång till adressort kräver uttryckligt separat scopebeslut och färskt passande underlag. Gamla eller felaktigt daterade priser får inte återaktiveras.
5. Registerrad 2002 är fortsatt okänd; full fysisk inventerings-/pristäckning påstås inte. City Gross/Lidl har separat status och blockerar inte det verifierade Willys-tillägget.

## Operatörssteg efter separat beslut

Välj den verifierade kompatibla imagen och säkerställ samma versionsuppsättning i app/refresh-process. Lägg kommunens byggomfattning i persistent `WILLYS_MUNICIPAL_CONFIG` och reläets kommunval i en separat beständig reläkatalog. Exempelformat och exakt insamlingskommando finns i `../../docs/willys_municipality.md`; `../../deploy/willys-municipality.override.yaml` förmedlar bara den nya konfigurationssökvägen och är inte applicerad.

Kontrollera källornas färskhet och fullständighet, då gällande kommunbevis samt giltigt rollbackunderlag. Leverera därefter genom befintlig källinbox och ordinarie låsta refresh/publicering/reload. Kontrollera faktiskt aktivt manifest och exakt butik/kanal, inte bara en kandidatfil eller HTTP 200. Denna uppgift utför inte dessa skarpa steg.

Nästa beräknade Willys-hämtning enligt källobservation +35 h: **Lund 23 september 12:31**, **Malmö 24 september 05:18** (Europe/Stockholm). Det är den förberedda policyn, inte installerade produktionskörningar. Tidigare allmänna basförfall och kampanjutgångar gäller oberoende av dessa tider. Vid hämt-/överföringsfel syns felet separat; endast fortfarande giltigt godkänt underlag får användas. En ny ombyggnad föryngrar inte källan.

Behåll väntande ICA-aktivering, Coop-/X:-tra-paket, Primat, användarval och aktuella scheman separata. Ingen kostnadsbesparing eller flerdagarsstabilitet påstås av denna kontroll.
