# Mindre dubbelarbete i menyberäkningen

Aktiverad 2026-10-31T20:21:52.356115+00:00 på https://beta.smako.nu.
[PR 56](https://github.com/ossebosse/smako/pull/56) är på main
`86cbd41efcf6284fa0d807739f2373946ef340bf`. PR- och [main-CI](https://github.com/ossebosse/smako/actions/runs/41237414450) passerar:
4 405 testfall gröna, 63 överhoppade, inga fel. Kandidat och merge har
identiskt kodträd `3870201967f204db818059061e0fcb5e80b103bd`.

## Resultat

Nyss beräknade produktfakta djupkopieras och återskapas inte längre för
cachelagringen. Anropslokala namn-/GTIN-index minskar upprepad sökning i
deklarationslistorna; samma exakta identitets- och konfliktkontroller körs.
Alla 54 515 faktaposter och deras innehållsversion är identiska.
Källbyteskontroller, personliga krav, prisoptimering, audit, sparning och
60-sekundersdeadline består. Inga användarbeslut cachas mellan anrop.

I isolerat kallt prov gick faktaladdningen från 35,414 till 26,863 s.
Basen nådde tidsgränsen vid 60,024 s; kandidaten levererade, slutkontrollerade,
sparade och återläste menyn på 55,273 s. Varmt prov: 26,905 till 24,947 s.
De lyckade proven gav alla priset 110,55 kr. Separat prisåterställning tog
cirka 92 s före anropet. Se [mätningen](../../reviews/menu-work-reduction-20261031/REPORT.md).

Första publika menyprovet levererade på **43,547 s**, med passerad checkout, pris 110,55 kr och identisk sparad återläsning. Inga JavaScriptfel. 60-sekundersmålet klarades i detta prov.

Ny gäst, första försöket utan omkörning: italiensk middag för två,
10–15 ingredienser, mjölk 1 l, Lund 22350/3 km och högst en butik.
Det publika provet mäter klick till renderad meny, medan de isolerade
anropstiderna saknar HTTP/kö/browser. Dessa enstaka prov bevisar inte
p95, samtidighet eller alla nya kombinationer av val.

134 riktade fall, Ruff och compileall passerar. Paketets två källfiler
är AST-identiska med den mätta och testade koden. Exakt byggd image klarade
isolerade HTTP-/API-/checkout-/sparningsprov utan produktionsmountar.

## Drift och återställning

BUILD_ID `app-b05b953576b7-fc1840af`; image `sha256:50ae810d8f4b4d71ea98c8c5150ca1531deff13d4d6fe9a6dcc0f09a6676bed5`.
Bas och återställningsbild `sha256:baf58c65ec96af10604548dcb6e8e1b8e5d4e96fe813678caa8d0e416c4e6912`. Två runtimefiler ändrade;
1009 andra och runtimekonfigurationen verifierade.
Endast appen byttes. Scheduler source-ops-8a53beb80e43, miljö, mountar och
båda prismanifesten bevarades. Lund/Malmö svarade HTTP 200/ready med rätt build.

Verifierad full backup `/srv/smako/backups/20261031T201056Z` skapades under befintligt driftlås.
Tidigare 327 planrevisioner,
140 privata tillstånd,
2 konton och 1
session bevarades enligt radhasher. Retention: complete.
Ledigt efteråt 47,92 GB; beräknat behov
15,21 GB.

Inga insamlingsprofiler eller scheman ändrades. Återställningsunderlag finns
i `/opt/smako/evidence/app-b05b953576b7-fc1840af/`. Använd befintlig appåterställning
utan att skriva över senare användardata med en äldre databasbackup.
Se [maskinunderlaget](EVIDENCE.json).
