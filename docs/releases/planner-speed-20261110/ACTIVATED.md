# Snabbare menysökning aktiverat

Aktiverad **2026-11-10 19:49 UTC** på https://beta.smako.nu.
Main `82b9ce411660`, app **app-82b9ce411660-7332b1f6** (bild `sha256:7732ebd892dd…`,
bas = föregående app `app-78c2649a2bf2-083247bf`, `sha256:21cb9593576f…`).
Schedulern orörd. Ägaren bad om aktivering 2026-11-10 20:25 lokal tid ("Ja aktivera").

## Ändring (tre filer)

- `442d822` – butiksmängdssökningen: varje varas sökrader byggs en gång per
  offertsession; sista butiken prissätts direkt och överges så fort den inte
  kan slå den bästa.
- `b1b1bf0` – exakta butiksnycklar delas mellan menysökningens två omgångar i
  samma förfrågan (`requirement_key_scope`); nyckelläget beskär oavgjorda fall;
  gräns i öre vid en verifieringsnivå; lättare kampanjkontroller.
- `82b9ce4` – lat ordning: väntande menyer ordnas efter ett golv som aldrig
  överstiger nyckeln (billigaste offerten per rad över alla butiker), och
  nyckeln räknas först när menyn når fram. Samma ordning, samma menyer.

Alla ändringar är exakta: hela planens svar är identiskt före/efter, utom
diagnostikräknarna i `operation_counters`.

## Verifiering

- CI `tests` grön för `442d822`, `b1b1bf0` och `82b9ce4`.
- Paketet: bas `cd8e16b` (inga appfiler ändrade sedan `78c2649`; intervallet
  `78c2649..cd8e16b` innehöll bara image-rensningens deploy-filer, redan
  installerade 2026-11-09). Bygget: endast de tre filerna ändrade, 1 391
  körtidsfiler oförändrade.
- Kandidatbilden isolerat (utan nätverk, skrivskyddad, Malmöunderlag 9/11,
  klocka 9/11 21:00 UTC): Malmö 2/3 36,7 s med identiskt svar som aktiv app.
- Mätningar i isolerad container, aktiv app → denna version, identiska svar:
  Malmö 2/3 117,3 → 37,9 s; 2/4 269,8 → 45,8 s; 2/2 36,1 → 19,0 s;
  1/3 36,2 → 14,6 s; 2/1 19,4 → 11,3 s; Lund 2/3 21,9 → 15,2 s; 1/3 10,0 → 8,4 s.
- Aktivering: backup `/srv/smako/backups/20261110T194041Z`; bevarat 358
  planversioner, 153 privata tillstånd, 2 konton, 2 sessioner.
  Lagringsunderhåll före bygge, före och efter aktivering: complete.
- `/ready` 22350 och 21120: ready, `app-82b9ce411660-7332b1f6`.
  `/ready/preparation` 21120: 200, ready.
- Publikt prov, ny gäst, 3 recept: Malmö 21120 2 portioner/3 butiker skapad
  på 39,8 s (tidigare SEARCH_INCOMPLETE vid 60 s), återläst 200; upprepad
  förfrågan 8,0 s (menycache), 102,15 kr, tre butiker, rader VERIFIED.
  Lund 22350 1/3: 19,6 s, 76,71 kr, VERIFIED.

## Genomförande

Hjälparens bygg- och aktiveringsjobb (oförändrad workerkod och samma
lagringsunderhåll) kördes fristående på servern via `nohup` och följdes via
logg, eftersom sessionens skal avbryter kommandon efter cirka tre minuter.
Tillfälliga filer i `/tmp` är borttagna.

## Kvar

- Gästgränssnittet tillåter 1–3 butiker; fyra butiker (2/4 nu 46 s) gäller
  bara vyer som tillåter fler butiker.
- Numpy-försöket ligger på grenen `perf/numpy-store-keys` och införs inte.
