# Basprisretention aktiverad på betan

Aktiverad 2026-10-15 07:22:47 UTC (09:22:47 svensk tid), efter användarens
uttryckliga instruktion "Aktivera och commita". Kodcommit `0f54e51`,
policy-/implementationsdokumentation `7c95fd6`, gren `fix/base-price-retention`.

Kvalificerade baspriser behålls tills de ersätts. Kampanjer och medlemsrabatter
följer sin giltighet för alla kedjor. Verklig observationsålder och
åldersvarningar kvarstår. Se [implementation och testurval](../../reports/base-price-retention-20261015.md).

## Driftsatta versioner

| Process | BUILD_ID | Image |
| --- | --- | --- |
| App | `base-price-retention-app-0f54e51` | `sha256:7ccbbfd7fe2f2edec89bd2a8a50fbbf2ff5791ff2ab7891f6ff5f759cd9c376a` |
| Scheduler | `base-price-retention-scheduler-0f54e51` | `sha256:13057faa6cdbdeb67e73345c1f6f2324c7ff084e25796d1f16febb91afa8935e` |

Bilderna byggdes utan nätverk ovanpå de verkliga, pinnade aktiva bilderna.
Kontroll av samtliga runtimefiler bekräftade exakt 25 ändrade appfiler och
26 ändrade schedulerfiler. Övriga 658/604 filer är byteidentiska.
Compose ändrar endast appens och schedulerns image och BUILD_ID. Proxy,
volymkonfiguration, scheman, Windowsrelä och manuella ops-profiler ändrades inte.
För ordinarie driftåtgärder gäller `scripts/smako_ops.py` mot scheduler;
de äldre manuella `refresh-once`-/`backup-once`-bilderna är inte denna release.

## Bevarad data och aktiveringsförlopp

Befintligt driftlås togs före aktivering. Inga nyliga menybegäranden eller
aktiv planner-CPU fanns. Båda SQLite-databaserna säkerhetskopierades med
online-backup och verifierades med `quick_check`; backupfilerna slutfördes
i DELETE-journalläge. Alla 278 befintliga planrevisioner och 92 privata
tillstånd bevarades enligt radhashar. Aktiva prismanifest är byteidentiska
före och efter bytet. Ingen databas återställdes och inga källtider skrevs om.

Den gamla schedulerns cron-process stannade inte vid TERM. Processinventering
visade endast cron och inget insamlingsjobb; den avslutades med KILL under
driftlåset så att ersättningen kunde starta. Appen startades separat under bytet.

Första efterkontrollen använde felaktigt kundpostnummer 22225 på `/ready`.
Den routen kräver registrerad områdeskod 22350 för Lund. Kontrollskriptet
avbröts utan återgång efter att både Lund och Malmö verifierats med korrekta
områdeskoder. Efterkontrollerna slutfördes under ett nytt driftlås.
Kundpostnumret 22225 testades genom `/api/shopping-location` och gav `eligible`.

## Driftresultat

- Lund `/ready?postal_code=22350`: HTTP 200, två äldre Willys-baskontexter
  åter användbara; 29 användbara kontexter totalt.
- Malmö `/ready?postal_code=21120`: HTTP 200, fyra äldre Willys-baskontexter
  åter användbara; 59 användbara kontexter totalt.
- Publicerat och laddat Lund-manifest är identiska. Willys 2176/2354 är
  fortfarande sanningsenligt `STALE`, men `base_prices_usable=true`.
- Windowsreläet har fortsatt väntande leverans/kvittens. Det separata öppna
  Willys-felet kring `hasPickingBaseStore` repareras inte av denna release.
  Automatisk hämtning av nya Willys-kampanjer är därför fortfarande begränsad.

## Prov på publik beta

- Chromium och WebKit: 22225 ger Lund och 29 inköpsställen. Alla nio
  måltidsdialoger fungerar och återlämnar fokus. Inga JavaScript-sidfel
  eller horisontell overflow vid 320, 390, 768 eller 1440 px.
- Ett verkligt knapptryck skapade middag, frukost och mellanmål, en portion
  vardera, på 161,5 sekunder. Resultatet använder den tidigare åldersspärrade
  Willys Lund-kontexten. Kassakontroll PASS, sju ingredienser kontrollerade,
  noll okända mängder och avstämd totalsumma 97,76 kr.
- Sparad GET gav identisk plan, som även återställdes vid omladdning.
- Båda ändrade serverade JavaScript-filerna matchar paketets SHA-256.
  Ny isolerad webbläsare använder shell-cache v17.
- Första webbläsarförsöket fick timeout under serverns cacheförberedelse
  efter omstart. Både Lund och Malmö slutförde förberedelsen; omprovet ovan
  passerade utan kod- eller konfigurationsändring.
- Det äldre publika menyflödet i Malmö gav HTTP 201 efter 11,625 sekunder:
  fem middagar, två portioner, 17 godkända acceptanskontroller, verifierad
  korg, avstämd totalsumma och identisk sparad GET/omladdning.
- Slutkontroll 07:36:25 UTC bekräftar samtliga ursprungliga radhashar även
  efter menyproven. Totalt finns nu 280 planrevisioner och 93 privata
  tillstånd; proven tillförde två planer och ett tillstånd. Noll nya
  OOM-händelser och noll automatiska containeromstarter.

## Evidens och återgång

[Sammanställd evidens](EVIDENCE.json). Privata loggar, paket och testunderlag
finns i `.local/base-price-retention/`.
Serverevidens: `/opt/smako/evidence/base-price-retention-0f54e51/`.
Databasbackup: `backup-20261015T071523Z/` därunder. Manifest, imagejämförelse,
original-compose, aktiveringsresultat och filhashar finns i samma evidenskatalog.

Vid återgång: verifiera först att compose fortfarande motsvarar denna release,
ta befintligt driftlås och invänta ledig app. Återställ sparad
`compose-wrapper.before` atomiskt och ersätt endast app/scheduler med
`up -d --no-deps --no-build --pull never app scheduler` genom wrappern.
Beakta att cron kan behöva stoppas separat efter kontroll att inga jobb körs.
Behåll aktuella datavolymer och databaser; återställ inte en äldre databas.
Kontrollera readiness, laddat/publicerat manifest och bevarade planrevisioner.
Föregående version återinför 48-timmarsspärren och kan därför åter ge 503.
