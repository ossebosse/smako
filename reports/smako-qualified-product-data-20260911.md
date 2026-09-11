# Smako – kvalificerade eko-/näringsval, 2026-09-11

Release `personal-v2-qualified-20260911b`, från faktiskt verifierad workspace/produktion
`e8e6f77` / `personal-v2-gaps-20260911c`. R4/R5 förblir **PARTIAL**: fungerande
delmängder är verifierade; hela katalogen, tillagad vikt och allergifrihet är inte det.
[R1–R9-matris](../docs/product/personal-planning-v2.md).

## Frysta versioner och räckvidd

- Prisversion: `price-universe:9ab6c58a4934c0a253e037c724d58fdcc8c84b484d26a87d2027be087e17b929`.
- Prisfil SHA-256: `5c16eb74a83e56f0648a04e55f75d9f4713935cf304943dc28114be19db5722e`.
- Fakta före: `retained-catalog-facts-v1:export:772429ba9b905c7b597a66a2c8272d7cfa4ab5caa1b28511c026e40547b26e11`.
- Fakta efter: `retained-catalog-facts-v2:a4283c8ba8ae5590d365808377efa00e2c6b2e2ae48d52f46d78fbddac756622`.
- Samma 449 produktrader i samma 52 middagar, 3 frukostar och 3 mellanmål används för före/efter. Datakrav kan söka bredare än denna jämförelsepool.
- Ingrediensdeklarationer **78 → 83**, verifierat ekologiskt **45 → 46**, kompletta fyra näringsdeklarationsvärden **73 → 78**. Av de senare har 75 nu godtagbar grund som såld vara; rätt receptenhet och granskad beredning krävs dessutom.
- Källstödd animalieklassning **0 → 82** i samma pool. Komplett allergenfrånvarounderlag fortfarande **0**.
- Adapter i byggd image: 34 790 faktaproduktrader; 9,801 s första laddning, cirka 850 MiB processens högsta RSS inklusive katalog. Detta är en observation, ingen prestandaoptimering.
[Frysta menyprov och radproveniens](personal-v2-qualified/frozen.json) · [defaultkonfiguration i nätverksavstängd image](personal-v2-qualified/runtime.json).

## Kravkopplingar som korrigerats

| Krav | Tillräckligt underlag / oberoende spärr |
|---|---|
| Ekologisk kostnadsandel | Källstödd positiv ekostatus och verkliga radsummor efter rabatt. Okänd status bidrar 0 till ekologisk täljare men hela matkostnaden till nämnaren. Tillagningsutbyte, makron och allergenfrånvaro krävs inte om dessa krav inte valts. |
| Ekologiska animalier | Verifierat ekologisk produkt uppfyller implikationen även om animaliskt innehåll är okänt. Annars krävs källstödd animalieklassning; ägg/mejeri omfattas. Veganmarkering kan styrka icke-animalisk sammansättning, aldrig allergifrihet. |
| Makron/energi | Bara valda mätvärden krävs, per 100 g/ml med deklarationsgrund; ingen g↔ml/st-omräkning utan data. Exakt skafferi räknas som egna faktabelagda bidrag, generiskt skafferi får inte låna en produktdeklaration. |
| Tillagad portionsvikt | Kontrolleras separat mot receptrevision, portioner och dokumenterat uppmätt utbyte. Tidigare gick även rena viktkrav igenom näringskrav; denna felkoppling är borttagen. Nödvändiga verkliga vikter saknas fortfarande. |
| Allergier | Oförändrad fail-closed-kontroll. Positiva ingredient-/spårkonflikter kan blockera. Okänd frånvaroinformation eller okänd allergi blir aldrig godkänd genom eko/vegan/GTIN. |

Näringsgrund: `cold-edible-assembly-v1` avgränsar stödet till granskade kalla
beredningar av uppmätt ätbar mängd utan värmning/avrinning/extra olja. Det omfattar
ostsmörgås med mjölk och morotsstavar med ost när alla produktuppgifter räcker,
samt motsvarande direkt servering av bröd/ost/mjölk. Det är en uppskattning från
produktdeklarationer, inte laboratoriemätt serverad näring. Ändrade steg/former
kräver ny kontroll. Tidigare råvarusummering för valfria varma recept var för bred;
sådan beredning blockeras nu utan godkänd förlustgrund. Inget vatten, svinn, utbyte
eller näringsvärde har antagits för att nå en tröskel.

Deklarerade avrinningsfall och mozzarella/feta/salladsost med otillräcklig grund
kan ha sparade makrovärden men deltar inte i näringsval som såld ingrediens.
Lågt klassade produktförslag från den breddade sökningen kan inte kvalificeras
bara för att de har näringsdata: exempelvis ostbröd som föreslogs som ost.

## Kandidatsökning och cache

Befintliga frysta semantiska index och produktsökning återanvänds före den billiga
kandidatpoolens gallring. Makrokrav kontrolleras också under mellanliggande
menysökning, inte bara sist. Ett komplett men näringsmässigt olämpligt produktval
kan ersättas i en begränsad sökning om högst 256 kombinationer. Närliggande val
över alla relevanta ingredienser prövas tidigt; orelaterade extravaror förbrukar
inte den budgeten. Varje förslag prissätts av samma hela-korgen-optimerare.
Eko kontrolleras slutligt och används för kandidatkostnad före menypruning där
möjligt. Sökgränsen bevisar inte matematisk omöjlighet och kraven sänks aldrig.

Faktainnehållets SHA-256 och policyversion ingår nu i personlig beräkningsidentitet,
tillsammans med befintlig privat profil/lager/recept/pris-/medlemsidentitet.
Databas-/WAL-revision ingår i faktaprojektionens cache; ändrade fakta ger nytt
innehålls-ID. Tillförlitlig viktmetadata ingår också. Inga historiska revisioner
eller bokförda köp skrivs om när fakta ändras.

## Exakt återanvändning av befintliga fakta

Befintlig `ProductFacts` och `ProductSearchIndex` används. Godkänd GTIN-kontroll
och samma förpackningsmått/försäljningsmodell krävs; motsägande variantprocent,
form, varumärke, kanonisk identitet eller marknad spärrar komplettering.
Svenska observationer måste ligga inom sju dagar. Detta är en konservativ
observationsgräns, inte bevis på samma tillverkningsbatch. Snapshot/produkt-ID
kontrolleras, och motstridiga fält hålls okända med konfliktmarkering och proveniens.
Olika g/ml- eller rå/tillagad näringsgrund blandas inte. Saknad tillverkarversion
är ingen allergigaranti. Pris, erbjudanden, medlemskap, lager, tillgänglighet och
prisernas observationstid kopieras aldrig och PriceUniverse skrivs aldrig.

Fältproveniens anger ursprunglig källa, källprodukt, snapshot, observationstid och
SE-marknad. Följande fem ICA/Primat-rader i jämförelsepoolen fick befintliga
Coop-fakta genom exakt GTIN/förpackning; ICA-priserna förblev ICA-priser:

- Pasta Spaghetti, GTIN `8076804215058`: ingredients, nutrition.
- Pasta Spaghetti, GTIN `8076809569811`: ingredients, nutrition.
- Vitlökspeppar, GTIN `7311311017391`: ingredients, nutrition.
- Vitlökssalt, GTIN `7311311026430`: ingredients, nutrition.
- Svart ris, GTIN `7317731535200`: ingredients, organic, nutrition.

**Nya produktdetaljhämtningar: 0 distinkta produkter, 0 anrop.** Sparade
hashverifierade svar räckte till de fungerande exemplen. Befintlig godkänd Coop
`fetch_products_by_id` har inspekterats: samma sökprojektion/åtkomst och ett inbyggt
tak 50 produkter. Inget extra utbytes-/densitetsunderlag har identifierats där;
ingen duplicerande kataloghämtning gjordes för att öka procentsiffror. Willys-task
och relay, ICA OWN-research, ICA/Primat-normalisering och insamling är orörda.

## Verkliga exempel A–E

Gemensamt: Lund/22350, Billigast, två portioner, ett tillfälle, blandkost, högst
två inköpsställen, inga medlemskap, inga hårda allergier/uteslutningar, inga
extravaror eller befintligt skafferi. Minimera överskott; hela förpackningar.
Inga nolltrösklar används som demonstrationskrav. Alla nedanstående priser är
källans ordinarie/rapporterade grundpris; ingen villkorad rabatt används.
Onlinepriser är inte verifierade fysiska hyllpriser eller lagergarantier.

### A: PASS

Inställningar: `dinner`, ekoandel `25.0 %`, animaliskt eko `False`, portionsgränser `{}`.

**Hela menyn: Gryta med tofu, nudlar och morot (2 portioner).**

Receptbehov: 200 g tofu, 175 g nudlar, 250 g morot, 200 ml kokosmjölk, 150 g gul lök.

| Produkt | Butik/priskontext | Hela förpackningsköp | Radsumma |
|---|---|---:|---:|
| Kokosmjölk Eko | Coop Online Syd | 1 paket, totalt 200 ml enligt källan | 14,67 kr |
| Lök Gul i Påse Klass 1 | Willys Lund | 1 paket, totalt 1000 g enligt källan | 9,90 kr |
| Morötter Klass 1 | Willys Lund | 1 paket, totalt 500 g enligt källan | 9,90 kr |
| Äggnudlar | Willys Lund | 1 paket, totalt 250 g enligt källan | 9,36 kr |
| Naturell Tofu Fast Vegansk | Willys Lund | 1 paket, totalt 200 g enligt källan | 11,90 kr |

**Full inköpskostnad: 55,73 kr.** Verifierat ekologisk kostnad 14,67 kr / 55,73 kr = 26.32 %.

### B: PASS

Inställningar: `breakfast`, ekoandel `0.0 %`, animaliskt eko `True`, portionsgränser `{}`.

**Hela menyn: Ostsmörgås och mjölk (2 portioner).**

Receptbehov: 160 g bröd, 60 g ost, 400 ml mjölk.

| Produkt | Butik/priskontext | Hela förpackningsköp | Radsumma |
|---|---|---:|---:|
| Mozzarella Eko | Coop Online Syd | 1 paket, totalt 240 g enligt källan | 20,54 kr |
| Knäckebröd Fullkornsråg Linfrö | Willys Lund | 1 paket, totalt 200 g enligt källan | 16,90 kr |
| Lättmjölk Ekologisk 0,5% | Willys Lund | 1 paket, totalt 1000 ml enligt källan | 12,90 kr |

**Full inköpskostnad: 50,34 kr.** Verifierat ekologisk kostnad 50,34 kr / 50,34 kr = 100.00 %.

Här verifieras det ekologiska animaliekravet, inte näring eller ätbar portionsvikt.
Mozzarellans katalogmängd 240 g innefattar en otillräckligt specificerad
avrinningsgrund. Den mängden/ett nominellt överskott är **inte** verifierad
ätbar ostvikt och används inte i C/E:s näringsberäkning.

### C: PASS

Inställningar: `breakfast`, ekoandel `0.0 %`, animaliskt eko `False`, portionsgränser `{"min_protein_g": 15.0, "min_carbs_g": 30.0, "max_carbs_g": 90.0, "min_fat_g": 5.0, "max_fat_g": 30.0, "max_kcal": 600.0}`.

**Hela menyn: Ostsmörgås och mjölk (2 portioner).**

Receptbehov: 160 g bröd, 60 g ost, 400 ml mjölk.

| Produkt | Butik/priskontext | Hela förpackningsköp | Radsumma |
|---|---|---:|---:|
| Liba Bröd Grov | Coop Online Syd | 1 paket, totalt 340 g enligt källan | 10,88 kr |
| Getmjölk | Coop Online Syd | 1 paket, totalt 1000 ml enligt källan | 35,49 kr |
| Riven ost Cheddar | Coop Online Syd | 1 paket, totalt 150 g enligt källan | 19,50 kr |

**Full inköpskostnad: 65,87 kr.** Verifierat ekologisk kostnad 0,00 kr / 65,87 kr = 0.00 %.

Per portion: fat_g 14.56, protein_g 21.84, carbs_g 51.71, kcal 437.90. Alla 3/3 ingrediensbehov har källa, rätt enhet och granskad kall beredningsgrund.

### D: DATA_BLOCKED

Inställningar: `breakfast`, ekoandel `0.0 %`, animaliskt eko `False`, portionsgränser `{"min_weight_g": 250.0, "max_weight_g": 600.0}`.

Tofumacka med tomat: verifierat tillagningsutbyte/ätbar tillagad vikt saknas.

Tre frukostkandidater har vardera 3/3 köpbara ingrediensbehov; 0/3 har
verifierad tillagad ätbar portionsvikt/utbyte. Det är det saknade fältet,
inte saknad näring, som blockerar detta rena viktkrav. Radvis lista finns i JSON-provet.

### E: PASS

Inställningar: `breakfast`, ekoandel `30.0 %`, animaliskt eko `False`, portionsgränser `{"min_protein_g": 15.0, "min_carbs_g": 30.0, "max_carbs_g": 90.0, "min_fat_g": 5.0, "max_fat_g": 30.0, "max_kcal": 600.0}`.

**Hela menyn: Ostsmörgås och mjölk (2 portioner).**

Receptbehov: 160 g bröd, 60 g ost, 400 ml mjölk.

| Produkt | Butik/priskontext | Hela förpackningsköp | Radsumma |
|---|---|---:|---:|
| Liba Bröd Grov | Coop Online Syd | 1 paket, totalt 340 g enligt källan | 10,88 kr |
| Getmjölk | Coop Online Syd | 1 paket, totalt 1000 ml enligt källan | 35,49 kr |
| Blåmögelost Organic blue Eko | Coop Online Syd | 1 paket, totalt 150 g enligt källan | 35,59 kr |

**Full inköpskostnad: 81,96 kr.** Verifierat ekologisk kostnad 35,59 kr / 81,96 kr = 43.42 %.

Per portion: fat_g 16.96, protein_g 18.54, carbs_g 51.35, kcal 445.70. Alla 3/3 ingrediensbehov har källa, rätt enhet och granskad kall beredningsgrund.

Beräknat förpackningsöverskott: 180 g bröd, 600 ml getmjölk och 90 g ost.
Skafferibidrag 0; faktiskt lager förblir 0 efter genereringen. Ingen
hållbarhet anges. Animaliskt eko är inte valt; ekologisk ost ger 43,42 %
trots okänd ekostatus för bröd/mjölk. Ingen generell säkerhetsstämpel.
Produktdeklarationerna kommer från Coop-snapshoten; fulla källpekare,
källprodukt-ID och tid står per näringsbidrag i den frysta JSON-rapporten.

## Kombinerade skydd, tester och leverans

- 175 relevanta samlade tester passerade. Efter sista avgränsade sökordningsfixen passerade 28 direkt berörda och därefter 81 fokuserade tester, inklusive ett nytt fall med 270 orelaterade extravaruvarianter. Ruff, Python 3.12 compileall och JavaScript-syntax passerar.
- Exakt 100 ml skafferi + 200 ml receptbehov + ytterligare 500 ml uttryckligt mjölkköp prövas fryst: ett 1 l-paket för 20 kr, 8 g protein per portion inklusive skafferi, samma lager före/efter generering. Generiskt skafferi utan produktdeklaration blockerar näringskravet.
- Medlemspris 10 kr mjölk + 10 kr bröd + 100 kr servetter: full korg 120 kr, matnämnare 20 kr och ekoandel 50 %. Icke-mat eller befintligt skafferi ökar inte nämnaren. Utan nya matinköp visas NO_NEW_FOOD_PURCHASES, inte 100 %.
- Befintliga bokförings-, samtidig revisions-, raderings/restore- och användarisoleringstester passerar. Inga användardata raderas. De nya resultaten kan läsas av tidigare release utan modell- eller databasmigrering.
- Frysta konsumentprov kördes med socketanslutning spärrad. Verkliga HTTPS-resultat kräver live_chain_requests=0. Ingen produktdetaljklient finns i konsumentflödet.
- Chromium/WebKit: 18 befintliga mobilkontroller per motor och integrerad bokförd redigering passerar. Slutliga verkliga HTTPS-kontroller passerar i båda motorerna, inklusive skapande genom Mina val med alla sex näringsgränser och eko 30 %. Fysisk iPhone/Safari är inte verifierad.

[Slutliga fokuserade tester](personal-v2-qualified/focused.xml) · [Formulär → HTTPS](personal-v2-qualified/https/choices.json) · [Samlad regression](personal-v2-qualified/regression.xml) · [sista sökfixen](personal-v2-qualified/search-order-final.xml) · [mobil HTTPS](personal-v2-qualified/https/results.json).

Backup `20260911T140005Z`, därefter `20260911T140622Z`. Endast appen byttes
under befintligt gemensamt refresh-/backup-/aktiveringslås. Första aktiveringen
bevarade alla 105 revisioner; den slutliga alla 109 då befintliga revisioner.
Scheduler, prismanifest och aktiva databaser är bevarade. Tidigare verifierad
isolerad restore/raderingsgaranti återanvänds; ingen schemamigrering tillkom.
[Deployment](personal-v2-qualified/deployment.json) · [rollback-läsning](personal-v2-qualified/rollback-compatibility.json).

Image `sha256:998f54de3933163b129d004a0c2afdbb69a33146f2f3acd09f4957449536aa06`.
Approllback, utan databasrestore: `ssh smako python3 /opt/smako/evidence/personal_v2_qualified_activate.py rollback`.
Det återgår till kvalificerad A-image under samma lås; källfakta/version och
datamodeller är desamma. Inköp/planer ligger kvar. Tidigare gaps-C kan också
läsa alla nya JSON-resultat enligt separat kompatibilitetsprov.

Oförändrad femmiddagsmeny kostar **244,49 kr** före/efter. Sekventiellt fryst prov:
kall **16,181 → 16,102 s (−0,5 %)**, varm **0,759 → 0,875 s (+15,3 %)**.
Enstaka mätningar, inget SLA. Sista sökordningsfixen körs endast vid nya aktiva
krav och påverkar inte detta basfalls kodväg. Inga goldens ändrades.
[Före](personal-v2-qualified/benchmark-before.json) · [efter](personal-v2-qualified/benchmark-after.json).

## Exakta kvarvarande hinder och nästa operatörssteg

1. D och varma måltiders makron: verifierad ätbar mängd, tillagnings-/avrinningsgrund och relevanta förluster knutna till exakt receptrevision saknas. Inga antagna faktorer införs.
2. B tillsammans med C:s makrokrav kan fortfarande blockeras: flera ekologiska mjölkprodukter har g-deklaration men ml-receptbehov, utan verifierad densitet/omräkning; vissa ostprodukter har oklar avrinning. En per-ml-deklaration eller verifierad omräkning för den exakta produkten behövs.
3. Generiskt skafferi saknar produktdeklaration. Användarval av exakt produkt möjliggör faktakontroll där katalogidentitet och rätt enhet finns. Redan förbrukade ingrediensers näringsunderlag kräver historiskt belagd grund vid en ny omberäkning; gamla planer/köp ändras inte.
4. Komplett spårbart allergenunderlag saknas. R1:s hårda allergifall förblir DATA_BLOCKED, även om ekologisk andel eller näring fungerar.
5. R2/OIDC kvarstår som separat operatörssteg: välj/godkänn leverantör, konfigurera de tre tidigare dokumenterade OIDC-värdena privat och kör verklig tvåenhets-/ägaracceptans. Ingen authändring, påhittad konfiguration eller ny tjänst/kostnad infördes.

R6/R9 har inte byggts om. R9:s fulla livekampanjdata, OIDC, kall plannerprestanda,
ICA OWN-research och Willys-task/relay förblir tidigare avgränsade uppföljningar.

Appkoden är commit `e1c0db1`. Alla fem deployade appfiler matchar verifierad källa
([filhashar](personal-v2-qualified/source-match.json)). Slutkontroll: 120 revisioner;
alla 109 före sista appbytet bevarade. Nya revisioner är syntetiska acceptansplaner.
[Sökning på HTTPS](personal-v2-qualified/https/search.json) verifierar också noll leverantörsanrop.
