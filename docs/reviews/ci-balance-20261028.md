# Balanserad CI och bevarad recepttäckning, 2026-10-28

PR #31 är integrerad på main `84c39008b3dc15a5262a0f372070a40866aeb271`.
Dess [hosted CI](https://github.com/ossebosse/smako/actions/runs/40641438279)
körde samtliga 4 170 noder utan fel, med 63 dokumenterade historiska data-skippar,
på 510 sekunder. Alla 26 leveranshashar verifierades efter main-fast-forward;
den fortsatta budgetjournalen återställdes byteidentiskt.

## Förändring och verifiering

De två senaste gröna JUnit-underlagen visar ojämn arbetsfördelning.
Åtta hela testfiler flyttas till den befintliga integrationsgruppen. Den
kräver fortfarande inga webbläsare; Chromium/WebKit-kontrollerna ligger kvar
i de två andra grupperna. Samtliga grupper är obligatoriska. Ny testkod
hamnar fortsatt automatiskt i core. Timeout och fel-/skipphantering ändras inte.

[Nodjämförelsen](ci-balance-20261028/ci-partitions.json) bevisar samma 4 170
unika noder: core 3 448, planner 125, integration 597. Tidigare mätningar
används som fördelningsunderlag, inte som ett löfte om ny hosted väggtid.

Testet för processvattnets portionsskalning skalar varje recept en gång
per portionsantal och granskar sedan alla dess vattensteg. Samma 19 415
kontrollpunkter finns kvar. Antalet kompletta skalningar minskar från
19 140 till 9 965. Två jämförelser i omvänd körordning gav cirka
28,12/27,88 sekunder före och 14,28/14,17 efter. Alla unika skalade
receptobjekt har identisk hash. Se
[jämförelsen](ci-balance-20261028/water-scaling-comparison.json).
Hela berörda testfilens tio tester, Ruff och compileall passerar lokalt.
Hosted CI krävs före integration av denna ändring.

## Återanvänt underlag och fortsatt täckningsarbete

Runtime, recept, produktfakta och priser är oförändrade. Metodsignaturen
är fortsatt `9113f04df621a53f67de4d16b422e762a9c56641352fdf585b798124c3d1ec8b`.
[Hashkontrollen](ci-balance-20261028/reused-verification.json) återanvänder
PR #31:s verifiering: 1 862/2 200 hela korgar inklusive uppskattningar,
1 066 exakt insatslösta och 1 064 exakt hela; 338 kvar. Ingen ny korg
räknas här och samma dyra korgprov upprepas inte efter enbart teständringar.

En ny primärstudie ger ett möjligt underlag för kokt, avrunnen mungböns-
och belugalinsmassa. [Tillämpningsgranskningen](ci-balance-20261028/legume-applicability.json)
bevarar de två exakta befintliga produktkällorna och visar skillnaden
mellan studiens och förpackningarnas beredning. Metoden är ännu inte
kvalificerad för nio berörda receptvarianter. Rensad torr vikt, inköpt
vikt, tillsatt vatten och färdigt utbyte måste redovisas separat.

Fortsätt mot alla 2 200 med samma obegränsade totaljournal och befintliga
resurs-/operationsgränser. Den separata nya källpiloten inväntar beslut.
Ingen produktion, beta, scheduler eller profil ändras.
