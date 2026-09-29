# Samtliga blockerartyper och kvarstående beroenden

Prisgodkännande, köpform, variantval, näring och receptlämplighet är olika beslut. Radräkningarna i JSON-faciten är uttömmande för den identifierade nämnaren, inte ett bevis för att bildinnehåll saknas eller att 100 % är godkänt.

| Typ | Stöd i slutkoden | Fortsatt gräns / exakt saknat underlag |
|---|---|---|
| Belagd lösvikt och kr/kg | Planerad behovsvikt och uppskattad kostnad | Kr/kg som enbart är jämförpris bevisar inte försäljning i lösvikt. |
| Cirka-vikt på hel förpackning | Hela paket, källans cirka-vikt, samordnade rester, reservation om minimivikt | Faktisk uppvägd vikt saknas tills köp. Ingen fast paketkostnad eller uppmätt lagerstatus hävdas. |
| Verifierat viktintervall | Kontraktet kan bevara faktisk min/max separat från cirka-vikt | Variantintervall får inte användas som viktfördelning inom samma produkt. Osäker källa för intervallets innebörd stoppas. |
| Styckpris utan gramvikt | Belagt styckköp och komplett prisgrupp | Gramnäring kräver uppmätt/belagd mängd. Ett flerköpsrestpaket får inget påhittat pris. |
| Olika sorter | Källbelagd grupp, undantag, uttryckligt villkorat användarval | Exakt variant, ingredienser, allergener och näring saknas för öppen grupp. Ingen automatisk receptsubstitution. |
| Fasta storlekar för olika varianter | Bevarat variantintervall, ingen mittpunkt | En specifik variant kan endast automatväljas med belagd mängd och kampanjmedlemskap. Villkorat styckval kräver val av kampanjmärkt förpackning. |
| Blandade identifierade varianter | Käll-ID→OWN-ID-bindning, verifierad delmängd, gemensam gruppmotor | Saknat grupp-ID/medlemsbevis, olika pris/period/medlemsvillkor eller oklar överlappande gruppfördelning kan inte gissas. Verkliga öppna Willys-grupper blir inte identifierade blandgrupper av detta. |
| Hela flerköp utan ordinarie pris | Kompletta gruppköp; säker komplettering i entydig grupp | Inte ett fristående restpris. Grupp-rabatt som behöver ordinarie pris kräver detta underlag. |
| Gemensamma hushållstak | Befintligt priskontrakt och explicit gemensamt grupp-ID/tak över produkter, recept och butiker | Räckvidden måste finnas i källan. Godtyckligt likadana butikspriser skapar inte gemensam kampanj. |
| Pant | Separat varupris/pant; okänd pant ger ofullständig köpstatus | Förpackningsspecifikt pantbelopp och om grupppriset inkluderar pant måste vara belagda. |
| Webbläsarvisare mot PDF | Befintlig jämförelse och felisolering bevarad | Verklig text-/revisionskonflikt behöver officiell rättelse eller entydigt revisionsunderlag. Lägsta pris väljs inte. |
| Prisruta, sidvillkor och flera mängder | Generell geometrisk pris-/textbindning och full villkorsgrammatik | Flera möjliga prisrutor, sammanslagna varumärken eller oklart lokalt undantag stoppas. |
| Okänd text | Igenkända beskrivningar kan passera generella regler | Okänd kritisk köpbegränsning får inte behandlas som dekoration. |
| Nationellt/regionalt/butik | Befintlig dokument- och butikskoppling | Regional datumgiltighet eller ett liknande produktnamn är inte fysiskt butiksbevis. |
| Pris utan GTIN | Entydig dokument-/produktbindning kan användas | Källans stabila produkt-ID är inte GTIN. Faktaöverföring kräver kontrollerad identitet. |
| Produktdeklaration | Arla och tidigare Garant-importer, exakt identitet/variant, spårbar källa | Annan fetthalt, viktvariant, sammansättning eller öppna sorter får inte låna deklarationen. |
| Generisk SLV-referens | Befintlig opt-in, spårbar version, uppmätta ätbara gram | Saknad ätbar andel, rå/tillagad konvertering, ml→g eller styckvikt måste kompletteras; inget antas. |
| Sammansatt mat/recept | Separata semantiska och näringsmässiga spärrar | Nuggets är inte vanlig kyckling; benhaltiga delar är inte gram rent kött; valfri pizza är inte en specifikt deklarerad pizza. |
| Framtida/utgångna priser | Datum behålls, får inte användas utanför belagd period | Nya kampanjer behöver egna källbevis. Gamla manuella godkännanden ärvs inte. |
| Omstart/rebuild | Kontrakt och kvalitetsstatus serialiseras; nya defaults ändrar inte gamla artefakters hash | Nya prisobservationer får endast komma från verklig hämtning. |

## Willys – kvarvarande automatiska beslut

Hemma: 23 av 34 annonser kvalificerade. Övriga 11: variant/mängd 2, okänd närliggande prisruta 2, flera förpackningsmängder 1, textstruktur 2, `Delad 19:90 kr/kg` 2, oklar enhet för köpgräns 1, duplicerad annons 1. Manuella dokumentbundna varianter redovisas separat i facit; dessa grupper får inte summeras till nya priser utan deduplicering.

Tolvsidigt: 75 av 112 kvalificerade. Övriga 37: visare/PDF skiljer sig 8, pris–textrelation inte entydig 8, variant/mängd 6, okänd prisruta 2, textstruktur 2, `Delad` 2, enhet för köpgräns 1, flera mängder 1, `Från` 2 samt fem övriga ej säkert separerade villkors-/produkttexter (två sammanslagna varumärkesgrupper, `GARANT EKO`, `4x125g`, `OLW`). Exakt annons, sida, text och beslut finns i `willys-denominator.json`.

Dessa kvarvarande textfall kräver fortsatt granskning eller ytterligare säkert tolkningsstöd. Kända ord är inte i sig bevis för vilken produkt, prisruta eller vilket undantag de tillhör. Annonsräkningen omfattar identifierbara textannonser; okänt innehåll som enbart finns i bilder är inte kvantifierat som noll.

## Lidl – kvarvarande automatiska beslut

380 unika käll-ID: 28 kvalificerade, 350 utan tillräcklig produkt–kampanj-/butiksbindning, 2 parserkarantäner. Den äldre etiketten som inkluderade parserfel i bindningsbortfallet används inte som ett nytt oberoende antal. Alla käll-ID och datum-/livsmedelsklassningar finns kvar i `lidl-denominator.json`.

Parserkarantäner: laddkabel `11070013` med ej stödd villkorstext (icke-livsmedel) och nöt-/kalkonsalami `11209435` med otillräckligt förenlig jämförpris-/mängdintervallinformation. Ett medelvärde eller godtycklig variant skulle inte lösa salamins identitet/prisrelation.

## Öppna release-/bevisuppgifter

* Ny oberoende, tidigare ogranskad verklig kampanjutgåva har inte verifierats. Återspelnings- och syntetiska tester räcker inte som ersättning.
* `backend/tests/test_reviewed_lidl_nutrition.py` saknar historiska `reports/source-implementation-20260915/lidl_offer_adapter.py`. Skyddet gäller bland annat exakt GTIN-/deklarationsversion och förpackningskedja, avvisning av närliggande variant, att ny kampanj/snapshot inte ärver granskning samt rå kycklinglårfilé i rätt dokumenterad tillagning. Nya tester verifierar nuvarande deklarations-/grupp-/enhets-/allergispärrar men återställer inte automatiskt dessa historiska fixturprov. Testluckan står kvar, utanför antalet passerade tester.
* Aktuell publicering kräver nytt komplett och tillräckligt färskt basunderlag. Historisk testklocka gör inte dagens bas färsk.
* Fullständigt Malmö-publiceringsprov med aktuell komplett bas är fortfarande separat integrationskontroll. Det isolerade kommun-/driftprovet i denna etapp ersätter inte den kontrollen.
