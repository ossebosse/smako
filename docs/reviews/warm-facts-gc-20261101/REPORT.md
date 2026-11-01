# Uppvärmda menyer: faktakontroller och minnesstädning, 2026-11-01

## Ändring och verifierat läge

Kod `b7c8d0506e23f434abdc5a5fecc53639c2de2f1d`, [PR 59](https://github.com/ossebosse/smako/pull/59).
Jämförelsen gäller den faktiskt aktiva basbilden `sha256:0c0f1720e9dd38555980ac1fc0e4c0f9402c242379570fa08fe69c5f87be73a6` och
byggd kandidat `sha256:a396c7774515c738a6b3909fb2b776d897bc48b29ddfc2d1064264f2ff97b8ad` (`app-b7c8d0506e23-c18e4ba9`). Aktivering journalförs separat.

- `/ready/preparation` ger 200 först när receptbibliotek och samtliga aktuella
  prisuniversum är färdigförberedda i processen, annars 202. Bygg-ID och exakt
  uppsättning universum måste matcha testets förväntningar. `Cache-Control: no-store`.
- Webbläsarverktyget `scripts/release_verification/complete_recipe_browser.py`
  har `--warm-build-id`, upprepad `--warm-universe-id` och `--warm-timeout`.
  Väntan sker före menyns tidtagning. Vanlig `/ready` förblir en hälsokontroll.
  Partiell, gammal eller saknad förberedelserapport intygar aldrig varmt läge.
- Axfood samordnar frånvarokontroller genom en begränsad katalogförteckning.
  Resultat byggs privat i en grund kopia av faktamappningen, högst 8 MiB.
  Katalogernas identitet, läge och ändringstider kontrolleras igen innan ändringarna
  publiceras. Ändring/läsfel kastar både provisoriska fakta och räknare och gör om
  projektionen en gång med ordinarie läsare, utan negativt index.
  Stora mappningar och icke återspelbara iteratorer använder tidigare kontrollväg.
- Befintliga, olistade, korrupta och återkallade dokument går fortfarande genom
  ordinarie hash-/identitetskontroller. Ingen negativ filcache delas mellan anrop.
- Ett antaget V2-jobb får använda sin redan genomförda fullständiga städning en
  gång: startens extra fulla GC ersätts med generation 1 och allocator trim.
  Full GC före menysökningen kvarstår. Direktanrop, äldre sökpolicy och nästa
  `create()` i samma jobb behåller full GC. Krediten är isolerad per jobb och
  kan konsumeras endast en gång även över arbetstrådar; fel lämnar ingen kredit.

`SOURCE_FACTS_PREWARM_ENABLED=true` och aktuell V2-uppvärmning behålls.
Skälen och avstängningsmöjligheten finns i
[förra uppföljningen](../warm-prewarm-20261101/REPORT.md). Ingen miljöflagga ändrades.
GC-samordningen gäller bara komplett V2-planering med bevisad städning vid
inträdet; övriga vägar behåller skyddet. Det finns ingen ny global avstängning av GC.

## Metod: faktiskt uppvärmt och verkligt antaget arbete

En separat process per bild, bas först och kandidat sedan, samma syntetiska
användarval och samma sparade pris-/källdata. Båda aktiva kommunernas fakta,
2 462 aktuella recept och portionsvyer 1–4 förbereddes synkront med `ready`
och noll persistensfel före första menyn. Första menyn särredovisas som primning;
nya svenska/grekiska/portionsval och det bredare fallet är nya kombinationer
mot det uppvärmda underlaget, inte bara identiska menyträffar.

Tio jobb per bild genom `PlannerAdmissionController`, inklusive städningen före
planeraren, verklig sökning, köpgranskning, sparning och ägd återläsning. Varje jobb
har separat syntetisk SQLite-fil i `/tmp`; produktionens användardata monterades
inte. Behållare utan nätverk, skrivskyddad rot och skrivskyddade källvolymer,
4 GiB minnesgräns, 512 MiB temporär yta. Inget belastningsprov överlappade bygge,
backup eller aktivering. Gränsen på 60 s för själva planeraren kvarstod.

Normalfallen: en middag, italienskt/svenskt/grekiskt, 1–2 portioner, mjölk 1 l,
17 valda Lund-priskontexter, högst en inköpsbutik. Det bredare fallet: tre
middagar, fri matkultur och högst tre inköpsbutiker. Inga krav, kvalitetsgrindar,
butiker eller recept beskars för att få en godkänd tid.

| Fall | Bas, s | Kandidat, s | Skillnad, s | Högsta observerade RSS under jobbet, MiB |
| --- | ---: | ---: | ---: | ---: |
| italian-prime | 26.737 | 25.519 | -1.218 | 2358.6 → 2356.0 |
| italian-repeat | 23.688 | 21.347 | -2.342 | 2348.5 → 2355.1 |
| swedish-new | 25.107 | 22.273 | -2.834 | 2350.6 → 2360.5 |
| greek-new | 25.305 | 21.588 | -3.717 | 2350.9 → 2349.1 |
| italian-one-new | 24.254 | 21.518 | -2.736 | 2346.6 → 2349.6 |
| italian-repeat-2 | 23.816 | 21.442 | -2.375 | 2353.1 → 2354.0 |
| swedish-repeat | 24.198 | 21.876 | -2.322 | 2350.3 → 2355.9 |
| greek-repeat | 23.933 | 21.833 | -2.100 | 2353.2 → 2353.2 |
| broader-three-dinners | 51.365 | 51.341 | -0.025 | 2392.1 → 2398.2 |
| italian-after-broader | 24.407 | 21.801 | -2.606 | 2456.9 → 2457.5 |

Det bredare fallet är i praktiken oförändrat: 51,365 → 51,341 s. Menysökningen
ökade från 14,135 till 18,606 s och varukorgsberäkningarna från 1 854 till 2 172.
Den befintliga sökpolicyn använder återstående jobbtid och reserverar 12 s för
slutförande (`menu_optimizer.py`, `checkpoint`); sparad förberedelse ger mer
sökutrymme här. Samma slutkorg innebär ingen bevisad ytterligare besparing.

Gemensam käll-/receptförberedelse före menyerna tog **84,999 → 92,572 s**;
prisåterställning 92,760 → 92,830 s och prisprojektion 12,918 → 12,782 s.
Den långsammare förberedelsen döljs inte i en etikett om snabbare uppstart.
Denna ändring motiveras av uppvärmda menyjobb; den visar ingen starttidsvinst.

Alla 20 jobb passerade köpgranskning, sparning och identisk ägd återläsning.
Alla tio motsvarande recept, varukorgshashar, priser, faktaversioner och antal
fakta är identiska. Separat fullständig objektsjämförelse efter menyserien:
**54 515 Lund-fakta och 95 998 Malmö-fakta**, samtliga fält och faktaversioner lika.

## Tid och maximal minnesförbrukning

Median över de åtta normalfallen efter primning (det bredare fallet särredovisas):

| Del | Bas | Kandidat |
| --- | ---: | ---: |
| Hela antagna jobbet | 24.226 s | 21.694 s |
| Faktaladdning | 7.112 s | 6.682 s |
| Alla uttryckliga GC-anrop, inklusive inträdet | 7.071 s | 4.712 s |
| Planerarens städningssteg, inklusive trim | 4.722 s | 2.401 s |

Varje basjobb gjorde tre fulla GC. Varje kandidatjobb gjorde två fulla GC och
ett generations-1-anrop. Den uppmätta omfattningen inkluderar den städning vid
inträdet som tidigare inte ingick i planerarens 3,7-sekunderssiffra.

Värdprocessen läste behållarprocessens `/proc/.../status` var 50 ms, oberoende
av Pythons GIL. Högsta observerade RSS under något menyjobb:
**2456.9 → 2457.5 MiB**.
Kernelns processövergripande högvattenmärke, inklusive inläsning och uppvärmning:
**2736.4 → 2737.0 MiB**.
Det bredare fallet följs av en ny italiensk meny för att kontrollera fortsatt
funktion och minne efter större arbete. Minne/tid för efterföljande dubbel
faktajämförelse ingår inte i menyresultaten. Sampling kan missa korta toppar;
processens kernelmätta högvattenmärke ger ett separat totalt maxmått.

Detta är en jämförd följd per bild på en delad server, inte p95, ett statistiskt
säkerställt mått för små skillnader, ett kallstartprov eller garanti för alla
val/samtidighetslägen. Ingen generell optimalitetsgaranti tillkommer.

## Extra kontroll av Malmö

Efter menyserien tog kandidatens enskilda Malmö-faktaladdning 13,390 s och
basläsarens efterföljande laddning 11,640 s. Objektsjämförelsen var identisk,
men denna ordnade engångsobservation var långsammare och föranledde mer kontroll.
Orsaken till den enskilda spiken är inte fastställd.

En ny process med färdig gemensam uppvärmning (88,679 s för källor/recept),
samma exakta kandidatbild och samma källor körde läsarna gammal–ny–ny–gammal.
Full GC genomfördes före varje mätning, utanför klockan, och ingen full automatisk
GC inträffade under de fyra faktaladdningarna. Samma 95 998 fakta/version:

| Läsare | Hela faktaladdningen, s | Axfood-projektion, s |
| --- | ---: | ---: |
| Gammal 1 | 11,326 | 1,022 |
| Ny 1 | 10,711 | 0,582 |
| Ny 2 | 10,734 | 0,576 |
| Gammal 2 | 11,234 | 1,048 |

Medel: **11,280 → 10,722 s**, detaljprojektionen **1,035 → 0,579 s**.
Detta styrker mindre upprepat faktarbete även för Malmö. Det är ett separat
faktaprov, inte fyra Malmö-menyer eller en statistisk latensgaranti.

## Källvalidering, tester och mätjournal

Den första varma profileringen mätte faktaladdning 7,001 och 6,904 s;
den äldre siffran 11,6 s återanvänds inte som dagens referens. Profilering med
cProfile är instrumenterad och används endast för fördelningen av arbete,
inte som meny- eller faktalatens. Den visade 19 137 djupa storleksberäkningar
för dokumentcacheposter och återkommande katalogkontroller. Större kvarvarande
kostnader är databas-/källrevision och kanonisk serialisering av faktaversionen;
dessa integritetskontroller är kvar.

- Lokalt: 115 godkända, 1 plattformsberoende symlänkskip. Riktade käll-,
  minnes-, kö-, readiness- och webbläsargrindtester. Ruff och compileall godkända.
- [CI för kodcommiten](https://github.com/ossebosse/smako/actions/runs/41279958101):
  4 442 godkända, 63 skip, noll fel. Alla tre testgrupper och coverage-overview gröna.
- Exakt kandidatbild: verklig fixture-checkout 59,90 kr, ägd sparning/återläsning,
  negativ generisk bindning, HTTP-/frontendkontroller och nya readiness-routen.
- Första lokala kandidatkontrollen stoppade på en felkodad svensk sträng i det
  återanvända testskriptet. UTF-8-kopieringen rättades och samma oförändrade bild
  passerade. Ingen menytimeout eller appregression doldes genom omkörningen.
- Nya källtester provar tillagda orphan-/metafiler, katalogbyte, borttagning,
  läsfel, budgetfallback och engångsiteratorer. Provisorisk projektion publiceras
  inte före slutkontroll och fallback ger samma fakta/räknare som ordinarie läsare.

Sanerat underlag: [EVIDENCE.json](EVIDENCE.json). Lokal råsamplingsjournal och
körverktyg finns i `.local/warm-facts-gc-20261101/`; de innehåller inga
produktionsprofiler eller cookies. Publika prov efter aktivering redovisas i
[aktiveringsjournalen](../../releases/warm-facts-gc-20261101/ACTIVATED.md).
