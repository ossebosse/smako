# Parade lokala prestandaprov

Samma frysta underlag, begäran, bibliotek och klocka före/efter. Två CPU,
3 GiB och en tung planerare. 1×/2×/5× är den tidigare syntetiska P2-korpusen;
huvudfallet använder det verkliga P3-biblioteket med 24 + 6 tillägg.
Historiska servertider är separata observationer, inte kontrollgruppen här.

## Hela kalla processer

| Fall | Antal före/efter | Före median | Efter median | Förändring |
| --- | ---: | ---: | ---: | ---: |
| Huvudfall P3 | 3/3 | 118,37 s | 111,16 s | -6,09 % |
| 1× P2 | 1/1 | 117,96 s | 109,87 s | -6,86 % |
| 2× P2 | 1/1 | 239,63 s | 227,83 s | -4,92 % |
| 5× P2 | 3/3 | 892,01 s | 534,79 s | -40,05 % |

Här ingår containerstart, Python, innehållsförberedelse, prisinläsning,
fakta, sökning, slutkontroller och serialisering. Skalverktygets särskilda
förberedelsetimer börjar efter dess första `current_recipes()`-anrop;
det tidigare arbetet ingår fortfarande i den fulla processtiden ovan.

## Varma nyberäkningar

| Fall | Antal före/efter | Före median | Efter median | Förändring |
| --- | ---: | ---: | ---: | ---: |
| Huvudfall P3 | 3/3 | 51,09 s | 48,39 s | -5,28 % |
| 1× P2 | 3/3 | 52,23 s | 49,16 s | -5,88 % |
| 2× P2 | 3/3 | 161,04 s | 155,64 s | -3,35 % |
| 5× P2 | 3/3 | 775,67 s | 419,03 s | -45,98 % |

Varm tid är fakta + ny planerare + serialisering, inte läsning av färdig
plan. Första uppvärmningsberäkningen finns kvar i råunderlaget och hela
containerns totalsiffra, men ingår inte i den varma medianen.
Råtider, min/max, CPU, RSS, cgroup, förberedelser och separata processer med
beständiga artefakter finns i PERFORMANCE.json. Minnet är processens
ackumulerade topp. CPU-differenserna omfattar fakta och planerare, inte
serialisering eller den tidigare prisinläsningen. Ingen p95 skattas.

## CPU och minne

Kall CPU nedan är containerns ackumulerade CPU till efter serialiseringen,
inklusive förberedelse och första prisinläsning; sista loggskrivning och
processavslut ligger efter avläsningen. Minnet är högsta uppmätta
cgroup-topp i respektive kalla serie, inklusive filcache och tmpfs.

| Fall | CPU före/efter, median | Minnestopp före/efter |
| --- | ---: | ---: |
| Huvudfall P3 | 85,50 / 79,11 s | 1,55 / 1,31 GiB |
| 1× P2 | 86,02 / 78,98 s | 1,25 / 1,21 GiB |
| 2× P2 | 198,64 / 186,08 s | 1,40 / 1,35 GiB |
| 5× P2 | 814,53 / 463,25 s | 1,64 / 1,55 GiB |

## Ny process med beständiga förberedelser

Ett par per profil. Tiden omfattar hela processen, inklusive prisinläsning
och fakta. Förberedelseartefakterna kommer från respektive versions tidigare
huvudprov; inget färdigt planresultat återanvänds.

| Profil | Före | Efter | Inköp före/efter, historisk replay |
| --- | ---: | ---: | ---: |
| main | 77,65 s | 75,18 s | 741,15 / 741,15 kr |
| simple | 55,43 s | 51,07 s | 262,28 / 262,28 kr |
| breakfast | 47,18 s | 44,42 s | 40,70 / 40,70 kr |
| snack | 45,92 s | 42,08 s | 56,86 / 56,86 kr |
| combined | 73,59 s | 68,89 s | 418,17 / 418,17 kr |
| crafted | 75,19 s | 71,73 s | 787,56 / 787,56 kr |

Den lokala arbetsstationens övriga appar var igång. ENVIRONMENT.json
redovisar hårdvara, ledigt minne, D:-lagring och den befintliga WSL-swapen
på C:. Ingen systemomfattande Docker-/WSL-flytt eller resursökning gjordes.
1× och 2× har endast ett kallt par; deras kalla siffror skattar ingen spridning.

Klicktider och strikta återhämtningsprov redovisas i SEARCH.md och
BROWSER-EVIDENCE.json. A:s produktionshinder är separat från dessa replayprov.
