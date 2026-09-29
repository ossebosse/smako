# Gemensam köpplanering – 25 september 2026

Det befintliga prisflödet har utökats med ett gemensamt köpkontrakt, ett valbart uppskattningsläge och villkorade kampanjval. Källans pris, köpform, variantidentitet och näringsunderlag bedöms separat. Ingen produktion, Windows-uppgift eller aktiv schemaläggning har ändrats.

## Jämförbart resultat

Prisjämförelsen använder samma sparade officiella dokument och strukturerade svar, köpdag **24 september 2026** och WillysPlus/Lidl Plus. Observationstiderna är oförändrade. Nya näringshämtningar den 25 september redovisas separat. Alla kvalificerade poster har behandlats, inte bara exemplen nedan.

| Underlag | Hela nämnaren | Automatiska annonser före → efter | Automatiska aktuella poster före → efter | Manuella aktuella poster, separat | OWN/PU före → efter per dokument/butik |
|---|---:|---:|---:|---:|---:|
| Willys Hemma | 34 annonser | 20 → 23 | 26 → 29 | 2 → 2 | 28 → 31 |
| Willys, 12 sidor | 112 annonser | 57 → 75 | 63 → 81 | 7 → 7 | 70 → 88 |
| Lidl | 380 unika källprodukt-ID | ej jämförbar annonsräkning | 26 → 28 | 0 → 0 | 26 → 28 |

De nya Willys-posterna är **kampanjgrupper med öppet variantval**, inte fullständigt identifierade produktvarianter. Gamla dokumentbundna manuella godkännanden är bevarade och deduplicerade; de ärvs inte av en ny utgåva.

| Unikt resultat över kommunerna | Willys före → efter | Lidl före → efter |
|---|---:|---:|
| Prisposter, deduplicerade över butiker | 87 → 108 | 26 → 28 |
| Livsmedelsposter | 82 → 101 | 26 → 28 |
| Exakta livsmedelsköp med matchning och audit | 74 → 74 | 26 → 26 |
| Uppskattade livsmedelsköp med matchning och audit | 0 → 8 | 0 → 2 |
| Villkorade livsmedelsval med verifierad kostnadsräkning | 0 → 19 | 0 → 0 |
| Näringsunderlag kompatibelt med gramköpet | 10 → 10 | 2 → 3 |
| Näringsunderlag om ätbara gram mäts separat | 14 → 14 | 4 → 5 |

En ny gruppost överlappar en tidigare prissatt glasskampanj. Därför är nettot **20 nya Willys-kampanjpriser, varav 18 livsmedel**, och **2 nya Lidl-livsmedelspriser**. De åtta Willys-viktpriserna fanns redan bevarade men saknade användbar uppskattad köpberäkning. De räknas inte som nya priser. Två nya Willys-poster är icke-livsmedel. Inga tidigare godkända prisposter har tagits bort.

Kostnadsräkning för ett öppet variantval är inte ett specifikt produkt-/allergi-/receptgodkännande. Sådana varukorgar får fortsatt **UNVERIFIED**. Uppskattade viktköp får **ESTIMATED**. Ett godkänt räkneprov får inte uppgradera kvalitetsstatusen.

Maskinläsbart facit: [comparison.json](comparison.json), [willys-denominator.json](willys-denominator.json), [lidl-denominator.json](lidl-denominator.json). Alla 17 butiker med officiell länk och importstatus finns i [STORES.md](STORES.md). Lund har 87 importerade butiksposter och Malmö 467; butikskopior ingår inte i nettot ovan.

## Implementationen

`PurchaseTerms` kompletterar befintliga SourceOffer-/OfferMetadata-kontrakt. Collector, katalog-API och OWN bevarar det i befintlig JSON-lagring; ingen ny databas eller prismotor har införts. PriceUniverse och de ordinarie kommunadaptrarna bevarar kontraktet och källidentiteten. Nya kedjor kan använda samma kontrakt.

* **Lösvikt:** belagt kr/kg räknas mot planerad inköpsvikt, utan fiktiv förpackning. Slutbeloppet beror på uppvägning.
* **Cirka-vikt:** källans cirka-vikt används för hela paket. 200 g receptbehov köper fortfarande ett helt paket om cirka 1,1 kg. Antal och rester samordnas genom befintlig behovsaggregering. Inköpsraden anger erforderlig minimimängd och att faktiskt utfall beror på paketvikten. Inget påhittat ±10-procentsintervall används.
* **Styckköp:** uttryckligt styckpris kan användas utan gramvikt. Näringen kräver separat tillämplig mängdgrund.
* **Öppna grupper:** en källbelagd kampanj lagras med variantval, källans storleksintervall och undantag. Ett intervall blir aldrig en mittpunktsförpackning. Gruppen kan väljas uttryckligt i inköpslistan, men blir inte en specifik receptprodukt.
* **Identifierade blandade varianter:** officiella produkt-ID, grupp-ID, samma butik/snapshot och identiska kampanjvillkor kan skapa en verifierad delmängd i befintlig `PromotionGroup`. Inga namnmatchade medlemmar läggs till. Saknade varianter behöver inte uppfinnas. Gruppkostnad, medlemskap och gemensamma tak räknas i befintlig gruppmotor. Saknas restpris köps en hel belagd grupp; överlappande grupper utan säker fullständig fördelning stoppas.
* **Pant:** varupris och pant hålls separata. Okänd pant bevarar prisuppgiften men blockerar en påstått komplett köptotal. Blandade grupper med oklar pantomfattning får inte en godtycklig pantberäkning.

API-fältet `purchase_planning_mode` har värdena `exact` och `estimated`, med **exact som bakåtkompatibel standard**. Personliga planeringsvyn har ett verkligt val som sparas och återläses. Uppskattade kostnader och berörda rader märks. Bokföring av ungefärliga inköp till skafferiet kräver faktisk uppmätt användbar mängd; uppskattade rester bokförs inte som uppmätt lager. Ett källimporterat fält kan inte smuggla in användarens privata variantbekräftelse.

Den gemensamma beräkningen gäller ICA, Coop/Stora Coop/X:-tra, Willys, Hemköp, City Gross och Lidl. Oförändrade kedjekällor behöver inte få nya butikslistor eller en separat motor. Parametriserade köpformstester kompletteras med befintliga kedje-/providerregressioner. Blandade identifierade källgrupper är verifierade med syntetiska kontraktsfall genom riktig collector/SQLite/OWN/PU; detta påstås inte vara en ny verkligt identifierad Willys-variantgrupp.

## Verkliga köp och näring

Exemplen avser det frysta underlaget och kampanjperioden **21–27 september 2026**. Ordinarie köppris är fortsatt okänt där källan inte belägger det.

* **Lidl Persikor:** 26,90 kr/kg, lösvikt, **Lidl Plus**. Planerade 200 g kostar cirka **5,38 kr**. Ingen fast gramvikt eller GTIN har hittats på. Produkt-/dokumentbindning och butiksgiltighet har verifierats; generiska SLV-värden per ätbara gram ger inte automatiskt näring för 200 g frukt med kärna. [Officiell Lundbutik](https://www.lidl.se/s/sv-SE/butiker/lund/magistratsvaegen-6/).
* **Lidl Arla Hushållsost:** 26 % fett, cirka 2,2 kg, 69,90 kr/kg, högst **3 förpackningar/hushåll**, offentligt pris. Receptbehov 200 g medför ett helt paket för cirka **153,78 kr**, inte 13,98 kr. Matchning till ost och checkout/audit passerar i uppskattningsläge. [Arlas officiella produktdeklaration](https://www.arla.se/produkter/arla-brand/hushallsost-2200g-793680/) binds med full produktidentitet, fetthalt och viktvariant. Deklarationen anger per 100 g 337 kcal, 25 g protein, 0 g kolhydrat och 26 g fett. Näringsberäkningen för 200 g använder 200 g, inte hela inköpta paketet. En relevant ostkomponent i befintligt receptprov passerar; detta är inte ett påstående om en ny fullständigt kvalificerad meny.
* **Willys Garant färsk pizza:** välj kampanjmärkt sort, **400 g, 3 för 99 kr, WillysPlus, högst 3 köp/hushåll**. En begärd förpackning utan belagt restpris medför en hel grupp om tre förpackningar. Kostnaden är 99 kr; det finns inget fabricerat fristående 33-kronorspris. Varianten måste väljas och produkten blir inte automatiskt närings-/allergigodkänd. [Officiellt Rosengårdsblad](https://reklamblad.willys.se/willys/2352).

Arla-deklarationen hämtades faktiskt den 25 september och importerades genom den återanvändbara deklarationsimporten. Källans streckkod kopierades **inte** till Lidls GTIN-fält. Sparade Garant-deklarationer och tidigare näringskopplingar bevarades.

Livsmedelsverkets **livsmedel 580, Persika**, har hämtats med ursprungliga värden, käll-ID, version och observation och lagts till i befintliga referensdata. Den är tillgänglig som tydligt märkt generisk referens för uppmätta ätbara gram enligt befintligt opt-in. Ingen kärnandel, styckvikt, densitet eller tillagningsomräkning har antagits. Sammansatta öppna kampanjprodukter får inte näring från godtyckligt närmaste produkt.

Det finns **5 nya officiella närings-/produkthämtningar** i [sources](sources): två SLV-sökningar, Arla-produktsidan och SLV:s persiko-/näringsdata. **0 nya priskälleanrop** gjordes i denna etapps före/efter- och driftreplay. Sparade metadatafält för äldre request counts är inte nya nätanrop.

## Verifiering och kvarstående status

Slutresultat för den riktiga oförändrade 15/20-profilen, komplett baskontroll, runtime och testantal finns i [VERIFICATION.md](VERIFICATION.md). Exakt respektive uppskattat läge provas med samma bas, datum och medlemskontext; ingen besparing framtvingas.

Hela nämnaren bevaras. Lidl har 28 kvalificerade, 350 med saknad tillräcklig produkt–kampanj-/butiksbindning och 2 parserkarantäner. Den regionala datumklassningen har 105 aktuella livsmedelskandidater, varav 26 kvalificerade; två ytterligare importerade produkter har annan regional datumklassning men separat belagd aktuell fysisk dokumentkampanj. Det gör inte resten av regionalflödet nationellt giltigt. Framtida regionala livsmedel är 132, framtida icke-livsmedel 64 och framtida okänd livsmedelstyp 3. Aktuella icke-livsmedel är 68 och aktuell okänd typ 2; okänt datum omfattar 5 livsmedel och 1 icke-livsmedel.

Alla blockerartyper, inklusive exakt saknat underlag/stöd, redovisas i [BLOCKERS.md](BLOCKERS.md). Full täckning är inte uppnådd. Det finns ingen ny oberoende, tidigare ogranskad verklig utgåva som har verifierats som holdout. Bevarade verkliga Lidl-revisioner har prövats men har även använts under regelutvecklingen. Syntetiska tester för kampanjbyte ersätter inte ett sådant prov.

Det historiska Lidl-testets saknade fixture och det fullständiga Malmö-publiceringsprovet med aktuell komplett bas är fortsatt öppna. Separat inaktivt [aktiveringsunderlag](RELEASE.md) och [paketmanifest](PACKAGE.json) anger förutsättningarna för nästa steg. Tidigare kedjearbete och releaseunderlag är bevarade.
