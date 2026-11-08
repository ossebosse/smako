# Snabbare sökning vid tre butiker och medlemsbesparingsfix aktiverat

Aktiverad **2026-11-08 08:58 UTC** på https://beta.smako.nu.
Main `979312084e7c`, app **app-979312084e7c-84cf5cea** (bild `sha256:1e3aab9411ad…`, bas = föregående app
`app-e02a2ef7f0db-1d6fdb43`). Schedulern orörd. Ägaren bad 2026-11-08 om åtgärd och aktivering.

## Ändring (två filer)

- `basket_optimizer.py` (`9793120`): med många butiker som säljer menyns varor (Malmö ≈ 42)
  räknades varje butiksmängd med högst tre butiker upp, ≈ 12 000 delmängder per varurad och
  menyförslag. Tak tre använder nu den befintliga exakta butiksmängdssökningen från ca 23
  butiker, med bästa tvåbutiksnyckel som startgräns; tak 1–2 räknas upp som förut. Sökningen
  beskär bara mängder som är strikt sämre, så nycklar och valda menyer är oförändrade (nytt
  test jämför mot full uppräkning).
- `membership_reporting.py` (`8943b12`): menyn faller inte längre när medlemsbesparingen
  inte kan prissättas (Lunds HTTP 500 vid 1 portion/3 butiker).

## Verifiering

- CI grön för `9793120`. Bygget: endast de två filerna ändrade, 1 391 oförändrade.
- Aktivering: backup `/srv/smako/backups/20261108T084904Z`, bevarat 348 planversioner,
  151 privata tillstånd, 2 konton, 1 session. Lagringsunderhåll före och efter: complete.
- Lokal omspelning mot universumen från 7/11 (samma resultat före/efter): Malmö 1/3
  63,4 → 18,5 s; Malmö 2/3 deadline → 53 s; Lund 1/3 17,0 → 15,5 s; Lund 2/3 23,9 → 23,1 s.

## Publika tider (ny gäst, 3 recept, direkt efter aktivering)

| Postnummer | Portioner / max butiker | Före | Efter |
|---|---|---|---|
| 21120 Malmö | 1 / 3 | 64 s, SEARCH_INCOMPLETE | 39,9 s, plan |
| 22350 Lund | 1 / 3 | HTTP 500 | 30,2 s, plan |
| 21120 Malmö | 2 / 3 | – | 61,9 s, SEARCH_INCOMPLETE |
| 21120 Malmö | 2 / 2 | 38,4 s | 35,9 s |
| 21120 Malmö | 2 / 1 | 34,6 s | 22,2 s |

## Kvarvarande

Malmö 2 portioner/3 butiker hinner fortfarande inte inom 60 s på servern (lokalt 53 s).
Fyra eller fler butiker i Malmö gick inte heller före ändringen (lokalt > 100 s). Tiden går
nu till själva butiksmängdssökningen (≈ 7 500 anrop), tak 1–2-uppräkningen och den
efterföljande "varierad"-sökningen.
