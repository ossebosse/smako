# Kategoriindelat recepturval, 2026-10-20

Analys av main `fcea66a`, efter frågan om en kycklingrätt, två vegetariska
och resterande kötträtter. Förslagen nedan är inte aktiverade sökändringar.
Scheduleraktiveringen för självstädning är en separat leverans.

## Vad nuvarande UI och planerare gör

`backend/app/static/personal.js` skickar uttryckliga antal i
`personal.meals[].distribution`. Kategorierna är `vegetarian`, `chicken`,
`fish` och `meat`. Den sistnämnda visas som **Övrigt kött**; den innebär
inte specifikt nötkött. `personal_policy.protein_category` tilldelar varje
recept exakt en kategori. Kalkon ingår i kycklingkategorin.

Antalen är exakta, inte minimikrav. Tomt/Standard är ospecificerat, medan
ett uttryckligt nolltal förbjuder kategorin. Vid fem middagar och enbart
`chicken=1, vegetarian=2` kan de två övriga bli fisk eller övrigt kött.
`meat=2` fyller hela fördelningen och utesluter då fisk.

`recipe_library.meal_candidates` gallrar redan på måltidstyp, matkök,
tillagningstid, ingrediensantal, fiskval och godkänd receptanpassning.
`PersonalPlanner._candidates` kontrollerar kost och uteslutningar, matchar
produkter och gör en individuell korg-/näringskvalificering. Fördelningen
används inte här för att utesluta omöjliga kategorier.

`PersonalPlanner._create` återanvänder en kandidatpool per måltidstyp.
`personal_policy.distribution_ok` gallrar delmenyer som redan har för många
av en kategori eller inte har tillräckligt många återstående platser för
ett angivet antal. Slutmenyn kontrolleras mot de exakta antalen.

Fler krav begränsar alltså tillåtna kombinationer, men sparar inte
automatiskt det inledande produkt-/kvalificeringsarbetet. Snäva krav kan
dessutom kräva bredare reservsökning. Antal kandidater är därför inte ett
direkt mått på svarstid.

En läsning av det aktuella registrerade middagsbiblioteket gav:

| Kategori | Grundrecept | Recept inklusive godkända varianter |
| --- | ---: | ---: |
| Vegetariskt | 50 | 103 |
| Kyckling/kalkon | 18 | 35 |
| Fisk/skaldjur | 12 | 22 |
| Övrigt kött | 14 | 29 |
| Totalt | 94 | 189 |

Detta är innehållsinventering, inte antal köpbara recept efter en användares
krav och aktuella butikspriser. Ett tidigt filter för en fullständig
1/2/2-fördelning kan här undvika kvalificering av 22 fiskalternativ, om de
inte redan har uteslutits av andra val. Det bevisar ingen viss tidsvinst.

## Förslag inom befintlig arkitektur

1. **Gallra bevisat omöjliga kategorier före kvalificering.** Använd samma
   kategorisering som slutkontrollen. Nolltal och en fullständigt fördelad
   meny ger säkra uteslutningar. Ospecificerade återstående platser måste
   behålla alla tillåtna kategorier. Redigering/byte av enstaka rätt behöver
   också räkna de kvarvarande, låsta rätterna.
2. **Välj representanter per efterfrågad kategori.** Reservera tillräckligt
   många olika grundrecept för varje kvot, med marginal för andra krav.
   Kombinera kostnad, matkök, rättform, tillagningssätt, huvudingrediens
   och möjlig förpackningsdelning. Flera varianter av samma grundrecept
   får inte räknas som flera tillgängliga middagar.
3. **Behåll hela biblioteket sökbart.** En begränsad arbetslista gäller
   bara den aktuella beräkningen. Påfyllning ska styras av vad som saknas
   för en giltig meny, exempelvis en kategori eller ett matkök. Historik
   och kontrollerad utforskning kan senare ge omväxling mellan veckor;
   ingen ny dold slump eller historikinsamling är införd genom denna analys.
4. **Optimera den gemensamma korgen.** Individuellt billigaste recept kan
   bli dyrare tillsammans än rätter som delar förpackningar, erbjudanden
   och butiker. Behåll därför både ekonomiskt starka och kompletterande
   alternativ. Slutlig näring, allergener, mängder och köpvillkor ska
   passera dagens verifiering.
5. **Bevara en färdig giltig jämförelsemeny.** Vid samma krav, priskontext
   och beräkningstid får utökad sökning inte kasta bort den tidigare
   färdigoptimerade lösningen. Den rättningen finns i utkast-PR #4.
   Det är inte ett bevis på globalt lägsta möjliga pris, och ett gammalt
   sparat pris får inte återanvändas efter pris-/kravändring.

Den nuvarande seed-begränsningen väljer billiga recept, förpackningsöverlapp
och representanter per matkök. Den reserverar inte uttryckligen utrymme
utifrån användarens kategorikvoter. Dess gränser ligger efter individuell
kvalificering och löser därför inte hela kostnaden för ett växande bibliotek.

En första säker implementation kan göra steg 1 och därefter kvotmedvetet
urval efter kvalificering. Ett tidigare heuristiskt urval som även minskar
produktmatchningen behöver separat utvärdering: grova priser är urvalssignaler,
inte kvalificerade köp eller säkra prisgränser. Fasta tal som ”20 per kategori”
ska inte låsas innan mätning.

## Acceptans innan nya gränser aktiveras

Använd samma frysta priser, klocka och syntetiska användarval i Lund och
Malmö. Jämför nuvarande sökning, kategoriindelat urval och den definierade
fullbiblioteksreferensen vid 222, 1 000 och 2 000 registrerade recept.
Fullbiblioteksreferens är fortfarande en sökalgoritm, inte en matematisk
globaloptimum-orakel.

Mät kvalificerade kandidater, verkliga korgutvärderingar, svarstid, topp-RAM,
betalt totalpris, uppfyllda kvoter, antal olika grundrätter och kulinarisk
spridning. Mät både kall och varm körning samt upprepade anrop och byte av
prisuniversum; minnet får inte växa med gamla sökningar och pensionerade
prisunderlag. Inkludera Standard, 1 kyckling/2 vegetariska/2 kött,
alla vegetariska, noll fisk, ospecificerad rest, snäva näringskrav,
saknade produkter, skafferi, låsta produkter och ett enskilt receptbyte.

Kontrollera särskilt att den lilla listan inte rapporterar omöjliga krav
när den bredare referensen hittar en giltig meny, att påfyllning sker utan
att mjuka upp användarens krav, och att upprepade sökningar inte låser
utbudet till samma lilla grupp. Prisavvikelse och variation ska redovisas
separat; snabbare svar räcker inte för att godkänna ändrade gränser.
Jämför samma läge: Billigast, Balanserad respektive Varierad. Ett medvetet
variationsval får kosta inom användarens valda gräns och ska inte ersättas
av ett dolt krav att alltid återkomma till billigaste veckan.
