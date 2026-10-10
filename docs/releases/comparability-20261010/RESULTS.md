# Jämförbara inköp – implementerad kandidat, inte aktiverad

Runtime `5786d5fa6a0febb7a581a70e583e5c876d494da2`, gren
`feature/comparability-20261010`. Bygger vidare på medlems-/viktkandidaten f00.
Ingen ändring av beta, produktionsdata, insamlingsschema eller Git-remote.
Generella medlemspriser tas med och valda medlemskrav visas, enligt f00.

## Förslag per fall och faktisk implementation

| Fall | Implementerat förslag | Verifierat utfall och kvarstående gräns |
| --- | --- | --- |
| Coop Scan fläskytterfilé, 65 kr/kg | Granska exakt tillkommande källfält; behåll separata fysiska butiksbindningar. | Värpinge 3659 och Klostergården 3820: källa → normalisering → databas → OWN → sökning → riktig PersonalPlanner → audit → sparad GET. 1 000 g behov ger uppskattad 1 kg-förpackning/65 kr, medlemskrav och max 2. Priset överförs inte till Online Syd. |
| Coop Vitlök, 57 g | Läs uttrycklig mängdtext när båda strukturerade mängdfälten saknas. | Autentisk `packageSizeInformation=57g` ger 57 g. 60 g behov: två förpackningar, flerpris 15 kr, godkänd audit. Ingen mängd härleds ur pris/jämförpris. |
| Coop aluminiumfolie, 10 m | Gör helt köppaket valbart utan att låtsas känna gram/liter. | Det tidigare blockerade exemplaret kan köpas: två paket à 29,95 = 59,90 kr. Längdoptimering är inte införd. Webbläsarprovet valde en annan exakt folierad: två à 24,95 = 49,90 kr. |
| Hemköp Krispsallat | Samma generella antal-köppaket-väg. | Två paket à 23,61 = 47,22 kr och audit. 150 g-behov stoppas fortfarande; jämförpriset används inte för att uppfinna vikt. |
| Willys Shi-take | Samma antal-köppaket-väg; kräver uttryckligt användarval. | Två paket à 46,90 = 93,80 kr och audit. Texten `150` saknar enhet; gramvikt förblir okänd. |
| Willys fläskfilé, 139 kr/kg och max 3 köp | Knyt köpgränsen till belagd styckbeställning, cirka 500 g och källans exakta kampanjidentitet. | 400/1 000/1 500/2 000 g ger uppskattat 69,50/139/208,50/293 kr. Fjärde paketet får belagt ordinarie 169 kr/kg. Gemensam gräns och oberoende audit förhindrar dubbel rabatt. Okänd gränsenhet stoppas fortsatt. Samma parserregel används av Hemköp. |
| ICA Chips och Sverige-/Fullkornspasta; Willys Crunchy | Visa befintligt villkorat kampanjval i den vanliga prisfria snabbmenyn. | Hela kampanjgrupper köps och ordinarie korg/audit/sparning används. Exakt variant, gram, allergener och näring påstås inte vara verifierade. De blir inte automatiskt receptingredienser. |
| Lidl Porchetta | Behåll befintligt explicit uppskattat viktköp och prova det tillsammans med ändringen. | Riktig korg, uppskattningsmärkning, audit och privat sparad GET passerar. Inget nytt Lidl-specialfall behövdes; inga blockerade Lidl-rader fanns i detta begränsade underlag. |
| City Gross | Visa täckningslucka med nästa steg: verifierat aktuellt butik-/kanalunderlag. | Ingen City Gross-källa i prisartefakten. UI visar luckan; det går inte att redovisa ett autentiskt produktfel eller kalla kedjan felfri. Ingen ny insamling gjord. |

Detta gäller gemensamma modeller och motorer, utan produktnamn eller produkt-ID
som specialfall i runtime. Identiteter ovan förekommer endast i tester/belägg.
Okänd mängd blir inte noll. Antal-köppaket är ett nytt uttryckligt val för en
exakt vara (eller säkra antingen/eller-alternativ), aldrig automatisk gramkonvertering.
Valen sparas privat och följer revisioner. Automatisk skafferibokföring av okänt
innehåll stoppas tills faktisk mängd är verifierad. Näringskrav i recept bevaras.

## Omfattning på samma frysta artefakt

42 492 källrader; samma priser, observationer och replayklocka 2026-10-10 12:00 UTC.
Detta är historisk replay, inte en aktuell prisoffert.

| Prisgrund | Före | Efter |
| --- | ---: | ---: |
| Känd förpackning | 40 100 | 40 100 |
| Vikt/enhetspris | 1 002 | 1 002 |
| Uttryckligt antal köpförpackningar, okänt innehåll | 0 | 956 |
| Inte säkert mängdjämförd | 1 390 | 434 |

De 956 är **rader**, inte unika produkter eller räddade recept: Coop 101,
Hemköp 191, Willys 664. Kvarvarande 434: Coop 2, ICA 398, Willys 34.
Öppna variantkampanjer kan nu väljas villkorat i inköpslistan även när de inte
kan jämföras per gram. Nya källparserresultat (Scan, vitlök, köpgräns) mäts
separat från denna oförändrade artefakt; de har inte smugits in i inventeringen.

## Verifiering

- 296 backend-/källtester PASS mot slutlig **appimage**, inga runtimekällmounts.
  Täcker mängd, pris, medlemskap, datum, köpgräns, fel butik, oberoende audit,
  shopping, gammal JSON, näring, privat lagring och negativa källkontrakt.
- 114 källtester PASS även mot separat källimage (överlapp med de 296, inte 410 unika tester).
- Mobila Chromium och WebKit PASS med riktiga knappflöden och vanlig planerare:
  prisfria förslag, två köppaket, sparad varulista/omladdning, dubbelklick med
  ett start-POST, faktisk resultatrendering, audit, tillagd kampanj,
  omräkning till revision 2, oförändrad revision 1 och fel ägare 403.
  Inga pageerrors, misslyckade nätanrop eller HTTP 5xx i dessa prov.
- Publik produktsökning PASS i båda webbläsarna: pris per köpförpackning och synlig City Gross-täckningslucka. Första provet missade att stänga välkomstdialogen; råfelet är bevarat och testhjälparen rättad.
- 24 appfiler, 7 källimagefiler och 6 faktiskt HTTP-serverade HTML/JS-filer
  hashmatchar leveransen. Befintliga status-/receptflödets oförändrade delar
  återanvänder f00:s versionsbundna bevis; de räknas inte som nykörda här.
- Försök som stoppades av saknad pytest-asyncio i testmiljön är bevarade.
  Separat testplugin monterades; produktionsimagen ändrades inte.
- Första byggförsöket stoppades korrekt av en baskontroll: tidigare appimage
  saknade den redan granskade Hemköp-källfixen från 04e. Exakta gamla hashvärden
  pinnades och dess modellberoende togs med. Ingen generell hashspärr stängdes av.

Ingen fysisk iPhone eller provlagning. Ingen ny prestandaförbättring hävdas.
Isolerad server: två CPU, 3 GiB, full fryst prisartefakt och offentlig faktabas,
ny tom testlagring. Ingen produktionsplan kopierad.

[Källbelägg och kvarstående research](RESEARCH.md) · [Maskinläsbara bevis](EVIDENCE.json)
· [Separata paket och framtida aktivering](ACTIVATION.md)
