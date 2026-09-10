# Deferred: ICA OWN acquisition research

Status: **DEFERRED — not executed in the 10 September 2026 unattended Willys milestone.**
Primat remains ICA's production source. These are future hypotheses and evidence
review tasks, not new verified acquisition capabilities. No ICA live requests,
browser experiments or offline request comparisons were performed for this item.

1. Build a historical attempt matrix: client, location, request contract,
   browser/session type, response and date. Keep local versus VPS evidence explicit.
2. Offline-diff Smako requests against the then-current `ica-cli`: store base URL,
   method/path, query encoding, Accept, Accept-Language, Referer, User-Agent,
   redirects/session behavior and 202/403/405 classification. A diff is diagnostic,
   not authorization to evade an access challenge.
3. Before further direct HTTP experiments, manually re-check ordinary anonymous
   public ICA website behavior in a clean browser.
4. Only if ordinary public browsing works, investigate **passive** capture:
   normal operator browsing → observe already-occurring relevant product responses
   → sanitized export. No extra API requests; no cookies, authentication, CSRF,
   customer information or session material in exported artifacts.
5. Qualify incrementally: one product → one complete category → continuation and
   pagination → category tree → only then complete catalog. Retain completeness
   evidence and stop on access challenges.
6. Revisit the reported historical evidence of approximately 57 category product
   IDs, approximately 50 with SSR metadata, and PUT
   `/stores/{store}/api/webproductpagews/v6/products` returning structured
   store-specific product/pricing data before later challenge behavior. These
   observations are historical leads to verify from saved evidence, not current
   endpoint availability or enumeration proof.
7. Review saved response classifications: normal HTML, unexpected API HTML, and
   explicit CAPTCHA/challenge. Do not treat every HTML response as equivalent.
8. Exclude CAPTCHA bypass, stealth plugins, proxy/IP rotation, customer login or
   session replay, brute-force hidden endpoint/product IDs, and source-gate weakening.
9. Primat remains production unless a future ICA OWN candidate proves completeness,
   exact identity, authoritative package semantics, store scope, price semantics,
   campaign applicability and freshness through the normal qualification path.
   Existing ambiguous/personal/unsupported cases stay excluded. Physical shelf
   inventory is not established by an online source.
10. Preserve the alternative of a **retailer/store-authorized CSV or JSON feed**
    as an ICA OWN acquisition source, subject to the same qualification gates.

Starting references for a future milestone (read then; no new investigation here):

- [Existing ICA source notes](ica.md)
- [ICA CLI research report](../../reports/smako-ica-cli-research-20260909.md)
- [Explicit local/home and VPS follow-up](../../reports/smako-ica-local-home-20260909.md)
- [Current Primat quality acceptance](../../reports/smako-automation-ica-20260909.md)

Next action: explicitly scope a future research milestone; this backlog item does
not authorize background browsing, retailer requests or automatic future execution.
