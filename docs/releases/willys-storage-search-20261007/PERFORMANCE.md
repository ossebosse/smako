# Parade lokala prestandaprov – slutmatris pågår

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
| 5× P2 | 1/1 | 866,53 s | 516,53 s | -40,39 % |

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

Varm tid är fakta + ny planerare + serialisering, inte läsning av färdig
plan. Första uppvärmningsberäkningen finns kvar i råunderlaget och hela
containerns totalsiffra, men ingår inte i den varma medianen.
Råtider, min/max, CPU, RSS, cgroup, förberedelser och separata processer med
beständiga artefakter finns i PERFORMANCE.json. Minnet är processens
ackumulerade topp. CPU-differenserna omfattar fakta och planerare, inte
serialisering eller den tidigare prisinläsningen. Ingen p95 skattas.

Klicktider och strikta återhämtningsprov redovisas i SEARCH.md och
BROWSER-EVIDENCE.json. A:s produktionshinder är separat från dessa replayprov.
