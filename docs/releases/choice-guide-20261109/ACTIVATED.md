# Mina val: Frågor aktiverat, plus daglig rensning av Docker-images

Aktiverad **2026-11-09T18:04:15Z** på https://beta.smako.nu.
Main `78c2649a2bf26ce3513d7a883cdad4471b6eae7a` (PR #70), app **app-78c2649a2bf2-083247bf**
(bild `sha256:21cb9593576f…`, bas `sha256:1e3aab9411ad…` = `app-979312084e7c-84cf5cea`).
Schedulern är orörd (`source-ops-e6d4ceaca5bc`). Ägaren beslutade 2026-11-09 att slå ihop och aktivera.

## Innehåll

Sex filer under `backend/app/static/`: ny `choice-guide.js` (Frågor, fjärde mobilvisningen
av Mina val), `configurator.js/.css`, `personal.js` (exponerar Gillar/Undvik för guiden),
`personal.html` och `service-worker.js` (cache v39). Se `docs/CHOICE-GUIDE.md`.

## Förfarande och avvikelser

1. `prepare --from-commit 979312084e7c --commit main` och `build` gick igenom
   (endast granskade filer ändrade, plattad konfiguration verifierad, importkontroll OK).
2. Första `activate` stoppade före bytet: kravet på 8 GB ledigt, servern hade 7,3 GB.
   Ägaren godkände engångsrensning och daglig automatik (PR #71,
   `deploy/scripts/image_retention.py`): 143 av 231 images togs bort, ledigt 7,8 → 123,9 GB.
   Kvitto `/opt/smako/evidence/image-retention/latest.json`. Timern
   `smako-image-retention.timer` installerad och aktiverad (dagligen 13:17 UTC).
3. Andra `activate` kördes från en molnsessions skal vars bakgrundsprocess avslutades
   när anropet tog slut. SSH-röret bröts under backupen; arbetarens utskrift av
   `app_replaced` misslyckades och den återställde till `app-979312084e7c-84cf5cea`
   enligt sin felväg (ca 15 min, `--timeout 900`). Ingen data ändrad; ny app kördes
   kort innan återställningen.
4. Tredje försöket: samma kod som `activate --checks-passed` (CONFIG + arbetare, efter
   `maintain_target`) startades fristående på servern med utdata till
   `/tmp/activate-78c2649.out`, som 2026-11-05. Lyckades.

Lärdom: starta alltid aktiveringen fristående på servern när klienten inte är en
egen terminal som lever hela körningen.

## Verifiering

- Kvitto: endast appen bytt, enda miljöändring BUILD_ID, prismanifest och mountar
  bevarade, driftlås taget, CPU lugn (0,03/0,01). Bevarat: 352 planversioner,
  151 privata tillstånd, 2 konton, 1 session. Backup `/srv/smako/backups/20261109T175534Z`.
- `/ready` för 22350 och 21120: ready, `app-78c2649a2bf2-083247bf`.
- `/personal` levererar `choice-guide.js?v=20261109-guide` (HTTP 200).
- Disk efteråt: 116 GB ledigt (71 %).
