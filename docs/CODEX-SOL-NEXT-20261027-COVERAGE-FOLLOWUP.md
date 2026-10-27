# Sol: rätta mängdspärren och fortsätt mot full recepttäckning

Ägaren har godkänt nästa steg efter granskningen av PR #19 och bett att
arbetet lämnas till Sol. Utgå från senaste main i `D:\Projects\Smako`;
granskad runtime är `7c0e066`. Läs AGENTS, HANDOFF, PRODUCT-GOAL,
PLANNING-ARCHITECTURE och DEVELOPMENT. Detta är nästa avgränsade etapp
inom målet att göra alla 2 200 importerade varianter användbara.

## 1. Rätta den reproducerade mängdkonflikten först

I `official_product_facts.project_usable_quantity` anropas
`project_reviewed_quantity` och dess resultat returneras före kontrollen
`_mass_blocking(fact.conflicts)`. Den nya vägen använder i stället
`identity_conflicts`, som undantar alla konflikter med prefixet `nutrition.`.
Det är för brett för att godkänna en mängdberäkning.

Reproducerat med samma slags isolerade salladslöksfixtur som i
`backend/tests/test_recipe_coverage_review.py`: en granskad 100-g-förpackning,
styrkt identitet och dokumenterat 96-procentigt utbyte ger 96 g i estimated.
Lägg till `conflicts=('nutrition.package_quantity',)` i de i övrigt lika
fakta. Befintlig `_mass_blocking` säger att konflikten blockerar, men den
nya projektionen ger ändå 96 g och `links.compatible` accepterar relationen.
Detta är ett reproducerat skyddsfel, inte ett belägg för att samma konflikt
finns i de 1 569 uppmätta korgarna.

Återanvänd den befintliga mängdkonfliktspolicyn även för den nya vägen.
Låt inte ett allmänt prefixundantag eller en alternativ ingång kringgå
den. Duplicera inte två listor över tillåtna konflikter som sedan kan glida
isär. En konflikt som rör mängd, identitet eller ett okänt förhållande
ska stoppa den ifrågasatta mängdprojektionen. Kända rena näringskonflikter
ska fortsatt kunna hanteras separat; de godkänner inte personliga näringsmål.

Lägg till regression som fallerar före och passerar efter rättningen.
Täck åtminstone `nutrition.package_quantity`, `package_quantity`,
`usable_quantity`, en okänd konflikt och en verklig näringskonflikt såsom
`nutrition.protein_g`. Kontrollera både projektion och efterföljande
kvalificering: ett motsägelsefullt underlag får inte bli ett godkänt
uppskattat köp. Testa även normal uppskattning utan konflikt, exact utan
samtycke samt prisuppdatering med oförändrad produktidentitet.

Flytta inte ett ovillkorligt krav på att fakta finns framför all projektion:
vissa granskade hela råvaror kan ha giltiga separata identitetsbevis utan
kompletta näringsfakta. Skyddet ska stoppa motsägelser, inte avskaffa den
godkända uppskattningsvägen. Kontrollera att faktisk data med en konflikt
inte återanvänds från en cache under en annan beroendeversion.

## 2. Förbättra återstående ingrediensstöd

Utgå från [PR #19-rapporten](reviews/recipe-coverage-20261027.md),
[alla 2 200 utfall](reviews/recipe-coverage-20261027/coverage.json) och
[blockerlistan](reviews/recipe-coverage-20261027/blockers.json).
Oberoende granskning har kontrollerat alla sparade korgkvittors SHA,
aktuella metod-/recept-/villkorsberoenden, audit och butikstak samt rätt
portionsmängder. 626 riktade tester passerade. GitHub-CI kunde inte läsas
oberoende i granskningssessionen; Sols integrationsrapport anger grön CI.

Fast utgångspunkt är **969 exakt/1 569 inklusive uppskattningar individuellt
lösta varianter**, samt **967/1 569 verifierade tvåbutikskorgar**. Estimated
inkluderar exact. 631 varianter har kvarstående insatshinder; två andra
har exakt insatsstöd men saknar verifierad exakt tvåbutikskorg.
De två trebutiksproven ersätter inte dessa tvåbutiksutfall.

Prioritera nedanstående grupper. Sista kolumnen är en villkorad övre
marginal om hela gruppens relevanta scope kan lösas, ingen utlovad vinst.

| Grupp | Blockerade varianter i estimated | Enda kvarvarande grupp |
| --- | ---: | ---: |
| Mynta | 131 | 83 |
| Tamarindpasta | 93 | 53 |
| Masa harina | 31 | 31 |
| Avrunnen mozzarella | 30 | 30 |
| Pärlkorn | 27 | 24 |

Dessa fem kan som mest frigöra 221 varianter som bara saknar respektive
grupp; fler kombinationer kan påverkas men får inte dubbelräknas.
Fortsätt med exempelvis citrongräs eller andra dokumenterat lösbara luckor
när marginalnytta och tillgängligt underlag motiverar det. Låt inte en
svår första grupp hindra andra färdiga förbättringar.

Återanvänd redan granskade dokument och sök först i befintligt prissatt
sortiment. Komplettera exakt artikel-/GTIN-bundna fakta via befintlig
godkänd Axfood-kedja eller relevanta offentliga tillverkardeklarationer.
Inga nya butiksscope, breda crawlar eller driftändringar ingår.

- Mynta behöver användbar bladmängd eller ett belagt utbyte för just den
  köpta presentationen; 25 g klippt mynta, rotad kruka och torr mynta skiljer sig.
- Tamarindkoncentrat i ml är inte automatiskt samma sak som kärnfri osötad
  pasta med rätt styrka i g. Styrk produkt, styrka och mängd var för sig.
- Masa harina ska vara rätt nixtamaliserat majsmjöl; masala, polenta och
  vanligt majsmjöl ger inte den kopplingen.
- Mozzarella behöver belagd användbar/avrunnen vikt, inte bara bruttovikt i lag.
- Pärlkorn behöver rätt bearbetad kornform och köpbar mängd, inte en liknande etikett.

Om ett nytt sortiment behövs: dokumentera exakt saknad vara, tänkt källa
och vad som skulle ändras. Blanda inte in det tyst i den frysta referensen.
Skriv inte om recept eller minska nämnaren för att nå ett procenttal.
Efter cirka 15 minuters fruktlös undersökning av en grupp, spara vad som
redan prövats och gå vidare till nästa konkret lösbara grupp.

## 3. Ny avgränsad budget och verifiering

Ägaren har godkänt fortsatt arbete och en ny begränsad budget. Denna
uppdragsfördelning sätter taket till **1 200 sekunder, 20 minuter**, för
nya tunga käll-/inventerings-/korg-/API-körningar. Använd den separata
[fortsättningsjournalen](reviews/recipe-coverage-followup-20261027/budget.json)
med `budgeted_check.py --budget ...`. Den gamla 120-minutersjournalen
bevaras orörd med 7 172,6967 s använda och 27,3033 s kvar; dess rest läggs
inte ovanpå det nya taket. Journalen anger ägarens godkännande och att
20-minutersbeloppet är denna etapps tilldelning, inte ett tidigare mätresultat.

En tung arbetare åt gången, två CPU, hårt 3 GiB och mål 2,5 GiB. Kontrollera
att ingen gammal journal/arbetare fortfarande kör. All ny laddning,
förberedelse, källhämtning/väntan, misslyckanden och upprepade mätningar
räknas. Öppna inte fler journaler när taket nås. Vanlig kodläsning och
riktade små regressionstester utan det stora prisunderlaget ligger utanför
denna tunga mätbudget. Ingen automatisk fortsättning eller gammal stor matris.

Reservera **tio minuter** av de tjugo för slutverifiering och eventuella
fel. Börja med regressionen för mängdspärren och små positiva/negativa
källfall. Samla källrättningar före en slutlig full insats-/korgkontroll,
med samma 2 200 ID:n, 52 butiker, portioner, tvåbutikstak och testklocka.
Använd rätt ny fakta-/metodversion. Återanvänd kvitton bara när samtliga
beroenden faktiskt matchar; inga omskrivna hashvärden på gammal verifiering.
Gör inte en ny full inventering efter varje artikel.

Efter samlade ändringar: ett A- och ett B2-prov om budgeten räcker.
Referenserna är A 290,82 kr/52,2790 s och B2 731,20 kr/32,6722 s,
med sparad plan/ägd GET och förberett underlag. Bevara hela sparade begäran
och B2-korgen när samma underlag används; jämför även tidigare giltig
A-kandidat via aktuell checkout om sökresultatet blir dyrare. Skala recept
till rätt portioner. Om källdata ändras, redovisa det som egen förändring.
API-tid är inte browsertid och A verifierar inte ett aktivt 10–15-krav.

Stoppa nya källförsök i tid för reserverad verifiering. Om budgeten inte
räcker till allt: leverera mängdrättningen och färdiga belagda förbättringar
med korrekt reststatus/checkpoint. En avbruten kontroll är aldrig PASS.
Förläng inte till en nattlig körning för att få ett grönt slutresultat.

## 4. Leverans

Implementera och verifiera mängdrättningen, integrera den och granskade
källförbättringar till main enligt repoets arbetsflöde, med relevanta
regressioner, Ruff/compileall och ordinarie CI på slutligt PR-huvud.
Håll mängdrättningen spårbar separat från berikningen. Uppdatera HANDOFF
och rapportera nya/förlorade ID:n, båda mängdlägenas insatsstöd och korgstöd,
källbevis, resthinder och faktisk förbrukad budget.

Rapportera en eventuell korrekthetsmotiverad minskning öppet; återställ
inte ett felaktigt godkännande för att hålla täckningstalet uppe. Fortsatt
mål är 2 200/2 200, inte bara de fem första grupperna. Legacy förblir
standard, V2 opt-in och ingen beta-/produktionsaktivering ingår.
