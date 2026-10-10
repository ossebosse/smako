> Uppdatering 2026-10-10 10:04 UTC: denna kandidat är nu aktiverad efter
> återställd prisdrift. [Utfört byte och slutprov](../source-return-recovery-20261010/ACTIVATED.md).
> Texten nedan bevarar läget vid den tidigare leveransen före aktivering.

# Återkomst till sparad inköpslista, 2026-10-10

**Appfix implementerad och paketerad, inte aktiverad. Beta är fortfarande
blockerad för nya beräkningar av för gamla obligatoriska Willys-priser.**
Ingen produktionsskrivning, insamling, rensning, reläändring eller Git-push i detta ärende.

## Belagda fel

Vid 06:37 UTC och återkontroll 06:55 UTC gav beta `/ready` 503;
PlanStore och databasen var OK. App `shopping-list-6b10628f22d8`, laddat
manifest `2c32fcefb1c4d2b92f88856b3bceb1727baff514bc8a8833074cfd06ae348341`.
Willys 2176/2354 var 55,40/55,06 timmar gamla vid sista kontrollen.
Detta är ett prisdriftfel, inte belägg för att användarens session löpt ut.

Befintlig `scripts/smako_ops.py status` och appincidenten
`app-891b10b6a8c192b4e2c0` hittade POST `/api/plans` 503 före jobbadmission:
`X-Error-Code: price_universe_unusable`. Requestreferenser
`9b05ebdf-bba0-4d95-af19-74c1e059e2fb` 06:33:11 UTC och
`9f3ce20a-7b02-475d-a945-3d3f082d4ea0` 06:34:25 UTC upprepades under samma ID.
Inget jobb/plan skapades av dessa avvisade anrop. Ingen exceptionkedja krävs
för avsiktlig HTTPException. Tiderna är metrikens lagringstid; skärmbilden
saknar requestreferens så exakt ägarkorrelation kan inte beläggas.

Frontend behandlade alla sådana 503 som transportfel och visade exakt texten
på bilden, behöll väntemarkören och låste knappar. Samma fel reproduceras med
produktionssvarets status/header/body i både Chromium och WebKit på förekoden.
Ett andra kodfel gjorde att personlig uppstart försökte återansluta före
läsning av sparad revision; en utgången obekräftad startmarkör rensades inte.

## Rättning

- Gemensamma statusläsaren behandlar de två exakta prisblockeringskoderna som
  slutligt avvisade försök, efter svarsschemavalidering. Ett POST, ingen
  automatisk omstart eller falsk kvarvarande jobbmarkör.
- Sparad plan och varuval läses först. En äldre sparad plan rensar inte en
  nyare pågående jobbmarkör. Navigation mellan vyer förblir tillgänglig.
- Ett slutligt 404 efter befintlig 30-sekunders upptäcktsperiod rensar även
  obekräftad start. Utgånget jobb får begripligt besked och knappar återställs.
- När nytt sparat resultat tagits emot rensas jobbmarkören före sekundär
  tillståndsläsning och resultatet renderas först.
- Ägarskydd, cookies, sessionStorage-modell, retrygränser, prisgränser,
  databas, recept, näring och planner är oförändrade.

## Verifiering

Runtime `205cd8ca0f31` (fullt ID i EVIDENCE.json).
28 fokuserade tester lokalt och 28 mot leveransimagen passerar.
Ruff, compileall och diffkontroll passerar.
Mobil layout 390×844 i Chromium och WebKit: verklig fristående korg via
knappen, dubbelklick ett POST, checkout/audit, oförändrad sparad GET,
fel ägare 403. Injekterade prisblockeringar, gamla kända/obekräftade jobb,
statusreset med samma verkliga jobb/resultat, 401/403, temporär 503,
oväntad HTML och förlorat startsvar provas separat. Inga oväntade pageerrors
eller requestfailed; två avsiktliga resets per webbläsare bevaras i evidensen.
Publik knapp: prisgate stannar efter ett POST och lämnar inga väntemarkörer.
Felinjektion är inte liveproduktion eller bevis för iPhone/Safari på fysisk enhet.
Verkliga korgar använder oförändrad isolerad historisk replay, inga dagsprispåståenden.
Slutprov körs utan källkodsmount. Alla fyra HTTP-serverade filer matchar paketets hash.

Misslyckade testförsök bevaras privat under `.local/return-session-20261010`:
först felaktig route-capture, sedan testmarkör i fel lagring och hash-navigation
utan dokumentbyte; dessa testverktygsfel korrigerades före slutproven.
Ett äldre statiskt test förväntade direkt fetch trots befintlig jobRequest;
assertionen uppdaterades till verkligt kontrakt. Första paketerade pytest
saknade uttrycklig laddning av tillgängliga asyncio-plugin; två asyncprov
kunde inte köras. Korrigerad körning med `-p pytest_asyncio.plugin`: 28 PASS.
Första paketbrowserstart före readiness misslyckades; en bounded readinesskontroll
lades till i testverktyget. Publik routeinjektion körs med service workers
blockerade i testkontexten så att testets POST säkert fångas; första försöket
med aktiv worker fångade inte POST och räknas inte som lyckad felinjektion.

## Separat kvarstående prisdrift

Den redan hämtade Willys-snapshoten `75f802ebbfcc410c9d65e356746f0816`
stoppas i schemaqualification: sex exakta image/thumbnail-fält i butik 2354
har observerat typset null|string → string. Hemköps snapshots
`eb7f4129141c4bd892702f0c5abc3b56` och `0f1daad517a74f8fb9066cdf069ba7c1`
stoppas när det granskade optionalfältet hasPickingBaseStore saknas på två
platser. Exakta diffar finns i DIAGNOSIS.json. Ingen generell schemaacceptans gjord.
Den vanliga bounded reproduceraren stoppade Willys-fallet på 32 MB-gränsen;
det är inte ett godkänt replayprov. Råreferenser finns i det skyddade källunderlaget.

Servern hade 5 202 354 176 lediga byte mot befintlig importmarginal
8 693 828 112 byte vid 06:55 UTC. Minst 3 491 473 936 byte saknas enligt
befintlig modell; detta är inte bevis för ny ENOSPC eller exakt framtida behov.
Fortsatt driftreparation behöver avgränsad råreproduktion/schemaändring med
negativa prov, versionsbundet källpaket, verifierad kapacitetsmarginal och
ordinarie replay/publicering/kvittens. Appfixen i denna leverans utför inget
av detta och får inte beskrivas som återställd prisdrift.
