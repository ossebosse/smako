# Mina val: Din mat, Inköp, Pescetariskt och tre lägen för omväxling aktiverat

Aktiverad **2026-11-05T20:39:14.514626+00:00** på https://beta.smako.nu.
Main `431ddb3ac0f2f1c97fc3fc8d2ad2d52edc8bfc91`, app **app-431ddb3ac0f2-28522b51**
(bild `sha256:53020af2a5ce…`, bas `sha256:a396c7774515…`). Schedulern är orörd
(`source-ops-e6d4ceaca5bc`). Ägaren beslutade 2026-11-05 att aktivera hela main.
Main-CI grön för [f2bdb9b](https://github.com/ossebosse/smako/actions/runs/42098774572),
[2ae1afa](https://github.com/ossebosse/smako/actions/runs/42101615218) och
[431ddb3](https://github.com/ossebosse/smako/actions/runs/42102623155).

## Innehåll

Releasen tar appen från Git-basen `78403f6154cd` till main: 424 filer under
`backend/app/`, varav 381 nya (främst receptdata). Utöver den här ändringen
följer alla appcommits sedan 2026-11-01 med som aldrig hade aktiverats:
språkgenomgången av texter och servermeddelanden, granskade receptvarianter
och receptspråk, samt adminfilerna som redan körde i runtime.

Den här ändringen (`2d86696`, `7caf8b8`, `f2bdb9b`):

- Mina val på mobil: Smak, Recept och Mer blir **Din mat**; Butiker och
  inköpsvalen blir **Inköp**. Åtta steg blir sex.
- En lista **Gillar** och en **Undvik**. Undvik ersätter "undvik om möjligt"
  och "utesluta"; kända allergener kan markeras som allergi och behåller
  allergen- och spårkontrollen. Äldre "undvik om möjligt" flyttas till Undvik.
- Recept: Omväxling (Lite/Lagom/Mer), aktiv tid och ingredienser som snabbval;
  alla detaljgränser under "Anpassa i detalj". Lite är den tidigare
  standarden och förvalt; Lagom är minst tre matkök och högst två middagar
  per huvudprotein; Mer är så många matkök som middagarna medger och aldrig
  samma huvudprotein två gånger.
- Nytt kostval **Pescetariskt** i app och server (vegetariskt plus fisk och
  skaldjur). "Tillåt fisk" visas bara för återställda planer som har stängt av fisk.

## Förfarande och avvikelser

- `prepare` stoppade på nio grocery-filer i intervallet, levererade till
  schedulern genom de fyra schedulerreleaserna 2026-11-04–05. Appbilden har en
  egen, äldre grocery-kopia (`schema_review.py` och `collector.py` matchar inte
  basen). `beta_release.py prepare --keep-app-grocery` (`431ddb3`) lämnar dem på
  appbildens version och listar dem i granskningen. Ingen ändrad appfil ändrar
  sina importrader mot dem; `store_operations.py` fick bara nya texter.
- Bygget kördes med verktyget. SSH-anropet bröts av klientens tidsgräns efter
  175 s medan `docker build` fortsatte på servern. Arbetaren skrev
  `candidates.json` efter alla kontroller (endast granskade filer ändrade,
  plattad konfiguration verifierad); den filen sparades som lokalt `build.json`.
- Aktiveringen kördes med exakt samma kod som `activate --checks-passed`
  skickar (CONFIG + arbetare), men startad fristående på servern med utdata
  till `/tmp/activate-app-431ddb3ac0f2-28522b51.out`, så att en bruten
  anslutning inte kunde avbryta mitt i bytet. Lagringsunderhåll före och efter
  kördes som i verktyget; båda complete.

## Verifiering

- Kvitto: endast appen bytt, enda miljöändring BUILD_ID, prismanifest och
  mountar bevarade, driftlås taget, CPU lugn (0,02/0,03). Bevarat:
  333 planversioner, 147 privata tillstånd, 2 konton, 1 session.
  Backup `/srv/smako/backups/20261105T203020Z`.
- `/ready` för 22350 och 21120: ready, `app-431ddb3ac0f2-28522b51`.
  `/personal` levererar `personal.js?v=20261105-dinmat2`.
- Importkontroll av kandidatbilden utan nätverk: `app.main` och
  `DietPreference("pescetarian")` laddar.
- Publikt prov, ny gäst, Lund 22350, 18 butiker inom 3 km, högst två: tre
  pescetariska middagar, en fisk, Lagom omväxling. Svar på cirka 49 s
  (köad 20:44:52, skapad 20:45:41 UTC). Italiensk ärt- och valnötspasta,
  grekisk bakpotatis med svamp och feta, krämig laxsoppa: tre matkök, en
  fiskrätt. Köpkontroll VERIFIED, 278,70 kr (46,45 kr/portion). Planen
  `4acebd77-…` återlästes med samma ID, version 1 och nytt bygge.
  En enstaka kall mätning; ingen tidsgaranti påstås.

## Nästa bas

Nästa appflöde utgår från `431ddb3ac0f2`.
