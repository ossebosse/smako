# Mindre arbete före receptkvalificering

Aktiverad 2026-10-31T15:33:37.426665+00:00 på https://beta.smako.nu.
[PR 55](https://github.com/ossebosse/smako/pull/55) är på main
`c5fdd5f911724d137fb1588c1b02bbe8cfd74e5e`. PR- och [main-CI](https://github.com/ossebosse/smako/actions/runs/41214201313) är gröna:
4 402 passerade testfall och 63 överhoppade, inga fel. Kodträdet efter merge
är identiskt med den granskade kandidaten `cd15469e50f9360cf644b799ffc6aef08bc8e94d`.

## Utfall

Två onödiga hashningar av produktfaktornas mellanled tas bort. Alla 54 515
slutliga faktaposter, full faktaversion och verifierad korg är identiska.
Källornas bytekontroller, konfliktspärrar, aktuella krav, audit, ägarskap och
60-sekundersdeadline består. Ingen ny cache eller prisväg införs.
Se [utredning och reproduktion](../../reviews/menu-timeout-20261031/REPORT.md).

I isolerat varmt prov blev faktaladdningen 17,281 → 12,272 s och komplett
planering/save/ägd GET 33,372 → 25,910 s, samma 110,55-kronorskorg.
Kallt prov nådde fortfarande deadlinen, nu 60,017 s. Separat prisåterställning
tog cirka 97 s. Enstaka prov; ingen p95-, samtidighets- eller fullkataloggaranti.
De två ursprungliga felreferenserna saknar exakt beständig steghistorik.

Första publika provet: **63,032 s**, 110,55 kr, passerad checkout och identisk sparad
återläsning. Ny gäst, samma typ av menyval; ingen omkörning. Inga JavaScriptfel. **Tidsmålet
60 s missades**, även om menyn levererades och funktionskontrollerna passerade.

Provets val: en italiensk middag för två, standardintervallet 10–15 ingredienser,
mjölk 1 l, max en butik och 3 km i Lund. 140 riktade fall verifierade, Ruff och
compileall gröna. Exakt bild klarade isolerade HTTP-/API-/checkout-/sparningsprov.
Paketets mätta funktion är AST-identisk med lokalt testad och isolerat jämförd
funktion; övriga specialanpassningar i aktiv runtime bevarades.

## Drift och återställning

BUILD_ID `app-cd15469e50f9-fa1f8fd2`; image `sha256:baf58c65ec96af10604548dcb6e8e1b8e5d4e96fe813678caa8d0e416c4e6912`.
Bas `sha256:db904d14fd788105c637c48684c336d94fcd56ac945b9edf277b3cfbf037bd5c`. En Pythonfil ändrad, 1010
andra runtimefiler och runtimekonfiguration verifierade oförändrade.
Scheduler består på source-ops-8a53beb80e43. Mountar, övrig miljö och båda
prismanifesten bevarades. Lund/Malmö svarade HTTP 200/ready med rätt BUILD_ID.

Verifierad full backup `/srv/smako/backups/20261031T152015Z` skapades under befintligt driftlås före
appbytet. Tidigare 326 planrevisioner,
139 privata tillstånd, 2
konton och 1 session verifierades oförändrade
med radhasher. Retention: complete.
Ledigt efteråt 51,76 GB; beräknat behov
15,20 GB.

Ordinarie daglig backupstatus blandas inte ihop med releasebackupen.
Inga scheman eller insamlingsprofiler ändrades. Föregående wrapper/image och
återställningsunderlag finns i `/opt/smako/evidence/app-cd15469e50f9-fa1f8fd2/`;
använd befintlig appåterställning utan att återställa databaser över senare
användarändringar. Se [maskinunderlaget](EVIDENCE.json).
