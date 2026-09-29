# Lidl kommunstöd: verifierat partiellt erbjudandetillskott

**Genomfört för Lund 1281 och Malmö 1280 med samma kod.** Officiell nationell inventering och gemensam kommungeometri hittar två respektive åtta butiker. Varje butik bidrar med tre kvalificerade aktuella erbjudanden: **6 Lund-poster och 24 Malmö-poster i OWN och publicerad privat PriceUniverse**. Ingen full Lidl-baspriskatalog påstås.

Den befintliga Lidl-parsern, collector, partiella radkontraktet, OWN, PriceUniverse, matcher, checkout/audit och ordinarie behovsrunner återanvänds. Kommunvalet är beständigt och styr återkommande uppdatering. Befintliga användarval/inköpsområden ändras inte. Fel i den frivilliga Lidl-källan stoppar inte fungerande baskällor.

- [Alla kommunbutiker, officiella källor, karantän och erbjudanden](STORES.md).
- [Ordinarie driftstart, andra rebuild, omstart, not-due, förfall, hämtfel och återhämtning](RUNTIME.md).
- [Tester, verkligt nät, replay och begränsningar](VALIDATION.md).
- [Separat Lidl-releaseunderlag](RELEASE-LIDL.md).
- [Konfiguration och kodväg](../../docs/lidl_municipality.md).

## Prisernas innebörd

Aktuellt officiellt nationellt blad gäller 21–27 september 2026. Exakt produktkoppling har granskats i dokumenttext för SOL&MAR Majssnacks ost & bacon 100 g, Culinea Hamburgare 1,8 kg och Pågen Lingongrova 500 g. En liknande benämning eller samma pris räcker inte. Resten av det regionala flödet har inte fått nationell giltighet.

Ordinarie köppris förblir null. Majssnacks har verifierat publikt variantpris 9,90 kr; dess frånpris i bladet innebär inte ett påstående om prissänkning. Hamburgare kostar 159 kr och Lingongrova 17,90 kr med allmänt Lidl Plus-medlemskap. Hamburgarnas högst två förpackningar per hushåll bevaras över butiker och recept. Personliga/aktiveringsberoende villkor går inte till gemensam köpimport.

20 representativa köp (två per fysisk butik) klarade matcher, checkout och audit. Pågens exakta GTIN/förpackning har separat leverantörsdeklaration och godkänd näringsprövning som såld. Korrekt köppris innebär inte att övriga produkter fått godkända näringsvärden eller får ersätta en annan receptingrediens. Ingen besparing påstås.

## Driftresultat och nästa uppdatering

Malmö: 24 Lidl-poster samt alla 13 523 oförändrade City Gross-basposter. Lund: 6 Lidl-poster samt alla 18 642 Willys-basposter i PriceUniverse. Första import/publicering/reload, återkommande rebuild, processomstart, lokalt not-due, förfall och injicerat hämtfel/återhämtning har körts i privata instanser. Alla lyckade serving-prov gav health/ready 200. Observationstider och priser behölls.

Nästa Lidl-källkontroll i de verifierade privata instanserna är **25 september cirka 04:28 Stockholm**, innan 36/48-timmarsgränserna. Butiksinventeringen kontrolleras igen 26 september. Ett nytt/ändrat reklamblad kräver ny produktbindning från text innan nya rader kan godkännas. Exakta tidsstämplar och övriga källors läge finns i RUNTIME.md.

Lunds gamla Willys-underlag är korrekt märkt över 36 timmar, ännu under 48 under provet; det separata reläets uppdatering är förfallen. Ingen observation föryngrades. Det är inte en full federerad Malmö-release med aktuell komplett bas.

## Verkliga återstående begränsningar

1. **Nästa kampanj:** den aktuella produktkopplingen är låst till granskad publikation/PDF-hash. Saknas strukturerad exakt produktjoin krävs ny dokumenttextgranskning. Obemannad import av ett nytt ogranskat blad är avsiktligt blockerad.
2. **Receptfakta:** hamburgare/snacks saknar här en kompatibel fullständig produktdeklaration. De har verifierade priser, inte allmän närings- eller receptbehörighet.
3. **Äldre regression:** ett oförändrat äldre Lidl-näringstest saknar sin historiska rapportfixture och kunde inte köras. Det räknas inte som grönt; nya fakta-/köptester är körda.
4. **Driftaktivering:** ingen produktionsaktivering har gjorts. En sådan kräver aktuella baskällor och separat normalt releasebeslut.

Följande är fortsatt **separata öppna uppgifter**, inte genomförda som sidoprojekt:

- Willys sju butiker med offentliga reklamblad men utan verifierad onlinekatalog: [bevarad butiksvis rapport](../citygross-municipality-20260923/WILLYS-GAPS.md).
- Fullständigt Malmö-publiceringsprov med aktuell komplett federerad bas.

Hashkontrollen bekräftar oförändrade kedjespecifika City Gross-/Willys-implementationer, tester och tidigare releaseunderlag samt ICA, Coop/X:-tra och Primat. Åtta gemensamma filer har avgränsade Lidl-tillägg och separata före-kopior/diffar. Ingen Windows-/schemaändring, bildanalys eller betald modell-API användes.
