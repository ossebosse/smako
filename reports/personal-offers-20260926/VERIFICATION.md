# PersonalPlanner – verkliga erbjudanden, 26 september 2026

Historisk replay, inga nya pris- eller näringsnätanrop. Samma kompletta artifact, 9 priskontexter inklusive 6 obligatoriska. Inga produktlistor eller kandidatlistor har handpatchats. Ursprunglig 15/20: 40/30/20 g protein och högst två inköpsställen. Separat medlemskopia med Willys Plus och Lidl Plus.

| 15/20 | Kostnad före → efter | Tid före → efter | Kvalitet | Valda rader E/U/V |
|---|---:|---:|---|---|
| public / exact | 535.25 → 535.25 kr | 57.822 → 61.501 s | VERIFIED | 12/0/0 |
| public / estimated | 535.25 → 535.25 kr | 59.124 → 64.528 s | VERIFIED | 12/0/0 |
| plus / exact | 535.25 → 535.25 kr | 52.395 → 62.825 s | VERIFIED | 12/0/0 |
| plus / estimated | 535.25 → 535.25 kr | 57.015 → 66.792 s | VERIFIED | 12/0/0 |

Alla fyra profiler väljer Coop Online Syd (`online_fulfillment`) och Willys Lund (`online_store`): 12 exakta köprader, 20 förpackningar. E/U/V betyder exakt/uppskattat/villkorat. Kostnaden avser hela inköp, inte förbrukade receptgram. Näring redovisas separat: 10 deklarationsbaserade VERIFIED och 5 tillåtna referensbaserade ESTIMATED måltider; samtliga 40/30/20-mål passerar.

| HTTP: ostsmörgås, Lidl Plus, uttryckligt Lidl-val | Kostnad | Tid | Kvalitet | E/U/V |
|---|---:|---:|---|---|
| before / exact | 30.28 | 11.214 s | VERIFIED | 2/0/0 |
| before / estimated | 30.28 | 5.453 s | VERIFIED | 2/0/0 |
| after / exact | spärrat | 9.553 s | HTTP 422 | –/–/– |
| after / estimated | 171.68 | 4.080 s | VERIFIED_WITH_ESTIMATES | 1/1/0 |

**HTTP-föreprovet är inte en jämförbar Lidl-kostnad:** den gamla API-modellen saknade `allowed_store_ids`, ignorerade fältet och valde Coop Online Syd (Liba Bröd Grov/Gouda Skivor). Efterprovet respekterar det nya, uttryckliga planbundna butiksvalet. Det ändrar inte sparad profil eller kommunens inventering.

Efter, uppskattat: Lidl Åkerlund och Rausings väg 1, fysisk butik. Pågen Lingongrova 500 g för 17,90 kr (Lidl Plus) + offentliga Arla Hushållsost 26 %, cirka 2,2 kg × 69,90 kr/kg = cirka 153,78 kr. Summa cirka **171,68 kr**. Ett helt ostpaket köps; receptet använder 100 g ost och 100 g bröd. 2 100 g uppskattad ostrest. Protein 25 + 8,8 = **33,8 g**, prövat mot minst 30 g. Deklarationsbaserad näringsstatus VERIFIED är skild från korgens VERIFIED_WITH_ESTIMATES; allergisäkerhet är inte begärd/bevisad.

Ordinarie HTTP POST `/api/plans`, GET, verklig backendprocessomstart och GET passerar med identisk sparad plan och återladdat hashkontrollerat artifact. Checkout/audit är sparad i `personal.checks.checkout_audit`. Inga extraköp, produktlås, injicerade kandidatlistor eller syntetiska priser användes.

## Produktvis faktiskt bortfall

- **Arla Hushållsost:** fanns redan i breda matched-indexet, som PersonalPlanner faktiskt använder när fakta behövs. Ingen bevisad överföringsförlust för den näringsprövade profilen. Den faktiska resolve-vägen använder candidates_by_name, kompletterar med matched_candidates_by_name och PriceUniverse-canonical-index samt befintligt textsökindex; semantic_candidates_by_name är ingen direkt ingång i PersonalPlanner. Deklarationsklassificering tillkommer som requestlokalt index. Exakt läge spärrar cirka-vikten. Uppskattat läge: matchning, pris, deklaration och korgkandidater passerar för fem ostrecept. Den fria slutmenyn väljer den inte. Två explicita hela-varukorgsjämförelser (en per Lidl-butik) uttömmer den befintliga näringssökningens 256 kombinationer under tvåbutikstaket; ett redovisat avslag ger 38,350347509 g protein mot 40 g för torsk/nudlar/vitkål. Detta bevisar varken att Arla är dyrare eller att en lösning globalt är omöjlig. Befintlig optimering prioriterar även verifieringsnivå före pris.
- **Willys Gouda:** prisvillkor stoppar utan Willys Plus. Med Plus och uppskattningsläge når den fem ostbehov, men saknar kvalificerad näring per 100 g för efterfrågat proteinfält. Källan anger VARDAGSFAVORITER, tillfälligt parti, cirka 1,1 kg; GTIN och fetthalt saknas. Därför finns inte grund för att välja en godtycklig SLV-ostreferens. Inget påhittat generiskt ostvärde lades till.
- **Willys fläskytterfilé:** dess relevanta ugnsplåtsrecept stoppas före produktprövning av saknad godkänd beredningsgrund; inget ekonomiskt bortval är visat.
- **Willys Granny Smith/Royal Gala och Lidl-persikor:** receptpoolen innehåller inget relevant fruktbehov. De har inte fallit bort i en faktisk kostnadsjämförelse. Persikans sparade SLV-värde avser ätbara gram; ingen kärnandel har gissats.
- **Lingongrova:** verifierad leverantörsklassificering Matbröd nådde tidigare inte index/matchning från det korta produktnamnet. Den generella deklarationsprojektionen rättar det med återkontrollerad GTIN/variant/förpackning och källhash. Pris, datum, butik och Plus-villkor kommer fortfarande från ursprungligt erbjudande.

## De 84 beredningsavslagen

80 genererade varma recept saknar en granskad beräkningsregel; deras instruktioner anger även neutral matolja utan mängd. Fyra andra fall: två recept med kokta/skalade ägg i styck (ätbar gramkoppling/beredning), stekt tofu (beredningsgrund), samt kokta avrunna kikärtor (mängd-/deklarationsgrund). Se alla 84 exakta ingredienslistor, steg och första avslag i `preparation-review.json`. Dessa är inte 84 avslag på prisposter. Skydden har inte sänkts.

## Kod och verifiering

- Bredare index används i uppskattningsläge även utan inlästa näringsfakta: prisdeltagande är inte beroende av näringsprövning. Separat oförändrat verkligt fryst indexprov ger 4 → 6 ostkandidater utan näringsfakta; de två tillkommande butiksposterna är samma Arla-erbjudande i två butiker, alltså ett unikt erbjudande. Se index-before.json/index-after.json.
- Exakt deklarationsklassificering kan komplettera korta produktnamn i gemensam matchning; oidentifierade variantgrupper eller konfliktfyllda deklarationer får inte ärva den.
- Planbundet uttryckligt butikskontextval med validering, lagring och oförändrat standardläge.
- Avgränsad produktspårning genom faktiska index, recept, prisvillkor, näring, korgkandidater och verkliga sökhändelser; första stopp skiljs från senare receptavslag. Hela alternativa korgar kontrolleras av befintlig optimering/näring/audit.
- 252 unika riktade regressioner PASS, däribland verkligt fryst måltidsprov och negativa fall för exakt läge, medlemskap, allergi, utgång, fel butik, ml/g och obelagd vikt. Begränsningar och käll-ID/snapshot följer diagnostiken. Ruff och compileall PASS.

Prisimport, PurchaseTerms, providers, kommuninventering och refresh-scheman är oförändrade jämfört med frysta utgångspunkten. Tidigare kontroller av kommunurval, andra rebuilden och behovsstyrning återanvänds som oförändrade käll-/driftbevis; detta steg utför inte ny extern insamling eller en ny komplett Malmö-publicering.

## Öppna beroenden och begränsningar

Den fria sökningen är begränsad (beam 8, säker fallback 64, näringssökning 256); diagnostiken är begränsad till 256 erbjudandeprodukter/4 096 recept–ingredienskontexter och högst 24 avslutande alternativa korgar. Den aktuella profilen har 87 spårade butiksposter och inga utelämnade produkt-/kontexthändelser. Butikskopior är inte nya unika erbjudanden. Ingen uttömmande global optimumgaranti.
Inga nya prisposter eller näringsvärden importerades. Den observerade förbättringen är användbar receptkoppling och fullständig HTTP-verifiering. Den gamla Lidl-fixtureluckan är fortsatt ÖPPEN. Ny oberoende verklig kampanjutgåva och fullständigt Malmö-publiceringsprov med färsk komplett bas är fortsatt separata öppna kontroller.
Underlaget är historiskt: 43,466 h gammal äldsta användbara bas vid testklockan och nu för gammalt för aktuell publicering. Näringsdeklarationen för Arla hämtades 25 september och återanvänds i retrospektivt pristest för 24 september. Observationer, 36/48-timmarsgränser och användarval har inte föryngrats/ändrats. Ingen produktion, schemaändring, bildanalys eller betald modell-API.
