# Kvarstående riktat källunderlag

Restlista efter genomförda rättningar. Detaljerad [JSON](RESEARCH.json) innehåller alla berörda receptversioner, råvaruformer, fält, mängdbaser, produkt-/butiks-/kanal-/snapshotreferenser, kontrollerade källor och övriga ingredienshinder. Den fullständiga kvalificeringen ligger i hashbundna råfiler utanför Git.

Prioriteten väger återanvändning mellan grundrätter, möjlig effekt och insats. Antal berörda grundrätter är inte ett löfte om lika många räddade rätter.

## Milda/medelstarka torra chiliflingor

Prioritet 1: 10 versioner, 5 unika grundrätter.

Kockens Chili Jalapeño Flakes 26 g, GTIN 7350046464858: komplett deklaration per 100 g torr produkt. Tillverkaren styrker medelstyrka och ren chili men saknar näring. Rätt styrka måste nå befintlig variantbunden faktaväg. `content_pack_requirements.compatible` behöver också använda det källbundna styrkeunderlaget; en ensam näringsrad tar inte bort denna separata spärr.

28 g-raden har citronpepparuppgifter som motsäger chilinamnet. Låna inte dem. SLV 380 är färsk chili. TH01 behöver även jordnötter; exakt köp kan dessutom stoppas av vitkål.

Berörda versioner: IN01-base, IN01-vita-bonor, TH01-base, TH01-tofu, TH02-base, TH02-kyckling, TH03-base, TH03-tofu, TH04-base, TH04-kyckling.

## Kokt, avrunnen majs

Prioritet 2: 6 versioner, 3 unika grundrätter.

Produktblad för en faktiskt prissatt variant, exempelvis Coop GTIN 7340191149557, med total nettovikt, avrunnen vikt per burk, antal burkar och uttrycklig näringsbasis för avrunna korn.

165 g/3-pack är inte en säker multiplikation. Jämförpriset bevisar inte avrunnen vikt. Fryst majs är annan form. MX02/MX04 behöver även rökt paprikapulver.

Berörda versioner: MX01-base, MX01-vita-bonor, MX02-base, MX02-tofu, MX04-base, MX04-fars.

## Rent, torrt och malt rökt paprikapulver

Prioritet 2: 4 versioner, 2 unika grundrätter.

Styrk pulverform och näring för Kockens Paprika Rökt 36 g, GTIN 7350046465299, eller Santa Maria Paprika Smoked 37 g, GTIN 7311311015243. De finns i bredare paprikaunderlag men nås inte av nuvarande snäva ingrediensuppslag.

Här återstår både en matchningslucka och form-/faktaprövning. Alias får bara förbättra hämtningen och aldrig ersätta formkontrollen. MX02/MX04 är fortfarande stoppade av majs även efter en sådan rättning.

Berörda versioner: MX02-base, MX02-tofu, MX04-base, MX04-fars.

## Färdigbakat pitabröd, som sålt

Prioritet 3: 2 versioner, 1 unik grundrätt.

Bind tillverkarens uppgift om färdigbakat bröd till Schysst Käk 350 g/5-pack, GTIN 7350090451125. Ett exakt produktblad eller en läsbar märkning räcker om övriga fakta är förenliga.

Familjesidan om stenugnsbakning identifierar inte förpackningen. Exakt Dabas-länk gav 404. Hatting/Eldorado kräver egen formprövning. Tillåt uppvärmning men inte att rå deg betraktas som färdigbakat bröd.

Berörda versioner: GR01-base, GR01-brostfile.

## Naturell mjölk; receptet använder gram

Prioritet 4: 2 versioner, 1 unik grundrätt.

Samma produkts nettomassa och volym eller styrkt produktspecifik densitet samt förenlig näringsbasis. Per 100 ml räcker inte för receptgram.

Ingen generell ml=g-regel införs. SE01-varianterna behöver dessutom ätbar äggvikt. Värden med fel mängdbasis är fortfarande otillräckliga även om de är numeriska.

Berörda versioner: SE01-base, SE01-svamp.

## Rått helt ägg utan skal, receptmängd i gram

Prioritet 4: 2 versioner, 1 unik grundrätt.

Produktspecifik ätbar gramvikt per styck/förpackning, eller dokumenterad tillåten uppskattning av ätbar andel med osäkerhet. Storleksklass och antal styrker inte gram utan skal.

Identitetsmatchningen är rättad. Sex skaläggskandidater når mängdspärren st/g. Näringsdeklaration per 100 g räcker inte för köpbar mängd. SE01 har dessutom ett separat mjölkstopp.

Berörda versioner: SE01-base, SE01-svamp.

## Rostade, osaltade och ätfärdiga jordnötter

Prioritet 5: 2 versioner, 1 unik grundrätt.

Komplett deklaration för de två kandidater som faktiskt klarar formkravet, alternativt direkt tillämplig officiell generisk referens med befintligt medgivande.

Råa, saltade och smaksatta nötter är andra former. TH01 har samtidigt ett chilistopp. Kandidatidentiteter, befintliga värden och källor finns i JSON.

Berörda versioner: TH01-base, TH01-tofu.

## Kokt och avrunnen tonfisk i vatten

Prioritet 5: 1 version, 1 unik grundrätt.

Exakt leverantörsblad för en bevarad vattenvariant, med avrunnen massa och näringsvärden uttryckligen för avrunnen fisk.

Bruttovikt eller oljeförpackad tonfisk kan inte överföras. Fisk måste vara tillåten av användaren. Tofuvariationen är redan kvalificerad.

Berörda versioner: IT03-base.

## Färsk ätlig vitkål i exakt köpläge

Prioritet 6: 22 versioner, 11 unika grundrätter.

Verifierad fast förpackningsmassa eller verifierat lösviktskontrakt på samma tillåtna prisunderlag.

Ungefärlig vikt blir inte exakt av bättre näring. Flera av de berörda recepten har andra oberoende stopp; se versionernas listor i JSON.

Berörda versioner: GR01-base, GR01-brostfile, IN02-base, IN02-tofu, IT02-base, IT02-bonor-linser, IT04-base, IT04-bonkram, MX01-base, MX01-vita-bonor, MX02-base, MX02-tofu, MX04-base, MX04-fars, SE01-base, SE01-svamp, SE04-base, SE04-tofu, TH01-base, TH01-tofu, TH03-base, TH03-tofu.

## Färskt äpple med skal i exakt köpläge

Prioritet 6: 2 versioner, 1 unik grundrätt.

Verifierad köpbar och användbar gramvikt för rätt fruktprodukt: fast vikt eller styrkt lösvikt, med nödvändig hantering av oätliga delar.

Generisk SLV 588-näring är redan importerad. Upprepa inte den researchen. SE04 fungerar med uppskattade köp; styckpris eller ungefärlig fruktvikt bevisar inte ett exakt köp.

Berörda versioner: SE04-base, SE04-tofu.

Källa, hämtningstid, råhash, variantidentitet och den styrkta uppgiften ska registreras i befintliga faktavägar. Prisobservationer får inte föryngras. Generiska referenser får varken bevisa allergensäkerhet, ersätta en märkesdeklaration eller tysta en källkonflikt. Mängd, köpstatus, näring och användarvillkor prövas separat.
