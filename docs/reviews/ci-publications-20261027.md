# CI och publiceringskedjor 2026-10-27

Föregående [CI-körning](https://github.com/ossebosse/smako/actions/runs/40575234955)
tog 20 min 35 s, varav 19 min 18 s i teststeget. Två isolerade partitioner
kör nu samtliga backendtester. Ett gemensamt `backend`-jobb kräver att båda
lyckas. Nya testfiler hamnar automatiskt i core. Föråldrade PR-körningar
avbryts när en ny revision startar; main-körningar behålls. JUnit och de
30 långsammaste testerna gör fortsatta flaskhalsar synliga.

Samma receptinnehåll hashades om för varje föregående publiceringsgeneration.
En lokal instans av befintlig `RecipeComputationCache` återanvänder nu rena
innehållsdigester. Exakta värdesnapshots upptäcker ändrade instruktioner även
på samma objekt. Ordning, versionskedjor och certifikat behåller sina värden.

I tre verkliga kedjor med 1, 27 respektive 28 noder sjönk uppbyggnadstiden
från 34,97 till 6,15 s med identiska noder. Samma 55 långsamma tester tog
258,73 respektive 239,32 s och passerade. Det är lokala Windowsmätningar
med två CPU och 3 GiB, inte en uppmätt förbättring av hosted CI.
[Underlaget](ci-publications-20261027/timings.json) skiljer dessa mått åt.
Fyra publiceringsregressioner och 20 cachetester passerar, liksom Ruff och
compileall. Full hosted CI mäts på PR:n före integration.
