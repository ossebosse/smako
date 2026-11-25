# 145 nya middagar med kött, fisk och kyckling (2026-11-25)

Aktiverad 2026-11-25 18:04 UTC. App **app-868cb9b93f81-bffcde1f**
(`sha256:797f68cb6893…`), bas `app-6a22c077aae2-16cbe919`
(`sha256:7cee29d782f2…`). Scheduler orörd.

## Innehåll

Main `e9c6af1`. Releasegren `release/protein-dinners-20261125` (`868cb9b`) =
`6a22c07` + `git diff 880a78c 691b1af -- backend scripts`. Bara receptdata:
sex nya `meal-pack-*` och manifestet, ingen kod.

145 middagar (60 kött, 48 fisk/skaldjur, 37 kyckling) över de sex köken, alla
med granskade mängdintervall. Biblioteket laddar 8 709 recept inklusive
skalade versioner. Granskning, köpbarhet och planerartest:
[REVIEW.md](../../reviews/protein-dinners-20261125/REVIEW.md).

## Prov

- `author`: 145 utan varningar och avvisningar, 10–15 räknade ingredienser.
- Köpbarhet: 145/145 i Lund och Malmö (uppskattat läge, 2 butiker).
- Planerartest före/efter: samma kostnader, +0–3 s per plan, +70 MB.
- Kandidatbild utan nätverk, skrivskyddad: 8 709 recept, 145 nya, `from
  app.main import app` ok.
- Efter aktivering: `/ready` Lund och Malmö ready med nytt BUILD_ID, 336 h
  prisålder, inga fel i apploggen. Malmös prisunderlag visar `degraded` som
  före aktiveringen. Lagringsretention complete före och efter.

Bygge och aktivering kördes frånkopplat på servern med samma arbetare som
`beta_release.py`. Kvitton i `.local/beta-release-protein-20261125/`.
