# Kategorimedveten receptsökning och Willys-kvittens, 2026-10-20

Status: kandidat verifieras; ingen appaktivering påstås ännu.
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

Resultat och aktivering kompletteras efter avslutad verifiering.

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
