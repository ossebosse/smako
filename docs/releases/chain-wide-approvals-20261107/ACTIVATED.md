# Kedjeövergripande produktgodkännanden aktiverat

Aktiverad **2026-11-07 19:08 UTC** på https://beta.smako.nu.
Main `e02a2ef7f0db`, app **app-e02a2ef7f0db-1d6fdb43** (bild `sha256:31fd3898675f…`, bas = föregående app
`app-bdd956c7351d-f0f775c9`). Schedulern orörd. Ägaren godkände 2026-11-07 19:48 lokal tid.

## Ändring (två filer)

`intake_product_links.py`, `reviewed_ingredients.py`: en granskad vara med GTIN eller
artikelnummer gäller i alla butiker i samma kedja (granskade länkar, mängdgranskningar och
utfärdade ingrediensförteckningar). Exakt etikett, förpackning, källa och förteckning krävs
fortfarande. Receptförsörjningskontrollen på samma data: Lund 233 → 85 blockerade
ingrediensgrupper och 1 741 → 659 blockerade av 2 851 receptvarianter; Malmö 47 → 46 och
216 → 209.

## Verifiering

- CI grön för `e02a2ef`. Bygget: endast de två filerna ändrade; kandidatbilden importeras
  isolerat (utan nätverk, skrivskyddad).
- Aktivering: backup `/srv/smako/backups/20261107T185850Z`, bevarat 343 planversioner, 151 privata tillstånd,
  2 konton, 1 session. Lagringsunderhåll före och efter: complete.
- `/ready/preparation` 21120 och 22350: 200, bibliotek ready, rätt BUILD_ID.

## Publika tider (ny gäst, 3 recept, före = app-bdd956c i drift sedan 14:10, efter = nystartad app)

| Postnummer | Portioner / max butiker | Före | Efter |
|---|---|---|---|
| 21120 Malmö | 2 / 1 | 22,5 s | 34,6 s |
| 22350 Lund | 2 / 1 | 17,1 s | 24,6 s |
| 21120 Malmö | 2 / 2 | 46 s (första efter 14:10) | 38,4 s |
| 22350 Lund | 2 / 2 | 30,2 s | 25,2 s |
| 21120 Malmö | 1 / 3 | 64 s, SEARCH_INCOMPLETE | 64 s, SEARCH_INCOMPLETE |
| 22350 Lund | 1 / 3 | 21,6 s, HTTP 500 | 21,6 s, HTTP 500 |

Enstaka mätningar med olika uppvärmning; ingen entydig förändring.

## Kvarvarande fel (fanns före aktiveringen)

Lund, 1 portion och högst 3 butiker: `ValueError` i `fixed_checkout_price.resolve_effective_price`
via `membership_reporting.fixed_basket_membership_savings` gör att hela menyn misslyckas
(incident `app-1e224402553ea8244e87`). Malmö samma val når tidsgränsen (SEARCH_INCOMPLETE).
