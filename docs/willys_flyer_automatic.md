# Drift och avgränsning: Willys textannonser, regler v3

Ordinarie `collect_willys_flyers` använder `AutomaticWillysFlyerConnector`. Befintligt kommunval, officiell inventering, publicerade butiksreferenser, delvis godkända offers_only-rader, snapshots, OWN, PriceUniverse och kampanj-/behovsstyrd uppdatering återanvänds. Ingen ny schemaläggare eller prissättare har införts.

Ny dokumenthash kräver inte manuell normalrutin. `flyer_text.py` kvalificerar stödda textannonser med kontroll av sidtext, annons/prisposition, prisetikett, mängd, jämförpris, medlemskap, period och köpgräns. Okända eller tvetydiga fall har synliga skäl i `qualification.document_qualification.automatic_decisions` och `page_reports`. Ett lokalt fel stoppar raden/sidan; saknad period eller obekant dokumentstruktur stoppar dokumentet. Ett frivilligt källfel får behålla enbart fortfarande giltig godkänd källa enligt befintliga regler.

Tidigare dokumentbundna granskningar återanvänds endast när deras hash-, text-, pris- och butikskoppling fortfarande är verifierad. De behövs inte för den automatiska vägen och får inte kopieras till en ny PDF. Eventuella nya undantagsgranskningar ska fortsatt använda den befintliga exakta granskningsmodellen. Ingen flagga kan godkänna allt.

Kvalificeringsmetoden finns på varje dokumentannons. Produktidentiteten är ett dokument-/annons-/variant-ID, inte en GTIN eller ett retailer-SKU. Saknat ordinarie pris är okänt. Belagda enstyckskampanjer och hela styckflerköp använder den befintliga kontraktsberäkningen; ett obelagt restköp stoppas. Hushållskontraktets identitet normaliserar endast skiftläge, blanksteg och samma numeriska mängd, så att automatisk respektive äldre granskning inte skapar dubbla köpgränser.

36-/48-timmarsgränser, 35-timmarsuppdatering, kampanjdatum och verkliga observationstider är oförändrade. Ny kommuninsamling ändrar inga användarprofiler. Nya kampanjer och inventering hämtas från aktuella officiella länkar; inga veckospecifika produkt- eller PDF-listor styr automatiken.

Se [verifiering och kvarstående releasekontroller](../reports/willys-auto-20260924/README.md). Den 24 september fanns två verifierbara v39-dokument men ingen annan kampanjvecka eller tidigare ogranskad verklig utgåva. Det är en uttrycklig kvarvarande testbegränsning. Bildinnehåll har inte tolkats. Lidl och dess historiska testlucka är separata och oförändrade.

Regler v3 skiljer historiska referensprisintervall från förpackningsintervall, läser flerradiga rubriker och stödda uttryckliga variantalternativ samt bevarar fetthalt, lagringstid och skivning. Prisrutan begränsas till den lokala annonsraden, med fortsatt aritmetisk och entydig kopplingskontroll. Se [jämförbar täckning för båda kedjorna](../reports/offer-coverage-20260924/README.md). Den äldre Lidl-avgränsningen ovan beskriver föregående leverans.
