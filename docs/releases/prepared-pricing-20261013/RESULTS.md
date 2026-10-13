# Förberedda prisvillkor och kommunvis menyförberäkning

## Förändringar

- Oföränderliga erbjudanden normaliseras en gång och återanvänds. Referenser,
  datum, pant, kampanjvillkor och exakta prisrepresentationer ingår i identiteten.
- Exakt kassapris återanvänds för samma antal förpackningar, bas-/ordinariepris,
  erbjudanden, datum och Decimal-kontext. Mängdtak och kombinationsregler beräknas
  fortfarande av den befintliga kassaprislösaren; inga ungefärliga priser används.
- Den innersta butiksjämförelsen summerar redan avrundade, icke-negativa priser
  i heltalsören. Ovanliga exponenter, precisioner och stora värden använder
  ursprunglig Decimal-beräkning. Alla butikskombinationer och kandidater kvarstår.
- Efter uppstart och atomiskt prisbyte köas standardmenyer för varje laddad kommun.
  Readiness och prisaktivering väntar inte på menyer. Befintliga användarjobb har
  företräde innan en bakgrundsberäkning startar. En redan startad beräkning kan
  däremot innebära väntetid för en användare som kommer senare.

Förberäkningen använder webbens exakta mängdpolicy, annonserade medlemspriser,
5 middagar, 2 portioner, högst 3 butiker och balanserat val. Samma sökning räknar
också fram billigast och varierat. Den gör inga kedje- eller LLM-anrop.
Kommunens aktiva prisunderlag och lokala postnummer väljs automatiskt. Även nya
kommuner använder samma kö och kalkylkod; inga kommunvisa kodkopior behövs.

## Kvalitet och lokal mätning

Samma frysta prisunderlag och klocka, nätverk blockerat. Hela PlanResponse för
både kall och varm körning samt sökräknare är identiska före/efter, med endast
`timings_seconds`, `timings_ms` och `span_statistics` borttagna vid jämförelsen.
Det omfattar menyer, kampanjer, inköpslistor, verifiering och alla alternativ.

| Körning | Före | Efter |
| --- | ---: | ---: |
| Kall meny | 367,798 s | 332,434 s |
| Upprepad meny | 3,235 s | 2,922 s |

Det är cirka 9,6 % kortare kall beräkning i detta test. Detta är en enskild
lokal jämförelse, inte en garanterad svarstid för alla användarval. Separat
mikroprov, fem repetitioner om 10 000 identiska kassaprisanrop: median
0,522 s före och 0,062 s efter. Mikroprovet är inte en hel menymätning.

253 unika riktade testfall godkändes i avgränsade testgrupper, inklusive
slumpade uttömmande butikskombinationer, decimalflaggor/fällor, kampanjtak,
utgångsdatum, köprioritet, kommunbyte, uppstart, omladdning och avstängning.
Ruff och compileall godkända. Förberäkningens serialiserade cacheidentitet
regressionstestas mot en explicit webbförfrågan: standardvärdet 25 måste
serialiseras som 25.0. Första kandidaten aktiverades aldrig; den korrigerades
innan driftsättning.

## Förberäkning följd av en ny tjänsteinstans

Med webbens exakta mängdpolicy: förberäkning 278,410 s, ny tjänsteinstans
3,307 s. Menycachen gick från 0 träffar/2 missar till 2 träffar/2 missar:
båda sökningarna återanvändes utan ny miss. Recept, ingredienser, korg,
optimeringsalternativ, enbutiksalternativ och kvalitetsresultat är identiska.
Ingen nätverksåtkomst eller användarprofil användes. Detta är en annan
policy än före/efter-tabellens reproducerade fixture och jämförs inte med
367,798 s som ett ytterligare optimeringssteg.

## Begränsningar och minne

Förberedda villkor har högst 256 poster, 8 erbjudanden per post och storleksgräns
8 192 tecken vardera för rå och normaliserad representation. Exakta kassautfall
har högst 2 048 poster. Större eller icke oföränderliga indata går genom den
ursprungliga lösaren. Cachen behåller ingen användarprofil eller skafferidata.
Butiksrepresentationerna lever endast inom den redan begränsade offertsessionen.
Bakgrundskön har högst 64 väntande kommuner och 64 färdigmarkerade versioner;
ny version ersätter en väntande äldre version för samma kommun.

Detta förbereder en vanlig offentlig profil, inte alla kombinationer av kost,
antal portioner, butiksval och privata skafferier. Annat prisunderlag, annat
beräkningsdatum, ändrade villkor eller cacheutkastning kan kräva ny beräkning.
Personlig planering har fortsatt sin separata väg och egna användardata.

## Underlag

Privata fullständiga planer, loggar och återspelningar finns under
`.local/prepared-pricing-20261013/`. Prisunderlagets SHA-256:
`de54eafb81cf9bf47fd50a6a3e2a4d6929c88357b5e00b0c48009dbe98a0d2f6`.
Fryst klocka: `2026-10-13T07:19:51+00:00`.

## Driftsättning och slutprov

Aktiverad 2026-10-13 18:00:19 UTC: `ops-prepared-pricing-32127ccf7e14`,
image `sha256:3cf0bbe2ae5125015fad33d92955c5c7d7778ef8389c8fd00085ae62e4ff00a9`.
Kodcommits `ec542ccf38d2` och `32127ccf7e14`. Sex granskade appfiler lades
ovanpå aktiv `ops-menu-reuse-334aeb2fa2a8` efter kontroll av basfilernas hash.
Source/scheduler är kvar på `ops-price-recovery-7e28ff96f72d`. Endast appen
ersattes. Den orelaterade frontendändringen `1518101` ingår inte.

Operationslåset hölls under backup och aktivering. Befintliga 274 planrevisioner
och 90 privata tillstånd är radvis hashverifierat bevarade, också efter proven.
Prismanifest, volymer och övriga containrar bevarades. Miljöändringarna är
avgränsade till BUILD_ID och den dokumenterade förberäkningsprofilen.
Efter prov: 277 planrevisioner och 91 privata tillstånd. Inga nya OOM-händelser.

Både Lund och Malmö rapporterade slutförd förberäkning på sina aktuella
prisunderlag. Första därefter testade webbsessionen i Malmö: **9,719 s**.
En ny separat webbsession: **8,172 s**. Båda fick två menycacheträffar och
noll missar, samma resultat och 17/17 godkända kontroller. Inga sidfel;
återläsning var identisk. Tiderna är observerade prov, inte en generell SLA.

Personlig meny med en middag, två portioner och en vald Willys-butik:
68,6 s, godkänd kassaprisrevision och identisk återläsning, inga sidfel.
Det är ett funktionsprov; personlig planering är inte den offentliga
standardmenycache som förvärms. Någon förbättring av dess svarstid påstås inte.

Slutlig readiness: 200 på rätt build för båda kommunerna, 0,343/0,329 s.
Sammanställd evidens finns i [EVIDENCE.json](EVIDENCE.json). Fullständiga
privata planer, testbilder och transportloggar stannar i den ignorerade
arbetsmappen. Serverns backup/aktiveringsbevis finns under
`/opt/smako/evidence/ops-prepared-pricing-32127ccf7e14/`.
