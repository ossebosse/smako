# Coop: näringskoppling och körbart driftpaket

Verifierat 22 september 2026 i den separata arbetskopian `areas/municipality-audit-20260920`. **Redo för separat, tidsbunden aktiveringsprövning av den partiella kandidaten. Ingenting aktiverat.** Beslut och återstående kontroller: [RELEASE-COOP.md](RELEASE-COOP.md).

| Mått | Före rättning | Efter rättning |
|---|---:|---:|
| Importerade fysiska butik–variantposter | 493 | 493 |
| Faktiskt näringsprövade Coop-rader i 15/20 | 22 | 22 |
| Näringsgodkända i dessa receptförsök | 0 | 14 |
| Kvarstående spärrade bland de 22 | 22 | 8 |
| Valda fysiska Coop-erbjudanden i vinnande meny | 0 | 0 |
| Total A / B | 536,27 / 536,27 kr | 536,27 / 536,27 kr |

Tio ostrader använder befintliga produktdeklarationer, fyra tomatrader använder den befintliga uttryckligt tillåtna uppskattningsreferensen SLV 364. [Samtliga 22 före/efter](22-POSTER.md) med butiks- och källpost-ID. Sju olika källvarianter, fem produktnamn; samma variant i flera butiker utreds inte som flera oberoende näringsprodukter.

Rättningen binder fakta via exakt Coop-identifierare + namn + varumärke + förpackning + samtidiga observationer. Katalogens uttryckliga EAN är belägg för faktagivaren; erbjudandets opaka externalId blir inte automatiskt GTIN. Pris, butik, kampanj och observationstid flyttas inte. Motstridiga givare spärras. Cacheversionen omfattar nu även mottagarens identitet och förpackning. Tomatens singularform/ordföljd återanvänder befintlig referens med oförändrad opt-in. `LESS_THAN` behålls som gränsuppgift, inte ett exakt näringsvärde. Ingen ny extern näringsinsamling behövdes för de relevanta produkterna.

265 av de 493 raderna får en exakt faktalänk genom samma generella modell; 264 har någon deklarerad näringsuppgift. Detta betyder **inte** att 264 är godkända för alla recept/näringskrav. Slutmåttet i den faktiska profilen är 14 av 22 prövade.

## Från 493 till 22

Alla 493 finns kvar i OWN och B:s PriceUniverse. Inget importbortfall döljs av recepturvalet.

| Observerat steg | Rader | Förklaring |
|---|---:|---|
| OWN → isolerat PriceUniverse | 493 | Samma nio kommunbutiker; 1 937 karantänposter separat |
| Matchning mot ekonomisk ingredienstaxonomi | 105 | 388 saknar matchning här; bl.a. andra varor/ingredienser än denna pool |
| Semantisk pool | 101 | Fyra tidigare matchningar underkänns: två Bratwurst, Pulled Pork och Falukorv |
| Begränsad ekonomisk kandidatpool | 93 | Åtta korvvarianter väljs bort i ekonomiskt urval; den bredare indexeringen bevaras |
| Faktisk ingrediens-/näringsprövning för oförändrade recept | 22 | 71 av poolens 93 når inte denna prövning, se nedan |
| Produktbundet näringsunderlag kvalificerat för försöken | 14 | Tio ostar + fyra tomater |

Detta är mätpunkter, inte en destruktiv raderingskedja: planerarens faktaläge kan återanvända den bredare matchningsindexeringen före ekonomisk beskärning. För de 71 som inte prövas: 27 saknar berättigat köppris med medlemskap av (Ost Rike 9, Falukorv Ring 8, Nötfärs 8, Morötter 2); 10 har låg produktsemantik (Philadelphia Västerbottensost 9, Kyckling Tex mex 1); återstående 34 når inte upplöst ingrediensval i de faktiska receptförsöken. Deras poolkopplingar gäller vitlök/paprika/korv/gul lök/crème fraiche. Receptprövningen stoppar 84 av de 106 rårecepten på befintligt krav på granskad beredning. Tidiga namnträffar såsom vitlökssmak på Philadelphia är inte ett bevis för att färskosten kan ersätta vitlök. Vi har inte breddat dessa recept-/semantikregler eller räknat detta urval som 71 näringsdatabristfall. Detaljer: `server-results/candidate-diagnostics.json`, tidigare `product-qualification.json` och slutkörningens kandidatdiagnostik.

De verkliga integrationsfelen bland de 22 var utebliven faktalänk för de tio ostraderna och utebliven tomatalias för fyra rader. Färsk fettuccine är fortsatt oförenlig med receptens torra durumvetepasta och saknar dessutom kvalificerad deklaration i det granskade faktaunderlaget.

## Faktisk 15/20 och köpbevis

Samma 106 frysta recept, kompletta basprodukter, inköpsdag 2026-09-22, faktaversion, medlemskap av, 40/30/20 g protein och max två inköpsställen i båda armarna. Coop Online Syd behåller sin onlinekanal. Frysta fullständiga baskällor: 36 867 råprodukter plus exakt samma tillägg i B; inte betans begränsade sökprojektion. Primat ingår. Faktaversion: `retained-catalog-facts-v5:00c7ad42f80db5bfa98e5b15aed3b28afb99f81af259b6faab1c7dbb4863c6c6`.

| Slutprov | A utan kommun-Coop | B med kommun-Coop |
|---|---:|---:|
| Kostnad | 536,27 kr | 536,27 kr |
| Fysiska Coop-rader valda | 0 | 0 |
| HTTP-planering | 45,160 s | 42,323 s |
| Faktaladdning + HTTP + verifiering | 84,869 s | 87,493 s |
| Separat komplett kandidatbygge | 147,042 s | 155,470 s |
| Checkout/audit | godkänt | godkänt |
| HTTP / health / ready | 201 / 200 / 200 | 201 / 200 / 200 |
| Sparning och exakt återläsning | godkänt | godkänt |

Båda väljer samma 12 produktposter i Coop Online Syd och Willys Lund; oförändrad butikskombination. 332 lyckade basket-audits per arm. `comparison.json` innehåller samtliga valda produkter, priser och butiks-ID:n; fullständiga planer finns under `server-results/profile/`.

Separata köpbarhetsprov, inte ändringar av den vinnande menyn: via befintligt explicit produktval prövades Cheddar 500 g respektive Gouda 450 g från [Coop Värpinge](https://www.coop.se/butiker-erbjudanden/coop/coop-varpinge-lund/) i det oförändrade receptet ”Pasta med röd linssås, tomat och riven ost”. Båda kostar annonserat 59,90 kr för en hel förpackning, utan medlemskrav, 21–27 september. 80 g ost används, resten är förpackningsöverskott. Full inköpskorg 128,72 kr mot 88,32 kr utan det uttryckliga ostvalet; två inköpsställen; audit PASS; 41,2 respektive 41,6 g protein per portion. Matlagningsberäkningen är samma redan tillåtna märkta uppskattning; osten har produktdeklaration. För menyns 140 g ost kostar Coop-förpackningen 59,90 kr mot den valda basproduktens 19,50 kr. Detta är en paketkostnadsnackdel, inte ett kvarstående näringshinder.

Plommontomat 500 g, 22 kr, [Stora Coop Lund](https://www.coop.se/butiker-erbjudanden/stora-coop/stora-coop-lund/), 21–27 september: produktens näringsreferens kvalificeras. Receptet ”Couscoussallad med tofu och tomat” hittar däremot ingen godkänd kombination i den befintliga sökningen (16 kombinationer; ett konkret utfall 22,3 g protein mot krav 40). Ingen global omöjlighet påstås och receptkravet sänks inte. Fulla köpbevis: `server-results/recipe-proofs.json` (21,079 s).

## Driftpaket och tester

Ny faktisk niobutiksinsamling på servern 09:34:42–09:35:19 Europe/Stockholm, 41,895 s: 493 radgodkända och 1 937 i karantän. Sex utgångna Stora-rader är fortsatt borta. Slutpaketets ytterligare begränsade Värpingeprov kl. 10:01:35–10:01:39: 55 godkända / 267 karantän, 4,960 s. Fulla snapshotens underkännande är fortfarande synligt; endast den uttryckligt partiella kandidaten används. Det senare provet ersätter inte jämförelsens frysta observationer.

Körbar serverimage med befintlig browsertransport, UID/GID 10001, Playwright 1.58.0, Chromium och befintliga Linuxberoenden, 2 CPU/5 GiB-gräns, kanoniskt operationslås och isolerade data. Ingen monterad utvecklarkod. Felaktig butik eller misslyckad källa ger synligt fel; basen/produktionen skrivs inte. [Exakta kommandon och imagehashar](PACKAGE.md).

125 fokuserade regressioner passerar, Ruff och compileall passerar. Verkliga sparade deklarationer/erbjudanden används som regressioner. Bland annat fel namnrymd, variant, förpackning, varumärke, tid, motstridiga fakta, ändrad cacheidentitet, näringsgräns, estimat av/på och faktiskt operationslås testas. Nytt paket: faktiskt serverprov, inte enbart stubbar. Privat publiceringsprov: sju kontroller PASS, 140,089 s inklusive giltig rollback, nekad för gammal rollback, felaktig kandidat, saknad lineage och omstart. Slutlig produktions-health/ready 200/200, oförändrad app/scheduler och aktivt manifest. Ingen flerdagarsstabilitet påstås.
