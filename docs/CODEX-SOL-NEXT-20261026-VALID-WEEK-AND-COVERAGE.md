# Sol: fler köpbara varianter och en verifierad personlig veckoplan

Ägarens uppdrag efter granskningen av PR #16, main `c94c229`, 2026-10-26.
Arbeta i `D:\Projects\Smako`. Hämta aktuell main utan att skriva över
andras ändringar. Läs AGENTS, DEVELOPMENT, PRODUCT-GOAL,
PLANNING-ARCHITECTURE och HANDOFF. Detta dokument ersätter
[WEEK-SEARCH](CODEX-SOL-NEXT-20261026-WEEK-SEARCH.md) som nästa uppdrag.

Genomför en avgränsad leverans med fyra delar: lös konflikten mellan
uttryckliga val och standardvariation, täpp till tidsgränsen vid omräkning,
förbättra och mät individuell köpbarhet, och pröva en fullständig vecka.
Behåll arbetet från PR #16; börja inte om med en ny generell arkitektur.

## 1. Vad som redan är visat

Läs [PR #16:s rapport](reviews/week-search-and-cache-20261026.md) med
`B-frontier-review.json` och föregående
[köpbarhetsrapport](reviews/recipe-quality-and-planning-20261026.md).

- 2 462 aktiva varianter/934 registrerade grundrätter, inklusive de 2 200
  importerade varianterna. Inga nya recept behövs för nästa mätning.
- De sex spettvarianterna och de tre rågbrödsvarianterna är korrigerade.
  Oberoende granskning på main gav 80 godkända riktade tester. Bevara
  innehållsrättningarna, historiska bytes och sparade referenser.
- Senaste helhetsinventering: **733/2 200 exakt (33,3 %), 920/2 200 med
  uttryckligen tillåtna mängduppskattningar (41,8 %)**. De 920 inkluderar
  exakta fall. Föregående nivå var 704/888; nettoökningen är 29/32.
  PR #16 har inte inventerat om detta efter det striktare rågbrödskravet.
  Siffrorna är historisk individuell produktlösbarhet, inte personligt
  närings-/allergen-/ekogodkännande eller antal möjliga veckoplaner.
- Förberedelse 95,97 s; ny process 4 926 cacheträffar utan missar. Det är
  ett användbart framsteg, men ingen uppmätt verklig veckouppdatering.
- B gav **avslag efter 45,10 s**, ingen slutkontrollerad eller sparad
  veckolista. Minskat sökarbete är inte lyckad användarlatens eller prisparitet.
- B har **52**, inte 55, tillåtna butikskontexter. De sparade anropen är
  oförändrade. Rättelsen får inte användas för att byta butiksurval.

## 2. Lös standardkonflikten innan fler dyra veckoprov

B kräver fem middagar för fyra, tre kyckling/två vegetariska,
grekiskt/italienskt, protein minst 35 g och högst tre middagar per
huvudprotein. Samtidigt gäller det separata
`max_same_primary_ingredient_meals=2`. Av de 29 kvalificerade recepten
(25 kyckling/fyra vegetariska) gav ingen av 13 800 kombinationer en
strukturellt giltig meny. Detta gäller den observerade poolen, inte alla
tänkbara recept-/produktval i hela biblioteket.

Spåra och rätta sambandet mellan UI, requestnormalisering, sparat intent
och upplöst variationspolicy. Berörda ingångar finns i `models/plan.py`,
`models/recipe_preferences.py`, `services/diversity_policy.py`,
`services/meal_plan_optimizer.py`, `services/menu_optimizer.py`,
`services/complete_recipes.py` och `static/complete-recipes.js`.

Beslut för nya V2-anrop: **uttryckliga användarval går före motsvarande
ärvda standardvariation**. En dold standard får inte oväntat göra det
uttryckliga valet omöjligt. Detta ger ingen rätt att ignorera ett annat
uttryckligt hårt krav. Huvudprotein, huvudråvara och grundrätt är skilda
begrepp; dokumentera deras verkliga klassificering innan reglerna ändras.

- Bevara vilka värden som är uttryckliga respektive härledda. UI får inte
  göra samtliga förifyllda standarder till skenbart uttryckliga val.
- Redovisa effektiv variationsregel och eventuell anpassning av standarden
  begripligt för användaren, och spara den med den nya planen. Ändra bara
  den standard som faktiskt kolliderar; behåll andra gällande gränser.
- Två motstridiga uttryckliga krav ger ett tidigt konkret konfliktbesked.
  Automatiskt borttagna närings-, kost-, allergi-, eko- eller butikskrav
  är inte en lösning. Ändra inte legacy/V1 eller gamla planers betydelse.
- För äldre serialiserade anrop där ursprunget till ett värde är okänt:
  gissa inte att det var en standard. Bevara historisk tolkning; ett nytt
  dokumenterat val krävs för att ändra innebörden vid omräkning.
- Inför billiga, säkra förkontroller där konflikten går att bevisa med
  faktisk klassificering och kapacitet. En ofullständig shortlist eller
  misslyckad beam-sökning får aldrig bli ett globalt omöjlighetsbevis.
- Testa UI → request → effektiv policy → save/GET, uttryckligt mot
  standard, två uttryckliga gränser, blandproteiner, basupprepning och
  gamla sparade anrop. Dokumentera beslutet i PLANNING-ARCHITECTURE.

Behåll original-B och dess normaliserade krav oförändrade som negativt
regressionsunderlag. Återanvänd dess kvitton; starta inte samma dyra sökning
igen för att upptäcka samma konflikt. Skapa ett separat **B2** för den nya,
avsiktliga policyn och redovisa exakt skillnad mot B.

## 3. Samma tidsgräns när en sparad plan räknas om

Granskningsfynd: `POST /personal/plans/{plan_id}/change` går i
`backend/app/api/personal.py` genom `_run_personal_work` och
`_run_personal_thread` till `PersonalPlanner.create` och sedan
`plans.append`, utan motsvarigheten till `_with_current_deadline` i
`api/plan.py`. Vid granskningen låg planner-anropet omkring rad 388.
Ett litet prov med simulerad klocka gav `deadline_in_worker=None` och
fortsatte efter 61 s; motsvarande skyddade anrop gav `SEARCH_INCOMPLETE`.

Återanvänd befintlig deadline-/avbrottsmodell för opt-in
`smako-current-library-v2`. Skydda relevanta personliga ändringsflöden,
inklusive omräkning och recept-/produktbyte, både direkt och som jobb.
Budgeten ska följa hela operationen genom admission, tråd, sökning,
checkout/audit och lagring. Starta inte en ny full tidsbudget i varje led.
Redovisa kötid och eventuell kvarvarande skillnad mellan serverbudget och
produktens klick→färdig-lista-mål; ett snabbt jobb-ID är inte färdigt resultat.

Testa med simulerad klocka så att proven inte behöver vänta en minut:
deadline i arbetstråden, direkt/async-flöde, stopp i dyra loopar,
lagringsfas, vanlig avbrytning, ägarscope och oförändrat legacybeteende.
Behåll revisions-/idempotensreglerna. En timeout får inte lämna en
ofullständig revision; om en fullständig lagring redan hunnit committa
måste återförsök och status hantera den konsekvent, inte skapa dubbelversion.
Enbart kontroll efter avslutad lång beräkning är otillräckligt.

## 4. Öka köpbarheten där underlaget räcker och mät alla 2 200

Prioritera en liten insats med stor möjlig effekt, inte fler recept eller
en ny importomgång. Använd befintlig inventerare, pris-/faktakoppling och
bevarat Malmöunderlag med samma testklocka, butiker och mängdpolicy.
Utgå från `recipe-quality-and-planning-20261026/HINDER.md`.

De tidigare största överlappande grupperna är limejuice 445 varianter,
ingefära 402, salladslök 139, mynta 131 och purjolök 111. Dessa antal får
inte summeras till en förväntad vinst: ett recept kan ha flera luckor.
Rangordna i stället efter hur många fullständiga varianter en verifierad
rättning faktiskt kan frigöra. Ta högst två eller tre välavgränsade grupper.

- Granska först befintligt behörigt källmaterial. Limejuice behöver rätt
  innehållsbevis; en produkt med rätt namn är inte automatiskt ren juice.
  Hel ingefära, knippen och krukor ger inte automatiskt exakt ätlig mängd.
- Förbättra definitioner, exakta produktkopplingar och mängdomvandlingar
  bara där identitet, form, enhet och källbevis räcker. Estimated får
  användas endast genom befintlig uttrycklig policy och med synlig status.
  Gör inte uppskattningar till exakta värden för att höja procentsatsen.
- Bevara smak, beredning, näring och ingrediensantal. Ett faktiskt
  receptbyte kräver normal innehållsgranskning och ny version; ingen
  massomskrivning till andra råvaror för att skapa en grön inventering.
- Begränsa dyr inventering/profilering för denna del till högst 12 minuter
  av kvarvarande journal, så att veckoprovet får utrymme. Börja inte en
  bred ny insamling. Om nödvändigt källstöd saknas, skriv exakt vilken
  deklaration/mängdbasis som behövs och gå vidare utan påhittade fakta.

Gör en aktuell inventering av **samtliga 2 200 importerade varianter**,
separat från de 262 ursprungliga. Återanvänd befintliga resultat endast
om beroenden och inventeringens innebörd är oförändrade och verifierade.
Spara både exakta och estimated-utfall, ID-listor/kompakta deltan,
kvarvarande hinder och bibliotek-/käll-/metodhashar. Redovisa nytillkomna
och förlorade fullständigt köpbara varianter, även effekten av rågbrödskravet.
Skilj mellan historisk 733/920, aktuell nivå före nya kopplingsändringar
och deras verkliga effekt; en förändrad räknedefinition är ingen vinst.
Ingen bestämd ökning lovas innan underlaget är kontrollerat.

## 5. Verifiera en verklig vecka, inte ännu ett snabbt avslag

B2 ska behålla B:s fem middagar/fyra portioner, tre kyckling/två
vegetariska, grekiskt/italienskt, minst 35 g protein, högst tre samma
huvudprotein, samma 52 tillåtna butiks-ID:n, inköpstak två och samma
uttryckliga estimated-val. Ändra bara den dokumenterade konfliktens
standardregel enligt avsnitt 2. Lagra råa val, fältursprung, normaliserad
begäran och effektiv policy. Detta är ett nytt acceptansfall, inte
bevis på förbättring för ett oförändrat B.

1. Kontrollera först att strukturell kapacitet finns med de nya reglerna.
   Bevara giltiga produktalternativ; ett gammalt individuellt kvalificerat
   delurval får inte tyst bli hela sökdomänen. Kör ett budgeterat B2 efter
   de konkreta rättningarna, med delat förberett underlag och en ny personlig
   begäran. Identisk färdigplanscache räknas inte som prestation.
2. Framgång kräver fullständiga recept, exakt gemensam checkout,
   kontroll av samtliga gällande krav, sparad lista och korrekt GET.
   Redovisa totalpris, faktisk protein-/näringsstatus, butikstak,
   kandidater efter filter, sökta kombinationer, fas-/totaltider och minne.
   Skilj bästa hittade meny från bevisat globalt billigast.
3. Vid lyckat B2 inom 60 s: gör ett verkligt browserprov av veckan och
   därefter ett avgränsat A om budget finns. Räkna knapptryck, kö,
   transport, save och synlig full lista. Endags-F:s 28,10 s ersätter
   inte detta. Enstaka prov är inte p95 eller kapacitetsgaranti.
4. Prisjämförelse kräver identiska krav, källor, bibliotek och datum.
   Återanvänd matchbar tidigare giltig vinnare; om sådan saknas, ange det.
   Behåll små uttömmande korg-/menyorakel och noll oförklarade
   prisregressioner. B:s avslag innehåller inget pris att jämföra med.
5. Om B2 inte ger en giltig vecka: redovisa exakt kvarvarande data-,
   policy- eller sökhinder och nästa minsta åtgärd. Kör inte identiska
   timeouter och byt inte till lättare personliga krav för att rapportera PASS.

## 6. Budget och leverans

Fortsätt samma `docs/reviews/recipe-integration-800-20261025/budget.json`:
senast **4 226,3128 s använda / 2 973,6872 s kvar (49,56 min)** av totalt
120 minuter. Läs aktuellt saldo; nollställ eller utöka inte budgeten.
Detta är mätbudget, inte ett påstående om total utvecklingstid.

Använd `scripts/recipe_layer/budgeted_check.py`, gemensamt OS-lås, en dyr
arbetare, två CPU och hårt 3 GiB commit. Minnesmål högst 2,5 GiB inklusive
versionsöverlapp kvarstår. Debitering inkluderar start, dataladdning,
förberedelse, inventering, profilering och misslyckade försök. Ange separata
stoppgränser före start; användaranrop har mål 60 s och testövervakare
senast 75 s. Återanvänd känd förberedelse när beroendena tillåter det.
Ingen gammal 252-cellsmatris, duplicerad 5 000-katalog eller nattlig fortsättning.

Kör fokuserade regressioner, Ruff/compileall för berörd kod och ordinarie
CI inklusive berörda browserprov. Dessa är separata från mätbudgeten;
göm inte mätkörningar bland enhetstester. Sluta med delrapport om budgeten
tar slut. Integrera verifierade commits på main enligt DEVELOPMENT.

Skriv `docs/reviews/valid-week-and-coverage-20261026.md` med kompakta
maskinkvitton och uppdatera HANDOFF. Rapportera tydligt: aktuell köpbarhet
av 2 200 och faktisk nettoändring, policybeslutet, deadlineprov, B2:s fulla
utfall och pris, klicklatens om mätt, återstående hinder och budgetsaldo.
Om ingen köpbarhetsökning eller lyckad vecka kunde visas ska det sägas direkt.

Behåll `legacy` som standard, `library_merge_generations=False` och den
nya sökvägen opt-in. Ingen beta-/produktionsaktivering, schedulerändring,
profiländring eller bred prisinsamling ingår.
