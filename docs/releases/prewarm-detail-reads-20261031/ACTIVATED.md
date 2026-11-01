# Mindre uppvärmning och färre filkontroller

> Uppföljning 2026-11-01: provet på 53,500 s överlappade ännu pågående
> bakgrundsförberedelse. Se [varma jämförelseprov](../../reviews/warm-prewarm-20261101/REPORT.md)
> och skälet till att uppvärmningen behålls på. Ursprungsobservationerna nedan
> är bevarade; ingen ny runtimeaktivering gjordes i uppföljningen.

Aktiverad 2026-10-31T21:41:47.238688+00:00 på https://beta.smako.nu.
[PR 57](https://github.com/ossebosse/smako/pull/57) är på main
`3eb21dc7feafcb071648d2ddfd9b0043a460f73b`. PR- och [main-CI](https://github.com/ossebosse/smako/actions/runs/41243602156) passerar:
4 417 testfall gröna, 63 överhoppade, inga fel. Kandidat och merge har
identiskt kodträd `d3983c0adb35b5839ddebcd8d03e3a74efbe4fd7`.

## Resultat

V2 värmer aktuella receptvyer och förbereder äldre historik vid behov.
En begränsad anropslokal kataloglista ersätter upprepade filkontroller när
båda Axfood-detaljfilerna saknas. Katalogändringar och osäkerhet ger vanlig
läsning; befintliga filer, korruption och återkallelser valideras som tidigare.
Minnesstädningens skydd, prisregler, recepturval och audit består.

Fem isolerade fall blev snabbare med identiska recept, hela varukorgar och
priser. Kallt: 56,118 → 49,688 s. Nytt svenskt/grekiskt val:
26,770 → 21,703 s respektive 26,167 → 21,639 s. Alla 54 515 faktaposter och
hela innehållsversionen identiska. Separat receptuppvärmning:
31,946 → 17,203 s och cirka 67 MiB lägre toppminne.
Se [mätningen](../../reviews/prewarm-detail-reads-20261031/REPORT.md).

Första publika menyprovet levererade på **53.500 s**, med passerad checkout, pris 110.55 kr och identisk sparad återläsning. Inga JavaScriptfel. 60-sekundersmålet klarades i detta prov. Föregående versions engångsprov var 43,547 s; det nya publika provet var alltså långsammare. Ingen publik latensvinst är visad av dessa två separata körningar, och orsaken till skillnaden är inte fastställd.

Ny gäst, första försöket utan omkörning: italiensk middag för två,
10–15 ingredienser, mjölk 1 l, Lund 22350/3 km och högst en butik.
Det publika provet mäter klick till renderad meny. Isolerade anrop inkluderar
audit, sparning och ägd GET men exkluderar separat prisåterställning (~92 s),
HTTP/kö/browser. Enstaka prov bevisar inte p95, samtidighet eller hela
valkatalogen. Uppvärmningstiden gäller recept, inte hela appuppstarten.

131 riktade fall, Ruff och compileall passerade lokalt; ytterligare ett
symlänksfall kördes i Linux-CI. Paketets två filer är AST-bundna till uppmätt
kod. Exakt byggd image klarade isolerade funktions-/HTTP-/checkout-/sparningsprov.

## Drift och återställning

BUILD_ID `app-327fa573eb3f-0541cf49`; image `sha256:0c0f1720e9dd38555980ac1fc0e4c0f9402c242379570fa08fe69c5f87be73a6`.
Bas och återställningsbild `sha256:50ae810d8f4b4d71ea98c8c5150ca1531deff13d4d6fe9a6dcc0f09a6676bed5`. Två runtimefiler ändrade;
1009 andra och runtimekonfigurationen verifierade.
Endast appen byttes. Scheduler source-ops-8a53beb80e43, miljö, mountar och
båda prismanifesten bevarades. Lund/Malmö svarade HTTP 200/ready med rätt build.

Verifierad full backup `/srv/smako/backups/20261031T213203Z` under befintligt driftlås.
Tidigare 328 planrevisioner,
141 privata tillstånd,
2 konton och 1
sessioner bevarades enligt radhasher. Retention: complete.
Ledigt efteråt 44.67 GB; beräknat behov
15.20 GB.

Inga insamlingsprofiler eller scheman ändrades. Återställningsunderlag finns
i `/opt/smako/evidence/app-327fa573eb3f-0541cf49/`. Använd befintlig appåterställning
utan att skriva över senare användardata med en äldre databasbackup.
Se [maskinunderlaget](EVIDENCE.json).
