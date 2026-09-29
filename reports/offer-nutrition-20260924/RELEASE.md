# Isolerat releaseunderlag – pris och näring 2026-09-24

**Ingen produktionsaktivering. Totalmålet 100 procent är inte uppnått.** Detta underlag kompletterar och ersätter inte tidigare kedjors releaseunderlag.

Ändrad produktionskod i detta steg:

- Willys `flyer_text.py`, `flyer_offers.py`: text-/priskoppling, tydliga varianter och deduplicering.
- Lidl `document_qualification.py`, `municipal_offers.py`: exakt bindning, dagsperiod, förpackning, hushållsgräns och avrunnen mängd.
- `product_matcher.py`: exakt begärd kvalificerad helprodukt, med oförändrad generisk receptisolering.
- `nutrition_reference.py`, `personal_nutrition.py`, `slv-20260924.json`: spårbara generiska referenser och avgränsad uppvägd rå beredning.
- `lidl_product_facts.py`: återanvändning av exakt leverantörsdeklaration utan att ärva kampanjgodkännande.

`PACKAGE.json` innehåller slutkodens hashvärden, före/efter, oförändrade råkällor och verifieringsfiler. `baseline-code/` innehåller kopior från före steget. Två ytterligare baseline-filer för matcher/beredning rekonstruerades från de lästa filerna genom att endast ta bort detta stegs tillägg; de är inte jämförda mot git HEAD, som föregår tidigare användararbete.

Verifierat:

- 427 berörda tester, inga fel eller skip; Ruff för ändrad kod.
- Samtliga godkända poster genom collector, OWN och två isolerade PU-byggen för Lund/Malmö.
- 431 livsmedelsköp genom matcher, checkout och audit; sju befintliga växtposter avvisas som livsmedel.
- Alla 438 prisrader spärras före start/efter slut utan observationstidsändring.
- Verklig begränsad hämtning separerad från slutkodens replay, testklocka och felinjektion.
- Ordinarie runner/appstart, publicering/reload, omstart och not_due. Slutkodens fel-/återhämtningsbyggen har samma pris- och bassignatur. Första/andra/restart på mellanliggande kod märks uttryckligen i ACCEPTANCE.
- Lidl har ett ytterligare ordinarie fel-/återhämtningsprov med ny faktiskt insamlad capture och oförändrade observationer.

Kända begränsningar/releasekontroller:

- Willys får fler automatiska godkännanden men ännu inget nettotillskott av unika priser i samma dokument.
- Endast en mindre del av hela Lidl-flödet har belagd nationell produktbindning. Full nämnare och alla beslut sparas.
- Näringsreferens är inte produktdeklaration eller automatiskt godkänt tillagat recept. Saknad näring tar inte bort prisposten.
- Tillgängliga tillverkarkällor behöver ytterligare exakt deklarationskoppling; fortsatt kodarbete återstår.
- Verklig v40-regression har redan tidigare granskats; oberoende helt ogranskad ny kampanjvecka är inte bevisad.
- Historisk Lidl-fixture saknas fortfarande. Motsvarande hela gamla ost-/lårfiléskydd är inte verifierat.
- Komplett Malmö-publiceringsprov med aktuell fullständig bas är separat och öppet. Isolerad City Gross-bas var 32,23 timmar vid kontroll; se `base-freshness.json` för absoluta gränser. En framtida publicering kräver ny färskhetskontroll.

Ingen ändring av kommuninventeringens geometri, användares butiksval, Windows-uppgift, aktiva scheman, Primat eller övriga kedjors implementation ingår i detta steg. Ingen ny prissättare eller parallell refreshmekanism har införts.
