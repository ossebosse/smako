# Physical product identification V2

The camera decoder and product identification are separate stages. A successful
EAN/UPC scan is counted as a scanner success even when the active digital source
does not know that GTIN.

## Identity outcomes

| Outcome | Meaning |
| --- | --- |
| `GTIN_MATCH` | A checksum-valid scanned GTIN has explicit source evidence for the selected product. |
| `GTIN_MISMATCH` | The scan succeeded but conflicts with the selected product's verified GTIN. |
| `GTIN_NOT_KNOWN_BY_SOURCE` | The scan succeeded; the source has no verified GTIN for the selected product yet. This is not `NO_MATCH`. |
| `WEIGHT_ITEM_NO_GTIN_REQUIRED` | The selected source product is sold by weight and is identified without a package barcode. |
| `SHELF_CODE_MATCH` | Reserved for a future, explicitly proven shelf-code relation. |
| `SHELF_CODE_UNKNOWN` | A shelf code was decoded and stored only as non-authoritative diagnostic evidence. |
| `MANUAL_EXACT_MATCH` | The user explicitly confirmed the exact preselected source product. |
| `NO_MATCH` | The physical item cannot safely be connected to the selected source product. |

The evidence type is stored separately (`gtin_verified`, `source_product_manual`,
`weight_source_product`, `shelf_code_verified`, or `unverified`). Historical V1
`exact` observations remain readable.

## Hemköp GTIN enrichment

Normal catalog refresh still performs zero bulk product-detail enrichment. A
field session first checks the persistent identifier registry. Remaining exact,
non-weight Hemköp targets can then use the approved public product-detail route,
one exact product per bounded API call. The collector:

1. activates and reads back the exact allowlisted Hemköp store in a fresh anonymous session;
2. requests the exact persisted external product ID;
3. requires response `code` to equal the requested ID;
4. accepts only an explicit checksum-valid `ean` field;
5. stores sanitized raw evidence before recording the identifier mapping; and
6. discards cookies and CSRF state when the request ends.

The mapping registry is separate from promoted price snapshots. It accumulates
across future field sessions, while source evidence remains scoped conservatively
to its verified store context. No identifier is derived from an image URL or an
internal article number.

On 2026-08-29, one bounded live detail lookup for Karhögstorg product
`101230686_ST` returned the explicit, checksum-valid `ean` `7391737003437` for
Finbröd Skånskt 700 g. The sanitized raw response was stored and the exact
store-scoped relation was added to the identifier registry. This is source
evidence, not a hardcoded barcode relation, and no physical-price observation
was created by the lookup.

## Weight products

Verified `sold_by_weight` and `variable_weight_package` products are presented as
`VIKTVARA / kr per kg`; an estimated online package weight is not shown as the
physical identity. A field capture records the current shelf value in `SEK/kg`,
an optional regular shelf value, and a separate type (`regular`, `sale`, `member`,
or `unknown`). Fixed or piece products are not silently converted to weight goods.

## Shelf-code diagnostics

Product mode scans EAN-13, EAN-8, UPC-A and UPC-E. Shelf mode uses ZXing with
Code 128, Code 39, ITF, EAN/UPC, RSS-14 (GS1 DataBar) and RSS Expanded. Shelf
mode preserves only the raw decoded value, format, selected store/product context
and timestamp. It never normalizes the value as GTIN and never creates a price
observation. A shelf relation remains unverified until several real paired scans
prove stable semantics.

## Next Karhögstorg field check

1. Start a 20-item blind session before or during the visit and let the bounded
   identifier preparation advance. Products without source GTIN remain usable.
2. Packaged product: scan the package EAN. Continue on `GTIN_MATCH`; on
   `GTIN_NOT_KNOWN_BY_SOURCE`, fetch the one product detail or explicitly confirm
   the selected product. Mark `NO_MATCH` only when it is genuinely the wrong or
   unidentifiable item.
3. Loose weight product: do not scan a barcode. Enter the current shelf price in
   kr/kg, its price type, and the optional regular kr/kg value.
4. Hemköp `Självscanna` label: use **Diagnostisera hyllkod**. Record at least three
   decoded formats/raw values; do not treat them as GTIN yet.

No camera image is uploaded or persisted, and physical samples never overwrite a
digital catalog price.
