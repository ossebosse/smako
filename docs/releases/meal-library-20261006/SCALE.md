# Avgränsade skalprov

Två CPU, 3 GiB, en tung beräkning åt gången, samma frysta underlag och P2-kod som slutimagen. Ingen sänkt sökbudget. Varje faktor/fall är ett avgränsat prov, ingen p95 eller treprovsskattning. De ordinarie P0–P3-fallen har separata tre kalla/tre varma körningar.

Syntetiska poster ändrar identitet, mängdoperander och metadata för befintliga stödda metoder. De ger både relevanta middagssökalternativ och innehåll som sorteras bort för frukost före tung korgberäkning. De är inte granskade nya grundrätter, köpbevis eller smakbevis och ingår inte i de 30 levererade recepten.

| Storlek | Fall | Aktuella poster | Syntetiska | Import/förberedelse (s) | Ny kall process (s) | Cgroup-topp (GiB) | Utfall |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1× | main | 176 | 0 | 0,38 | 95,87 | 1,390 | PASS |
| 1× | breakfast | 176 | 0 | 0,46 | 55,59 | 1,381 | PASS |
| 2× | main | 352 | 176 | 2,19 | 219,17 | 1,409 | PASS |
| 2× | breakfast | 352 | 176 | 2,10 | 64,83 | 1,405 | PASS |
| 5× | main | 880 | 704 | 8,37 | 919,89 | 1,619 | PASS |
| 5× | breakfast | 880 | 704 | 8,21 | 78,29 | 1,336 | PASS |

Minnet klarar 5× inom 3 GiB efter den generella begränsningen av samtidigt levande korgobjekt. Tiden för relevant middagssökning växer däremot från 95,87 till 219,17 och 919,89 sekunder. Detta bevisar inte snabb planering i stora relevanta bibliotek. Frukost växer 55,59→64,83→78,29 s i kalla processer. Ett tidigare 2×-OOM och övriga första försök är bevarade; slutproven ersätter inte deras orsaksunderlag.

[Fulla operander, sökdiagnostik, förberedelse och råfilshashar](SCALE.json). Syntetiska korgsummor får inte användas som konsumentbesparingar.
