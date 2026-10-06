# Prestanda och resurser

Alla jämförbara backendled: två CPU, 3 GiB, en tung beräkning åt gången, samma beroenden och frysta underlag. Ingen färdig meny återanvänds för nyberäkning.

Status: slutlig matris färdig.

| Led | Fall | Kall process, median (s) | Ny process med artefakter (s) | Varm nyberäkning, median (s) | Högsta cgroup (GiB) |
| --- | --- | --- | --- | --- | --- |
| p0 | main | 86,49 | — | 53,62 | 2,072 |
| p1b | main | 97,91 | 84,45 | 57,71 | 1,500 |
| p2final | main | 95,95 | 84,45 | 57,56 | 1,530 |
| p2final | simple | 56,62 | 45,35 | 17,90 | 1,417 |
| p2final | breakfast | 52,49 | 41,22 | 14,15 | 1,377 |
| p2final | snack | 51,53 | 40,23 | 13,80 | 1,383 |
| p2final | combined | 67,02 | 54,68 | 26,00 | 1,431 |
| final | main | 95,87 | 87,51 | 57,11 | 1,500 |
| final | simple | 66,90 | 57,74 | 28,37 | 1,407 |
| final | breakfast | 60,73 | 49,43 | 21,07 | 1,385 |
| final | snack | 58,74 | 47,32 | 19,85 | 1,385 |
| final | combined | 87,57 | 77,12 | 48,25 | 1,441 |

Kall process mäter containerstart, Python, återläsning av PriceUniverse, fakta, planerare och serialisering. Den varma kolumnen är fakta plus ny planerare i redan startad process; universum har redan lästs. Första uppvärmningsberäkningen finns i råfilen men ingår inte i medianen. Artefaktkolumnen är en separat ny process per fall.

Varje färdig grupp har tre kalla och tre varma nyberäkningar. Råtider, min/max, spridning, RSS, cacheträffar och processomkostnad finns i [PERFORMANCE.json](PERFORMANCE.json). Ingen säker p95 skattas från tre körningar. RSS är processens ackumulerade topp, inte iterationens nya minne.

## Klick till visat resultat

Slutligt ostört huvudfall: Chromium 63,875 s och WebKit 63,281 s. 60-sekundersmålet är inte uppnått. Små frukost-/mellanmålsflöden tog 25,828/24,032 s inklusive kontrollerad återhämtning; de är inte ostörda backendmedianer. Kombinerad vecka tog 59,859/52,047 s med separat förlustinjicering respektive dold sida/offline. [Webbprov](BROWSER-EVIDENCE.json) skiljer kö, beräkning och klientleverans.

## Förberedelse och lagring

Ordinarie CLI för hela utfärdade biblioteket och portioner 1/2/4: 42,853 s inuti processen, 47,407 s inklusive container; cgroup-topp 1,505 GiB. Cirka 8,55 MB artefakter. Struktur-/skalning förbereds vid innehålls-/metodändring, offentliga källprojektioner vid ändrad källsignatur. Privata begäranskrav och slutlig audit körs fortfarande. Separat CPU-mätning redovisas när råprovet är avslutat.

Beständiga artefakter är hashkontrollerade och begränsade i storlek och generationer. Proven använder värdens tmpfs och kopierar evidens med hash till D:; tmpfs överlever appomstart men inte värdomstart. Detta är isolerad testlagring, inte en rekommendation att flytta produktionsdata till RAM.

Skalprov och inkrementella källändringar redovisas separat. Syntetiskt innehåll räknas inte som recept, matkvalitet eller konsumentmenyer. Bibliotekstillväxt kräver fortfarande mer relevant kandidatarbete; global kostnadsoptimalitet är inte bevisad.
