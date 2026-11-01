# Uppvärmda prov, samordnad faktaläsning och GC aktiverat

Aktiverad **2026-11-01T06:55:41.384281+00:00** på https://beta.smako.nu.
[PR 59](https://github.com/ossebosse/smako/pull/59) är på main
`b47e07febe6e95173a9375eee5e3b323aa02972c`. Kod `b7c8d0506e23f434abdc5a5fecc53639c2de2f1d` och merge har samma
träd `920dd5a79ae4e80a01064ceed2307ac89b101848`. [PR-CI](https://github.com/ossebosse/smako/actions/runs/41279958101)
och [main-CI](https://github.com/ossebosse/smako/actions/runs/41281654418) passerade: 4 442 godkända tester, 63 skip, inga fel.

## Resultat och mätgränser

Menytidtagning väntar nu på `/ready/preparation` med rätt bygg-ID och exakt
uppsättning aktiva prisuniversum. HTTP 200 kräver färdigt receptbibliotek och
färdig gemensam förberedelse för Lund och Malmö. Vanlig `/ready` räcker inte.
Ofullständigt eller gammalt underlag ger 202; ingen varm mätning startas då.

Axfood samordnar kontroller av saknade filer och validerar katalogerna igen
före publicering av resultaten. Ändring/läsfel ger vanlig källäsning. Alla
befintliga dokument, hasher och identiteter kontrolleras som tidigare.
V2-jobbets städning vid inträdet återanvänds en gång: tre fulla GC blir två
fulla plus generation 1. Full städning före sökningen och övriga anropsvägar består.

I uppvärmda normalfall efter primning blev medianen **24,226 → 21,694 s**,
faktaladdning **7,112 → 6,682 s**, planerarens städningssteg **4,722 → 2,401 s**.
Med städningen före planeraren medräknad: GC **7,071 → 4,712 s**.
Alla 20 jämförda menyer passerade köpgranskning, sparning och ägd återläsning;
hela motsvarande recept/korgar/priser/faktaversioner är identiska. Samtliga
54 515 Lund-fakta och 95 998 Malmö-fakta jämfördes fält för fält.
Separat Malmö-kontroll i ordningen gammal–ny–ny–gammal: **11,280 → 10,722 s**.

Högsta observerade meny-RSS **2 456,9 → 2 457,5 MiB**; processens kernelmätta
max inklusive uppstart **2 736,4 → 2 737,0 MiB**. I praktiken oförändrat i
proven. 50 ms sampling från värdprocessen, oberoende av Pythons GIL, och
4 GiB behållargräns. Ingen p95-, kallstart-, samtidighets- eller fullvalsgaranti.
Det större fallet låg kvar på cirka **51,3 s** och prövade fler varukorgar inom
sin befintliga tidsgräns. Gemensam uppvärmning var långsammare i jämförelsen,
**85,0 → 92,6 s**; ingen uppstartsvinst påstås.

Se [hela jämförelsen och den extra Malmö-kontrollen](../../reviews/warm-facts-gc-20261101/REPORT.md).
`SOURCE_FACTS_PREWARM_ENABLED=true` och aktuell V2-uppvärmning behålls;
`PRICE_UNIVERSE_PREWARM_ENABLED=false` består. Motivering och operatörens
befintliga avstängning är dokumenterade i mätningen. Ingen miljöflagga ändrades.

## Publika prov efter aktivering

Två nya gäster, samma val: en italiensk middag för två, 10–15 ingredienser,
mjölk 1 l, Lund 22350/3 km, högst en butik. Båda väntade uttryckligen på
färdig gemensam förberedelse i samma bygge för båda kommunerna **före** klicket.
Efter aktivering observerades HTTP 202/running från förberedelsekontrollen
kl. 06:56:18 UTC, trots att vanlig readiness redan godkänts. Menytidtagningen
startade först efter att förberedelsekontrollen gav 200/ready.
Första menyn efter denna grind och nästa jämförbara meny särredovisas:

| Prov | Klick till renderad meny | Checkout/sparad återläsning | Pris |
| --- | ---: | --- | ---: |
| Första efter bekräftad uppvärmning | 28.469 s | Godkänd/identisk | 110.55 kr |
| Nästa jämförbara meny | 25.203 s | Godkänd/identisk | 110.55 kr |

Första provet väntade 16,953 s på uppvärmningsgrinden före menyklockan.
Faktaladdningen på betan tog 6,894 respektive 6,804 s; planerarens
städningssteg 2,495 respektive 2,460 s.

Varje prov använde första försöket utan dold omkörning. Inga JavaScriptfel;
planinformationen kontrollerades i alla fyra visningslägen. Samma BUILD_ID och
aktiva pris-ID:n verifierades före och efter proven. Förberedelseväntan ingår
inte i menylatensen; kvittot sparar väntetid och tillstånd. Enstaka publika
observationer på en delad server är inte en kontrollerad före/efter-jämförelse.

## Drift och återställning

BUILD_ID `app-b7c8d0506e23-c18e4ba9`. Image `sha256:a396c7774515c738a6b3909fb2b776d897bc48b29ddfc2d1064264f2ff97b8ad`.
Bas/återställningsbild `sha256:0c0f1720e9dd38555980ac1fc0e4c0f9402c242379570fa08fe69c5f87be73a6`. Sex runtimefiler ändrade;
1005 andra filer och runtimekonfigurationen verifierade.
Scheduler **source-ops-8a53beb80e43**, proxy, mountar och båda prismanifesten
bevarade. Bara appbild och BUILD_ID ändrades. Inga insamlingsprofiler eller scheman ändrades.

Verifierad full backup `/srv/smako/backups/20261101T064110Z` med befintligt driftlås.
Tidigare användarrader bevarade enligt radhasher:
{"consumer_plan_revisions": 331, "personal_private_state": 144, "member_accounts": 2, "member_sessions": 1, "member_auth_attempts": 4, "planner_owned_artifacts": 0}.
Retention före/efter: complete. Slutkontrollens aktuella 5xx-metriklista var tom;
inga incidenter var knutna till det nya bygg-ID:t. Lund och Malmö svarar HTTP 200/ready med rätt bygge.
Återställningsunderlag: `/opt/smako/evidence/app-b7c8d0506e23-c18e4ba9/`.
Använd befintlig appåterställning utan att skriva över senare användardata med äldre backup.

Första lokala kandidatkontrollen stannade på en felkodad svensk teststräng efter
kopiering. Testskriptet rättades till UTF-8 och samma oförändrade image passerade.
Ingen publik omkörning eller appregression döljs i det utfallet.
Sanerad [aktiveringsjournal](EVIDENCE.json); inga profiler eller cookies är med.
