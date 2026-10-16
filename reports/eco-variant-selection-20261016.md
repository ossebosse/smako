# Mindre arbete i ekosökning och begränsat varianturval

Lokalt arbete i `D:\Projects\Smako`, gren `perf/eco-and-variant-selection`,
bas `a294a71`. Beställning: punkt 3–4 i prestandalistan, därefter granskning av
punkt 5 i den ursprungliga produktplanen (bättre optimering av hela veckan).
Ingen betaaktivering, källinsamling eller ändring av användarkrav.

## Genomfört: punkt 3

De befintliga säkra prisgränserna, offertcacherna och butiksberäkningarna återanvänds.
Efter att den vanliga prismotorn har valt exakt vinnande produkter och butiker kan
ekosökningen kontrollera ekoandelen direkt på offertvärdena. Ett sådant avslag
slipper bygga alla publika korgmodeller. Det väljer inte andra produkter och
ändrar inte pris, butiksval, kvalificering eller avrundning. Gemensamma kampanjer
och egna kalkylatorer behåller den fullständiga vägen. Varje kvarvarande korg
kontrolleras dessutom av den befintliga eko- och slutkontrollen.

Högst 32 lyckade ekoberäkningar sparas inom samma planerare. Nyckeln tar en ny
värdekopia av kandidater inklusive muterbara erbjudandelistor, källuppgifter och
köpvillkor samt aktuell verifierad ekoegenskap. Den innehåller också ordnade
behov med exakta mängder/enheter, matklassning, butiker, verifieringspolicy,
butikstak och ekoandel. Returnerade modeller kopieras så att en efterföljande
ändring inte skadar cachen. Ingenting delas mellan användare eller begäranden.

Den ursprungliga ordningen och budgeten om högst 256 delmängder är kvar, liksom
första vinnaren vid lika pris. Avslag på offertval räknas fortfarande som en
kontrollerad kombination i felmeddelandet. Nya räknare skiljer cacheträffar och
avslag på ekoandel från de tidigare kostnadsgränserna.

## Genomfört: punkt 4

Stora variantfamiljer får normalt fyra alternativ per grundrecept i startsökningen.
Alla grundrecept behålls. Urvalet återanvänder `stratified_candidate_shortlist`
och den redan gjorda individuella kvalificeringen. Skyddade alternativ är:

- första kvalificerade varianten i urvalet;
- lägst faktisk inköpssumma när receptet prövas enskilt;
- starkast överlapp av valda produktidentiteter med andra grundrecept;
- min/max för varje efterfrågat och kvalificerat närings-/viktmått.

Skyddade alternativ får överskrida fyra: högst tre plus två per efterfrågat mått.
Saknade jämförelsevärden behåller hela familjen. Kulinariska dimensioner och
produktidentiteter väljer återstående platser. Ursprunglig receptordning bevaras.
Pris och näring här är urvalssignaler, aldrig ersättning för veckans checkout.
Skafferi och erbjudanden ingår redan i den enskilda kvalificering som ger signalerna.

Om det begränsade urvalet inte ger en giltig startmeny körs samma generation med
hela urvalet. Alla kvalificerade recept ligger kvar för enskilda och parvisa
förbättringsbyten. Sökspåret visar tillgängliga/behållna alternativ över
måltidspositionerna samt om det fullständiga omförsöket användes.

Inga recept-ID:n är hårdkodade. Stresstest med 300 syntetiska varianter i samma
familj behåller de fyra skyddade alternativen; separata test kontrollerar fler
näringsmått, gemensamma produkter, saknat underlag och det verkliga biblioteket.
Kvalificering och senare enskilda bytesprov växer fortfarande med biblioteket.
Detta är ingen garanti om konstant svarstid för tusentals nya recept.

## Granskning: punkt 5

Följande finns redan och ska fortsätta vara den enda prisvägen:

| Del | Befintligt stöd |
| --- | --- |
| Samma ingrediens i flera rätter | Gemensamma inköpsbehov aggregeras före prissättning. |
| Skafferi | Tillgänglig, reserverad och använd mängd fördelas före inköpet. |
| Förpackningar | Verkliga förpackningsmängder, användbar mängd och avrundade antal. |
| Butikstak | Hela korgen optimeras inom valt tak; snävare jämförelseurval kan behållas. |
| Erbjudanden | Kvalificerade medlemsvillkor, kampanjdatum, köpgränser och gemensamma kampanjer. |
| Sökning från giltig meny | Enskilda byten och högst 128 parvisa byten; hela korgen räknas om. |
| Slutkontroll | Ny komplett mängd-, pris-, närings- och variationskontroll. |

Två konkreta luckor återstår, i föreslagen ordning:

1. **Parvisa byten som bara klarar kraven tillsammans.** Dagens åtta alternativ
   per måltid kommer från giltiga enskilda bytesprov. Ett byte kan därför saknas
   i parurvalet trots att ett andra byte återställer den begärda fördelningen eller
   variationen. Lägg till ett separat, begränsat parurval direkt från kvalificerade
   recept, rankat efter gemensamma inköpsbehov, produktidentiteter och enskilt pris.
   Kontrollera båda bytena tillsammans före checkout. Behåll befintliga parförslag
   så att nya heuristiska förslag inte tränger undan tidigare vinnare.
2. **Mindre överskott vid samma faktiska inköpssumma.** Dagens slutrankning är pris,
   befintlig smakpoäng och namnordning. `surplus_mode=minimize` undviker det
   uttryckliga steget för större strategiska inköp, men ger ingen allmän
   överskottsrangordning mellan lika dyra menyer. Inför en dokumenterad sekundär
   jämförelse från verifierad köpt användbar mängd och oanvänd mängd, både vid
   likvärdiga produktval och vid menyval. Summera inte gram, milliliter och styck
   som samma dimension. Ett möjligt mått är kvarvarande andel av betald varukostnad;
   det ska redovisas separat och aldrig dras av från den faktiska inköpssumman.

Gå därefter vidare till begränsade samtidiga byten av tre rätter om mätningarna
visar nytta. Alla förbättringssteg ska starta från och behålla den giltiga menyn,
återanvända befintlig prismotor och ha separat sökbudget. För punkt 5 behövs
regressionsfall med fördelningskrav som bara ett gemensamt byte klarar,
förpackningsgränser, skafferireserveringar, butikstak, kampanjpaket och lika pris
med olika kvarvarande mängd. Mät både verkligt betald summa, överskott per dimension
och extra beräkningstid. Dessa återstående ändringar ingår inte i denna etapp.

## Mätning och verifiering

Samma frysta 22225-underlag som föregående etapp: 26 840 produkter, 19 tillåtna
butikskontexter, explicita produktfakta och klockan `2026-10-15T13:00:00+00:00`.
Indata kontrolleras mot `.local/planner-preparation/inputs/matrix-inputs.json`.
Ingen färdig menycache; nätverk är blockerat. Tid avser planering, exklusive
laddning av prisartefakten och den separata oberoende resultatverifieringen.
Kall/varm avser samma process per profil med separat förberedelsecache per profil.

| Profil | Före kall / varm, s | Efter kall / varm, s | Inköpssumma, kr |
| --- | ---: | ---: | ---: |
| Ekoandel minst 20 % | 144,09 / ej mätt | 121,86 / ej mätt | 434,13 |
| Standard | 49,97 / 25,94 | 49,91 / 25,94 | 674,16 |
| Minst 40 g protein | 33,44 / 8,30 | 33,50 / 8,43 | 1 184,12 |
| Frukost + mellanmål + vikt | 24,54 / 2,06 | 25,31 / 2,11 | 85,55 |
| Alla fyra makronäringskrav | 33,76 / 8,40 | 33,10 / 8,62 | 1 184,12 |
| Veganskt | 27,73 / 3,57 | 27,79 / 3,53 | 478,17 |
| Angiven måltidsfördelning | 33,77 / 10,10 | 34,40 / 10,16 | 1 107,34 |

Alla positiva profiler behåller full semantisk resultathash och inköpssumma i
båda körningarna. Mjölkallergi, ekologiska animalier och omöjligt proteinmål är
fortsatt blockerade: 25,68/1,14, 25,94/1,41 respektive 27,72/3,39 sekunder.
Totalt tio profiler och 19 körningar. Högsta observerade processminne är
825,13 MiB mot 825,27 MiB i föregående serie; detta är inte minne per användare
eller en mätning av samtidig serverlast.

Ekofallet är 22,23 sekunder, **15,4 %**, snabbare i denna jämförelse. Samma
inköpssumma, meny och ekoandel 23,4953 % behålls. 45 476 exakt prissatta val
avvisas före modellbygge på otillräcklig ekoandel. Den extra cachen med 32
ekokorgar gav inga träffar i detta fall; vinsten ska därför inte tillskrivas den.
En tidigare prototyp med 128 poster gav bara en träff och behöll mer minne;
den mindre slutliga gränsen används. Cacheåteranvändningen verifieras separat
med upprepade identiska behov och ändringar av beroendena.

Övriga tidsförändringar är små och bevisar ingen förbättring. Punkt 4 skyddar
framför allt startens kombinationssökning när familjer får många fler varianter;
en märkbar aktuell tidsvinst från det urvalet har inte påvisats. Globala lägsta
priset, prisstabilitet för varje framtida bibliotek och konstant svarstid är
inte bevisade. Sökningen kan fortfarande missa kombinationer utanför urvalen.

Rådata: `.local/eco-variant-selection/final/after-<profil>.json` och
`.local/eco-variant-selection/matrix-summary.json`. Jämförelse:
`.local/incremental-library/final/after-<profil>.json`. Körhjälpare:
`.local/eco-variant-selection/matrix.py`. Slutseriens metodsignatur:
`7582db517224f7b211e502c72c68029e7e96a98adc8eab2d236d2827c145bde3`.

```powershell
$env:PYTHONPATH='backend;.'
$env:PYTHON_DOTENV_DISABLED='1'
.venv\Scripts\python.exe -X utf8 backend/scripts/combined_performance_probe.py --matrix --inputs .local/planner-preparation/inputs --output .local/eco-variant-selection/recheck --label recheck --matrix-case organic-share --repeat 1
```

Kodverifieringen omfattar ekvivalens mot ekosökning utan tidiga avslag, inklusive
förpackningar, kampanjer, butikstak, första lika pris, icke-mat och egna kalkylatorer.
Cacheprov täcker ändrade mängder, ekoandel, butikstak, erbjudanden och faktaunderlag,
separata planerare, oberoende resultatmodeller och minnesgräns. Variantproven
täcker breda familjer, näringsextremer, gemensamma produkter, fallback till hela
urvalet och förbättringar från varianter utanför startsökningen.

**445 regressionstester passerar** i 24 berörda moduler via `scripts/verify_offline.py`
med `SMAKO_VERIFY_LABEL=eco-variant-regression`, liksom Ruff och compileall.
Isoleringslogg: `.local/verification/eco-variant-regression-access.json`, utan
rapportläsningar eller blockerade nätverks-/historiska workspaceförsök.
De 18 befintliga serialiseringsvarningarna gäller syntetisk `semantic_confidence`
i prestandafixturer. Mätserien visar också två varningar när befintliga internt
kopierade kandidatvärden (`high`, `estimated`) serialiseras; representation och
resultat verifieras oförändrade. Inga tester misslyckas.
