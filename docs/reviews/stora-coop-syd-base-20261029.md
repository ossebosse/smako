# Coop Online Syd som baspriskälla för Stora Coop

Ägaren har uttryckligen beställt kopplingen 29 oktober 2026. Den ersätter
tidigare begränsning av denna källas användning för de tre angivna butikerna.
Priskällan, snapshoten och observationstiden behålls; det är inte ny
observation av respektive butiks hyllpris.

| Kommun | Officiellt butiks-ID | Butik | Ledger-ID |
| --- | --- | --- | --- |
| Lund 1281 | 2696 | Stora Coop Lund | 105760 |
| Malmö 1280 | 3850 | Coop Forum Jägersro | 105810 |
| Malmö 1280 | 3853 | Stora Coop Stadion | 105860 |

Jägersro heter Coop Forum i den officiella locatorn. Kopplingen använder
exakta ID:n, ledger-ID och det befintliga kommununderlaget. Den gäller
inte namnliknande, utanförliggande eller mindre Coop-/X:-tra-butiker.

Normal PriceUniverse-byggning hämtar redan kvalificerade ordinarie priser
från OWN:s frysta 730400-katalog. De tilldelas respektive fysisk köpkontext
och märks `Baspris från Coop Online Syd`. Befintliga fysiska kontext-ID:n,
användarval, egna kampanjer, köpgränser och datum består. Ett tomt
kampanjflöde får fortfarande använda den tilldelade baskällan.

Onlinekatalogens kampanjer/medlemspriser överförs inte till fysisk butik.
GTIN, förpackning, mängdklass, köpbegränsningar och faktaproveniens behålls.
Inga källtider förnyas och inga nya råsnapshots skapas för kopplingen.
Saknad/tvetydig baskälla eller ändrad destinationsidentitet stoppar bygget.

Malmös publiceringsfingeravtryck beror också på Syds aktiva snapshot.
Nästa validerade Syd-hämtning slår därför igenom i båda kommunernas
ordinarie lokala prisbyggen. Inga ytterligare källhämtningar eller timers
införs; befintlig tvånattspolicy och driftlås gäller.

Offlineprov använder riktiga sparade kommun-/locatorunderlag och separata
syntetiska prisexempel. Verklig aktivering och laddning dokumenteras separat.

Publiceringskontrollen upptäckte att samma råsnapshots gav samma universe-ID
före och efter den nya butikstilldelningen. Den ordinarie byggaren inkluderar
nu den explicita tilldelningspolicyn i sin befintliga source_strategy_version.
Det ändrar artefaktens identitet utan att skapa snapshot-ID eller observationer.
Båda byggcachens nycklar använder samma version; standardbyggen behåller sin
tidigare version. Versionsbyte och återanvändning provas separat.

Faktaläsaren följer det exakta produkt-ID:t `<käll-UUID>:stora-syd:<butiks-ID>`
till samma sparade Coop-produkt. Det kräver ägartilldelningsrollen, katalogkanal,
källbutik 730400, onlineursprung och identisk fysisk destination. Snapshot,
råprodukt-ID, dokumenthash och ordinarie faktaregler kontrolleras som tidigare.
Samma källa kan ge fakta till båda Malmöbutikerna utan en separat onlinekontext
som faktadonator. Saknad eller avvikande bindning förblir okänd. Pris,
observationstid och personliga beräkningsregler ändras inte av faktaprojektionen.
