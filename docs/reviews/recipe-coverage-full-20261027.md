# Kontrollpunkt: hela restlistan och generellt prisgap

**Full täckning är inte klar.** Alla ursprungliga 76 grupper är granskade,
och hela nämnaren om 2 200 varianter har kontrollerats med aktuella kvitton.
41 fler hela korgar fungerar med tillåtna uppskattningar. 554 varianter i
69 grupper återstår. Beredning med separata utfall är dokumenterad men inte
aktiverad. Inga recept, original-ID:n, priser eller källtider har skrivits om.

| Mått, av 2 200 | Före | Nu | Förändring |
| --- | ---: | ---: | ---: |
| Individuellt lösta ingredienser, exakt | 999 | 1 010 | +11 |
| Fulla verifierade korgar, exakt | 997 | 1 008 | +11 |
| Individuellt lösta, inklusive uppskattningar | 1 605 | 1 646 | +41 |
| Fulla verifierade korgar, inklusive uppskattningar | 1 605 | 1 646 | +41 |
| Blockerade även med uppskattningar | 595 | 554 | −41 |

Det motsvarar 74,8 % verifierade korgar inklusive uppskattningar. Inga tidigare
lösta original-ID:n förlorades. Två tidigare exakta checkout-avslag består;
de redovisas inte som färdiga. Ett först tidsbegränsat exakt prov verifierades
vid ett avgränsat återprov, medan alla giltiga kvitton återanvändes.
Slutläget innehåller ingen ofullständig eller okontrollerad sökning.

## Vad som ändrats

- Fem exakt bundna leverantörsdeklarationer: GoGreen kokta gröna linser,
  Yipin silkestofu, Abba matjes, Skånemejerier kefir och Dr. Oetker gelatinblad.
  Alla fem normaliseringar har jämförts med sparade, hashverifierade källbytes.
- Befintlig mängdprojektion hanterar explicit deklarerad massa för ett
  styckpaket och explicit volym för ett grampaket. Gelatinets 12 blad väger
  20 g enligt exakt GTIN-variant; sidans standardvariant 10 blad/17 g utesluts.
  Kefirens mass-/volympar gäller bara den identifierade förpackningen.
- Arton exakta pomelo-/rödgrapefruktrelationer använder USDA:s art- och
  formbundna ätliga utbyten i uttryckligt uppskattningsläge. Bruttopaket,
  inköpspris och observeringstid behålls.
- Sexton ytterligare källbundna nötköttsrelationer för fyra granskade
  styckdetaljer använder befintliga receptkrav och prisvägar. Tre recept med
  hel oxfilé är fortsatt blockerade av viktprisavtalet; det är ett separat
  tekniskt hinder, inte ett påstående om saknad råvara.
- Menysökningen återgår till tidigare kandidatrankningar när den gemensamma
  korgen förbättras. Delade paket kan då göra tidigare avvisade receptbyten
  lönsamma. Fulla nya menyförslag fortsätter inom samma deadline; ingen
  historisk meny används som sökfacit.

## Pris och tid under oförändrade fullständiga begäranden

| Prov | Tidigare total | Aktuell total | API + spara + GET | Förberedelse utanför API |
| --- | ---: | ---: | ---: | ---: |
| A | 317,82 kr | 283,24 kr | 52,04 s | 98,10 s |
| B2 | 731,20 kr | 731,20 kr | 32,56 s | 76,12 s |

A är 34,58 kr billigare än föregående körning och 7,58 kr under den tidigare
verifierade referenskorgen på 290,82 kr. B2:s **hela korg är identisk** med
föregående körning. Båda sparades och återlästes med godkänd slut-audit.
Hela sparade begäranden är jämförda, inklusive sparade diversitetsfält.
Resultaten bevisar dessa två fall, inte global optimalitet eller tidsmålet
för varje användarkombination. Miljön är Windows med två CPU och hårt 3 GiB,
inte en Linux-servermätning. TestClient mäter in-process HTTP; browsertransport
och liveinsamling ingår inte.

## Återstående hinder och källgranskning

[Arbetsmatrisen](recipe-coverage-full-20261027/work-matrix.md) och dess
[fullständiga ID-/kandidatkarta](recipe-coverage-full-20261027/work-matrix.json)
omfattar samtliga ursprungliga 595 ID:n i 76 grupper. Den skiljer saknade
produktfakta, sortimentsluckor i den frysta referensen, tekniskt kvarvarande
beredning och authored scope. Statusen `partly_implemented` för nötkött gör
de kvarvarande tre recepten synliga. Summerade gruppmarginaler är inte
additiva vinster; det verkliga tillskottet är 41 unika hela varianter.

Källarbetet använde 88 explicita offentliga dokumentförsök, befintliga
verifierade artikelarkiv och den frysta katalogen. Ursprungliga hämtnings-
och tolkningsutfall är bevarade; exempelvis kunde Yipins sparade `400G`
tolkas först efter en avgränsad parserrättning. Rå-HTML/PDF stannar lokalt.
Den tillåtna 44-artikelskön gjorde **noll handlaranrop**: tre avgränsade
försök stannade vid upptagen serverlease. Inget lås bröts eller kringgicks.

Mynta saknar art-/presentationsbundet bladutbyte; krukans 429 g är inte
bladmassa. Tamarindkoncentrat i ml saknar verifierad pastastyrka och gramgrund.
Vanligt majsmjöl etablerar inte masa harina och skurna korngryn etablerar
inte pärlkorn. De fyra gruppernas 200 ensamblockerade varianter är kvar.
Lemongrass-postens motsägande USDA-taxon används inte som citrongräsutbyte.

[Beredningsgranskningen](recipe-coverage-full-20261027/preparation-review.md)
har källor och konkreta acceptansfall för äggdelar, baljväxter och kaffe.
Äggens samköp, biprodukter, näring och verkliga skafferibokföring behöver
byggas samman i befintliga modeller. Mungbönskällans volymökning och
kaffekällans tillsatta vatten räcker inte som efterfrågat mass-/slutvolymutbyte.
Detta är kvarvarande implementation och evidensarbete, inte ett ägarbeslut
att sänka kraven. Inget nytt käll-/handlar-/allowlistscope har aktiverats.

## Verifiering och reproduktion

640 riktade offline-tester passerade på 37,88 s, därefter fyra ytterligare
gränsfall för de nya köttrelationerna. Ruff och compileall passerar för
berörda filer/paket. Repo-CI redovisas på PR:en före integration.
CI:s hämtning av Ubuntu-paket från Azure-spegeln blev mycket långsam: den
första loggen anger 119 MB att hämta och fortsatt nedladdning efter cirka
20 minuter. Återförsöket låg kvar
i samma steg efter 30 minuter. Befintlig workflow använder därför Ubuntus
ordinarie arkiv, med oförändrade suites, signeringsnycklar, paketverifiering
och teststeg. Detta ändrar inte appens metodhash eller verifierade korgbevis.
Alla 2 656 kvittofiler kontrolleras mot filhash, evidenshash, aktuella
metod-/recept-/villkorsberoenden, audit och butikstak. 2 654 är verifierade
korgar och två är de kvarvarande exakta checkout-avslagen.

Referensen behåller 89 458 produkter, 52 kontexter, samma klocka,
middagsportioner, övriga portioner, tvåbutikstak och inget skafferi.
Faktaversionen, metodhash och samtliga original-ID:n finns i
[coverage.json](recipe-coverage-full-20261027/coverage.json).
Stora fakta och fullständiga kontrollkvitton finns under
`.local/recipe-coverage-full-20261027/`; `facts-final-v2.json` är slutunderlaget.
Prototyper och misslyckade försök är bevarade separat och räknas inte som
slutbevis. Inga konsumentkvitton, inloggningar eller sessionsdata committas.

Kör `check_recipe_coverage.py`, `summarize_recipe_coverage.py` och
`verify_full_coverage_delivery.py` genom befintlig `budgeted_check.py` när
beroenden ändrats. Oförändrade kvitton får återanvändas efter hashkontroll.
[Budgetjournalen](recipe-coverage-full-20261027/budget.json) innehåller
även laddning, stopp och återprov; båda äldre journalerna är orörda.
Av denna etapps 3 600 s har **1 311,3678 s använts och 2 288,6322 s återstår**.
Det reserverade utrymmet för slutverifiering har bevarats genom källarbetet.
Detta är den begärda första kontrollpunkten. Ingen automatisk fortsättning,
beta-/produktionsaktivering eller schedulerändring har gjorts.
