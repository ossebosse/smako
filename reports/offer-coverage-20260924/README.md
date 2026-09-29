# Automatisk pristäckning: Willys och Lidl, 24 september 2026

Willys får fler automatiskt godkända livsmedelsannonser. Lidl får dessutom 14 tidigare ej importerade livsmedelsprodukter. Willys sammanlagda unika prisutbud växer inte i det frysta underlaget: ökningen ersätter tidigare dokumentbunden manuell granskning. Det ska inte beskrivas som nya unika Willys-priser. Om acceptanskravet är nettotillskott av unika priser även för Willys återstår den delen.

Ingen produktion, Windows-uppgift eller aktiv schemaläggning har ändrats. Ingen bildanalys eller betald modell har använts. Tidigare källarbete och releaseunderlag ligger kvar. Inga sparade användarval ändras.

## Jämförbar utgångspunkt

`baseline-manifest.json` fryser råfiler och fem berörda ursprungliga kodfiler. `willys-before.json` är den tidigare slutrapporten. Källdata har kontrollerats oförändrade efter arbetet. Köpdatum är 24 september, samma medlemskontext och verkliga observationstider före/efter. Jämförelseinsamlingarna är replay med noll externa anrop.

| Samma underlag | Identifierade annonser / käll-ID | Automatiska annonser före → efter | Automatiska varianter före → efter | Manuella varianter före → efter, efter deduplicering | Datumgiltiga unika varianter i OWN/PU före → efter |
|---|---:|---:|---:|---:|---:|
| Willys Hemma, fyra sidor | 34 annonser | 7 → 13 | 7 → 16 | 17 → 8 | 24 → 24 |
| Willys, tolv sidor | 112 annonser | 29 → 42 | 29 → 46 | 35 → 18 | 64 → 64 |
| Lidl v39, sparade 28 sidor | 380 unika strukturerade käll-ID | 0 → 14 dokumentbindningar | 0 → 14 | 3 → 3 | 3 → 17 |

För Willys är 9 respektive 17 livsmedelsvarianter nytillkomna i automatiken, samtliga tidigare manuellt godkända. Antalet manuella annonser minskar 12 → 6 respektive 29 → 16. Okända variantgrupper betyder att totalantalet verkliga produktvarianter bakom alla 34/112 annonser inte kan fastställas. För Lidl är 380 käll-ID inte ett påstående om 380 bevisade nationella produktvarianter eller 380 dokumentannonser.

Alla kvalificerade poster har behandlats: Willys 208 butiksposter och Lidl 170 i det frysta efterprovet. Dubbletter över butiker räknas inte som förbättrad produkt-/annonstäckning. [Butiker och officiella länkar](STORES.md), `comparison.json`, `verification-1281.json`, `verification-1280.json`.

## Vad ändrades för Willys?

`flyer_text.py`, regler v3, använder samma textläsning, connector och prisavtal. Kontrollerade ändringar:

- Rubriken kan fortsätta på flera rader med samma rubriktypografi. Den andra rubrikraden blir inte längre ett påhittat varumärke.
- Historiska 30-dagarsprisintervall skiljs från förpacknings-/variantintervall. Historiska priser blir aldrig ordinarie köppriser.
- Uttrycklig fetthalt, lagringstid, skivning och pluralformen djupfrysta bevaras. Okänd resterande text stoppar fortfarande raden.
- Slutna, utskrivna alternativ inom samma egenskapsdimension kan delas, exempelvis normalsaltat/extrasaltat. Ingen öppen "olika sorter"-grupp godkänns och två tvetydiga variantdimensioner kombineras inte.
- Prisrutan får överlappa en kompakt annons vertikalt men begränsas till lokal annonsrad. Jämförprisets aritmetik och entydig pris-/annonskoppling krävs fortfarande. Detta löser exempelvis Hemma-bladets pizzadeg och falukorv utan att låna en annan annons pris.

Den äldre granskningen är kontrollfacit i tester, inte indata till dessa regler. `willys-manual-v-auto.json` visar varje tidigare manuellt godkänd annons och den kvarvarande automatiska orsaken. Gamla hashbundna godkännanden används bara av den redan befintliga, separata reservvägen.

Kvarvarande automatiska bortfall, exklusiva huvudorsaker:

| Orsak | Hemma | Tolvsidigt |
|---|---:|---:|
| Variant-/mängdintervall eller ungefärlig mängd | 8 | 40 |
| Okänt villkor/variant i texten | 3 | 9 |
| Webbvisare och PDF avviker | 0 | 8 |
| Pris-/annonskoppling inte entydig | 3 | 5 |
| Pant kräver ytterligare belägg | 3 | 3 |
| Okänd närliggande prisruta | 1 | 2 |
| Okänd textstruktur | 2 | 2 |
| Köpgräns uttryckt i annan enhet | 1 | 1 |
| Summa inte automatiskt godkända | 21 | 70 |

Dessa antal inkluderar fortfarande manuellt godkända fall. De ska inte summeras med separat manuell karantän. Bildinnehåll har inte tolkats; antalet enbart bildbaserade annonser är okänt. En annan verklig Willys-kampanjvecka har inte blivit tillgänglig i det sparade/officiellt tidigare kontrollerade underlaget. Två format av v39 är inte bevis för en ny kampanjvecka.

## Vad ändrades för Lidl?

Utgångspunkten är verifierad: 3 godkända + 348 utan granskad bindning + 27 oprövade prisfält + 1 oprövat rabattvillkor + 1 jämförprisintervall = 380. De två sista posterna får inte döljas i avrundningen.

`document_qualification.py` använder en komplett typografiskt avgränsad varumärkes-/produktrubrik, bokstavlig entydig förpackning och en unik strukturerad identitet. Pris används först efter identitetsbindningen. Dokumentets prisruta, pris, jämförpris där det finns, sidans kampanjdatum och lokala villkor kontrolleras separat. Nationell giltighet kommer från den aktuella officiella publikationens uttryckliga omfattning. Den tilldelas endast kvalificerade produkter, aldrig hela regionflödet. Förpackade vätskor utan bevisad tillämpning av pantregler spärras.

Automatiken har inga produkt-ID:n, GTIN, veckolänkar eller godkännandelistor. Kontrollsiffergiltig GTIN kommer fortfarande enbart från uttryckligt EAN-fält, inte från källans produkt-ID. 140 av 378 parsade poster saknar godkänd GTIN; 12 av dem är livsmedel med prisgiltighet vid observationen. Ingen av dessa har klarat den oberoende kompletta dokumentbindningen (bland annat viktvaror, ofullständig rubrikbindning och pant). Att bara slopa GTIN-kravet gav därför inget belagt ytterligare importfall; kontraktet har inte försvagats. Tidigare manuella godkännanden ligger separat och kräver exakt gammal dokumenthash. Alternativet v2 samexisterar med tidigare v1-snapshots i OWN och PriceUniverse.

`collect_lidl_municipality` upptäcker aktuell nationell publikation från officiella listningen. Hämtad och återspelad PDF binds till publikationens URL och faktisk hash. Oklar aktuell publikation stoppar källan säkert. Bounded transport och befintlig behovsstyrning används vidare.

De 348 tidigare obundna posterna är uppdelade utan dubbelräkning i `lidl-348-dispositions.json`:

- 14 får automatisk dokumentbindning och köpimport.
- 231 är inte giltiga vid den ursprungliga verkliga observationen; denna tid flyttas inte fram.
- 62 saknar fortfarande exakt komplett varumärkes-/variantrubrikbindning.
- 24 saknar verifierad livsmedelsklassning för denna prioriterade väg.
- 4 har avvikande/flera förpackningsmängder, 4 okänt variant-/villkorstext, 3 oprövad panttillämpning för vätska, 3 saknar fast enskild förpackning, 2 tvetydig prisruta och 1 ett kritiskt sidvillkor.

De 27 oprövade prisfälten är `priceLegendName`/`priceLegendText`: texten undantar angivna butiker i Stockholm och Göteborg. Fälten kan nu läsas med typkontroll, och undantagen bevaras som geografiska villkor. Samtliga 27 gäller icke-livsmedel, exempelvis kläder och hushållsartiklar. Ingen har fått automatisk butiksgiltighet eller köpimport. Parserökningen 351 → 378 är alltså inte prisimportökningen. Efterprovet har fortfarande 363 ej importerade kandidater: 334 återstående från gruppen 348, dessa 27 samt de två andra parserfallen.

## Aktuell revision och oberoende nästa kampanj

12 verkliga nätanrop hämtade den aktuella listningen, tre publiceringsmetadata, PDF och det strukturerade produktflödet. Aktuell PDF har 29 sidor och annan hash än de sparade 28 sidorna. Den innehåller 14 automatiskt kvalificerade livsmedel; de tre gamla manuella godkännandena ärvs inte. Samtliga 14 går genom OWN/PU i båda kommunerna (28 butiksposter/16 auditgodkända köp i Lund, 112/64 i Malmö, 0 nya näringsgodkännanden) i `lidl-current-1281` och `lidl-current-1280`. Detta är separat från den frysta 3 → 17-jämförelsen.

Ytterligare två verkliga nätanrop följde en faktiskt publicerad relaterad länk till v40, 28 september–4 oktober. Samma regler prövades före någon produktlista för den utgåvan: 142 typografiska kandidatrubriker, fyra kvalificerade dokumentbindningar, 138 kvar för annan tolkning/granskning. Dessa fyra är skivat stekfläsk 375 g/27,90 (Lidl Plus), kryddig grönsaksröra 540 g/59,90, rökt korv 330 g/34,90 och dumplings med plommon 1 kg/39,90. De är korrekt spärrade från dagens köpimport: 0 aktuella PU-poster. Testet bevisar textgeneralisering och datumstopp, inte ett framtida faktiskt genomfört driftbyte. `lidl-holdout` innehåller råmetadata, PDF, observation och beslut. Inga observationer har föryngrats.

## Köp, produktfakta och näring

Den frysta jämförelsen går genom riktig collector, radvalidering, SQLite/OWN, ordinarie PU-byggare, ProductMatcher, användarprissättning, BasketCalculator och BasketAuditor. Båda kommunerna har två reproducerbara PU-rebuilds med oförändrade produktdata: Lund 58 poster, Malmö 320. Alla produkter prövas, men matcheravslag behålls. Köpantal inkluderar butiksposter och är inte produktökning: 39 respektive 223 auditgodkända listköp. I dessa ingår även bevarade gamla erbjudanden; alla räknas inte som nykvalificerade livsmedel.

Representativa automatiskt nykvalificerade exempel, 21–27 september, publika villkor utan separat belagd köpgräns:

| Källa | Produkt och förpackning | Köpavtal | Verifiering |
|---|---|---|---|
| [Willys Hemma Stortorget](https://reklamblad.willys.se/willys/2863/) | Garant Smör & raps normalsaltat, 600 g | 44,90 kr/förp | matcher, checkout, audit; ingen godkänd näringsdeklaration |
| [Willys Hemma Stortorget](https://reklamblad.willys.se/willys/2863/) | Garant Jamon Serrano skivad, 11 månader, 100 g | 2 för 40 kr; obelagt restköp spärrat | matcher, checkout, audit; ingen godkänd näringsdeklaration |
| [Willys Rosengård](https://reklamblad.willys.se/willys/2352/) | Garant Crème fraiche 32 %, 500 ml | 23,90 kr/förp | matcher, checkout, audit; ingen godkänd näringsdeklaration |
| [Lidl Kalkonbröstfilé](https://www.lidl.se/p/butcher-s-kalkonbrostfile/p11209202) | Butcher's, 1 kg | 99 kr/förp | matcher, checkout, audit; ingen godkänd näringsdeklaration |
| [Lidl Paella](https://www.lidl.se/p/sol-mar-paella-med-skaldjur/p11005814) | SOL&MAR Paella med skaldjur, 500 g, ID 11005814 | 27,90 kr/förp | matcher, checkout, audit; färdigrätt, inte rått ris |
| [Lidl Piri piri-sås](https://www.lidl.se/p/sol-mar-piri-piri-saas/p11039774) | SOL&MAR Piri piri-sås, 195 ml, ID 11039774 | 11,90 kr/förp | matcher, checkout, audit; ingen godkänd näringsdeklaration |

Ordinarie köppris förblir okänt. Fulla prisavtal, kampanjbevis, förpackningar och observationer finns i respektive `verification*.json`. Prisgodkännande ger ingen automatisk recept- eller näringsbehörighet. Nya produkter har 0 nya näringsgodkännanden. Befintlig exakt Pågen-deklaration används fortsatt för det gamla, kompatibla Lingongrova-erbjudandet i den frysta jämförelsen. Ostsnacks/kroketter blir inte ost och paella blir inte rått ris genom prisimporten.

## Drift och återstående status

189 unika riktade/regressionstester passerar, inklusive källpris, fel variant/förpackning/varumärkesgräns, medlemsvillkor, datum, butiksurval, hushållsgränser, nytt dokument utan manuell lista och fel källbindning. Ruff och compileall passerar. JUnit-filerna är bevarade; överlappande testkörningar summeras inte.

Privat avsedd runner/CLI/app-start verifierar publicering, HTTP-reload, normal rebuild, omstart, status, hämtfel/LKG och återhämtning. Slutkodens accepterade faser är `restart`, `not_due`, `fetch_fail`, `recovery`; de två sistnämnda innehåller fulla normala rebuilds. Första import/publicering och andra rebuild kördes före de sista skärpningarna av Lidl-källkontrollen och är märkta mellanliggande kod i `runtime-1280/ACCEPTANCE.json`. De nya skärpningarna har separat slutkodstest och aktuell import. Inga externa nätförsök skedde i driftreplayen. Alla produkt-/observationssignaturer bevarades, inklusive 184 Willys- och 136 Lidl-butiksposter samt den befintliga City Gross-basen.

Första behovskontrollen behövde initiera saknad publiceringsstatus genom lokal rebuild. Detta misslyckade no-work-påstående är sparat som `demand_bootstrap`. Den efterföljande riktiga no-work-kontrollen passerade på cirka 12 sekunder utan child/rebuild/prisanrop. Det döljs inte som en omedelbart fungerande första kontroll.

Lidls separata vanliga källjobb prövar fel med bibehållen giltig snapshot, återhämtning till den faktiskt hämtade nya revisionen, omstart/not_due samt utgång med testklocka. Återhämtningen är replay av verklig hämtning, inte ett påstått nytt nätanrop vid felprovet. Se `lidl-recovery-verification.json`. Framtidsklockor och felinjektioner ändrar inga observationer.

Basfärskheten har räknats om inför slutprovet: City Gross-basen i privat Malmö-prov är FRESH (cirka 31 timmar), Lunds sparade Willys-onlinebas STALE (cirka 63 timmar). Fullständigt Malmö-publiceringsprov med aktuell komplett bas inklusive övriga baskällor/Primat är fortfarande separat och inte påstått genomfört här.

Nästa behovskontroll enligt oförändrade 35 timmar: Willys cirka 25 september 20:40–20:41 svensk tid; fryst Lidl-underlag 25 september 04:45; dagens Lidl-hämtning 26 september 03:35; City Gross 24 september 21:04. Dessa är källberäkningar, inga aktiverade scheman. Kampanjbyte och 48-timmarsstopp gäller fortfarande. `source-freshness.json`/`base-freshness.json` innehåller exakta tider.

Kvar: Willys nettotillskott av unika priser (om det krävs utöver ökad automatisk täckning), osäkra annonser enligt orsakerna ovan, verklig annan Willys-kampanjvecka, fullständig aktuell Malmö-bas och integration, samt det historiska Lidl-nutritionstestets saknade `reports/source-implementation-20260915/lidl_offer_adapter.py`. Dess tidigare testlucka är inte räknad som löst eller inkluderad bland passerade tester. Ingen generell release-/produktionsaktivering ges av denna rapport.
