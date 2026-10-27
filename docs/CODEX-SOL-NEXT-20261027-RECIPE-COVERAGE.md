# Sol: gör alla 2 200 importerade receptvarianter användbara

PR #19/main `7c0e066` gav ett verifierat delresultat. Ägaren har därefter
godkänt [COVERAGE-FOLLOWUP](CODEX-SOL-NEXT-20261027-COVERAGE-FOLLOWUP.md)
som nästa etapp: mängdkonfliktsspärren först, sedan prioriterade källgap,
med separat begränsad budget. Målet och den fasta nämnaren nedan består;
den äldre budgeten förlängs inte genom denna hänvisning.

Ägarbeslut 2026-10-27 efter PR #18/main `fd2dcb8`: köpbarheten är för låg.
**Högsta prioritet är nu 100 procent användbara importerade varianter.**
Arbeta i `D:\Projects\Smako`, hämta senaste main och följ AGENTS,
DEVELOPMENT, PRODUCT-GOAL, PLANNING-ARCHITECTURE och HANDOFF. Detta ersätter
BROAD-WEEK som nästa uppdrag. Implementera förbättringarna och redovisa
faktiska vinster; stanna inte vid ytterligare en lista över kända luckor.

## 1. Korrekt utgångspunkt och vad 100 procent betyder

Alla 2 200 importerade varianter är aktiva; med tidigare 262 är biblioteket
2 462. [Inventeringen](reviews/valid-week-and-coverage-20261026/purchase-coverage.json)
och [rapporten](reviews/valid-week-and-coverage-20261026.md) är utgångspunkt.
PR #18 ändrade inte dessa kopplingar eller källdata.

| Mått, fast nämnare 2 200 | Exakt inköpsläge | Inklusive tillåtna uppskattningar |
| --- | ---: | ---: |
| Alla ingredienser individuellt produkt-/mängdlösta | 738 (33,5 %) | 931 (42,3 %) |
| Minst en ingrediens blockerad | 1 462 | 1 269 |
| Blockerade varianter med bara en blockerande ingrediensgrupp | 786 | 782 |
| Distinkta blockerande ingrediensgrupper | 104 | 99 |

931 inkluderar 738. Dessa tal bevisar varken en gemensam receptkorg inom
butikstaket eller personliga närings-/allergen-/ekokrav. De gäller fryst
Malmöunderlag med testklocka 2026-10-23, inte hela Sveriges aktuella sortiment.

Milstolpe ett: 2 200/2 200 varianter har verkliga tillåtna produkt- och
mängdkandidater för alla ingredienser. Slutmål: 2 200/2 200 har dessutom
en verifierad komplett receptkorg, inklusive förpackningar, giltiga priser
och slutlig audit. Redovisa båda måtten; kalla inte det första för det andra.
100 procent i exakt läge är inte bevisat av 100 procent med uppskattningar.
Det finns inget beslut om att byta standardläge eller godta uppskattningar
utan användarens val. Redovisa öppet vilka varianter som kräver sådana val.

Frys referensscopet före verifiering: samma namngivna Malmöunderlag och
ursprungs-ID:n, faktisk lista med butikskontexter, deklarerad fakta-/pris-
version/klocka, fyra middagsportioner respektive en frukost-/mellanmålsportion,
utan skafferi eller extra personliga begränsningar. Utgå från befintligt
butikstak två för den nya korgkontrollen. Ett vidare butikstak kan redovisas
separat men får inte ersätta ett misslyckat tvåbutiksfall i samma mått.
Nya källfakta får en ny redovisad version och före-/efterjämförelse.

Alla varianter behöver inte passa varje personligt val. Ett nötinnehållande
recept ska exempelvis fortfarande uteslutas när användarens allergikrav
kräver det. En faktisk saknad vara i ett valt område är ett datatäcknings-
eller sortimentshinder. Dölj inte det genom att minska nämnaren eller påstå
100 procent för en mindre lista. Bevara de ursprungliga 2 200 referenserna
även om en felaktig receptversion behöver rättas med spårbar ersättare.

## 2. Rätta kopplingsmodellen och fyll de gemensamma luckorna

Registret `backend/app/data/ingredients/intake-all-20261026.json` har 181
identiteter, varav **89 är `definition_only`**. Alla 89 återfinns bland
blockerande grupper i båda mängdlägena. `intake_product_links.py` accepterar
dem bara via `declared_definition`, som kräver en särskild
`manufacturer_culinary_declaration`, angiven användbar mängd/basis och
`quantity_confidence == exact`. Det innebär att den vägen inte kan lösa
en osäker inköpsmängd bara för att användaren tillåtit `estimated`.

Utred och rätta två olika slags hinder: saknat verkligt underlag respektive
underlag som finns men inte kan uttryckas/användas av kopplingsmodellen.
Kräv inte en artificiell tillverkardeklaration i Smakos format när samma
egenskap redan kan beläggas av exakta, granskade produktuppgifter.
Följ arkitekturtillägget för separata identitets-, form-, mängd- och
personliga bevis. Gör ingen generell `definition_only -> godkänd`-genväg.

Arbetsordning per ingrediensgrupp:

1. Läs befintliga exakta produkt-/butiks-/snapshotreferenser och tillgängliga
   källdeklarationer. Klassificera hindret: retrieval/alias, identitet/form,
   saknad sammansättning, mängd/enhet/utbyte, pris/scope eller verkligt
   sortimentsgap. Samma grupp kan ha flera olika kravscope.
2. Rätta kopplingar för redan belagda produkter i det befintliga registret
   och kvalificeringsflödet. Smak, konsistens, tillagning och verklig form
   måste passa receptet. Kompositprodukter får inte bli rena ingredienser.
3. Komplettera saknade fakta genom befintlig källkedja. Ägarens tidigare
   godkännande av Axfood-berikning gäller; återanvänd bevarade detaljer först
   och befintlig godkänd insamlare/scope för avgränsade relevanta luckor.
   Bevara bevis, produktidentitet, källtid och misslyckade/okända svar.
   Ingen bred ny crawl, nytt schema, utvidgat butiksscope eller driftaktivering.
4. När identiteten är styrkt men mängden osäker: stöd endast källbelagda,
   granskade uppskattningar i befintligt uttryckligt uppskattningsläge.
   Beräkna köpbar mängd och ätlig förbrukning separat; styrk utbytets
   tillämpningsområde. En okänd mängd utan underlag är fortfarande okänd.
5. Kontrollera berörda ingrediensscope och hela nytillkomna varianter.
   Spara positiva och negativa produktfall, faktareferenser och vilka
   tidigare lösta ID:n som eventuellt förloras. Mät marginalvinsten på hela
   varianter; summera inte överlappande ingrediensförekomster.

Att byta ingrediens, ta bort kryddor eller skriva om en rätt för att få ett
grönt tal är inte produktberikning. Rätta bara faktiska receptfel spårbart
med bevarad grundrätt och instruktioner. Bredare alternativa råvaror kräver
kulinariskt granskade, uttryckliga receptalternativ och egna konsekvenser
för mängd, näring och allergener; använd inte detta som första genväg.

## 3. Börja där hela recept kan frigöras

Följande kommer från befintlig inventering, ingen ny dyr mätning behövs för
att börja. Sista kolumnen är ett **villkorat övre antal**, inte en uppmätt
vinst eller ett bevis att rätt produktunderlag finns.

| Ingrediensgrupp | Blockerade varianter, uppskattningar tillåtna | Varianter där detta är enda blockerande gruppen |
| --- | ---: | ---: |
| Limejuice | 445 | 160 |
| Purjolök | 111 | 90 |
| Mynta | 131 | 50 |
| Pumpa | 65 | 36 |
| Tamarindpasta | 93 | 33 |
| Keso | 55 | 31 |
| Kvarg | 75 | 27 |
| Kapris | 55 | 26 |

Börja med dessa och närliggande råvarugrupper som kan dela belagd metod.
Salladslök blockerar också 139 varianter men behöver ofta kombineras med
andra rättningar. Ingefära blockerar 402 i exakt läge men har redan stöd
med uppskattningar: redovisa därför dess vinst i rätt kolumn. Uppdatera
prioriteringen när lösta kombinationer ändrar marginalnyttan. Slutmålet
omfattar även sällsynta ingredienser; enbart de största grupperna räcker inte.

En kompakt maskinläsbar lista ska täcka alla 2 200: ursprungs-ID, aktuellt
ID, exakta/uppskattade utfall, blockerande scope, nästa åtgärd, källbehov
och fullkorgens status/referens. Lista kompletta resthinder. Ge konkreta
besked när en extern källa saknas; gör inte samma fruktlösa sökning igen.

## 4. Verifiera riktat och återupptagbart

Använd samma delade journal
`docs/reviews/recipe-integration-800-20261025/budget.json`: vid uppdragets
start **1 855,0158 s (30,92 minuter) kvar** av 120 min. Kontrollera faktisk
journal innan start. Nollställ inte budgeten, öppna ingen parallell dyr
arbetare och återuppta inte den gamla stora matrisen. Tidsmålet 30–60 s
kvarstår; inga dygnslånga verifikationer för denna etapp.

Läs tidigare små rapporter och gör riktade tester först. Deduplicera
produkt-/mängdscope och återanvänd oförändrade bevis med korrekta hashar.
Samla en ingrediensfamiljs rättningar före ny full insatsinventering;
kör inte alla 2 200 efter varje enskild produktkoppling.

Bygg fullkorgskontrollen så den kan återupptas per variant/version med
korta tidsgränser. För denna täckningskontroll behövs en giltig köpbar
korg, inte tusentals omkörningar av bred femmiddagsoptimering. Använd
befintlig checkout/audit; en föreslagen tilldelning måste verifieras där.
Återanvänd fullkorgsbevis endast när samtliga lästa beroenden matchar.
Avbrott/ofullständig sökning är inte bevisad omöjlighet eller PASS.

Reservera minst sex minuter av kvarvarande tunga mätbudget för en samlad
efterinventering och begränsade slutprov. Kontrollera resursgränserna från
befintlig supervisor (två CPU, hårt 3 GiB, mål 2,5 GiB); räkna även laddning
och misslyckanden. Om fulla 2 200 korgbevis inte ryms: avsluta med ärligt
mätstatus/checkpoint och en kostnadsbedömd fortsättning, inte påstått 100 %.
Varken budgettaket eller ett godkänt delsteg ändrar slutmålet.

Testa fel produkt/form/enhet, rå/brutto/avrunnen/tillagad mängd, exakta kontra
uppskattade köp, förpackningsavrundning, saknad proveniens, motstridiga fakta,
allergen-/ekokrav och invalidering av förändrade produktfakta. Inga fabricerade
fält i produktionsdata; syntetiska fixturer bevisar kod, inte verklig täckning.

Efter en väsentligt större användbar pool: ett riktat A- och B2-prov om
budgeten medger, med före-/efterkällor och aktiva krav redovisade. Bevara
kända prisvinnare när underlag/krav är identiska. Gamla 55,12 s/297,18 kr
för A och B2:s 731,20 kr är referenser, inte nya mätresultat. Mer täckning
kan öka sökarbetet; lös inte det genom att gömma de nya recepten.
Rättelse av A:s rapport är gjord: råa globala 10–15 ingredienser var inte
effektivt aktiva. Nya ingrediensgränsprov måste sätta dem per måltid.

## 5. Leverans

Implementera, kör relevanta regressioner/Ruff/compileall och repoets
ordinarie CI, integrera granskat arbete till main och uppdatera HANDOFF.
Lämna fungerande kopplingar, spårbara fakta/mängdmetoder, återupptagbar
täckningskontroll och före-/eftertal med fasta ID:n. Separera redan löst,
nyligen löst, fortfarande blockerat och ännu inte fullkorgsverifierat.

Redovisa vad som återstår till 2 200/2 200 och den konkreta nästa åtgärden
per kvarvarande hinder. En mindre förbättring är ett delresultat, inte ett
avslutat 100-procentsuppdrag. Ingen standardväxling, betaaktivering eller
pris-/allergen-/ekolättnad ingår. Nästa prioritet är fortsatt täckningsgapet
tills det är stängt eller ett precist externt hinder kräver ägarens beslut.
