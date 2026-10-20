# Kategorimedveten receptsökning och Willys-kvittens, 2026-10-20

Status: kandidat verifierad och byggd; aktivering väntar på driftlås.
Utgår från main `254f142` och den aktiva appen
`app-bac0fc15ca9a-512ef3ea`. Användaren har godkänt implementation,
driftåtgärd, commit och aktivering på betan.

## Sökändring

- `remaining_category_capacity` beräknar återstående platser med samma
  kategorisering som slutkontrollen. Explicit noll utesluter kategorin;
  ospecificerade kategorier delar de återstående fria platserna. Vid byte
  räknas alla kvarvarande rätter i samma måltidstyp in. Omöjliga kategorier
  stoppas före produktmatchning och individuell korg-/näringskvalificering.
- `category_seed_cap` fördelar befintlig sökbudget proportionellt över
  möjliga kategorier. Billiga recept, förpackningsöverlapp, matkök och olika
  grundrätter skyddas, följt av kulinarisk spridning. Varianter av en
  grundrätt räknas inte som flera olika grundrätter. Okänd individuell
  prisinformation behålls, och skyddade representanter får överskrida taket.
- När bara en kategori är möjlig används det tidigare ekonomiska urvalet,
  med komplettering endast om för få olika grundrätter finns kvar. Det
  undviker onödig omfördelning inom exempelvis en helt vegetarisk meny.
- Hela den kvalificerade poolen finns kvar för befintlig reservsökning när
  arbetsurvalet inte ger en giltig meny. Gemensam korg, förpackningar,
  butikstak, näring, allergier och slutlig kassakontroll är oförändrade.

Inga nya recept eller lägre globala söktak införs. Utan kategorival används
befintligt kategorioberoende urval. En mindre arbetslista är en heuristik,
inte ett bevis på lägsta möjliga pris eller att en meny är globalt omöjlig.
Ingen användarhistorik eller slump införs; variation mellan veckor får inte
påstås vara verifierad bara för att en meny innehåller olika grundrätter.

## Verifiering

Riktade offlineprov täcker exakta/noll/partiella kvoter, alla vegetariska,
uttömmande möjliga fortsättningar för små menyer, gallring före
produktmatchning, receptbyte med fasta grannrätter, saknat prisunderlag,
distinkta grundrätter och reservsökning.
Testerna använder inga privata profiler och gör inga butiksanrop.
Slutkoden `73306ac` klarar 26 riktade tester för kategorier, befintligt
urval, fullbiblioteksreferens och bokade receptbyten. Ruff och compileall
är godkända. Testerna med 1 000/2 000 syntetiska recept verifierar enbart
urvalets skala, inte köpbarhet eller svarstid för ett utökat riktigt bibliotek.
Full CI för `73306ac`: **2 854 PASS, 10 kända XFAIL, 53 SKIP**;
uppstart, ändrade Pythonfiler och installerade browserprov är godkända.
[CI-kvitto](https://github.com/ossebosse/smako/actions/runs/39493853316).

Den verkliga jämförelsen använder `benchmark_category_search.py` och den
befintliga acceptansmatrisen: samma frysta priser, fakta, klocka,
butiksurval och receptbibliotek för båda versionerna. Separata kalla
processer och tomma förberedelsecacher, därefter en varm upprepning.
Linuxcontainer utan nät, 2 CPU och 3 GiB RAM; separata syntetiska tillstånd.
Kassakontroll, näringskrav, exakta kvoter, butikstak och olika grundrätter
verifieras mot resultaten. Fullbiblioteksreferensen är fortfarande en
begränsad sökalgoritm, inte ett globaloptimum.

Det första försöket inkluderade även PR #4:s separata rättning för färdiga
vinnare från tidigare publiceringssteg (`e6f7d32`/`ea847bb`). För fem
vegetariska rätter i Lund ökade då kall tid 33,54 → 64,20 s och
korgberäkningar 1 347 → 3 498, vid samma pris 535,06 kr. Den ändringen
återställdes före aktivering. Slutreleasen ändrar inte generationssökningen;
dess befintliga giltiga kandidat behålls under jämförelserna. En generell
garanti för färdigoptimerade äldre bibliotek ligger kvar i det separata
skalningsarbetet. Inga överlägsna mätvärden från den kasserade kombinationen
får tillskrivas slutkandidaten.

## Slutmätning mot main 254f142

Slutkod `73306ac`, oförändrat registrerat bibliotek med 222 recept.
Samtliga 24 körningar passerade. Indatahashar, klocka och exakt begäran
matchar mellan respektive bas/kandidat. Kall/varm körning ger samma
semantiska resultat inom varje arm. Alla menyer har fem olika grundrätter.
Kategorifallen begär inga särskilda näringsmål; de ska inte beskrivas som
nya prestandabevis för näringsbegränsade menyer.

| Fall | Bas kall/varm, s | Kandidat kall/varm, s | Pris före → efter, kr | Matkök före → efter | Korgberäkningar före → efter |
| --- | ---: | ---: | ---: | ---: | ---: |
| Lund 1 kyckling, 2 veg, 2 kött | 74,40 / 65,57 | 35,63 / 29,20 | 640,20 → 640,20 | 4 → 4 | 5 593 → 1 339 |
| Malmö 1 kyckling, 2 veg, 2 kött | 102,05 / 95,18 | 47,54 / 39,02 | 685,27 → 685,27 | 3 → 3 | 4 535 → 1 134 |
| Lund 5 vegetariska | 33,54 / 26,99 | 36,90 / 32,74 | 535,06 → 535,06 | 3 → 3 | 1 347 → 1 729 |
| Malmö 5 vegetariska | 44,05 / 39,45 | 44,83 / 35,89 | 534,92 → 534,92 | 3 → 3 | 1 013 → 1 191 |
| Lund 1 kyckling, 2 veg, 2 fria | 76,78 / 73,17 | 39,63 / 34,02 | 640,20 → 640,20 | 4 → 4 | 5 865 → 1 636 |
| Malmö 1 kyckling, 2 veg, 2 fria | 105,59 / 98,97 | 50,67 / 42,61 | 656,42 → 656,42 | 3 → 3 | 4 686 → 1 242 |

Det är cirka halverad tid för blandade kategorier, inte en allmän
hastighetsgaranti. Helt vegetariskt i Lund är långsammare. Tidig gallring
ändrar även vilka sökvägar som hinns med inom befintliga budgetar.
Minnestoppen för kandidaterna är 1,50–1,52 GiB i Lund och 2,37–2,40 GiB
i Malmö. Två upprepningar per fall ger ingen statistisk latensgaranti.
Ordinarie källjobb kunde arbeta samtidigt på värden; testcontainrarna
kördes sekventiellt. Inget butiksanrop gjordes av testkörningarna.

Fryst arkiv: SHA-256
`ea895f92ec8bb6f4d6d953eb93243fcfebc37bf6df809ec118bbfc053aeee670`.
Slutunderlag: `/opt/smako/evidence/category-search-20261020-v3/output/`.
Fullpoolskontrollen (`--uncapped`, en kall körning per kommun) är godkänd:
Lund 45,18 s / 640,20 kr / fyra matkök / 2 400 korgberäkningar;
Malmö 56,50 s / 685,27 kr / tre matkök / 1 514 korgberäkningar.
Samma pris och matkök som arbetsurvalet i båda 1+2+2-fallen, med identiska
indata och fem olika grundrätter. Fullpoolen kör fortfarande en begränsad
heuristisk sökning och bevisar inget globaloptimum.

Kandidatbild `sha256:0ad2b6021e6a71b5a849edb42430d0a94c33ea152e58984353de8124182a0830`,
BUILD_ID `app-73306acc382d-0d139487`. Tre granskade appfiler ändrade,
696 övriga runtimefiler hashidentiska, runtimekonfiguration och platt bild
verifierade. Isolerat prov utan nät på exakt image klarar appimport,
admininställning, samtliga 222 registrerade recept, kategoriurval och
kapacitetsberäkning vid byte. Förkontrollens retention är godkänd;
32 äldre snapshots pensionerade och 1 821 491 766 byte filer borttagna.
Aktivering väntar på det ordinarie Lundjobb som startade 22:00 UTC.

## Driftsfelet och genomförd återställning

Aktuell relälogg visar `RefreshAlreadyRunningError` vid mottagarens
driftlås 16:14 UTC. Den schemalagda leveransen avslutades därför med kod 1;
det var inte ett fel i de kvalificerade produktposterna. En senare
driftläsning visar samma nya Willys-artefakt importerad, publicerad och
laddad för båda Lundbutikerna, men lokalt saknades beständig kvittens.

Installerad release `2464596b6f07` kontrollerades mot sitt manifest:
685 filer, Python 3.12.10, godkänd installationskontroll. Ordinarie reläväg
återlevererade endast Lunds exakt verifierade artefakt
`e28d4c89b1011643abe4415b1621ccccd143d6ca1b67102eecda62436240f650`.
Ny insamling var uttryckligen spärrad i operatörshjälparen. Befintliga
kommun-, workflow- och serverlås bevarades.

Kvittens mottogs **20:11:30 UTC**, `already_active`, och körningen
avslutades med kod 0. Ursprunglig observation är fortsatt
**15:32:59 UTC**, snapshot `eec0850fbc3c477f9b31cb2dbc739055`.
Inget schema eller installerad reläkod ändrades. Det gamla schemalagda
försökets LastTaskResult skrivs inte om för att dölja dess fel; den nya
beständiga kvittensen bevisar återställningen. Vanlig konkurrens om
driftlåset kan fortfarande göra ett enskilt försök uppskjutet/misslyckat.

Privat underlag finns i `.local/category-search-20261020/` och
`/opt/smako/evidence/category-search-20261020/`; inga råprofiler,
databasfiler, sessionsuppgifter eller hemligheter ingår i Git.
