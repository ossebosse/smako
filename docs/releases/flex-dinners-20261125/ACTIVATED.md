# Flexrätter och skalade versioner för näringsmål (2026-11-25)

Aktiverad 2026-11-25 09:50 UTC. App **app-6a22c077aae2-16cbe919**
(`sha256:7cee29d782f2…`), bas `app-1032ff8a39be-31d9e0ed`
(`sha256:d4fc44f19193…`). Scheduler orörd.

## Innehåll

Main `4334dbf`. Releasegren `release/flex-dinners-20261125` (`6a22c07`) =
`1032ff8` + samma ändring (`git diff 5ccfb4a 4334dbf -- backend scripts`),
eftersom main efter `d3bad43` har schedulerfiler som kräver nyare grocery-kod.

Ägarbeslut 2026-11-24/25:

- Recept med granskade intervall (`design.scaling = "reviewed_ranges"`) får
  skalade versioner (mer huvudingrediens, mindre tillbehör; kryddor och
  marinad med `scales_with` följer med) som bara erbjuds måltider med
  näringsmål. 2 kr straff per steg (`scaled_step_kr`).
- 1 992 middagsversioner har gjorts flexibla (tre paket, 0 avvisningar,
  AI-granskade: `docs/reviews/flex-dinners-20261125/REVIEW.md`). Biblioteket
  laddar 8 012 recept varav 4 714 skalade.
- Planeraren provar en skalad version bara för en rätt som missar näringsmålet
  (inte för rätter som klarar det eller stoppas av produkter/data), närmast
  först, och behåller den första som klarar sig.

## Prov

- Lokalt: `test_scalable_recipes_20261124.py`, `test_recipe_library.py`,
  `test_meal_library.py`, interning- och författartester.
- Server, slängcontainer mot Lunds priser (2 CPU, låg prioritet): plantider
  och kostnader i granskningen ovan; 45 g protein × 5 middagar 636,50 → 523,82 kr.
- Kandidatbild utan nätverk, skrivskyddad: bibliotek 8 012/4 714, 5 middagar
  utan mål 374,33 kr, 45 g × 5 523,82 kr med nötfärs 120 % och fiskcurry 124 %,
  `from app.main import app` ok.
- Efter aktivering: `/ready` Lund och Malmö ready med nytt BUILD_ID, 336 h
  prisålder, inga fel i apploggen. Lagringsretention complete före och efter.

## Avvikelser

Bygge och aktivering kördes frånkopplat på servern (`setsid nohup`) med samma
arbetare som `beta_release.py`; retentionen kördes separat före och efter.
Kvitton i `.local/beta-release-flex-20261125/`.
