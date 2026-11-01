# Uppföljning av varma menyprov, 2026-11-01

## Beslut och inställning

**V2:s begränsade uppvärmning och `SOURCE_FACTS_PREWARM_ENABLED=true` ligger kvar på betan.**
Den upprepade varma menyn blev i snitt 22,358 → 21,648 s i den kontrollerade
jämförelsen, och första menyn efter färdig uppvärmning 27,334 → 24,629 s.
Det tidigare publika provet på 53,500 s överlappade en ännu pågående
förberedelse. Det ger inte belägg för att återställa den gamla uppvärmningen.

Detta är **inte en förbättring för varje val**: de tre nya valen hade
0,145–1,016 s högre medeltid. Dessa utfall redovisas nedan. Två observationer
per läge/fall räcker inte för statistisk säkerhet om små skillnader eller
en generell latensgaranti. Beslutet innebär inte att dessa skillnader avfärdas.

| Funktion | Effektivt läge | Skäl och innebörd |
| --- | --- | --- |
| `SOURCE_FACTS_PREWARM_ENABLED` | `true`, befintligt standardvärde | Förbereder gemensamma fakta och recept efter start/prisbyte. Varm upprepning har inte försämrats i denna jämförelse. |
| `warm_recipe_library(current_only=True)` för V2 | På | Aktuella portionsvyer förbereds; historik laddas när den används. Gamla läget gav längre förberedelse och långsammare första/upprepade menyprov här. Detta är ett kodstyrt policyval, ingen separat miljöflagga. |
| Axfoods kataloglista för saknade detaljfiler | På, identisk i båda lägena | Hölls konstant för att isolera uppvärmningen. Den tidigare separata jämförelsen visade mindre faktarbete med identiska fakta. |

`SOURCE_FACTS_PREWARM_ENABLED=false` finns kvar som operatörens avstängning av
hela denna bakgrundsförberedelse. Den ändrar inte recept- eller prisgrindar,
men lämnar mer förberedelse åt första användningen. Den är inte samma sak
som att återställa enbart historikuppvärmningen. Den separata
`PRICE_UNIVERSE_PREWARM_ENABLED` är fortsatt `false`; den ändrades inte här.
Effektiva inställningar lästes från den aktiva containerns `get_settings()`.

## Varför 53,500 s inte var ett rent varmt prov

Appen startade 2026-10-31 21:39:44 UTC. Det tidigare publika provet pågick
21:43:08–21:44:15 UTC. Förberedelsens sista `ready`-kvitto skrevs
**21:44:14.356 UTC**, under detta prov. Kvittots metodsignatur matchar den
aktiva koden. Den kvarvarande kvittofilen och processens starttid är
oförändrade före och efter dagens publika prov.

Detta visar att testet inte hade säkerställt avslutad bakgrundsförberedelse.
Bakgrundstråden kan konkurrera med menyberäkningen om CPU/minne även utan
att hålla admissionplatsen. Det bevisar inte exakt hur mycket av skillnaden
43,547 → 53,500 s som överlappningen orsakade. Vanlig `/ready` visar att
appen/prisunderlaget är redo att ta emot anrop; den intygar inte att hela
`source_facts_prewarm` har status `ready`.

## Kontrollerad jämförelse efter avslutad uppvärmning

Ordning: full historik, endast aktuella, endast aktuella, full historik.
Varje körning använde en ny process och tom härledd diskcache. Båda aktiva
kommunerna förbereddes klart före första menyprovet. Endast
`warm_recipe_library(current_only=False/True)` varierades. Samma aktiva
betabild, planeringsmiljö, prisartefakter och Axfood-kod användes.

Alla tider är sekunder. Båda observationerna visas; sista kolumnen är
skillnaden mellan medeltiderna (positiv betyder långsammare med det nya läget).

| Menyprov | Gammal full uppvärmning | Ny begränsad uppvärmning | Ny minus gammal, medel |
| --- | ---: | ---: | ---: |
| Första italienska efter färdig uppvärmning | 27.234 / 27.433 | 24.474 / 24.784 | -2.705 s |
| Samma italienska val, varmt | 22.331 / 22.384 | 21.904 / 21.391 | -0.710 s |
| Nytt svenskt val | 22.952 / 22.750 | 22.562 / 23.430 | +0.145 s |
| Nytt grekiskt val | 22.634 / 22.878 | 22.776 / 23.820 | +0.542 s |
| Nytt italienskt val, en portion | 22.241 / 22.448 | 23.051 / 23.670 | +1.016 s |

Alla **20 av 20** klarade checkout-audit, sparning och identisk ägd återläsning.
Motsvarande fall har identiska valda recept, hela serialiserade varukorgars
SHA-256, faktaversioner och antal fakta (54 515). Priserna var 110,55 kr
för de två första fallen, sedan 104,23 / 106,90 / 88,61 kr.

Hela käll-/receptförberedelsen efter prisförberedelsen tog 110,029 / 101,046 s
med historik och 86,203 / 85,853 s utan den. Enbart receptdelen tog
26,180 / 26,028 respektive 11,419 / 11,079 s. Prisåterställning
(92,7–94,9 s) och prisförberedelse (~13 s) mättes separat.

Menygränsen omfattar `PersonalPlanner`-konstruktion, beräkning, audit,
sparning och ägd GET, med oförändrad 60 s-deadline. HTTP, admission och
browser ingår inte. Testcontainrarna hade 4 GiB, inget nät, skrivskyddade
offentliga källmountar och nya syntetiska plandatabaser i `/tmp`.
Produktionsplaner monterades inte. Val: Lund 22350, en middag, 17 valda
butikskontexter, köp i högst en butik, mjölk 1 l, 10–15 ingredienser,
italiensk/svensk/grekisk och en/två portioner. Ingen privat profil användes.

## Publik kontroll på färdiguppvärmd beta

Två nya gäster, ett försök vardera, efter att de isolerade proven avslutats:
**32,391 och 28,359 s** från klick till renderad meny. Båda klarade audit,
verifierad varukorg 110,55 kr, identisk sparad återläsning och UI-kontroller
utan JavaScriptfel. Båda var under 60 s. Samma menyval som det tidigare
publika provet. Dessa är nya observationer på aktuell kod, inte en publik
A/B-jämförelse mot den äldre appbilden.

Mätverktygets temaloop återanvände filnamnsvariabeln och skrev över det
första publika diskkvittot med det andra. Första kvittots värden återfördes
från den redan fångade standardutmatningen; andra kvittots originalbytes
bevarades. Det påverkade inte menyberäkningen. Inget prov kördes om.

## Drift, underlag och begränsning

Betans runtimekod, miljövariabler, appcontainer, prisaktivering och scheduler
var oförändrade under undersökningen. Betan ligger kvar på
`app-327fa573eb3f-0541cf49`. Både Lund och Malmö kontrollerades före/efter.
Detta är dokumentation av ett verifierat beslut, ingen ny appaktivering.

Se [maskinunderlaget](EVIDENCE.json) för alla 20 mätningar, stegtider,
beredskapsrapporter, kvittotider, publika försök och indatans kontrollsummor.
Körningen är begränsad till fem fall och två replikat per läge. Den visar
inte p95, samtidighet, hela valkatalogen eller att nya användarval alltid
blir snabbare. Ingen kvalitetsspärr, deadline eller urvalsregel ändrades.
Den kvarvarande starten med överlappande bakgrundsarbete är inte löst av
denna undersökning; håll den skild från färdiguppvärmd prestanda.
