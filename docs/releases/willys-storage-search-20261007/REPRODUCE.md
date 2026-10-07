# Reproducera den isolerade jämförelsen

Kör från `D:\Projects\Smako`. Produktionsinsamling, appbyte och relästart
ingår inte i dessa kommandon. Alla stora filer finns under
`.local/willys-storage-search-20261007/` eller i de namngivna Docker-volymerna
på den verifierade D:-placerade Docker-disken.

## Låst indata

- Före: fd2-paketet och dess SHA i SEARCH.md, lokalt återbyggd image
  `smako-search-baseline:fd2cfda5490a`.
- Efter: oföränderligt 54cb-paket och image enligt PACKAGE.json.
- Prisartefakt SHA-256
  `f82d66103e830b82b7d919fe847fd5b3ef85c5e323e0a2133c338f064dfb8768`.
  Dess 2 233 råreferenser är hashkontrollerade. Input-volymen är skrivskyddad.
- Köpklocka `2026-10-04T07:19:16.028059+00:00`; inga liveprisanrop.
- Huvud- och profilprov: verkligt P3-innehåll, 182 recept. Skalprov: exakt
  föregående etapps `scale.py` och P2-innehåll, 176/352/880 poster.
  Syntetiska tillägg är belastningsdata, inte kvalificerade nya recept.

INPUTS.json binder samtliga begäranden till föregående etapps JSON:
alla tio är exakt lika som objekt. Skalgeneratorns Git-objekt använder LF
och den körda Windows-kopian CRLF; efter enbart denna radslutsnormalisering
är källan identisk. Båda bytehasharna bevaras. Ingen generatorlogik eller
syntetisk mängdregel har ändrats.

## Körväg

Den versionshanterade harnessen är
`scripts/release_verification/week_search_benchmark.py`. Den vanliga
`PersonalPlanner` och ordinarie slutkontroller körs i respektive image.
`evaluation` innehåller endast teststart och mätning; ingen mount skuggar
appens moduler. Hela kommandot för varje försök finns i dess `command.json`.

Den bevarade lokala orkestreringen består av `matrix.py`, `run_benchmark.py`
och `matrix-jobs.json` under evidensroten. Varje försök får ett nytt namn;
verktyget vägrar skriva över en tidigare försöksmapp. Exempel, med ett nytt
unikt försöksnamn:

```powershell
.venv/Scripts/python.exe -X utf8 .local/willys-storage-search-20261007/run_benchmark.py verifiering-ny-1 smako-week-search:54cb2e8159a1-packaged 0 main cold
```

Argument efter imagen är biblioteksfaktor (`0` för verkligt P3), profil
(`main`, `simple`, `breakfast`, `snack`, `combined`, `crafted`) och läge
(`cold`, `warm`, `persistent`). För `persistent` anges sist namnet på en
tidigare körnings förberedelsekatalog från samma sida i jämförelsen.
Skalfaktorer 1/2/5 använder den separata P2-innehållsimagen, aldrig
leveransimagen som om den innehöll 880 verkliga recept.

Varje container har två CPU, 3 GiB, nätverk avstängt, skrivskyddade inputs,
egen förberedelsekatalog och `/tmp` på 512 MiB tmpfs inom minnesgränsen.
Kör endast ett tungt prov åt gången. `warm` gör en uppvärmningsberäkning
och tre nya beräkningar; den hämtar inte tre färdiga planer.

## Råbevis och bedömning

`trials/<namn>/` innehåller kommandot, rålogg, exitkod, full containerinspect,
fulla planresultat och mätningar. `exit.json` mäter hela containerprocessen;
kopiering av resultat efter avslut ingår inte. Tidsfält inne i resultatet
har andra, uttryckligen dokumenterade mätgränser i PERFORMANCE.json.

`compare_all.py` jämför hela resultat och sparar varje normaliserad
metadataavvikelse. `validate_results.py` kontrollerar dessutom resultat
mot användarvillkor. Tillåtna metadataskillnader anges i SEARCH.md/TESTS.md;
recept, mängder, produkter, avtal, köp-/näringsstatus och audit undantas inte.

Webbläsar- och HTTP-råbevis ligger separat under `browser/`,
`concurrency-*`, `legacy-http/` och `pantry-http/`. Injektioner, ursprungliga
FAIL och omkörningar behålls. Teststarten med den först felaktiga isolerade
SQLite-väntetiden finns kvar; senare prov använder produktionens verifierade
30 sekunder. Det är en testmiljörättning, inte en ändrad appimage.

För individuellt innehåll och invalidering används ordinarie
`app.services.meal_library_cli qualify/prepare` och den versionshanterade
`scripts/release_verification/meal_library_incremental.py`. Exakta kommandon
och exitkoder finns i `*-exit.json` vid evidensroten. Dessa prov har eget
resultatområde och körs efter prestandamatrisen, inte samtidigt.

Inga privata produktionsdatabaser, cookiehemligheter eller reläkonfigurationer
ska kopieras till versionshanterade rapporter. Lokala råbevis bevaras på D:;
rapporternas små sammanfattningar och hashreferenser är versionshanterade.
