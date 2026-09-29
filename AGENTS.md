# Project rules

- Preserve the existing snapshot, source-strategy, promotion, PriceUniverse,
  GroceryContext, PhysicalStore, provider and CLI architecture. Do not create
  parallel pricing, promotion, assortment or refresh systems.
- PriceUniverse is shared and source-driven. Community evidence stays advisory,
  and `USER_SPECIFIC` offers must never enter the shared artifact.
- Keep product identity and price scope exact. Fuzzy names may suggest manual
  review but must never attach authoritative prices automatically.
- `own:coop:730400` is Coop Online Syd: `ONLINE_FULFILLMENT` with
  `online_price`. It is not a physical Lund shelf-price context. Keep Coop's
  physical offer feeds separate.
- Production Coop crawling is restricted to
  `COOP_ALLOW_FULL_CRAWL=true` and `COOP_ONLINE_CONTEXT_IDS=730400`. Never
  broaden this allowlist without separately verified source and scope evidence.
- Refreshes must retain valid LKG data on failure, validate candidates before
  atomic activation, report truthful source age, and use the shared operation
  lock. Never overlap a full refresh, source retry, backup or activation.
- Do not weaken freshness or quality gates to make status green. The default
  source states are FRESH under 36 h, AGING from 36 h, and STALE at 48 h.
- Never log, document or commit secrets, retailer credentials, raw receipt
  contents, cookies or browser/session identity. Do not implement challenge
  bypasses or undocumented retailer login automation.
- Preserve user work in this directory. Do not reset, clean, or remove data
  unless an exact disposable target has been verified first.
- Use Python 3.12. After relevant changes, run focused tests, Ruff and
  compileall; reuse unchanged, hash-stable verification instead of needlessly
  repeating expensive live collections.

- Permanent municipal acceptance: Coop, Stora Coop and X:-tra must use the same
  official municipality parameter through discovery, store-bound collection,
  validation, OWN, PriceUniverse and refresh selection. Verify Lund and another
  municipality with the same code; distinguish live network evidence from
  retained-data tests. X:-tra publications must come from each official store's
  current source links, never a fixed Skansvägen URL or saved Lund flyer.
  Preserve every discovered/unknown/failed store in coverage and report unknown
  PDF layouts explicitly. This never expands existing user area/store choices
  or authorizes production activation or changes to the pending ICA release.
